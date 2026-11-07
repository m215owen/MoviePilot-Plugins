"""常量：来源标识、实体前缀、URL 模板、缓存 region / TTL。

站点结构见 ``docs/sources/短剧百科-页面结构分析.md``：详情页与海报的 URL 形态对
八类实体完全一致，因此这里只放模板，不放任何 id 字符集规则。
"""

from __future__ import annotations

import re
from pathlib import Path

# ── 来源身份 ───────────────────────────────────────────────────────────
# 全局稳定扩展标识，发布后不随显示名/接口地址变化（官方 FAQ 19）。
MEDIA_SOURCE_ID = "djbaike"
SOURCE_NAME = "短剧百科"
SOURCE_DESC = "短剧百科数据源（duanjubaike.net / duanjubaike.org 二选一）：短剧 / 漫剧 / 原著与人物。"

# ── 站点 ──────────────────────────────────────────────────────────────
SITE_BASE = "https://www.duanjubaike.net"

#: 站点二选一（2026-11-03 用户口径：把 .org 接到本插件上）。
#:
#: 两个站是**两套完全不同的架构**，解析器各一套（:mod:`parser` 对 .net、
#: :mod:`orgsite` 对 .org）。站点只影响三件事：**检索 / 人物目录 / 榜单**走哪个站。
#: 详情与图片按 ``media_id`` 前缀路由（``drama:`` / ``actor:`` 必然来自 .org），
#: 与配置无关 —— 换站不会让已入库的旧身份失效。
SITE_NET = "net"
SITE_ORG = "org"
DEFAULT_SITE = SITE_NET
SITE_DOMAINS = {
    SITE_NET: "https://www.duanjubaike.net",
    SITE_ORG: "https://duanjubaike.org",
}

#: 当前主站（模块级开关；由插件 ``init_plugin`` 按配置 ``site`` 设置）。
#: 走模块级而不是逐参传递，理由同 :func:`set_use_baidu_proxy`：站点在
#: ``search`` / ``pages`` / ``service`` 里被当纯函数取用，逐处传参改动面过大。
_site: str = DEFAULT_SITE

# ── .org（新站）专有 ──

#: .org 的语言路径段（URL 都挂在语言前缀下，抓简体）
ORG_LANG = "zh-Hans"

#: .org 的作品 / 人物**媒体前缀**（同时也是站点路径段）
ORG_WORK_KIND = "drama"
ORG_PERSON_KIND = "actor"

#: .org 图片 CDN（自建、直连 200；不走百度代理，海报是绝对地址、按页抓取后随记录
#: 落盘 —— .org 的图地址含 UUID 路径，**不能**像 .net 那样按身份现拼）
ORG_IMAGE_DOMAIN = "https://cdn.duanjubaike.org"

#: .org 检索路径（作品 / 人物各一个端点，不像 .net 一页同回两块）
ORG_WORK_SEARCH_PATH = "/{lang}/drama/search"
ORG_PERSON_SEARCH_PATH = "/{lang}/actor/search"

#: .org 人物目录（分页：``{lang}/actor?page=N``）
ORG_PEOPLE_PATH = "/{lang}/actor"

#: .org 作品页上的三个「关系区块」标题（卡片结构与搜索页同构）。
ORG_SERIES_SECTION = "这个系列拍了好几季"
ORG_SAME_SCRIPT_SECTION = "同一剧本还拍了以下版本"
ORG_SAME_NOVEL_SECTION = "同一小说还拍了以下版本"

#: .org 作品页「原著小说」区块的标题前缀（实际是 ``《剧名》原著小说``）。
#: 该区块**没有链接**（实测整块 0 个 ``<a>``）⇒ 拿不到 ``xiaoshuo:<id>``。
ORG_NOVEL_SECTION = "原著小说"

#: .org 作品页「热评」区块（``<section id="comments">``）。
ORG_COMMENTS_SECTION = "热评"

#: .org 标题行左侧的 AI 生成标（``AI短剧``）。
ORG_AI_BADGE_TITLE = "AI短剧"

#: 站点自家图床主机（``media_id`` 可直接反推 ``{host}/{entity}/{id}.jpg``）
IMAGE_HOST = "img.duanjubaike.net"
IMAGE_BASE = f"https://{IMAGE_HOST}"

#: 百度 gimg 中转前缀：站点页面 / 榜单接口实际出图就是这种形态——
#: ``https://gimg0.baidu.com/gimg/app=2001&n=0&g=0n&src=img.duanjubaike.net/{entity}/{id}.jpg``。
#: 配置 ``use_baidu_image_proxy`` 打开时按它拼（保留站点原样）；关闭时用 ``IMAGE_BASE`` 直链。
BAIDU_IMAGE_PROXY_PREFIX = "https://gimg0.baidu.com/gimg/app=2001&n=0&g=0n&src="

