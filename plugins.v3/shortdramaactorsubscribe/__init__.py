"""短剧演员订阅（MoviePilot V3 插件后端）。

一句话：把喜欢的**短剧演员**填进来，插件从**短剧百科**抓回他们的全部作品，摆成一面
和宿主「探索」页同形的海报墙；想追哪部点「订阅」，走的就是**宿主自己的订阅系统**。

这个插件**不做什么**
--------------------
2026-10-15 整体重写，删掉了一整条自建链路（站点搜索 / 择优下载 / 账本去重 / 自建订阅表
/ 自建整理入库 / 自写 NFO）。原因只有一条：这些宿主都已经有了 ——

* **订阅**：宿主订阅系统吃显式媒体身份（``media_source`` + ``media_id``），而短剧百科
  已经作为一等媒体数据源接入了宿主框架（能出卡片、能开媒体详情页），所以订阅直接交还给
  系统：插件面板上的「订阅」按钮调宿主注入的 ``nativeSubscribe``，弹出来的就是系统自己的
  订阅对话框，建出来的就是系统订阅，搜索 / 下载 / 整理全由宿主负责。
* **识别与刮削**：同理交给百科数据源与宿主刮削链，插件不再自己写 NFO。

插件现在只负责**发现**：演员 → 百科作品 → 作品墙 → 交给系统。

发现源 = 只有短剧百科
---------------------
作品 100% 来自 ``ShortDramaBaikeSource``（duanjubaike.org）。走**跨插件模块方法**
（``search_actors`` / ``actor_works`` / ``actor_profile``，经 ``self.chain.run_module``
分发；注意 ``get_module()`` 白名单没登记的名字是**静默拿空**，不会报错）。

⚠️ V3 SDK 的 ``_PluginBase`` **不继承** ChainBase，``self.run_module`` 不存在，
必须走成员 ``self.chain``（生产实证过的坑）。

演员解析纪律：站外索引的候选**含模糊结果**（搜「王石」会带出「王碩」），因此只收**归一化
名字精确相等**的候选；解析出的百科 ID 缓存进快照，后续轮次零引擎请求。

「新作品」口径
-------------
``first_seen``（作品首次出现）晚于该演员的 ``baseline_at``（加入时的基线）、且距今在
3 天窗口内 ⇒ 标「新」。刻意不用「相对上一轮快照新增」—— 那个口径只活到下次刷新。
基线那一轮的作品天然不算新，否则一次导入十几位演员会整片标新。

V3 契约要点
-----------
1. **依赖入口**：宿主依赖一律走 ``app.sdk.*``。
2. **渲染模式**：``vue``（Vue 模块联邦）。配置页 / 详情页 / 仪表板 / 侧栏全页由
   ``dist/assets`` 里的联邦组件渲染，后端只提供 ``get_api()`` 接口。
3. **不在模块导入期**做网络、数据库或任务启动。
4. **插件类的运行时容器必须在 ``init_plugin`` 里重新赋值**（宿主 reconcile 会反复重建
   实例，类属性字典会跨实例串味）。
"""
from __future__ import annotations

import re
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from apscheduler.triggers.interval import IntervalTrigger

from app.sdk.events import Event, eventmanager
from app.sdk.logging import logger
from app.sdk.media import MetaInfo
from app.sdk.plugin import _PluginBase
from app.schemas.types import EventType

# 消息类型枚举在宿主版本间存在改名：V3.1+ 使用 MessageType，更早的实现使用 NotificationType。
try:  # pragma: no cover - 取决于宿主版本
    from app.schemas.types import MessageType as _MessageType
except ImportError:  # pragma: no cover
    from app.schemas.types import NotificationType as _MessageType  # type: ignore

# 插件展示名，同时作为通知标题
PLUGIN_NAME = "短剧演员订阅"

# ─────────────────────────── 常量 ───────────────────────────

# 演员作品快照（插件数据，不是配置）
_DATA_ACTORS = "actors_state"

# 解析失败重试间隔（分钟）。「上一轮失败」是可自愈的，等满一轮发现间隔恢复体验太差，
# 所以单独按短间隔重试（演员快照的保鲜期 = 发现间隔，见 snapshot_ttl_seconds）。
_DEFAULT_RETRY_MINUTES = 20

# 快照时间戳格式
_STAMP_FORMAT = "%Y-%m-%d %H:%M:%S"

# 「新作品」的时间窗（天）：作品在**演员加入之后**首次出现起，N 天内标「新」。
_NEW_WINDOW_DAYS = 3
_NEW_WINDOW_SECONDS = _NEW_WINDOW_DAYS * 24 * 3600

# 唯一发现源标识（短剧百科作为宿主媒体数据源的标识）。
#
# ⚠️ 必须用**规范标识** ``duanju``（与 ShortDramaBaikeSource 的 ``MEDIA_SOURCE_KEY`` 一致）：
# 官方插件开发文档要求「通用媒体身份必须同时包含 media_source + media_id，不要在通用
# 链路中只保存裸 ID」，而宿主侧的分类规则（``sources: ["duanju"]``）、来源目录
# （``GET /api/v1/media/source``）认的都是这个规范值 —— 用旧标识订阅出去的条目
# 会被当成另一个来源，分类规则里的来源过滤就落空了。
# 早期标识 ``duanjubaike`` 由百科插件的别名表兜着（**只读兼容**，本插件不再产出它）。
_BAIKE_SOURCE = "duanju"

# 百科作品的类型：短剧一律按电视剧走（宿主没有「短剧」媒体类型）
_BAIKE_TYPE = "电视剧"

# 作品墙分页：单页上限与默认页大小。
#
# 作品墙是**服务端筛选 + 排序 + 分页**（真机实测 95 位演员 = 2256 部），前端按页拉、
# 滚到底再拉下一页，所以默认页就是首屏规模（三两行卡片），不必一次拿全。
_MAX_PAGE_SIZE = 200
_DEFAULT_PAGE_SIZE = 60

# 排序模式 → (作品记录字段, 比较方式)。四项都是作品自带的真实数据（短剧百科页面印的
# 「354万 热度 / 996 播放 / 8.2 分 / 2025-07-09 首播」），缺数据的作品排最后。
#   ``num``  → 数值降序（热度 / 播放 / 评分）
#   ``date`` → 日期降序（``YYYY-MM-DD`` 字典序即时间序）
_SORT_FIELDS = {
    "heat": ("heat", "num"),
    "play": ("play_count", "num"),
    "rating": ("vote", "num"),
    "date": ("release_date", "date"),
}
_DEFAULT_SORT = "heat"

# 「搜索演员」时最多给前几位候选补档案（头像 / 作品数 / 简介）—— 每位一次页面请求，
# 不设上限会让一次搜索拖很久；超出的候选仍以「只有名字」的卡片给出。
_ACTOR_LOOKUP_LIMIT = 12

# 快照记录的字段版本：低于当前值的记录会在下一轮刷新时重抓一次。
# 2026-10-15 = 2：作品开始带类型 / 年份 / 热度 / 播放 / 版权方等筛选排序字段，
# 旧快照里没有这些字段，靠这个版本号自动触发一次重抓（不必用户手动刷新）。
_SNAPSHOT_SCHEMA = 2

# 作品字段在数据源版本间会改名，一律按候选名依次取，取到第一个有值的为准。
# 版权方（``studio``）目前只有作品详情页才有，演员页的卡片补齐后这里自动接上。
_TAGS_FIELDS = ("tags", "genres", "genres_names")
_HEAT_FIELDS = ("heat", "heat_count", "popularity")
_PLAY_FIELDS = ("play_count", "plays", "play")
_STUDIO_FIELDS = (
    "studio",
    "production_companies",
    "production",
    "producer",
    "company",
    "copyright",
    "copyright_holder",
)

# 一次性任务 ID
_ONCE_JOB_ID = "refresh_once"

# 全角 ASCII → 半角（剧名归一化用；0x3000 是全角空格）
_FULLWIDTH_MAP = {code: code - 0xFEE0 for code in range(0xFF01, 0xFF5F)}
_FULLWIDTH_MAP[0x3000] = 0x20

# 季/部标记：归一化剧名时剔除。注意「云渺3」这类**片名序号不属于季标记**，必须保留 ——
# 「云渺3：镇魔世家」和「云渺4：绝嗣佛子」是两部独立的剧，序号是唯一的区分键。
_SEASON_TOKEN_PATTERNS = (
    re.compile(r"(?:full\s*)?season\s*0*\d+", re.IGNORECASE),
    re.compile(r"[sS]0*\d{1,2}(?!\d)(?!\s*[eE]\d)"),
    re.compile(r"第\s*0*\d+\s*[季部]"),
    re.compile(r"第\s*[一二三四五六七八九十]+\s*[季部]"),
)

# 集数标记：只作信息字段，同时要从剧名里剔除以免影响归一化
_EPISODE_PATTERNS = (
    re.compile(r"共\s*\d+\s*集"),
    re.compile(r"全\s*\d+\s*集"),
    re.compile(r"\d+\s*集"),
    re.compile(r"[sS]\d{1,2}[eE]\d{1,4}"),
    re.compile(r"[eE][pP]?\d{1,4}\b"),
)

# 文件名/剧名中的非法字符
_ILLEGAL_NAME_CHARS = re.compile(r'[\\/*?:"<>|]')
# 归一化时要去除的标点与空白（保留字母、数字、汉字）
_NAME_NOISE = re.compile(
    r"[\s\-_.·•:：、,，;；!！?？~～^《》<>「」『』\[\]［］\(\)（）\"'“”‘’]+"
)


# ─────────────────────────── 纯函数（可单测） ───────────────────────────


def _clean_text(value: Any) -> str:
    """把任意值收敛成去空白的字符串（None / 数字 / 空白串 → 空串）。"""
    if value is None:
        return ""
    return str(value).strip()


def _to_bool(value: Any, default: bool = False) -> bool:
    """宽松布尔转换：前端可能传真布尔，也可能传 "true"/"on"/"1" 之类的字符串。"""
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("true", "1", "yes", "on")


