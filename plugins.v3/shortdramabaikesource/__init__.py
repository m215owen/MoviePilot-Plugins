"""短剧百科数据源（MoviePilot V3 插件后端）。

把「短剧百科」（``duanjubaike.org``）包装成 MoviePilot 的一等媒体数据源 —— 与
TMDB / 豆瓣 / Bangumi 在宿主里同级，而不是另起一套私有链路。宿主、其它插件、
探索页、识别刮削都能直接选它。

为什么需要它
------------
短剧在 TMDB / 豆瓣上大量没有条目，宿主识别器因此建不起媒体身份（本机实例已实证：
站点搜索能命中剧名，但 ``media_info`` 全为 null）。本插件补的正是这一段空白。

宿主契约（V3.1.3 源码实证）
---------------------------
1. **扩展点是官方的**：插件基类 ``app.sdk.plugin._PluginBase`` 提供
   ``get_media_source()``（声明数据源：``name`` / ``media_source`` / ``media_types``）
   与 ``get_module()``（把宿主模块方法名映射到插件实现）。宿主
   ``GET /api/v1/media/source`` 会把本插件声明的来源与内置来源 **合并去重**后下发。
2. **来源标识不是封闭枚举**：``MediaSource("duanjubaike")`` 可直接构造。
   已装插件 ``iqiyidiscover``（``MediaSource("iqiyi")``）与 ``lunatvsource``
   （``PLUGIN_MEDIA_SOURCE = "lunatv"``）为同等先例。
3. **本插件实现的模块方法**（宿主 ``run_module`` 分发的名字）：
   ``recognize_media`` / ``async_recognize_media``、``search_medias`` /
   ``async_search_medias``、``obtain_images`` / ``async_obtain_images``。
   签名照 ``app/chain/media/contract.py`` 的静态合同，一个字都不能改。
4. **默认视频识别源是硬编码的** ``MediaSource.TMDB``（``app/chain/media/facade.py:49``）
   ⇒ 本插件**不会**自动成为全局兜底。因此 ``media_source`` 不匹配时**必须返回
   None**，绝不能劫持其它来源的识别。
5. **图片域名要登记**：宿主的图片代理只放行 ``settings.SECURITY_IMAGE_DOMAINS``
   内的域名，插件自带的图片站必须在 ``init_plugin`` 里补进去（照 ``iqiyidiscover``）。

站点能力边界（实测 2026-10-14，全部为 ``.org`` 单站）
-----------------------------------------------------
======================  ==========================================================
``/zh-Hans/drama/{id}`` 详情页：JSON-LD（``TVSeries`` + ``PerformanceRole`` 演员，
                        带 ``characterName``）+ HTML（演员阵容、剧照、播放/收藏、
                        集数/时长/首播时间/出品方）。**最可靠的一条路**。
``/zh-Hans/drama/list`` **全量目录**：``?page=N``，30 部/页，站内自述「共 1879 页」
                        ⇒ 全库约 5.6 万部。卡片自带海报、片名、真人/AI 角标、状态角标、
                        评分、系列季、集数、热度/播放/收藏、标签。
``/zh-Hans/drama``     首页式**精选页**：固定 30 条 + 轮播（``?page=N`` 无效，
                        实测 page=2/3/9999 内容一致 ⇒ 该页**不分页**）。
``/zh-Hans/top/{key}`` 17 个榜单（``hot`` / ``new`` / ``celebrity`` / ``comic-hot`` /
                        ``hot-*`` 系列 / ``search``）：**数量固定、不分页**。
``/zh-Hans/drama/search`` 站内检索：**Cloudflare JS 挑战**，服务端直连恒 403
                        （正文是 ``Just a moment...``）；``/drama/list?q=`` 会 301
                        跳到这里，``?keyword=`` 挂在目录页上不做服务端过滤。
``robots.txt``         ``Disallow`` 全部 ``/search``（drama/actor/director/writer/
                        producer）与 ``/auth``，并声明 ``Sitemap``。
``sitemap.xml``        sitemapindex：61 个 ``sitemap-dramas-N.xml.gz``（+actors /
                        producers），只有 ID 没有片名。
======================  ==========================================================

**配额（实测，这是本插件设计的核心约束）**：站点的 Cloudflare 风控**按 IP 计**，
无论普通 HTTP 还是宿主浏览器都一样。实测以 **1.5 秒**间隔连抓，第 6 次即 403；
把间隔放宽到 **10 秒**，**仍然是第 6 次** 403 —— 说明它卡的是「一个窗口内几次」，
不是「每秒几次」。冷却数分钟后恢复。⇒ 全量目录抓取**必须**做成「小步 + 冷却 +
断点续爬」的后台任务，且**必须给交互式识别留额度**，绝不能在一次识别调用里翻页。

因此本插件用一个**滚动窗口配额闸门**（``_take_slot``）管住所有出站请求：

* 窗口 ``quota_window_minutes``（默认 5 分钟）内最多 ``quota_max_requests`` 次
  （默认 5 次，即实测值）；
* 后台任务（索引 / 榜单）多留一个额度（``reserve=1``），**把最后的额度让给
  识别与检索** —— 否则后台把额度吃光，用户点一次识别就直接撞 403；
* 真撞上 403 时进冷却（``cooldown_minutes``），期间所有请求短路，
  免得反复试错把 IP 拖进更长的封禁。

检索是**三级**的，逐级降级：

1. **本地目录索引**（主力，见 ``_index``）：后台任务按配额一小步一小步地把
   ``/zh-Hans/drama/list`` 抓成本地索引并持久化，检索时在本地做片名匹配。
   这是唯一能在配额内做到「全库片名检索」的路子。
2. **榜单快照**（``_top_cache``）：17 个榜单的最近快照，覆盖最新与热门。
3. **实时目录扫描**（``scan_pages``）：实在没有索引时，现场抓目录前 N 页做匹配。

统一媒体身份
------------
``media_source`` 恒为 ``"duanjubaike"``，``media_id`` 形如 ``org:<id>``；裸数字 ID
也接受（等价于 ``org:<id>``）。复合 ID 在宿主里有先例：豆瓣音乐是
``album_id:track_number``。

供其它插件调用（本插件同时是「短剧识别服务」）
---------------------------------------------
本插件的定位是**只提供数据源**，所以识别能力必须能被别人直接用掉。三条通道：

1. **宿主模块分发（首选，进程内、零序列化）**。宿主的分发器同时挂了模块目录与
   **插件目录**（``app/chain/base.py``: ``module_dispatcher_factory(module_catalog=
   self.modulemanager, plugin_catalog=self.pluginmanager, …)``），而每个插件都是
   ``ChainBase`` 子类 ⇒ 其它插件直接：

       infos = self.run_module("search_medias", meta=meta, media_source="duanjubaike")
       info  = self.run_module("recognize_media", media_source="duanjubaike",
                               media_id="org:40105")

   ``media_source`` 可写 ``duanjubaike`` / ``shortdramabaike`` /
   ``shortdramabaikesource`` 任一（见 ``MEDIA_SOURCE_ALIASES``）。返回值是宿主
   ``MediaInfo``，与 TMDB / 豆瓣模块同一个领域模型。

2. **HTTP 纯 JSON 出口**：``GET /api/v1/plugin/ShortDramaBaikeSource/recognize``
   （``media_id`` 或 ``keyword`` + 可选 ``year``）。给不想被 ``MediaInfo`` 字段
   版本绑住的脚本 / 外部程序用，形状见 ``build_public_record``。

3. **智能体工具** ``short_drama_identify``（``get_agent_tools``），供 AI 智能体用。

4. **宿主「探索」页的来源**：监听宿主广播的 ``ChainEventType.DiscoverSource``，
   把「短剧百科」登记成一个探索来源（``DiscoverMediaSource``，``api_path`` 指向本插件
   的 ``/explore``）。⚠️ 探索页**只读本地**（榜单快照 + 目录索引），零网络请求 ——
   用户怎么翻页都不会消耗站点配额。要看到更多榜单，在配置里勾「榜单快照范围」。

⚠️ 前三种入口内部都走同一套代码（``_resolve_item`` / ``_search_by_title`` /
``_fetch_detail``），因此**共享同一个配额闸门**：不管谁来调，都不会绕过限流。
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

try:  # 宿主的浏览器仿真门面（cloakbrowser / FlareSolverr，见配置里的实验开关）
    from app.sdk.browser import launch_browser_context as _launch_browser_context
except Exception:  # pragma: no cover - 宿主版本差异兜底
    _launch_browser_context = None

try:  # 宿主事件总线 —— 「探索」页的来源收集就靠它广播 DiscoverSource 事件
    from app.sdk.events import Event as _HostEvent
    from app.sdk.events import eventmanager as _eventmanager
except Exception:  # pragma: no cover - 宿主版本差异兜底
    _HostEvent = None  # type: ignore[assignment]
    _eventmanager = None  # type: ignore[assignment]

try:  # 探索页来源 schema（SDK 未导出；走 app.schemas，与已装插件同一路径）
    from app.schemas import DiscoverMediaSource as _DiscoverMediaSource
    from app.schemas import DiscoverSourceEventData as _DiscoverSourceEventData
except Exception:  # pragma: no cover - 宿主版本差异兜底
    _DiscoverMediaSource = None  # type: ignore[assignment]
    _DiscoverSourceEventData = None  # type: ignore[assignment]

try:  # 事件类型枚举（DiscoverSource 在此）
    from app.schemas.types import ChainEventType as _ChainEventType
except Exception:  # pragma: no cover - 宿主版本差异兜底
    _ChainEventType = None  # type: ignore[assignment]

try:  # 定时服务
    from apscheduler.triggers.interval import IntervalTrigger
except Exception:  # pragma: no cover - 极端兜底

    class IntervalTrigger:  # type: ignore[no-redef]
        """宿主调度器不可用时的占位（插件仍然可用，只是没有定时索引）。"""

        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = kwargs


try:  # 智能体工具（宿主没有该能力时插件照常工作）
    from .agenttool import ShortDramaIdentifyTool
except Exception:  # pragma: no cover - 宿主版本差异兜底
    ShortDramaIdentifyTool = None  # type: ignore[assignment]


# ── 插件元数据（须与 package.v3.json 保持一致） ──────────────────────
PLUGIN_NAME = "短剧百科数据源"
PLUGIN_ICON = (
    "https://raw.githubusercontent.com/m215owen/MoviePilot-Plugins/main/icons/"
    "ShortDramaBaikeSource.png"
)
PLUGIN_VERSION = "1.3.0"

# ── 数据源常量 ────────────────────────────────────────────────────
# 规范写法是宿主 ``MediaSource`` 枚举值；另外两个别名是为了让**其它插件**按
# 「插件 ID」或「域名简称」点名时也能命中，不必去查枚举值的准确拼写。
MEDIA_SOURCE_KEY = "duanjubaike"
MEDIA_SOURCE_LABEL = "短剧百科"
MEDIA_SOURCE_ALIASES = frozenset({"duanjubaike", "shortdramabaike", "shortdramabaikesource"})

ORG_DEFAULT_DOMAIN = "https://duanjubaike.org"

# 站点路径（``{id}`` 为占位）
DETAIL_PATH = "/zh-Hans/drama/{id}"
CATALOG_PATH = "/zh-Hans/drama/list"
FEATURED_PATH = "/zh-Hans/drama"
TOP_PATH = "/zh-Hans/top/{key}"

# 目录每页作品数（站点固定 30；用于估算总条数与索引进度）
CATALOG_PAGE_SIZE = 30
# 实测站内自述「共 1879 页」，这里给一个上限用于钳制配置
CATALOG_MAX_PAGES = 2000

# 17 个榜单（实测 /zh-Hans/top/hot 页面上的全部导航项）。
# ⚠️ 榜单**数量固定、不分页** —— 不要试图给它加 ?page=N。
TOP_LISTS: Dict[str, str] = {
    "hot": "热播榜",
    "new": "新剧榜",
    "celebrity": "明星榜",
    "comic-hot": "漫剧热榜",
    "search": "搜索榜",
    "hot-urban": "都市榜",
    "hot-rebirth": "重生榜",
    "hot-through": "穿越榜",
    "hot-system": "系统榜",
    "hot-male": "男频榜",
    "hot-female": "女频榜",
    "hot-female-grouth": "女性成长榜",
    "hot-strong-female": "大女主榜",
    "hot-vest": "战神马甲榜",
    "hot-face-slapping": "打脸榜",
    "hot-counter-attack": "逆袭榜",
    "hot-country": "乡村榜",
}
DEFAULT_TOP_KEY = "hot"
# 默认只刷两个最实用的榜单：**每个榜单要花一次站点请求配额**
DEFAULT_TOP_KEYS: Tuple[str, ...] = ("hot", "new")

# 统一媒体 ID 前缀（media_id 形如 ``org:40105``）。探索页的 ``mediaid_prefix``
# 必须与它一致，前端才能把条目路由回本数据源。
MEDIA_ID_PREFIX = "org"

# ── 宿主「探索」页（/discover）────────────────────────────────────
# 宿主 ``GET /api/v1/discover/source`` 会广播 ``ChainEventType.DiscoverSource``，
# 插件把 ``DiscoverMediaSource`` 塞进 ``event_data.extra_sources`` 即成为一个来源；
# 前端随后按该来源的 ``api_path`` 拉 ``List[MediaInfo]``。
EXPLORE_PATH = "/explore"
EXPLORE_DEFAULT_COUNT = 30
MAX_EXPLORE_COUNT = 60
# 「全部短剧」：用本地目录索引当伪榜单 —— 榜单只有十几条，索引会持续增长
EXPLORE_INDEX_KEY = "index"
EXPLORE_INDEX_LABEL = "全部短剧"
# 榜单页 / 目录页的卡片只有「标题 + 海报 + 集数」，而 TMDB 那种「简介 + 年份 +
# 类型 + 演员」只在**作品详情页**里。为了不把探索页做成空壳，打开探索页时按需
# 回填少量详情（走同一个配额闸门，并给「识别」留出额度）。
EXPLORE_DETAIL_FETCH_DEFAULT = 2    # 每次探索请求最多回填几部作品的详情（0 = 只读本地）
MAX_EXPLORE_DETAIL_FETCH = 10
EXPLORE_DETAIL_RESERVE = 2          # 回填期间给识别保留的额度（用完至少剩这么多）

# 需要登记进宿主图片白名单的域名（否则图片代理会拒收）
IMAGE_DOMAINS: Tuple[str, ...] = (
    "cdn.duanjubaike.org",
    "cdn.duanjubaike.cn",
    "duanjubaike.org",
)

# 默认值 / 上限
DEFAULT_TIMEOUT = 15
DEFAULT_CACHE_TTL = 604800          # 详情页内容基本不变，缓存 7 天
DEFAULT_MIN_INTERVAL = 3.0          # 两次请求的最小间隔（秒）—— 站点配额很紧
DEFAULT_COOLDOWN_MINUTES = 10       # 撞到 403 后的冷却时长
# 滚动窗口配额（实测：1.5s 与 10s 间隔都是第 6 次撞 403 ⇒ 卡的是「窗口内次数」）
DEFAULT_QUOTA_WINDOW_MINUTES = 5
DEFAULT_QUOTA_MAX_REQUESTS = 5
DEFAULT_SCAN_PAGES = 1              # 无索引时的实时扫描页数（1 × 30 部）
MAX_SCAN_PAGES = 10
# 每轮索引页数默认压到配额以内：这样一轮跑完**不会**撞 403，IP 不会被打死。
DEFAULT_INDEX_PAGES_PER_RUN = 4
MAX_INDEX_PAGES_PER_RUN = 200
DEFAULT_INDEX_MAX_PAGES = 700       # 索引最多覆盖多少页（700 × 30 = 21000 部）
MAX_INDEX_MAX_PAGES = CATALOG_MAX_PAGES
DEFAULT_INTERVAL_MINUTES = 5        # 后台索引轮询间隔（分钟）
MAX_CANDIDATES = 12
# 持久化键（宿主 save_data / get_data）
_DATA_INDEX = "catalog_index"
_DATA_INDEX_STATE = "catalog_state"
_DATA_TOP = "top_snapshot"
# 单次索引落盘的最大条数（防 index.json 无限膨胀 + 单次写盘过慢）
_INDEX_HARD_LIMIT = 60000
# 浏览器过 CF 时最多等多久（秒）
_BROWSER_CHALLENGE_WAIT = 25
# 榜单快照存活时长（小时）
_TOP_TTL_HOURS = 6

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
    """去掉标签后折叠空白——用于从片段里取纯文本。"""
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
    """把图片地址归一成可用直链（补协议、去掉多余空白）。"""
    src = _clean(src)
    if not src:
        return ""
    if src.startswith("//"):
        return f"https:{src}"
    return src


def _parse_int(value: Any) -> Optional[int]:
    """从「80」「80 集」「2小时18分钟」这类文本里取出第一个整数。"""
    match = re.search(r"\d+", str(value or ""))
    return int(match.group(0)) if match else None


def _parse_year(value: Any) -> Optional[str]:
    """从「2026年10月10日」/「2026-10-10」里取出四位年份。"""
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
    """把「2小时18分钟」/ ISO8601 的 ``PT2H46S`` 统一成分钟数。"""
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
    """归一化片名用于比对：去书名号、去空白、全角转半角、统一大小写。"""
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
# 目录页底部：<span …>第 1 页，共 1879 页</span>
_ORG_TOTAL_PAGES_RE = re.compile(r"共\s*(?P<total>\d+)\s*页")
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


def parse_org_total_pages(html: str) -> int:
    """从目录页底部的「第 1 页，共 1879 页」取总页数；取不到返回 0。

    ⚠️ 只有 ``/zh-Hans/drama/list`` 有这个分页控件 —— ``/zh-Hans/drama``（精选页）
    与 ``/zh-Hans/top/*``（榜单）**都不分页**，拿它们的内容去问总页数没有意义。
    """
    match = _ORG_TOTAL_PAGES_RE.search(html or "")
    return int(match.group("total")) if match else 0


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
    """从页面里抽出 ``TVSeries`` 与 ``WebPage`` 两个 JSON-LD 节点。"""
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


def is_cloudflare_challenge(html: str, status_code: Optional[int] = None) -> bool:
    """判断响应是否为 Cloudflare 人机校验页（而非真实内容）。

    ⚠️ 本站在配额耗尽时对**整站**（含详情页、robots.txt）返回 403 —— 它既是
    「被挡」，也是「该退避了」的信号，调用方必须据此进入冷却而不是重试。
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


# ── 宿主「探索」页的支持件 ────────────────────────────────────────


def _discover_source_listener(func: Any) -> Any:
    """把方法注册成 ``ChainEventType.DiscoverSource`` 的处理器。

    刻意用「函数包一层」而不是直接写 ``@eventmanager.register(...)``：宿主版本
    差异下 ``app.sdk.events`` 或 ``ChainEventType.DiscoverSource`` 可能取不到，
    那时插件仍必须能正常加载（只是探索页里不会出现它的来源）。
    """
    if _eventmanager is None or _ChainEventType is None:
        return func
    try:
        return _eventmanager.register(_ChainEventType.DiscoverSource)(func)
    except Exception as err:  # pragma: no cover - 宿主版本差异兜底
        logger.debug(f"{PLUGIN_NAME} 注册探索来源事件失败：{err}")
        return func


def _media_to_dict(mediainfo: Any) -> Dict[str, Any]:
    """把 ``MediaInfo`` 转成探索页能吃的 dict（模型缺 ``to_dict`` 时手工兜底）。"""
    if mediainfo is None:
        return {}
    dump = getattr(mediainfo, "to_dict", None)
    if callable(dump):
        try:
            return dump()
        except Exception as err:  # pragma: no cover - 个别模型只读
            logger.debug(f"{PLUGIN_NAME} 序列化媒体信息失败：{err}")
    if isinstance(mediainfo, dict):
        return dict(mediainfo)
    return {}


def _explore_response(data: Any) -> Any:
    """按探索页的合同包一层（``Response[List[MediaInfo]]``）。

    宿主已装插件（``IMDbSource`` / ``IqiyiDiscover``）都用这个形状；拿不到
    ``app.schemas.Response`` 时退化成同名字段的普通 dict。
    """
    try:
        from app.schemas import Response as _Response

        return _Response(success=True, data=data)
    except Exception:  # pragma: no cover - 宿主版本差异兜底
        return {"success": True, "message": "", "data": data}


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
PUBLIC_ACTOR_FIELDS = ("id", "name", "role", "kind")


def build_public_record(item: Optional[Dict[str, Any]], origin: str = "detail") -> Dict[str, Any]:
    """把一条作品记录压成**纯 JSON** 载荷（其它插件调用的统一形状）。

    :param item: ``parse_org_detail`` / ``parse_org_cards`` 产出的记录
    :param origin: ``detail``（来自详情页，字段全）或 ``index``（来自本地索引，字段少）
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
        {key: actor.get(key) for key in PUBLIC_ACTOR_FIELDS if actor.get(key)}
        for actor in (item.get("actors") or [])
        if actor.get("name")
    ]
    if actors:
        record["actors"] = actors
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
    _scan_pages: int = DEFAULT_SCAN_PAGES
    _timeout: int = DEFAULT_TIMEOUT
    _cache_ttl: int = DEFAULT_CACHE_TTL
    _min_interval: float = DEFAULT_MIN_INTERVAL
    _cooldown_minutes: int = DEFAULT_COOLDOWN_MINUTES
    _quota_window_minutes: int = DEFAULT_QUOTA_WINDOW_MINUTES
    _quota_max_requests: int = DEFAULT_QUOTA_MAX_REQUESTS
    _index_enabled: bool = True
    _index_pages_per_run: int = DEFAULT_INDEX_PAGES_PER_RUN
    _index_max_pages: int = DEFAULT_INDEX_MAX_PAGES
    _interval_minutes: int = DEFAULT_INTERVAL_MINUTES
    _use_browser_search: bool = False
    _proxy: bool = False
    # 探索页每次请求最多回填几部作品的详情（0 = 不额外请求，只读本地快照）
    _explore_detail_fetch: int = EXPLORE_DETAIL_FETCH_DEFAULT
    # 详情页事实摘要行（评分 · 集数 · 主演）：宿主详情页没有给自定义来源留位置，
    # 只能借 tagline 位承载，见 build_detail_facts()
    _detail_facts: bool = True

    # ── 运行时状态（由 init_plugin 重建，保证可重复初始化） ──
    _cache: Dict[str, Tuple[float, Any]] = {}
    _cache_lock = threading.RLock()
    # 配额闸门：所有出站请求都要先过 _take_slot()，它保证「最小间隔 + 滚动窗口额度」
    _gate_lock = threading.Lock()
    _next_request_at: float = 0.0
    _blocked_until: float = 0.0
    _blocked_at: float = 0.0
    _slots: List[float] = []
    # 本地目录索引：id -> {"title", "poster", ...}
    _index: Dict[str, Dict[str, Any]] = {}
    _index_state: Dict[str, Any] = {}
    # 榜单快照：榜单键 -> {"items": [...], "fetched_at": ts}
    _top_cache: Dict[str, Dict[str, Any]] = {}
    _stats: Dict[str, Any] = {}
    # 榜单快照要刷哪些榜单（探索页的榜单来源就是它；每个榜单一次请求配额）
    _top_keys: List[str] = list(DEFAULT_TOP_KEYS)

    # ── 生命周期 ──────────────────────────────────────────────────

    def init_plugin(self, config: Optional[Dict[str, Any]] = None) -> None:
        """按配置重建运行状态，并把持久化的索引 / 榜单快照读回内存。"""
        config = config or {}
        self._enabled = bool(config.get("enabled"))
        self._domain = self._as_domain(config.get("domain"), ORG_DEFAULT_DOMAIN)
        self._search_in_global = self._as_bool(config.get("search_in_global"), True)
        self._scan_pages = self._as_range(config.get("scan_pages"), DEFAULT_SCAN_PAGES, 1, MAX_SCAN_PAGES)
        self._timeout = self._as_range(config.get("timeout"), DEFAULT_TIMEOUT, 5, 120)
        self._cache_ttl = self._as_range(config.get("cache_ttl"), DEFAULT_CACHE_TTL, 0, 2592000)
        self._min_interval = self._as_float(config.get("min_interval"), DEFAULT_MIN_INTERVAL, 0.0, 60.0)
        self._cooldown_minutes = self._as_range(
            config.get("cooldown_minutes"), DEFAULT_COOLDOWN_MINUTES, 1, 240
        )
        self._quota_window_minutes = self._as_range(
            config.get("quota_window_minutes"), DEFAULT_QUOTA_WINDOW_MINUTES, 1, 120
        )
        self._quota_max_requests = self._as_range(
            config.get("quota_max_requests"), DEFAULT_QUOTA_MAX_REQUESTS, 1, 100
        )
        self._index_enabled = self._as_bool(config.get("index_enabled"), True)
        self._index_pages_per_run = self._as_range(
            config.get("index_pages_per_run"), DEFAULT_INDEX_PAGES_PER_RUN, 1, MAX_INDEX_PAGES_PER_RUN
        )
        self._index_max_pages = self._as_range(
            config.get("index_max_pages"), DEFAULT_INDEX_MAX_PAGES, 30, MAX_INDEX_MAX_PAGES
        )
        self._interval_minutes = self._as_range(
            config.get("interval_minutes"), DEFAULT_INTERVAL_MINUTES, 1, 1440
        )
        self._use_browser_search = self._as_bool(config.get("use_browser_search"), False)
        self._proxy = bool(config.get("proxy"))
        self._top_keys = self._as_top_keys(config.get("top_keys"))
        self._explore_detail_fetch = self._as_range(
            config.get("explore_detail_fetch"),
            EXPLORE_DETAIL_FETCH_DEFAULT,
            0,
            MAX_EXPLORE_DETAIL_FETCH,
        )
        self._detail_facts = self._as_bool(config.get("detail_facts"), True)

        # ⚠️ 运行时容器必须在**每个实例**上重新绑定。它们是类属性，若只原地 clear()
        # 或干脆不动，同一进程里被重建的插件实例（宿主 reconcile 会反复重建）会共用
        # 同一批 dict —— 计数器与去重记录会跨实例串味（实测 blocked_count 一次请求
        # 记出 3 次）。这里一次性换成新对象：既让旧缓存/旧域名失效，也把语义钉死。
        self._cache = {}
        self._index = {}
        self._index_state = {}
        self._top_cache = {}
        self._stats = {}
        with self._gate_lock:
            self._next_request_at = 0.0
            self._blocked_until = 0.0
            self._blocked_at = 0.0
            self._slots = []

        self._load_state()
        self._register_image_domains()
        logger.info(
            f"{PLUGIN_NAME} 已就绪：启用={self._enabled} 域名={self._domain} "
            f"全局检索={self._search_in_global} 索引={len(self._index)} 条"
            f"（已抓 {self._index_state.get('next_page', 1) - 1} 页）"
        )

    def get_state(self) -> bool:
        """返回插件是否启用。"""
        return self._enabled

    def stop_service(self) -> None:
        """停止插件：清空内存缓存（持久化数据保留）。"""
        with self._cache_lock:
            self._cache.clear()

    def get_render_mode(self) -> Tuple[str, Optional[str]]:
        """使用宿主默认的 vuetify 渲染模式（无需前端构建产物）。"""
        return "vuetify", None

    def get_service(self) -> List[Dict[str, Any]]:
        """注册后台服务：**小步推进**本地目录索引 + 刷新榜单快照。

        ⚠️ 这个服务存在的唯一原因是站点的 Cloudflare 配额（实测：一个窗口内约 5 次
        请求，1.5 秒间隔和 10 秒间隔都是第 6 次撞 403）。所以它每轮只抓
        ``index_pages_per_run`` 页（默认 4 页，**故意压在配额以内**，让一轮跑完不会
        触发 403），页间还隔着 ``min_interval`` 秒，并且额外留一个额度给识别
        （``reserve=1``），撞到 403 就立刻停手进入冷却，**断点续爬**。

        绝不能把它改成「一次抓完 1879 页」—— 那会把 IP 打死，详情识别也跟着废。
        """
        if not self.get_state():
            return []
        return [
            {
                "id": f"{self.__class__.__name__}.Index",
                "name": f"{self.plugin_name}·目录索引与榜单刷新",
                "trigger": IntervalTrigger(minutes=max(1, self._interval_minutes)),
                "func": self.execute_task,
                # 宿主会把 service["kwargs"] 原样展开给 scheduler.add_job()，
                # 而 trigger 是 add_job 自己的形参名 ⇒ 必须写进 func_kwargs。
                "func_kwargs": {"trigger": "interval"},
            }
        ]

    def execute_task(self, trigger: str = "interval") -> Dict[str, Any]:
        """后台任务：推进一页索引批次，并在快照过期时刷新榜单。

        返回一份可读的结果摘要（也用于 API 手动触发）。
        """
        if not self.get_state():
            return {"success": False, "message": "插件未启用"}
        report: Dict[str, Any] = {"trigger": trigger}

        top_report = self.refresh_top_lists(force=False)
        report["top"] = top_report

        if self._index_enabled:
            report["index"] = self.build_index_step(
                pages=self._index_pages_per_run, reason=trigger
            )
        else:
            report["index"] = {"success": False, "message": "目录索引已关闭"}
        return report

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
        """
        return {
            "recognize_media": self.recognize_media,
            "async_recognize_media": self.async_recognize_media,
            "search_medias": self.search_medias,
            "async_search_medias": self.async_search_medias,
            "obtain_images": self.obtain_images,
            "async_obtain_images": self.async_obtain_images,
        }

    def get_agent_tools(self) -> List[type]:
        """注册智能体工具，供 MoviePilot 的 AI 智能体识别短剧。

        宿主会在**插件实例**上调用本方法，所以这里先把当前实例注入工具类
        （``bind``），工具内部就不必依赖进程级单例或硬编码插件 ID。
        """
        if ShortDramaIdentifyTool is None:  # pragma: no cover - 宿主无智能体能力
            return []
        ShortDramaIdentifyTool.bind(self)
        return [ShortDramaIdentifyTool]


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
        """按媒体身份或片名识别短剧作品。"""
        if not self._enabled:
            return None
        # 宿主默认源是 TMDB，插件源必须只认自己，否则会劫持别人的识别
        if not self._is_our_source(media_source):
            return None

        item = self._resolve_item(media_id=media_id, meta=meta, use_cache=cache)
        if not item:
            return None
        # 作品详情页没有评分（评分只渲染在目录页的卡片上），所以这里再向本地索引
        # 借一次 —— 同一部作品两边 native_id 相同，零请求就能把评分/标签补上。
        item = self._merge_index_extras(item)
        return build_media_info(item, facts=self._detail_facts)

    async def async_recognize_media(self, *args: Any, **kwargs: Any) -> Any:
        """``recognize_media`` 的异步版本（网络请求放到线程池）。"""
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
        """``search_medias`` 的异步版本。"""
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
        """``obtain_images`` 的异步版本。"""
        return await asyncio.to_thread(self.obtain_images, mediainfo)

    # ── 身份解析 ──────────────────────────────────────────────────

    def _resolve_item(
        self,
        media_id: Optional[str],
        meta: Any,
        use_cache: bool = True,
    ) -> Optional[Dict[str, Any]]:
        """把「媒体身份或片名」解析成一条件作品记录。"""
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
            # 老版本用过 net:<section>:<id> 复合 ID；这种值在本站不存在，
            # 直接判空 —— 把它当数字 ID 去请求只会白白消耗一次配额。
            return ""
        return text if text.isdigit() else ""

    def _fetch_detail(
        self,
        media_id: str,
        use_cache: bool = True,
        reserve: int = 0,
    ) -> Optional[Dict[str, Any]]:
        """按统一媒体 ID 抓取详情页（带 TTL 缓存）。

        ``reserve`` 透传给配额闸门：探索页回填详情时用它给「识别」留额度。
        """
        native_id = self._native_id(media_id)
        if not native_id:
            return None
        cache_key = f"detail:{native_id}"
        if use_cache:
            cached = self._cache_get(cache_key)
            if cached is not None:
                return cached

        html, status = self._get(
            f"{self._domain}{DETAIL_PATH.format(id=native_id)}", reserve=reserve
        )
        if not html or is_cloudflare_challenge(html, status):
            return None
        item = parse_org_detail(html, native_id, self._domain)
        if not item.get("title"):
            return None
        item["media_id"] = f"org:{native_id}"
        if use_cache:
            self._cache_set(cache_key, item)
        return item

    # ── 检索：三级降级 ────────────────────────────────────────────

    def _search_by_title(self, query: str, target_year: Optional[str] = None) -> List[Dict[str, Any]]:
        """按片名检索，返回带打分的候选（分高在前）。

        三级降级，任一级命中即返回（后面的级别既慢又费配额）：

        1. **本地目录索引**（``_index``）：后台任务逐页抓下来的全量片名表。
        2. **榜单快照**（``_top_cache``）：最新 / 热门作品，覆盖索引还没抓到的部分。
        3. **实时目录扫描**：现场抓目录前 ``scan_pages`` 页 —— 只在没有索引时兜底，
           因为它要花掉宝贵的配额。
        """
        candidates: List[Dict[str, Any]] = []

        # 1) 本地索引
        for native_id, record in self._index.items():
            title = _clean(record.get("title"))
            if title:
                candidates.append(dict(record, media_id=f"org:{native_id}", native_id=native_id))

        # 2) 榜单快照
        for entry in self._top_cache.values():
            for item in entry.get("items") or []:
                candidates.append(dict(item))

        # 3) 实时目录扫描（前面两级都没有可用数据时才打网络）
        if not self._index and not self._top_cache:
            candidates.extend(self._scan_catalog(self._scan_pages))

        # 4) 站内检索（实验开关）：宿主浏览器过 Cloudflare 后抓 /drama/search
        if self._use_browser_search:
            candidates.extend(self._search_via_browser(query))

        return self._rank_candidates(candidates, query, target_year)

    @staticmethod
    def _rank_candidates(
        candidates: List[Dict[str, Any]],
        query: str,
        target_year: Optional[str],
    ) -> List[Dict[str, Any]]:
        """给候选打分、按「归一化标题 + 年份」去重、按分排序。"""
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

    def _scan_catalog(self, pages: int) -> List[Dict[str, Any]]:
        """实时抓目录前 N 页做本地片名匹配（没有索引时的兜底，费配额）。"""
        results: List[Dict[str, Any]] = []
        for page in range(1, max(1, pages) + 1):
            html = self._fetch_catalog_page(page)
            if not html:
                # 拿不到内容（多半是撞上配额）就没必要继续翻页
                break
            cards = parse_org_cards(html, self._domain)
            if not cards:
                break
            results.extend(cards)
        return results

    def _search_via_browser(self, query: str) -> List[Dict[str, Any]]:
        """用宿主浏览器仿真打站内检索（实验特性，默认关闭）。

        站内检索被 Cloudflare 的 JS 挑战挡着：普通 HTTP 一律 403（正文是
        ``Just a moment...``）。宿主的 ``app.sdk.browser``（cloakbrowser /
        FlareSolverr）能把挑战页跑掉，所以这里给它一条路。

        ⚠️ 这条路**没有在 NAS 上验证过能稳定通过**，因此默认关闭、失败即静默返回
        空列表：检索的主力永远是本地索引，浏览器只是「多一条腿」。
        """
        url = f"{self._domain}/zh-Hans/drama/search"
        html = self._browser_fetch(url, params={"q": query})
        if not html:
            return []
        return parse_org_cards(html, self._domain)

    # ── 目录索引 ──────────────────────────────────────────────────

    def build_index_step(self, pages: int = 0, reason: str = "manual") -> Dict[str, Any]:
        """按配额推进一批目录页，把作品并入本地索引并落盘（断点续爬）。

        每轮从 ``_index_state["next_page"]`` 接着抓，抓满 ``pages`` 页或撞到 403
        就停；撞到 403 时**不推进** ``next_page``（否则会永久跳过这些页），
        并把冷却时间交给配额闸门。
        """
        pages = max(1, int(pages or self._index_pages_per_run))
        fetched = 0
        added = 0
        blocked = False
        total_pages = int(self._index_state.get("total_pages") or 0)
        next_page = int(self._index_state.get("next_page") or 1)
        limit = min(self._index_max_pages, total_pages or self._index_max_pages)

        while fetched < pages:
            # 额度用光（或已在冷却）就停手：留给识别与检索，且绝不主动去撞 403
            if self._quota_remaining() <= 1:
                break
            if next_page > limit:
                # 抓满配置的上限后回到第 1 页继续追新（新剧都在最前面）
                next_page = 1
            html = self._fetch_catalog_page(next_page)
            if not html:
                blocked = True
                break
            if not total_pages:
                total_pages = parse_org_total_pages(html)
            cards = parse_org_cards(html, self._domain)
            fetched += 1
            for card in cards:
                native_id = card["native_id"]
                if native_id in self._index:
                    continue
                if len(self._index) >= _INDEX_HARD_LIMIT:
                    break
                self._index[native_id] = {
                    "title": card["title"],
                    "poster": card.get("poster", ""),
                    **{
                        key: card[key]
                        for key in ("tags", "episode_count", "rating", "kind", "series", "season")
                        if card.get(key) not in (None, "", [])
                    },
                }
                added += 1
            next_page += 1

        self._index_state.update(
            {
                "next_page": next_page,
                "total_pages": total_pages,
                "last_run_at": time.time(),
                "last_reason": reason,
                "last_blocked": blocked,
            }
        )
        self._save_state()
        report = {
            "success": fetched > 0,
            "pages": fetched,
            "added": added,
            "indexed": len(self._index),
            "next_page": next_page,
            "total_pages": total_pages,
            # 「停手」既可能是撞上 403，也可能只是配额闸门把额度留给了识别 ——
            # 两者都算正常，区分开是为了让面板能如实说明原因。
            "stopped_early": blocked,
            "cooling_down": self._blocked_until > time.time(),
            "quota_remaining": self._quota_remaining(),
        }
        if fetched:
            logger.info(
                f"{PLUGIN_NAME} 目录索引推进 {fetched} 页（+{added} 部，共 {len(self._index)} 部，"
                f"下一页 {next_page}/{total_pages or '?'}{'，已停手' if blocked else ''}）"
            )
        return report

    def _fetch_catalog_page(self, page: int) -> str:
        """取目录第 ``page`` 页；被风控拦住时返回空串（配额闸门会记冷却）。

        ``reserve=1`` 表示这是**后台**请求：它要求用完后至少还剩一个额度，
        把最后的额度让给交互式识别。
        """
        html, status = self._get(
            f"{self._domain}{CATALOG_PATH}",
            params={"page": str(max(1, int(page or 1)))},
            reserve=1,
        )
        if is_cloudflare_challenge(html, status):
            return ""
        return html

    # ── 榜单快照 ──────────────────────────────────────────────────

    def refresh_top_lists(self, force: bool = False, keys: Optional[List[str]] = None) -> Dict[str, Any]:
        """刷新榜单快照（默认 6 小时一次；榜单数量固定、不分页，一页一个请求）。

        ⚠️ 每个榜单要花一次请求配额，所以默认只刷「热播榜 + 新剧榜」；想多刷几个
        在配置里勾（``top_keys``）—— 探索页能看到的榜单就是这些。
        """
        wanted = [
            key
            for key in (keys or self._top_keys or list(DEFAULT_TOP_KEYS))
            if key in TOP_LISTS
        ]
        ttl = _TOP_TTL_HOURS * 3600
        now = time.time()
        refreshed: List[str] = []
        for key in wanted:
            cached = self._top_cache.get(key) or {}
            if not force and now - float(cached.get("fetched_at") or 0) < ttl:
                continue
            # 后台请求：留一个额度给识别，额度不够就本轮不刷
            if self._quota_remaining() <= 1:
                break
            html, status = self._get(
                f"{self._domain}{TOP_PATH.format(key=key)}", reserve=1
            )
            if not html or is_cloudflare_challenge(html, status):
                break  # 配额已到，剩下的榜单等下一轮
            items = parse_org_cards(html, self._domain)
            if not items:
                continue
            self._top_cache[key] = {"items": items, "fetched_at": now, "label": TOP_LISTS[key]}
            refreshed.append(key)
        if refreshed:
            self._save_state()
        return {"success": bool(refreshed), "refreshed": refreshed}

    # ── 宿主「探索」页的数据源 ────────────────────────────────────
    #
    # 宿主 ``GET /api/v1/discover/source`` 会广播 ``ChainEventType.DiscoverSource``，
    # 插件把 ``DiscoverMediaSource`` 追加进 ``event_data.extra_sources`` 就成为一个
    # 来源；前端随后按 ``api_path`` 拉 ``List[MediaInfo]``。已装插件 ``IMDbSource`` /
    # ``IqiyiDiscover`` / ``ExploreServices`` 都是这个姿势。
    #
    # ⚠️ 探索页的数据**一律只读本地**（榜单快照 + 目录索引），零网络请求 ——
    # 用户翻页不会消耗站点配额，也不会把 IP 打到 CF 冷却里。

    def _top_snapshot_summary(self) -> str:
        """榜单快照的一行摘要（``热播榜 19 部 / 新剧榜 20 部``），供面板展示。"""
        if not self._top_cache:
            return "无（等后台任务刷新；可在配置里勾要刷的榜单）"
        parts: List[str] = []
        for key, entry in self._top_cache.items():
            label = str((entry or {}).get("label") or TOP_LISTS.get(key, key))
            parts.append(f"{label} {len((entry or {}).get('items') or [])} 部")
        return " / ".join(parts)

    def _explore_top_keys(self) -> List[str]:
        """探索页里可选的榜单键：配置里勾的在前，已缓存快照的补在后。"""
        keys: List[str] = [key for key in self._top_keys if key in TOP_LISTS]
        for key in self._top_cache:
            if key in TOP_LISTS and key not in keys:
                keys.append(key)
        return keys

    def _explore_default_key(self) -> str:
        """默认选中的来源键：**优先挑已经有快照数据的那个**。

        配置里勾了但还没刷到的榜单是空的，若把它当默认项，用户打开探索页会看到
        一片空白 —— 所以按配置顺序找第一个「有数据」的，全都没有才退回配置首位。
        """
        keys = self._explore_top_keys()
        for key in keys:
            if key in self._top_cache:
                return key
        return keys[0] if keys else DEFAULT_TOP_KEY

    def _explore_options(self) -> List[Tuple[str, str]]:
        """探索页的来源选项 ``(键, 中文名)``：榜单 + 「全部短剧」（本地目录索引）。"""
        options: List[Tuple[str, str]] = [
            (key, TOP_LISTS[key]) for key in self._explore_top_keys()
        ]
        if self._index:
            # 榜单只有十几条，索引会一直长 —— 给它也留一个来源，探索页才不至于太空
            options.append((EXPLORE_INDEX_KEY, EXPLORE_INDEX_LABEL))
        return options

    def _explore_items(self, key: str) -> List[Dict[str, Any]]:
        """取某个来源的条目（**只读本地**，不产生任何请求）。"""
        if key == EXPLORE_INDEX_KEY:
            rows: List[Dict[str, Any]] = []
            for native_id, record in self._index.items():
                rows.append(dict(record, media_id=f"{MEDIA_ID_PREFIX}:{native_id}", native_id=native_id))
            # 站点 ID 越大越新 ⇒ 倒序就是「最新在前」
            rows.sort(key=lambda row: int(str(row.get("native_id") or 0) or 0), reverse=True)
            return rows
        entry = self._top_cache.get(key) or {}
        return [self._merge_index_extras(dict(item)) for item in (entry.get("items") or [])]

    def _merge_index_extras(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """用本地目录索引给一条记录补齐评分 / 标签这类**卡片字段**（**零请求**）。

        评分与标签只在**目录页的卡片**上渲染：榜单页卡片只有「标题 + 海报 + 集数 +
        热度」，作品详情页更是只有「简介 + 播放 + 收藏」。所以不管是探索页的榜单条目
        还是详情识别，都可以按 ``native_id`` 去本地索引里取一份来补 —— 同一部作品在
        三处的 ID 完全相同，而索引本来就在本地。只补**缺失**字段，已有的（尤其是
        榜单/详情里更新的集数）一律不动。
        """
        native_id = self._native_id(row.get("media_id") or row.get("native_id"))
        record = self._index.get(native_id) if native_id else None
        if not record:
            return row
        merged = dict(row)
        for field in ("rating", "tags", "episode_count", "series", "season", "kind"):
            if not _has_value(merged.get(field)) and _has_value(record.get(field)):
                merged[field] = record[field]
        return merged

    def _explore_enrich(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """把探索页条目的**详情字段**补齐（简介 / 年份 / 类型 / 演员 / 评分）。

        榜单页与目录页的卡片只有「标题 + 海报 + 集数」，TMDB 那种详情只在**作品详情页**
        里（JSON-LD）。所以这里按需回填，两条来路：

        * 先查**详情缓存**（识别 / 检索 / 上一轮回填都写同一个 ``detail:<id>`` 键）；
        * 缓存没有、且配额闸门放行（用完至少剩 ``EXPLORE_DETAIL_RESERVE`` 次给识别）时
          现场抓一部；抓失败（403 / 超时）就**立即收手**，绝不空转把 IP 打进冷却。

        回填条数由 ``explore_detail_fetch`` 控制（0 = 完全只读本地，零请求）。
        """
        if not rows:
            return rows
        budget = self._explore_detail_fetch if self._enabled else 0
        enriched: List[Dict[str, Any]] = []
        for row in rows:
            merged = dict(row)
            native_id = self._native_id(merged.get("media_id") or merged.get("native_id"))
            if native_id:
                detail = self._cache_get(f"detail:{native_id}")
                if detail is None and budget > 0:
                    if self._quota_remaining() > EXPLORE_DETAIL_RESERVE:
                        detail = self._fetch_detail(
                            f"{MEDIA_ID_PREFIX}:{native_id}",
                            use_cache=True,
                            reserve=EXPLORE_DETAIL_RESERVE,
                        )
                        budget -= 1
                        if not detail:
                            # 站点不给数据了（多半是撞配额 / CF），本轮别再试
                            budget = 0
                    else:
                        # 额度见底：把剩下的留给识别，回填下轮再说
                        budget = 0
                if detail:
                    merged.update(
                        {key: value for key, value in detail.items() if _has_value(value)}
                    )
                    # 身份字段听列表项的（榜单条目的季/集数比详情页更贴合当前条目）
                    merged["media_id"] = row.get("media_id") or detail.get("media_id")
                    merged["native_id"] = native_id
            enriched.append(merged)
        return enriched

    def _explore_api_path(self) -> str:
        """探索页要调的相对地址（``/api/v1/`` 之后的部分，含 apikey）。"""
        path = f"plugin/{self.__class__.__name__}{EXPLORE_PATH}"
        token = _clean(getattr(_settings, "API_TOKEN", None))
        return f"{path}?apikey={token}" if token else path

    def _explore_filter_ui(self) -> List[Dict[str, Any]]:
        """探索页的筛选条：一行「榜单」chips，值原样回传成 ``top_key``。

        结构照抄宿主已装插件（``VLabel`` + ``VChipGroup``，``model`` 对应查询参数名）。
        """
        chips = [
            {
                "component": "VChip",
                "props": {"filter": True, "tile": True, "value": key},
                "text": label,
            }
            for key, label in self._explore_options()
        ]
        if not chips:
            return []
        return [
            {
                "component": "div",
                "props": {"class": "flex justify-start items-center"},
                "content": [
                    {
                        "component": "div",
                        "props": {"class": "mr-5"},
                        "content": [{"component": "VLabel", "text": "榜单"}],
                    },
                    {
                        "component": "VChipGroup",
                        "props": {"model": "top_key"},
                        "content": chips,
                    },
                ],
            }
        ]

    @_discover_source_listener
    def discover_source(self, event: Any) -> None:
        """响应宿主探索页的来源广播，把「短剧百科」登记成一个探索来源。"""
        if not self._enabled or _DiscoverMediaSource is None:
            return
        event_data = getattr(event, "event_data", None)
        if event_data is None:
            return
        source = _DiscoverMediaSource(
            name=PLUGIN_NAME,
            # 枚举是开放的，与 get_media_source() 里注册的 key 保持一致
            media_source=MediaSource(MEDIA_SOURCE_KEY),
            mediaid_prefix=MEDIA_ID_PREFIX,
            api_path=self._explore_api_path(),
            filter_params={
                "top_key": self._explore_default_key(),
                "page": 1,
                "count": EXPLORE_DEFAULT_COUNT,
            },
            filter_ui=self._explore_filter_ui(),
        )
        existing = getattr(event_data, "extra_sources", None)
        if existing:
            # 幂等：宿主 reload 会重新广播，同一个来源只登记一次
            for item in existing:
                if getattr(item, "mediaid_prefix", "") == MEDIA_ID_PREFIX:
                    return
            existing.append(source)
        else:
            event_data.extra_sources = [source]

    def api_explore(
        self,
        top_key: str = "",
        page: int = 1,
        count: int = EXPLORE_DEFAULT_COUNT,
    ) -> Any:
        """探索页数据源：按榜单键分页返回短剧列表（``Response[List[MediaInfo]]``）。

        数据以本地为准（榜单快照 / 目录索引），但榜单卡片里只有标题 + 海报 + 集数 ——
        为了让它像 TMDB 来源那样「点开有简介、年份、类型、演员」，这里会对**当前这一页**
        按需回填少量作品详情（``explore_detail_fetch``，默认 2 部；0 = 只读本地）。
        回填走同一个配额闸门并给识别留额度，抓不到就退回卡片字段，绝不阻塞返回。
        """
        medias: List[Any] = []
        if self._enabled:
            keys = [key for key, _ in self._explore_options()]
            wanted = _clean(top_key)
            if wanted not in keys:
                wanted = self._explore_default_key()
            rows = self._explore_items(wanted)
            current = self._as_range(page, 1, 1, 10000)
            size = self._as_range(count, EXPLORE_DEFAULT_COUNT, 1, MAX_EXPLORE_COUNT)
            start = (current - 1) * size
            for row in self._explore_enrich(rows[start : start + size]):
                mediainfo = build_media_info(row, facts=False)
                if mediainfo is None:
                    continue
                payload = _media_to_dict(mediainfo)
                if payload:
                    medias.append(payload)
        return _explore_response(medias)

    # ── HTTP ＋ 配额闸门 ──────────────────────────────────────────

    def _take_slot(self, reserve: int = 0) -> bool:
        """请求前的配额闸门：拿到额度返回 True，否则 False（**不等待**）。

        站点卡的是「一个窗口内几次」而不是「每秒几次」—— 实测把间隔从 1.5 秒放宽到
        10 秒，撞 403 的仍然是第 6 次。所以这里用一个**滚动窗口**建模它：窗口内已用
        次数达到上限就拒绝，等最老那次滑出窗口后自然又可用。

        ``reserve`` 是给后台任务用的：它要求「用完之后至少还剩这么多额度」，
        这样索引任务不会把配额吃光，识别与检索永远有得用。反过来，宁可让后台停手，
        也不能让用户点一次识别就撞 403 —— 那会把整站（含详情页）一起封掉。
        """
        now = time.time()
        window = max(60, self._quota_window_minutes * 60)
        with self._gate_lock:
            if now < self._blocked_until:
                return False
            self._slots = [stamp for stamp in self._slots if now - stamp < window]
            if len(self._slots) + max(0, reserve) >= max(1, self._quota_max_requests):
                return False
            if now < self._next_request_at:
                return False
            self._slots.append(now)
            self._next_request_at = now + self._min_interval
            return True

    def _quota_remaining(self) -> int:
        """当前窗口内还剩几次额度（供状态展示与后台任务判断）。"""
        now = time.time()
        window = max(60, self._quota_window_minutes * 60)
        with self._gate_lock:
            used = len([stamp for stamp in self._slots if now - stamp < window])
        return max(0, self._quota_max_requests - used)

    def _mark_blocked(self) -> None:
        """记录一次风控命中，进入冷却，并写一条日志。

        正常情况下配额闸门会让我们**在撞到之前**就停手；真撞上了说明站点策略变了，
        或窗口估计得偏大 —— 冷却 + 记日志，让用户在面板上看得见。
        """
        now = time.time()
        with self._gate_lock:
            self._blocked_at = now
            self._blocked_until = now + self._cooldown_minutes * 60
            self._next_request_at = self._blocked_until
        self._stats["blocked_count"] = int(self._stats.get("blocked_count") or 0) + 1
        logger.warning(
            f"{PLUGIN_NAME} 撞到站点风控（403），暂停请求 {self._cooldown_minutes} 分钟后再试"
        )

    def _request(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        reserve: int = 0,
    ) -> Any:
        """发起一次 GET，失败返回 None（绝不抛异常打断宿主链路）。"""
        if _RequestUtils is None:  # pragma: no cover - 极端兜底
            logger.warning(f"{PLUGIN_NAME} 宿主未提供 HTTP 入口")
            return None
        if not self._take_slot(reserve=reserve):
            logger.debug(f"{PLUGIN_NAME} 配额闸门拒绝了本次请求：{url}")
            return None
        headers = {
            "User-Agent": _USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
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
        reserve: int = 0,
    ) -> Tuple[str, Optional[int]]:
        """取页面正文与状态码。

        **不吞状态码**：本站在配额耗尽时对所有路径返回 403 + ``Just a moment...``，
        只有拿到状态码才分得清「被 Cloudflare 挡了」与「这个地址本来就没内容」，
        前者必须触发冷却而不是重试。
        """
        response = self._request(url, params=params, reserve=reserve)
        if response is None:
            return "", None
        status = getattr(response, "status_code", None)
        text = getattr(response, "text", "") or ""
        if is_cloudflare_challenge(text, status):
            self._mark_blocked()
            return "", status
        if status is not None and status >= 400:
            logger.debug(f"{PLUGIN_NAME} {url} 返回 {status}")
            return "", status
        self._stats["ok_count"] = int(self._stats.get("ok_count") or 0) + 1
        return text, status

    def _browser_fetch(self, url: str, params: Optional[Dict[str, Any]] = None) -> str:
        """用宿主浏览器仿真取页面（**不过配额闸门** —— 它走的是另一条通道）。

        宿主 ``app.sdk.browser`` 内部是 cloakbrowser（带 ``CLOAKBROWSER_HUMANIZE``
        等反检测开关），能跑掉 Cloudflare 的 JS 挑战；但这一步在 NAS 上
        **尚未验证稳定**，所以整段都包在 try 里，失败一律返回空串。
        """
        if _launch_browser_context is None:
            logger.debug(f"{PLUGIN_NAME} 宿主未提供浏览器仿真入口")
            return ""
        target = url
        if params:
            target = f"{url}?{urllib.parse.urlencode(params)}"
        context = None
        try:
            context = _launch_browser_context(headless=True)
            page = context.new_page()
            page.goto(target, wait_until="domcontentloaded", timeout=max(5, self._timeout) * 1000)
            deadline = time.time() + _BROWSER_CHALLENGE_WAIT
            html = ""
            while time.time() < deadline:
                html = page.content() or ""
                if not is_cloudflare_challenge(html, None):
                    return html
                page.wait_for_timeout(1500)
            logger.debug(f"{PLUGIN_NAME} 浏览器未能在 {_BROWSER_CHALLENGE_WAIT}s 内解除挑战页")
            return ""
        except Exception as err:
            logger.debug(f"{PLUGIN_NAME} 浏览器取页失败 {target}：{err}")
            return ""
        finally:
            if context is not None:
                try:
                    context.close()
                except Exception:  # pragma: no cover - 关闭失败不影响结果
                    pass

    # ── 持久化 ────────────────────────────────────────────────────

    def _load_state(self) -> None:
        """把索引 / 榜单快照从宿主数据目录读回内存（读不到就用空值）。"""
        self._index = self._read_data(_DATA_INDEX, {}) or {}
        self._index_state = self._read_data(_DATA_INDEX_STATE, {}) or {}
        self._top_cache = self._read_data(_DATA_TOP, {}) or {}
        if not isinstance(self._index, dict):
            self._index = {}
        if not isinstance(self._index_state, dict):
            self._index_state = {}
        if not isinstance(self._top_cache, dict):
            self._top_cache = {}

    def _save_state(self) -> None:
        """把索引 / 榜单快照写回宿主数据目录（失败只记日志，不影响主链路）。"""
        for key, value in (
            (_DATA_INDEX, self._index),
            (_DATA_INDEX_STATE, self._index_state),
            (_DATA_TOP, self._top_cache),
        ):
            self._write_data(key, value)

    def _read_data(self, key: str, default: Any) -> Any:
        """宿主 ``get_data`` 的稳健包装（不同版本签名略有差异）。"""
        try:
            return self.get_data(key)
        except TypeError:  # pragma: no cover - 老版本签名
            try:
                return self.get_data(key, self.__class__.__name__)
            except Exception:
                return default
        except Exception as err:  # pragma: no cover - 数据损坏
            logger.debug(f"{PLUGIN_NAME} 读取 {key} 失败：{err}")
            return default

    def _write_data(self, key: str, value: Any) -> None:
        """宿主 ``save_data`` 的稳健包装。"""
        try:
            self.save_data(key, value)
        except TypeError:  # pragma: no cover - 老版本签名
            try:
                self.save_data(key, value, self.__class__.__name__)
            except Exception as err:
                logger.debug(f"{PLUGIN_NAME} 写入 {key} 失败：{err}")
        except Exception as err:  # pragma: no cover - 磁盘异常
            logger.debug(f"{PLUGIN_NAME} 写入 {key} 失败：{err}")

    # ── 缓存 ─────────────────────────────────────────────────────

    def _cache_get(self, key: str) -> Any:
        """命中且未过期时返回缓存值，否则 None。"""
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
        """写入缓存，并把缓存规模压在合理范围。"""
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
            "scan_pages": DEFAULT_SCAN_PAGES,
            "index_enabled": True,
            "index_pages_per_run": DEFAULT_INDEX_PAGES_PER_RUN,
            "index_max_pages": DEFAULT_INDEX_MAX_PAGES,
            "interval_minutes": DEFAULT_INTERVAL_MINUTES,
            "min_interval": DEFAULT_MIN_INTERVAL,
            "quota_window_minutes": DEFAULT_QUOTA_WINDOW_MINUTES,
            "quota_max_requests": DEFAULT_QUOTA_MAX_REQUESTS,
            "cooldown_minutes": DEFAULT_COOLDOWN_MINUTES,
            "timeout": DEFAULT_TIMEOUT,
            "cache_ttl": DEFAULT_CACHE_TTL,
            "use_browser_search": False,
            "proxy": False,
            "top_keys": list(DEFAULT_TOP_KEYS),
            "explore_detail_fetch": EXPLORE_DETAIL_FETCH_DEFAULT,
            "detail_facts": True,
        }

    def get_form(self) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """组装配置表单与默认配置（vuetify 渲染模式）。"""
        return [
            {
                "component": "VForm",
                "content": [
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12},
                                "content": [
                                    {
                                        "component": "VAlert",
                                        "props": {
                                            "type": "info",
                                            "variant": "tonal",
                                            "text": (
                                                "启用后，「短剧百科」会作为一个媒体数据源注册到 "
                                                "MoviePilot，与 TMDB / 豆瓣同级：识别、刮削、搜索时"
                                                "都能显式选择它。详情页（演员阵容、剧照、集数、出品方）"
                                                "按作品 ID 直取，稳定可靠；**片名检索走本地目录索引** —— "
                                                "站内检索被 Cloudflare 挡住，且站点配额极紧，"
                                                "所以索引由后台任务小步抓取、断点续爬。"
                                            ),
                                        },
                                    }
                                ],
                            }
                        ],
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 6},
                                "content": [
                                    {
                                        "component": "VSwitch",
                                        "props": {
                                            "model": "enabled",
                                            "label": "启用数据源",
                                            "hint": "关闭后本插件不再响应任何识别与检索请求",
                                            "persistent-hint": True,
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 6},
                                "content": [
                                    {
                                        "component": "VSwitch",
                                        "props": {
                                            "model": "search_in_global",
                                            "label": "参与全局检索",
                                            "hint": "开启后，宿主搜索框不限定来源时也会带出短剧结果",
                                            "persistent-hint": True,
                                        },
                                    }
                                ],
                            },
                        ],
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12},
                                "content": [
                                    {
                                        "component": "VTextField",
                                        "props": {
                                            "model": "domain",
                                            "label": "站点域名",
                                            "placeholder": ORG_DEFAULT_DOMAIN,
                                        },
                                    }
                                ],
                            }
                        ],
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12},
                                "content": [
                                    {
                                        "component": "VDivider",
                                        "props": {"class": "my-2"},
                                    }
                                ],
                            }
                        ],
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 3},
                                "content": [
                                    {
                                        "component": "VSwitch",
                                        "props": {
                                            "model": "index_enabled",
                                            "label": "启用目录索引",
                                            "hint": "关闭后只能靠实时扫描与榜单检索",
                                            "persistent-hint": True,
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 3},
                                "content": [
                                    {
                                        "component": "VTextField",
                                        "props": {
                                            "model": "index_pages_per_run",
                                            "label": "索引每轮页数",
                                            "type": "number",
                                            "hint": f"1 ~ {MAX_INDEX_PAGES_PER_RUN}；每页 30 部",
                                            "persistent-hint": True,
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 3},
                                "content": [
                                    {
                                        "component": "VTextField",
                                        "props": {
                                            "model": "index_max_pages",
                                            "label": "索引页数上限",
                                            "type": "number",
                                            "hint": f"1 ~ {MAX_INDEX_MAX_PAGES}；站内自述共约 1879 页",
                                            "persistent-hint": True,
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 6},
                                "content": [
                                    {
                                        "component": "VSelect",
                                        "props": {
                                            "model": "top_keys",
                                            "label": "榜单快照范围（= 探索页的来源）",
                                            "multiple": True,
                                            "chips": True,
                                            "clearable": True,
                                            "items": [
                                                {"title": label, "value": key}
                                                for key, label in TOP_LISTS.items()
                                            ],
                                            "hint": (
                                                "每个榜单要花一次站点请求配额，"
                                                "默认只刷「热播榜 + 新剧榜」；"
                                                "勾上的榜单会出现在 MoviePilot 探索页"
                                            ),
                                            "persistent-hint": True,
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 3},
                                "content": [
                                    {
                                        "component": "VTextField",
                                        "props": {
                                            "model": "interval_minutes",
                                            "label": "索引轮询间隔（分钟）",
                                            "type": "number",
                                        },
                                    }
                                ],
                            },
                        ],
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 3},
                                "content": [
                                    {
                                        "component": "VTextField",
                                        "props": {
                                            "model": "quota_window_minutes",
                                            "label": "配额窗口（分钟）",
                                            "type": "number",
                                            "hint": "实测站点每窗口只放行几次请求",
                                            "persistent-hint": True,
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 3},
                                "content": [
                                    {
                                        "component": "VTextField",
                                        "props": {
                                            "model": "quota_max_requests",
                                            "label": "窗口内最大请求数",
                                            "type": "number",
                                            "hint": "实测为 5；调大只会更快撞 403",
                                            "persistent-hint": True,
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 3},
                                "content": [
                                    {
                                        "component": "VTextField",
                                        "props": {
                                            "model": "min_interval",
                                            "label": "请求最小间隔（秒）",
                                            "type": "number",
                                            "hint": "不建议小于 2 秒",
                                            "persistent-hint": True,
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 3},
                                "content": [
                                    {
                                        "component": "VTextField",
                                        "props": {
                                            "model": "cooldown_minutes",
                                            "label": "撞风控冷却（分钟）",
                                            "type": "number",
                                            "hint": "命中 403 后暂停请求的时长",
                                            "persistent-hint": True,
                                        },
                                    }
                                ],
                            },
                        ],
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 3},
                                "content": [
                                    {
                                        "component": "VTextField",
                                        "props": {
                                            "model": "scan_pages",
                                            "label": "实时扫描页数",
                                            "type": "number",
                                            "hint": "没有索引时的兜底翻页数",
                                            "persistent-hint": True,
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 3},
                                "content": [
                                    {
                                        "component": "VTextField",
                                        "props": {
                                            "model": "timeout",
                                            "label": "请求超时（秒）",
                                            "type": "number",
                                        },
                                    }
                                ],
                            },
                        ],
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 3},
                                "content": [
                                    {
                                        "component": "VTextField",
                                        "props": {
                                            "model": "cache_ttl",
                                            "label": "详情缓存（秒）",
                                            "type": "number",
                                            "hint": "0 表示不缓存",
                                            "persistent-hint": True,
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 3},
                                "content": [
                                    {
                                        "component": "VSwitch",
                                        "props": {
                                            "model": "use_browser_search",
                                            "label": "浏览器检索（实验）",
                                            "hint": "用宿主浏览器仿真尝试穿过 Cloudflare 打站内检索；未验证稳定",
                                            "persistent-hint": True,
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 3},
                                "content": [
                                    {
                                        "component": "VSwitch",
                                        "props": {
                                            "model": "proxy",
                                            "label": "使用系统代理",
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 3},
                                "content": [
                                    {
                                        "component": "VTextField",
                                        "props": {
                                            "model": "explore_detail_fetch",
                                            "label": "探索页详情回填（部/次）",
                                            "type": "number",
                                            "hint": (
                                                "榜单卡片只有标题和海报；填几就在打开探索页时"
                                                "最多抓几部作品的简介/年份/类型/主演。"
                                                "0 = 完全不额外请求"
                                            ),
                                            "persistent-hint": True,
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 3},
                                "content": [
                                    {
                                        "component": "VSwitch",
                                        "props": {
                                            "model": "detail_facts",
                                            "label": "详情页摘要行",
                                            "hint": (
                                                "在作品详情页「简介」上方显示一行"
                                                "「评分 · 全 N 集 · 主演 X、Y」。"
                                                "宿主的评分区与演职员区只对 TMDB/豆瓣/"
                                                "Bangumi 来源渲染，自定义来源靠这行承载"
                                            ),
                                            "persistent-hint": True,
                                        },
                                    }
                                ],
                            },
                        ],
                    },
                ],
            }
        ], self._default_config()

    def get_page(self) -> List[Dict[str, Any]]:
        """详情页：展示数据源状态、索引进度与配额状态。"""
        state = "已启用" if self._enabled else "未启用"
        indexed = len(self._index)
        next_page = int(self._index_state.get("next_page") or 1)
        total_pages = int(self._index_state.get("total_pages") or 0)
        progress = "未开始"
        if total_pages:
            progress = f"{min(next_page - 1, total_pages)}/{total_pages} 页"
        elif indexed:
            progress = f"已抓 {next_page - 1} 页"

        remaining = max(0, int(self._blocked_until - time.time()))
        if remaining > 0:
            quota = f"冷却中（剩余 {remaining} 秒）"
        else:
            quota = f"窗口内剩余 {self._quota_remaining()}/{self._quota_max_requests} 次"

        with self._cache_lock:
            detail_cached = len([key for key in self._cache if str(key).startswith("detail:")])
        if self._explore_detail_fetch > 0:
            explore_line = (
                f"探索页详情回填：每次最多 {self._explore_detail_fetch} 部"
                f"（已缓存 {detail_cached} 部详情）"
            )
        else:
            explore_line = f"探索页详情回填：已关闭（详情缓存 {detail_cached} 部）"

        return [
            {
                "component": "VRow",
                "content": [
                    {
                        "component": "VCol",
                        "props": {"cols": 12},
                        "content": [
                            {
                                "component": "VAlert",
                                "props": {
                                    "type": "success" if self._enabled else "warning",
                                    "variant": "tonal",
                                    "text": f"数据源状态：{state}；来源标识：{MEDIA_SOURCE_KEY}",
                                },
                            }
                        ],
                    }
                ],
            },
            {
                "component": "VRow",
                "content": [
                    {
                        "component": "VCol",
                        "props": {"cols": 12, "md": 4},
                        "content": [
                            {
                                "component": "VCard",
                                "props": {"variant": "tonal"},
                                "content": [
                                    {
                                        "component": "VCardText",
                                        "text": f"本地索引：{indexed} 部（{progress}）",
                                    }
                                ],
                            }
                        ],
                    },
                    {
                        "component": "VCol",
                        "props": {"cols": 12, "md": 4},
                        "content": [
                            {
                                "component": "VCard",
                                "props": {"variant": "tonal"},
                                "content": [
                                    {
                                        "component": "VCardText",
                                        "text": f"榜单快照：{len(self._top_cache)} 个（{self._top_snapshot_summary()}）",
                                    }
                                ],
                            }
                        ],
                    },
                    {
                        "component": "VCol",
                        "props": {"cols": 12, "md": 4},
                        "content": [
                            {
                                "component": "VCard",
                                "props": {"variant": "tonal"},
                                "content": [
                                    {
                                        "component": "VCardText",
                                        "text": f"站点配额：{quota}",
                                    }
                                ],
                            }
                        ],
                    },
                ],
            },
            {
                "component": "VRow",
                "content": [
                    {
                        "component": "VCol",
                        "props": {"cols": 12},
                        "content": [
                            {
                                "component": "VCard",
                                "props": {"variant": "tonal"},
                                "content": [
                                    {
                                        "component": "VCardText",
                                        "text": explore_line,
                                    }
                                ],
                            }
                        ],
                    },
                    {
                        "component": "VCol",
                        "props": {"cols": 12},
                        "content": [
                            {
                                "component": "VCard",
                                "props": {"variant": "tonal"},
                                "content": [
                                    {
                                        "component": "VCardText",
                                        "text": (
                                            "详情页摘要行：已开启（评分 · 全 N 集 · 主演）"
                                            if self._detail_facts
                                            else "详情页摘要行：已关闭"
                                        ),
                                    }
                                ],
                            }
                        ],
                    },
                ],
            },
            {
                "component": "VRow",
                "content": [
                    {
                        "component": "VCol",
                        "props": {"cols": 12},
                        "content": [
                            {
                                "component": "VCard",
                                "props": {"variant": "outlined"},
                                "content": [
                                    {
                                        "component": "VCardText",
                                        "text": (
                                            "用法：在 MoviePilot 的识别 / 刮削 / 搜索界面里，"
                                            "把媒体来源选为「短剧百科」即可。短剧在 TMDB 与豆瓣上"
                                            "常常没有条目，本数据源补的正是这一段。"
                                            "片名检索依赖本地目录索引，索引由后台任务逐页建立，"
                                            "可在「配置」里调大每轮页数加快进度。"
                                            "浏览入口在 MoviePilot 的「探索」菜单："
                                            "那里会多出一个「短剧百科」来源，榜单可切换"
                                            "（刷哪些榜单由「配置 → 榜单快照范围」决定，"
                                            "多勾几个就有更多来源可选）。"
                                            "其它插件也能直接调它：self.run_module(\"recognize_media\", "
                                            "media_source=\"duanjubaike\", media_id=\"org:40105\")；"
                                            "不想依赖宿主模型时用 GET /plugin/ShortDramaBaikeSource/recognize "
                                            "拿纯 JSON。"
                                        ),
                                    }
                                ],
                            }
                        ],
                    }
                ],
            },
        ]

    def get_api(self) -> List[Dict[str, Any]]:
        """注册排障接口 + **跨插件消费接口**。

        ``/recognize`` 是给其它插件 / 外部脚本用的稳定出口：它只回纯 JSON，
        与宿主 ``MediaInfo`` 的字段版本解耦。
        """
        return [
            {
                "path": EXPLORE_PATH,
                "endpoint": self.api_explore,
                "methods": ["GET"],
                "auth": "apikey",
                "summary": "宿主探索页数据源",
                "description": (
                    "按榜单键（hot / new / … / index）分页返回短剧列表，"
                    "供 MoviePilot 探索页消费；数据取自本地快照与索引，"
                    "并对当前页按需回填少量作品详情（explore_detail_fetch 控制条数，0 = 不回填）。"
                ),
            },
            {
                "path": "/recognize",
                "endpoint": self.api_recognize,
                "methods": ["GET"],
                "auth": "apikey",
                "summary": "识别一部短剧（跨插件调用的稳定出口）",
                "description": (
                    "给 media_id（如 org:40105）或 keyword（片名）返回一条作品记录："
                    "片名/年份/海报/集数/时长/标签/演员等，全部为纯 JSON。"
                ),
            },
            {
                "path": "/probe",
                "endpoint": self.api_probe,
                "methods": ["GET"],
                "auth": "apikey",
                "summary": "数据源连通性自检",
                "description": "请求 robots.txt / 目录页 / 榜单 / 详情页，返回状态码与解析条数。",
            },
            {
                "path": "/search",
                "endpoint": self.api_search,
                "methods": ["GET"],
                "auth": "apikey",
                "summary": "按片名试搜短剧",
                "description": "用给定片名走一遍本插件的检索链路，返回候选与匹配分。",
            },
            {
                "path": "/index",
                "endpoint": self.api_index,
                "methods": ["GET"],
                "auth": "apikey",
                "summary": "手动推进本地目录索引",
                "description": "按给定页数推进一次索引抓取（受站点配额限制，超额会自动停手）。",
            },
            {
                "path": "/status",
                "endpoint": self.api_status,
                "methods": ["GET"],
                "auth": "apikey",
                "summary": "查看索引与配额状态",
                "description": "返回本地索引条数、抓取进度、榜单快照与冷却剩余时间。",
            },
        ]

    def api_recognize(self, media_id: str = "", keyword: str = "", year: str = "") -> Dict[str, Any]:
        """见 ``/recognize``：给 ``media_id`` 或片名，回一条**纯 JSON** 作品记录。

        其它插件调用本插件有三条路（都在模块 docstring 里写了例子）：

        1. ``self.run_module("recognize_media" | "search_medias" | "obtain_images", …)``
           —— 宿主分发器会把请求送进本插件（标准姿势，返回宿主模型）；
        2. 本 HTTP 接口 —— 返回纯 JSON，适合脚本 / 外部程序；
        3. 智能体工具 ``short_drama_identify``—— 给 AI 智能体用。

        ``media_id`` 优先：给了就直接取详情页；只给片名则先在本地索引里匹配，
        取最高分那条再补详情。``origin`` 字段会说明数据是详情页还是仅索引。
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
                item = self._fetch_detail(best.get("media_id")) or best
                if "actors" not in (item or {}):
                    origin = "index"
        if not item:
            return {
                "success": False,
                "message": "未命中（片名对不上或本地索引还没抓到这部）",
                "record": None,
            }
        return {"success": True, "record": build_public_record(item, origin)}


    def api_probe(self, keyword: str = "世子爷") -> Dict[str, Any]:
        """连通性自检（供配置页排障用）。"""
        report: Dict[str, Any] = {
            "enabled": self._enabled,
            "media_source": MEDIA_SOURCE_KEY,
            "domain": self._domain,
            "media_info_model": getattr(_HostMediaInfo, "__name__", None),
            "browser_available": _launch_browser_context is not None,
        }

        robots = self._request(f"{self._domain}/robots.txt")
        report["robots"] = {
            "status": getattr(robots, "status_code", None),
            "disallow_search": "drama/search" in (getattr(robots, "text", "") or ""),
        }

        catalog_html = self._fetch_catalog_page(1)
        catalog_cards = parse_org_cards(catalog_html, self._domain) if catalog_html else []
        report["catalog"] = {
            "url": f"{self._domain}{CATALOG_PATH}",
            "cards": len(catalog_cards),
            "total_pages": parse_org_total_pages(catalog_html) if catalog_html else 0,
            "sample": [card["title"] for card in catalog_cards[:5]],
        }

        top_html, top_status = self._get(f"{self._domain}{TOP_PATH.format(key=DEFAULT_TOP_KEY)}")
        top_cards = parse_org_cards(top_html, self._domain) if top_html else []
        report["top"] = {
            "key": DEFAULT_TOP_KEY,
            "status": top_status,
            "cards": len(top_cards),
            "sample": [card["title"] for card in top_cards[:5]],
        }

        if catalog_cards:
            first = catalog_cards[0]["native_id"]
            detail = self._fetch_detail(f"org:{first}", use_cache=False)
            report["detail"] = {
                "media_id": f"org:{first}",
                "title": (detail or {}).get("title"),
                "actors": len((detail or {}).get("actors") or []),
                "episodes": (detail or {}).get("episode_count"),
                "stills": len((detail or {}).get("stills") or []),
            }

        report["ok"] = bool(report["catalog"]["cards"] or report["top"]["cards"])
        report["quota"] = self._quota_state()
        report["stats"] = dict(self._stats)
        return report

    def api_search(self, keyword: str = "", year: str = "") -> Dict[str, Any]:
        """按片名试搜（供配置页排障用）。"""
        query = _clean(keyword)
        if not query:
            return {"success": False, "message": "缺少 keyword 参数", "candidates": []}
        candidates = self._search_by_title(query, target_year=_clean(year) or None)
        return {
            "success": bool(candidates),
            "keyword": query,
            "count": len(candidates),
            "indexed": len(self._index),
            "candidates": [
                {
                    "media_id": candidate.get("media_id"),
                    "title": candidate.get("title"),
                    "score": candidate.get("_score"),
                    "poster": candidate.get("poster"),
                    "episode_count": candidate.get("episode_count"),
                }
                for candidate in candidates[:MAX_CANDIDATES]
            ],
        }

    def api_index(self, pages: int = 0, reason: str = "manual") -> Dict[str, Any]:
        """手动推进本地目录索引（配置页 / 外部脚本可用）。

        ``pages`` 省略（或传 0）时用配置里的「每轮页数」。这里**不做上限放宽** ——
        配额闸门在 ``_request`` 里，所以就算传了 200 页，撞到 403 也会立刻停手。
        """
        if not self.get_state():
            return {"success": False, "message": "插件未启用"}
        # ``pages or …``：0 / None 都视为「用配置值」，否则 _as_range 会把 0 钳成下限 1
        wanted = self._as_range(
            pages or self._index_pages_per_run,
            self._index_pages_per_run,
            1,
            MAX_INDEX_PAGES_PER_RUN,
        )
        return self.build_index_step(pages=wanted, reason=reason)

    def api_status(self) -> Dict[str, Any]:
        """查看索引与配额状态。"""
        return {
            "enabled": self._enabled,
            "indexed": len(self._index),
            "index_state": dict(self._index_state),
            "top_lists": sorted(self._top_cache),
            "quota": self._quota_state(),
            "stats": dict(self._stats),
            "browser_available": _launch_browser_context is not None,
        }

    def _quota_state(self) -> Dict[str, Any]:
        """把配额闸门的内部状态整理成可读形式。"""
        now = time.time()
        return {
            "cooling_down": self._blocked_until > now,
            "remaining_seconds": max(0, int(self._blocked_until - now)),
            "window_minutes": self._quota_window_minutes,
            "max_requests": self._quota_max_requests,
            "remaining_requests": self._quota_remaining(),
            "min_interval": self._min_interval,
            "blocked_count": int(self._stats.get("blocked_count") or 0),
            "ok_count": int(self._stats.get("ok_count") or 0),
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
    def _as_bool(value: Any, default: bool) -> bool:
        """把配置值稳健地转成布尔。"""
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        return str(value).strip().lower() in {"1", "true", "yes", "on", "是"}

    @staticmethod
    def _as_range(value: Any, default: int, low: int, high: int) -> int:
        """把配置值钳到闭区间内；非法值回落默认。"""
        try:
            number = int(str(value).strip())
        except (TypeError, ValueError):
            return default
        return max(low, min(high, number))

    @staticmethod
    def _as_float(value: Any, default: float, low: float, high: float) -> float:
        """把配置值钳到闭区间内（浮点版）；非法值回落默认。"""
        try:
            number = float(str(value).strip())
        except (TypeError, ValueError):
            return default
        return max(low, min(high, number))

    @staticmethod
    def _as_top_keys(value: Any) -> List[str]:
        """清洗「要刷哪些榜单」配置：只留下 ``TOP_LISTS`` 里的键，去重保序。

        配置可能来自多选控件（列表）、逗号串（老值）或空 —— 一律兜底到
        ``DEFAULT_TOP_KEYS``，免得用户清空后连热播榜都不刷了。
        """
        if isinstance(value, str):
            raw = [item for item in re.split(r"[,\s]+", value) if item]
        elif isinstance(value, (list, tuple, set)):
            raw = [str(item) for item in value]
        else:
            raw = []
        keys: List[str] = []
        for item in raw:
            key = item.strip()
            if key in TOP_LISTS and key not in keys:
                keys.append(key)
        return keys or list(DEFAULT_TOP_KEYS)

    @staticmethod
    def _as_domain(value: Any, default: str) -> str:
        """规范化站点域名配置（补协议、去尾斜杠）。"""
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
