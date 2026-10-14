"""短剧百科数据源（MoviePilot V3 插件后端）。

把「短剧百科」（``duanjubaike.org``）包装成 MoviePilot 的一等媒体数据源 —— 与
TMDB / 豆瓣 / Bangumi 同级。短剧在 TMDB / 豆瓣上大量没有条目，宿主识别器因此建不起
媒体身份；本插件补的正是这一段空白，同时对外提供**演员数据**。

宿主契约（V3.1.5 源码实证）
---------------------------
1. **扩展点是官方的**：``_PluginBase`` 提供 ``get_media_source()``（声明数据源）与
   ``get_module()``（把宿主模块方法名映射到插件实现）；宿主会把本插件声明的来源与
   内置来源合并去重后下发。
2. **来源标识不是封闭枚举**：``MediaSource("duanjubaike")`` 可直接构造（已装插件
   ``iqiyidiscover`` / ``lunatvsource`` 是同等先例）。
3. **模块方法签名照宿主静态合同，一个字都不能改**：``recognize_media`` /
   ``async_recognize_media`` / ``search_medias`` / ``async_search_medias`` /
   ``obtain_images`` / ``async_obtain_images``。
4. **默认视频识别源是硬编码的 TMDB** ⇒ 本插件**不会**自动成为全局兜底，
   ``media_source`` 不匹配时**必须返回 None**，绝不能劫持其它来源的识别。
5. **图片域名要登记**：宿主图片代理只放行 ``settings.SECURITY_IMAGE_DOMAINS`` 内的
   域名，插件自带的图片站要在 ``init_plugin`` 里补进去。

站点能力边界（2026-10-14 / 15 实测）
------------------------------------
* ``/zh-Hans/drama/{id}``：详情页，JSON-LD（``TVSeries`` + ``PerformanceRole`` 演员）
  + HTML（阵容、剧照、集数/时长/首播/出品方）。**最可靠的一条路**。
* ``/zh-Hans/actor/{id}``：演员页，JSON-LD ``Person``（姓名/简介/头像/性别/国籍）
  + 「作品」网格（实测 59 部也一次全渲染、不分页）+ 合作演员区。

检索只有**一条路：站外索引**（``_web_index_search``）——``site:<域名> <关键词>`` 交给
搜索引擎，从已收录的详情页 / 演员页 URL 里取数字 ID。

⚠️ 站点自身没有可用的检索通道：``/zh-Hans/drama/search`` 是 Cloudflare **托管挑战**，
服务端直连恒 403，宿主浏览器仿真**有头/无头都过不去**；目录页则是最早被限流的一条路径。
因此 v1.8.0 把此前的「榜单快照」一级也去掉了（见下）。

**演员数据走同一条通道**：``site:<域名> <演员名>`` → 结果里的 ``/actor/<id>`` →
抓演员页 → 复用 ``parse_org_cards`` 取出全部作品（见 ``search_actors`` / ``actor_works``）。

统一媒体身份
------------
``media_source`` 恒为 ``"duanjubaike"``；作品 ``media_id`` 形如 ``org:<id>``，
演员形如 ``actor:<id>``（裸数字也接受）。复合 ID 在宿主里有先例。

供其它插件调用
--------------
1. **宿主模块分发（首选，进程内、零序列化）** —— 宿主的分发器同时挂了模块目录与
   **插件目录**，而每个插件都是 ``ChainBase`` 子类，所以其它插件直接：

       infos  = self.run_module("search_medias", meta=meta, media_source="duanjubaike")
       info   = self.run_module("recognize_media", media_source="duanjubaike",
                                media_id="org:40105")
       works  = self.run_module("actor_works", actor_id="371")
       actors = self.run_module("search_actors", name="魏依珂")

   ``media_source`` 可写 ``duanjubaike`` / ``shortdramabaike`` / ``shortdramabaikesource``
   任一（见 ``MEDIA_SOURCE_ALIASES``）。作品类方法返回宿主 ``MediaInfo``。

   ⚠️ ``search_actors`` / ``actor_works`` 是**自定义模块方法名**（不在宿主
   ``module_method`` 合同里）。宿主对未登记的名字走 legacy 契约
   （``public_to_plugins=True``，聚合 = 有序列表合并），且分发器按
   ``plugin.get_module()[method]`` 取函数、**没有该方法名的插件会被跳过** ⇒ 新增自定义
   名不会影响别的插件。两个方法都**返回列表**（legacy 聚合对列表做 ``extend``）。

2. **HTTP 纯 JSON 出口**：``GET /api/v1/plugin/ShortDramaBaikeSource/recognize``
   （``media_id`` 或 ``keyword`` + 可选 ``year``）与 ``…/actor``（``actor_id`` 或
   ``name``）；形状见 ``build_public_record`` / ``build_public_actor``。

3. **插件面板（Vue 联邦前端）**：详情弹窗里**只有一个搜索框** —— 片名与演员名都收，
   一次检索同时给出「作品候选」与「演员候选」两块，哪块有结果就显示哪块；
   条目以卡片呈现、每条可展开看插件处理后的完整字段。

所有入口内部都走同一套代码（``_resolve_item`` / ``_search_by_title`` / ``_fetch_detail``
/ ``_fetch_actor``）。

**v1.8.0 移除了「榜单快照」与「宿主探索页」两条功能线**（用户明确要求）：榜单快照原本
只服务于探索页的数据来源与片名检索的零请求降级，探索页去掉后它就没有存在理由；
``TOP_LISTS`` / ``refresh_top_lists`` / ``get_service`` / ``discover_source`` / ``/explore``
与 ``top_keys`` / ``explore_detail_fetch`` 两个配置项**整体删除**，插件不再注册任何后台
服务，也不再往宿主的探索页挂来源。

**⚠️ 本插件不提供智能体工具**（`get_agent_tools` 已删除）：面板搜索框 + HTTP 接口
已经覆盖同样的能力，而智能体工具会往宿主的工具目录里塞两个入口、与面板职责重复。
"""
from __future__ import annotations

import asyncio
import html as _html
import json
import re
import threading
import time
import urllib.parse
from typing import Any, Dict, List, Optional, Tuple

from app.schemas.types import MediaSource, MediaType
from app.sdk.logging import logger
from app.sdk.plugin import _PluginBase

try:  # 宿主的稳定配置入口（图片域名白名单等）
    from app.sdk.config import settings as _settings
except Exception:  # pragma: no cover - 宿主版本差异兜底
    _settings = None

try:  # 宿主统一 HTTP 入口（自动继承系统代理等设置）
    from app.sdk.network import RequestUtils as _RequestUtils
except Exception:  # pragma: no cover - 宿主版本差异兜底
    _RequestUtils = None

try:  # 宿主媒体信息领域模型（与 TMDB / 豆瓣模块返回的是同一个类）
    from app.sdk.media import MediaInfo as _HostMediaInfo
except Exception:  # pragma: no cover - 宿主版本差异兜底
    _HostMediaInfo = None

try:  # 站外索引检索：宿主依赖里的多引擎搜索（DDGS），缺失时该通道自动停用
    from ddgs import DDGS as _DDGS
except Exception:  # pragma: no cover - 宿主版本差异兜底
    _DDGS = None  # type: ignore[assignment]

# ── 插件元数据（须与 package.v3.json 保持一致） ──────────────────────
PLUGIN_NAME = "短剧百科数据源"
PLUGIN_ICON = (
    "https://raw.githubusercontent.com/m215owen/MoviePilot-Plugins/main/icons/"
    "ShortDramaBaikeSource.png"
)
PLUGIN_VERSION = "1.8.0"

# ── 数据源常量 ────────────────────────────────────────────────────
# 规范写法是宿主 ``MediaSource`` 枚举值；另外两个别名是为了让**其它插件**按
# 「插件 ID」或「域名简称」点名时也能命中，不必去查枚举值的准确拼写。
MEDIA_SOURCE_KEY = "duanjubaike"
MEDIA_SOURCE_LABEL = "短剧百科"
MEDIA_SOURCE_ALIASES = frozenset({"duanjubaike", "shortdramabaike", "shortdramabaikesource"})

ORG_DEFAULT_DOMAIN = "https://duanjubaike.org"

# 站点路径（``{id}`` 为占位）
DETAIL_PATH = "/zh-Hans/drama/{id}"
ACTOR_PATH = "/zh-Hans/actor/{id}"

# 统一媒体 ID 前缀（media_id 形如 ``org:40105``）。
MEDIA_ID_PREFIX = "org"
# 演员 ID 前缀（形如 ``actor:371``）。演员**不是**媒体条目，不给宿主路由用，
# 只是让跨插件调用方能一眼分清「这是演员 ID 还是作品 ID」。
ACTOR_ID_PREFIX = "actor"

# 需要登记进宿主图片白名单的域名（否则图片代理会拒收）
IMAGE_DOMAINS: Tuple[str, ...] = (
    "cdn.duanjubaike.org",
    "cdn.duanjubaike.cn",
    "duanjubaike.org",
)

# 默认值 / 上限
DEFAULT_TIMEOUT = 15
DEFAULT_CACHE_TTL = 604800          # 详情页内容基本不变，缓存 7 天

# ⚠️ 请求闸门（额度窗口 / 最小间隔 / 撞 403 冷却）已**整体删除**。原因见模块头「限流」：
# 站点风控只压在目录页那条路径上，而本插件已经不用目录页。现在 ``_request`` 就是一次
# 裸 GET，撞到 403 的后果仅仅是当次拿不到数据 —— 不写任何跨请求状态。
MAX_CANDIDATES = 12
# 演员检索：一次站外检索返回多少个候选演员（结果里会混进引擎的模糊匹配，交给打分排序）
MAX_ACTOR_CANDIDATES = 8
# 自检（/probe）在「检索没命中」时用来兜底的详情样本：实测存在且字段完整的作品
PROBE_SAMPLE_MEDIA_ID = "org:45982"

# ── 站外索引（搜索引擎收录）检索 ────────────────────────────────────
# 站内检索被 Cloudflare 挡住，于是改问搜索引擎：``site:<域名> <片名>`` 返回的是
# **搜索引擎已收录的详情页 URL**，路径末尾的数字就是作品 ID；而详情页本身没有挑战
# （2026-10-15 实测：普通 HTTP 抓 ``/zh-Hans/drama/<id>`` 与 ``/drama/<id>`` 都是 200 / 约 2s）。
WEB_INDEX_BACKENDS = ("auto", "duckduckgo", "yandex", "google", "brave", "mojeek")
DEFAULT_WEB_INDEX_BACKEND = "auto"
WEB_INDEX_MAX_RESULTS = 10          # 单次取多少条结果（实测 10 条足够覆盖多季）
WEB_INDEX_TIMEOUT = 25              # 单次检索超时（秒）
WEB_INDEX_MIN_INTERVAL = 3.0        # 相邻两次站外检索的最小间隔（秒）—— 引擎不接受高频调用
# 搜索结果标题带站点后缀：「片名 - 短剧 - 短剧百科」/「姓名 - 短剧演员 - 短剧百科」
# （繁体页面是「短劇」），剥掉才能参与打分
WEB_INDEX_TITLE_SUFFIX_RE = re.compile(
    r"\s*[-|｜]\s*(?:短剧|短劇)(?:演员|演員)?(?:\s*[-|｜]\s*(?:短剧|短劇)百科)?\s*$"
)
# 只认作品详情页：``/drama/<数字>``（可带 zh-Hans / zh-Hant 前缀），排除 /photos、/actor 等
_WEB_INDEX_DETAIL_RE = re.compile(r"^/(?:zh-Hans|zh-Hant)?/?drama/(?P<id>\d+)/?$")
# 只认演员页：``/actor/<数字>``（可带 zh-Hans / zh-Hant 前缀）
_WEB_INDEX_ACTOR_RE = re.compile(r"^/(?:zh-Hans|zh-Hant)?/?actor/(?P<id>\d+)/?$")

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


# ── 通用小工具 ────────────────────────────────────────────────────


def _clean(text: Any) -> str:
    """折叠空白并做 HTML 反转义；非字符串一律转成空串。"""
    if text is None:
        return ""
    if not isinstance(text, str):
        text = str(text)
    return _html.unescape(re.sub(r"\s+", " ", text)).strip()


def _strip_tags(text: Any) -> str:
    if not isinstance(text, str):
        return _clean(text)
    return _clean(re.sub(r"<[^>]+>", " ", text))


def _has_value(value: Any) -> bool:
    """合并详情时用：空串 / 空集合 / None 都算「没值」，不该覆盖已有字段。"""
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, dict, set)):
        return bool(value)
    return True