def _to_int(value: Any, default: int = 0) -> int:
    """宽松整数转换；拿不到数字返回默认值（百科的集数/热度字段经常是字符串或空）。"""
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return default


def _to_float(value: Any, default: float = 0.0) -> float:
    """宽松浮点转换；拿不到数字返回默认值（评分缺省按 0 处理，前端会统一格式化）。"""
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return default


def _pick_text(item: Dict[str, Any], names: Any) -> str:
    """按候选字段名依次取值，返回第一个非空文本（数据源版本间字段会改名）。

    ``[{"name": "红果…"}]``（宿主模型形态）、``{"name": "红果…"}``、``"红果…"``
    三种形态都收敛成同一个字符串。
    """
    for name in names:
        value = item.get(name)
        if isinstance(value, (list, tuple)):
            value = value[0] if value else ""
        if isinstance(value, dict):
            value = value.get("name")
        text = _clean_text(value)
        if text:
            return text
    return ""


def _pick_number(item: Dict[str, Any], names: Any) -> float:
    """按候选字段名依次取数值；一个都没有就返回 0（排序时自然排到最后）。"""
    for name in names:
        value = item.get(name)
        if value in (None, ""):
            continue
        number = _to_float(value, -1.0)
        if number >= 0:
            return number
    return 0.0


def tags_of(item: Dict[str, Any]) -> List[str]:
    """作品的题材/类型标签（去重保序，可单测）。

    兼容三种形态：``["逆袭", "都市日常"]``、``"逆袭,都市日常"``、
    ``[{"name": "逆袭"}]`` —— 数据源在卡片 / 详情 / 宿主模型里给的并不一致。
    """
    raw: Any = None
    for name in _TAGS_FIELDS:
        value = item.get(name)
        if value:
            raw = value
            break
    if isinstance(raw, str):
        raw = re.split(r"[,，/、|;；]+", raw)
    if not isinstance(raw, (list, tuple)):
        return []
    result: List[str] = []
    seen: set = set()
    for entry in raw:
        if isinstance(entry, dict):
            entry = entry.get("name")
        text = _clean_text(entry)
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return result


def work_year(item: Dict[str, Any]) -> str:
    """作品的年份：优先 ``year``，否则从 ``release_date``（首播日期）里取前四位。"""
    year = _clean_text(item.get("year"))
    if year:
        return year
    release = _clean_text(item.get("release_date") or item.get("first_air_date"))
    match = re.match(r"(\d{4})", release)
    return match.group(1) if match else ""


def classify_error(message: str) -> str:
    """把百科侧的错误文案归成稳定的原因码。

    * ``baike_empty`` —— **稳定**结果：百科没收录这位演员（或百科插件没装/停用）；
    * ``baike`` —— **临时**故障：网络抖动 / 索引超时，重试大概率自愈；
    * ``other`` —— 其余。
    """
    text = _clean_text(message)
    if "未收录" in text or "没有作品" in text:
        return "baike_empty"
    if text.startswith("短剧百科"):
        return "baike"
    return "other"


def record_state(record: Dict[str, Any]) -> str:
    """演员记录当前的展示状态（可单测）。

    * ``''`` 正常（已有作品）；
    * ``'waiting'`` 临时性失败 —— 面板只给一句「等待自动重试」；
    * ``'empty'`` 百科未收录 —— 中性说明，不是故障。

    临时性优先：同一条记录里既有临时故障又有「未收录」时按可重试处理；
    ``stale``（本轮数据源空手而归、沿用旧快照）同样按可重试处理 —— 否则要等满
    整个快照 TTL 才会再去拉一次。
    """
    if not isinstance(record, dict):
        return "waiting"
    if record.get("works"):
        return "waiting" if record.get("stale") else ""
    kinds = {classify_error(str(item)) for item in record.get("errors") or []}
    if "baike" in kinds or "other" in kinds:
        return "waiting"
    if "baike_empty" in kinds:
        return "empty"
    return "waiting"


def parse_stamp(value: Any) -> Optional[datetime]:
    """解析快照里的时间戳（``YYYY-MM-DD HH:MM:SS``）；不可解析返回 None。"""
    text = _clean_text(value)
    if not text:
        return None
    try:
        return datetime.strptime(text, _STAMP_FORMAT)
    except ValueError:
        return None


def snapshot_age_seconds(record: Dict[str, Any], now: Optional[datetime] = None) -> Optional[float]:
    """一条演员快照距今多少秒；缺时间戳 / 格式不对返回 None（视为「该刷新」）。"""
    parsed = parse_stamp((record or {}).get("time"))
    if parsed is None:
        return None
    return max(0.0, ((now or datetime.now()) - parsed).total_seconds())


def record_needs_refresh(
    record: Dict[str, Any],
    ttl_seconds: float,
    retry_seconds: float,
    now: Optional[datetime] = None,
    schema: int = 0,
) -> bool:
    """一条演员快照是否到了该重新解析的时间点（可单测）。

    - 没有记录 / 时间戳不可解析 → 要（新加的演员立刻解析）
    - 记录字段版本低于 ``schema``（数据源补齐了新字段）→ 要，立刻重抓一次
    - ``waiting``（临时性失败）→ 按**失败重试间隔**判定
    - 其余 → 按**快照刷新间隔**判定
    """
    if not isinstance(record, dict):
        return True
    if schema and _to_int(record.get("schema")) < schema:
        return True
    age = snapshot_age_seconds(record, now)
    if age is None:
        return True
    state = _clean_text(record.get("state"))
    if state == "waiting":
        return age >= retry_seconds
    if not state and not record.get("works"):
        # 老快照（还没有 state 字段）里没作品的记录：分不清失败还是确无作品，按可重试处理
        return age >= retry_seconds
    return age >= ttl_seconds


def is_retry_candidate(record: Dict[str, Any]) -> bool:
    """该记录是否属于「解析失败、值得按短间隔重试」的一类（可单测）。"""
    if not isinstance(record, dict):
        return True
    if _clean_text(record.get("state")) == "waiting":
        return True
    return not record.get("state") and not record.get("works")


def stamp_epoch(value: Any) -> float:
    """快照时间戳文本 → epoch 秒；缺失或格式非法返回 0（「新」判定用）。"""
    parsed = parse_stamp(value)
    return parsed.timestamp() if parsed else 0.0


def is_fresh_work(work: Dict[str, Any], now: float, baseline_at: float = 0.0) -> bool:
    """作品是否属于「演员加入之后才出现的新作品」（可单测）。

    1. 首次出现在**基线之后**（``first_seen`` > ``baseline_at``）—— 建立基线时就有的作品
       永远不算新；
    2. 首次出现距今在 ``_NEW_WINDOW_SECONDS`` 之内 —— 时间窗负责让「新」自然过期。

    ``first_seen`` 缺失按**不新**处理。
    """
    first_seen = stamp_epoch(work.get("first_seen"))
    if not first_seen:
        return False
    if baseline_at and first_seen <= baseline_at:
        return False
    return (now - first_seen) <= _NEW_WINDOW_SECONDS


def normalize_title(title: str) -> str:
    """把剧名归一化成可比较的键（全角转半角 → 去非法字符 → 剔季/集标记 → 去标点 → 小写）。

    **片名中的序号必须保留**：见 ``_SEASON_TOKEN_PATTERNS`` 处的说明。
    """
    text = _clean_text(title)
    if not text:
        return ""
    text = text.translate(_FULLWIDTH_MAP)
    text = _ILLEGAL_NAME_CHARS.sub("", text)
    for pattern in _SEASON_TOKEN_PATTERNS:
        text = pattern.sub(" ", text)
    for pattern in _EPISODE_PATTERNS:
        text = pattern.sub(" ", text)
    text = _NAME_NOISE.sub("", text)
    return text.lower()


def work_key(title: str, year: str = "") -> str:
    """作品的去重键：归一化剧名 + 年份。"""
    return f"{normalize_title(title)}|{_clean_text(year)}"


#: ``media_id`` 的历史形态（百科插件只读兼容）；规范身份是 ``duanju`` + **裸数字**
_LEGACY_ID_PREFIXES = ("duanjubaike:", "duanju:", "org:")


def baike_media_id(work: Dict[str, Any]) -> str:
    """把作品行的 ``media_id`` 归一成百科的**裸数字** ID（可单测）。

    快照里同一部剧可能存在两种身份（新版 ``39980`` / 旧版 ``duanju:39980``），
    只看字符串就会把一部剧拆成两行 —— 这里剥掉历史前缀，只剩数字。
    无法归一（非数字）时原样返回，交给调用方回退。
    """
    media_id = _clean_text(work.get("media_id"))
    lowered = media_id.lower()
    for prefix in _LEGACY_ID_PREFIXES:
        if lowered.startswith(prefix):
            media_id = media_id[len(prefix):].strip()
            break
    return media_id


def wall_row_key(work: Dict[str, Any]) -> str:
    """作品墙行的去重键：**优先按百科 ID**，ID 归一不了再退回 剧名|年份。

    为什么不直接用 ``work_key(title, year)``：不同演员的快照抓取时间不同，
    同一部剧可能一份带年份、一份是早年「年份恒空」的旧卡 —— 按剧名|年份
    会把同一部剧数成两部（这正是真机上 2185 行里混着 78 对重复的根因）。
    百科的数字 ID 是作品的一等身份，用它最稳。
    """
    media_id = baike_media_id(work)
    if media_id.isdigit():
        return f"{_BAIKE_SOURCE}|{media_id}"
    return work_key(work.get("title") or "", work.get("year") or "")