# Vue 联邦构建产物目录（相对**插件目录**；FAQ 17 的 `get_render_mode` 第二返回值）。
# ⚠️ 必须与 `frontend/vite.config.ts` 的 `build.outDir`（`../dist`，即插件根 dist）
# 对上：宿主要按这个相对路径去找 `remoteEntry.js`，写成 frontend/dist 就会 404。
FRONTEND_DIST = "dist/assets"

#: 产物子目录的命名规则（`a1`、`a2`…）：数字部分同时是浏览器缓存键
_BUILD_DIR_RE = re.compile(r"a(\d+)")


def frontend_dist() -> str:
    """返回 Vue 产物目录（相对插件根），取 ``dist/`` 下序号最大的 ``a<N>`` 目录。

    宿主给联邦入口拼的 URL 是
    ``/plugin/file/<id>/<本函数返回值>/remoteEntry.js?v=<plugin_version>``。

    为什么要动态扫目录：**测试阶段版本号冻结**（用户要求不升级），``?v=`` 永远不变，
    浏览器强缓存 / Service Worker 会一直复用旧 ``remoteEntry.js`` —— 表现是「代码改了
    但组件加载失败 / 还是旧界面」。于是把目录名当缓存键：前端有实质改动就把
    ``vite.config.ts`` 里的 ``ASSETS_DIR`` 递增一位（a1 → a2），URL 随之变化，
    缓存天然失效，而版本号仍可冻结。

    找不到 ``a<N>`` 目录（老产物 / 首次构建前）时退回 ``FRONTEND_DIST``。
    """
    try:
        base = Path(__file__).resolve().parent / "dist"
        best: tuple[int, str] | None = None
        for child in base.iterdir():
            if not child.is_dir():
                continue
            matched = _BUILD_DIR_RE.fullmatch(child.name)
            if not matched:
                continue
            # 只认里面有 remoteEntry.js 的目录，避免半成品目录把路径带偏
            if not (child / "remoteEntry.js").exists():
                continue
            order = int(matched.group(1))
            if best is None or order > best[0]:
                best = (order, child.name)
        return f"dist/{best[1]}" if best else FRONTEND_DIST
    except Exception:  # noqa: BLE001 - 目录扫描失败不该影响识别主功能
        return FRONTEND_DIST

# ── 实体（= media_id 前缀 = 站内分区） ────────────────────────────────
#
# ``drama`` / ``actor`` 是 .org 的两个固定分区（新站没有 .net 那种细分），
# 与 .net 的 ``duanju`` / ``yanyuan`` **编号空间完全无关**，靠前缀天然隔离：
# ``drama:13502`` 与 ``duanju:7696405989787978814`` 是两部不同的剧、两套 URL。
ENTITY_DRAMA = frozenset({"duanju", "manju", "hema", "huolong", "drama"})
ENTITY_NOVEL = frozenset({"xiaoshuo"})
ENTITY_PERSON = frozenset({"yanyuan", "daoyan", "bianju", "actor"})
ENTITY_ALL = frozenset(ENTITY_DRAMA | ENTITY_NOVEL | ENTITY_PERSON)

#: .org 的实体（详情 / 图片走 .org 解析器与 CDN，不走 .net 的模板反推）
ORG_ENTITIES = frozenset({ORG_WORK_KIND, ORG_PERSON_KIND})

#: 漫剧的站内分区。站点把它们和短剧分开挂着，但详情页结构完全一致；
#: 配置 ``exclude_manju`` 打开时，识别候选 / 面板检索 / 榜单都按这份集合剔除。
MANJU_ENTITIES = frozenset({"manju", "hema", "huolong"})

# 豆瓣：作品与人物共用 subject ID 空间，必须两个前缀区分（计划 §2.5）。
DOUBAN_WORK = "douban"
DOUBAN_PERSON = "doubanp"

#: TMDB：作品 ``tmdb:{id}``、影人 ``tmdbp:{pid}`` —— 与豆瓣的 ``douban:`` /
#: ``doubanp:`` 对称（2026-11-04 用户口径「豆瓣和 tmdb 的 id 也可以作为复合 id」）。
#: 旧数据里的裸数字仍兼容读（``store.tmdb_number`` 剥前缀）。
TMDB_WORK = "tmdb"
TMDB_PERSON = "tmdbp"

DOUBAN_MOVIE_BASE = "https://movie.douban.com"