def _normalize_image(src: str) -> str:
    src = _clean(src)
    if not src:
        return ""
    if src.startswith("//"):
        return f"https:{src}"
    return src


def _parse_int(value: Any) -> Optional[int]:
    match = re.search(r"\d+", str(value or ""))
    return int(match.group(0)) if match else None


def _parse_year(value: Any) -> Optional[str]:
    match = re.search(r"(19|20)\d{2}", str(value or ""))
    return match.group(0) if match else None


def _parse_wannum(value: Any) -> Optional[float]:
    """把「965 万」这类带单位的计数还原成绝对值。

    站点在播放量一类的大数上会用**千分位**（``1,029``），所以先把逗号去掉再取数 ——
    否则正则只会匹配到第一个数字段，``1,029`` 会静默变成 ``1``。
    """
    text = _clean(value).replace(",", "")
    if not text:
        return None
    number = re.search(r"\d+(?:\.\d+)?", text)
    if not number:
        return None
    amount = float(number.group(0))
    if "亿" in text:
        amount *= 100000000
    elif "万" in text:
        amount *= 10000
    return amount


def _parse_duration_minutes(value: Any) -> Optional[int]:
    text = _clean(value)
    if not text:
        return None
    iso = re.fullmatch(
        r"P(?:(?P<days>\d+)D)?T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?",
        text,
    )
    if iso:
        days = int(iso.group("days") or 0)
        hours = int(iso.group("hours") or 0)
        minutes = int(iso.group("minutes") or 0)
        seconds = int(iso.group("seconds") or 0)
        total = days * 1440 + hours * 60 + minutes + (1 if seconds >= 30 else 0)
        return total or None
    hours = re.search(r"(\d+)\s*小时", text)
    minutes = re.search(r"(\d+)\s*分", text)
    if hours or minutes:
        return int(hours.group(1) if hours else 0) * 60 + int(minutes.group(1) if minutes else 0)
    return None


def _normalize_title(title: str) -> str:
    text = _clean(title)
    text = text.replace("《", "").replace("》", "")
    text = re.sub(r"\s+", "", text)
    text = "".join(
        chr(ord(char) - 0xFEE0) if "\uFF01" <= char <= "\uFF5E" else char for char in text
    )
    return text.casefold()


def _match_title(candidate: str, target: str) -> int:
    """给候选片名与目标片名的接近程度打分（越大越像），0 表示不相关。

    短剧站常见的召回缺口是「站点加了前后缀」（我的闪婚老公是豪门 vs 闪婚老公是豪门），
    所以包含关系也给分，但精确相等得分最高。
    """
    left, right = _normalize_title(candidate), _normalize_title(target)
    if not left or not right:
        return 0
    if left == right:
        return 100
    if left in right or right in left:
        return 60
    # 去掉季/部/集数等尾缀后再比一次
    trimmed = re.sub(r"(第[一二三四五六七八九十\d]+[季部]|全\d+集)$", "", right)
    if trimmed and trimmed != right and (left in trimmed or trimmed in left):
        return 40
    return 0


def _strip_org_suffix(title: str) -> str:
    """剥掉搜索引擎结果标题里的站点后缀。

    ``片名 - 短剧 - 短剧百科`` → ``片名``；``姓名 - 短剧演员 - 短剧百科`` → ``姓名``
    （繁体页面是「短劇」「演員」）。
    """
    text = _clean(title)
    while True:
        stripped = WEB_INDEX_TITLE_SUFFIX_RE.sub("", text).strip()
        if stripped == text:
            return text
        text = stripped


def _web_index_native_id(url: str, host: str) -> str:
    """从搜索引擎结果里的 URL 取作品 ID；不是本域的详情页一律返回空串。

    结果里混着演员页（``/actor/371``）、图集页（``/drama/37508/photos``）与榜单页，
    它们都拿不到作品 ID —— 用「路径恰好是 ``/drama/<数字>``」这一条把它们筛掉。
    """
    return _web_index_id(url, host, _WEB_INDEX_DETAIL_RE)


def _web_index_actor_id(url: str, host: str) -> str:
    return _web_index_id(url, host, _WEB_INDEX_ACTOR_RE)


def _web_index_id(url: str, host: str, pattern: Any) -> str:
    """本域 + 路径形态都对上时取出末尾的数字 ID，否则空串。

    :param url: 搜索引擎结果里的地址
    :param host: 本域主机名（空表示不校验域名）
    :param pattern: 路径正则（``/drama/<id>`` 或 ``/actor/<id>``）
    """
    try:
        parsed = urllib.parse.urlparse(_clean(url))
    except Exception:  # pragma: no cover - 地址异常按非目标页处理
        return ""
    netloc = (parsed.netloc or "").lower()
    host = _clean(host).lower()
    if host and not (netloc == host or netloc.endswith("." + host)):
        return ""
    match = pattern.match(parsed.path or "")
    return match.group("id") if match else ""


# ── ``.org`` 卡片解析（目录页 / 精选页 / 榜单页通用） ────────────────

# 作品卡链接。三种版式的 href 形态一致，但标题与封面位置不同：
#   目录页/精选页  <a href="…/zh-Hans/drama/61824" class="relative block …">
#                      <img … alt="片名" src="封面">…</a>
#   榜单页        <a href="…/zh-Hans/drama/37512" class="hover:text-orange-600">片名</a>
#                  —— 标题是**锚文本**，封面 <img> 在**兄弟节点**（锚之前）
# 所以 id 一律从 href 取，标题与封面按「锚内优先、锚外兜底」两级取。
_ORG_CARD_RE = re.compile(
    r'<a\b[^>]*href="(?:https?://[^"]*?)?/zh-Hans/drama/(?P<id>\d+)"[^>]*>(?P<body>.*?)</a>',
    re.S,
)
_ORG_CARD_ALT_RE = re.compile(r'alt="(?P<alt>[^"]*)"')
_ORG_CARD_SRC_RE = re.compile(r'src="(?P<src>[^"]+)"')
_ORG_IMG_RE = re.compile(r'<img\b[^>]*src="(?P<src>[^"]+)"', re.S)

# ⚠️ 目录页 / 精选页的**每一部作品有两个锚**（海报锚 + 标题锚），而字段分散在两处：
#   海报锚内   封面 <img alt/src>、评分、系列季、集数
#   标题锚前后 真人/AI 角标、热度/播放、标签
# 所以必须按「卡片外壳」整块切，**不能**按「下一个锚」切 —— 那样会在标题锚处截断，
# 真人/AI、热度、标签三组字段会整段丢掉（实测过的静默失效）。
_ORG_CARD_BLOCK_MARK = (
    '<div class="bg-gray-50 dark:bg-gray-700 rounded-xl overflow-hidden '
    'border border-gray-200 dark:border-gray-600">'
)
_ORG_CARD_SPAN = 5000

# ── 卡片内的可选字段（站点在不同版式下渲染的字段并不一致，取不到就整条不带） ──
# 真人 / AI 角标：标题前那个带 title 的小胶囊
_ORG_KIND_RE = re.compile(r'<span class="inline-flex[^"]*"\s+title="(?P<kind>[^"]+)"')
# 状态角标（爆火 / 新剧 …）：海报左上角的胶囊。底色随语义变（目录页红＝爆火、
# 精选页绿＝新剧），所以颜色位用通配，靠 `text-white text-xs px-2 py-1 rounded-full`
# 这串固定的排版类锁定它。
_ORG_BADGE_RE = re.compile(
    r'<div class="bg-[a-z]+-500 text-white text-xs px-2 py-1 rounded-full[^"]*"[^>]*>(?P<body>.*?)</div>',
    re.S,
)
_ORG_EPISODES_RE = re.compile(r"(?P<count>\d+)\s*集")
_ORG_RATING_RE = re.compile(r"icon-star[^>]*>.*?<span>\s*(?P<rating>\d+(?:\.\d+)?)\s*</span>", re.S)
_ORG_SERIES_RE = re.compile(r'class="absolute bottom-2 left-2[^"]*"[^>]*title="(?P<series>[^"]*)"')
_ORG_SEASON_RE = re.compile(r"第\s*(?P<season>\d+)\s*季")
_ORG_TAG_RE = re.compile(r'<span class="inline-block rounded bg-blue-100[^"]*">\s*(?P<tag>[^<]+?)\s*</span>')
# 「11721万热度/648万播放」——两个数各自独立，播放数可能缺省
_ORG_HEAT_RE = re.compile(r"(?P<value>[\d.]+\s*[万亿]?)\s*热度")
_ORG_PLAYS_RE = re.compile(r"(?P<value>[\d.]+\s*[万亿]?)\s*播放")
# 站点的 ``genre`` 里混着集数说明（实测「家庭」「女性成长」后面跟着「全72集」），
# 它不是类型标签，直接丢掉 —— 否则详情页的类型行会显示成「… | 全72集」。
_ORG_COUNT_TAG_RE = re.compile(r"^(?:全|共|更新至|已更新至)?\s*\d+\s*集$")


def _clean_tags(values: Any) -> List[str]:
    """清洗类型标签：去空白、去重、丢掉站点误塞进来的集数说明。"""
    tags: List[str] = []
    for value in values if isinstance(values, (list, tuple)) else [values]:
        tag = _clean(value)
        if not tag or _ORG_COUNT_TAG_RE.match(tag):
            continue
        if tag not in tags:
            tags.append(tag)
    return tags


def _org_card_regions(source: str) -> List[str]:
    """把页面切成「一张卡」的区间（逐字，不丢字段）。

    有卡片外壳标记（目录页 / 精选页）时按外壳切：一整张卡 = 海报锚 + 标题锚 +
    热度 + 标签，三处字段都在同一块里；没有外壳标记时退回「锚 + 锚前兄弟 ``<img>``」
    的切法（榜单页）。
    """
    if not source:
        return []

    marks = [match.start() for match in re.finditer(re.escape(_ORG_CARD_BLOCK_MARK), source)]
    if marks:
        regions = []
        for index, start in enumerate(marks):
            # 精确止于下一张卡的开头，避免把相邻作品的字段混进来
            end = (
                marks[index + 1]
                if index + 1 < len(marks)
                else min(len(source), start + _ORG_CARD_SPAN)
            )
            regions.append(source[start:end])
        return regions

    regions: List[str] = []
    anchors = list(_ORG_CARD_RE.finditer(source))
    seen: set = set()
    previous_end = 0
    for index, match in enumerate(anchors):
        native_id = match.group("id")
        if native_id in seen:
            continue
        seen.add(native_id)
        # 封面在**锚之前**的兄弟节点里（榜单页版式）。取「上一张卡的锚之后 → 本锚
        # 之前」这段窗口里的**最后一张** <img：既不回捞到上卡的封面，也不会错拿到
        # 页头 logo（窗口下界就是上卡锚的结尾）。
        window = source[previous_end: match.start()]
        images = list(_ORG_IMG_RE.finditer(window))
        start = previous_end + images[-1].start() if images else match.start()
        next_start = None
        for later in anchors[index + 1:]:
            if later.group("id") not in seen:
                next_start = later.start()
                break
        end = min(next_start or (match.end() + _ORG_CARD_SPAN), start + _ORG_CARD_SPAN)
        regions.append(source[start:end])
        previous_end = match.end()
    return regions


def parse_org_cards(html: str, domain: str = ORG_DEFAULT_DOMAIN) -> List[Dict[str, Any]]:
    """解析 ``.org`` 目录页 / 精选页 / 榜单页的作品卡，返回 ``id + 片名 + 海报``。

    三种页面共用同一套 ``href`` 形态，所以一个函数通吃；补充字段（真人/AI、状态角标、
    评分、集数、系列季、热度、播放、标签）能取到就带上，取不到留空 —— 榜单页没有这些
    字段，它们是**可选**的，任何调用方都不能依赖它们一定存在。
    """
    results: List[Dict[str, Any]] = []
    seen: set = set()
    for region in _org_card_regions(html or ""):
        anchor = _ORG_CARD_RE.search(region)
        if anchor is None:
            continue
        native_id = anchor.group("id")
        if native_id in seen:
            continue
        body = anchor.group("body") or ""

        # 标题：优先锚内 <img alt>（目录页 / 精选页），否则取锚文本（榜单页）
        alt = _ORG_CARD_ALT_RE.search(body)
        title = _clean(alt.group("alt")) if alt else ""
        if not title:
            title = _clean(_strip_tags(body))
        if not title:
            continue
        seen.add(native_id)

        # 封面：锚内 <img src> 优先，否则取锚之前的最近一张图（榜单页版式）
        src = _ORG_CARD_SRC_RE.search(body)
        if src is None:
            head = list(_ORG_IMG_RE.finditer(region[: anchor.start()]))
            if head:
                src = head[-1]

        record: Dict[str, Any] = {
            "media_id": f"org:{native_id}",
            "native_id": native_id,
            "title": title,
            "poster": _normalize_image(src.group("src")) if src else "",
            "url": f"{domain.rstrip('/')}/zh-Hans/drama/{native_id}",
        }
        record.update(_parse_org_card_extras(region))
        results.append(record)
    return results