def merge_first_seen(old_works: Any, works: List[Dict[str, Any]], stamp: str) -> None:
    """给本轮抓到的作品**就地**打上 ``first_seen``（可单测）。

    旧快照里已有的作品**继承原来的首次出现时间**，只有真正新冒出来的才记成本轮 ``stamp``。

    ⚠️ 匹配是「先按 剧名|年份，再退回按剧名」：早年快照的作品卡没有年份（``year`` 恒空），
    若只按完整键匹配，一旦数据源开始给年份，**整墙作品会被误判成新作品**。
    """
    known: Dict[str, str] = {}
    known_titles: Dict[str, str] = {}
    for item in old_works or []:
        if not isinstance(item, dict):
            continue
        title = item.get("title") or ""
        key = work_key(title, item.get("year") or "")
        seen = _clean_text(item.get("first_seen"))
        if not (key and seen):
            continue
        if key not in known:
            known[key] = seen
        title_key = normalize_title(title)
        if title_key and title_key not in known_titles:
            known_titles[title_key] = seen
    for work in works:
        title = work.get("title") or ""
        key = work_key(title, work.get("year") or "")
        work["first_seen"] = (
            known.get(key) or known_titles.get(normalize_title(title)) or stamp
        )


def _actor_name_key(name: Any) -> str:
    """演员名的宽松比较键：去空白后比对（百科候选可能带多余空格）。"""
    return re.sub(r"\s+", "", _clean_text(name))


def baike_work_to_candidate(card: Any) -> Optional[Dict[str, Any]]:
    """把百科作品卡转成作品墙用的统一候选结构。

    ``media_id`` 是百科自己的原生 ID（**裸数字**，形如 ``34146``），与 ``media_source``
    一起构成宿主订阅系统认的**媒体身份** —— 作品墙上的「订阅」就是拿这两个字段
    交给系统订阅。``duanju:`` 这类前缀是历史形态，百科插件仍能读，但本插件不再产出。

    筛选 / 排序用的字段（``genres`` 类型、``year`` 年份、``heat`` 热度、
    ``play_count`` 播放、``studio`` 版权方）**数据源给多少就存多少**，缺的一律
    留空或 0 —— 前端据此隐藏没有数据的筛选项，绝不拿假值填充（假值会让「按版权方
    筛选」出现一堆空标签，比没有这项更糟）。
    """
    if not isinstance(card, dict):
        return None
    title = _clean_text(card.get("title"))
    if not title:
        return None
    return {
        "title": title,
        "year": work_year(card),
        "type": _BAIKE_TYPE,
        "source": _BAIKE_SOURCE,
        "media_id": _clean_text(card.get("media_id")),
        # 海报是站内 CDN 绝对地址，前端统一走宿主 system/img 代理
        "poster": _clean_text(card.get("poster")),
        "vote": _to_float(card.get("rating")),
        "episode_count": _to_int(card.get("episode_count")),
        "url": _clean_text(card.get("url")),
        "genres": tags_of(card),
        "heat": _pick_number(card, _HEAT_FIELDS),
        "play_count": _pick_number(card, _PLAY_FIELDS),
        "studio": _pick_text(card, _STUDIO_FIELDS),
        "kind": _clean_text(card.get("kind")),
        "release_date": _clean_text(card.get("release_date")),
    }


def work_row(work: Dict[str, Any], actor: str, actor_key: str) -> Dict[str, Any]:
    """把候选作品补成作品墙的一行（带上演员归属与前端需要的字段）。"""
    row = dict(work)
    row["key"] = wall_row_key(work)
    row["actor"] = actor
    row["actor_key"] = actor_key
    # 源标识统一收敛到规范值 ``duanju``：旧快照残留的 ``duanjubaike`` 只在百科插件
    # 只读兼容，本插件产出的行必须带规范身份（订阅 / 在库探针都按它匹配）
    row["media_source"] = _BAIKE_SOURCE
    # 旧快照残留的 ``duanju:`` 前缀身份在此归一：媒体身份必须是 ``duanju`` + 裸数字，
    # 带前缀的 ID 交给宿主订阅 / 在库探针都匹配不上
    row["media_id"] = baike_media_id(work)
    return row


def filter_works(
    rows: List[Dict[str, Any]],
    *,
    actor: str = "",
    genre: str = "",
    year: str = "",
    studio: str = "",
    only_not_in_library: bool = False,
    keyword: str = "",
) -> List[Dict[str, Any]]:
    """按查询条件过滤作品行（纯函数，可单测）。

    所有条件都是「空 = 不参与筛选」；演员命中口径与前端的演员 chip 一致 ——
    同一部剧多位演员参演时行里的 ``actor`` 是「A / B」，命中任一即可。

    ``only_not_in_library`` 只排除**明确已在库**的行（``in_library`` 为 ``True``）；
    「未知」（字段缺失 / 查库失败）的行**保留** —— 任何一处把「没查成」塌缩成
    「都不在库」，都会让异常被显示成结论。
    """
    word = normalize_title(keyword)
    result: List[Dict[str, Any]] = []
    for row in rows:
        if actor:
            owners = [item.strip() for item in str(row.get("actor") or "").split(" / ")]
            if actor not in owners and actor != row.get("actor_key"):
                continue
        if genre and genre not in (row.get("genres") or []):
            continue
        if year and _clean_text(row.get("year")) != year:
            continue
        if studio and _clean_text(row.get("studio")) != studio:
            continue
        if only_not_in_library and row.get("in_library") is True:
            continue
        if word and word not in normalize_title(row.get("title") or ""):
            continue
        result.append(row)
    return result


def sort_works(rows: List[Dict[str, Any]], mode: str = _DEFAULT_SORT) -> List[Dict[str, Any]]:
    """按作品自带的数值 / 日期排序（纯函数，可单测）。

    * ``heat``（默认）→ 作品的热度降序；
    * ``play`` → 作品的播放量降序；
    * ``rating`` → 作品的评分降序；
    * ``date`` → 作品的首播日期降序（新剧在前）。

    所有值都来自作品本身（百科页面印的「354万 热度 / 996 播放 / 8.2 分 / 首播日期」）。
    缺数据的作品排最后；同值时按剧名排序，保证顺序稳定可预期 ——
    做法是**先按剧名排一遍，再按目标字段稳定排序**（Python 的 ``sort`` 是稳定排序），
    这样不必为「日期降序但空值垫底」写特殊的可比较键。
    """
    field, kind = _SORT_FIELDS.get(_clean_text(mode)) or _SORT_FIELDS[_DEFAULT_SORT]
    ordered = sorted(rows, key=lambda row: normalize_title(row.get("title") or ""))
    if kind == "date":
        # ``YYYY-MM-DD`` 的字典序就是时间序；空串最小，降序后自然落到末尾
        ordered.sort(key=lambda row: _clean_text(row.get(field)) or "", reverse=True)
    else:
        ordered.sort(key=lambda row: _to_float(row.get(field)), reverse=True)
    return ordered


def build_facets(rows: List[Dict[str, Any]], limit: int = 60) -> Dict[str, Any]:
    """算筛选项（纯函数，可单测）：类型 / 年份 / 版权方，各项带作品数。

    基于**筛选前**的全集计算 —— 选项不随用户勾选跳动。某项一条数据都没有时天然
    不在列表里：版权方在数据源补齐之前就是空数组，前端据此隐藏该筛选项。
    """
    genres: Dict[str, int] = {}
    years: Dict[str, int] = {}
    studios: Dict[str, int] = {}
    for row in rows:
        for tag in row.get("genres") or []:
            genres[tag] = genres.get(tag, 0) + 1
        year = _clean_text(row.get("year"))
        if year:
            years[year] = years.get(year, 0) + 1
        studio = _clean_text(row.get("studio"))
        if studio:
            studios[studio] = studios.get(studio, 0) + 1

    def top(counter: Dict[str, int], key: Any) -> List[Dict[str, Any]]:
        return [
            {"value": name, "count": count}
            for name, count in sorted(counter.items(), key=key)[:limit]
        ]

    return {
        "genres": top(genres, lambda kv: (-kv[1], kv[0])),
        # 年份：新的在前
        "years": top(
            years, lambda kv: (-_to_int(kv[0]), kv[0])
        ),
        "studios": top(studios, lambda kv: (-kv[1], kv[0])),
    }


# ─────────────────────────── 媒体库在库探针 ───────────────────────────


def _media_server_oper() -> Any:
    """惰性拿宿主的媒体服务器库操作对象（见 :class:`_LibraryProbe` 的取舍说明）。"""
    from app.db.oper.mediaserver import MediaServerOper

    return MediaServerOper()


