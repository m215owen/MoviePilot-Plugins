"""短剧演员订阅（MoviePilot V3 插件后端）。

一句话：跟着演员追短剧 —— 用「演员 → 作品列表 → 剧名 → 站点搜索 → 下载 → 整理」
这条**不依赖宿主识别器**的链路，把喜欢的演员参演的短剧自动下回来。

为什么不用宿主订阅系统
----------------------
宿主的订阅链路必须先建立「媒体身份」（``media_source`` + ``media_id``，通常是 TMDB id），
而短剧恰好死在这一步。对目标实例的实测结果：

* 头部/出圈的短剧 TMDB 有收录（古相思曲、东栏雪、虚颜、夜色将明…），能识别，但一律被
  归成「电视剧」（宿主没有「短剧」这个媒体类型）。
* 长尾短剧 TMDB 与豆瓣都没有条目，识别器建不起身份。
* 更关键的是：**资源其实就在站点上**。实测 ``/search/title?keyword=闪婚老公是豪门``
  在 AGSVPT 命中 2 条（全 90 集 / 全 100 集），但同一批结果的 ``media_info`` 全部为
  ``null``、``candidate_recognized`` 全部为 0 —— 剧名精确匹配、资源就在眼前，宿主依然
  建立不起媒体身份，订阅因此永远不触发。

所以本插件绕开识别器：用**剧名**直接在站点搜索，用**账本**记录「哪个种子对应哪部剧」，
整理时直接查账本而不是猜文件名。

决策基线（本插件据此实现，改动前先看这里）
------------------------------------------
1. 发现源 = TMDB + 豆瓣**并集**，任一可用即可工作，两源都失败才报错。
2. 候选范围 = **仅演员本人**（不含编剧/导演）。
3. 轮询 = **真订阅**：定时轮询 + 已下账本（ledger），已下过的剧不重复下载。
4. 匹配主键 = 剧名（**含序号**，如「云渺3：镇魔世家」的 3）归一化后**精确相等**。
5. 年份 = 可选校验；**任一侧缺失即放行**（宽进）。
6. 去重键 = 剧名 + 年份(可空)，**不含集数**。同一部剧的 90 集版与 100 集整合版是
   同一部剧，键里带集数会把它们判成两部而重复下载、重复入库。
7. 集数 = 仅**信息字段**（通知里展示「全 90 集」），不参与匹配与去重。
8. 同一部剧多个资源包 → **择优一条**：做种数 → 体积(码率代理) → 分辨率。
9. 多剧合集包 → **忽略**（剧名匹配天然匹配不到它）。
10. 整理入库**自建**：用账本中「种子 → 剧名/年份」的已知映射定位文件。

已知的召回缺口（实测到、但按基线选择接受）
------------------------------------------
站点上传者写的剧名可能与豆瓣/TMDB 不完全一致，例如站点的
``我的闪婚老公是豪门`` 对豆瓣的 ``闪婚老公是豪门``（多了「我的」前缀）。严格精确匹配
会漏掉这类。当前按基线 4 保持严格匹配，宁可漏也不错配；如需提高召回，应新增一条
显式的「前缀容忍」规则，而不是放宽精确相等。

V3 契约要点
-----------
1. **依赖入口**：宿主依赖一律走 ``app.sdk.*`` 稳定入口；站点搜索走公开的
   ``app.chain.torrents.TorrentsChain``。不使用 ``app.core`` / ``app.helper`` / ``app.utils``。
2. **渲染模式**：``vue``（Vue 模块联邦）。配置页 / 详情页 / 仪表板 / 侧栏全页由
   ``dist/assets`` 里的联邦组件渲染（暴露 ``Page`` / ``Config`` / ``Dashboard`` /
   ``AppPage`` / ``AppPageSettings``），后端只提供 ``get_api()`` 接口，
   **不再下发 Vuetify 组件 JSON**（``get_form`` / ``get_page`` 返回空壳）。
3. **站内组件白名单**：只使用在目标宿主（v3.1.3）上被在产插件实际验证过的组件 ——
   ``VForm`` / ``VRow`` / ``VCol`` / ``VSwitch`` / ``VTextField`` / ``VTextarea`` /
   ``VSelect`` / ``VAlert`` / ``VTable``（含原生 ``thead`` / ``tbody`` / ``tr`` / ``th`` / ``td``）。
   宿主按需自动注册 Vuetify 组件，未注册的组件会被渲染成空元素且不报错。
4. **配置与数据**：一律走基类方法（``get_data`` / ``save_data`` / ``update_config``），
   且以 ``self.__class__.__name__`` 推导 ID，兼容插件虚拟分身。
5. **不在模块导入期**做网络、数据库或任务启动。
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import re
import shutil
import threading
import time
from datetime import datetime
from pathlib import Path
from random import choice
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib import parse

from apscheduler.triggers.interval import IntervalTrigger

from app.schemas.types import EventType, MediaType
from app.sdk.config import settings
from app.sdk.events import Event, eventmanager
from app.sdk.logging import logger
from app.sdk.network import RequestUtils
from app.sdk.plugin import _PluginBase

# 消息类型枚举在宿主版本间存在改名：V3.1+ 使用 MessageType，更早的实现使用 NotificationType。
# 这里做一次兼容性导入，避免因宿主版本差异导致插件整体加载失败。
try:  # pragma: no cover - 取决于宿主版本
    from app.schemas.types import MessageType as _MessageType
except ImportError:  # pragma: no cover
    from app.schemas.types import NotificationType as _MessageType  # type: ignore

# 插件展示名，同时作为下载器标签与通知标题
PLUGIN_NAME = "短剧演员订阅"

# 框架模块：站点搜索与下载器属于可选能力，缺失时插件仍应能加载（只是不能下载）
try:
    from app.sdk.network import SitesHelper
    from app.sdk.services import DownloaderHelper
    from app.chain.torrents import TorrentsChain

    HAS_FRAMEWORK = True
except ImportError as _err:  # pragma: no cover - 取决于宿主版本
    HAS_FRAMEWORK = False
    logger.warning(f"{PLUGIN_NAME} 部分框架模块不可用：{_err}")


# ─────────────────────────── 常量 ───────────────────────────

# 插件数据键（写入插件数据目录，不写回源码目录）
_DATA_ACTORS = "actors_state"
_DATA_LEDGER = "ledger"
_DATA_STATS = "stats"
_DATA_MISS = "misses"

# 未命中冷却：站点上暂时没有资源的剧，不必每轮都全站重搜（一位演员最多 40+10 部候选，
# 不加冷却会每 6 小时对站点发起几十次注定空手而归的搜索）。搜过但没下到的剧记录时间戳，
# 冷却期内直接跳过；已下载的剧由账本负责去重，冷却表只覆盖「搜过但没下到」的情形。
_MISS_COOLDOWN_HOURS = 24

# 一次性任务 ID
_ONCE_JOB_ID = "refresh_once"
# 只刷新作品快照（不下载）的一次性任务 ID，与上面分开以免互相覆盖
_ONCE_JOB_ID_WORKS = "refresh_works_once"

# 下载器标签：便于在下载器里一眼认出哪些种子由本插件发起
_DOWNLOAD_TAG = PLUGIN_NAME

# 站点「短剧分类」识别关键词。站点分类结构形如
# {"tv": [{"id": 419, "cat": "TV", "desc": "Playlet/短剧"}], "field": "cat"}
_SHORT_DRAMA_CATEGORY_HINTS = ("短剧", "微短", "竖屏", "playlet", "short drama", "shortdrama")

# 一个剧名归一化后的最小长度：低于该长度不做「包含式」目录匹配，避免误命中
_MIN_TITLE_FOR_LOOSE_MATCH = 4

# TMDB combined_credits 会返回演员的全部作品（可能上百条），逐条去站点搜索成本过高，
# 因此按年份倒序只保留最近的一批。豆瓣侧受接口限制最多只有 10 条，这里按下限放宽，
# 保证并集不丢近期作品（尤其短剧演员的产出集中在近一两年）。
_TMDB_CREDITS_LIMIT = 40

# 全角 ASCII → 半角（用于剧名归一化；0x3000 是全角空格）
_FULLWIDTH_MAP = {code: code - 0xFEE0 for code in range(0xFF01, 0xFF5F)}
_FULLWIDTH_MAP[0x3000] = 0x20

# 季/部标记：归一化剧名时剔除。注意「云渺3」这类**片名序号不属于季标记**，必须保留。
_SEASON_TOKEN_PATTERNS = (
    re.compile(r"(?:full\s*)?season\s*0*\d+", re.IGNORECASE),
    # 排除 S01E02 这种「季+集」连写，避免把集数标记也吃掉
    re.compile(r"[sS]0*\d{1,2}(?!\d)(?!\s*[eE]\d)"),
    re.compile(r"第\s*0*\d+\s*[季部]"),
    re.compile(r"第\s*[一二三四五六七八九十]+\s*[季部]"),
)

# 集数标记：只作为信息字段，同时必须从剧名里剔除以免影响归一化
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

# 年份：只认 4 位且带边界，避免把分辨率（2160p）或集数当年份
_YEAR_TOKEN = re.compile(r"(?:19|20)\d{2}")

# 种子标题中「剧名」与「技术尾巴」的分界标记
_TITLE_STOP_TOKEN = re.compile(
    r"^(?:19|20)\d{2}$"          # 年份
    r"|^[sS]\d{1,2}(?:[eE]\d{1,4})?$"  # S01 / S01E02
    r"|^\d{3,4}[piPI]$"          # 1080p / 720i
    r"|^4K$|^UHD$|^FHD$|^SD$"    # 分辨率别名
    r"|^第[0-9一二三四五六七八九十]+[季部]$",
    re.IGNORECASE,
)

# 分辨率 → 分数（择优排序的最后一级）
_RESOLUTION_SCORES = (
    ("2160", 2160),
    ("4K", 2160),
    ("UHD", 2160),
    ("1440", 1440),
    ("2K", 1440),
    ("1080", 1080),
    ("720", 720),
    ("576", 576),
    ("480", 480),
)

# 豆瓣人物主页地址 → 人物 ID（允许用户直接粘贴链接）
_PERSON_URL_PATTERN = re.compile(r"(?:personage|celebrity)/(\d+)")

# 豆瓣登录态提示文案
_NEED_LOGIN_HINT = "豆瓣要求登录（need_login），匿名搜索额度极低，建议在 CookieCloud 中同步豆瓣登录态"
_COOKIE_EXPIRED_HINT = "豆瓣 Cookie 已失效，请重新登录豆瓣并同步到 CookieCloud"
_RATE_LIMIT_HINT = "豆瓣接口限流，稍后会自动重试"


# ─────────────────────────── 纯函数（可单测） ───────────────────────────


def _clean_text(value: Any) -> str:
    """统一清洗外部文本：去首尾空白、把多余空白压成单个空格。"""
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _to_int(value: Any) -> int:
    """宽松整数转换，失败返回 0（用于做种数等站点字段）。"""
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _to_float(value: Any) -> float:
    """宽松浮点转换，失败返回 0.0（用于体积等站点字段）。"""
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _conf_field(item: Any, field: str, default: Any = None) -> Any:
    """从宿主的配置对象里取字段。

    宿主配置项在版本间可能是 pydantic 模型（``DownloaderConf`` /
    ``TransferDirectoryConf``）也可能是原始 dict，这里两种形状都兼容，
    避免因为一处``getattr``/``get`` 用法不对就让整个下拉静默变空。
    """
    if isinstance(item, dict):
        return item.get(field, default)
    return getattr(item, field, default)


def normalize_title(title: str) -> str:
    """把剧名归一化成可比较的键。

    处理顺序：全角转半角 → 去非法字符 → 剔除季/部标记 → 剔除集数标记 →
    去标点与空白 → 转小写。

    **片名中的序号必须保留**：「云渺3：镇魔世家」和「云渺4：绝嗣佛子」是两部独立的剧，
    序号是它们唯一的区分键（年份不足以区分，两者都是 2025）。
    """
    text = str(title or "").strip()
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


def extract_year(text: str) -> str:
    """从文本中提取年份（1900-2099），取第一个可信的 4 位数字。

    只认**未被 ASCII 字母包夹**的 4 位数字，从而排除 ``2160p`` / ``x2049`` 这类噪声；
    但允许后面紧跟汉字（``2024年``），这是中文站点的常见写法。
    """
    source = str(text or "")
    for match in _YEAR_TOKEN.finditer(source):
        start, end = match.span()
        before = source[start - 1] if start > 0 else ""
        after = source[end] if end < len(source) else ""
        if (before.isascii() and before.isalpha()) or (after.isascii() and after.isalpha()):
            continue
        return match.group(0)
    return ""


def extract_episode_count(text: str) -> int:
    """从站点副标题里提取总集数（如「全90集」→ 90）。

    仅用于通知展示，**不参与匹配与去重**（见决策基线 7）。
    """
    source = str(text or "")
    for pattern in (re.compile(r"共\s*(\d+)\s*集"), re.compile(r"全\s*(\d+)\s*集"), re.compile(r"(\d+)\s*集")):
        match = pattern.search(source)
        if match:
            return _to_int(match.group(1))
    return 0


def resolution_score(text: str) -> int:
    """把分辨率折算成分数，仅用作择优排序的最后一级。"""
    upper = str(text or "").upper()
    for token, score in _RESOLUTION_SCORES:
        if token in upper:
            return score
    return 0


def torrent_title_head(title: str) -> str:
    """截取种子标题里「剧名」那一段，丢掉年份/季集/分辨率/编码等尾巴。

    站长通常把剧名（多为拼音）写在最前面，例如
    ``Wo De Shan Hun Lao Gong Shi Hao Men 2024 S01 720p WEB-DL AVC AAC-GodDramas``，
    截断后得到 ``Wo De Shan Hun Lao Gong Shi Hao Men``。它等于剧名的拼音，
    因此能与 TMDB 提供的英文名/原名对上，作为多语言别名的兜底。
    """
    head: List[str] = []
    for token in str(title or "").split():
        if _TITLE_STOP_TOKEN.match(token):
            break
        head.append(token)
    return " ".join(head)


def torrent_title_candidates(torrent: Dict[str, Any]) -> List[str]:
    """列出一条搜索结果里可用来比对剧名的候选片段。

    站点种子的中文剧名通常写在**副标题**里，惯例是
    ``剧名 | 全X集 | 年份 | 网络收费短剧 | 类型：…``，因此按分隔符切开全部保留；
    再把正标题的「剧名段」作为拼音别名补上。
    """
    candidates: List[str] = []
    description = str(torrent.get("description") or "")
    for part in re.split(r"[|｜/／]", description):
        part = _clean_text(part)
        if part:
            candidates.append(part)
    head = _clean_text(torrent_title_head(torrent.get("title") or ""))
    if head:
        candidates.append(head)
    return candidates


def title_matches(torrent: Dict[str, Any], aliases: List[str]) -> bool:
    """判定一条搜索结果是否命中目标剧。

    规则（决策基线 4）：把种子侧候选片段与目标剧的全部别名分别归一化，要求
    **精确相等**。别名可包含中文名与英文/原名，用于覆盖拼音命名的种子。
    """
    wanted = {normalize_title(item) for item in aliases if normalize_title(item)}
    if not wanted:
        return False
    for candidate in torrent_title_candidates(torrent):
        if normalize_title(candidate) in wanted:
            return True
    return False


def year_compatible(torrent_year: str, want_year: str) -> bool:
    """年份校验（决策基线 5）：任一侧缺失即放行，两侧都有才要求相等。"""
    if not want_year or not torrent_year:
        return True
    return str(torrent_year) == str(want_year)


def pick_best(torrents: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """在同剧的多个资源包里择优一条（决策基线 8）。

    排序键：``做种数 → 体积(码率代理) → 分辨率``。
    做种数优先体现「**能下得动 > 画质好**」——短剧做种普遍稀少，先保证下载成功率。
    刻意**不使用集数**：短剧整包发布，集数差异来自整合版本，不代表质量优劣。
    """
    if not torrents:
        return None

    def _key(item: Dict[str, Any]) -> Tuple[int, float, int]:
        return (
            _to_int(item.get("seeders")),
            _to_float(item.get("size")),
            resolution_score(item.get("title")),
        )

    return max(torrents, key=_key)


def detect_short_drama_category(indexer: Optional[Dict[str, Any]]) -> str:
    """从站点索引配置里探测「短剧分类」的 ID，探测不到返回空串。

    宿主 ``TorrentsChain.browse(domain, cat=…)`` 支持按分类过滤，把搜索收窄到站点的
    短剧区能显著降低同名误命中。分类结构形如::

        {"tv": [{"id": 419, "cat": "TV", "desc": "Playlet/短剧"}], "field": "cat"}

    站点没有短剧分类（实测馒头 13 个分类里没有）时返回空串，调用方退化为全站关键词搜索。
    """
    if not isinstance(indexer, dict):
        return ""
    categories = indexer.get("category")
    if not isinstance(categories, dict):
        return ""
    for key, items in categories.items():
        if key == "field" or not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            label = f"{item.get('desc') or ''} {item.get('cat') or ''}".lower()
            if any(hint in label for hint in _SHORT_DRAMA_CATEGORY_HINTS):
                category_id = str(item.get("id") or "").strip()
                if category_id:
                    return category_id
    return ""


def ledger_key(title: str, year: str) -> str:
    """账本键 = 归一化剧名 + 年份(可空)。

    **刻意不含集数**（决策基线 6）：同一部剧的 90 集版与 100 集整合版必须落到同一个键，
    否则会被当成两部剧重复下载、重复入库。
    """
    return f"{normalize_title(title)}|{str(year or '').strip()}"


def site_domain_of(url: str) -> str:
    """从种子链接里取出站点域名（用于回查站点 Cookie）。"""
    try:
        parsed = parse.urlparse(str(url or ""))
        domain = parsed.netloc or ""
        if domain:
            return domain
        # 少数站点用磁力/相对链接，退回按 '/' 切分
        return str(url or "").split("/")[2] if str(url or "").count("/") >= 2 else ""
    except Exception:  # pragma: no cover - 解析失败按空域名处理
        return ""


# ─────────────────────────── CookieCloud ───────────────────────────


class _CookieCloudClient:
    """从 CookieCloud 取指定域名的 Cookie。

    为什么不自己解密：CookieCloud 服务端支持 ``POST /get/{key}`` 带密码直接返回**已解密**的
    ``cookie_data``，插件因此不必实现 AES 解密，只依赖 ``app.sdk.network`` 即可。

    Cookie 只留在内存里，不落盘、不写日志，避免把登录态持久化。
    """

    TIMEOUT = 20

    def __init__(self, host: str = "", key: str = "", password: str = "") -> None:
        self._host = str(host or "").strip().rstrip("/")
        self._key = str(key or "").strip()
        self._password = str(password or "").strip()
        self.last_error = ""

    @property
    def configured(self) -> bool:
        """服务器地址、用户 KEY、加密密码三者齐全才算配置可用。"""
        return bool(self._host and self._key and self._password)

    def fetch(self, domain_keyword: str) -> str:
        """取包含 ``domain_keyword`` 的域名分组，拼成可直接使用的 Cookie 头。"""
        self.last_error = ""
        if not self.configured:
            self.last_error = "CookieCloud 未配置（缺服务器地址 / KEY / 密码）"
            return ""

        response = None
        try:
            response = RequestUtils(content_type="application/json", timeout=self.TIMEOUT).post_res(
                url=f"{self._host}/get/{self._key}", json={"password": self._password}
            )
            if response is None:
                self.last_error = "CookieCloud 请求失败（网络不可达或地址有误）"
                return ""
            if response.status_code != 200:
                self.last_error = f"CookieCloud 返回 HTTP {response.status_code}"
                return ""
            payload = response.json()
        except Exception as err:  # noqa: BLE001 - 任何异常都降级为「取不到」
            self.last_error = f"CookieCloud 请求异常：{err}"
            return ""
        finally:
            if response is not None:
                try:
                    response.close()
                except Exception:  # pragma: no cover - 关闭失败可忽略
                    pass

        contents = payload.get("cookie_data") if isinstance(payload, dict) else None
        if not isinstance(contents, dict):
            self.last_error = (
                "CookieCloud 只返回了密文（服务端未解密），请在插件配置里手工粘贴豆瓣 Cookie"
                if isinstance(payload, dict) and payload.get("encrypted")
                else "CookieCloud 返回内容为空"
            )
            return ""

        pairs: List[str] = []
        seen: set = set()
        for domain, cookies in contents.items():
            if domain_keyword not in str(domain).lower() or not isinstance(cookies, list):
                continue
            for item in cookies:
                if not isinstance(item, dict):
                    continue
                name, value = item.get("name"), item.get("value")
                if not name or value is None or name in seen:
                    continue
                seen.add(name)
                pairs.append(f"{name}={value}")

        if not pairs:
            self.last_error = f"CookieCloud 里没有 {domain_keyword} 的 Cookie（请确认浏览器已登录并同步）"
            return ""
        return "; ".join(pairs)


# ─────────────────────────── 豆瓣发现源 ───────────────────────────


class _DoubanClient:
    """豆瓣 Frodo API 的轻量客户端（插件内自持，不依赖宿主内部模块）。

    签名规则与豆瓣移动端一致：``_sig = base64(hmac_sha1(secret, "GET&" + quote(path) + "&" + _ts))``。
    ``path`` 必须是**完整请求路径**（含 ``/api/v2`` 前缀），漏掉前缀会直接 400。
    """

    BASE_URL = "https://frodo.douban.com/api/v2"
    SIGN_BASE_PATH = "/api/v2"
    API_KEY = "0dad551ec0f84ed02907ff5c42e8ec70"
    API_SECRET = "bf7dddc7c9cfe6f7"
    TIMEOUT = 15

    # 作品集接口单次最多 10 条，且 start > 0 一律返回空，即**不支持翻页**，
    # 因此每位演员实际只能取到最近 10 部作品。
    MAX_WORKS_PER_REQUEST = 10
    SORT_ORDERS = ("time", "collection")

    RATE_LIMIT_STATUS = frozenset({403, 429, 503})
    RATE_LIMIT_RETRIES = 2
    RATE_LIMIT_BACKOFF = 1.5
    POLITE_DELAY = 0.35

    USER_AGENTS = (
        "api-client/1 com.douban.frodo/7.22.0.beta9(231) Android/23 product/Mate 40 "
        "vendor/HUAWEI model/Mate 40 brand/HUAWEI  rom/android  network/wifi  platform/AndroidPad",
        "api-client/1 com.douban.frodo/7.18.0(230) Android/22 product/MI 9 vendor/Xiaomi "
        "model/MI 9 brand/Android  rom/miui6  network/wifi  platform/mobile nd/1",
    )

    def __init__(self, proxy: bool = False, cookie: str = "") -> None:
        self._proxy = proxy
        self._cookie = str(cookie or "").strip()
        self._last_request_at = 0.0
        self.last_status = 0
        self.last_error = ""
        self.last_need_login = False
        self.last_body = ""
        self.search_calls = 0

    @classmethod
    def _sign(cls, url_path: str, ts: str) -> str:
        """按豆瓣移动端规则生成 ``_sig``。"""
        path = url_path if url_path.startswith(cls.SIGN_BASE_PATH) else f"{cls.SIGN_BASE_PATH}{url_path}"
        raw = "&".join(["GET", parse.quote(path, safe=""), ts])
        digest = hmac.new(cls.API_SECRET.encode(), raw.encode(), hashlib.sha1).digest()
        return base64.b64encode(digest).decode()

    def _wait_turn(self) -> None:
        """维持相邻请求之间的最小间隔，降低触发限流的概率。"""
        gap = time.monotonic() - self._last_request_at
        if gap < self.POLITE_DELAY:
            time.sleep(self.POLITE_DELAY - gap)
        self._last_request_at = time.monotonic()

    def _request_once(self, url_path: str, params: Dict[str, Any], proxies: Any):
        """发起一次带签名的 GET，返回 ``(status, payload)``；网络层失败返回 None。"""
        self._wait_turn()
        response = None
        try:
            response = RequestUtils(
                ua=choice(self.USER_AGENTS),
                proxies=proxies,
                cookies=self._cookie or None,
                timeout=self.TIMEOUT,
            ).get_res(url=f"{self.BASE_URL}{url_path}", params=params)
            if response is None:
                self.last_error = "豆瓣请求无响应"
                return None
            status = response.status_code
            self.last_status = status
            if status != 200:
                try:
                    self.last_body = (response.text or "")[:300]
                except Exception:  # pragma: no cover - 读取失败不影响判定
                    self.last_body = ""
                if "need_login" in self.last_body:
                    self.last_need_login = True
                return status, None
            payload = response.json()
            return status, (payload if isinstance(payload, dict) else None)
        except Exception as err:
            self.last_error = str(err)
            logger.error(f"{PLUGIN_NAME} 请求豆瓣接口失败（{url_path}）：{err}")
            return None
        finally:
            if response is not None:
                try:
                    response.close()
                except Exception:  # pragma: no cover - 关闭失败可忽略
                    pass

    def _get(self, url_path: str, **kwargs: Any) -> Optional[Dict[str, Any]]:
        """发起一次签名 GET；限流时按指数退避重试，失败不抛异常。"""
        ts = datetime.now().strftime("%Y%m%d")
        params: Dict[str, Any] = dict(kwargs)
        params.update(
            {
                "os_rom": "android",
                "apiKey": self.API_KEY,
                "_ts": ts,
                "_sig": self._sign(url_path, ts),
            }
        )
        proxies = getattr(settings, "PROXY", None) if self._proxy else None

        self.last_status = 0
        self.last_error = ""
        self.last_need_login = False
        self.last_body = ""

        for attempt in range(self.RATE_LIMIT_RETRIES + 1):
            outcome = self._request_once(url_path, params, proxies)
            if outcome is None:
                return None
            status, payload = outcome
            if status == 200:
                return payload
            if status in self.RATE_LIMIT_STATUS:
                # need_login 说明匿名请求被挡在门外，退避重试基本无效，直接放弃更省配额
                if self.last_need_login and not self._cookie:
                    self.last_error = "豆瓣要求登录（need_login）"
                    return None
                self.last_error = f"豆瓣限流（HTTP {status}）"
                if attempt < self.RATE_LIMIT_RETRIES:
                    time.sleep(self.RATE_LIMIT_BACKOFF * (2**attempt))
                    continue
                return None
            self.last_error = f"豆瓣接口返回 HTTP {status}"
            return None
        return None

    def failure_hint(self) -> str:
        """按最近一次失败的成因给出**可操作**的提示。"""
        if self.last_need_login:
            return _COOKIE_EXPIRED_HINT if self._cookie else _NEED_LOGIN_HINT
        return _RATE_LIMIT_HINT

    def search_person(self, name: str, count: int = 10) -> List[Dict[str, Any]]:
        """按名称搜索豆瓣人物，返回 ``[{id, name, avatar, url}]``。"""
        self.search_calls += 1
        payload = self._get("/search/subjects", type="person", q=name, start=0, count=count)
        results: List[Dict[str, Any]] = []
        seen: set = set()
        for item in (payload or {}).get("items") or []:
            if not isinstance(item, dict):
                continue
            target = item.get("target") if isinstance(item.get("target"), dict) else {}
            person_id = str(item.get("target_id") or target.get("id") or "").strip()
            title = _clean_text(target.get("title"))
            if not person_id.isdigit() or not title or person_id in seen:
                continue
            seen.add(person_id)
            cover = target.get("cover_img") if isinstance(target.get("cover_img"), dict) else {}
            results.append(
                {
                    "id": person_id,
                    "name": title,
                    "avatar": str(cover.get("url") or "").replace("/l/public/", "/s/public/") or None,
                    "url": target.get("url"),
                }
            )
        return results

    def person_detail(self, person_id: str) -> Optional[Dict[str, Any]]:
        """获取豆瓣人物详情（含作品集 modules）。"""
        if not person_id:
            return None
        return self._get(f"/elessar/subject/{person_id}")

    def person_works(self, collection_id: str, count: int = 10, sort_by: str = "time") -> List[Dict[str, Any]]:
        """获取人物「影视」作品集（受接口限制只取首页，最多 10 条）。"""
        if not collection_id:
            return []
        order = sort_by if sort_by in self.SORT_ORDERS else "time"
        limit = min(max(1, _to_int(count) or self.MAX_WORKS_PER_REQUEST), self.MAX_WORKS_PER_REQUEST)
        payload = self._get(
            f"/elessar/work_collections/{collection_id}/works",
            sortby=order,
            collection_title="影视",
            start=0,
            count=limit,
        )
        return [item for item in (payload or {}).get("works") or [] if isinstance(item, dict)]


def douban_work_to_candidate(raw: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """把豆瓣作品条目转成统一的候选结构 ``{title, year, alt_title, source, media_id}``。

    豆瓣作品条目的媒体类型在 ``subject.subtype``（``subject.type`` 恒为占位的 ``"subject"``），
    这里只保留电影/电视剧两类，其余（书、音乐、综艺等）跳过。
    """
    if not isinstance(raw, dict):
        return None
    subject = raw.get("subject") if isinstance(raw.get("subject"), dict) else raw
    raw_type = _clean_text(subject.get("subtype") or subject.get("type_name") or subject.get("type"))
    if raw_type.lower() in ("subject", ""):
        raw_type = _clean_text(raw.get("subtype") or raw.get("type_name"))
    if raw_type and raw_type not in ("电影", "电视剧", "movie", "tv", "series"):
        return None

    title = _clean_text(subject.get("title") or raw.get("title"))
    if not title:
        return None
    year = _clean_text(subject.get("year") or raw.get("year"))
    if not year:
        # 豆瓣部分条目把年份写在 card_subtitle 里，如 "2024 / 中国大陆 / 剧情"
        year = extract_year(subject.get("card_subtitle") or raw.get("card_subtitle") or "")
    if not year:
        # 当前版本把年份放在 extra.year（并冗余在 extra.short_info 里）
        extra = subject.get("extra") if isinstance(subject.get("extra"), dict) else {}
        year = _clean_text(extra.get("year")) or extract_year(extra.get("short_info") or "")
    media_id = str(subject.get("id") or raw.get("id") or "").strip()
    return {
        "title": title,
        "year": year,
        "alt_title": "",
        "source": "douban",
        "media_id": media_id,
        # subtype 是英文（movie / tv），统一译成宿主那套中文媒体类型，便于前端展示
        "type": {"movie": "电影", "tv": "电视剧", "series": "电视剧"}.get(raw_type.lower(), raw_type),
    }


# ─────────────────────────── TMDB 发现源 ───────────────────────────


class _TmdbClient:
    """TMDB 的轻量客户端，用于「演员 → 参演作品」发现。

    只依赖 ``app.sdk.network`` 与宿主设置里的 ``TMDB_API_KEY`` / ``TMDB_API_DOMAIN``：
    后者在本机实例被配置成镜像域名，直接用它比硬编码官方域名更贴合宿主环境。
    任何失败都返回空列表，由调用方与豆瓣结果做并集，不中断主流程。
    """

    TIMEOUT = 15
    # only 取演员参演（cast），排除剧组其他职位
    CREDITS_PATH = "/3/person/{person_id}/combined_credits"

    def __init__(self, proxy: bool = False) -> None:
        self._proxy = proxy
        self._api_key = str(getattr(settings, "TMDB_API_KEY", "") or "").strip()
        self._api_domain = str(getattr(settings, "TMDB_API_DOMAIN", "") or "").strip() or "api.themoviedb.org"
        self.last_error = ""

    @property
    def configured(self) -> bool:
        """有 API Key 才能用。宿主默认带一个公共 Key，因此通常都是可用的。"""
        return bool(self._api_key)

    def _get(self, path: str, **params: Any) -> Optional[Dict[str, Any]]:
        """发起一次 TMDB GET，失败返回 None（不抛异常）。"""
        self.last_error = ""
        if not self.configured:
            self.last_error = "未取到 TMDB_API_KEY，TMDB 发现源不可用"
            return None
        query = dict(params)
        query["api_key"] = self._api_key
        if "language" not in query:
            query["language"] = "zh-CN"
        proxies = getattr(settings, "PROXY", None) if self._proxy else None
        response = None
        try:
            response = RequestUtils(proxies=proxies, timeout=self.TIMEOUT).get_res(
                url=f"https://{self._api_domain}{path}", params=query
            )
            if response is None:
                self.last_error = "TMDB 请求无响应"
                return None
            if response.status_code != 200:
                self.last_error = f"TMDB 返回 HTTP {response.status_code}"
                return None
            payload = response.json()
            return payload if isinstance(payload, dict) else None
        except Exception as err:  # noqa: BLE001 - 任何异常都降级为「取不到」
            self.last_error = f"TMDB 请求异常：{err}"
            return None
        finally:
            if response is not None:
                try:
                    response.close()
                except Exception:  # pragma: no cover
                    pass

    def search_person(self, name: str) -> List[Dict[str, Any]]:
        """按名称搜索 TMDB 人物，返回 ``[{id, name, original_name}]``。"""
        payload = self._get("/3/search/person", query=name)
        results: List[Dict[str, Any]] = []
        for item in (payload or {}).get("results") or []:
            if not isinstance(item, dict):
                continue
            person_id = str(item.get("id") or "").strip()
            if not person_id:
                continue
            results.append(
                {
                    "id": person_id,
                    "name": _clean_text(item.get("name")),
                    "original_name": _clean_text(item.get("original_name")),
                }
            )
        return results

    def person_credits(self, person_id: str) -> List[Dict[str, Any]]:
        """取人物参演作品，返回统一候选结构。

        只用 ``cast``（演员本人参演），不含 ``crew``（编剧/导演等），
        与决策基线 2「候选范围仅演员本人」一致。结果按年份倒序截断到
        ``_TMDB_CREDITS_LIMIT``：追短剧关心的是近期产出，而每条候选都要付出
        「站点数 × 1 次搜索」的成本，不能无节制展开。
        """
        if not person_id:
            return []
        payload = self._get(self.CREDITS_PATH.format(person_id=person_id))
        results: List[Dict[str, Any]] = []
        for item in (payload or {}).get("cast") or []:
            if not isinstance(item, dict):
                continue
            media_type = _clean_text(item.get("media_type"))
            # 只要电影/电视剧；短剧在 TMDB 侧一律被归入 tv
            if media_type not in ("movie", "tv"):
                continue
            title = _clean_text(item.get("name") or item.get("title") or item.get("original_name"))
            if not title:
                continue
            date = _clean_text(item.get("first_air_date") or item.get("release_date"))
            results.append(
                {
                    "title": title,
                    "year": extract_year(date),
                    "alt_title": _clean_text(item.get("original_name") or item.get("original_title")),
                    "source": "tmdb",
                    "media_id": str(item.get("id") or "").strip(),
                    "type": MediaType.TV.value if media_type == "tv" else MediaType.MOVIE.value,
                }
            )
        # 年份缺失的排在最后（空串小于任何年份），因此优先保留近期作品
        results.sort(key=lambda item: item.get("year") or "", reverse=True)
        return results[:_TMDB_CREDITS_LIMIT]


# ─────────────────────────── 站点搜索 ───────────────────────────


class _SiteSearcher:
    """按剧名在配置的站点里搜索资源。

    走宿主公开的 ``TorrentsChain().browse(domain, keyword=…, cat=…)``：``keyword`` 就是
    剧名关键字搜索，``cat`` 可把范围收窄到站点的短剧分类。
    """

    def __init__(self, sites: List[int], prefer_short_drama_category: bool = True) -> None:
        self._sites = [int(item) for item in (sites or []) if str(item).strip()]
        self._prefer_cat = bool(prefer_short_drama_category)
        self._category_cache: Dict[str, str] = {}

    def _indexer(self, domain: str) -> Optional[Dict[str, Any]]:
        """取站点索引配置（含分类表）。"""
        if not HAS_FRAMEWORK:
            return None
        try:
            return SitesHelper().get_indexer(domain)
        except Exception as err:  # noqa: BLE001 - 站点配置缺失按无分类处理
            logger.warning(f"{PLUGIN_NAME} 读取站点配置失败（{domain}）：{err}")
            return None

    def _short_drama_cat(self, domain: str) -> str:
        """带缓存的短剧分类探测：同一轮任务内每个站点只查一次。"""
        if not self._prefer_cat:
            return ""
        if domain in self._category_cache:
            return self._category_cache[domain]
        cat = detect_short_drama_category(self._indexer(domain))
        self._category_cache[domain] = cat
        return cat

    def _domains(self) -> List[str]:
        """把配置里的站点 ID 解析成域名列表。

        用 ``get_indexers()`` 一次取回全部站点再按 ID 过滤 —— 单站点查询接口的名字在
        宿主版本间并不稳定，一次取回再本地过滤更安全。
        """
        if not HAS_FRAMEWORK:
            return []
        try:
            indexers = SitesHelper().get_indexers() or []
        except Exception as err:  # noqa: BLE001
            logger.warning(f"{PLUGIN_NAME} 读取站点列表失败：{err}")
            return []
        by_id: Dict[int, Dict[str, Any]] = {}
        for item in indexers:
            try:
                by_id[int(item.get("id"))] = item
            except (TypeError, ValueError):
                continue
        domains: List[str] = []
        for site_id in self._sites:
            site = by_id.get(site_id)
            domain = str((site or {}).get("domain") or "").strip()
            if domain:
                domains.append(domain)
            else:
                logger.warning(f"{PLUGIN_NAME} 站点 ID={site_id} 未解析出域名，已跳过")
        return domains

    @staticmethod
    def _to_dict(torrent: Any) -> Dict[str, Any]:
        """把宿主 ``TorrentInfo`` 转成普通字典（只保留决策需要的字段）。"""
        keys = (
            "title",
            "description",
            "enclosure",
            "page_url",
            "size",
            "seeders",
            "peers",
            "grabs",
            "pubdate",
            "site",
            "site_name",
            "downloadvolumefactor",
            "uploadvolumefactor",
            "hit_and_run",
            "labels",
        )
        row: Dict[str, Any] = {}
        for key in keys:
            row[key] = getattr(torrent, key, None)
        return row

    def search(self, keyword: str) -> List[Dict[str, Any]]:
        """在全部配置站点上按剧名搜索，返回合并后的结果列表。

        单个站点失败只记日志并继续，不影响其它站点。
        """
        results: List[Dict[str, Any]] = []
        if not HAS_FRAMEWORK:
            logger.warning(f"{PLUGIN_NAME} 框架模块不可用，无法执行站点搜索")
            return results
        if not keyword:
            return results

        for domain in self._domains():
            cat = self._short_drama_cat(domain)
            try:
                torrents = TorrentsChain().browse(domain=domain, keyword=keyword, cat=cat or None)
            except Exception as err:  # noqa: BLE001 - 站点异常不阻断本轮其它站点
                logger.warning(f"{PLUGIN_NAME} 站点 {domain} 搜索失败：{err}")
                continue
            if not torrents:
                continue
            logger.info(
                f"{PLUGIN_NAME} 站点 {domain} 关键词「{keyword}」"
                f"{'（分类 ' + cat + '）' if cat else ''}命中 {len(torrents)} 条"
            )
            for torrent in torrents:
                row = self._to_dict(torrent)
                row["search_keyword"] = keyword
                results.append(row)
        return results


# ─────────────────────────── 整理器（自建） ───────────────────────────


class _Organizer:
    """自建整理入库：把下载完成的短剧搬进媒体库并生成 NFO。

    与「从文件名猜剧名」的通用整理器不同，本插件**自带账本**：账本里已经记录了
    「这个种子是哪部剧、哪一年」，因此整理时不需要识别、也不需要猜 —— 这是本插件
    在整理环节相对通用方案的结构性优势。
    """

    def __init__(self, download_path: str, library_path: str, transfer_type: str = "link") -> None:
        # 保留原始字符串：Path("") 会变成 "."（当前目录）且恒为真，直接用 Path 判空会误判
        self._download_raw = str(download_path or "").strip()
        self._library_raw = str(library_path or "").strip()
        self._download_path = Path(self._download_raw).expanduser() if self._download_raw else None
        self._library_path = Path(self._library_raw).expanduser() if self._library_raw else None
        self._transfer_type = transfer_type if transfer_type in ("link", "copy", "move") else "link"

    @property
    def ready(self) -> bool:
        """下载目录与媒体库目录都配置了才可整理。"""
        return bool(self._download_raw and self._library_raw)

    def find_content(self, entry: Dict[str, Any]) -> Optional[Path]:
        """在下载目录里定位某个账本条目的已完成内容（目录或文件）。

        匹配策略：先按**账本记录的种子名截断段**（拼音剧名）做精确/前缀匹配，再退回按
        中文剧名做包含匹配。两种都比「猜文件名」可靠，因为比对对象来自账本而非推断。
        """
        if not self.ready or not self._download_path or not self._download_path.exists():
            return None

        # 账本里 `torrent_title` 是种子原名（站点上多为拼音），`title` 是中文剧名。
        # 两者都过一遍「截断出剧名段」再归一化：前者是最可靠的定位键（下载目录名通常就是
        # 种子名的截断版），把 `title` 一并纳入是为了兜住 `torrent_title` 缺失的情形 ——
        # 只按中文剧名找是不够的，AGSVPT 这类站点的落地目录名本身就只有拼音。
        heads: List[str] = []
        for raw in (entry.get("torrent_title"), entry.get("title")):
            head = normalize_title(torrent_title_head(_clean_text(raw)))
            if len(head) >= _MIN_TITLE_FOR_LOOSE_MATCH and head not in heads:
                heads.append(head)

        title = normalize_title(_clean_text(entry.get("title")))
        try:
            children = list(self._download_path.iterdir())
        except OSError as err:
            logger.warning(f"{PLUGIN_NAME} 读取下载目录失败：{err}")
            return None

        # 优先按种子名截断段做精确/前缀/包含匹配
        for head in heads:
            for child in children:
                name = normalize_title(child.stem if child.is_file() else child.name)
                if name and (name == head or name.startswith(head) or head in name):
                    return child
        # 退回中文剧名包含匹配（剧名过短达不到宽松匹配门槛时仍能救回来）
        if title:
            for child in children:
                name = normalize_title(child.stem if child.is_file() else child.name)
                if title in name:
                    return child
        return None

    @staticmethod
    def target_dir_name(entry: Dict[str, Any]) -> str:
        """媒体库里的目标目录名：``剧名 (年份)``（无年份时只用剧名）。"""
        title = _ILLEGAL_NAME_CHARS.sub("", _clean_text(entry.get("title") or "")) or "未命名短剧"
        year = _clean_text(entry.get("year") or "")
        return f"{title} ({year})" if year else title

    def _move_tree(self, source: Path, target: Path) -> None:
        """按配置的搬运方式把内容放到目标路径。

        链接模式**先复制、再尽力替换为硬链接**：同设备时省空间，跨设备或文件系统不支持
        硬链接时保留副本，且不视为失败（否则一个文件系统差异就会让整轮整理全挂）。
        """
        if self._transfer_type == "move":
            shutil.move(str(source), str(target))
            return

        if source.is_dir():
            shutil.copytree(str(source), str(target), dirs_exist_ok=True, copy_function=shutil.copy2)
            if self._transfer_type == "link":
                for item in target.iterdir():
                    if not item.is_file():
                        continue
                    origin = source / item.name
                    self._replace_with_link(item, origin)
            return

        shutil.copy2(str(source), str(target))
        if self._transfer_type == "link":
            self._replace_with_link(target, source)

    @staticmethod
    def _replace_with_link(link_path: Path, origin: Path) -> None:
        """把已复制的文件替换成指向 ``origin`` 的硬链接；失败则回退为副本。"""
        try:
            link_path.unlink()
            link_path.hardlink_to(origin)
        except OSError as err:
            logger.warning(f"{PLUGIN_NAME} 建立硬链接失败，保留文件副本（{link_path.name}）：{err}")
            if not link_path.exists() and origin.exists():
                try:
                    shutil.copy2(origin, link_path)
                except (OSError, shutil.Error) as copy_err:  # pragma: no cover
                    logger.error(f"{PLUGIN_NAME} 回退复制失败：{copy_err}")

    def organize(self, entry: Dict[str, Any]) -> Tuple[bool, str]:
        """整理一个账本条目，返回 ``(是否成功, 说明)``。"""
        if not self.ready:
            return False, "未配置下载目录或媒体库目录"
        if not self._library_path:
            return False, "未配置媒体库目录"
        source = self.find_content(entry)
        if source is None:
            return False, "下载目录里暂未找到对应内容（可能仍在下载）"

        target_root = self._library_path / "短剧"
        target = target_root / self.target_dir_name(entry)
        if target.exists() and self._transfer_type != "move":
            return True, "目标目录已存在，跳过"

        try:
            target_root.mkdir(parents=True, exist_ok=True)
            target.parent.mkdir(parents=True, exist_ok=True)
            self._move_tree(source, target)
            self._write_nfo(target if target.is_dir() else target.parent, entry)
        except (OSError, shutil.Error) as err:
            logger.error(f"{PLUGIN_NAME} 整理失败（{entry.get('title')}）：{err}")
            return False, f"整理失败：{err}"
        return True, str(target)

    @staticmethod
    def _write_nfo(series_dir: Path, entry: Dict[str, Any]) -> None:
        """在剧集目录里生成最小可用 NFO。

        只写**账本里确知**的字段（剧名、年份、来源身份），不做任何猜测性刮削。
        """
        try:
            series_dir.mkdir(parents=True, exist_ok=True)
            title = str(entry.get("title") or "")
            year = str(entry.get("year") or "")
            source = str(entry.get("media_source") or "")
            media_id = str(entry.get("media_id") or "")
            lines = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>', "<tvshow>"]
            lines.append(f"  <title>{title}</title>")
            lines.append(f"  <originaltitle>{title}</originaltitle>")
            if year:
                lines.append(f"  <year>{year}</year>")
                lines.append(f"  <premiered>{year}-01-01</premiered>")
            if source and media_id:
                lines.append(f'  <uniqueid type="{source}" default="true">{media_id}</uniqueid>')
            lines.append(f"  <genre>短剧</genre>")
            lines.append(f"  <studio>{PLUGIN_NAME}</studio>")
            lines.append("</tvshow>")
            (series_dir / "tvshow.nfo").write_text("\n".join(lines), encoding="utf-8")
        except OSError as err:  # pragma: no cover - 写 NFO 失败不应让整理失败
            logger.warning(f"{PLUGIN_NAME} 写入 NFO 失败：{err}")


# ─────────────────────────── 插件主类 ───────────────────────────


class ShortDramaActorSubscribe(_PluginBase):
    """按演员自动订阅短剧：剧名直搜站点，绕开宿主识别器。"""

    # ── 插件元数据（需与 package.v3.json 保持一致） ──
    # 注意：plugin_name / plugin_icon 必须是**字符串字面量**，不能引用模块常量。
    # 宿主的部分离线安装工具会用 AST 静态解析插件类，只认 ast.Constant，
    # 引用变量会被判定为「缺少 plugin_name」；一致性由 scripts/verify_plugin.py 校验。
    plugin_name = "短剧演员订阅"
    plugin_desc = (
        "跟着喜欢的演员追短剧：合并 TMDB 与豆瓣的演员作品列表，用剧名直接在站点搜索并按"
        "「做种数→体积→分辨率」择优下载，自带账本去重与整理入库；全程不依赖宿主识别器，"
        "因此长尾短剧也能追。"
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

    # ── 运行时状态 ──
    _enabled = False
    _onlyonce = False
    _actors: List[str] = []
    _sites: List[int] = []
    _prefer_short_drama_category = True
    _downloader = ""
    _download_path = ""
    _library_path = ""
    _transfer_type = "link"
    _interval_hours = 6
    _organize_enabled = True
    _organize_interval_minutes = 30
    _notify = True
    _douban_cookie = ""
    _proxy = False
    _max_works = 10
    _sidebar_nav = True
    # 同一进程内的重入保护：定时任务与手动触发可能撞在一起
    _lock = threading.Lock()

    def __init__(self) -> None:
        super().__init__()
        self._running = False
        self._last_result: Dict[str, Any] = {}
        # CookieCloud 取数的进程内缓存（见 _resolve_douban_cookie）
        self._cookie_cache = ""
        self._cookie_cache_at = 0.0

    # ── 生命周期 ──

    def init_plugin(self, config: Optional[Dict[str, Any]] = None) -> None:
        """读取配置并建立运行时状态；必须允许重复调用。"""
        config = config or {}
        self._enabled = bool(config.get("enabled"))
        self._onlyonce = bool(config.get("onlyonce"))
        self._actors = self._parse_actors(config.get("actors"))
        self._sites = [int(item) for item in (config.get("sites") or []) if str(item).strip()]
        self._prefer_short_drama_category = bool(config.get("prefer_short_drama_category", True))
        self._downloader = str(config.get("downloader") or "").strip()
        self._download_path = str(config.get("download_path") or "").strip()
        self._library_path = str(config.get("library_path") or "").strip()
        self._transfer_type = str(config.get("transfer_type") or "link").strip()
        self._interval_hours = max(1, _to_int(config.get("interval_hours")) or 6)
        self._organize_enabled = bool(config.get("organize_enabled", True))
        self._organize_interval_minutes = max(5, _to_int(config.get("organize_interval_minutes")) or 30)
        self._notify = bool(config.get("notify", True))
        self._douban_cookie = str(config.get("douban_cookie") or "").strip()
        self._proxy = bool(config.get("proxy"))
        self._max_works = min(10, max(1, _to_int(config.get("max_works")) or 10))
        self._sidebar_nav = bool(config.get("sidebar_nav", True))

        # 配置变更后让 CookieCloud 缓存立刻失效，避免刚填好的 Cookie 不生效
        self._cookie_cache = ""
        self._cookie_cache_at = 0.0

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
        """释放插件创建的后台资源（本插件不自建调度器/线程池，只清运行时标记）。"""
        self._running = False

    # ── 配置解析 ──

    @staticmethod
    def _parse_actors(value: Any) -> List[str]:
        """解析演员配置：支持逗号/换行/分号分隔，去重且保序。"""
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

    def _live_config(self) -> Dict[str, Any]:
        """组装当前运行时配置，用于回写（与 ``_default_config`` 的键保持一致）。

        必须读**实例属性**（``self._xxx``）而不是类属性：插件虚拟分身会在同一份源码上
        创建多个运行实例，类属性是共享的、也是过期的，只有实例属性才是本实例的真实配置。
        """
        return {
            "enabled": self._enabled,
            "onlyonce": self._onlyonce,
            "actors": ",".join(self._actors),
            "sites": list(self._sites),
            "prefer_short_drama_category": self._prefer_short_drama_category,
            "downloader": self._downloader,
            "download_path": self._download_path,
            "library_path": self._library_path,
            "transfer_type": self._transfer_type,
            "interval_hours": self._interval_hours,
            "organize_enabled": self._organize_enabled,
            "organize_interval_minutes": self._organize_interval_minutes,
            "notify": self._notify,
            "douban_cookie": self._douban_cookie,
            "proxy": self._proxy,
            "max_works": self._max_works,
            "sidebar_nav": self._sidebar_nav,
        }

    @staticmethod
    def _default_config() -> Dict[str, Any]:
        """返回配置页默认值。"""
        return {
            "enabled": False,
            "onlyonce": False,
            "actors": "",
            "sites": [],
            "prefer_short_drama_category": True,
            "downloader": "",
            "download_path": "",
            "library_path": "",
            "transfer_type": "link",
            "interval_hours": 6,
            "organize_enabled": True,
            "organize_interval_minutes": 30,
            "notify": True,
            "douban_cookie": "",
            "proxy": False,
            "max_works": 10,
            "sidebar_nav": True,
        }

    # ── 页面与渲染模式 ──

    @staticmethod
    def get_render_mode() -> Tuple[str, str]:
        """声明使用 Vue 联邦远程组件渲染，产物目录为 dist/assets。

        Vue 模式下配置页 / 详情页 / 仪表板都由远程组件（Config / Page / Dashboard）绘制，
        后端只负责给数据：``get_form`` 下发默认配置模型，``get_page`` 与仪表板的
        页面 JSON 都返回空列表。
        """
        return "vue", "dist/assets"

    def get_form(self) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Vue 模式下配置页由远程 Config 组件渲染，后端只返回默认配置模型。"""
        return [], self._default_config()

    def get_page(self) -> List[Dict[str, Any]]:
        """Vue 模式下详情页由远程 Page 组件渲染，后端返回空列表。"""
        return []

    def get_sidebar_nav(self) -> List[Dict[str, Any]]:
        """声明主界面侧栏全页入口；只有 Vue 渲染模式的插件会被宿主聚合。

        与宿主订阅体系同形：宿主侧栏「订阅」分组里是 电影订阅 / 电视剧订阅 /
        音乐订阅 / 订阅日历 / 订阅分享（见宿主功能表 ``TG``，各自 ``permission=subscribe``），
        本插件以同样的形态追加一个「短剧」入口 —— ``section=subscribe`` +
        ``permission=subscribe`` + 同族图标，因此会和它们并列落在「订阅」组里。

        ⚠️ 宿主侧栏合并逻辑（``mp_default`` 里的 ``Ce()``）把插件项**追加到分组末尾**
        （``V.value.push(navMenu)``），``order`` 只在多个插件项之间排序，无法插到宿主条目中间。

        ``section`` 仅接受 start / discovery / subscribe / organize / system
        （未知取值会被归入「系统」组）；``permission`` 仅接受
        subscribe / discovery / search / manage / admin。是否露出由配置项
        ``sidebar_nav`` 控制。
        """
        if not self.get_state() or not self._sidebar_nav:
            return []
        return [
            {
                "nav_key": "main",
                "title": "短剧",
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
        """声明仪表板内容，返回 ``(列配置, 全局配置, 页面 JSON)`` 三元组。

        Vue 联邦插件通过前端 Dashboard 组件呈现内容，因此页面 JSON 为空。
        """
        if not self.get_state():
            return None
        if key and key != "overview":
            return None
        ledger = self._load_ledger()
        misses = self._load_misses()
        return (
            {"cols": 12, "sm": 6, "md": 4},
            {
                "title": f"{self.plugin_name} · 追剧概览",
                "subtitle": (
                    f"{len(self._load_actors())} 位演员｜已下载 {len(ledger)} 部"
                    f"｜冷却中 {len(misses)} 部"
                ),
                "refresh": 300,
                "border": True,
            },
            [],
        )

    # ── 后台能力 ──

    def get_service(self) -> List[Dict[str, Any]]:
        """注册两个定时服务：订阅轮询与整理扫描。

        ⚠️ 传给被调函数的参数必须写在 ``func_kwargs`` 里。宿主注册时会把
        ``service["kwargs"]`` **原样展开给** ``scheduler.add_job()``，而 ``trigger``
        正是 ``add_job`` 自己的形参名 —— 写成 ``kwargs`` 会让它抛
        ``got multiple values for argument 'trigger'`` 并**静默拒绝注册**。
        这里传 ``func_kwargs={"trigger": ...}`` 仅为区分统计口径（定时 vs 手动）。
        """
        if not self.get_state():
            return []
        services: List[Dict[str, Any]] = []
        if self._actors and self._sites:
            services.append(
                {
                    "id": f"{self.__class__.__name__}.Refresh",
                    "name": f"{self.plugin_name}·订阅轮询",
                    "trigger": IntervalTrigger(hours=self._interval_hours),
                    "func": self.execute_task,
                    "func_kwargs": {"trigger": "interval"},
                }
            )
        if self._organize_enabled and self._download_path and self._library_path:
            services.append(
                {
                    "id": f"{self.__class__.__name__}.Organize",
                    "name": f"{self.plugin_name}·整理入库",
                    "trigger": IntervalTrigger(minutes=self._organize_interval_minutes),
                    "func": self.organize_once,
                    "func_kwargs": {"trigger": "interval"},
                }
            )
        return services

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        """注册远程命令，实际动作通过 EventType.PluginAction 事件路由。"""
        return [
            {
                "cmd": "/shortdrama",
                "event": EventType.PluginAction,
                "desc": "刷新短剧演员订阅",
                "category": "插件命令",
                "data": {"action": "shortdramaactorsubscribe_refresh"},
            }
        ]

    @eventmanager.register(EventType.PluginAction)
    def on_plugin_action(self, event: Event) -> None:
        """响应远程命令；仅处理属于本插件的 action。"""
        event_data = event.event_data or {}
        if event_data.get("action") != "shortdramaactorsubscribe_refresh":
            return
        self.execute_task()

    def get_api(self) -> List[Dict[str, Any]]:
        """声明插件 HTTP 接口，最终挂载在 ``/api/v1/plugin/<PluginID>/<path>``。

        联邦前端的三个组件（Config / Page / Dashboard）走同一套接口，统一用 ``bear``
        鉴权：侧栏全页、配置弹窗、仪表板三处都能直接调用。
        """
        return [
            {
                "path": "/config",
                "endpoint": self.api_get_config,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "获取插件配置与下拉候选",
            },
            {
                "path": "/config",
                "endpoint": self.api_update_config,
                "methods": ["PUT"],
                "auth": "bear",
                "summary": "更新插件配置",
            },
            {
                "path": "/options",
                "endpoint": self.api_options,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "获取站点 / 下载器 / 整理方式候选",
            },
            {
                "path": "/status",
                "endpoint": self.api_status,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "获取运行概览、账本与冷却列表",
            },
            {
                "path": "/run",
                "endpoint": self.api_run,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "立即执行一次订阅轮询",
            },
            {
                "path": "/organize",
                "endpoint": self.api_organize,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "立即整理一次",
            },
            {
                "path": "/unmatch",
                "endpoint": self.api_unmatch,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "从账本移除一条记录（允许重新下载）",
            },
            {
                "path": "/miss/clear",
                "endpoint": self.api_clear_miss,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "清空未命中冷却",
            },
            {
                "path": "/search_actor",
                "endpoint": self.api_search_actor,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "按名称搜索 TMDB / 豆瓣演员",
            },
            {
                "path": "/clear",
                "endpoint": self.api_clear,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "清空账本",
            },
            {
                "path": "/works",
                "endpoint": self.api_works,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "演员作品墙（发现层快照 + 每条状态）",
            },
            {
                "path": "/works/subscribe",
                "endpoint": self.api_subscribe,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "按作品立即搜索并下载一条",
            },
            {
                "path": "/works/refresh",
                "endpoint": self.api_refresh_works,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "只刷新演员作品快照（不下载）",
            },
        ]

    # ── API 实现 ──
    def api_get_config(self) -> Dict[str, Any]:
        """返回当前配置与下拉候选，供联邦 Config 组件回显。"""
        config = self._live_config()
        config["douban_cookie_source"] = self._douban_cookie_source()
        return {
            "success": True,
            "message": "",
            "data": {"config": config, "options": self._options_payload()},
        }

    def api_update_config(self, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """接收前端提交的配置，持久化后重新初始化插件。

        与宿主配置页的保存**语义等价**：Vue 模式下配置页由远程组件渲染，组件只负责
        抛出 ``save`` 事件，落盘仍由这里的接口（或宿主的 ``PUT /plugin/<id>``）完成，
        否则侧栏全页里改的配置不会生效。
        """
        if not isinstance(payload, dict):
            return {"success": False, "message": "请求体不是合法对象", "data": None}

        live = self._live_config()
        merged: Dict[str, Any] = {}
        for key, default in self._default_config().items():
            merged[key] = payload.get(key, live.get(key, default))

        merged["enabled"] = bool(merged.get("enabled"))
        merged["onlyonce"] = bool(merged.get("onlyonce"))
        merged["notify"] = bool(merged.get("notify"))
        merged["proxy"] = bool(merged.get("proxy"))
        merged["sidebar_nav"] = bool(merged.get("sidebar_nav", True))
        merged["prefer_short_drama_category"] = bool(merged.get("prefer_short_drama_category", True))
        merged["organize_enabled"] = bool(merged.get("organize_enabled", True))
        merged["actors"] = str(merged.get("actors") or "").strip()
        merged["sites"] = [
            _to_int(item) for item in (merged.get("sites") or []) if str(item).strip().lstrip("-").isdigit()
        ]
        merged["downloader"] = str(merged.get("downloader") or "").strip()
        merged["download_path"] = str(merged.get("download_path") or "").strip()
        merged["library_path"] = str(merged.get("library_path") or "").strip()
        merged["transfer_type"] = str(merged.get("transfer_type") or "link").strip() or "link"
        merged["interval_hours"] = max(1, _to_int(merged.get("interval_hours")) or 6)
        merged["organize_interval_minutes"] = max(5, _to_int(merged.get("organize_interval_minutes")) or 30)
        merged["max_works"] = min(10, max(1, _to_int(merged.get("max_works")) or 10))
        merged["douban_cookie"] = str(merged.get("douban_cookie") or "").strip()

        self.update_config(merged)
        self.init_plugin(merged)
        logger.info(f"{PLUGIN_NAME} 配置已通过前端接口更新")
        return {"success": True, "message": "配置已保存", "data": self._live_config()}

    def api_options(self) -> Dict[str, Any]:
        """返回站点 / 下载器 / 整理方式的候选列表（供下拉框使用）。"""
        return {"success": True, "message": "", "data": self._options_payload()}

    def api_organize(self) -> Dict[str, Any]:
        """立即整理一次（整理条目通常很少，允许同步执行）。"""
        if not self.get_state():
            return {"success": False, "message": "插件未启用", "data": None}
        ok = self.organize_once(trigger="api")
        return {
            "success": ok,
            "message": "已执行整理扫描" if ok else "整理未执行（需启用整理、配置目录且账本非空）",
            "data": None,
        }

    def api_clear_miss(self) -> Dict[str, Any]:
        """清空未命中冷却表，让所有「搜过但没搜到」的剧立刻可重搜。"""
        self.save_data(_DATA_MISS, {})
        return {"success": True, "message": "未命中冷却已清空", "data": None}

    def api_search_actor(self, name: str = "") -> Dict[str, Any]:
        """按名称搜索演员，返回 TMDB 与豆瓣的候选（供配置页直接取 ID）。

        两个来源分别容错：任一来源失败只影响它自己的候选，另一个照常返回。
        """
        keyword = _clean_text(name)
        if not keyword:
            return {"success": False, "message": "缺少 name 参数", "data": []}
        if not HAS_FRAMEWORK:
            return {"success": False, "message": "框架模块不可用", "data": []}

        items: List[Dict[str, Any]] = []
        errors: List[str] = []

        tmdb = _TmdbClient(proxy=self._proxy)
        if tmdb.configured:
            try:
                for person in tmdb.search_person(keyword)[:8]:
                    person_id = str(person.get("id") or "").strip()
                    if not person_id:
                        continue
                    items.append(
                        {
                            "source": "tmdb",
                            "id": person_id,
                            "name": person.get("name") or person.get("original_name") or keyword,
                            "original_name": person.get("original_name") or "",
                            "avatar": "",
                        }
                    )
            except Exception as err:  # noqa: BLE001 - 搜索失败降级为无候选
                errors.append(f"TMDB：{err}")
        else:
            errors.append(tmdb.last_error or "TMDB 未配置")

        douban = _DoubanClient(proxy=self._proxy, cookie=self._resolve_douban_cookie())
        try:
            for person in douban.search_person(keyword, count=8):
                person_id = str(person.get("id") or "").strip()
                if not person_id:
                    continue
                items.append(
                    {
                        "source": "douban",
                        "id": person_id,
                        "name": person.get("name") or keyword,
                        "original_name": "",
                        "avatar": str(person.get("avatar") or ""),
                    }
                )
        except Exception as err:  # noqa: BLE001
            errors.append(f"豆瓣：{err}")
        if douban.last_error and not any(item["source"] == "douban" for item in items):
            errors.append(f"豆瓣：{douban.failure_hint()}")

        return {
            "success": True,
            "message": "" if items else ("；".join(errors) or "未找到匹配的演员"),
            "data": items,
        }


    def api_status(self) -> Dict[str, Any]:
        """返回运行概览、账本与冷却列表（联邦前端与仪表板共用）。"""
        ledger = self._load_ledger()
        misses = self._load_misses()
        stats = self._load_stats()
        return {
            "success": True,
            "message": "",
            "data": {
                "enabled": self._enabled,
                "running": self._running,
                "sidebar_nav": self._sidebar_nav,
                "actors": self._load_actors(),
                "stats": stats,
                "ledger": self._ledger_rows(ledger),
                "cooldown": self._cooldown_rows(misses),
                "summary": {
                    "actor_count": len(self._load_actors()),
                    "candidate_count": _to_int(stats.get("candidates")),
                    "downloaded_count": len(ledger),
                    "organized_count": sum(
                        1
                        for item in ledger.values()
                        if isinstance(item, dict) and item.get("organized")
                    ),
                    "cooldown_count": len(misses),
                    "last_run": str(stats.get("last_run") or ""),
                    "elapsed": _to_float(stats.get("elapsed")),
                },
                "last_result": self._last_result,
            },
        }

    def api_run(self) -> Dict[str, Any]:
        """立即触发一次订阅轮询。"""
        if not self.get_state():
            return {"success": False, "message": "插件未启用", "data": None}
        self._add_once_job(delay_seconds=1, trigger="api")
        return {"success": True, "message": "已提交执行", "data": None}

    def api_unmatch(self, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """从账本移除一条记录，使其下次轮询可以重新下载。"""
        payload = payload or {}
        key = str(payload.get("key") or "").strip()
        if not key:
            return {"success": False, "message": "缺少 key", "data": None}
        ledger = self._load_ledger()
        if key not in ledger:
            return {"success": False, "message": "账本中不存在该记录", "data": None}
        ledger.pop(key)
        self.save_data(_DATA_LEDGER, ledger)
        # 同时清掉冷却，让这条记录在下一轮立刻被重新搜索
        misses = self._load_misses()
        if misses.pop(key, None) is not None:
            self.save_data(_DATA_MISS, misses)
        return {"success": True, "message": "已移除", "data": None}

    def api_clear(self) -> Dict[str, Any]:
        """清空账本。"""
        self.save_data(_DATA_LEDGER, {})
        self.save_data(_DATA_MISS, {})
        return {"success": True, "message": "账本已清空", "data": None}

    # ── 作品墙（「短剧页」的主体） ──

    def _work_rows(self) -> List[Dict[str, Any]]:
        """把演员快照里的作品摊平成作品墙行，并标出每条当前的状态。

        状态口径与主流程**完全一致**（同一份账本 + 同一份冷却表），因此页面显示
        的状态不会与实际行为错位：

        * ``organized``  —— 账本命中且已整理入库
        * ``downloaded`` —— 账本命中（已提交下载）
        * ``cooling``    —— 搜过但站点暂无资源，冷却中
        * ``pending``    —— 还没处理过（下一轮会自动下载，也可手动「订阅」）
        """
        ledger = self._load_ledger()
        misses = self._load_misses()
        now = time.time()
        lifetime = _MISS_COOLDOWN_HOURS * 3600
        rows: List[Dict[str, Any]] = []
        for record in self._load_actors().values():
            if not isinstance(record, dict):
                continue
            actor = _clean_text(record.get("name")) or _clean_text(record.get("key"))
            for work in record.get("works") or []:
                if not isinstance(work, dict):
                    continue
                title = _clean_text(work.get("title"))
                if not title:
                    continue
                year = _clean_text(work.get("year"))
                key = ledger_key(title, year)
                row: Dict[str, Any] = {
                    "key": key,
                    "title": title,
                    "year": year,
                    "alt_title": _clean_text(work.get("alt_title")),
                    "type": _clean_text(work.get("type")),
                    "source": _clean_text(work.get("source")),
                    "media_id": _clean_text(work.get("media_id")),
                    "actor": actor,
                    "state": "pending",
                    "remaining_minutes": 0,
                    "site_name": "",
                    "torrent_title": "",
                    "time": "",
                }
                entry = ledger.get(key)
                if isinstance(entry, dict):
                    row["state"] = "organized" if entry.get("organized") else "downloaded"
                    row["site_name"] = _clean_text(entry.get("site_name"))
                    row["torrent_title"] = _clean_text(entry.get("torrent_title"))
                    row["time"] = _clean_text(entry.get("time"))
                else:
                    last = _to_float(misses.get(key))
                    if last:
                        remaining = int(lifetime - (now - last))
                        if remaining > 0:
                            row["state"] = "cooling"
                            row["remaining_minutes"] = max(1, remaining // 60)
                rows.append(row)

        order = {"pending": 0, "cooling": 1, "downloaded": 2, "organized": 3}
        rows.sort(
            key=lambda item: (
                order.get(str(item.get("state")), 9),
                str(item.get("actor") or ""),
                -_to_int(item.get("year")),
                str(item.get("title") or ""),
            )
        )
        return rows

    def api_works(self) -> Dict[str, Any]:
        """演员作品墙：发现层快照里的全部作品 + 每条的当前状态。

        「短剧页」的主体数据。状态由账本与冷却表推导（与主流程同源），前端只负责
        渲染与筛选；`pending` 的条目可以逐条「订阅」（见 ``api_subscribe``）。
        """
        rows = self._work_rows()
        actors = self._load_actors()
        refreshed = ""
        for record in actors.values():
            if not isinstance(record, dict):
                continue
            stamp = _clean_text(record.get("time"))
            if stamp > refreshed:
                refreshed = stamp
        return {
            "success": True,
            "message": "",
            "data": {
                "items": rows,
                "summary": {
                    "total": len(rows),
                    "pending": sum(1 for item in rows if item["state"] == "pending"),
                    "cooling": sum(1 for item in rows if item["state"] == "cooling"),
                    "downloaded": sum(
                        1 for item in rows if item["state"] in ("downloaded", "organized")
                    ),
                },
                "refreshed_at": refreshed,
                "running": self._running,
                "configured": bool(self._actors and self._sites),
                "actors": list(self._actors),
                "actor_count": len(actors),
            },
        }

    def _find_work(self, key: str) -> Optional[Dict[str, Any]]:
        """按账本键在演员快照里反查一部作品（作品墙按钮只回传 key）。"""
        if not key:
            return None
        for record in self._load_actors().values():
            if not isinstance(record, dict):
                continue
            actor = _clean_text(record.get("name")) or _clean_text(record.get("key"))
            for work in record.get("works") or []:
                if not isinstance(work, dict):
                    continue
                title = _clean_text(work.get("title"))
                if not title:
                    continue
                if ledger_key(title, work.get("year")) == key:
                    found = dict(work)
                    found["actor"] = actor
                    return found
        return None

    def api_subscribe(self, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """按作品立即搜索并下载（作品墙上每条的「订阅」按钮）。

        与定时轮询走**同一条**「搜索 → 匹配 → 择优 → 下载」链路，因此手动订阅的
        条目同样会写账本、清冷却，下一轮不会被重复下载。同步执行（单条通常几秒）；
        若后台正有一轮任务在跑则直接拒绝，避免同一部剧被提交两次。
        """
        payload = payload or {}
        if not self.get_state():
            return {"success": False, "message": "插件未启用", "data": None}
        if not self._sites:
            return {"success": False, "message": "未配置搜索站点", "data": None}
        if not self._download_path or not self._downloader:
            return {"success": False, "message": "未配置下载目录或下载器", "data": None}

        key = str(payload.get("key") or "").strip()
        work = self._find_work(key) if key else None
        if work is None:
            title_raw = _clean_text(payload.get("title"))
            if not title_raw:
                return {"success": False, "message": "缺少作品信息（key 或 title）", "data": None}
            work = {
                "title": title_raw,
                "year": _clean_text(payload.get("year")),
                "alt_title": _clean_text(payload.get("alt_title")),
                "media_source": _clean_text(payload.get("media_source")),
                "media_id": _clean_text(payload.get("media_id")),
                "actor": _clean_text(payload.get("actor")),
            }

        title = _clean_text(work.get("title"))
        entry_key = ledger_key(title, work.get("year"))
        ledger = self._load_ledger()
        if entry_key in ledger:
            return {
                "success": False,
                "message": f"「{title}」已在账本里（已下载）；如需重下，请先在下方列表移除该条",
                "data": None,
            }

        if not self._lock.acquire(blocking=False):
            return {"success": False, "message": "后台正在执行任务，请稍后再试", "data": None}
        try:
            searcher = _SiteSearcher(
                self._sites, prefer_short_drama_category=self._prefer_short_drama_category
            )
            outcome = self._process_candidate(work, searcher)
            if outcome is None:
                misses = self._load_misses()
                misses[entry_key] = time.time()
                self.save_data(_DATA_MISS, misses)
                return {
                    "success": False,
                    "message": f"站点暂无「{title}」的资源（已进入冷却，24 小时后自动重试）",
                    "data": None,
                }
            if not outcome.get("ok"):
                return {
                    "success": False,
                    "message": f"「{title}」下载失败：{outcome.get('reason') or '未知原因'}",
                    "data": None,
                }
            entry = outcome["entry"]
            ledger[entry_key] = entry
            self._save_ledger(ledger)
            misses = self._load_misses()
            if misses.pop(entry_key, None) is not None:
                self.save_data(_DATA_MISS, misses)
            stats = self._load_stats()
            stats["downloaded"] = len(ledger)
            self._save_stats(stats)
            logger.info(f"{PLUGIN_NAME} 手动订阅「{title}」已提交下载")
            return {
                "success": True,
                "message": f"已订阅「{title}」，已提交下载（{entry.get('site_name') or '未知站点'}）",
                "data": entry,
            }
        except Exception as err:  # noqa: BLE001 - 单条失败不影响其它
            logger.error(f"{PLUGIN_NAME} 手动订阅「{title}」失败：{err}")
            return {"success": False, "message": f"订阅失败：{err}", "data": None}
        finally:
            self._lock.release()

    def api_refresh_works(self) -> Dict[str, Any]:
        """只刷新演员作品快照（不下载），供作品墙的「刷新作品」按钮。

        发现层要打 TMDB + 豆瓣，演员多时可能几十秒，因此登记成一次性后台任务；
        前端轮询 ``GET /works`` 的 ``running`` 判断是否结束。
        """
        if not self.get_state():
            return {"success": False, "message": "插件未启用", "data": None}
        if not self._actors:
            return {"success": False, "message": "未配置演员", "data": None}
        if self._running:
            return {"success": False, "message": "已有任务在执行，请稍候", "data": None}
        ok = self._add_once_job(
            delay_seconds=1,
            trigger="api",
            func=self.refresh_works_task,
            job_id=_ONCE_JOB_ID_WORKS,
            job_name=f"{PLUGIN_NAME}刷新作品",
        )
        return {
            "success": ok,
            "message": "已提交刷新作品，稍后自动更新" if ok else "提交失败（当前宿主不支持一次性任务）",
            "data": None,
        }

    def refresh_works_task(self, trigger: str = "manual") -> bool:
        """只跑发现层：刷新演员作品快照并落库，不触发任何下载。

        与 ``execute_task`` 共用同一把锁，避免和整轮任务同时打豆瓣/TMDB。
        """
        if not self.get_state() or not self._actors:
            return False
        if not self._lock.acquire(blocking=False):
            logger.info(f"{PLUGIN_NAME} 后台任务执行中，跳过本次作品刷新（{trigger}）")
            return False
        self._running = True
        try:
            candidates = self._refresh_actors()
            logger.info(f"{PLUGIN_NAME} 作品快照已刷新，共 {len(candidates)} 部候选")
            return True
        except Exception as err:  # noqa: BLE001 - 兜底，避免定时任务挂掉
            logger.error(f"{PLUGIN_NAME} 刷新作品失败：{err}")
            return False
        finally:
            self._running = False
            self._lock.release()

    # ── 前端展示辅助 ──

    @staticmethod
    def _ledger_rows(ledger: Dict[str, Any]) -> List[Dict[str, Any]]:
        """把账本转成前端友好的行列表（带 key、按时间倒序）。"""
        rows: List[Dict[str, Any]] = []
        for key, entry in ledger.items():
            if not isinstance(entry, dict):
                continue
            row = dict(entry)
            row["key"] = key
            rows.append(row)
        rows.sort(key=lambda item: str(item.get("time") or ""), reverse=True)
        return rows

    def _title_index(self) -> Dict[str, Dict[str, str]]:
        """由演员快照建立「账本键 → 剧名/年份/演员」索引。

        冷却表的键是归一化后的剧名（去标点、小写），直接展示不可读，
        因此回显时用它换回原始剧名。
        """
        index: Dict[str, Dict[str, str]] = {}
        for record in self._load_actors().values():
            if not isinstance(record, dict):
                continue
            actor_name = _clean_text(record.get("name")) or _clean_text(record.get("key"))
            for work in record.get("works") or []:
                if not isinstance(work, dict):
                    continue
                title = _clean_text(work.get("title"))
                if not title:
                    continue
                index[ledger_key(title, work.get("year"))] = {
                    "title": title,
                    "year": _clean_text(work.get("year")),
                    "actor": actor_name,
                }
        return index

    def _cooldown_rows(self, misses: Dict[str, Any]) -> List[Dict[str, Any]]:
        """把冷却表转成可读行（仅保留仍在冷却期内的，附剩余分钟数）。"""
        index = self._title_index()
        now = time.time()
        lifetime = _MISS_COOLDOWN_HOURS * 3600
        rows: List[Dict[str, Any]] = []
        for key, stamp in misses.items():
            last = _to_float(stamp)
            if not last:
                continue
            remaining = int(lifetime - (now - last))
            if remaining <= 0:
                continue
            parts = str(key).split("|")
            info = index.get(str(key)) or {}
            rows.append(
                {
                    "key": str(key),
                    "title": info.get("title") or (parts[0] if parts else str(key)),
                    "year": info.get("year") or (parts[1] if len(parts) > 1 else ""),
                    "actor": info.get("actor") or "",
                    "remaining_minutes": max(1, remaining // 60),
                }
            )
        rows.sort(key=lambda item: item["remaining_minutes"])
        return rows

    def _options_payload(self) -> Dict[str, Any]:
        """前端下拉候选：搜索站点 / 下载器 / 系统目录 / 整理方式。

        ``directories`` 直接取自宿主「目录管理」（下载目录与媒体库目录成对），
        这样配置页的下载路径不必让用户再手抄一遍；``defaults`` 给出推荐初值：
        系统默认下载器、以及优先命中的「短剧」目录（没有就叫第一个目录）。
        """
        directories = self._system_directories()
        preferred = next((item for item in directories if item.get("is_short_drama")), None)
        if preferred is None and directories:
            preferred = directories[0]
        preferred = preferred or {}
        return {
            "sites": self._site_items(),
            "downloaders": self._downloader_items(),
            "transfer_types": [
                {"title": "硬链接（推荐，省空间）", "value": "link"},
                {"title": "复制", "value": "copy"},
                {"title": "移动", "value": "move"},
            ],
            "directories": [
                {
                    "title": self._directory_label(item),
                    "value": str(item.get("download_path") or ""),
                    "name": str(item.get("name") or ""),
                    "download_path": str(item.get("download_path") or ""),
                    "library_path": str(item.get("library_path") or ""),
                    "media_type": str(item.get("media_type") or ""),
                    "media_category": str(item.get("media_category") or ""),
                    "is_short_drama": bool(item.get("is_short_drama")),
                }
                for item in directories
            ],
            "defaults": {
                "downloader": self._default_downloader(),
                "directory": str(preferred.get("download_path") or ""),
                "library_path": str(preferred.get("library_path") or ""),
                "directory_name": str(preferred.get("name") or ""),
            },
        }

    def _douban_cookie_source(self) -> str:
        """回显当前豆瓣 Cookie 来源：manual / cookiecloud / none（只读）。"""
        if self._douban_cookie:
            return "manual"
        if not HAS_FRAMEWORK:
            return "none"
        try:
            return "cookiecloud" if self._resolve_douban_cookie() else "none"
        except Exception as err:  # noqa: BLE001 - 回显失败不影响页面渲染
            logger.debug(f"{PLUGIN_NAME} 读取 CookieCloud 登录态失败：{err}")
            return "none"

    # ── 数据存取 ──

    def _load_ledger(self) -> Dict[str, Any]:
        """读取已下账本（键为 ``归一化剧名|年份``）。"""
        data = self.get_data(_DATA_LEDGER)
        return data if isinstance(data, dict) else {}

    def _save_ledger(self, ledger: Dict[str, Any]) -> None:
        """保存账本。"""
        self.save_data(_DATA_LEDGER, ledger)

    def _load_actors(self) -> Dict[str, Any]:
        """读取演员及其作品快照。"""
        data = self.get_data(_DATA_ACTORS)
        return data if isinstance(data, dict) else {}

    def _load_stats(self) -> Dict[str, Any]:
        """读取运行统计。"""
        data = self.get_data(_DATA_STATS)
        return data if isinstance(data, dict) else {}

    def _load_misses(self) -> Dict[str, float]:
        """读取未命中冷却表（键与账本一致，值为上次搜索的 Unix 时间戳）。"""
        data = self.get_data(_DATA_MISS)
        return data if isinstance(data, dict) else {}

    def _save_stats(self, stats: Dict[str, Any]) -> None:
        """保存运行统计。"""
        self.save_data(_DATA_STATS, stats)

    # ── 配置表单候选值 ──

    @staticmethod
    def _site_items() -> List[Dict[str, Any]]:
        """站点下拉项（从宿主站点配置读取）。"""
        if not HAS_FRAMEWORK:
            return []
        try:
            return [
                {"title": str(indexer.get("name") or indexer.get("domain") or ""), "value": indexer.get("id")}
                for indexer in SitesHelper().get_indexers()
                if indexer.get("id")
            ]
        except Exception as err:  # noqa: BLE001 - 读取失败给空列表，页面仍可渲染
            logger.warning(f"{PLUGIN_NAME} 读取站点列表失败：{err}")
            return []

    @staticmethod
    def _downloader_items() -> List[Dict[str, Any]]:
        """下载器下拉项（从宿主下载器配置读取，并标出系统默认的那个）。

        ⚠️ 实测坑：宿主 ``ServiceBaseHelper.get_configs()`` 返回的是 **``{name: conf}``
        字典**（不是列表），且 ``conf`` 是 ``DownloaderConf`` 对象而不是 dict。
        直接 ``for item in get_configs()`` 迭代到的是字符串键，``item.get(...)`` 抛
        ``AttributeError`` 被 except 吞掉 ⇒ 下拉永远是空的（本插件踩过一次）。
        因此这里键与字段两种来源都取，并对对象 / dict 都做兼容。
        """
        if not HAS_FRAMEWORK:
            return []
        try:
            raw = DownloaderHelper().get_configs() or {}
        except Exception as err:  # noqa: BLE001 - 读取失败给空列表，页面仍可渲染
            logger.warning(f"{PLUGIN_NAME} 读取下载器列表失败：{err}")
            return []
        pairs = list(raw.items()) if isinstance(raw, dict) else [(None, item) for item in raw]
        items: List[Dict[str, Any]] = []
        for key, conf in pairs:
            name = str(key or _conf_field(conf, "name") or "").strip()
            if not name:
                continue
            items.append(
                {
                    "title": name,
                    "value": name,
                    "default": bool(_conf_field(conf, "default")),
                }
            )
        return items

    # ── 系统目录与默认下载器（读宿主既有配置，避免重复手填） ──

    @staticmethod
    def _system_directories() -> List[Dict[str, Any]]:
        """读取宿主「目录管理」里维护的目录清单（下载目录 + 媒体库目录成对）。

        宿主前端下载/整理用的就是这一份配置（``GET /download/paths`` 与
        ``GET /storage/directories`` 同源），插件直接复用，用户就不必在插件里
        再手抄一遍路径。取不到时返回空列表，前端退化为「可手填」。
        """
        if not HAS_FRAMEWORK:
            return []
        try:
            from app.application.directory import DirectoryHelper
        except Exception as err:  # noqa: BLE001 - 宿主未暴露该模块时降级
            logger.debug(f"{PLUGIN_NAME} 宿主未暴露 DirectoryHelper：{err}")
            return []
        try:
            items: List[Dict[str, Any]] = []
            for conf in DirectoryHelper().get_dirs():
                name = _clean_text(_conf_field(conf, "name"))
                download_path = _clean_text(_conf_field(conf, "download_path"))
                library_path = _clean_text(_conf_field(conf, "library_path"))
                media_type = _clean_text(_conf_field(conf, "media_type"))
                media_category = _clean_text(_conf_field(conf, "media_category"))
                if not download_path and not library_path:
                    continue
                items.append(
                    {
                        "name": name,
                        "download_path": download_path,
                        "library_path": library_path,
                        "media_type": media_type,
                        "media_category": media_category,
                        "priority": _to_int(_conf_field(conf, "priority")),
                        "is_short_drama": "短剧" in f"{name}{media_category}{download_path}",
                    }
                )
            items.sort(
                key=lambda item: (_to_int(item.get("priority")), str(item.get("name") or ""))
            )
            return items
        except Exception as err:  # noqa: BLE001 - 读取失败不影响页面渲染
            logger.warning(f"{PLUGIN_NAME} 读取系统目录配置失败：{err}")
            return []

    @staticmethod
    def _default_downloader() -> str:
        """宿主下载器配置里被标为「默认」的那个名字；取不到返回空串。"""
        if not HAS_FRAMEWORK:
            return ""
        try:
            from app.application.configuration import get_configured_system_config
            from app.schemas.types import SystemConfigKey

            configs = get_configured_system_config().get(SystemConfigKey.Downloaders) or []
        except Exception as err:  # noqa: BLE001 - 读不到就让前端显示「未指定」
            logger.debug(f"{PLUGIN_NAME} 读取系统默认下载器失败：{err}")
            return ""
        for item in configs:
            if not isinstance(item, dict):
                continue
            if item.get("default") and item.get("enabled", True):
                return str(item.get("name") or "")
        return ""

    @staticmethod
    def _directory_label(item: Dict[str, Any]) -> str:
        """目录下拉的展示文案：``短剧（/vol00/…/短剧/）``。"""
        name = _clean_text(item.get("name")) or _clean_text(item.get("media_category")) or "未命名"
        path = _clean_text(item.get("download_path"))
        return f"{name}（{path}）" if path else name

    # ── 一次性任务 ──

    def _add_once_job(
        self,
        delay_seconds: float = 3,
        trigger: str = "once",
        func: Optional[Callable[..., Any]] = None,
        job_id: str = _ONCE_JOB_ID,
        job_name: str = "",
    ) -> bool:
        """向宿主调度器登记一次性任务。

        关键字是 ``func_kwargs``（不是 ``kwargs``），传错会被内部 try/except 吞掉、
        只留一条错误日志，表现为「手动运行没反应」。

        ``func`` 缺省是整轮任务（``execute_task``）；「刷新作品」等只跑一部分的
        动作传自己的函数，并用 ``job_id`` 与整轮任务区分，避免互相覆盖。
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
                func or self.execute_task,
                job_name or f"{PLUGIN_NAME}执行",
                delay_seconds=delay_seconds,
                func_kwargs={"trigger": trigger},
            )
            return True
        except Exception as err:  # pragma: no cover - 宿主版本差异兜底
            logger.warning(f"{PLUGIN_NAME} 登记一次性任务失败：{err}")
            return False

    # ── 发现层 ──

    def _resolve_douban_cookie(self) -> str:
        """决定用哪份豆瓣 Cookie：配置优先，否则复用宿主 CookieCloud 的登录态。

        带 60 秒进程内缓存：一轮任务里**每位演员**都会取一次 Cookie，直接打 CookieCloud
        会把同一个请求重复几十次（这一层是纯网络往返，宿主侧没有缓存）。
        """
        if self._douban_cookie:
            return self._douban_cookie
        now = time.time()
        if self._cookie_cache_at and now - self._cookie_cache_at < 60:
            return self._cookie_cache
        host = str(getattr(settings, "COOKIECLOUD_HOST", "") or "").strip()
        key = str(getattr(settings, "COOKIECLOUD_KEY", "") or "").strip()
        password = str(getattr(settings, "COOKIECLOUD_PASSWORD", "") or "").strip()
        client = _CookieCloudClient(host=host, key=key, password=password)
        if not client.configured:
            self._cookie_cache = ""
            self._cookie_cache_at = now
            return ""
        cookie = client.fetch("douban.com")
        if cookie:
            logger.info(f"{PLUGIN_NAME} 已从 CookieCloud 取到豆瓣登录态")
        else:
            logger.warning(f"{PLUGIN_NAME} CookieCloud 未取到豆瓣 Cookie：{client.last_error}")
        self._cookie_cache = cookie
        self._cookie_cache_at = now
        return cookie

    def _discover_actor(self, key: str) -> Dict[str, Any]:
        """发现单个演员的作品列表（TMDB + 豆瓣 并集）。

        返回 ``{"key", "name", "douban_id", "tmdb_id", "works": [...], "errors": [...]}``。
        两个来源都失败时 ``works`` 为空、``errors`` 有可读原因。
        """
        record: Dict[str, Any] = {
            "key": key,
            "name": key,
            "douban_id": "",
            "tmdb_id": "",
            "works": [],
            "errors": [],
        }
        works: List[Dict[str, Any]] = []

        # ── 豆瓣：可填人物 ID 或主页链接，否则按名称搜索 ──
        existing = self._load_actors().get(key)
        if isinstance(existing, dict):
            record["douban_id"] = str(existing.get("douban_id") or "")
            record["tmdb_id"] = str(existing.get("tmdb_id") or "")
            record["name"] = str(existing.get("name") or key)

        douban = _DoubanClient(proxy=self._proxy, cookie=self._resolve_douban_cookie())
        person_id = record["douban_id"] or self._extract_person_id(key)
        if not person_id:
            matches = douban.search_person(key)
            if matches:
                person_id = matches[0]["id"]
                record["name"] = matches[0].get("name") or key
            elif douban.last_error:
                record["errors"].append(f"豆瓣：{douban.failure_hint()}")
        if person_id:
            record["douban_id"] = person_id
            works.extend(self._douban_works(douban, person_id, record))

        # ── TMDB ──
        tmdb = _TmdbClient(proxy=self._proxy)
        tmdb_id = record["tmdb_id"]
        if not tmdb_id:
            matches = tmdb.search_person(key)
            if matches:
                tmdb_id = matches[0]["id"]
            elif tmdb.last_error:
                record["errors"].append(f"TMDB：{tmdb.last_error}")
        if tmdb_id:
            record["tmdb_id"] = tmdb_id
            credits = tmdb.person_credits(tmdb_id)
            if not credits and tmdb.last_error:
                record["errors"].append(f"TMDB：{tmdb.last_error}")
            works.extend(credits)

        record["works"] = self._merge_works(works)
        return record

    @staticmethod
    def _extract_person_id(value: str) -> str:
        """从「纯数字 ID」或「豆瓣人物主页链接」里取人物 ID；取不到返回空串。"""
        text = _clean_text(value)
        if text.isdigit():
            return text
        match = _PERSON_URL_PATTERN.search(text)
        return match.group(1) if match else ""

    def _douban_works(self, client: _DoubanClient, person_id: str, record: Dict[str, Any]) -> List[Dict[str, Any]]:
        """取一位豆瓣人物的影视作品集（先取详情，作品集与作品都在详情里）。"""
        detail = client.person_detail(person_id)
        if not detail:
            if client.last_error:
                record["errors"].append(f"豆瓣：{client.failure_hint()}")
            else:
                record["errors"].append("豆瓣：人物详情为空（可能人物 ID 无效）")
            return []
        collection = self._work_collection(detail)
        if not collection:
            # 静默返回空会让「作品墙只有 TMDB 的几条」这种问题无从排查，
            # 因此把详情里实际有哪些 module 类型一并报出来。
            types = [
                str(module.get("type"))
                for module in (detail.get("modules") or [])
                if isinstance(module, dict)
            ]
            record["errors"].append(f"豆瓣：人物详情里没有「影视」作品集（modules={types or '无'}）")
            return []

        works: List[Dict[str, Any]] = []
        for raw in collection.get("works") or []:
            candidate = douban_work_to_candidate(raw)
            if candidate:
                works.append(candidate)
            if len(works) >= self._max_works:
                break

        if not works:
            # 集合里没内嵌作品时，退回按集合 id 请求一次（老结构的行为）
            collection_id = _clean_text(collection.get("id")) or _clean_text(collection.get("_payload_id"))
            for raw in client.person_works(collection_id, count=self._max_works):
                candidate = douban_work_to_candidate(raw)
                if candidate:
                    works.append(candidate)

        if not works:
            record["errors"].append("豆瓣：作品集里没有可解析的影视条目")
        return works

    @staticmethod
    def _work_collection(detail: Dict[str, Any]) -> Dict[str, Any]:
        """从人物详情里取「影视」作品集（返回整个集合对象，作品就内嵌在里面）。

        ⚠️ 实测（2026-10，豆瓣 frodo ``/elessar/subject/{id}``）：真实结构是

        ``modules[type=work_collections].payload.collections[].{id, title, total, works}``

        两个与直觉不符的点，都足以让整条豆瓣链路**静默失效**（不报错、只是没数据）：

        1. 比早期文档多了一层 ``payload``（``module["collections"]`` 恒为 ``None``）；
        2. 集合自身的 ``id`` 是**空串**（``payload.id`` 才是可用 ID），
           ``works`` 直接内嵌在集合里（10 条；``start>0`` 一律返回空，即不支持翻页）。

        因此这里对「内嵌 ``payload``」与「旧版直接挂 collections」两种结构都做兼容。
        """
        for module in detail.get("modules") or []:
            if not isinstance(module, dict) or module.get("type") != "work_collections":
                continue
            payload = module.get("payload") if isinstance(module.get("payload"), dict) else {}
            collections: Any = payload.get("collections")
            if collections is None:
                collections = module.get("collections")  # 旧结构兜底
            for collection in collections or []:
                if not isinstance(collection, dict):
                    continue
                if "影视" not in _clean_text(collection.get("title")):
                    continue
                merged = dict(collection)
                if payload.get("id"):
                    merged["_payload_id"] = payload.get("id")
                return merged
        return {}

    @staticmethod
    def _merge_works(works: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """合并多来源作品，按「归一化剧名 + 年份」去重，豆瓣优先补别名。

        去重键与账本键一致，保证「发现 → 匹配 → 记账」用的是同一套身份口径。
        """
        merged: Dict[str, Dict[str, Any]] = {}
        for item in works:
            if not isinstance(item, dict):
                continue
            title = _clean_text(item.get("title"))
            if not title:
                continue
            year = _clean_text(item.get("year"))
            key = ledger_key(title, year)
            current = merged.get(key)
            if current is None:
                merged[key] = dict(item)
                continue
            # 已经有一条时：补齐缺失字段，不覆盖已有值
            for field in ("year", "alt_title", "media_id", "type"):
                if not current.get(field) and item.get(field):
                    current[field] = item[field]
        return list(merged.values())

    def _refresh_actors(self) -> List[Dict[str, Any]]:
        """刷新全部演员的作品快照，并汇总出候选作品列表。"""
        snapshot: Dict[str, Any] = {}
        candidates: Dict[str, Dict[str, Any]] = {}
        for key in self._actors:
            try:
                record = self._discover_actor(key)
            except Exception as err:  # noqa: BLE001 - 单个演员失败不影响其它演员
                logger.error(f"{PLUGIN_NAME} 解析演员「{key}」失败：{err}")
                record = {"key": key, "name": key, "works": [], "errors": [str(err)]}
            record["time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            snapshot[key] = record
            for work in record.get("works") or []:
                work = dict(work)
                work["actor"] = record.get("name") or key
                candidates[ledger_key(work.get("title") or "", work.get("year") or "")] = work
            if record.get("errors"):
                logger.warning(f"{PLUGIN_NAME} 演员「{key}」部分来源失败：{record['errors']}")
        self.save_data(_DATA_ACTORS, snapshot)
        return list(candidates.values())

    # ── 主流程 ──

    def execute_task(self, trigger: str = "manual") -> bool:
        """执行一轮完整任务：发现 → 搜索 → 匹配 → 择优 → 下载。

        返回是否成功（无异常即视为成功，即使没有新剧可下）。
        """
        if not self.get_state():
            return False
        if not self._actors or not self._sites:
            self._last_result = {"success": False, "message": "未配置演员或搜索站点"}
            logger.warning(f"{PLUGIN_NAME} 未配置演员或搜索站点，跳过执行")
            return False
        if not self._lock.acquire(blocking=False):
            logger.info(f"{PLUGIN_NAME} 上一轮仍在执行，跳过本次触发（{trigger}）")
            return False
        self._running = True
        started = time.time()
        try:
            logger.info(f"{PLUGIN_NAME} 开始执行（触发方式：{trigger}）")
            candidates = self._refresh_actors()
            ledger = self._load_ledger()
            misses = self._load_misses()
            searcher = _SiteSearcher(self._sites, prefer_short_drama_category=self._prefer_short_drama_category)

            downloaded: List[Dict[str, Any]] = []
            skipped = 0
            cooled = 0
            errors: List[str] = []
            cooldown_seconds = _MISS_COOLDOWN_HOURS * 3600

            for work in candidates:
                title = _clean_text(work.get("title"))
                year = _clean_text(work.get("year"))
                key = ledger_key(title, year)
                if key in ledger:
                    skipped += 1
                    continue
                if not title:
                    continue
                # 未命中冷却：上次搜过且空手而归的剧，冷却期内不重复搜索
                last_miss = _to_float(misses.get(key))
                if last_miss and time.time() - last_miss < cooldown_seconds:
                    cooled += 1
                    continue
                try:
                    outcome = self._process_candidate(work, searcher)
                except Exception as err:  # noqa: BLE001 - 单剧失败不影响整轮
                    logger.error(f"{PLUGIN_NAME} 处理「{title}」失败：{err}")
                    errors.append(f"{title}：{err}")
                    continue
                # 无论「站点没资源」还是「下载提交失败」，都记一次冷却；
                # 成功下载的剧从冷却表移除（账本接手去重）。
                if outcome is None:
                    misses[key] = time.time()
                elif outcome.get("ok"):
                    misses.pop(key, None)
                    ledger[key] = outcome["entry"]
                    downloaded.append(outcome["entry"])
                else:
                    misses[key] = time.time()
                    if outcome.get("reason"):
                        errors.append(f"{title}：{outcome['reason']}")

            self._save_ledger(ledger)
            self.save_data(_DATA_MISS, misses)
            stats = {
                "candidates": len(candidates),
                "downloaded": len(ledger),
                "last_run": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "elapsed": round(time.time() - started, 1),
            }
            self._save_stats(stats)
            self._last_result = {
                "success": True,
                "message": (
                    f"本轮候选 {len(candidates)} 部，跳过已下载 {skipped} 部，"
                    f"冷却中 {cooled} 部，新下载 {len(downloaded)} 部，耗时 {stats['elapsed']}s"
                ),
            }
            logger.info(f"{PLUGIN_NAME} {self._last_result['message']}")
            if self._notify:
                self._send_notify(self._last_result["message"], downloaded, errors)
            return True
        except Exception as err:  # noqa: BLE001 - 兜底，避免定时任务整体挂掉
            self._last_result = {"success": False, "message": f"执行异常：{err}"}
            logger.error(f"{PLUGIN_NAME} 执行异常：{err}")
            return False
        finally:
            self._running = False
            self._lock.release()

    def _process_candidate(self, work: Dict[str, Any], searcher: _SiteSearcher) -> Optional[Dict[str, Any]]:
        """处理单个候选作品：搜索 → 匹配 → 择优 → 下载。

        返回 ``None`` 表示站点无资源（不算错误）；否则返回
        ``{"ok": bool, "entry"|"reason": ...}``。
        """
        title = _clean_text(work.get("title"))
        alt_title = _clean_text(work.get("alt_title"))
        year = _clean_text(work.get("year"))
        aliases = [item for item in (title, alt_title) if item]

        results = searcher.search(title)
        if not results:
            return None

        matched: List[Dict[str, Any]] = []
        for torrent in results:
            if not title_matches(torrent, aliases):
                continue
            torrent_year = extract_year(
                f"{torrent.get('title') or ''} {torrent.get('description') or ''}"
            )
            if not year_compatible(torrent_year, year):
                continue
            torrent["_year"] = torrent_year
            matched.append(torrent)

        if not matched:
            return None

        best = pick_best(matched)
        if not best:
            return None

        download_hash = self._download(best)
        if not download_hash:
            return {"ok": False, "reason": "下载提交失败"}

        return {
            "ok": True,
            "entry": {
                "title": title,
                "year": year,
                "episodes": extract_episode_count(best.get("description") or ""),
                "site_name": best.get("site_name") or "",
                "torrent_title": best.get("title") or "",
                "torrent_hash": download_hash,
                "media_source": work.get("source") or "",
                "media_id": work.get("media_id") or "",
                "actor": work.get("actor") or "",
                "alternatives": len(matched),
                "organized": False,
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            },
        }

    # ── 下载 ──

    def _download(self, torrent: Dict[str, Any]) -> Optional[str]:
        """下载种子文件并提交给下载器，成功返回下载哈希。

        流程与宿主内的常规下载一致：带站点 Cookie 拉种子文件 → 校验是合法种子 →
        交给 ``DownloaderHelper`` 的实例按下载器类型调用 ``add_torrent``。
        """
        if not HAS_FRAMEWORK:
            logger.error(f"{PLUGIN_NAME} 框架模块不可用，无法下载")
            return None
        enclosure = str(torrent.get("enclosure") or "").strip()
        if not enclosure:
            logger.error(f"{PLUGIN_NAME} 种子无下载链接：{torrent.get('title')}")
            return None
        if not self._download_path:
            logger.error(f"{PLUGIN_NAME} 未配置下载目录")
            return None
        if not self._downloader:
            logger.error(f"{PLUGIN_NAME} 未选择下载器")
            return None

        cookie = self._site_cookie(site_domain_of(enclosure))
        proxies = getattr(settings, "PROXY", None) if self._proxy else None
        response = None
        try:
            response = RequestUtils(cookies=cookie, timeout=30, proxies=proxies).get_res(enclosure)
            if not response or not response.content:
                logger.error(f"{PLUGIN_NAME} 下载种子文件失败：{torrent.get('title')}")
                return None
            content = response.content
            head = content[:20] if len(content) >= 20 else content
            if not (head.startswith(b"d8:announce") or b"d8:announce" in head):
                logger.error(f"{PLUGIN_NAME} 下载到的内容不是合法种子文件")
                return None
        except Exception as err:  # noqa: BLE001 - 网络异常统一降级为失败
            logger.error(f"{PLUGIN_NAME} 获取种子文件异常：{err}")
            return None
        finally:
            if response is not None:
                try:
                    response.close()
                except Exception:  # pragma: no cover
                    pass

        try:
            service = DownloaderHelper().get_service(name=self._downloader)
            if not service or not service.instance:
                logger.error(f"{PLUGIN_NAME} 下载器 {self._downloader} 不存在或未连接")
                return None
            instance = service.instance
            if DownloaderHelper().is_downloader("qbittorrent", service=service):
                success, hashes = instance.add_torrent(
                    content=content, download_dir=self._download_path, tag=_DOWNLOAD_TAG
                )
                if not success:
                    logger.error(f"{PLUGIN_NAME} qBittorrent 添加种子失败")
                    return None
                download_hash = hashes[0] if hashes else None
            else:
                added = instance.add_torrent(
                    content=content, download_dir=self._download_path, labels=[_DOWNLOAD_TAG]
                )
                if not added:
                    logger.error(f"{PLUGIN_NAME} Transmission 添加种子失败")
                    return None
                download_hash = getattr(added, "hashString", None)
            logger.info(f"{PLUGIN_NAME} 已提交下载：{torrent.get('title')}（hash={download_hash}）")
            return download_hash or "submitted"
        except Exception as err:  # noqa: BLE001
            logger.error(f"{PLUGIN_NAME} 提交下载器异常：{err}")
            return None

    @staticmethod
    def _site_cookie(domain: str) -> str:
        """按域名取站点 Cookie（用于下载种子文件）。"""
        if not domain or not HAS_FRAMEWORK:
            return ""
        try:
            site = SitesHelper().get_indexer(domain)
            if not site:
                # 退一级域名再试（下载链接可能是子域）
                parts = domain.split(".")
                if len(parts) >= 2:
                    site = SitesHelper().get_indexer(".".join(parts[-2:]))
            return str((site or {}).get("cookie") or "")
        except Exception as err:  # noqa: BLE001
            logger.warning(f"{PLUGIN_NAME} 读取站点 Cookie 失败（{domain}）：{err}")
            return ""

    # ── 整理 ──

    def organize_once(self, trigger: str = "manual") -> bool:
        """扫描账本中已下载未整理的条目，逐一整理入库。

        与下载解耦：整理是独立的定时任务，因此下载还在进行时不会误判为失败。
        ``trigger`` 由宿主调度器按 ``func_kwargs`` 注入（interval/manual），
        仅用于日志口径，不影响行为。
        """
        if not self.get_state() or not self._organize_enabled:
            return False
        ledger = self._load_ledger()
        if not ledger:
            return False
        organizer = _Organizer(
            download_path=self._download_path,
            library_path=self._library_path,
            transfer_type=self._transfer_type,
        )
        if not organizer.ready:
            logger.warning(f"{PLUGIN_NAME} 未配置下载目录或媒体库目录，跳过整理")
            return False

        organized = 0
        changed = False
        for key, entry in ledger.items():
            if not isinstance(entry, dict) or entry.get("organized"):
                continue
            ok, message = organizer.organize(entry)
            if ok:
                entry["organized"] = True
                entry["organized_path"] = message
                organized += 1
                changed = True
                logger.info(f"{PLUGIN_NAME} 已整理「{entry.get('title')}」→ {message}")
        if changed:
            self._save_ledger(ledger)
            logger.info(f"{PLUGIN_NAME} 本轮整理完成，共 {organized} 部")
        return True

    # ── 通知 ──

    def _send_notify(self, detail: str, downloaded: List[Dict[str, Any]], errors: List[str]) -> None:
        """通过宿主通知渠道发送结果；通知失败不影响主流程。"""
        lines = [detail]
        if downloaded:
            lines.append("")
            lines.append("新下载：")
            for item in downloaded[:10]:
                episode = f" 全{item['episodes']}集" if item.get("episodes") else ""
                lines.append(f"· {item['title']}（{item.get('year') or '年份未知'}）{episode} @ {item.get('site_name') or '未知站点'}")
        if errors:
            lines.append("")
            lines.append("异常：")
            lines.extend(f"· {item}" for item in errors[:5])
        try:
            self.post_message(
                mtype=_MessageType.Plugin,
                title=f"【{self.plugin_name}】订阅轮询完成",
                text="\n".join(lines),
            )
        except Exception as err:  # pragma: no cover - 未配置通知渠道时兜底
            logger.warning(f"{PLUGIN_NAME} 发送通知失败：{err}")