def _parse_org_card_extras(region: str) -> Dict[str, Any]:
    """从**整张卡**的 HTML 里取「真人/AI、状态、评分、集数、系列季、热度、播放、标签」。

    这些字段是**锦上添花**：站点在不同版式下渲染的字段并不一致（榜单页就没有），
    所以每个字段都独立判空，取不到就整条不带，绝不让缺失变成异常。
    """
    extras: Dict[str, Any] = {}
    if not region:
        return extras

    kind = _ORG_KIND_RE.search(region)
    if kind and _clean(kind.group("kind")):
        extras["kind"] = _clean(kind.group("kind"))

    badge = _ORG_BADGE_RE.search(region)
    if badge:
        text = _clean(_strip_tags(badge.group("body")))
        if text:
            extras["badge"] = text

    rating = _ORG_RATING_RE.search(region)
    if rating:
        extras["rating"] = _clean(rating.group("rating"))

    episodes = _ORG_EPISODES_RE.search(region)
    if episodes:
        extras["episode_count"] = int(episodes.group("count"))

    series = _ORG_SERIES_RE.search(region)
    if series and _clean(series.group("series")):
        extras["series"] = _clean(series.group("series"))
        season = _ORG_SEASON_RE.search(region)
        if season:
            extras["season"] = int(season.group("season"))

    tags = _clean_tags([match.group("tag") for match in _ORG_TAG_RE.finditer(region)])
    if tags:
        extras["tags"] = tags

    heat = _ORG_HEAT_RE.search(region)
    if heat:
        amount = _parse_wannum(heat.group("value"))
        if amount is not None:
            extras["heat"] = amount

    plays = _ORG_PLAYS_RE.search(region)
    if plays:
        amount = _parse_wannum(plays.group("value"))
        if amount is not None:
            extras["play_count"] = amount

    return extras


# ── ``.org`` 详情页解析 ───────────────────────────────────────────

_ORG_LD_RE = re.compile(
    r'<script[^>]*application/ld\+json[^>]*>(?P<body>.*?)</script>', re.S
)
_ORG_H1_RE = re.compile(r"<h1[^>]*>(?P<title>.*?)</h1>", re.S)
_ORG_SUMMARY_RE = re.compile(r"剧情简介</h2>\s*<p[^>]*>(?P<overview>.*?)</p>", re.S)
# 形如 <span class="text-gray-500">集数：</span><span class="text-gray-900 …">106集</span>
_ORG_FIELD_RE = re.compile(
    r'<span class="text-gray-500">\s*(?P<label>[^<：:]+?)\s*[：:]\s*</span>\s*'
    r'<span class="text-gray-900[^"]*">\s*(?P<value>.*?)\s*</span>',
    re.S,
)
_ORG_STAT_RE = re.compile(
    r'<span class="font-medium">\s*(?P<value>[^<]+?)\s*</span>\s*(?P<label>播放|收藏|评分)',
    re.S,
)
# 演员阵容：<a href="…/zh-Hans/actor/{id}"> 头像锚 + 姓名锚，同一 id 出现两次
_ORG_ACTOR_LINK_RE = re.compile(
    r'<a\b[^>]*href="(?:https?://[^"]*?)?/zh-Hans/actor/(?P<id>\d+)"', re.S
)
_ORG_ACTOR_NAME_RE = re.compile(
    r'<a\b[^>]*href="[^"]*/zh-Hans/actor/\d+"[^>]*class="[^"]*text-blue-600[^"]*"[^>]*>'
    r"\s*(?P<name>[^<]+?)\s*</a>",
    re.S,
)
_ORG_ACTOR_ROLE_RE = re.compile(
    r"<span[^>]*>\s*饰\s*</span>\s*<span[^>]*>\s*(?P<role>[^<]*?)\s*</span>", re.S
)
_ORG_ACTOR_KIND_RE = re.compile(r">\s*(?P<kind>主演|配角|客串|特别出演)\s*<")
_ORG_ACTOR_ALT_RE = re.compile(r'alt="(?P<alt>[^"]*)"')
_ORG_ACTOR_WINDOW = 1500
# 「饰 XXX」到「主演 / 配角」之间隔着一条 HTML 注释和一整段 span 属性（实测约 450
# 字符），窗口给小了会取不到主次 —— 但也不能无限大，否则会把下一个演员的标签算进来
# （实测相邻演员相距约 1900 字符，900 是安全值）。
_ORG_ACTOR_KIND_SPAN = 900
# 剧照：<div id="drama-photo-gallery" …> 内每张图的 <a href> 就是原图
_ORG_GALLERY_MARK = 'id="drama-photo-gallery"'
_ORG_GALLERY_SRC_RE = re.compile(r'href="(?P<src>https?://[^"]+\.(?:jpg|jpeg|png|webp))"', re.S)
_ORG_GALLERY_WINDOW = 6000


def _org_html_body(html: str) -> str:
    """去掉 JSON-LD 脚本块后的正文。

    JSON-LD 里也有 ``/zh-Hans/actor/{id}`` 形式的 URL，不去掉会让按锚点定位的
    HTML 解析把 JSON-LD 误当成演员卡（窗口落在 JSON 里，取不到「饰 XXX」）。
    """
    return _ORG_LD_RE.sub(" ", html or "")