class _LibraryProbe:
    """「这部作品是否已在媒体库」的探针 —— 与宿主媒体详情页**同一套判定**。

    宿主媒体详情页打开时会请求 ``GET /mediaserver/exists?media_source=&media_id=&title=&year=&season=&mtype=``，
    该端点只是把参数转给 ``MediaServerOper().get_item_id()``，由后者按下述顺序在本地库表
    ``mediaserveritem`` 里找条目（见宿主 ``db/oper/mediaserver.py`` 的 ``exists``）：

    1. ``media_source`` + ``media_id`` 同时给出时，先按「规范媒体身份 + 类型」精确匹配；
    2. 上一步未命中且有片名时，**回退**按「片名（+ 类型 + 年份）」匹配 ——
       媒体库里一部作品只保存一个主来源，短剧百科里的剧就算被以别的来源入库，
       靠这一手也能对得上；
    3. 只给片名时直接走第 2 步。

    这里刻意复用宿主自己的 ``MediaServerOper``，而不是自己写 SQL 或走
    ``app.sdk`` 的 ``media_exists``（那是远程问 Emby/Plex，慢且语义不同）：判定口径
    （尤其是回退规则与类型过滤）随宿主版本演进的细节都由宿主保证，插件只负责调用与展示。
    调用失败（宿主版本差异、事务执行器未就绪等）一律返回 ``None``（未知），
    绝不当成「不在库」——否则一次异常就会让整面墙看起来都没入库。

    结果带 **TTL 缓存**：作品墙每次打开都要现算（``in_library`` 和 ``is_new`` 一样
    不落盘），同一位演员的作品集变化不快，600 秒内重复打开墙面零查询。
    """

    #: 缓存有效期（秒）；过期后重新查库 —— 「不在库」的结论必须能被后续入库推翻
    CACHE_TTL = 600.0

    def __init__(self) -> None:
        self._oper: Any = None
        self._disabled = False
        # key -> (True/False, 缓存时刻)；None 表示「查不了」，也缓存（免得反复撞同一个错误）
        self._cache: Dict[Tuple[str, str, str, str, str], Tuple[Optional[bool], float]] = {}
        self.last_error = ""

    def _ensure_oper(self) -> Any:
        """惰性导入宿主的库操作对象；不可用时只记录一次并停用后续尝试。"""
        if self._oper is not None or self._disabled:
            return self._oper
        try:
            self._oper = _media_server_oper()
        except Exception as err:  # pragma: no cover - 宿主版本差异兜底
            self._disabled = True
            self.last_error = str(err)
            logger.warning(f"{PLUGIN_NAME} 媒体库存在性检查不可用，本轮不标注入库状态：{err}")
        return self._oper

    @staticmethod
    def _cache_key(work: Dict[str, Any]) -> Tuple[str, str, str, str, str]:
        return (
            str(work.get("media_source") or ""),
            str(work.get("media_id") or ""),
            str(work.get("type") or ""),
            str(work.get("title") or ""),
            str(work.get("year") or ""),
        )

    def lookup(self, work: Dict[str, Any], now: Optional[float] = None) -> Optional[bool]:
        """查询单个作品：``True`` 在库 / ``False`` 不在库 / ``None`` 未知（查不了）。

        ``now`` 仅供单测注入时钟。
        """
        key = self._cache_key(work)
        stamp = time.time() if now is None else now
        cached = self._cache.get(key)
        if cached is not None and stamp - cached[1] < self.CACHE_TTL:
            return cached[0]
        flag = self._lookup_uncached(work)
        self._cache[key] = (flag, stamp)
        return flag

    def _lookup_uncached(self, work: Dict[str, Any]) -> Optional[bool]:
        if self._disabled:
            # 之前失败过：本轮所有作品都是「未知」，不再反复触库刷警告
            return None
        media_source = str(work.get("media_source") or "").strip()
        media_id = str(work.get("media_id") or "").strip()
        title = str(work.get("title") or "").strip()
        if not (media_source and media_id) and not title:
            return None
        oper = self._ensure_oper()
        if oper is None:
            return None
        try:
            item_id = oper.get_item_id(
                media_source=media_source or None,
                media_id=media_id or None,
                title=title or None,
                year=str(work.get("year") or "").strip() or None,
                mtype=str(work.get("type") or "").strip() or None,
            )
        except Exception as err:  # pragma: no cover - 宿主机内差异兜底
            self._disabled = True
            self.last_error = str(err)
            logger.warning(f"{PLUGIN_NAME} 媒体库存在性检查失败，后续作品不再查询：{err}")
            return None
        # 宿主返回的是媒体服务器的 item_id 字符串；空值即「本地没有这条」
        return bool(str(item_id or "").strip())


# ─────────────────────────── 插件 ───────────────────────────


