"""短剧百科数据源 · 跨模块共享的常量与站点契约。

只放「多个模块都要用」的常量：插件元数据、数据源契约、URL 形态、默认值上限、
搜索引擎参数。站点 DOM 的解析正则与解析函数在 :mod:`parser`，数据库模型在
:mod:`store`，宿主的媒体模型映射在 :mod:`payload`，宿主**分类协议**的声明与事实
在 :mod:`classification`（本模块只提供那份字段表当唯一事实来源）。
"""
from __future__ import annotations

import re
from typing import Any, Dict, Tuple

# ── 插件元数据（须与 package.v3.json 保持一致） ──────────────────────
PLUGIN_NAME = "短剧百科数据源"
PLUGIN_ICON = (
    "https://raw.githubusercontent.com/m215owen/MoviePilot-Plugins/main/icons/"
    "ShortDramaBaikeSource.png"
)
# 插件仍在测试期：版本号定为首版，不跟随迭代次数往上堆
PLUGIN_VERSION = "1.0.0"

# ── 数据源契约 ────────────────────────────────────────────────────
# 来源标识 = 宿主 ``MediaSource`` 枚举值（``MediaSource("duanju")`` 动态构造）。
# 取名与「媒体 ID 前缀」同源（``duanju`` ↔ 作品号 ``60017``），与 TMDB 的
# ``themoviedb`` ↔ ``603`` 一个姿势 —— 一眼就能对上是哪个来源的编号。
MEDIA_SOURCE_KEY = "duanju"
MEDIA_SOURCE_LABEL = "短剧百科"
# ⚠️ ``duanjubaike`` 是**早期版本用过的来源标识**，必须继续接受：
#   * 别的插件（如 ShortDramaActorSubscribe）里把 ``duanjubaike`` 写死在常量里；
#   * 宿主 ``app.env`` 的 ``SEARCH_SOURCE`` 里也留着一份；
#   * 旧订阅 / 旧识别缓存里可能存着按它落库的身份。
# 后两个别名是为了让消费方能按「插件 ID」或「域名简称」点名，不必去查枚举拼写。
MEDIA_SOURCE_ALIASES = frozenset(
    {"duanju", "duanjubaike", "shortdramabaike", "shortdramabaikesource"}
)

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

# 媒体 ID 就是**站点原生数字**（``media_id = "60017"``）—— 不带前缀，与
# TMDB 的 ``603`` / 豆瓣的 ``1234567`` 同款。宿主只会把 (``media_source``,
# ``media_id``) 当成一对「来源 + 该来源的编号」，前缀对宿主没有任何意义，
# 反而会让 ID 与来源标识重复表达同一件事。
#
# ⚠️ 历史上用过 ``duanju:`` / ``org:`` 两种前缀（早期把来源信息塞进 ID 里），
# 别的插件与旧识别缓存里可能还留着按它们存下来的身份 —— 解析时**一律接受**，
# 见 :data:`LEGACY_MEDIA_ID_PREFIXES`；新产出一律是裸数字。
LEGACY_MEDIA_ID_PREFIXES: Tuple[str, ...] = ("duanju", "org")
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
# 缓存有效期（秒）配置项的默认值：**0 = 跟随宿主** —— 取系统设置「单条元数据识别缓存
# 有效期」（``META_CACHE_EXPIRE``，单位小时，0/未填时宿主按 24 小时、大内存模式 72 小时计）。
# 非 0 时以本项显式覆盖，用来在排障或站点改版期临时拉长/缩短插件自己的缓存。
DEFAULT_CACHE_TTL = 0
MAX_CANDIDATES = 12                 # 一个关键词最多回多少条作品候选
MAX_ACTOR_CANDIDATES = 8            # 一个关键词最多回多少位演员候选
# 演员页「全部作品补详情」的并发线程数。
# 为什么必须并发：URL 库只存 URL 不存数据，所以打开一位没缓存过的演员要把**每一部**
# 演员作品补全的**默认并发线程数**（配置项 ``enrich_workers``，1~32 可调）。
# 一位没缓存过的演员要把名下每一部作品的详情页都抓一遍 —— 实测 46 部串行要 **124s**
# （每部含一次站点页 + 一次 TMDB 身份查询）。站点对详情页**不设风控**（实测 12 并发
# 全部 200、无 challenge，12 个页面 3.53s vs 串行约 12s），所以并发是安全的；取 8 而
# 不拉满，是给「同一台机器上还有别的任务在出网」留余量。
ENRICH_WORKERS = 8
# 一次识别/检索最多试几个候选名：中文名 + 它的简体写法（繁体文件名才会用到第二条）。
# 照宿主 TMDB 源「逐个候选试、第一个有结果就停」的口径，但**不照抄它的英文候选** ——
# 本站只收中文短剧，英文名既搜不到又要白白打一次搜索引擎（引擎侧有 3 秒最小间隔）。
MAX_META_KEYWORDS = 2
# 每个关键词在 URL 库里最多留几条 URL（多季 / 同名 / 演员重名都可能有多条）
MAX_URLS_PER_KEYWORD = 12
# 入库门槛：搜索引擎给的标题必须与**搜索的剧名完全相等**（``parser._match_title`` 满分
# 100）才建库。只按「包含关系」（60 / 40 分）放行是危险的 —— 引擎召回不稳，实测搜
# 「相亲对象是迟来的心动」返回的是「深渊之花」「照片是舍友，網戀對象是繼承人」等五部
# 毫不相干的剧；一旦按搜索词入库，库里就多出一批「键是这个搜索词、内容却是别的剧」
# 的错行，下次搜同一个词虚报「库命中 5」。**宁可漏，不可错** —— 漏了下回再搜一次就
# 补上，错了会一直污染库。
EXACT_TITLE_SCORE = 100