# 实体 → 展示类型。``hema`` 约 7% 实为短剧，误差只由详情缓存的精确 kind 在展示层纠正，
# 不入库、不加列（计划 §2.3）。
KIND_OF_ENTITY = {
    "duanju": "短剧",
    "manju": "漫剧",
    "hema": "漫剧",
    "huolong": "漫剧",
    "xiaoshuo": "原著",
    "drama": "短剧",
}


# ── 站点开关（模块级，供 parser / search / pages / service 当纯函数取） ──


def set_site(value: object) -> str:
    """设置当前主站；不认识的值回落 :data:`DEFAULT_SITE`，返回最终生效值。"""
    global _site
    key = str(value or "").strip().lower()
    _site = key if key in SITE_DOMAINS else DEFAULT_SITE
    return _site


def site() -> str:
    """当前主站（``net`` / ``org``）。"""
    return _site


def is_org_site(value: object = None) -> bool:
    """是否 .org：不传参数时看当前主站，传了则按传入值判。"""
    key = _site if value is None else str(value or "").strip().lower()
    return key == SITE_ORG

# ── 缓存 region / TTL（计划 §4） ──────────────────────────────────────
REGION_DETAIL = "djbaike.detail"
REGION_PERSON = "djbaike.person"
REGION_DOUBAN = "djbaike.douban"
REGION_SEARCH = "djbaike.search"
#: 榜单卡缓存（``rank_medias`` 用；解析后的卡行）
REGION_RANK = "djbaike.rank"

ALL_REGIONS = (
    REGION_DETAIL,
    REGION_PERSON,
    REGION_DOUBAN,
    REGION_SEARCH,
    REGION_RANK,
)

# ── 统一有效期（2026-10-23 用户口径：缓存要全插件统一，跟随系统配置） ──
#
# 所有 region 共用一份 TTL：宿主系统设置 ``META_CACHE_EXPIRE``（小时，0 = 自动），
# 自动档按宿主口径 —— 普通模式 24 小时、大内存模式 72 小时（与
# shortdramabaikesource 的 ``system_cache_settings`` 同口径）。解析逻辑在
# ``cache.unified_ttl``，插件每次 init / 保存配置时经 ``CacheFacade.refresh``
# 重读，宿主改设置即生效。

AUTO_TTL_NORMAL = 24 * 3600
AUTO_TTL_BIG_MEMORY = 72 * 3600

MAXSIZE_DETAIL = 8192
MAXSIZE_PERSON = 4096
MAXSIZE_DOUBAN = 2048
MAXSIZE_SEARCH = 2048
MAXSIZE_RANK = 64


# 人物目录三分类（站点 ``/<kind>/list.html?page=N``）。2026-10-22 实测翻页可用：
# 每页 24 条、分页导航给出尾页号（演员 1396 / 导演 333 / 编剧 211），
# 页间零重叠 —— 供 ``module_list_people``（跨插件契约 ``list_people``）翻页。
PEOPLE_KINDS: tuple[str, ...] = ("yanyuan", "daoyan", "bianju")

PEOPLE_KIND_NAMES: dict[str, str] = {
    "yanyuan": "演员",
    "daoyan": "导演",
    "bianju": "编剧",
}


def people_list_url(kind: str, page: int = 1) -> str:
    """人物目录页绝对 URL；未知分类或非法页码返回空串（第 1 页不带 query）。

    ``.org`` 主站时只有**一个**演员目录（``/{lang}/actor``，导演 / 编剧不单列），
    ``kind`` 忽略；页码同样从 2 起才带 ``?page=``。
    """
    page_no = max(1, int(page or 1))
    if is_org_site():
        base = SITE_DOMAINS[SITE_ORG]
        url = f"{base}/{ORG_LANG}/actor"
        return f"{url}?page={page_no}" if page_no > 1 else url
    kind_key = str(kind or "").strip().lower()
    if kind_key not in PEOPLE_KINDS or page < 1:
        return ""
    suffix = "" if page_no <= 1 else f"?page={page_no}"
    return f"{SITE_BASE}/{kind_key}/list.html{suffix}"


# ── 榜单（站点 ``/paihang/<key>.html``；2026-10-23 恢复为跨插件模块方法供给） ──
#
#: key → (展示名, 站点路径)。「排行榜首页」(index，混合页) 与「预约榜」(yuyue，
#: 整页卡无详情 id) 不收 —— 2026-10-23 对照站点实测。「推荐」(tuijian) 是
#: 站点导航里的「推荐短剧」页（``/tuijian.html``，路径不在 ``/paihang/`` 下），
#: 排在最前（2026-10-23 用户口径：发现页里「推荐」紧跟「演员」）。
RANK_CATALOG: dict[str, tuple[str, str]] = {
    "tuijian": ("推荐", "/tuijian.html"),
    "rebo": ("热播榜", "/paihang/rebo.html"),
    "reso": ("热搜榜", "/paihang/reso.html"),
    "shoucang": ("收藏榜", "/paihang/shoucang.html"),
    "niandu": ("年度榜", "/paihang/niandu.html"),
    "xinju": ("新剧榜", "/paihang/xinju.html"),
    "manjurebo": ("漫剧热播", "/paihang/manjurebo.html"),
    "manjuxinju": ("漫剧新剧", "/paihang/manjuxinju.html"),
}


