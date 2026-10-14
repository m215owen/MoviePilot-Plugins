"""短剧百科数据源 · 跨模块共享的常量与站点契约。

只放「多个模块都要用」的常量：插件元数据、数据源契约、URL 形态、默认值上限、
搜索引擎参数。站点 DOM 的解析正则与解析函数在 :mod:`parser`，数据库模型在
:mod:`store`，宿主的媒体模型映射在 :mod:`payload`。
"""
from __future__ import annotations

import re
from typing import Tuple

# ── 插件元数据（须与 package.v3.json 保持一致） ──────────────────────
PLUGIN_NAME = "短剧百科数据源"
PLUGIN_ICON = (
    "https://raw.githubusercontent.com/m215owen/MoviePilot-Plugins/main/icons/"
    "ShortDramaBaikeSource.png"
)
PLUGIN_VERSION = "2.1.1"

# ── 数据源契约 ────────────────────────────────────────────────────
# 规范写法是宿主 ``MediaSource`` 枚举值；另外两个别名是为了让**其它插件**按
# 「插件 ID」或「域名简称」点名时也能命中，不必去查枚举值的准确拼写。
MEDIA_SOURCE_KEY = "duanjubaike"
MEDIA_SOURCE_LABEL = "短剧百科"
MEDIA_SOURCE_ALIASES = frozenset({"duanjubaike", "shortdramabaike", "shortdramabaikesource"})

ORG_DEFAULT_DOMAIN = "https://duanjubaike.org"

# 站点路径（``{id}`` 为占位）
DETAIL_PATH = "/zh-Hans/drama/{id}"
ACTOR_PATH = "/zh-Hans/actor/{id}"

# 站点只有简体 / 繁体两套页面，**必须抓简体**。实测：``/actor/371`` 与
# ``/zh-Hant/actor/371`` 都会被 301 到繁体页，而繁体页里
# 1) 作品链接写成 ``/zh-Hant/drama/…``（卡片正则只认简体前缀 ⇒ 静默解析出 **0 部作品**），
# 2) 统计标签是「熱度 / 評分」（简体正则匹配不到 ⇒ ``heat`` 恒为 null）。
# 所以地址在**抓取与入库前**一律归一化到这个前缀（见 ``parser.canonical_page_url``）。
LANG_PATH = "/zh-Hans"

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

# ── 默认值 / 上限 ─────────────────────────────────────────────────
DEFAULT_TIMEOUT = 15
DEFAULT_CACHE_TTL = 604800          # 详情页内容基本不变，缓存 7 天
MAX_CANDIDATES = 12                 # 一个关键词最多回多少条作品候选
MAX_ACTOR_CANDIDATES = 8            # 一个关键词最多回多少位演员候选
# 每个关键词在 URL 库里最多留几条 URL（多季 / 同名 / 演员重名都可能有多条）
MAX_URLS_PER_KEYWORD = 12
# 入库门槛：搜索引擎给的标题必须与**搜索的剧名完全相等**（``parser._match_title`` 满分
# 100）才建库。只按「包含关系」（60 / 40 分）放行是危险的 —— 引擎召回不稳，实测搜
# 「相亲对象是迟来的心动」返回的是「深渊之花」「照片是舍友，網戀對象是繼承人」等五部
# 毫不相干的剧；一旦按搜索词入库，库里就多出一批「键是这个搜索词、内容却是别的剧」
# 的错行，下次搜同一个词虚报「库命中 5」。**宁可漏，不可错** —— 漏了下回再搜一次就
# 补上，错了会一直污染库。
EXACT_TITLE_SCORE = 100

# 一次检索里最多为几条「标题不可信」的候选**补抓一次简体页**拿真标题（见
# ``parser.href_points_to_simplified``）。引擎三到五成结果给的是繁体标题，不换掉就会
# 跟简体关键词字面对不上、被当无关候选丢掉；补抓有 TTL 缓存，之后识别零成本。
DISCOVER_TITLE_ENRICH_LIMIT = 3
# 自检（/probe）在「检索没命中」时用来兜底的详情样本：实测存在且字段完整的作品
PROBE_SAMPLE_MEDIA_ID = "org:45982"

# ── 搜索引擎（URL 发现通道）────────────────────────────────────────
# 站内检索被 Cloudflare 挡住，于是改问搜索引擎：``site:<域名> <关键词>`` 返回的
# 每一条结果都是**带完整 URL 的结构化行**（``title`` / ``href`` / ``body``，实测
# ddgs 9.14.4），``href`` 就是详情页或演员页地址，路径末尾的数字即站点 ID。
WEB_INDEX_BACKENDS = ("auto", "duckduckgo", "yandex", "google", "brave", "mojeek")
DEFAULT_WEB_INDEX_BACKEND = "auto"
WEB_INDEX_MAX_RESULTS = 10          # 单次取多少条结果（实测 10 条足够覆盖多季）
WEB_INDEX_TIMEOUT = 25              # 单次检索超时（秒）
WEB_INDEX_MIN_INTERVAL = 3.0        # 相邻两次检索的最小间隔（秒），引擎不接受高频调用

# 搜索结果标题自带站点后缀，形如 ``<标题> - <中间段> - 短剧百科``。实测出现过的中间段有
# 「短剧」「短剧演员」「剧照」三种（繁体对应「短劇」「短劇演員」「劇照」），以后还可能加
# 新的（演员动态 / 剧集列表 …）—— 所以**不要把中间段写死成枚举**，用一条通用式：
# 剥掉末尾的「`- 若干短段 - 短剧百科`」，允许 0~2 个中间段。
#   「片名 - 短剧 - 短剧百科」    → 片名
#   「姓名 - 短剧演员 - 短剧百科」→ 姓名
#   「片名 - 剧照 - 短剧百科」    → 片名
#   「真人短剧 - 短剧百科」       → 真人短剧（站点目录页的标题）
# ⚠️ 必须有前置分隔符才剥：「重生之短剧百科」这种正常片名不该被动。
WEB_INDEX_TITLE_SUFFIX_RE = re.compile(
    r"\s*[-|｜]\s*(?:[^\s\-|｜]{1,16}\s*[-|｜]\s*)*(?:短剧|短劇)百科\s*$"
)
# 有些后端还会在标题末尾再挂一个裸域名（实测：「魏珂 - 短劇演員 - 短劇百科 - duanjubaike.org」），
# 同样要剥 —— 留着它会让标签变成一整条串，与关键词打分时长得像个别人物
WEB_INDEX_HOST_SUFFIX_RE = re.compile(
    r"\s*[-|｜]\s*(?:www\.)?[a-z0-9-]+(?:\.[a-z0-9-]+)+\s*$",
    re.I,
)
# 只认作品详情页：``/drama/<数字>``（可带 zh-Hans / zh-Hant 前缀），排除 /photos、/actor 等
WEB_INDEX_DETAIL_RE = re.compile(r"^/(?:zh-Hans|zh-Hant)?/?drama/(?P<id>\d+)/?$")
# 只认演员页：``/actor/<数字>``（可带 zh-Hans / zh-Hant 前缀）
WEB_INDEX_ACTOR_RE = re.compile(r"^/(?:zh-Hans|zh-Hant)?/?actor/(?P<id>\d+)/?$")

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