# 演员档案里的作品条目在**演员页**上只是卡片摘要：题材标签只印 1~3 个（实测《失控交易》
# 卡片上只有「爱情」，详情页有 5 个），也没有版权方 / 简介 / 剧照 / 首播 —— 这些都是
# **作品页有、演员页没有**的缺口。所以插件把演员页的**每一部**作品都补抓一次详情页，
# 整条记录灌进作品条目（详见 ``ShortDramaBaikeSource._enrich_works``）：对外（面板 /
# `/actor` / 跨插件）「演员页带的作品数据」与作品页那条记录**字段完全一致**，
# 没有开关可关 —— 不补就缺字段。详情有 TTL 缓存（默认 7 天），重复打开不出网。
# 自检（/probe）在「检索没命中」时用来兜底的详情样本：实测存在且字段完整的作品
PROBE_SAMPLE_MEDIA_ID = "45982"

# ── 分类扩展字段（宿主「媒体分类策略」用）──────────────────────────
# 这一段是**事实来源**：声明与事实两条路径都读它（白名单也是它）。
# 为什么要声明扩展字段、协议怎么探测、降级怎么走，见 :mod:`classification` 的模块头
# —— 那儿对齐的是官方文档 ``docs/faq/19-register-media-source.md`` 第 4 节与
# ``docs/faq/20-media-classification.md`` 第 2 节。
CLASSIFICATION_FIELD_PREFIX = f"extensions.{MEDIA_SOURCE_KEY}."
# 三个字段：一个恒真（兜底，保证规则一定命中）+ 两个站点真实字段（便于以后细分）。
# ⚠️ 值类型与操作符必须匹配宿主 ``domain/classification/fields.VALUE_TYPE_OPERATORS``
# （v3.1.5 逐条核对），否则插件加载时**整份**声明会被拒
# （``PluginClassificationDeclarationError``）—— 连恒真那条也一起丢。
# 站点只有一套页面（简体页按电视剧投放），所以三个字段的 ``media_types`` 都是「电视剧」；
# 不填宿主也会回落成来源的媒体类型，显式写出来是为了让面板上的适用范围一目了然。
_MEDIA_TYPE_TV: Tuple[str, ...] = ("电视剧",)
CLASSIFICATION_FIELDS: Tuple[Dict[str, Any], ...] = (
    {
        "id": f"{CLASSIFICATION_FIELD_PREFIX}is_short_drama",
        "label": "短剧百科收录",
        "group": "短剧百科",
        "description": "由短剧百科识别成功的条目；本站只收录短剧，因此恒为真",
        "value_type": "boolean",
        "operators": ["is_true", "is_false", "exists", "not_exists"],
        "media_types": list(_MEDIA_TYPE_TV),
    },
    {
        "id": f"{CLASSIFICATION_FIELD_PREFIX}kind",
        "label": "短剧形态（真人 / AI）",
        "group": "短剧百科",
        "description": "详情页角标：真人短剧 / AI短剧；页面没给出角标时不带这一条",
        "value_type": "string",
        "operators": ["equals", "not_equals", "in", "not_in", "exists", "not_exists"],
        # ⚠️ 刻意**不用** ``enum``：站点角标是抓来的、随时可能多出第三种（动态漫画 /
        # 互动剧…），而 ``enum`` + ``allow_custom_values=False`` 会让宿主把目录外的
        # 新值当「值不符合声明」整条丢弃 ⇒ 分类规则静默漏命中。这里当**开放字符串**，
        # ``options`` 只作前端候选提示，``allow_custom_values`` 保持默认 True。
        "options": [
            {"value": "真人短剧", "label": "真人短剧"},
            {"value": "AI短剧", "label": "AI短剧"},
        ],
        "media_types": list(_MEDIA_TYPE_TV),
    },
    {
        "id": f"{CLASSIFICATION_FIELD_PREFIX}tags",
        "label": "短剧百科题材标签",
        "group": "短剧百科",
        "description": "详情页的题材标签（都市 / 逆袭 / 系统 …）",
        "value_type": "string_list",
        "operators": ["contains_any", "contains_all", "contains_none", "exists", "not_exists"],
        "media_types": list(_MEDIA_TYPE_TV),
    },
)