#: 支持翻页的榜单（2026-10-24 实测：「推荐」页有 ``?page=N``，共 130 页、每页 30 部；
#: ``/paihang/*`` 的排行榜页忽略分页参数，一页就是全部）。
PAGEABLE_RANKS = frozenset({"tuijian"})

#: **「排除」开关管得到的专属榜单**。配置 ``exclude_manju`` 打开时，这些榜
#: **整条不进目录**（``list_ranks`` 不再列出）、``rank_medias`` 也直接短路返回空，
#: 不再抓页面。
#:
#: 开关一词两站两义（2026-11-03 用户口径）：老站排**漫剧**、新站排 **AI 剧**，
#: 所以集合里既有漫剧榜也有 AI 榜 ——
#: * ``manjurebo`` / ``manjuxinju``：.net 的漫剧热播 / 漫剧新剧；
#: * ``top-comic``：.org 的漫剧热播榜（2026-11-03 接入）；
#: * ``top-ai``：.org 的 AI 热播榜（2026-11-03 接入，与开关同口径：开关一开
#:   整榜消失，用户明确要求）。
#:
#: ⚠️ 只管**整榜**，不做逐条筛：综合热播榜（``top``）里混着的 AI 卡片仍照常出现
#: —— 与 .net 的 ``tuijian`` 里混着漫剧卡同一口径。
MANJU_RANKS = frozenset({"manjurebo", "manjuxinju", "top-comic", "top-ai"})

# ── .org 榜单（2026-11-03 接入） ──
#
# 新站的榜单只有**一页四榜**：``/zh-Hans/top``（综合热播榜）与
# ``/top/hot-real-drama`` / ``/top/hot-ai-drama`` / ``/top/hot-comic-drama``。
# 每榜**一页给 100 部、没有分页**（实测 2026-11-03），所以 org 侧走「整份卡行
# 缓存 + 按 page_size 切片」，与 .net 的 ``/paihang/*`` 同一套节奏。
#
# ``top-feel-good``（2026-11-03 接入）不是 ``/top`` 系的榜，是导航里的
# **「爽剧」分类页**（``/drama/feel-good``，一页 15 部、无分页）；用户要求
# 进发现页，卡片结构与四榜完全同构，照同一套取法接。它是真人剧分类，
# **不受**「排除」开关管辖（不在 :data:`MANJU_RANKS`）。
ORG_RANK_CATALOG: dict[str, tuple[str, str]] = {
    "top": ("综合热播榜", "/{lang}/top"),
    "top-real": ("真人热播榜", "/{lang}/top/hot-real-drama"),
    "top-ai": ("AI 热播榜", "/{lang}/top/hot-ai-drama"),
    "top-comic": ("漫剧热播榜", "/{lang}/top/hot-comic-drama"),
    "top-feel-good": ("爽剧热播榜", "/{lang}/drama/feel-good"),
}


def rank_catalog() -> dict[str, tuple[str, str]]:
    """当前主站的榜单目录（``key -> (展示名, 站点路径)``）。"""
    return ORG_RANK_CATALOG if is_org_site() else RANK_CATALOG


def rank_name(key: str) -> str:
    """榜单 key → 展示名；未知 key 返回空串。"""
    return rank_catalog().get(str(key or "").strip().lower(), ("", ""))[0]


def rank_url(key: str, page: int = 1) -> str:
    """榜单页绝对 URL；未知 key 返回空串。

    只有 :data:`PAGEABLE_RANKS` 里的榜认页码（第 1 页不带 query），其余榜忽略页码。

    ``.org`` 主站走 :data:`ORG_RANK_CATALOG`（四榜、**无分页**，页码被忽略）。
    """
    key = str(key or "").strip().lower()
    if is_org_site():
        item = ORG_RANK_CATALOG.get(key)
        if not item:
            return ""
        return f"{SITE_DOMAINS[SITE_ORG]}{item[1].format(lang=ORG_LANG)}"
    item = RANK_CATALOG.get(key)
    if not item:
        return ""
    if key in PAGEABLE_RANKS and page > 1:
        return f"{SITE_BASE}{item[1]}?page={page}"
    return f"{SITE_BASE}{item[1]}"