def _org_json_ld(html: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    series: Dict[str, Any] = {}
    page: Dict[str, Any] = {}
    for match in _ORG_LD_RE.finditer(html or ""):
        try:
            payload = json.loads(match.group("body"))
        except (ValueError, TypeError):
            continue
        graph = payload.get("@graph") if isinstance(payload, dict) else None
        nodes = graph if isinstance(graph, list) else [payload]
        for node in nodes:
            if not isinstance(node, dict):
                continue
            if node.get("@type") == "TVSeries":
                series = node
            elif node.get("@type") == "WebPage":
                page = node
    return series, page


def _org_cast_from_json_ld(series: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """从 ``TVSeries.actor``（``PerformanceRole`` 数组）取演员阵容。

    这是本站**最稳**的演员来源：字段规整，且 ``characterName`` 直接给出饰演角色。
    """
    roles = (series or {}).get("actor")
    if not isinstance(roles, list):
        return []
    actors: List[Dict[str, Any]] = []
    for role in roles:
        if not isinstance(role, dict):
            continue
        person = role.get("actor") if isinstance(role.get("actor"), dict) else role
        name = _clean(person.get("name"))
        if not name:
            continue
        actor_id = ""
        found = re.search(r"/zh-Hans/actor/(\d+)", _clean(person.get("url") or person.get("@id")))
        if found:
            actor_id = found.group(1)
        actors.append(
            {
                "id": actor_id,
                "name": name,
                "character": _clean(role.get("characterName")),
                "profile_path": _normalize_image(person.get("image")),
            }
        )
    return actors


def _org_actor_kinds(html: str) -> Dict[str, str]:
    """从 HTML 演员卡里取「主演 / 配角」标签，键为演员 ID。

    JSON-LD 没有主次之分，这个信息只在正文里。
    """
    body = _org_html_body(html)
    kinds: Dict[str, str] = {}
    for match in _ORG_ACTOR_LINK_RE.finditer(body):
        actor_id = match.group("id")
        if actor_id in kinds:
            continue
        window = body[match.start(): match.start() + _ORG_ACTOR_WINDOW]
        role_match = _ORG_ACTOR_ROLE_RE.search(window)
        if not role_match:
            continue
        # 只在「饰 XXX」之后的一小段里找，避免把下一个演员的标签算进来
        tail = window[role_match.end(): role_match.end() + _ORG_ACTOR_KIND_SPAN]
        kind_match = _ORG_ACTOR_KIND_RE.search(tail)
        if kind_match:
            kinds[actor_id] = _clean(kind_match.group("kind"))
    return kinds


def _org_cast_from_html(html: str) -> List[Dict[str, Any]]:
    """从 HTML「演员阵容」区块取演员阵容（JSON-LD 缺失时的兜底）。

    每个演员在标记里有两个同 ID 的 ``<a href="…/zh-Hans/actor/{id}">``：一个是头像、
    一个是姓名，按 id 去重即可。该区块在「这部作品没有录入角色」时整块不渲染 ——
    那是**作品级**差异，不是站点能力缺失（早期只读 JSON-LD 的 name/description
    就下过「本站没有演员表」的结论，实测证明是错的）。
    """
    body = _org_html_body(html)
    actors: List[Dict[str, Any]] = []
    seen: set = set()
    for match in _ORG_ACTOR_LINK_RE.finditer(body):
        actor_id = match.group("id")
        if actor_id in seen:
            continue
        window = body[match.start(): match.start() + _ORG_ACTOR_WINDOW]

        name = ""
        name_match = _ORG_ACTOR_NAME_RE.search(window)
        if name_match:
            name = _clean(name_match.group("name"))
        if not name:
            alt = _ORG_ACTOR_ALT_RE.search(window)
            if alt:
                name = _clean(alt.group("alt"))
        if not name:
            continue
        seen.add(actor_id)

        role = ""
        role_match = _ORG_ACTOR_ROLE_RE.search(window)
        if role_match:
            role = _clean(role_match.group("role"))

        avatar = ""
        src = _ORG_CARD_SRC_RE.search(window)
        if src:
            avatar = _normalize_image(src.group("src"))

        actors.append(
            {
                "id": actor_id,
                "name": name,
                "character": role,
                "profile_path": avatar,
            }
        )
    return actors


def parse_org_cast(
    html: str,
    series: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """解析演员阵容：JSON-LD 优先，HTML 兜底，再用 HTML 补「主演 / 配角」。"""
    source = html or ""
    actors = _org_cast_from_json_ld(series) or _org_cast_from_html(source)
    if not actors:
        return []
    kinds = _org_actor_kinds(source)
    for actor in actors:
        actor["kind"] = kinds.get(actor.get("id", ""), actor.get("kind", ""))
    return actors


def parse_org_gallery(html: str) -> List[str]:
    """解析剧照区块，返回原图直链（该站 PC / 移动端都只渲染 4 张）。"""
    source = html or ""
    mark = source.find(_ORG_GALLERY_MARK)
    if mark < 0:
        return []
    window = source[mark: mark + _ORG_GALLERY_WINDOW]
    stills: List[str] = []
    for match in _ORG_GALLERY_SRC_RE.finditer(window):
        src = _normalize_image(match.group("src"))
        if src and src not in stills:
            stills.append(src)
    return stills


def parse_org_detail(html: str, native_id: str, domain: str = ORG_DEFAULT_DOMAIN) -> Dict[str, Any]:
    """解析 ``.org`` 作品详情页。

    优先级：JSON-LD（字段规整、跨版本稳） → 页面正文（演员阵容 / 剧照 / 播放收藏
    这些 JSON-LD 里根本没有的内容只能从 HTML 取；其余字段作兜底）。
    """
    source = html or ""
    data: Dict[str, Any] = {
        "media_id": f"org:{native_id}",
        "native_id": native_id,
        "url": f"{domain.rstrip('/')}/zh-Hans/drama/{native_id}",
    }

    series, page = _org_json_ld(source)

    data["title"] = _clean(series.get("name") or page.get("name"))
    if not data["title"]:
        h1 = _ORG_H1_RE.search(source)
        if h1:
            data["title"] = _strip_tags(h1.group("title"))

    data["overview"] = _clean(series.get("description") or page.get("description"))
    if not data["overview"]:
        summary = _ORG_SUMMARY_RE.search(source)
        if summary:
            data["overview"] = _strip_tags(summary.group("overview"))

    cover = ""
    primary = page.get("primaryImageOfPage")
    if isinstance(primary, dict):
        cover = _normalize_image(primary.get("url"))
    if not cover:
        image = series.get("image")
        cover = _normalize_image(image if isinstance(image, str) else "")
    data["poster"] = cover

    data["episode_count"] = _parse_int(series.get("numberOfEpisodes"))
    data["duration_minutes"] = _parse_duration_minutes(series.get("duration"))

    published = _clean(series.get("datePublished"))
    if published:
        data["release_date"] = published
        data["year"] = _parse_year(published)

    genre = series.get("genre")
    if _has_value(genre):
        data["tags"] = _clean_tags(genre)

    holder = series.get("copyrightHolder")
    if isinstance(holder, dict):
        data["studio"] = _clean(holder.get("name"))

    # 评分：结构化数据里的 aggregateRating 优先（站上多数作品没有这一项）
    aggregate = series.get("aggregateRating")
    if isinstance(aggregate, dict):
        score = _clean(aggregate.get("ratingValue"))
    elif isinstance(aggregate, (str, int, float)):
        score = _clean(aggregate)
    else:
        score = ""
    if score:
        data["rating"] = score

    # 正文「标签：值」区块：补齐 JSON-LD 缺的字段
    for match in _ORG_FIELD_RE.finditer(source):
        label = _clean(match.group("label"))
        value = _strip_tags(match.group("value"))
        if not value:
            continue
        if label == "集数" and not data.get("episode_count"):
            data["episode_count"] = _parse_int(value)
        elif label == "时长" and not data.get("duration_minutes"):
            data["duration_minutes"] = _parse_duration_minutes(value)
        elif label == "首播时间" and not data.get("release_date"):
            data["release_date"] = value
            data["year"] = _parse_year(value)
        elif label == "出品方" and not data.get("studio"):
            data["studio"] = value
        elif label in ("类型", "标签") and not data.get("tags"):
            data["tags"] = _clean_tags(re.split(r"[，,、/\s]+", value))

    # 播放 / 收藏 / 评分（JSON-LD 里没有）
    for match in _ORG_STAT_RE.finditer(source):
        label = _clean(match.group("label"))
        text = match.group("value").replace(",", "")
        if label == "播放":
            data["play_count"] = _parse_wannum(text)
        elif label == "收藏":
            data["favorite_count"] = _parse_wannum(text)
        elif label == "评分" and not _has_value(data.get("rating")):
            # 详情页的「评分」与卡片上的星星是同一个分值。站点无值时整个统计项不渲染，
            # 所以这里取不到就留空，绝不塞 0 —— 0 分会被宿主当成「有评分」显示出来。
            score = _clean(text)
            if score:
                data["rating"] = score

    # 剧照 → 背景图
    stills = parse_org_gallery(source)
    if stills:
        data["stills"] = stills
        data["backdrop"] = stills[0]

    data["actors"] = parse_org_cast(source, series)
    data.setdefault("tags", [])
    return data


# ── ``.org`` 演员页解析 ───────────────────────────────────────────
# ⚠️ 必须抓 **zh-Hans** 路径：不带语言前缀访问会被 301 到 zh-Hant，页面里的作品链接
# 随之变成 ``/zh-Hant/drama/<id>``，而卡片正则只认 ``/zh-Hans/drama/`` ⇒ 静默解析出
# 0 部作品（资料字段照常正确，所以极难发现）。

_ORG_PERSON_TITLE_RE = re.compile(r"<title>(?P<title>.*?)</title>", re.S)


def _org_person_json_ld(html: str) -> Dict[str, Any]:
    """从页面里抽出 ``Person`` JSON-LD 节点（演员页有，作品详情页没有）。"""
    for match in _ORG_LD_RE.finditer(html or ""):
        try:
            payload = json.loads(match.group("body"))
        except (ValueError, TypeError):
            continue
        graph = payload.get("@graph") if isinstance(payload, dict) else None
        nodes = graph if isinstance(graph, list) else [payload]
        for node in nodes:
            if isinstance(node, dict) and node.get("@type") == "Person":
                return node
    return {}


def parse_org_actor(
    html: str,
    actor_id: str,
    domain: str = ORG_DEFAULT_DOMAIN,
) -> Dict[str, Any]:
    """解析 ``.org`` 演员页，返回演员档案 + 全部作品 + 合作演员。

    :param html: 演员页正文（必须是 ``/zh-Hans/actor/<id>`` 的响应，见上方警告）
    :param actor_id: 站点演员 ID（裸数字）
    :param domain: 站点域名
    :return: ``{"actor_id", "media_id", "name", "bio", "profile", "job_title",
        "gender", "nationality", "url", "works": [...], "coactors": [...]}``
    """
    source = html or ""
    person = _org_person_json_ld(source)
    data: Dict[str, Any] = {
        "actor_id": actor_id,
        "media_id": f"{ACTOR_ID_PREFIX}:{actor_id}",
        "url": f"{domain.rstrip('/')}{ACTOR_PATH.format(id=actor_id)}",
        "name": _clean(person.get("name")),
        "bio": _clean(person.get("description")),
        "profile": _normalize_image(person.get("image")),
        "job_title": _clean(person.get("jobTitle")),
        "gender": _clean(person.get("gender")),
    }

    nationality = person.get("nationality")
    if isinstance(nationality, dict):
        data["nationality"] = _clean(nationality.get("name"))
    elif _has_value(nationality):
        data["nationality"] = _clean(nationality)

    # 姓名兜底：JSON-LD 缺失时从 <title> 里剥站点后缀（「魏依珂 - 短剧演员 - 短剧百科」）
    if not data["name"]:
        title = _ORG_PERSON_TITLE_RE.search(source)
        if title:
            data["name"] = _strip_org_suffix(_strip_tags(title.group("title")))

    data["works"] = parse_org_cards(source, domain)
    data["coactors"] = parse_org_cast(source, None)
    return data


def is_cloudflare_challenge(html: str, status_code: Optional[int] = None) -> bool:
    """判断响应是否为 Cloudflare 人机校验页（而非真实内容）。

    被挡住时把它当「没拿到内容」处理即可 —— 调用方据此放弃**这一次**解析。
    """
    if status_code == 403:
        return True
    text = (html or "")[:4000]
    return "Just a moment" in text or "cf-chl" in text or "Attention Required" in text


# ── 媒体信息映射 ──────────────────────────────────────────────────


def media_source_value() -> Any:
    """返回宿主的媒体来源标识；``MediaSource`` 不可用时退回纯字符串。"""
    if MediaSource is None:  # pragma: no cover - 极端兜底
        return MEDIA_SOURCE_KEY
    try:
        return MediaSource(MEDIA_SOURCE_KEY)
    except Exception:  # pragma: no cover - 宿主枚举不接受自定义值时
        return MEDIA_SOURCE_KEY


def build_detail_facts(item: Dict[str, Any]) -> str:
    """把「评分 / 集数 / 主演」拼成一行摘要，供详情页的 ``tagline`` 位使用。

    这是**有意的补偿**，不是照抄站点字段：宿主的媒体详情页里，「评分」区与
    「演职员」区是前端按 **TMDB / 豆瓣 / Bangumi 三个来源硬编码**渲染的 —— 判定
    条件就是媒体有没有 ``tmdb_id`` / ``douban_id`` / ``bangumi_id``，自定义来源
    （本插件）无论如何都拿不到这两个位置。整页里唯一能承载这类信息的**自由文本
    位**是 ``tagline``（它渲染在「简介」标题的正上方），所以把评分与主演收进
    这一行，是让它们在详情页可见的唯一办法。``detail_facts`` 开关可以关掉它。
    """
    parts: List[str] = []
    rating = _clean(item.get("rating"))
    if rating:
        parts.append(f"评分 {rating}")
    episodes = item.get("episode_count")
    if isinstance(episodes, int) and episodes > 0:
        parts.append(f"全 {episodes} 集")
    names = [
        _clean(actor.get("name"))
        for actor in (item.get("actors") or [])
        if isinstance(actor, dict) and _clean(actor.get("name"))
    ]
    if names:
        parts.append("主演 " + "、".join(names[:3]) + (" 等" if len(names) > 3 else ""))
    return " · ".join(parts)


def build_media_info(item: Dict[str, Any], facts: bool = True) -> Any:
    """把解析结果映射成宿主 ``MediaInfo``。

    宿主对插件返回值的唯一硬要求是「能当 ``MediaInfo`` 用」，因此这里先按
    ``app.sdk.media.MediaInfo``（与 TMDB / 豆瓣模块同一个领域模型）构造；
    该模型不可用时再退到 ``app.schemas.MediaInfo``。构造完成后**重新断言**
    ``media_source`` / ``media_id`` —— ``MediaInfo.__post_init__`` 会调用
    ``resolve_media_identity``，自定义来源有被归一化掉的风险，而已装插件
    ``iqiyidiscover`` 正是用「构造后再赋值」这一姿势绕开它的。

    ``facts`` 控制是否写入那行事实摘要（见 :func:`build_detail_facts`）——
    探索页的卡片不渲染 ``tagline``，只有媒体详情页会渲染，所以由调用方按配置决定。
    """
    media_id = str(item.get("media_id") or "")
    title = _clean(item.get("title"))
    if not media_id or not title:
        return None

    rating = item.get("rating")
    try:
        vote_average = float(str(rating).strip()) if rating not in (None, "") else 0.0
    except (TypeError, ValueError):
        vote_average = 0.0

    tags = [tag for tag in (item.get("tags") or []) if tag]
    actors = [actor for actor in (item.get("actors") or []) if actor.get("name")]
    studio = _clean(item.get("studio"))
    release_date = _clean(item.get("release_date")) or None

    fields: Dict[str, Any] = {
        "media_source": media_source_value(),
        "media_id": media_id,
        "type": MediaType.TV,
        "title": title,
        "year": item.get("year") or None,
        "overview": _clean(item.get("overview")) or None,
        "tagline": (build_detail_facts(item) or None) if facts else None,
        "poster_path": _normalize_image(item.get("poster")) or None,
        "backdrop_path": _normalize_image(item.get("backdrop")) or None,
        "vote_average": vote_average,
        "release_date": release_date,
        "first_air_date": release_date,
        "number_of_episodes": item.get("episode_count"),
        "runtime": item.get("duration_minutes"),
        "genres": [{"name": tag} for tag in tags],
        "names": list(tags),
        "actors": actors,
        "production_companies": [{"name": studio}] if studio else [],
        "status": _clean(item.get("status")) or None,
        "homepage": _clean(item.get("url")) or None,
    }

    mediainfo = None
    for model in (_HostMediaInfo, _schema_media_info()):
        if model is None:
            continue
        try:
            mediainfo = model(**fields)  # type: ignore[misc]
            break
        except Exception as err:  # pragma: no cover - 字段集差异兜底
            logger.debug(f"{PLUGIN_NAME} 构造媒体信息失败（{model}）：{err}")

    if mediainfo is None:
        return None

    # __post_init__ 里的 resolve_media_identity 可能改写自定义来源，这里显式复位
    try:
        mediainfo.media_source = media_source_value()
        mediainfo.media_id = media_id
    except Exception as err:  # pragma: no cover - 只读模型兜底
        logger.debug(f"{PLUGIN_NAME} 复位媒体身份失败：{err}")
    return mediainfo


def _schema_media_info() -> Any:
    """惰性取 ``app.schemas.MediaInfo``（部分宿主版本只在这里暴露该类）。"""
    try:
        from app import schemas

        return getattr(schemas, "MediaInfo", None)
    except Exception:  # pragma: no cover - 宿主版本差异兜底
        return None


# ── 跨插件 / 外部消费的稳定载荷 ───────────────────────────────────
# 只保留标量 + 精简演员表：消费方（其它插件、脚本、外部程序）不该被宿主
# ``MediaInfo`` 的字段版本绑住，也不该在 JSON 里收到模型对象。
PUBLIC_RECORD_FIELDS = (
    "media_id",
    "native_id",
    "title",
    "year",
    "overview",
    "poster",
    "backdrop",
    "episode_count",
    "duration_minutes",
    "release_date",
    "rating",
    "heat",
    "play_count",
    "favorite_count",
    "kind",
    "badge",
    "series",
    "season",
    "tags",
    "studio",
    "url",
)
# 作品记录里「演员」条目的字段（与演员档案的 PUBLIC_ACTOR_FIELDS 是两回事）。
# ⚠️ 字段名必须与 ``_org_cast_from_json_ld`` / ``_org_cast_from_html`` 的产出逐字一致
# —— 那两处写的是 ``character`` / ``profile_path``，不是 ``role`` / ``poster``。
PUBLIC_CAST_FIELDS = ("id", "name", "character", "profile_path", "kind")


def build_public_record(item: Optional[Dict[str, Any]], origin: str = "detail") -> Dict[str, Any]:
    """把一条作品记录压成**纯 JSON** 载荷（其它插件调用的统一形状）。

    :param item: ``parse_org_detail`` / ``parse_org_cards`` 产出的记录
    :param origin: ``detail``（来自详情页，字段全）或 ``card``（来自榜单/演员页卡片，字段少）
    """
    record: Dict[str, Any] = {
        "media_source": MEDIA_SOURCE_KEY,
        "origin": origin,
        "url": "",
        "title": "",
    }
    if not item:
        return record
    for name in PUBLIC_RECORD_FIELDS:
        value = item.get(name)
        if value in (None, "", []):
            continue
        record[name] = value
    actors = [
        {key: actor.get(key) for key in PUBLIC_CAST_FIELDS if actor.get(key)}
        for actor in (item.get("actors") or [])
        if actor.get("name")
    ]
    if actors:
        record["actors"] = actors
    return record


# 演员档案对外 JSON 里带的字段（顺序即展示顺序）
PUBLIC_ACTOR_FIELDS: Tuple[str, ...] = (
    "actor_id",
    "media_id",
    "name",
    "job_title",
    "gender",
    "nationality",
    "profile",
    "bio",
    "url",
)


def build_public_actor(item: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """把一条演员档案整理成纯 JSON（跨插件 / 外部脚本用）。

    作品条目复用 ``parse_org_cards`` 的输出（``media_id`` / ``title`` / ``poster`` /
    ``episode_count`` / ``rating`` / ``tags`` …），这里只补一个 ``works_count``，
    免得消费方还要自己数。

    :param item: ``parse_org_actor`` 的结果
    :return: 无空值的纯 JSON 字典；``item`` 为空时返回空字典
    """
    if not item:
        return {}
    record: Dict[str, Any] = {
        name: item[name]
        for name in PUBLIC_ACTOR_FIELDS
        if _has_value(item.get(name))
    }
    works = [dict(work) for work in (item.get("works") or []) if work.get("title")]
    record["works"] = works
    record["works_count"] = len(works)
    # 合作演员来自 ``parse_org_cast``，用的是**阵容记录**的字段名（id / character /
    # profile_path），不是演员档案的字段名 —— 套错会把内容整条清空，只剩 name。
    coactors = [
        {key: actor.get(key) for key in PUBLIC_CAST_FIELDS if _has_value(actor.get(key))}
        for actor in (item.get("coactors") or [])
        if actor.get("name")
    ]
    if coactors:
        record["coactors"] = coactors
    return record


# ── 插件主体 ──────────────────────────────────────────────────────


class ShortDramaBaikeSource(_PluginBase):
    """把「短剧百科」注册为 MoviePilot 的媒体数据源。"""

    plugin_name = PLUGIN_NAME
    plugin_desc = (
        "把「短剧百科」注册为 MoviePilot 的媒体数据源（与 TMDB / 豆瓣同级）："
        "为短剧提供片名检索与详情识别，补齐 TMDB、豆瓣上没有条目的短剧。"
    )
    plugin_icon = PLUGIN_ICON
    plugin_version = PLUGIN_VERSION
    plugin_author = "m215owen"
    author_url = "https://github.com/m215owen"
    plugin_config_prefix = "shortdramabaikesource_"
    plugin_order = 60
    auth_level = 1

    # ── 运行配置 ──
    _enabled: bool = False
    _domain: str = ORG_DEFAULT_DOMAIN
    _search_in_global: bool = True
    _timeout: int = DEFAULT_TIMEOUT
    _cache_ttl: int = DEFAULT_CACHE_TTL
    # 站外索引检索：站内检索过不了 Cloudflare，改问搜索引擎要详情页 ID（见 _search_via_web_index）
    _web_index_search: bool = True
    _web_index_backend: str = DEFAULT_WEB_INDEX_BACKEND
    _proxy: bool = False
    # 详情页事实摘要行（评分 · 集数 · 主演）：宿主详情页没有给自定义来源留位置，
    # 只能借 tagline 位承载，见 build_detail_facts()
    _detail_facts: bool = True

    # ── 运行时状态（由 init_plugin 重建，保证可重复初始化） ──
    _cache: Dict[str, Tuple[float, Any]] = {}
    _cache_lock = threading.RLock()
    # 站外索引检索的节流时间戳 —— 这是**搜索引擎**的礼貌间隔，与站点闸门无关
    _web_index_last_at: float = 0.0
    _web_index_lock = threading.Lock()

    # ── 生命周期 ──────────────────────────────────────────────────

    def init_plugin(self, config: Optional[Dict[str, Any]] = None) -> None:
        """按配置重建运行状态。"""
        config = config or {}
        self._enabled = bool(config.get("enabled"))
        self._domain = self._as_domain(config.get("domain"), ORG_DEFAULT_DOMAIN)
        self._search_in_global = self._as_bool(config.get("search_in_global"), True)
        self._timeout = self._as_range(config.get("timeout"), DEFAULT_TIMEOUT, 5, 120)
        self._cache_ttl = self._as_range(config.get("cache_ttl"), DEFAULT_CACHE_TTL, 0, 2592000)
        # 站外索引检索：默认开启 —— 它是「按片名 / 按演员找 ID」唯一可用的通道（站内检索过不了 CF）
        self._web_index_search = self._as_bool(config.get("web_index_search"), True)
        self._web_index_backend = self._as_choice(
            config.get("web_index_backend"), DEFAULT_WEB_INDEX_BACKEND, WEB_INDEX_BACKENDS
        )
        self._proxy = bool(config.get("proxy"))
        self._detail_facts = self._as_bool(config.get("detail_facts"), True)

        # ⚠️ 运行时容器必须在**每个实例**上重新绑定。它们是类属性，若只原地 clear()
        # 或干脆不动，同一进程里被重建的插件实例（宿主 reconcile 会反复重建）会共用
        # 同一批 dict —— 上一实例的缓存会漏进新实例。这里一次性换成新对象。
        self._cache = {}
        self._web_index_last_at = 0.0

        self._register_image_domains()
        logger.info(
            f"{PLUGIN_NAME} 已就绪：启用={self._enabled} 域名={self._domain} "
            f"全局检索={self._search_in_global}"
            f"｜站外索引={'开' if self._web_index_search else '关'}"
            f"（后端 {self._web_index_backend}）"
        )

    def get_state(self) -> bool:
        return self._enabled

    def stop_service(self) -> None:
        """停止插件：清空内存缓存。"""
        with self._cache_lock:
            self._cache.clear()

    def get_render_mode(self) -> Tuple[str, Optional[str]]:
        """声明使用 Vue 联邦远程组件渲染，产物目录为 ``dist/assets``。

        面板上要放**能回传输入的搜索框**，而宿主的 Vuetify（JSON）页面只支持静态组件树
        与「点击 → 调接口」这类无参交互，承载不了输入框，因此这里改用联邦前端：
        ``./Page`` 画详情弹窗、``./Config`` 画配置页，后端只负责给数据
        （``get_form`` 下发默认配置、``get_page`` 返回空列表）。
        """
        return "vue", "dist/assets"

    def get_service(self) -> List[Dict[str, Any]]:
        """**不注册任何后台服务**（v1.8.0 起）。

        以前这里挂着「榜单快照刷新」定时任务；榜单只服务于宿主「探索」页与片名检索的
        零请求降级，两条线都在 v1.8.0 移除 ⇒ 插件现在完全**按需**：只有面板搜索 /
        宿主识别调用时才出网，没人调用就一个请求都不发。
        """
        return []

    # ── 数据源声明（本插件的核心） ─────────────────────────────────

    def get_media_source(self) -> List[Dict[str, Any]]:
        """声明本插件提供的媒体数据源。

        ``media_types`` 只声明电视剧：短剧在 MoviePilot 里统一按电视剧处理
        （与宿主「短剧」目录、``MediaType.TV`` 的语义一致）。
        """
        return [
            {
                "name": MEDIA_SOURCE_LABEL,
                "media_source": media_source_value(),
                "media_types": [MediaType.TV],
            }
        ]

    def get_module(self) -> Dict[str, Any]:
        """把宿主模块方法名映射到本插件实现。

        方法名必须与宿主 ``run_module`` 分发的名字逐字一致；每个实现内部都会
        先判断请求是否真的点名了本来源，因此这里可以无条件挂载。

        ⚠️ 这就是「供其它插件调用」的主通道：宿主的分发器同时挂了**模块目录**与
        **插件目录**（``chain/base.py`` 里 ``module_dispatcher_factory(module_catalog=
        self.modulemanager, plugin_catalog=self.pluginmanager)``），所以任何插件
        （它们都是 ``ChainBase`` 子类）都能这样调到本插件：

            infos = self.run_module("search_medias", meta=meta, media_source="duanjubaike")
            info = self.run_module("recognize_media", media_source="duanjubaike", media_id="org:40105")

        返回的是宿主 ``MediaInfo``（与 TMDB / 豆瓣模块同一个领域模型）。若消费方不想
        依赖模型版本，走 HTTP ``GET /plugin/ShortDramaBaikeSource/recognize`` 拿纯 JSON。

        **演员数据**（``search_actors`` / ``actor_works``）走同一张表 —— 它们是本插件
        **自定义**的方法名（宿主模块合同里没有这两个名字，走 legacy 契约放行），返回
        **纯 Python 列表**，不涉及宿主模型，消费方不必做任何转换：

            works = self.run_module("actor_works", actor_id="371")
            # → [{"media_id": "org:45982", "title": "女足替补的滚烫夏天", "year": ..., ...}, …]
            actors = self.run_module("search_actors", name="魏依珂")
            # → [{"actor_id": "371", "name": "魏依珂", "media_id": "actor:371", ...}, …]
        """
        return {
            "recognize_media": self.recognize_media,
            "async_recognize_media": self.async_recognize_media,
            "search_medias": self.search_medias,
            "async_search_medias": self.async_search_medias,
            "obtain_images": self.obtain_images,
            "async_obtain_images": self.async_obtain_images,
            # 自定义能力（非宿主标准模块名，见类 docstring / 模块头「供其它插件调用」）
            "search_actors": self.search_actors,
            "async_search_actors": self.async_search_actors,
            "actor_works": self.actor_works,
            "async_actor_works": self.async_actor_works,
        }

    # ── 模块接口：识别 ────────────────────────────────────────────

    def recognize_media(
        self,
        meta: Any = None,
        mtype: Any = None,
        media_source: Any = None,
        media_id: Optional[str] = None,
        episode_group: Optional[str] = None,
        cache: bool = True,
        share_meta: Any = None,
        music_type: Optional[str] = None,
        **kwargs: Any,
    ) -> Any:
        if not self._enabled:
            return None
        # 宿主默认源是 TMDB，插件源必须只认自己，否则会劫持别人的识别
        if not self._is_our_source(media_source):
            return None

        item = self._resolve_item(media_id=media_id, meta=meta, use_cache=cache)
        if not item:
            return None
        return build_media_info(item, facts=self._detail_facts)

    async def async_recognize_media(self, *args: Any, **kwargs: Any) -> Any:
        return await asyncio.to_thread(self.recognize_media, *args, **kwargs)

    # ── 模块接口：检索 ────────────────────────────────────────────

    def search_medias(self, meta: Any = None, media_source: Any = None, **kwargs: Any) -> List[Any]:
        """按片名检索短剧作品。

        ``media_source`` 为空表示宿主的全局检索（未限定来源）。是否参与由
        ``search_in_global`` 开关决定——默认参与，这样短剧能出现在宿主搜索框里。
        """
        if not self._enabled:
            return []
        if media_source in (None, "", (), []):
            # 未限定来源 = 宿主的全局检索，是否参与由开关决定
            if not self._search_in_global:
                return []
        elif not self._is_our_source(media_source):
            return []

        query = _clean(
            getattr(meta, "name", None)
            or getattr(meta, "title", None)
            or getattr(meta, "cn_name", None)
            or ""
        )
        if not query:
            return []
        target_year = _clean(getattr(meta, "year", None)) or None

        candidates = self._search_by_title(query, target_year=target_year)
        medias: List[Any] = []
        for candidate in candidates[:MAX_CANDIDATES]:
            mediainfo = build_media_info(candidate, facts=self._detail_facts)
            if mediainfo is not None:
                medias.append(mediainfo)
        return medias

    async def async_search_medias(self, **kwargs: Any) -> List[Any]:
        return await asyncio.to_thread(self.search_medias, **kwargs)

    def obtain_images(self, mediainfo: Any = None, **kwargs: Any) -> Any:
        """补充图片。

        本插件在识别阶段就已经带上海报，通常无需额外请求；这里只做两件事：
        缺海报时按 ``media_id`` 重新解析一次，以及把海报兜底填到背景图上。
        """
        if not self._enabled or mediainfo is None:
            return mediainfo
        if not self._is_our_source(getattr(mediainfo, "media_source", None)):
            return mediainfo
        if not getattr(mediainfo, "poster_path", None):
            item = self._resolve_item(media_id=getattr(mediainfo, "media_id", None), meta=None, use_cache=True)
            if item:
                poster = _normalize_image(item.get("poster"))
                if poster:
                    try:
                        mediainfo.poster_path = poster
                    except Exception as err:  # pragma: no cover - 只读模型兜底
                        logger.debug(f"{PLUGIN_NAME} 写入海报失败：{err}")
        if not getattr(mediainfo, "backdrop_path", None) and getattr(mediainfo, "poster_path", None):
            try:
                mediainfo.backdrop_path = mediainfo.poster_path
            except Exception as err:  # pragma: no cover - 只读模型兜底
                logger.debug(f"{PLUGIN_NAME} 写入背景图失败：{err}")
        return mediainfo

    async def async_obtain_images(self, mediainfo: Any = None, **kwargs: Any) -> Any:
        return await asyncio.to_thread(self.obtain_images, mediainfo)

    # ── 身份解析 ──────────────────────────────────────────────────

    def _resolve_item(
        self,
        media_id: Optional[str],
        meta: Any,
        use_cache: bool = True,
    ) -> Optional[Dict[str, Any]]:
        media_id = _clean(media_id) or None
        if media_id:
            return self._fetch_detail(media_id, use_cache=use_cache)

        query = _clean(
            getattr(meta, "name", None)
            or getattr(meta, "title", None)
            or getattr(meta, "cn_name", None)
            or ""
        )
        if not query:
            return None
        target_year = _clean(getattr(meta, "year", None)) or None
        candidates = self._search_by_title(query, target_year=target_year)
        if not candidates:
            return None
        best = self._pick_best(candidates, query, target_year)
        if best is None:
            return None
        return self._fetch_detail(best["media_id"], use_cache=use_cache) or best

    @staticmethod
    def _native_id(media_id: str) -> str:
        """把统一媒体 ID 还原成站点作品 ID（``org:123`` 与裸 ``123`` 等价）。"""
        text = _clean(media_id)
        if not text:
            return ""
        if text.startswith("org:"):
            text = text[4:]
        elif ":" in text:
            # 老版本用过 net:<section>:<id> 复合 ID；这种值在本站不存在，直接判空
            return ""
        return text if text.isdigit() else ""

    def _fetch_detail(
        self,
        media_id: str,
        use_cache: bool = True,
    ) -> Optional[Dict[str, Any]]:
        """按统一媒体 ID 抓取详情页（带 TTL 缓存）。"""
        native_id = self._native_id(media_id)
        if not native_id:
            return None
        cache_key = f"detail:{native_id}"
        if use_cache:
            cached = self._cache_get(cache_key)
            if cached is not None:
                return cached

        html, status = self._get(f"{self._domain}{DETAIL_PATH.format(id=native_id)}")
        if not html or is_cloudflare_challenge(html, status):
            return None
        item = parse_org_detail(html, native_id, self._domain)
        if not item.get("title"):
            return None
        item["media_id"] = f"org:{native_id}"
        if use_cache:
            self._cache_set(cache_key, item)
        return item

    # ── 检索：两级降级 ────────────────────────────────────────────

    def _search_by_title(self, query: str, target_year: Optional[str] = None) -> List[Dict[str, Any]]:
        """按片名检索，返回带打分的候选（分高在前）。

        只有**一条路：站外索引** —— 搜索引擎已收录的详情页 URL
        （``site:<域名> <片名>``）。站内检索过不了 Cloudflare，这条路是它的替代品，
        见 ``_search_via_web_index``。

        ⚠️ 这里**没有全库索引**，也**不抓目录页**（目录页是站点上唯一有突发限流的路径）。
        v1.8.0 起还去掉了原来的「榜单快照」一级（那是为宿主探索页服务的，随探索页一起删除）
        —— 所以按片名找作品**完全依赖搜索引擎的收录**：召回不稳定，且基本只认完整片名。
        """
        if not self._web_index_search:
            return []
        return self._rank_candidates(self._search_via_web_index(query), query, target_year)

    @staticmethod
    def _rank_candidates(
        candidates: List[Dict[str, Any]],
        query: str,
        target_year: Optional[str],
    ) -> List[Dict[str, Any]]:
        best_by_title: Dict[str, Dict[str, Any]] = {}
        for candidate in candidates:
            score = _match_title(candidate.get("title", ""), query)
            if score <= 0:
                continue
            if target_year and candidate.get("year"):
                score += 10 if str(candidate["year"]) == str(target_year) else -15
            candidate["_score"] = score
            key = f"{_normalize_title(candidate.get('title', ''))}|{candidate.get('year') or ''}"
            current = best_by_title.get(key)
            if current is None or candidate["_score"] > current["_score"]:
                best_by_title[key] = candidate
        return sorted(best_by_title.values(), key=lambda row: row["_score"], reverse=True)

    def _domain_host(self) -> str:
        host = re.sub(r"^https?://", "", _clean(self._domain)).split("/")[0].strip().lower()
        return host[4:] if host.startswith("www.") else host

    def _site_search(self, keyword: str) -> List[Dict[str, Any]]:
        """一次站外检索的**原始结果** —— 作品与演员共用同一批行。

        引擎返回的每条结果里都有完整 URL，``/drama/<id>`` 与 ``/actor/<id>`` 同时躺在
        同一份结果里。所以「一个搜索框同时找作品和演员」**只需查一次**：查两次不仅浪费，
        还会被 ``WEB_INDEX_MIN_INTERVAL`` 挡掉第二次（结果是其中一边恒为空）。
        """
        return self._ddgs_site_search(keyword)

    def _ddgs_site_search(self, keyword: str) -> List[Dict[str, Any]]:
        """用搜索引擎的站点限定检索取原始结果（``site:<域名> <关键词>``）。

        站点的 ``/drama/search`` 是 Cloudflare **托管挑战**（``cType=managed``）：
        服务端直连恒 403，宿主浏览器仿真（cloakbrowser）**有头 / 无头都过不去**
        （2026-10-15 在 NAS 上实测：有头模式跑到 105 秒仍停在挑战页，连 ``cf_clearance``
        都没落下），所以不再尝试站内检索，改成问搜索引擎。

        返回的是**已被搜索引擎收录的 URL**（详情页 ``/drama/<id>`` 或演员页
        ``/actor/<id>``），路径末尾的数字就是站点 ID；后续抓页面走普通 HTTP ——
        详情页与演员页本身都没有挑战（实测 200 / 约 2s）。

        :param keyword: 片名或演员名
        :return: 原始结果列表（``title`` / ``href``）；不可用、过频或失败一律空列表
        """
        if _DDGS is None:
            logger.debug(f"{PLUGIN_NAME} 宿主未提供 ddgs，站外索引检索停用")
            return []
        host = self._domain_host()
        if not host:
            return []
        cache_key = f"webindex:{keyword}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return [dict(row) for row in cached]

        # 引擎不接受高频调用：两次检索挨得太近就放弃这一级（本地候选照常返回，不影响识别）
        now = time.time()
        with self._web_index_lock:
            if now - self._web_index_last_at < WEB_INDEX_MIN_INTERVAL:
                logger.debug(f"{PLUGIN_NAME} 站外索引检索过于频繁，本次跳过：{keyword}")
                return []
            self._web_index_last_at = now

        try:
            with _DDGS(timeout=WEB_INDEX_TIMEOUT) as client:
                raw = list(
                    client.text(
                        f"site:{host} {keyword}",
                        backend=self._web_index_backend,
                        max_results=WEB_INDEX_MAX_RESULTS,
                    )
                )
        except Exception as err:
            logger.debug(f"{PLUGIN_NAME} 站外索引检索失败（{keyword}）：{err}")
            return []

        results = [
            {"title": _strip_org_suffix(row.get("title") or ""),
             "href": _clean(row.get("href") or row.get("url") or "")}
            for row in raw
        ]
        # ⚠️ **失败/空结果不写缓存**：引擎偶发抽风时不该把空答案钉死一整个 TTL
        if results:
            self._cache_set(cache_key, results)
        return results

    def _search_via_web_index(
        self, query: str, rows: Optional[List[Dict[str, Any]]] = None
    ) -> List[Dict[str, Any]]:
        """按片名走站外索引，返回作品候选（``media_id`` 形如 ``org:<id>``）。

        只认 ``/drama/<数字>`` 形态的 URL —— 结果里混着演员页（``/actor/371``）、
        图集页（``/drama/37508/photos``）与外站域名，它们都拿不到作品 ID，一律剔除。

        :param rows: 已经取回的原始检索结果（``api_lookup`` 一次检索要同时喂给作品与
            演员两条解析路，避免为此多打一次引擎）；为 None 时自己查一次。
        """
        host = self._domain_host()
        results: List[Dict[str, Any]] = []
        seen: set = set()
        for row in (self._site_search(query) if rows is None else rows):
            native_id = _web_index_native_id(row.get("href") or "", host)
            title = row.get("title") or ""
            if not native_id or not title or native_id in seen:
                continue
            seen.add(native_id)
            results.append(
                {
                    "native_id": native_id,
                    "title": title,
                    "media_id": f"org:{native_id}",
                    "source": "web_index",
                }
            )
        if results:
            logger.info(f"{PLUGIN_NAME} 站外索引检索「{query}」命中 {len(results)} 部作品")
        return results

    # ── 演员数据（供其它插件查询） ────────────────────────────────
    # 演员名 → 演员 ID 走同一条站外索引：``site:<域名> <演员名>`` 的结果里就有
    # ``/actor/<id>``。

    def _search_actors_via_web_index(
        self, name: str, rows: Optional[List[Dict[str, Any]]] = None
    ) -> List[Dict[str, Any]]:
        """按演员名走站外索引，返回候选演员（按名字接近程度打分，分高在前）。

        引擎会给不少模糊匹配（搜「王石」会带出「王碩」「王思瑾」），所以这里必须
        **按名字再筛一遍**：只有 ``_match_title`` 给分 > 0 的才留下，且按分排序
        —— 调用方取第一条就是最像的那个。

        :param rows: 同 ``_search_via_web_index``：可复用一次检索的原始结果。
        """
        host = self._domain_host()
        results: List[Dict[str, Any]] = []
        seen: set = set()
        for row in (self._site_search(name) if rows is None else rows):
            actor_id = _web_index_actor_id(row.get("href") or "", host)
            actor_name = row.get("title") or ""
            if not actor_id or not actor_name or actor_id in seen:
                continue
            score = _match_title(actor_name, name)
            if score <= 0:
                continue
            seen.add(actor_id)
            results.append(
                {
                    "actor_id": actor_id,
                    "name": actor_name,
                    "media_id": f"{ACTOR_ID_PREFIX}:{actor_id}",
                    "url": f"{self._domain}{ACTOR_PATH.format(id=actor_id)}",
                    "source": "web_index",
                    "_score": score,
                }
            )
        results.sort(key=lambda row: row.get("_score", 0), reverse=True)
        if results:
            logger.info(f"{PLUGIN_NAME} 站外索引检索演员「{name}」命中 {len(results)} 位")
        return results

    def _fetch_actor(self, actor_id: str, use_cache: bool = True) -> Optional[Dict[str, Any]]:
        """抓演员页并解析（带 TTL 缓存）。

        :param actor_id: 站点演员 ID（``371``，或带前缀的 ``actor:371``）
        :return: 演员档案（``works`` 为全部作品卡片）；取不到返回 None
        """
        native_id = self._actor_native_id(actor_id)
        if not native_id:
            return None
        cache_key = f"actor:{native_id}"
        if use_cache:
            cached = self._cache_get(cache_key)
            if cached is not None:
                return cached

        html, status = self._get(f"{self._domain}{ACTOR_PATH.format(id=native_id)}")
        if not html or is_cloudflare_challenge(html, status):
            return None
        item = parse_org_actor(html, native_id, self._domain)
        if not item.get("name"):
            return None
        if use_cache:
            self._cache_set(cache_key, item)
        return item

    @staticmethod
    def _actor_native_id(actor_id: Any) -> str:
        """把演员 ID 归一成裸数字（``actor:371`` / ``371`` 等价；其它形态判空）。"""
        text = _clean(actor_id)
        if text.startswith(f"{ACTOR_ID_PREFIX}:"):
            text = text[len(ACTOR_ID_PREFIX) + 1:]
        return text if text.isdigit() else ""

    def search_actors(self, name: str = "", **kwargs: Any) -> List[Dict[str, Any]]:
        """按姓名查演员 —— **跨插件调用的主入口**（可被 ``run_module`` 分发）。

        走站外索引：``site:<域名> <姓名>`` → 结果里的 ``/actor/<id>``。**不抓演员页**，
        所以很快、只花一次搜索引擎往返；要看作品就用 ``actor_works``。

        :param name: 演员姓名（中文，可带别名）
        :param kwargs: 宿主分发器可能附带的参数（忽略）
        :return: 候选演员列表，**按名字接近程度排序**；每一项含
            ``actor_id`` / ``name`` / ``media_id``（``actor:<id>``）/ ``url`` / ``source``
        """
        query = _clean(name)
        if not query or not self._enabled:
            return []
        if not self._web_index_search:  # 站外检索被关掉时没有任何别的演员发现通道
            logger.debug(f"{PLUGIN_NAME} 站外索引已关闭，无法按姓名检索演员：{query}")
            return []
        results = self._search_actors_via_web_index(query)
        return [
            {key: value for key, value in row.items() if key != "_score"}
            for row in results[:MAX_ACTOR_CANDIDATES]
        ]

    async def async_search_actors(self, *args: Any, **kwargs: Any) -> List[Dict[str, Any]]:
        return await asyncio.to_thread(self.search_actors, *args, **kwargs)

    def actor_works(self, actor_id: str = "", name: str = "", **kwargs: Any) -> List[Dict[str, Any]]:
        """查一位演员参演的全部作品 —— **跨插件调用的主入口**。

        两种用法（``actor_id`` 优先，最省一次搜索）：

        * ``actor_works(actor_id="371")`` —— 已知站点演员 ID，直接抓演员页；
        * ``actor_works(name="魏依珂")`` —— 先走站外索引把姓名换成 ID，再抓演员页。

        :param actor_id: 站点演员 ID（``371`` 或 ``actor:371``）
        :param name: 演员姓名（没有 ID 时用）
        :param kwargs: 宿主分发器可能附带的参数（忽略）
        :return: 作品列表（**可直接当 ``MediaInfo`` 的素材**）：每一项含
            ``media_id``（``org:<作品ID>``）/ ``title`` / ``poster`` /
            ``episode_count`` / ``rating`` / ``tags`` / ``kind`` / ``url``；
            查不到返回空列表
        """
        if not self._enabled:
            return []
        native_id = self._actor_native_id(actor_id)
        if not native_id:
            query = _clean(name)
            if not query:
                return []
            candidates = self.search_actors(query)
            if not candidates:
                return []
            native_id = candidates[0]["actor_id"]
        item = self._fetch_actor(native_id)
        if not item:
            return []
        return [dict(work) for work in (item.get("works") or [])]

    async def async_actor_works(self, *args: Any, **kwargs: Any) -> List[Dict[str, Any]]:
        return await asyncio.to_thread(self.actor_works, *args, **kwargs)

    def actor_profile(self, actor_id: str = "", name: str = "") -> Dict[str, Any]:
        """查一位演员的完整档案（资料 + 全部作品 + 合作演员）。

        ``actor_works`` 只回作品列表（跨插件调用要的是能直接用的作品），
        需要姓名 / 简介 / 头像 / 性别 / 国籍这些资料时走这里。

        :return: ``{"success", "actor": {...} | None, "message"}``；``actor`` 里
            ``works`` 与 ``coactors`` 都是列表
        """
        if not self._enabled:
            return {"success": False, "message": "插件未启用", "actor": None}
        native_id = self._actor_native_id(actor_id)
        if not native_id:
            query = _clean(name)
            if not query:
                return {"success": False, "message": "需要 actor_id 或 name 之一", "actor": None}
            candidates = self.search_actors(query)
            if not candidates:
                return {
                    "success": False,
                    "message": f"没找到演员「{query}」（站外索引未收录或姓名对不上）",
                    "actor": None,
                }
            native_id = candidates[0]["actor_id"]
        item = self._fetch_actor(native_id)
        if not item:
            return {"success": False, "message": "演员页抓取失败（多半是站点风控）", "actor": None}
        return {"success": True, "message": "", "actor": build_public_actor(item)}

    # ── HTTP ──────────────────────────────────────────────────────
    #
    # ⚠️ 这里**没有闸门**（原因见模块头「限流」）：``_request`` 就是一次裸 GET，
    # 撞到 403 只影响当次调用。唯一的节流是搜索引擎侧的礼貌间隔
    # （``_ddgs_site_search`` 里的 ``WEB_INDEX_MIN_INTERVAL``），与站点无关。

    def _request(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """发起一次 GET，失败返回 None（绝不抛异常打断宿主链路）。"""
        if _RequestUtils is None:  # pragma: no cover - 极端兜底
            logger.warning(f"{PLUGIN_NAME} 宿主未提供 HTTP 入口")
            return None
        headers = {
            "User-Agent": _USER_AGENT,
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;q=0.9,"
                "image/avif,image/webp,image/apng,*/*;q=0.8,"
                "application/signed-exchange;v=b3;q=0.7"
            ),
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            # 浏览器特征头：让请求更像真实浏览器，免得站点风控收紧时把我们当脚本。
            # ⚠️ ``Accept-Encoding`` 故意不设：交给宿主 HTTP 客户端决定，它才知道环境里
            # 装了哪些解压器（乱声明 br 会解压失败）。
            "sec-ch-ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
        }
        kwargs: Dict[str, Any] = {"timeout": self._timeout}
        if self._proxy:
            proxies = getattr(_settings, "PROXY", None) if _settings is not None else None
            if proxies:
                kwargs["proxies"] = proxies
        try:
            client = _RequestUtils(headers=headers, **kwargs)
            return client.get_res(url, params=params or None)
        except Exception as err:
            logger.debug(f"{PLUGIN_NAME} 请求失败 {url}：{err}")
            return None

    def _get(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Tuple[str, Optional[int]]:
        """取页面正文与状态码。

        **不吞状态码**：本站被风控拦住时返回 403 + ``Just a moment...``，只有拿到
        状态码才分得清「被 Cloudflare 挡了」与「这个地址本来就没内容」。被挡住时只是
        这次返回空文本，不产生任何后续影响。
        """
        response = self._request(url, params=params)
        if response is None:
            return "", None
        status = getattr(response, "status_code", None)
        text = getattr(response, "text", "") or ""
        if is_cloudflare_challenge(text, status):
            logger.debug(f"{PLUGIN_NAME} {url} 撞到站点风控（status={status}）")
            return "", status
        if status is not None and status >= 400:
            logger.debug(f"{PLUGIN_NAME} {url} 返回 {status}")
            return "", status
        return text, status

    # ── 缓存 ─────────────────────────────────────────────────────

    def _cache_get(self, key: str) -> Any:
        if self._cache_ttl <= 0:
            return None
        with self._cache_lock:
            entry = self._cache.get(key)
        if not entry:
            return None
        if time.time() - entry[0] > self._cache_ttl:
            with self._cache_lock:
                self._cache.pop(key, None)
            return None
        return entry[1]

    def _cache_set(self, key: str, value: Any) -> None:
        if self._cache_ttl <= 0:
            return
        with self._cache_lock:
            self._cache[key] = (time.time(), value)
            if len(self._cache) > 512:
                oldest = sorted(self._cache.items(), key=lambda pair: pair[1][0])
                for stale_key, _ in oldest[:128]:
                    self._cache.pop(stale_key, None)

    # ── 配置页面 ──────────────────────────────────────────────────

    @staticmethod
    def _default_config() -> Dict[str, Any]:
        """默认配置（须与 init_plugin 的读取键完全一致）。"""
        return {
            "enabled": False,
            "domain": ORG_DEFAULT_DOMAIN,
            "search_in_global": True,
            "timeout": DEFAULT_TIMEOUT,
            "cache_ttl": DEFAULT_CACHE_TTL,
            "web_index_search": True,
            "web_index_backend": DEFAULT_WEB_INDEX_BACKEND,
            "proxy": False,
            "detail_facts": True,
        }

    def _current_config(self) -> Dict[str, Any]:
        """当前生效的配置（键与 ``_default_config`` 完全一致）。

        Vue 模式下配置页由远程 ``./Config`` 组件绘制，它挂载时拉 ``GET /config``
        回显，保存时 ``PUT /config``；宿主 ``get_form()`` 只把这个模型下发一次。
        """
        return {
            "enabled": bool(self._enabled),
            "domain": self._domain,
            "search_in_global": bool(self._search_in_global),
            "timeout": self._timeout,
            "cache_ttl": self._cache_ttl,
            "web_index_search": bool(self._web_index_search),
            "web_index_backend": self._web_index_backend,
            "proxy": bool(self._proxy),
            "detail_facts": bool(self._detail_facts),
        }

    def get_form(self) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Vue 模式下只下发配置模型，配置界面由远程 ``./Config`` 组件渲染。"""
        return [], self._current_config()

    def get_page(self) -> List[Dict[str, Any]]:
        """Vue 模式下详情面板由远程 ``./Page`` 组件渲染，后端返回空列表。"""
        return []

    def get_api(self) -> List[Dict[str, Any]]:
        """注册面板接口 + **跨插件消费接口**。

        ⚠️ 全部用 ``auth: "bear"``：宿主把它映射成 ``verify_token``，而那个依赖
        **同时接受 JWT（浏览器登录态）与 ``X-API-KEY``** —— 于是同一批接口既能给
        插件面板的联邦前端直接调，也能给外部脚本用，不必开两套。

        ``/recognize`` 与 ``/actor`` 是给其它插件 / 外部脚本用的稳定出口：只回纯 JSON，
        与宿主 ``MediaInfo`` 的字段版本解耦。
        """
        return [
            {
                "path": "/recognize",
                "endpoint": self.api_recognize,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "识别一部短剧（面板 + 跨插件调用）",
                "description": (
                    "给 media_id（如 org:40105）或 keyword（片名）返回一条作品记录："
                    "片名/年份/海报/集数/时长/标签/演员等，全部为纯 JSON。"
                ),
            },
            {
                "path": "/actor",
                "endpoint": self.api_actor,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "查演员档案与作品（面板 + 跨插件调用）",
                "description": (
                    "给 actor_id（如 371）或 name（演员姓名）返回演员档案："
                    "姓名/简介/头像/性别/国籍 + 全部作品（media_id/片名/海报/集数/评分/标签）"
                    "+ 合作演员，全部为纯 JSON。"
                ),
            },
            {
                "path": "/lookup",
                "endpoint": self.api_lookup,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "一个关键字，同时找作品与演员（面板搜索框）",
                "description": (
                    "面板只有一个搜索框，片名与演员名都收：这一条用**一次**站外检索同时"
                    "给出作品候选与演员候选，哪边有结果就返回哪边（两边都可能非空）。"
                    "为什么只查一次：搜索引擎侧有 3 秒最小间隔，分头调两次必然有一次被跳过。"
                ),
            },
            {
                "path": "/status",
                "endpoint": self.api_status,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "查看运行状态",
                "description": "返回站外索引配置与详情 / 演员缓存条数。",
            },
            {
                "path": "/config",
                "endpoint": self.api_get_config,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "读取当前配置（面板配置页回显）",
                "description": "返回当前生效的配置与可选项（检索后端）。",
            },
            {
                "path": "/config",
                "endpoint": self.api_update_config,
                "methods": ["PUT"],
                "auth": "bear",
                "summary": "保存配置（面板配置页）",
                "description": "接收前端提交的配置，落盘后重建运行状态。",
            },
            {
                "path": "/probe",
                "endpoint": self.api_probe,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "数据源连通性自检",
                "description": "请求 robots.txt / 详情页 / 演员页，返回状态码与解析条数。",
            },
        ]

    def api_get_config(self) -> Dict[str, Any]:
        """见 ``/config``（GET）：返回配置模型与可选项，供联邦 Config 组件回显。"""
        return {
            "success": True,
            "message": "",
            "config": self._current_config(),
            "options": self._config_options(),
        }

    def api_update_config(self, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """见 ``/config``（PUT）：保存面板提交的配置，落盘后重建运行状态。

        Vue 模式下配置页由远程组件渲染，组件只负责校验与抛事件，落盘必须由这里
        （或宿主的 ``PUT /plugin/<id>``）完成，否则面板里改的配置不会生效。

        逐键合并：``payload`` 里缺的键沿用当前生效值，**绝不静默改成别的默认值**
        （用户只翻一个开关就保存，不能把站外索引或其它开关一起改掉）。
        """
        if not isinstance(payload, dict):
            return {"success": False, "message": "请求体不是合法对象", "config": None}

        live = self._current_config()
        raw: Dict[str, Any] = {
            key: payload.get(key, live.get(key, default))
            for key, default in self._default_config().items()
        }
        # 清洗用 init_plugin 的**同一批** _as_* 与同一组上下界，保证「面板存下来的配置」
        # 与「宿主配置页存下来的配置」逐字一致。
        merged: Dict[str, Any] = {
            "enabled": bool(raw.get("enabled")),
            "domain": self._as_domain(raw.get("domain"), ORG_DEFAULT_DOMAIN),
            "search_in_global": self._as_bool(raw.get("search_in_global"), True),
            "timeout": self._as_range(raw.get("timeout"), DEFAULT_TIMEOUT, 5, 120),
            "cache_ttl": self._as_range(raw.get("cache_ttl"), DEFAULT_CACHE_TTL, 0, 2592000),
            "web_index_search": self._as_bool(raw.get("web_index_search"), True),
            "web_index_backend": self._as_choice(
                raw.get("web_index_backend"), DEFAULT_WEB_INDEX_BACKEND, WEB_INDEX_BACKENDS
            ),
            "proxy": bool(raw.get("proxy")),
            "detail_facts": self._as_bool(raw.get("detail_facts"), True),
        }

        self.update_config(merged)
        self.init_plugin(merged)
        logger.info(f"{PLUGIN_NAME} 配置已通过面板接口更新")
        return {"success": True, "message": "配置已保存", "config": self._current_config()}

    @staticmethod
    def _config_options() -> Dict[str, Any]:
        """配置页要用到的候选值（检索后端），免得前端硬编码。"""
        return {
            "web_index_backends": list(WEB_INDEX_BACKENDS),
        }


    def api_recognize(self, media_id: str = "", keyword: str = "", year: str = "") -> Dict[str, Any]:
        """见 ``/recognize``：给 ``media_id`` 或片名，回一条**纯 JSON** 作品记录。

        其它插件调用本插件有两条路（都在模块 docstring 里写了例子）：

        1. ``self.run_module("recognize_media" | "search_medias" | "obtain_images", …)``
           —— 宿主分发器会把请求送进本插件（标准姿势，返回宿主模型）；
        2. 本 HTTP 接口 —— 返回纯 JSON，插件面板与外部脚本用的是同一条。

        ``media_id`` 优先：给了就直接取详情页；只给片名则先走站外索引检索，
        取最高分那条再补详情。``origin`` 字段会说明数据来自详情页还是仅检索结果。
        """
        if not self.get_state():
            return {"success": False, "message": "插件未启用", "record": None}

        media_id = _clean(media_id)
        keyword = _clean(keyword)
        if not media_id and not keyword:
            return {"success": False, "message": "需要 media_id 或 keyword 之一", "record": None}

        item: Optional[Dict[str, Any]] = None
        origin = "detail"
        if media_id:
            item = self._fetch_detail(media_id)
        else:
            target_year = _clean(year) or None
            candidates = self._search_by_title(keyword, target_year=target_year)
            best = self._pick_best(candidates, keyword, target_year)
            if best is not None:
                detail = self._fetch_detail(best.get("media_id"))
                if detail:
                    item = detail
                else:
                    # 详情页没抓到（风控 / 网络）时退回检索结果：至少给出 ID 与片名
                    item = best
                    origin = "search"
        if not item:
            return {
                "success": False,
                "message": "未命中（片名对不上，或站外索引还没收录这部）",
                "record": None,
            }
        return {"success": True, "record": build_public_record(item, origin)}

    def api_actor(self, actor_id: str = "", name: str = "") -> Dict[str, Any]:
        """见 ``/actor``：给演员 ID 或姓名，回一份**纯 JSON** 演员档案。

        其它插件调用本插件的演员数据有两条路（模块 docstring 里有例子）：

        1. ``self.run_module("search_actors", name="魏依珂")`` 找演员，
           ``self.run_module("actor_works", actor_id="371")`` 拿作品列表
           —— 标准姿势，进程内、零序列化、返回纯 Python 列表；
        2. 本 HTTP 接口 —— 返回纯 JSON，插件面板与外部脚本用的是同一条。

        ``actor_id`` 优先（省一次搜索引擎往返）；只给姓名时先走站外索引换成 ID。
        作品列表里的 ``media_id``（``org:<作品ID>``）可直接喂给本插件的识别接口。
        """
        return self.actor_profile(actor_id=actor_id, name=name)

    def api_probe(self, keyword: str = "魏依珂") -> Dict[str, Any]:
        """连通性自检（供配置页排障用）。

        ``keyword`` 是**演员名**（走站外索引 → 演员页），默认给一个实测有档案的演员，
        这样这一段的 ``index_hits`` / ``detail.works`` 才有参考价值。
        """
        report: Dict[str, Any] = {
            "enabled": self._enabled,
            "media_source": MEDIA_SOURCE_KEY,
            "domain": self._domain,
            "media_info_model": getattr(_HostMediaInfo, "__name__", None),
            "web_index": {
                "available": _DDGS is not None,
                "enabled": self._web_index_search,
                "backend": self._web_index_backend,
            },
        }

        robots = self._request(f"{self._domain}/robots.txt")
        report["robots"] = {
            "status": getattr(robots, "status_code", None),
            "disallow_search": "drama/search" in (getattr(robots, "text", "") or ""),
        }

        # 站外索引（唯一可用的检索通道）：一个关键词同时喂作品与演员两条解析路
        rows = self._site_search(_clean(keyword)) if self._web_index_search else []
        titles = self._search_via_web_index(_clean(keyword), rows) if rows else []
        actors = self._search_actors_via_web_index(_clean(keyword), rows) if rows else []
        report["web_index_search"] = {
            "keyword": _clean(keyword),
            "raw_hits": len(rows),
            "titles": len(titles),
            "title_sample": [row.get("title") for row in titles[:5]],
        }

        # 详情页：优先拿检索命中的第一部作品当样本
        # （抓不到就退回内置的已知样本，保证这一段永远有参考值）
        sample_id = titles[0]["media_id"] if titles else PROBE_SAMPLE_MEDIA_ID
        detail = self._fetch_detail(sample_id, use_cache=False)
        report["detail"] = {
            "media_id": sample_id,
            "title": (detail or {}).get("title"),
            "actors": len((detail or {}).get("actors") or []),
            "episodes": (detail or {}).get("episode_count"),
            "stills": len((detail or {}).get("stills") or []),
        }

        # 演员通道：先按姓名走站外索引，再抓第一个命中的演员页看作品数
        report["actor"] = {
            "keyword": _clean(keyword),
            "index_hits": len(actors),
            "sample": [row.get("name") for row in actors[:5]],
        }
        if actors:
            profile = self._fetch_actor(actors[0]["actor_id"], use_cache=False)
            report["actor"]["detail"] = {
                "actor_id": actors[0]["actor_id"],
                "name": (profile or {}).get("name"),
                "works": len((profile or {}).get("works") or []),
                "coactors": len((profile or {}).get("coactors") or []),
            }

        report["ok"] = bool(
            titles
            or report["actor"]["index_hits"]
            or (report.get("detail") or {}).get("title")
        )
        return report

    def api_lookup(self, keyword: str = "", year: str = "") -> Dict[str, Any]:
        """见 ``/lookup``：面板**唯一那个搜索框**的后端 —— 一个词，两边都试。

        片名与演员名共用同一条站外索引，所以这里**只查一次**
        （``_site_search``），再把同一批原始结果分别交给作品解析与演员解析：

        * ``titles``：按片名打分的作品候选，取第一条喂 ``/recognize`` 即可；
        * ``actors``：按姓名打分的演员候选，取第一条喂 ``/actor`` 即可。

        两边都可能非空（引擎返回的结果里本来就混着作品页与演员页），哪边有结果前端
        就展示哪边；输入的是片名时 ``actors`` 多半为空，反之亦然。

        ⚠️ 只查一次不是为了省事：``WEB_INDEX_MIN_INTERVAL`` 会让相邻两次引擎检索中的
        第二次直接返回空，分头查两次必然有一边是空的。
        """
        query = _clean(keyword)
        if not query:
            return {
                "success": False,
                "message": "缺少 keyword 参数",
                "keyword": "",
                "titles": [],
                "actors": [],
            }
        if not self._web_index_search:
            return {
                "success": False,
                "message": "站外索引检索已关闭（设置里把「站外索引」打开后才能搜）",
                "keyword": query,
                "titles": [],
                "actors": [],
            }

        rows = self._site_search(query)  # 一次检索，两边共用
        titles = self._rank_candidates(
            self._search_via_web_index(query, rows), query, _clean(year) or None
        )
        actors = self._search_actors_via_web_index(query, rows)
        return {
            "success": bool(titles or actors),
            "message": ""
            if (titles or actors)
            else (
                f"没搜到「{query}」：片名与演员名都走的「搜索引擎 site: 收录」，"
                "它召回不稳定、也基本只认完整名字 —— 换成完整片名或演员全名再试一次。"
            ),
            "keyword": query,
            "titles": [
                {
                    "media_id": candidate.get("media_id"),
                    "title": candidate.get("title"),
                    "score": candidate.get("_score"),
                    "poster": candidate.get("poster"),
                    "episode_count": candidate.get("episode_count"),
                }
                for candidate in titles[:MAX_CANDIDATES]
            ],
            "actors": [
                {
                    "actor_id": row.get("actor_id"),
                    "media_id": row.get("media_id"),
                    "name": row.get("name"),
                    "score": row.get("_score"),
                }
                for row in actors[:MAX_ACTOR_CANDIDATES]
            ],
        }

    def api_status(self) -> Dict[str, Any]:
        """查看站外索引 / 缓存状态。"""
        with self._cache_lock:
            cached_detail = len([key for key in self._cache if str(key).startswith("detail:")])
            cached_actor = len([key for key in self._cache if str(key).startswith("actor:")])
        return {
            "enabled": self._enabled,
            "domain": self._domain,
            "cache": {"detail": cached_detail, "actor": cached_actor},
            "web_index": {
                "available": _DDGS is not None,
                "enabled": self._web_index_search,
                "backend": self._web_index_backend,
            },
            "actor": {
                "enabled": bool(self._enabled and self._web_index_search and _DDGS is not None),
                "max_candidates": MAX_ACTOR_CANDIDATES,
            },
        }

    # ── 内部工具 ──────────────────────────────────────────────────

    @staticmethod
    def _is_our_source(media_source: Any) -> bool:
        """判断请求是否点名了本数据源。

        ``media_source`` 在不同调用路径下可能是字符串、枚举，或它们的元组/列表
        （宿主支持一次选多个来源），因此统一拆开逐个比对。比对时接受
        ``MEDIA_SOURCE_ALIASES`` 里的任一写法 —— 其它插件按插件 ID 点名时也能命中。
        """
        if media_source in (None, "", (), []):
            return False
        values = media_source if isinstance(media_source, (list, tuple, set)) else (media_source,)
        for value in values:
            text = getattr(value, "value", value)
            if str(text or "").strip().lower() in MEDIA_SOURCE_ALIASES:
                return True
        return False

    @staticmethod
    def _pick_best(
        candidates: List[Dict[str, Any]],
        query: str,
        target_year: Optional[str],
    ) -> Optional[Dict[str, Any]]:
        """从候选里挑出最可信的一条：标题必须真的对得上。"""
        best: Optional[Dict[str, Any]] = None
        best_score = 0
        for candidate in candidates:
            score = _match_title(candidate.get("title", ""), query)
            if score <= 0:
                continue
            if target_year and candidate.get("year"):
                score += 10 if str(candidate["year"]) == str(target_year) else -15
            if score > best_score:
                best, best_score = candidate, score
        # 阈值 40：至少要有「包含关系」，宁可漏过也不能错配（短剧站同名衍生剧极多）
        return best if best_score >= 40 else None

    @staticmethod
    def _as_choice(value: Any, default: str, options: Tuple[str, ...]) -> str:
        text = _clean(value).lower()
        return text if text in options else default

    @staticmethod
    def _as_bool(value: Any, default: bool) -> bool:
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        return str(value).strip().lower() in {"1", "true", "yes", "on", "是"}

    @staticmethod
    def _as_range(value: Any, default: int, low: int, high: int) -> int:
        try:
            number = int(str(value).strip())
        except (TypeError, ValueError):
            return default
        return max(low, min(high, number))

    @staticmethod
    def _as_domain(value: Any, default: str) -> str:
        text = _clean(value) or default
        if not text.startswith(("http://", "https://")):
            text = f"https://{text}"
        return text.rstrip("/")

    @staticmethod
    def _register_image_domains() -> None:
        """把本插件的图片站登记进宿主白名单，否则图片代理会拒收。"""
        if _settings is None:  # pragma: no cover - 极端兜底
            return
        domains = getattr(_settings, "SECURITY_IMAGE_DOMAINS", None)
        if not isinstance(domains, list):
            return
        for domain in IMAGE_DOMAINS:
            if domain not in domains:
                domains.append(domain)