# ⚠️ 宿主详情页（``/media``）里，评分星条 / 状态 / 上映日期 / 出品方 / 演职员区**全部**挂在
# ``tmdb_id``/``douban_id``/``bangumi_id``/``anilist_id`` 四个分支上（前端 ``media-*.js``
# 逐块核对：v3.1.5 与 v3.1.6 一致）—— 插件来源没有这些 ID，那些区块就整块不渲染。
# 无条件的只有：海报 / 背景图 / 标题 / 年份 / ``runtime``（缺则 ``episode_run_time[0]``）
# ``| genres`` / 简介 / 媒体库与订阅按钮。**别用 ``tagline`` 往简介上方塞摘要**
# （2026-10-15 用户明确不要），也不要伪造 ``tmdb_id``。
# 上映日期另有一处能显示：``MediaInfoDialog``（种子/识别的结果弹窗）无条件读
# ``release_date || year``。

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
# 作品**图集页**：``/drama/<数字>/photos`` —— 它是详情页的子路径，**作品 ID 完全相同**，
# 所以它是「这部作品存在」的等价证据。实测（2026-10-15）搜「难驯」时引擎一条详情页都没给，
# 只给了 ``/zh-Hans/drama/17139/photos``（标题「难驯 - 剧照 - 短剧百科」）—— 以前它被当
# 「图集页」整行剔除，于是这部作品**在插件里永远搜不到**（用户看到的正是「库里只有作品 0」）。
# 现在认它，并在 :func:`parser.canonical_page_url` 里归一化成作品页地址再入库。
WEB_INDEX_GALLERY_RE = re.compile(r"^/(?:zh-Hans|zh-Hant)?/?drama/(?P<id>\d+)/photos/?$")
# 只认演员页：``/actor/<数字>``（可带 zh-Hans / zh-Hant 前缀）
WEB_INDEX_ACTOR_RE = re.compile(r"^/(?:zh-Hans|zh-Hant)?/?actor/(?P<id>\d+)/?$")

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

# ── 文件名去噪 ────────────────────────────────────────────────────
# 宿主把**整个文件名**塞进 ``MetaInfo.title``（实测 ``雾锁情迷 - S01E71.mp4`` →
# ``title = '雾锁情迷 - S01E71.mp4'``、``name = '雾锁情迷'``）。这种脏串拿去问引擎、
# 查 URL 库、写检索节流键都会落空 —— 库里明明存着「雾锁情迷」也查不回来。
# 这里只剥**明确的文件级噪音**（扩展名 / ``S01E71`` / ``第71集``），不碰正常片名。
VIDEO_EXT_RE = re.compile(
    r"\.(mp4|mkv|avi|rmvb|rm|ts|m2ts|mov|flv|wmv|webm|vob|mpg|mpeg|m4v|iso|f4v|tp)\s*$",
    re.I,
)
# ``S01E71`` / ``S1E2E3`` / ``s01.e71`` —— 允许前置分隔符完全缺省（``片名S01E71``）
SEASON_EPISODE_RE = re.compile(
    r"[\s._\-–—]*[Ss]\d{1,3}[\s._]?[Ee]\d{1,3}(?:[\s._\-–—]?[Ee]\d{1,3})*[\s._\-–—]*$"
)
# 只有季、没有集（``片名.S01`` / ``片名 S2``）
SEASON_ONLY_RE = re.compile(r"[\s._\-–—]*[Ss][\s._]?\d{1,3}[\s._\-–—]*$")
# 「第71集」/「71集」
EPISODE_CN_RE = re.compile(r"[\s._\-–—]*第?\s*\d{1,4}\s*集[\s._\-–—]*$")
# 剥完噪音留下的悬空分隔符（``片名 -``）
FILENAME_EDGE_SEPARATOR_RE = re.compile(r"^[\s._\-–—]+|[\s._\-–—]+$")
