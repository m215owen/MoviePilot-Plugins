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
SOURCE_DESC = "短剧百科（duanjubaike.net）数据源：短剧 / 漫剧 / 原著与人物。"

# ── 站点 ──────────────────────────────────────────────────────────────
SITE_BASE = "https://www.duanjubaike.net"
IMAGE_BASE = "https://img.duanjubaike.net"

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
ENTITY_DRAMA = frozenset({"duanju", "manju", "hema", "huolong"})
ENTITY_NOVEL = frozenset({"xiaoshuo"})
ENTITY_PERSON = frozenset({"yanyuan", "daoyan", "bianju"})
ENTITY_ALL = frozenset(ENTITY_DRAMA | ENTITY_NOVEL | ENTITY_PERSON)

# 豆瓣：作品与人物共用 subject ID 空间，必须两个前缀区分（计划 §2.5）。
DOUBAN_WORK = "douban"
DOUBAN_PERSON = "doubanp"

DOUBAN_MOVIE_BASE = "https://movie.douban.com"

# 实体 → 展示类型。``hema`` 约 7% 实为短剧，误差只由详情缓存的精确 kind 在展示层纠正，
# 不入库、不加列（计划 §2.3）。
KIND_OF_ENTITY = {
    "duanju": "短剧",
    "manju": "漫剧",
    "hema": "漫剧",
    "huolong": "漫剧",
    "xiaoshuo": "原著",
}

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
    """人物目录页绝对 URL；未知分类或非法页码返回空串（第 1 页不带 query）。"""
    kind_key = str(kind or "").strip().lower()
    if kind_key not in PEOPLE_KINDS or page < 1:
        return ""
    suffix = "" if page <= 1 else f"?page={page}"
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


def rank_url(key: str, page: int = 1) -> str:
    """榜单页绝对 URL；未知 key 返回空串。

    只有 :data:`PAGEABLE_RANKS` 里的榜认页码（第 1 页不带 query），其余榜忽略页码。
    """
    key = str(key or "").strip().lower()
    item = RANK_CATALOG.get(key)
    if not item:
        return ""
    if key in PAGEABLE_RANKS and page > 1:
        return f"{SITE_BASE}{item[1]}?page={page}"
    return f"{SITE_BASE}{item[1]}"