class ShortDramaActorSubscribe(_PluginBase):
    """按演员发现短剧作品，订阅交回宿主订阅系统。"""

    # ── 插件元数据（需与 package.v3.json 保持一致） ──
    # 注意：plugin_name / plugin_icon 必须是**字符串字面量**，不能引用模块常量 ——
    # 宿主的部分离线安装工具用 AST 静态解析插件类，只认 ast.Constant。
    plugin_name = "短剧演员订阅"
    plugin_desc = (
        "跟着喜欢的演员追短剧：填演员名，插件从短剧百科（duanjubaike.org）取回他们的全部作品，"
        "摆成和「探索」页同形的海报墙；看中哪部点「订阅」，走的就是 MoviePilot 自己的订阅系统"
        "（搜索、下载、整理全部由系统负责）。作品墙按演员筛选，新作品自动标「新」。"
    )
    plugin_icon = (
        "https://raw.githubusercontent.com/m215owen/MoviePilot-Plugins/main/"
        "icons/ShortDramaActorSubscribe.png"
    )
    plugin_version = "1.0.0"
    plugin_author = "m215owen"
    author_url = "https://github.com/m215owen"
    plugin_config_prefix = "shortdramaactorsubscribe_"
    plugin_order = 55
    auth_level = 1

    # ── 运行时状态（⚠️ 全部在 init_plugin 里重新赋值，避免跨实例串味） ──
    _enabled = False
    _onlyonce = False
    _actors: List[str] = []
    _interval_hours = 12
    _retry_minutes = _DEFAULT_RETRY_MINUTES
    _notify = True
    _sidebar_nav = True
    # 资源搜索站点：逗号分隔的站点 ID（空 = 不限定，走宿主默认）
    _search_sites = ""
    # 订阅下载器：宿主下载客户端的名字（空 = 跟随系统默认）。
    # 插件后端不参与订阅 —— 这个值只负责持久化，作品墙提交订阅时由前端取用
    # （系统订阅弹窗没有下载器选项，配置了就得绕过弹窗直接提交）。
    _subscribe_downloader = ""
    # 同一进程内的重入保护：定时任务与手动触发可能撞在一起
    _lock = threading.Lock()

    def __init__(self) -> None:
        super().__init__()
        self._actors = []
        self._running = False
        self._last_result: Dict[str, Any] = {}

    # ── 生命周期 ──

    def init_plugin(self, config: Optional[Dict[str, Any]] = None) -> None:
        """读取配置并建立运行时状态；必须允许重复调用。"""
        config = config or {}
        self._enabled = bool(config.get("enabled"))
        self._onlyonce = bool(config.get("onlyonce"))
        self._actors = self._parse_actors(config.get("actors"))
        self._interval_hours = max(1, _to_int(config.get("interval_hours")) or 12)
        self._retry_minutes = max(
            1, _to_int(config.get("retry_minutes")) or _DEFAULT_RETRY_MINUTES
        )
        self._notify = _to_bool(config.get("notify"), True)
        self._sidebar_nav = _to_bool(config.get("sidebar_nav"), True)
        self._search_sites = self._parse_site_ids(config.get("search_sites"))
        self._subscribe_downloader = _clean_text(config.get("subscribe_downloader"))

        if self._onlyonce:
            self._add_once_job(delay_seconds=3, trigger="once")
            # 立即执行是「一次性」语义，落库时清掉开关，避免每次重载都触发
            self._onlyonce = False
            self.update_config(self._live_config())
            logger.info(f"{PLUGIN_NAME} 已登记立即运行一次任务")

    def get_state(self) -> bool:
        """返回插件当前是否启用。"""
        return self._enabled

    def stop_service(self) -> None:
        """释放插件创建的后台资源。"""
        self._running = False

    # ── 配置解析 ──

    @staticmethod
    def _parse_actors(value: Any) -> List[str]:
        """解析演员配置：支持列表或逗号/换行/分号分隔的字符串，去重且保序。"""
        if isinstance(value, (list, tuple)):
            items = [str(item) for item in value]
        else:
            items = re.split(r"[,，;；\n\r]+", str(value or ""))
        result: List[str] = []
        seen: set = set()
        for item in items:
            item = _clean_text(item)
            if not item or item in seen:
                continue
            seen.add(item)
            result.append(item)
        return result

    @staticmethod
    def _parse_site_ids(value: Any) -> str:
        """解析搜索站点配置：容忍列表或逗号/换行分隔，归一成逗号分隔的数字串。"""
        items = value if isinstance(value, (list, tuple)) else re.split(r"[,，;；\n\r]+", str(value or ""))
        ids: List[str] = []
        for item in items:
            text = _clean_text(str(item))
            if text.isdigit() and text not in ids:
                ids.append(text)
        return ",".join(ids)

    def _live_config(self) -> Dict[str, Any]:
        """组装当前运行时配置用于回写（键与 ``_default_config`` 一致）。

        必须读**实例属性**：插件虚拟分身会在同一份源码上创建多个运行实例，只有实例属性
        才是本实例的真实配置。
        """
        return {
            "enabled": self._enabled,
            "onlyonce": self._onlyonce,
            "actors": ",".join(self._actors),
            "interval_hours": self._interval_hours,
            "retry_minutes": self._retry_minutes,
            "notify": self._notify,
            "sidebar_nav": self._sidebar_nav,
            "search_sites": self._search_sites,
            "subscribe_downloader": self._subscribe_downloader,
        }

    @staticmethod
    def _default_config() -> Dict[str, Any]:
        """返回配置页默认值。"""
        return {
            "enabled": False,
            "onlyonce": False,
            "actors": "",
            "interval_hours": 12,
            "retry_minutes": _DEFAULT_RETRY_MINUTES,
            "notify": True,
            "sidebar_nav": True,
            "search_sites": "",
            "subscribe_downloader": "",
        }

    # ── 页面与渲染模式 ──

    @staticmethod
    def get_render_mode() -> Tuple[str, str]:
        """声明使用 Vue 联邦远程组件渲染，产物目录为 dist/assets。"""
        return "vue", "dist/assets"

    def get_form(self) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Vue 模式下配置页由远程 Config 组件渲染，后端只返回默认配置模型。"""
        return [], self._default_config()

    def get_page(self) -> List[Dict[str, Any]]:
        """Vue 模式下详情页由远程 Page 组件渲染，后端返回空列表。"""
        return []

    def get_sidebar_nav(self) -> List[Dict[str, Any]]:
        """侧栏入口「短剧演员」，落在宿主的「订阅」分组里。

        宿主侧栏合并逻辑把插件项**追加到分组末尾**（``order`` 只在插件项之间排序），
        ``section`` 仅接受 start / discovery / subscribe / organize / system。
        """
        if not self.get_state() or not self._sidebar_nav:
            return []
        return [
            {
                "nav_key": "main",
                "title": "短剧演员",
                "icon": "mdi-movie-open-star-outline",
                "section": "subscribe",
                "permission": "subscribe",
                "order": 32,
            },
        ]

    def get_dashboard_meta(self) -> Optional[List[Dict[str, str]]]:
        """声明仪表板窗口；插件未启用时不注册。"""
        if not self.get_state():
            return None
        return [{"key": "overview", "name": f"{self.plugin_name} · 追剧概览"}]

    def get_dashboard(
        self, key: str = "", **kwargs: Any
    ) -> Optional[Tuple[Dict[str, Any], Dict[str, Any], List[dict]]]:
        """仪表板内容：``(列配置, 全局配置, 页面 JSON)``。

        Vue 联邦插件由前端 Dashboard 组件呈现内容，因此页面 JSON 为空。
        """
        if not self.get_state():
            return None
        if key and key != "overview":
            return None
        _, summary = self._work_rows()
        return (
            {"cols": 12, "sm": 6, "md": 4},
            {
                "title": f"{self.plugin_name} · 追剧概览",
                "subtitle": (
                    f"{len(self._actors)} 位演员｜{summary.get('total', 0)} 部作品"
                    f"｜新作品 {summary.get('new', 0)} 部"
                ),
                "refresh": 300,
                "border": True,
            },
            [],
        )

    # ── 服务 ──

    def get_service(self) -> List[Dict[str, Any]]:
        """注册定时服务：作品发现（按间隔）+ 解析失败重试（短间隔）。"""
        if not self.get_state() or not self._actors:
            return []
        # ⚠️ 传给被调函数的参数必须写在 ``func_kwargs`` 里。宿主注册时会把
        # ``service["kwargs"]`` **原样展开给** ``scheduler.add_job()``，而 ``trigger``
        # 正是 ``add_job`` 自己的形参名 —— 写成 ``kwargs`` 会抛
        # ``got multiple values for argument 'trigger'`` 并**拒绝注册**（真机实证）。
        services: List[Dict[str, Any]] = [
            {
                "id": f"{self.__class__.__name__}.Refresh",
                "name": "短剧演员 · 作品发现",
                "trigger": IntervalTrigger(hours=max(1, self._interval_hours)),
                "func": self.refresh_works_task,
                "func_kwargs": {"trigger": "interval"},
            },
        ]
        # 失败重试与整体刷新是两条节奏：失败是临时故障，等满一天才恢复体验太差
        services.append(
            {
                "id": f"{self.__class__.__name__}.Retry",
                "name": "短剧演员 · 解析失败重试",
                "trigger": IntervalTrigger(minutes=max(1, self._retry_minutes)),
                "func": self.retry_failed_actors,
                "func_kwargs": {"trigger": "interval"},
            }
        )
        return services

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        """注册远程命令，实际动作通过 ``EventType.PluginAction`` 事件路由。"""
        return [
            {
                "cmd": "/shortdrama",
                "event": EventType.PluginAction,
                "desc": "刷新短剧演员作品",
                "category": "插件命令",
                "data": {"action": "shortdramaactorsubscribe_refresh"},
            }
        ]

    @eventmanager.register(EventType.PluginAction)
    def on_plugin_action(self, event: Event) -> None:
        """响应远程命令；仅处理属于本插件的 action。"""
        event_data = getattr(event, "event_data", None) or {}
        if _clean_text((event_data or {}).get("action")) != "shortdramaactorsubscribe_refresh":
            return
        if not self._lock.acquire(blocking=False):
            logger.info(f"{PLUGIN_NAME} 已有刷新任务在运行，忽略本次命令")
            return
        try:
            before = self._load_actors()
            self._refresh_actors(force=True)
            fresh = self._collect_fresh(before)
            self._notify_fresh(fresh)
        finally:
            self._lock.release()

    # ── 接口 ──

    def get_api(self) -> List[Dict[str, Any]]:
        """插件 HTTP 端点（``/api/v1/plugin/ShortDramaActorSubscribe/…``）。

        统一 ``auth: "bear"``：宿主 ``verify_token`` 同时接受 JWT 与 API Token，
        这样面板（登录态）与外部脚本能共用同一批接口。
        """
        return [
            {
                "path": "/status",
                "endpoint": self.api_status,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "插件状态",
            },
            {
                "path": "/works",
                "endpoint": self.api_works,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "作品墙",
            },
            {
                "path": "/actors",
                "endpoint": self.api_actors,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "演员列表",
            },
            {
                "path": "/actors/search",
                "endpoint": self.api_search_actor,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "在短剧百科里查演员",
            },
            {
                "path": "/works/search",
                "endpoint": self.api_search_work,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "在短剧百科里按片名查作品",
            },
            {
                "path": "/actors/add",
                "endpoint": self.api_add_actor,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "添加演员",
            },
            {
                "path": "/actors/remove",
                "endpoint": self.api_remove_actor,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "移除演员",
            },
            {
                "path": "/actors/works",
                "endpoint": self.api_actor_works,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "某位演员的全部作品（百科实时，关注与否均可）",
            },
            {
                "path": "/refresh",
                "endpoint": self.api_refresh,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "立即刷新作品",
            },
            {
                "path": "/config",
                "endpoint": self.api_get_config,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "读取配置",
            },
            {
                "path": "/config",
                "endpoint": self.api_update_config,
                "methods": ["PUT"],
                "auth": "bear",
                "summary": "保存配置",
            },
        ]

    def api_get_config(self) -> Dict[str, Any]:
        """读取当前配置（前端配置弹窗用）。"""
        return {"success": True, "config": self._live_config()}

    def api_update_config(self, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """保存配置：只认 ``_default_config()`` 里的键，其余一律丢弃。

        整体替换而不是合并，这样删掉的概念（比如曾经的配置项）会在用户保存一次后
        自动从库里消失，不会残留成幽灵配置。
        """
        incoming = payload if isinstance(payload, dict) else {}
        base = self._default_config()
        merged = {key: incoming.get(key, base[key]) for key in base}
        self.update_config(merged)
        self.init_plugin(merged)
        return {"success": True, "config": self._live_config()}

    def api_status(self) -> Dict[str, Any]:
        """插件状态总览：演员、作品、新作品、最近刷新时间。"""
        rows, summary = self._work_rows()
        snapshot = self._load_actors()
        last = ""
        for record in snapshot.values():
            if isinstance(record, dict):
                stamp = _clean_text(record.get("time"))
                if stamp > last:
                    last = stamp
        return {
            "success": True,
            "enabled": self.get_state(),
            "configured": bool(self._actors),
            "actors": len(self._actors),
            "works": summary.get("total", 0),
            "new_works": summary.get("new", 0),
            "last_refresh": last,
            "new_window_days": _NEW_WINDOW_DAYS,
            "states": [
                self._actor_row(key, record)
                for key, record in snapshot.items()
                if isinstance(record, dict)
            ],
        }

    def api_works(
        self,
        actor: str = "",
        genre: str = "",
        year: str = "",
        studio: str = "",
        sort: str = "",
        only_not_in_library: str = "",
        keyword: str = "",
        page: str = "",
        page_size: str = "",
    ) -> Dict[str, Any]:
        """作品墙数据（服务端筛选 / 排序 / 分页）。

        ⚠️ 参数一律声明成**函数形参**：宿主把插件端点直接交给 FastAPI 注册
        （``adapters/web/plugin/routes.py`` → ``add_api_route``），查询参数靠 FastAPI
        按形参名注入 —— 用 flask 的 ``request.args`` 读在 v3 上永远是空（真机实证：
        ``?page_size=2`` 被忽略、照样返回整页）。

        参数：

        * ``actor`` —— 演员（名字或 key，空=全部）
        * ``genre`` —— 类型（作品的题材标签，任一命中）
        * ``year`` —— 年份（作品的首播年）
        * ``studio`` —— 版权方（数据源给出才有，空选项时前端不显示这一栏）
        * ``sort`` —— ``heat``（热度，默认）/ ``play``（播放）/ ``rating``（评分）/
          ``date``（首播日期，新剧在前）
        * ``only_not_in_library`` —— ``1`` 只看未入库（只排除**明确已在库**的；
          查库失败/没有数据的「未知」作品保留，绝不把「没查成」显示成「都不在库」。
          判定与宿主媒体详情页同一套：身份精确匹配 → 片名+类型+年份回退）
        * ``keyword`` —— 剧名关键字
        * ``page`` / ``page_size`` —— 分页（前端滚到底再拉下一页）

        全部用字符串接、内部再宽松转换：非法值（比如 ``page=abc``）只该被当成默认值，
        不该让 FastAPI 直接甩 422 把整面墙打死。

        响应里的 ``facets`` 是筛选项（类型 / 年份 / 版权方，各带作品数）、
        ``has_more`` 供前端判断还要不要继续加载。
        """
        rows, summary = self._work_rows(
            {
                "actor": actor,
                "genre": genre,
                "year": year,
                "studio": studio,
                "sort": sort,
                "only_not_in_library": only_not_in_library,
                "keyword": keyword,
            }
        )
        page_no = max(1, _to_int(page, 1))
        size = min(_MAX_PAGE_SIZE, max(1, _to_int(page_size, _DEFAULT_PAGE_SIZE)))
        total = len(rows)
        start = (page_no - 1) * size
        chunk = rows[start : start + size]
        return {
            "success": True,
            "total": total,
            "page": page_no,
            "page_size": size,
            "has_more": start + len(chunk) < total,
            "works": chunk,
            "actor_filters": summary.get("actors", []),
            "facets": summary.get("facets") or {"genres": [], "years": [], "studios": []},
            "sort": _clean_text(sort) or _DEFAULT_SORT,
            "new_window_days": _NEW_WINDOW_DAYS,
            "summary": {
                key: value
                for key, value in summary.items()
                if key not in ("actors", "facets")
            },
        }

    def api_actors(self) -> Dict[str, Any]:
        """演员列表（含解析状态、百科 ID、作品数）。"""
        snapshot = self._load_actors()
        return {
            "success": True,
            "actors": [
                self._actor_row(key, snapshot.get(key))
                for key in self._actors
            ],
        }

    def api_search_actor(self, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """在短剧百科里查演员：返回候选（供添加演员时挑选 / 演员搜索卡片）。

        百科的站外索引召回**含模糊结果**，所以这里把候选原样返回给前端挑；
        后端只在「归一化名字精确相等」时才认为可以直接采纳。

        ``enrich`` 为真时再给**前 N 位**候选补上演员档案（头像 ``profile`` / 作品数
        ``works_count`` / 简介 ``bio`` / 性别 / 国籍）—— 每位候选要多抓一次演员页，
        所以只补前几位，且失败一律降级成「只有名字」的卡片，不让整次搜索失败。
        面板的「搜索演员」用得上头像，添加演员的候选列表不需要，按需开启。

        ``subscribed`` 表示这位演员是否已在关注列表里（前端据此把卡片标成已添加）。
        """
        body = payload if isinstance(payload, dict) else {}
        name = _clean_text(body.get("name"))
        if not name:
            return {"success": False, "message": "请填写演员名"}
        enrich = _to_bool(body.get("enrich"), False)
        try:
            candidates = self.chain.run_module("search_actors", name=name) or []
        except Exception as err:  # noqa: BLE001 - 百科不可用只降级
            logger.warning(f"{PLUGIN_NAME} 短剧百科查找演员失败（{name}）：{err}")
            return {"success": False, "message": f"短剧百科查找失败：{err}"}
        rows: List[Dict[str, Any]] = []
        for row in candidates:
            if not isinstance(row, dict):
                continue
            actor_id = _clean_text(row.get("actor_id"))
            if not actor_id:
                continue
            label = _clean_text(row.get("name"))
            rows.append(
                {
                    "name": label,
                    "actor_id": actor_id,
                    "media_id": _clean_text(row.get("media_id")),
                    "url": _clean_text(row.get("url")),
                    "exact": _actor_name_key(label) == _actor_name_key(name),
                    "subscribed": label in self._actors,
                }
            )
        if enrich and rows:
            self._enrich_actor_cards(rows[:_ACTOR_LOOKUP_LIMIT])
        return {"success": True, "name": name, "candidates": rows}

    def api_search_work(self, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """在短剧百科里按片名查作品：返回候选（搜索结果页的作品卡片用）。

        经 ``run_module("search_medias", meta=…, media_source="duanju")`` 分发给
        短剧百科数据源 —— 与宿主搜索框同一条检索链路（URL 库 → 站内索引 → 站点
        搜索），返回宿主 ``MediaInfo``，这里只挑展示用的字段转成纯 dict。
        """
        body = payload if isinstance(payload, dict) else {}
        name = _clean_text(body.get("name"))
        if not name:
            return {"success": False, "message": "请填写作品名"}
        meta = MetaInfo(name)
        try:
            infos = self.chain.run_module(
                "search_medias", meta=meta, media_source=_BAIKE_SOURCE
            ) or []
        except Exception as err:  # noqa: BLE001 - 百科不可用只降级
            logger.warning(f"{PLUGIN_NAME} 短剧百科查找作品失败（{name}）：{err}")
            return {"success": False, "message": f"短剧百科查找失败：{err}"}
        works: List[Dict[str, Any]] = []
        for info in infos:
            media_id = _clean_text(getattr(info, "media_id", "") or "")
            title = _clean_text(getattr(info, "title", "") or "")
            if not media_id or not title:
                continue
            works.append(
                {
                    "media_source": _clean_text(getattr(info, "media_source", "") or "")
                    or _BAIKE_SOURCE,
                    "media_id": media_id,
                    "title": title,
                    "year": _clean_text(str(getattr(info, "year", "") or "")),
                    "poster": _clean_text(getattr(info, "poster_path", "") or ""),
                    "overview": _clean_text(getattr(info, "overview", "") or ""),
                    "vote": float(getattr(info, "vote_average", 0) or 0),
                }
            )
        return {"success": True, "name": name, "works": works}

    def _enrich_actor_cards(self, rows: List[Dict[str, Any]]) -> None:
        """给演员候选补头像 / 作品数 / 简介（就地改 ``rows``，best-effort）。

        ``actor_profile(enrich=False)`` 只抓演员页本身、不补作品详情 —— 卡片只需要
        头像与作品数，补详情是浪费。任何异常都只跳过这一位候选。
        """
        for row in rows:
            actor_id = _clean_text(row.get("actor_id"))
            if not actor_id:
                continue
            try:
                profile = self.chain.run_module(
                    "actor_profile", actor_id=actor_id, enrich=False
                ) or {}
            except Exception as err:  # noqa: BLE001 - 补档案失败只跳过
                logger.debug(f"{PLUGIN_NAME} 取演员档案失败（{actor_id}）：{err}")
                continue
            if not isinstance(profile, dict) or not profile:
                continue
            row["name"] = _clean_text(profile.get("name")) or row.get("name", "")
            row["profile"] = _clean_text(profile.get("profile"))
            row["works_count"] = _to_int(profile.get("works_count"))
            row["bio"] = _clean_text(profile.get("bio"))
            row["gender"] = _clean_text(profile.get("gender"))
            row["nationality"] = _clean_text(profile.get("nationality"))
            row["job_title"] = _clean_text(profile.get("job_title"))
            row["url"] = _clean_text(profile.get("url")) or row.get("url", "")

    def api_add_actor(self, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """添加演员到关注列表。

        - 给了 ``actor_id``（用户在候选里挑过）→ 直接采用；
        - 只给名字 → 先查百科，**只有归一化名字精确相等**才采纳（宁可让用户挑一次，
          也不错配成另一个演员）；没有精确命中就把候选回给前端（``need_pick``）。
        """
        body = payload if isinstance(payload, dict) else {}
        name = _clean_text(body.get("name"))
        actor_id = _clean_text(body.get("actor_id"))
        if not name:
            return {"success": False, "message": "请填写演员名"}
        if name in self._actors:
            return {"success": False, "message": f"「{name}」已经在关注列表里"}

        if not actor_id:
            picked = self.api_search_actor({"name": name})
            if not picked.get("success"):
                return {"success": False, "message": str(picked.get("message") or "短剧百科查找失败")}
            rows = [row for row in picked.get("candidates") or [] if row.get("exact")]
            if not rows:
                return {
                    "success": False,
                    "code": "need_pick",
                    "message": f"短剧百科里没有与「{name}」完全同名的演员，请从候选里挑一位",
                    "candidates": picked.get("candidates") or [],
                }
            actor_id = _clean_text(rows[0].get("actor_id"))

        # 先把演员写进配置，再立即抓一轮（让用户马上看到作品，而不是等下个轮询周期）
        self._actors = self._actors + [name]
        config = self._live_config()
        self.update_config(config)
        self.init_plugin(config)
        # 记下百科 ID：后续轮次直接按 ID 取作品页，不再走站外索引
        snapshot = self._load_actors()
        snapshot[name] = {
            "key": name,
            "name": name,
            "baike_id": actor_id,
            "works": [],
            "errors": [],
        }
        self.save_data(_DATA_ACTORS, snapshot)
        count = self._refresh_one(name)
        return {
            "success": True,
            "message": f"已添加「{name}」" + (f"，拿到 {count} 部作品" if count else "，正在获取作品"),
            "actors": self._actors,
        }

    def api_remove_actor(self, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """把演员移出关注列表（连同他的快照一起删掉）。"""
        body = payload if isinstance(payload, dict) else {}
        name = _clean_text(body.get("name"))
        if not name or name not in self._actors:
            return {"success": False, "message": "演员不在关注列表里"}
        self._actors = [item for item in self._actors if item != name]
        config = self._live_config()
        self.update_config(config)
        self.init_plugin(config)
        snapshot = self._load_actors()
        snapshot.pop(name, None)
        self.save_data(_DATA_ACTORS, snapshot)
        return {"success": True, "message": f"已移除「{name}」", "actors": self._actors}

    def api_actor_works(self, actor_id: str = "", name: str = "") -> Dict[str, Any]:
        """某位演员的**全部**作品（点演员卡片展开作品墙用，关注与否均可）。

        作品**现查**短剧百科（``run_module("actor_works")``，每条都已补成作品页
        记录），不落盘、不进快照 —— 关注列表的作品墙数据照旧走 ``/works``。
        参数是函数形参（FastAPI 按名注入，见 ``api_works`` 的说明）。
        """
        actor_id = _clean_text(actor_id)
        name = _clean_text(name)
        if not actor_id and not name:
            return {"success": False, "message": "缺少演员标识（actor_id 或 name）"}
        try:
            works = self.chain.run_module("actor_works", actor_id=actor_id, name=name) or []
        except Exception as err:  # noqa: BLE001 - 百科不可用时降级报错
            logger.warning(f"{PLUGIN_NAME} 短剧百科取演员作品失败（{actor_id or name}）：{err}")
            return {"success": False, "message": f"短剧百科取作品失败：{err}"}
        rows: List[Dict[str, Any]] = []
        seen: set = set()
        for work in works:
            if not isinstance(work, dict):
                continue
            candidate = baike_work_to_candidate(work)
            if not candidate:
                continue
            row = work_row(candidate, name, actor_id)
            if row["key"] in seen:
                continue
            seen.add(row["key"])
            # 在库判定与作品墙同一套探针（三态；查不了就是「未知」，不硬给结论）
            row["in_library"] = self.library_probe.lookup(row)
            rows.append(row)
        sort_works(rows, _DEFAULT_SORT)
        return {"success": True, "name": name, "total": len(rows), "works": rows}

    def api_refresh(self) -> Dict[str, Any]:
        """立即刷新全部演员的作品（忽略缓存）。"""
        if not self._actors:
            return {"success": False, "message": "还没有添加演员"}
        if not self._lock.acquire(blocking=False):
            return {"success": False, "message": "已有刷新任务在运行"}
        try:
            before = self._load_actors()
            self._refresh_actors(force=True)
            fresh = self._collect_fresh(before)
            self._notify_fresh(fresh)
            rows, summary = self._work_rows()
            return {
                "success": True,
                "message": f"刷新完成：{summary.get('total', 0)} 部作品"
                + (f"，新增 {len(fresh)} 部" if fresh else ""),
                "total": summary.get("total", 0),
                "new": summary.get("new", 0),
            }
        finally:
            self._lock.release()

    # ── 发现层：只认短剧百科 ──

    def _discover_actor(self, key: str) -> Dict[str, Any]:
        """发现单个演员的作品列表（只认短剧百科）。

        返回 ``{"key","name","baike_id","works","errors","baseline_at"}``。
        """
        record: Dict[str, Any] = {
            "key": key,
            "name": key,
            "baike_id": "",
            "works": [],
            "errors": [],
        }
        works: List[Dict[str, Any]] = []

        existing = self._load_actors().get(key)
        if isinstance(existing, dict):
            # 百科演员 ID 缓存在快照里：解析一次后，后续轮次直接按 ID 取作品页，
            # 不再走站外索引（搜索引擎一次 10 秒级，几十位演员逐个查一轮不可接受）
            record["baike_id"] = _clean_text(existing.get("baike_id"))
            record["name"] = _clean_text(existing.get("name")) or key

        # 「新作品」基线：第一次见到这位演员时记下时间，之后每轮沿用它判定谁是新来的
        stamp = datetime.now().strftime(_STAMP_FORMAT)
        baseline = _clean_text(existing.get("baseline_at")) if isinstance(existing, dict) else ""
        record["baseline_at"] = baseline or stamp

        self._baike_works(record, works)
        # ⚠️ 数据源这一轮空手而归时**保留旧作品**：真机见过数据源插件处于升级/中间态
        # 时演员页返回 0 部作品，若直接覆盖，整面作品墙会被一次临时故障清空。
        # 保留旧数据并标 ``stale``，让它按「临时故障」的短间隔重试（见 record_state）。
        if not works and record.get("errors"):
            kept = [
                dict(item)
                for item in (
                    (existing.get("works") if isinstance(existing, dict) else None) or []
                )
                if isinstance(item, dict)
            ]
            if kept:
                works = kept
                record["stale"] = True
        # first_seen 就地从旧快照继承（只有新冒出来的才记成本轮时间）
        merge_first_seen(
            existing.get("works") if isinstance(existing, dict) else None, works, stamp
        )
        record["works"] = works
        # 字段版本：低于当前版本的记录会被判定为「需要重抓」（见 _SNAPSHOT_SCHEMA）
        record["schema"] = _SNAPSHOT_SCHEMA
        record["state"] = record_state(record)
        return record

    def _baike_works(self, record: Dict[str, Any], works: List[Dict[str, Any]]) -> None:
        """从短剧百科插件取一位演员的全部作品（就地追加进 ``works``）。

        链路（全部经 ``self.chain.run_module`` 分发给 ShortDramaBaikeSource）：

        1. 快照里已缓存 ``baike_id`` → 直接 ``actor_works(actor_id)``（零引擎请求）；
        2. 没缓存 → ``search_actors(name)``，只收**归一化名字精确相等**的候选。

        任何异常都只记进 ``errors``，不会拖垮发现任务。
        """
        key = _clean_text(record.get("key"))
        if not key:
            return
        try:
            baike_id = _clean_text(record.get("baike_id"))
            if baike_id:
                cards = self.chain.run_module("actor_works", actor_id=baike_id) or []
            else:
                candidates = self.chain.run_module("search_actors", name=key) or []
                matched = [
                    row
                    for row in candidates
                    if isinstance(row, dict)
                    and _actor_name_key(row.get("name")) == _actor_name_key(key)
                    and _clean_text(row.get("actor_id"))
                ]
                if not matched:
                    # 稳定结果：站上没收录这位演员（或百科插件未安装/已停用）
                    record["errors"].append(
                        "短剧百科：未收录该演员（若百科插件未安装或已停用也会出现此提示）"
                    )
                    return
                baike_id = _clean_text(matched[0].get("actor_id"))
                record["baike_id"] = baike_id
                cards = self.chain.run_module("actor_works", actor_id=baike_id) or []
            for card in cards or []:
                candidate = baike_work_to_candidate(card)
                if candidate:
                    works.append(candidate)
            if baike_id and not cards:
                record["errors"].append("短剧百科：演员页没有作品")
        except Exception as err:  # noqa: BLE001 - 百科不可用只记错误
            record["errors"].append(f"短剧百科：查找失败（{err}）")

    # ── 发现层节奏 ──

    def snapshot_ttl_seconds(self) -> float:
        """演员快照的保鲜期（秒）= 发现间隔。

        「发现间隔」既是定时任务的轮询节奏，也是快照的 TTL：
        每轮任务把「距上次抓取已超过一个间隔」的演员重抓一遍，
        两个口径天然一致，不再分开配置。
        """
        return max(1, _to_int(self._interval_hours) or 12) * 3600.0

    def retry_seconds(self) -> float:
        """解析失败后的重试间隔（秒）。"""
        return max(1, _to_int(self._retry_minutes) or _DEFAULT_RETRY_MINUTES) * 60.0

    def _due_actor_keys(self, cached: Dict[str, Any]) -> List[str]:
        """当前到期待解析的演员（新加的 / 快照过期 / 字段版本落后 / 失败已到重试点）。"""
        ttl = self.snapshot_ttl_seconds()
        retry = self.retry_seconds()
        return [
            key
            for key in self._actors
            if record_needs_refresh(cached.get(key), ttl, retry, schema=_SNAPSHOT_SCHEMA)
        ]

    def _refresh_one(self, key: str) -> int:
        """只重解析一位演员并落盘，返回作品数（添加演员时用）。"""
        snapshot = self._load_actors()
        record = self._discover_actor(key)
        record["time"] = datetime.now().strftime(_STAMP_FORMAT)
        snapshot[key] = record
        self.save_data(_DATA_ACTORS, snapshot)
        return len(record.get("works") or [])

    def _refresh_actors(
        self, force: bool = False, only: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """刷新演员作品快照；只重解析「到期」的演员，其余沿用缓存。

        - ``force=True``（手动刷新）无视缓存全部重解析；
        - ``only=[…]`` 只重解析指定演员（失败重试任务用）。

        全部命中缓存时**不写盘也不打日志** —— 定时轮询每轮都会走这里，静默是常态。
        """
        cached = {
            key: value for key, value in self._load_actors().items() if key in self._actors
        }
        if force:
            due = list(self._actors)
        elif only is not None:
            wanted = set(only)
            due = [key for key in self._actors if key in wanted]
        else:
            due = self._due_actor_keys(cached)
        if not due:
            return self._candidates_from(cached)

        snapshot: Dict[str, Any] = dict(cached)
        for key in due:
            try:
                record = self._discover_actor(key)
            except Exception as err:  # noqa: BLE001 - 单个演员失败不影响其它演员
                logger.error(f"{PLUGIN_NAME} 解析演员「{key}」失败：{err}")
                record = {"key": key, "name": key, "works": [], "errors": [str(err)]}
            record["state"] = record_state(record)
            record["time"] = datetime.now().strftime(_STAMP_FORMAT)
            snapshot[key] = record
            # ⚠️ 逐演员**增量落盘**：首轮解析可能拉长到几十分钟，宿主 reconcile 随时会
            # 重载插件打断整轮 —— 整轮结束才写盘会把已解析的演员全部丢回去重来。
            self.save_data(_DATA_ACTORS, snapshot)
        # 只保留配置里现有的演员（用户删掉的演员其作品不该再出现在作品墙）
        snapshot = {key: snapshot[key] for key in self._actors if key in snapshot}
        self._log_actor_states(snapshot)
        self.save_data(_DATA_ACTORS, snapshot)
        return self._candidates_from(snapshot)

    @staticmethod
    def _candidates_from(snapshot: Dict[str, Any]) -> List[Dict[str, Any]]:
        """把快照摊平成作品行列表（同一部剧被多位演员参演时只保留一条，后见覆盖先见）。"""
        rows: Dict[str, Dict[str, Any]] = {}
        for key, record in snapshot.items():
            if not isinstance(record, dict):
                continue
            actor = _clean_text(record.get("name")) or key
            for work in record.get("works") or []:
                if not isinstance(work, dict):
                    continue
                row = work_row(work, actor, key)
                rows[row["key"]] = row
        return list(rows.values())

    def _work_rows(
        self, query: Optional[Dict[str, Any]] = None
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """作品墙数据（可单测）：先算筛选前的全集，再按查询参数过滤 + 排序。

        :param query: 查询条件（``actor`` / ``genre`` / ``year`` / ``studio`` /
            ``sort`` / ``keyword``）。不传 = 不过滤、按默认排序
            （``api_status`` 只取统计口径，走这条路）。

        ``is_new`` **不落盘**，每次查询现算 —— 过期的「新」自动消失，读旧快照也不会
        显示过期标记。
        """
        snapshot = {
            key: value for key, value in self._load_actors().items() if key in self._actors
        }
        rows: Dict[str, Dict[str, Any]] = {}
        actor_counts: Dict[str, int] = {}
        for key, record in snapshot.items():
            if not isinstance(record, dict):
                continue
            actor = _clean_text(record.get("name")) or key
            baseline = stamp_epoch(record.get("baseline_at"))
            works = record.get("works") or []
            actor_counts[actor] = len(works)
            for work in works:
                if not isinstance(work, dict):
                    continue
                row = work_row(work, actor, key)
                row["is_new"] = is_fresh_work(work, time.time(), baseline)
                seen = rows.get(row["key"])
                if seen:
                    # 同一部剧多位演员参演时合并演员名（「A / B」），命中任一演员的筛选都算
                    owners = {
                        item.strip()
                        for item in str(seen.get("actor") or "").split(" / ")
                        if item.strip()
                    }
                    owners.add(actor)
                    merged = " / ".join(sorted(owners))
                    # 新旧快照并存的同一部剧：早年作品卡「年份恒空」、字段残缺，
                    # 不能拿残缺的做底（空年份 + 失真的「新」标记都会上墙）——
                    # 字段更全的行顶上，演员归属无论谁做底都要合并
                    if not _clean_text(seen.get("year")) and _clean_text(row.get("year")):
                        row["actor"] = merged
                        rows[row["key"]] = row
                    else:
                        seen["actor"] = merged
                    continue
                rows[row["key"]] = row

        all_rows = list(rows.values())

        # ── 在库判定（与宿主媒体详情页同一套口径）──
        # ``in_library`` 和 ``is_new`` 一样**不落盘**、每次查询现算：媒体库是活的，
        # 落盘的结论会过期。探针内部带 TTL 缓存，同一批作品反复打开墙面零查询。
        # 三态：True 在库 / False 不在库 / None 未知（查不了）——未知不参与统计、
        # 也不被「只看未入库」排除，免得把「没查成」说成「都不在库」。
        probe = self.library_probe
        for row in all_rows:
            row["in_library"] = probe.lookup(row)
        known = [row for row in all_rows if row.get("in_library") is not None]

        summary = {
            "total": len(all_rows),
            "new": sum(1 for row in all_rows if row.get("is_new")),
            # 「已在库」统计只在**至少查成一条**时才给：整个库表都查不了时
            # library_known=0，前端据此隐藏统计与「只看未入库」开关
            "library_known": len(known),
            "in_library": sum(1 for row in known if row.get("in_library") is True),
            "actors": [
                {
                    "key": _clean_text(record.get("name")) or key,
                    "name": _clean_text(record.get("name")) or key,
                    "works": len(record.get("works") or []),
                    "state": _clean_text(record.get("state")),
                }
                for key, record in snapshot.items()
                if isinstance(record, dict)
            ],
            # 筛选项基于**全集**算：选项不随勾选跳动
            "facets": build_facets(all_rows),
        }

        # ── 查询参数：筛选 → 排序 ──
        params = query if isinstance(query, dict) else {}
        filtered = filter_works(
            all_rows,
            actor=_clean_text(params.get("actor")),
            genre=_clean_text(params.get("genre")),
            year=_clean_text(params.get("year")),
            studio=_clean_text(params.get("studio")),
            only_not_in_library=_to_bool(params.get("only_not_in_library")),
            keyword=_clean_text(params.get("keyword")),
        )
        return sort_works(filtered, _clean_text(params.get("sort"))), summary

    @property
    def library_probe(self) -> _LibraryProbe:
        """作品在库探针（实例级复用：TTL 缓存跨请求生效，进程里只建一个 Oper）。"""
        probe = getattr(self, "_probe", None)
        if probe is None:
            probe = _LibraryProbe()
            self._probe = probe
        return probe

    def _actor_row(self, key: str, record: Any) -> Dict[str, Any]:
        """演员列表的一行（状态 / 作品数 / 错误原因）。"""
        record = record if isinstance(record, dict) else {}
        return {
            "key": key,
            "name": _clean_text(record.get("name")) or key,
            "baike_id": _clean_text(record.get("baike_id")),
            "works": len(record.get("works") or []),
            "state": _clean_text(record.get("state")),
            "time": _clean_text(record.get("time")),
            "errors": [str(item) for item in record.get("errors") or []],
        }

    def _collect_fresh(self, before: Dict[str, Any]) -> List[Dict[str, Any]]:
        """对比刷新前后的快照，找出这一轮**新出现**的作品。

        只统计「刷新前已经有快照」的演员 —— 首次建立基线那一轮的全部作品都不算新，
        否则一次导入十几位演员会整片标成新作品。
        """
        after = self._load_actors()
        fresh: List[Dict[str, Any]] = []
        for key, record in after.items():
            if not isinstance(record, dict):
                continue
            old = before.get(key)
            if not isinstance(old, dict) or not old.get("works"):
                continue
            old_keys = {
                work_key(work.get("title") or "", work.get("year") or "")
                for work in old.get("works") or []
                if isinstance(work, dict)
            }
            # 早年快照的作品没有年份（``year`` 恒空），字段升级后完整键会变
            # ⇒ 同时按剧名比对，否则整墙作品会被误判成本轮新出现的
            old_titles = {
                normalize_title(work.get("title") or "")
                for work in old.get("works") or []
                if isinstance(work, dict)
            }
            actor = _clean_text(record.get("name")) or key
            for work in record.get("works") or []:
                if not isinstance(work, dict):
                    continue
                if work_key(work.get("title") or "", work.get("year") or "") in old_keys:
                    continue
                if normalize_title(work.get("title") or "") in old_titles:
                    continue
                fresh.append({"actor": actor, **work})
        return fresh

    def _notify_fresh(self, fresh: List[Dict[str, Any]]) -> None:
        """新作品汇总通知（一条，不逐条刷屏）。"""
        if not fresh or not self._notify:
            return
        lines = [f"发现 {len(fresh)} 部新作品："]
        for item in fresh[:10]:
            title = _clean_text(item.get("title"))
            actor = _clean_text(item.get("actor"))
            lines.append(f"· {actor}：{title}")
        if len(fresh) > 10:
            lines.append(f"· ……另有 {len(fresh) - 10} 部")
        try:
            self.post_message(
                mtype=_MessageType.Plugin,
                title=f"【{self.plugin_name}】新作品",
                text="\n".join(lines),
            )
        except Exception as err:  # noqa: BLE001 - 通知失败不该影响发现结果
            logger.warning(f"{PLUGIN_NAME} 发送新作品通知失败：{err}")

    @staticmethod
    def _log_actor_states(snapshot: Dict[str, Any]) -> None:
        """把整轮演员状态汇总成最多两条日志（等待重试 / 百科未收录）。"""
        waiting: List[str] = []
        empty: List[str] = []
        for key, record in snapshot.items():
            name = _clean_text(record.get("name")) or key
            state = _clean_text(record.get("state"))
            if state == "waiting":
                waiting.append(name)
            elif state == "empty":
                empty.append(name)
        if waiting:
            logger.info(
                f"{PLUGIN_NAME} 暂未取到作品的演员（会自动重试）：{'、'.join(waiting)}"
            )
        if empty:
            logger.info(f"{PLUGIN_NAME} 短剧百科未收录的演员：{'、'.join(empty)}")

    # ── 任务 ──

    def refresh_works_task(self, trigger: str = "interval") -> bool:
        """定时发现任务：刷新演员作品快照，新作品发一条汇总通知。

        ⚠️ 这里**不下载、不订阅** —— 插件只负责把作品摆到墙上，追哪部由用户在墙上点
        「订阅」，后续搜索 / 下载 / 整理全部由宿主订阅系统接管。
        """
        if not self.get_state() or not self._actors:
            return False
        if not self._lock.acquire(blocking=False):
            logger.info(f"{PLUGIN_NAME} 上一轮刷新还在进行，本次跳过（{trigger}）")
            return False
        try:
            before = self._load_actors()
            self._refresh_actors()
            fresh = self._collect_fresh(before)
            self._notify_fresh(fresh)
            rows, summary = self._work_rows()
            self._last_result = {
                "trigger": trigger,
                "works": summary.get("total", 0),
                "new": len(fresh),
            }
            logger.info(
                f"{PLUGIN_NAME} 作品发现完成（{trigger}）：{len(self._actors)} 位演员、"
                f"{summary.get('total', 0)} 部作品"
                + (f"，新增 {len(fresh)} 部" if fresh else "")
            )
            return True
        except Exception as err:  # noqa: BLE001 - 兜底，避免定时任务挂掉
            logger.error(f"{PLUGIN_NAME} 作品发现异常：{err}")
            return False
        finally:
            self._lock.release()

    def retry_failed_actors(self, trigger: str = "interval") -> bool:
        """失败重试任务：只重解析「到期的失败演员」。

        与完整刷新分开，是因为两者时间尺度不同：快照一天刷一次，而失败的演员
        20 分钟后就该再试一次（百科插件一恢复就能自己好，不必等满一天）。
        """
        if not self.get_state() or not self._actors:
            return False
        cached = self._load_actors()
        due = [
            key for key in self._due_actor_keys(cached) if is_retry_candidate(cached.get(key))
        ]
        if not due:
            return False
        if not self._lock.acquire(blocking=False):
            return False
        try:
            before = {
                key: _clean_text((cached.get(key) or {}).get("state"))
                for key in self._actors
                if isinstance(cached.get(key), dict)
            }
            before_snapshot = dict(cached)
            self._refresh_actors(only=due)
            after = self._load_actors()
            recovered = [
                key
                for key, state in before.items()
                if state == "waiting"
                and _clean_text((after.get(key) or {}).get("state")) != "waiting"
            ]
            fresh = self._collect_fresh(before_snapshot)
            self._notify_fresh(fresh)
            logger.info(
                f"{PLUGIN_NAME} 解析失败重试完成（{trigger}）：重试 {len(due)} 位"
                + (f"，已恢复 {len(recovered)} 位：{'、'.join(recovered)}" if recovered else "")
            )
            return True
        except Exception as err:  # noqa: BLE001 - 兜底
            logger.error(f"{PLUGIN_NAME} 失败重试异常：{err}")
            return False
        finally:
            self._lock.release()

    # ── 工具 ──

    def _load_actors(self) -> Dict[str, Any]:
        """加载演员快照；没有数据时返回空字典（首次运行）。"""
        data = self.get_data(_DATA_ACTORS)
        return data if isinstance(data, dict) else {}

    def _add_once_job(
        self,
        delay_seconds: float = 3,
        trigger: str = "once",
        func: Optional[Any] = None,
        job_id: str = _ONCE_JOB_ID,
    ) -> bool:
        """向宿主调度器登记一次性任务（立即刷新一次）。

        ⚠️ 关键字是 ``func_kwargs``（不是 ``kwargs``），传错会被内部 try/except 吞掉，
        只留一条错误日志，表现为「手动运行没反应」。
        """
        try:
            from app.sdk import scheduler as scheduler_sdk

            add_once = getattr(scheduler_sdk, "add_plugin_once_job", None)
            if not add_once:
                logger.warning(f"{PLUGIN_NAME} 当前宿主不支持一次性任务接口")
                return False
            add_once(
                self.__class__.__name__,
                job_id,
                func or self.refresh_works_task,
                f"{PLUGIN_NAME}执行",
                delay_seconds=delay_seconds,
                func_kwargs={"trigger": trigger},
            )
            return True
        except Exception as err:  # pragma: no cover - 宿主版本差异兜底
            logger.warning(f"{PLUGIN_NAME} 登记一次性任务失败：{err}")
            return False
