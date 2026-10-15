"""短剧百科数据源（MoviePilot V3 插件后端）。

把「短剧百科」（``duanjubaike.org``）包装成 MoviePilot 的一等媒体数据源 —— 与
TMDB / 豆瓣 / Bangumi 同级。短剧在 TMDB / 豆瓣上大量没有条目，宿主识别器因此建不起
媒体身份；本插件补的正是这一段空白，**同时作为数据服务**供其它插件取用。

三层结构
--------
1. **发现（URL 从哪来）**：站内检索过不了 Cloudflare，所以问搜索引擎要
   ``site:<域名> <关键词>``。引擎返回的每条都是**带完整 URL 的结构化行**
   （``title`` / ``href`` / ``body``），``/drama/<id>`` 是作品、``/actor/<id>`` 是演员。
   见 :mod:`discover`。
2. **沉淀（URL 存哪）**：发现的 URL 写进**宿主的插件自有数据库**
   （``app.sdk.database.plugin_declarative_base``：PostgreSQL 下是宿主库里的独立
   schema，SQLite 下是插件数据目录里的 ``plugin.db``）。**库里只存 URL，不存解析
   结果** —— 站点内容随时在变，页面永远实时解析。见 :mod:`store`。
3. **解析（数据从哪来）**：拿 URL 抓页面，把站点给的字段**全部**解析出来
   （评分 / 热度 / 播放 / 收藏 / 集数 / 时长 / 首播 / 类型 / 出品方 / 真人-AI /
   剧照 / 演员阵容含角色 / 推荐位；演员页另有职务、性别、国籍、简介、全部作品、
   合作演员）。见 :mod:`parser`。

**取数顺序**：先查库 → 命中就直接抓页面（零引擎请求）→ 库里没有才检索一次引擎，
把两类 URL 都写进库。一次检索同时喂给「作品」与「演员」两条解析路，因为引擎侧有
3 秒最小间隔，分头查两次必然有一边为空。

URL 会**自己长大**：解析作品页时顺带把 ``actor[].url`` 入库，解析演员页时顺带把
``works[].url`` 入库（``follow_links`` 可关）。所以搜过一次作品，之后再搜它里面的
演员名也是零引擎请求。

宿主契约（V3.1.5 源码实证）
--------------------------
1. **扩展点是官方的**：``_PluginBase`` 提供 ``get_media_source()``（声明数据源）、
   ``get_module()``（把宿主模块方法名映射到插件实现）、``get_database_models()``
   （声明插件自有表）。
2. **来源标识不是封闭枚举**：``MediaSource("duanjubaike")`` 可直接构造。
3. **模块方法签名照宿主静态合同，一个字都不能改**：``recognize_media`` /
   ``async_recognize_media`` / ``search_medias`` / ``async_search_medias`` /
   ``obtain_images`` / ``async_obtain_images``。
4. **默认视频识别源是硬编码的 TMDB** ⇒ 本插件**不会**自动成为全局兜底，
   ``media_source`` 不匹配时**必须返回 None**，绝不能劫持其它来源的识别。
5. **图片域名要登记**：宿主图片代理只放行 ``SECURITY_IMAGE_DOMAINS`` 内的域名。

站点能力边界（2026-10-14 / 15 实测）
------------------------------------
* ``/zh-Hans/drama/{id}``：详情页，JSON-LD（``TVSeries`` + ``PerformanceRole`` 演员）
  + HTML（阵容、剧照、评分与统计、角标、推荐位）。**最可靠的一条路**。
* ``/zh-Hans/actor/{id}``：演员页，JSON-LD ``Person`` + 「出演短剧」网格（实测 59 部
  一次全渲染、不分页）+ 合作演员区。⚠️ 必须带 ``/zh-Hans`` 前缀，否则 301 到
  ``/zh-Hant`` 后页面里的作品链接变成 ``/zh-Hant/drama/…``，而卡片正则只认
  ``/zh-Hans`` ⇒ 静默解析出 0 部作品。
* ``/zh-Hans/drama/search``：Cloudflare **托管挑战**，服务端恒 403 ⇒ 已弃用
  （浏览器仿真有头/无头都过不去，实测有头跑到 105 秒仍停在挑战页）。
"""
from __future__ import annotations

import asyncio
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

from app.schemas.types import MediaType
from app.sdk.logging import logger
from app.sdk.plugin import _PluginBase

# 简繁转换：宿主 TMDB 源（``app/modules/themoviedb``）用的就是这一枚入口
# （``from app.foundation.text import convert as zhconv_convert``）。
# ⚠️ 必须容缺：它是 v3.1.5 才落到 ``app.foundation`` 的，老版本宿主与本地单测桩里都没有，
# 拿不到就退化为「没有简体候选」，不影响主流程。
try:  # pragma: no cover - 分支只取决于宿主版本
    from app.foundation.text import convert as zhconv_convert
except Exception:  # pragma: no cover
    zhconv_convert = None

from .constants import (
    ACTOR_ID_PREFIX,
    ACTOR_PATH,
    ACTOR_WORKS_ENRICH_LIMIT,
    DEFAULT_CACHE_TTL,
    DEFAULT_TIMEOUT,
    DEFAULT_WEB_INDEX_BACKEND,
    DETAIL_PATH,
    DISCOVER_TITLE_ENRICH_LIMIT,
    EXACT_TITLE_SCORE,
    IMAGE_DOMAINS,
    LANG_PATH,
    MAX_ACTOR_CANDIDATES,
    MAX_CANDIDATES,
    MAX_META_KEYWORDS,
    LEGACY_MEDIA_ID_PREFIXES,
    MEDIA_ID_PREFIX,
    MEDIA_SOURCE_ALIASES,
    MEDIA_SOURCE_KEY,
    MEDIA_SOURCE_LABEL,
    ORG_DEFAULT_DOMAIN,
    PLUGIN_ICON,
    PLUGIN_NAME,
    PLUGIN_VERSION,
    PROBE_SAMPLE_MEDIA_ID,
    USER_AGENT,
    WEB_INDEX_BACKENDS,
)
from .discover import WebIndex, extract_urls
from .parser import (
    _clean,
    _has_value,
    _match_title,
    _normalize_image,
    _normalize_title,
    canonical_page_url,
    is_cloudflare_challenge,
    parse_org_actor,
    parse_org_detail,
    video_name_of,
)
from .payload import (
    build_media_info,
    build_public_actor,
    build_public_record,
    media_source_value,
)
from .store import SiteUrl, UrlStore
from .tmdb import TmdbIdentity

try:  # 宿主统一 HTTP 入口（自动继承系统代理等设置）
    from app.sdk.network import RequestUtils as _RequestUtils
except Exception:  # pragma: no cover - 宿主版本差异兜底
    _RequestUtils = None

try:  # 宿主配置（读系统代理 / 图片白名单）
    from app.sdk.config import settings as _settings
except Exception:  # pragma: no cover - 宿主版本差异兜底
    _settings = None

# 同一个关键词在这个间隔内查过引擎就不再查（库里确实没有时也不必每次搜索都出网）
SEARCH_RETRY_INTERVAL = 300.0

# 「这条记录数据全不全」的判据（字段, 权重）。站点会给同一部剧建多条记录：实测
# ``/drama/40354``（AI短剧）与 ``/drama/40445``（真人短剧）标题 / 简介 / 首播日期完全相同，
# 但前者没有演员、集数、时长、出品方。权重按「缺了最影响使用」排 —— 演员最重要，
# 因为 AI 短剧几乎恒缺演员。
_RICHNESS_WEIGHTS: Tuple[Tuple[str, int], ...] = (
    ("actors", 4),
    ("episode_count", 2),
    ("duration_minutes", 2),
    ("heat", 1),
    ("play_count", 1),
    ("rating", 1),
    ("studio", 1),
    ("tags", 1),
    ("overview", 1),
    ("backdrop", 1),
    ("release_date", 1),
)


class ShortDramaBaikeSource(_PluginBase):
    """把「短剧百科」注册为 MoviePilot 的媒体数据源，并提供 URL 库。"""

    plugin_name = PLUGIN_NAME
    plugin_desc = (
        "把「短剧百科」注册为 MoviePilot 的媒体数据源（与 TMDB / 豆瓣同级）："
        "为短剧提供片名检索与详情识别，补齐 TMDB、豆瓣上没有条目的短剧；"
        "同时把搜索到的作品 / 演员页面 URL 存进插件自有数据库，供其它插件取用。"
    )
    plugin_icon = PLUGIN_ICON
    plugin_version = PLUGIN_VERSION
    plugin_author = "m215owen"
    author_url = "https://github.com/m215owen"
    plugin_config_prefix = "shortdramabaikesource_"
    plugin_order = 60
    auth_level = 1

    # ── 运行配置（init_plugin 从库里读，类属性只是默认值） ──
    _enabled: bool = False
    _domain: str = ORG_DEFAULT_DOMAIN
    _search_in_global: bool = True
    _timeout: int = DEFAULT_TIMEOUT
    _cache_ttl: int = DEFAULT_CACHE_TTL
    _web_index_search: bool = True
    _web_index_backend: str = DEFAULT_WEB_INDEX_BACKEND
    _proxy: bool = False
    # 解析页面时顺带把页面里的演员 / 作品链接写进 URL 库
    _follow_links: bool = True

    # ── 运行时状态（init_plugin 逐个重建，保证实例之间不串味） ──
    _cache: Dict[str, Tuple[float, Any]] = {}
    _cache_lock = threading.RLock()
    # 关键词 → 上次问引擎的时间戳（避免库里确实没有时每次搜索都出网）
    _searched_at: Dict[str, float] = {}
    # TMDB 身份补充器（init_plugin 里按实例重建；为 None 时该功能整体跳过）
    _tmdb: Optional["TmdbIdentity"] = None

    def __init__(self) -> None:
        super().__init__()
        # 实例级对象：引擎节流状态与数据库句柄都不能挂在类上，否则宿主重建插件实例
        # （reconcile 会反复重建）时会共用同一份状态
        self._web_index = WebIndex()
        self._url_store: Optional[UrlStore] = None
        self._store_lock = threading.RLock()

    # ── 生命周期 ──────────────────────────────────────────────────

    def init_plugin(self, config: Optional[Dict[str, Any]] = None) -> None:
        """按配置重建运行状态。"""
        config = config or {}
        self._enabled = bool(config.get("enabled"))
        self._domain = self._as_domain(config.get("domain"), ORG_DEFAULT_DOMAIN)
        self._search_in_global = self._as_bool(config.get("search_in_global"), True)
        self._timeout = self._as_range(config.get("timeout"), DEFAULT_TIMEOUT, 5, 120)
        self._cache_ttl = self._as_range(config.get("cache_ttl"), DEFAULT_CACHE_TTL, 0, 2592000)
        self._web_index_search = self._as_bool(config.get("web_index_search"), True)
        self._web_index_backend = self._as_choice(
            config.get("web_index_backend"), DEFAULT_WEB_INDEX_BACKEND, WEB_INDEX_BACKENDS
        )
        self._proxy = bool(config.get("proxy"))
        self._follow_links = self._as_bool(config.get("follow_links"), True)

        # ⚠️ 运行时容器必须在**每个实例**上重新绑定（它们是类属性）。
        self._cache = {}
        self._searched_at = {}
        self._web_index.reset_throttle()
        # TMDB 身份补充器：复用本插件的同步 GET（代理 / 超时 / UA 与站点请求一致）
        self._tmdb = TmdbIdentity(self._get)

        self._register_image_domains()
        # 历史遗留的重复行（同一个页面存成多条）在启动时合并掉：面板上一行＝一站剧
        merged = self._dedupe_store()
        stats = self._store_count()
        logger.info(
            f"{PLUGIN_NAME} 已就绪：启用={self._enabled} 域名={self._domain} "
            f"全局检索={self._search_in_global}｜站外索引={'开' if self._web_index_search else '关'}"
            f"（后端 {self._web_index_backend}）"
            f"｜URL 库={stats.get('total', 0)} 条"
            f"（作品 {stats.get('work', 0)} / 演员 {stats.get('actor', 0)}）"
            f"｜顺带入库={'开' if self._follow_links else '关'}"
            f"｜缓存={'关' if self._cache_ttl <= 0 else f'{self._cache_ttl}s'}"
            + (f"｜去重合并 {merged} 条重复记录" if merged else "")
        )

    def get_state(self) -> bool:
        return self._enabled

    def stop_service(self) -> None:
        """停止插件：清空内存缓存（URL 库是持久数据，不动）。"""
        with self._cache_lock:
            kept = len(self._cache)
            self._cache.clear()
        identities = self._tmdb.clear() if self._tmdb is not None else 0
        logger.info(
            f"{PLUGIN_NAME} 已停止：清空 {kept} 条内存缓存、{identities} 条 TMDB 身份缓存"
            f"（URL 库是持久数据，保留）"
        )

    def get_render_mode(self) -> Tuple[str, Optional[str]]:
        """声明使用 Vue 联邦远程组件渲染，产物目录为 ``dist/assets``。

        面板上要放**能回传输入的搜索框**，而宿主的 Vuetify（JSON）页面只支持静态组件树
        与「点击 → 调接口」这类无参交互，承载不了输入框，因此改用联邦前端。
        """
        return "vue", "dist/assets"

    def get_service(self) -> List[Dict[str, Any]]:
        """**不注册任何后台服务**：插件完全按需 —— 只有面板搜索 / 宿主识别 / 别的插件
        调用时才出网，没人调用就一个请求都不发。"""
        return []

    def get_database_models(self) -> List[Any]:
        """声明插件自有数据库里的表（宿主在插件启动时建表）。

        PostgreSQL 下这些表落在宿主库的独立 schema（``plugin_shortdramabaikesource``），
        SQLite 下落在插件数据目录的 ``plugin.db``；两种情况下都跟着宿主一起备份。
        """
        return [SiteUrl]

    # ── 数据源声明 ────────────────────────────────────────────────

    def get_media_source(self) -> List[Dict[str, Any]]:
        """声明本插件提供的媒体数据源（短剧在 MoviePilot 里统一按电视剧处理）。"""
        return [
            {
                "name": MEDIA_SOURCE_LABEL,
                "media_source": media_source_value(),
                "media_types": [MediaType.TV],
            }
        ]

    def get_module(self) -> Dict[str, Any]:
        """把宿主模块方法名映射到本插件实现 —— **供其它插件调用的主通道**。

        任何 ``ChainBase`` 子类（也就是别的插件）都能直接调到：

            infos = self.run_module("search_medias", meta=meta, media_source="duanjubaike")
            info = self.run_module("recognize_media", media_source="duanjubaike", media_id="duanju:45982")
            works = self.run_module("actor_works", actor_id="371")
            actors = self.run_module("search_actors", name="魏依珂")

        前两个返回宿主 ``MediaInfo``（与 TMDB / 豆瓣模块同一个模型）；演员那两个是本插件
        **自定义**方法名，返回纯 Python 列表，消费方不必做任何转换。
        """
        return {
            "recognize_media": self.recognize_media,
            "async_recognize_media": self.async_recognize_media,
            "search_medias": self.search_medias,
            "async_search_medias": self.async_search_medias,
            "obtain_images": self.obtain_images,
            "async_obtain_images": self.async_obtain_images,
            # 自定义能力（宿主模块合同里没有这两个名字，走 legacy 契约放行）
            "search_actors": self.search_actors,
            "async_search_actors": self.async_search_actors,
            "actor_works": self.actor_works,
            "async_actor_works": self.async_actor_works,
        }

    # ── URL 库（插件自有数据库） ──────────────────────────────────

    def _store(self) -> Optional[UrlStore]:
        """取 URL 库门面；宿主没给出数据库句柄时返回 None（插件降级为纯实时检索）。"""
        with self._store_lock:
            if self._url_store is not None:
                return self._url_store
            try:
                handle = self.get_database()
            except Exception as err:  # pragma: no cover - 宿主数据库异常
                logger.warning(f"{PLUGIN_NAME} 取插件数据库失败，URL 库停用：{err}")
                return None
            if handle is None:  # pragma: no cover - 极端兜底
                return None
            self._url_store = UrlStore(handle)
            return self._url_store

    def _remember(self, entries: List[Dict[str, Any]]) -> int:
        """把 URL 写进库（失败只记日志，绝不影响本次结果）。"""
        store = self._store()
        rows = [row for row in entries if row.get("url") and row.get("keyword")]
        if store is None or not rows:
            return 0
        try:
            return store.add(rows)
        except Exception as err:
            # ⚠️ 入库失败是**静默降级**：本次结果照常返回，但下一次搜索还得再问一次引擎。
            # 不记日志的话只会表现为「引擎召回时好时坏」，很难想到是库写不进去。
            logger.warning(f"{PLUGIN_NAME} URL 入库失败（{len(rows)} 条）：{err}")
            return 0

    def _store_count(self) -> Dict[str, Any]:
        store = self._store()
        if store is None:
            return {"total": 0, "work": 0, "actor": 0, "keywords": 0, "last_seen_at": 0}
        try:
            return store.count()
        except Exception:  # pragma: no cover - 数据库异常
            return {"total": 0, "work": 0, "actor": 0, "keywords": 0, "last_seen_at": 0}

    def _dedupe_store(self) -> int:
        """整库去重（同一个页面只留一条），返回被合并掉的条数。

        插件启动时跑一次：早期版本按「搜索词」给演员建档，同一个演员会同时以片名和
        自己的名字各存一条（实测库里 40445 那条繁体标题行与简体行并存），面板上一行是
        一部剧才对得上。
        """
        store = self._store()
        if store is None:
            return 0
        try:
            merged = store.dedupe()
            # 顺手清掉历史遗留的「张冠李戴」行（键是搜索词、内容却是别的剧，见
            # ``UrlStore.prune_mismatched``）—— 它们会让日志虚报「库命中」
            pruned = store.prune_mismatched()
        except Exception as err:  # pragma: no cover - 数据库异常
            logger.warning(f"{PLUGIN_NAME} URL 库去重失败：{err}")
            return 0
        if pruned:
            logger.info(f"{PLUGIN_NAME} URL 库清理错行：删除 {pruned} 条（片名与键对不上）")
        return merged

    @staticmethod
    def _as_entry(kind: str, keyword: str, native_id: str, label: str, url: str,
                  origin: str, backend: str = "", display: str = "") -> Dict[str, Any]:
        """组装一条入库记录（入库是**唯一写入口**，所有前提都收在这里）。

        * ``keyword`` 一律归一化（大小写 / 空格 / 全角 / 书名号都不影响命中），并且是
          **这条记录自己的名字**（作品＝片名，演员＝演员名）—— 演员常常是搜一部剧时
          顺带发现的，键必须落在它自己身上，否则按演员名查不回来。
        * ``display`` 是**触发这次发现的搜索词**原文，缺省等于 ``keyword``（面板上显示来源）。
        * ``url`` 在这里就归一化语言前缀（:func:`parser.canonical_page_url`），读出来的
          地址就一定可以直接抓。
        """
        return {
            "kind": kind,
            "keyword": _normalize_title(keyword),
            "display": _clean(display) or _clean(keyword),
            "label": _clean(label),
            "native_id": _clean(native_id),
            "url": canonical_page_url(url),
            "origin": origin,
            "backend": backend,
        }

    def _remember_links(self, rows: List[Dict[str, Any]], origin: str = "page") -> int:
        """把**页面里顺带发现的链接**入库（``follow_links`` 开着时才算）。

        :param rows: ``[{"kind", "keyword", "native_id", "label", "url"[, "display"]}]``
        """
        if not self._follow_links or not rows:
            return 0
        entries = [
            self._as_entry(
                str(row.get("kind") or "work"),
                str(row.get("keyword") or ""),
                str(row.get("native_id") or ""),
                str(row.get("label") or ""),
                str(row.get("url") or ""),
                origin,
                display=str(row.get("display") or ""),
            )
            for row in rows
        ]
        added = self._remember(entries)
        if added:
            logger.info(f"{PLUGIN_NAME} URL 库新增 {added} 条（来自{origin}）")
        return added

    # ── URL 解析（库优先 → 引擎发现 → 入库） ─────────────────────

    def _resolve(self, keyword: str, force: bool = False) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """把一个关键词解析成两类 URL 记录（作品 / 演员）。

        **库优先**：库里命中就直接用（零引擎请求）。库里某类为空、且这个关键词最近没
        问过引擎时，才检索一次；一次检索抽出的两类 URL 都会入库。

        库里的命中是**宽松匹配**（键 / 标题 / 触发词任一命中，见 :meth:`store.UrlStore.match`）：
        一个页面只留一条记录，那条的键落在哪儿取决于它先被哪条路发现，三个字段都认才对
        得上「库优先」这个承诺。

        :return: ``(works, actors)``，每项含 ``url`` / ``label`` / ``native_id`` / ``from``
        """
        query = _clean(keyword)
        key = _normalize_title(query)
        if not key:
            return [], []
        store = self._store()
        works: List[Dict[str, Any]] = []
        actors: List[Dict[str, Any]] = []
        if store is not None and not force:
            try:
                works = self._dedupe([row.as_dict() | {"from": "store"} for row in store.match("work", key)])
                actors = self._dedupe([row.as_dict() | {"from": "store"} for row in store.match("actor", key)])
            except Exception as err:  # pragma: no cover - 数据库异常
                logger.debug(f"{PLUGIN_NAME} 读 URL 库失败：{err}")
        if works and actors:
            # 这两条用 INFO：默认日志级别是 INFO（宿主 LOG_LEVEL），而它们正是
            # 「为什么这次没出网 / 为什么没结果」的答案 —— 放到 DEBUG 在真机上根本看不到
            logger.info(
                f"{PLUGIN_NAME}「{query}」URL 库命中：作品 {len(works)} / "
                f"演员 {len(actors)}（零引擎请求）"
            )
            return works, actors
        if not force and not self._should_search(key):
            # 两类里缺了哪一类、为什么这次不问引擎 —— 「库里没有」与「刚查过被挡住」
            # 表现一样（都是没结果），日志里必须分得开
            logger.info(
                f"{PLUGIN_NAME}「{query}」库里只有 作品 {len(works)} / 演员 {len(actors)}，"
                f"本次不问引擎：{self._search_skip_reason(key)}"
            )
            return works, actors
        found_works, found_actors = self._discover(query)
        # ⚠️ 必须**合并**而不是「库里有就用库里的」：库里只要有一条命中（例如那条是从
        # 页面里的链接顺带发现的），`works or found_works` 就会把本次新检索到的整批结果
        # 丢掉 —— 面板上第一次只显示库里那条（实测「相亲对象是迟来的心动」只出 40354
        # 那条 AI 版空壳），得再查一次才看得到引擎刚发现的 40445。库里没有的才补进来。
        return self._merge(works, found_works), self._merge(actors, found_actors)

    @staticmethod
    def _merge(
        primary: List[Dict[str, Any]], extra: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """按 ``native_id`` 合并两组候选：``primary`` 在前，重复的以 ``primary`` 为准。"""
        merged: Dict[str, Dict[str, Any]] = {}
        for row in list(primary) + list(extra):
            native_id = _clean(str(row.get("native_id") or ""))
            if native_id and native_id not in merged:
                merged[native_id] = row
        return list(merged.values())

    @staticmethod
    def _dedupe(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """按 ``native_id`` 去重（保留 ``hits`` 最高的那条）。

        库里同一个 ID 可能有多条 URL —— 早期版本会把引擎给的无前缀 / 繁体地址原样存下来，
        归一化上线后就与简体地址并存了。同一个 ID 只该在面板上占一行。
        """
        best: Dict[str, Dict[str, Any]] = {}
        order: List[str] = []
        for row in rows:
            native_id = _clean(str(row.get("native_id") or ""))
            if not native_id:
                continue
            current = best.get(native_id)
            if current is None:
                best[native_id] = row
                order.append(native_id)
                continue
            if (row.get("hits") or 0) > (current.get("hits") or 0):
                best[native_id] = row
        return [best[native_id] for native_id in order]

    def _should_search(self, key: str) -> bool:
        """这个关键词现在该不该问引擎（含「站外索引」开关与重试间隔）。"""
        if not self._web_index_search or not self._web_index.available:
            return False
        last = self._searched_at.get(key)
        return last is None or (time.time() - last) >= SEARCH_RETRY_INTERVAL

    def _search_skip_reason(self, key: str) -> str:
        """「这次不问引擎」的真实原因 —— 开关关着 / 环境缺依赖 / 刚查过，三者都要说得清。"""
        if not self._web_index_search:
            return "站外索引已关闭"
        if not self._web_index.available:
            return "宿主环境缺少 ddgs"
        last = self._searched_at.get(key)
        if last is None:
            return "（无需跳过）"
        return f"{int(time.time() - last)}s 前刚检索过（间隔需 {int(SEARCH_RETRY_INTERVAL)}s）"

    def _discover(self, keyword: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """检索一次引擎，**两类 URL 一起抽、一起入库**，返回入库后的记录。

        ⚠️ 必须只查一次：引擎侧有 3 秒最小间隔，分头查「作品」与「演员」必然有一次
        被跳过，结果就是两块里恒有一块是空的。
        """
        key = _normalize_title(keyword)
        self._searched_at[key] = time.time()
        host = self._domain_host()
        rows = self._web_index.search(keyword, host, self._web_index_backend)
        if not rows:
            # 引擎侧的原因（后端报错 / 环境缺依赖 / 被节流）已在 discover 模块里记过，
            # 这里只补一句「结论」，让「搜了但没结果」与「压根没搜」在日志里分得开
            logger.info(f"{PLUGIN_NAME} 站外索引「{keyword}」没有返回任何结果")
            return [], []
        raw_works, raw_actors = extract_urls(rows, host)
        if not raw_works and not raw_actors:
            logger.info(
                f"{PLUGIN_NAME} 站外索引「{keyword}」返回 {len(rows)} 条，"
                f"但都不是作品页 / 演员页 —— 图集页、榜单页与外域地址一律剔除"
            )
            return [], []
        raw_works = raw_works[:MAX_CANDIDATES]
        raw_actors = raw_actors[:MAX_ACTOR_CANDIDATES]
        self._enrich_labels(keyword, raw_works, raw_actors)
        entries: List[Dict[str, Any]] = []
        stored = 0
        for row in raw_works:
            title = _clean(row.get("label") or "")
            if not title:
                continue
            # ⚠️ **只有完全匹配的才建库**。引擎的召回本来就不稳：实测搜「相亲对象是迟来的
            # 心动」返回的是「深渊之花」「照片是舍友，網戀對象是繼承人」等五部**毫不相干**
            # 的剧。以前一律按搜索词建档入库 ⇒ 库里攒下一批「键是这个搜索词、内容却是别的
            # 剧」的错行，下次搜同一个词虚报「库命中 5」，其实一条都对不上。
            # 宁可漏（漏了下回再搜一次就补上），不可错（错了会一直污染库）。
            #
            # 注意这只卡**入库** —— 候选照旧全部返回，交上层按片名打分排序
            # （``api_lookup`` / ``search_medias`` 都会按同一条门槛再筛一遍）。
            if _match_title(title, keyword) < EXACT_TITLE_SCORE:
                continue
            stored += 1
            # 作品按**自己的片名**建档（引擎标题已剥过后缀、繁体的也补抓成了简体），
            # 触发这次发现的搜索词记在 display 里 —— 同一个词下一次照样查得回来。
            entries.append(self._as_entry(
                "work", title, row["native_id"], title, row["url"],
                "search", self._web_index_backend, display=keyword,
            ))
        # 演员**不**按这个门槛过滤：它多半是搜一部剧时顺带发现的（本插件「URL 会自己
        # 长大」靠的就是这个），而且它按自己的名字建档，不会污染库。
        for row in raw_actors:
            # 演员按**自己的名字**建档：它多半是搜片名时顺带发现的，挂在片名下就查不回来，
            # 还会跟「解析作品页顺带写一条演员行」那条重复
            name = _clean(row.get("label") or "") or _clean(keyword)
            entries.append(self._as_entry(
                "actor", name, row["native_id"], name, row["url"],
                "search", self._web_index_backend, display=keyword,
            ))
        added = self._remember(entries)
        logger.info(
            f"{PLUGIN_NAME} 站外索引「{keyword}」命中 {len(raw_works)} 部作品 / "
            f"{len(raw_actors)} 位演员｜与搜索词完全匹配 {stored} 部，入库 {added} 条"
            + ("" if stored else "（其余只是字面沾边，不建库）" if raw_works else "")
        )
        works = [
            {"url": row["url"], "label": row.get("label", ""), "native_id": row["native_id"],
             "kind": "work", "from": "search"}
            for row in raw_works
        ]
        actors = [
            {"url": row["url"], "label": row.get("label", ""), "native_id": row["native_id"],
             "kind": "actor", "from": "search"}
            for row in raw_actors
        ]
        return works, actors

    def _enrich_labels(
        self, keyword: str, works: List[Dict[str, Any]], actors: List[Dict[str, Any]]
    ) -> None:
        """给「标题不可信」的候选补抓一次简体页，把标题换成页面自己给的那个（原地改）。

        引擎给的是搜索结果标题，语言跟着它命中的那份页面走：实测同一部剧会有
        ``/zh-Hans/drama/40354``（简体标题）与 ``/zh-Hant/drama/40445``（繁体标题）两行，
        繁体那行按简体关键词打分**恒为 0** ⇒ 被当无关候选丢掉，面板上看不到它，
        用户也就无从知道「这部剧还有一版」。补抓一次简体页拿真标题就解决了，顺带把详情
        写进 TTL 缓存（点「识别」不再出网）。

        两道闸门控制代价（一次检索最多多花 ``DISCOVER_TITLE_ENRICH_LIMIT`` 个请求）：

        1. 只补**非 ``/zh-Hans`` 地址**（:func:`parser.href_points_to_simplified`）——
           简体地址那行的标题本来就是简体，不用换；
        2. 只补「标题像是这个关键词的繁体写法」的（:meth:`_may_be_traditional`）——
           无关候选为它多抓一次页面不值得。
        """
        budget = DISCOVER_TITLE_ENRICH_LIMIT
        if budget <= 0:
            return
        query = _clean(keyword)
        for kind, rows in (("work", works), ("actor", actors)):
            for row in rows:
                if budget <= 0:
                    return
                if row.get("simplified") or not row.get("native_id"):
                    continue
                if not self._may_be_traditional(_clean(str(row.get("label") or "")), query):
                    continue
                budget -= 1
                native_id = _clean(str(row.get("native_id") or ""))
                url = _clean(str(row.get("url") or ""))
                if kind == "work":
                    label = _clean(((self._fetch_detail(native_id, url) or {})).get("title") or "")
                else:
                    label = _clean(((self._fetch_actor(native_id, url) or {})).get("name") or "")
                if label and label != _clean(str(row.get("label") or "")):
                    logger.info(
                        f"{PLUGIN_NAME} 候选 {kind}:{native_id} 标题『{row.get('label')}』"
                        f"补抓简体页后换成『{label}』"
                    )
                    row["label"] = label

    @staticmethod
    def _may_be_traditional(label: str, query: str) -> bool:
        """这条标题有没有可能是同一个名字的**繁体**写法。

        简繁是**逐字转写**，字数必然一样 —— 字数不同的候选不可能是同一个名字换套字，
        不必为它去抓页面。实测那对重复条目正好同为 9 字（``相亲对象是迟来的心动`` /
        ``相親對象是遲來的心動``）。
        """
        return bool(label) and bool(query) and label != query and len(label) == len(query)

    def _url_for_native(self, kind: str, native_id: str) -> str:
        """按站点 ID 取库里记着的 URL；没有就返回空串（调用方兜底拼一个）。"""
        store = self._store()
        if store is None or not native_id:
            return ""
        try:
            record = store.by_native_id(kind, native_id)
        except Exception:  # pragma: no cover - 数据库异常
            return ""
        return record.url if record is not None else ""

    # ── 抓取与解析 ────────────────────────────────────────────────

    def _fetch_detail(self, native_id: str, url: str = "") -> Optional[Dict[str, Any]]:
        """抓作品详情页并解析（带 TTL 缓存）。取不到返回 None。

        :param native_id: 站点作品 ID（裸数字）
        :param url: 优先使用的地址（库里的 URL / 引擎给的地址）；为空则按 ID 拼兜底。
            无论哪种都会被 :func:`parser.canonical_page_url` 归一化成简体地址 ——
            库里可能还留着旧版写的繁体/无前缀地址。
        """
        native_id = _clean(native_id)
        if not native_id.isdigit():
            # 站点作品 ID 恒为裸数字；别拿 ``duanju:abc`` 这类值去拼一个必然 404 的地址
            return None
        cached = self._cache_get(f"detail:{native_id}")
        if cached is not None:
            logger.debug(f"{PLUGIN_NAME} 作品 {native_id} 命中详情缓存（零请求）")
            return dict(cached)
        target = canonical_page_url(
            _clean(url) or f"{self._domain.rstrip('/')}{DETAIL_PATH.format(id=native_id)}",
            self._domain,
        )
        html, status = self._get(target)
        if not html:
            logger.warning(f"{PLUGIN_NAME} 详情页取不到内容：{target}（status={status}）")
            return None
        record = parse_org_detail(html, native_id, self._domain)
        if not record.get("title"):
            # 页面拿到了却解析不出标题 ⇒ 站点改版（或抓到的是挑战页 / 错误页）。
            # 静默返回 None 只会表现为「这部剧搜不到」，必须留下现场。
            logger.warning(
                f"{PLUGIN_NAME} 详情页解析不出标题：{target}"
                f"（正文 {len(html)} 字节，解析出 {len(record)} 个字段）"
            )
            return None
        # TMDB 真实身份：严格匹配命中就写进 record（面板「原始数据」能看见），
        # 详情页那几块只认 tmdb_id 的区块也会跟着亮 —— 必须在写缓存**之前**做，
        # 否则缓存里那份没有它，面板展开的原始数据就会缺这一项
        self._tmdb_identity(record)
        self._cache_set(f"detail:{native_id}", record)
        logger.debug(
            f"{PLUGIN_NAME} 作品 {native_id}《{record.get('title')}》解析完成："
            f"{len(record)} 个字段 / 演员 {len(record.get('actors') or [])} 位"
            f" / 剧照 {len(record.get('stills') or [])} 张"
            f" / 推荐 {len(record.get('related') or [])} 条"
        )
        # 顺手把地址与演员链接沉淀进 URL 库。演员行按**演员名**建档、``display`` 记这部
        # 剧 —— 面板上要看得出一位演员是搜哪部剧时带出来的
        if self._follow_links:
            title = _clean(record.get("title") or "")
            self._remember_links(
                [{"kind": "work", "keyword": title, "native_id": native_id,
                  "label": title, "url": record.get("url") or target}]
                + [
                    {"kind": "actor", "keyword": actor.get("name", ""),
                     "native_id": actor.get("id", ""), "label": actor.get("name", ""),
                     "display": title,
                     "url": f"{self._domain.rstrip('/')}{ACTOR_PATH.format(id=actor['id'])}"}
                    for actor in (record.get("actors") or [])
                    if actor.get("id") and actor.get("name")
                ]
            )
        return dict(record)

    def _fetch_actor(self, actor_id: str, url: str = "") -> Optional[Dict[str, Any]]:
        """抓演员页并解析（带 TTL 缓存）。取不到返回 None。

        ⚠️ 地址一律过 :func:`parser.canonical_page_url`：演员页**必须**抓 ``/zh-Hans``，
        否则 301 到繁体页后页面内的作品链接变成 ``/zh-Hant/drama/…``，而卡片正则只认简体
        ⇒ **作品静默解析出 0 部**（资料字段照常正确，极难发现）。
        """
        actor_id = _clean(actor_id)
        if not actor_id.isdigit():
            return None
        cached = self._cache_get(f"actor:{actor_id}")
        if cached is not None:
            logger.debug(f"{PLUGIN_NAME} 演员 {actor_id} 命中档案缓存（零请求）")
            return dict(cached)
        target = canonical_page_url(
            _clean(url) or f"{self._domain.rstrip('/')}{ACTOR_PATH.format(id=actor_id)}",
            self._domain,
        )
        html, status = self._get(target)
        if not html:
            logger.warning(f"{PLUGIN_NAME} 演员页取不到内容：{target}（status={status}）")
            return None
        profile = parse_org_actor(html, actor_id, self._domain)
        if not profile.get("name"):
            logger.warning(
                f"{PLUGIN_NAME} 演员页解析不出姓名：{target}"
                f"（正文 {len(html)} 字节，解析出 {len(profile)} 个字段）"
            )
            return None
        self._cache_set(f"actor:{actor_id}", profile)
        if not (profile.get("works") or []):
            # ⚠️ 这是本插件**最难发现**的一类故障：资料字段全对、只有作品为 0。
            # 真因几乎总是抓到了繁体页（/zh-Hant 或没带 /zh-Hans 被 301），页面里作品
            # 链接写成 /zh-Hant/drama/… 而卡片正则只认简体 —— 不点破就会一直查下去。
            logger.warning(
                f"{PLUGIN_NAME} 演员 {actor_id}「{profile.get('name')}」解析出 0 部作品："
                f"{target} —— 多半是抓到了繁体页，检查地址是否带 {LANG_PATH} 前缀"
            )
        else:
            logger.debug(
                f"{PLUGIN_NAME} 演员 {actor_id}「{profile.get('name')}」解析完成："
                f"作品 {profile.get('works_count') or len(profile.get('works') or [])} 部"
                f" / 合作演员 {len(profile.get('coactors') or [])} 位"
            )
        if self._follow_links:
            # 作品行按片名建档、``display`` 记这位演员 —— 面板上要看得出一部作品是从谁的
            # 演员页顺带发现的
            self._remember_links(
                [
                    {"kind": "work", "keyword": work.get("title", ""),
                     "native_id": work.get("native_id", ""), "label": work.get("title", ""),
                     "display": _clean(profile.get("name") or ""),
                     "url": work.get("url", "")}
                    for work in (profile.get("works") or [])
                    if work.get("title") and work.get("url")
                ],
                origin="page",
            )
        return dict(profile)

    def _resolve_item(
        self,
        media_id: str = "",
        keyword: str = "",
        year: str = "",
        url: str = "",
    ) -> Optional[Dict[str, Any]]:
        """按 ``media_id``（``duanju:<id>``，兼容旧前缀 ``org:``）或片名取一条作品记录。"""
        native_id = self._native_id(media_id)
        if native_id:
            target = url or self._url_for_native("work", native_id)
            return self._fetch_detail(native_id, target)
        query = _clean(keyword)
        if not query:
            return None
        works, _ = self._resolve(query)
        if not works:
            return None
        return self._fetch_best_detail(works, query, _clean(year) or None)

    def _fetch_best_detail(
        self,
        candidates: List[Dict[str, Any]],
        query: str,
        target_year: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """取出「最像关键词、且数据最全」的那条详情。

        ⚠️ **站点会给同一部剧建多条记录。** 实测 ``/drama/40354`` 与 ``/drama/40445``
        标题、简介、首播日期**一字不差**，但 40354 是 AI 版（没有演员 / 集数 / 时长 /
        出品方，``kind = AI短剧``），40445 是真人版（字段齐全，``kind = 真人短剧``）；
        两个页面**互不引用**，站点也不提供任何「谁是正版」的标注。

        光看候选标题分不出谁是谁，所以**并列时**逐条抓下来比「字段完整度」
        （:meth:`_richness`），取数据全的那条 —— 同名并列最多抓 2 条，第 2 条还会进
        TTL 缓存，后续识别零成本。
        """
        ranked = self._rank(candidates, query, target_year)
        if not ranked:
            return None
        top = ranked[0][0]
        tied = [row for score, row in ranked if score == top][:2]
        records: List[Dict[str, Any]] = []
        for row in tied:
            record = self._fetch_detail(
                _clean(str(row.get("native_id") or "")), _clean(str(row.get("url") or ""))
            )
            if record is not None:
                records.append(record)
        if not records:
            return None
        # ``max`` 在并列时取第一个 ⇒ 分数更高的那条优先保留
        return max(records, key=self._richness)

    @staticmethod
    def _rank(
        candidates: List[Dict[str, Any]],
        query: str,
        target_year: Optional[str] = None,
    ) -> List[Tuple[int, Dict[str, Any]]]:
        """按片名接近程度给候选打分并降序排（年份命中加权，年份不符扣分）。

        字面对不上的候选（``score <= 0``）直接不留 —— 站外索引的召回本来就不稳。
        """
        scored: List[Tuple[int, Dict[str, Any]]] = []
        for row in candidates:
            title = _clean(row.get("label") or row.get("title") or "")
            score = _match_title(title, query)
            if score <= 0:
                continue
            if target_year and row.get("year"):
                score += 10 if str(row["year"]) == str(target_year) else -15
            scored.append((score, row))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return scored

    @classmethod
    def _pick_best(
        cls,
        candidates: List[Dict[str, Any]],
        query: str,
        target_year: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """按片名接近程度挑最像的一条（年份命中加权，年份不符扣分）。"""
        ranked = cls._rank(candidates, query, target_year)
        return ranked[0][1] if ranked else None

    @staticmethod
    def _richness(record: Optional[Dict[str, Any]]) -> int:
        """给一条详情记录打「完整度」分（同名多版本时用它择优）。

        权重按「缺了最影响使用」排：**演员 > 集数 ≈ 时长 > 其余**。AI 短剧几乎恒缺演员，
        所以 ``actors`` 权重最高。
        """
        if not record:
            return -1
        score = 0
        for field, weight in _RICHNESS_WEIGHTS:
            value = record.get(field)
            if isinstance(value, str):
                has = bool(value.strip())
            elif isinstance(value, (list, tuple, dict, set)):
                has = bool(value)
            else:
                has = value not in (None, 0, 0.0, "")
            if has:
                score += weight
        return score

    # ── TMDB 身份补充 ─────────────────────────────────────────────

    def _tmdb_identity(self, record: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """给**确实存在于 TMDB** 的作品补上真实 ``tmdb_id``（+ 分季信息）。

        为什么值得多打一次 TMDB：宿主详情页里右侧信息面板（评分 / 状态 / 首播 / 出品方）、
        演职员区、推荐 / 相似、分季分集**全部挂在 ``tmdb_id`` 上**，而这些区块的内容是宿主自己
        拿这个 ID 去 TMDB 取的（``/api/v1/tmdb/credits/{id}`` 等）。短剧大多不在 TMDB 上
        （实测抽 14 部只命中 1 部），所以这里只做「有就附、没有就算」，且 :mod:`tmdb` 里
        用的是严格匹配（同名 + 年份一致）—— 附错 ID 会把页面连到另一部剧。

        任何异常都吞掉：身份补充失败绝不能影响识别本身。
        """
        if not record or self._tmdb is None:
            return {}
        cached = record.get("tmdb_identity")
        if isinstance(cached, dict):
            return dict(cached)
        try:
            extra = self._tmdb.enrich(
                _clean(record.get("title")),
                record.get("year") or record.get("release_date"),
            )
        except Exception as err:  # pragma: no cover - 兜底
            logger.debug(f"{PLUGIN_NAME} TMDB 身份补充失败：{type(err).__name__}: {err}")
            return {}
        if extra:
            # 落进 record：面板的「原始数据」与跨插件载荷都能看到 —— ``tmdb_id`` 在
            # PUBLIC_RECORD_FIELDS 里（对外可见），``tmdb_identity`` 是内部结构（含
            # season_info，不进对外载荷，只给 MediaInfo 用）
            record["tmdb_identity"] = extra
            if extra.get("tmdb_id"):
                record["tmdb_id"] = extra["tmdb_id"]
        return extra

    # ── 模块接口：识别（宿主静态合同）──────────────────────────────

    @classmethod
    def _meta_keywords(cls, meta: Any) -> List[str]:
        """按**宿主 TMDB 源的口径**准备候选检索名（有序、去重、去空）。

        照 ``app/modules/themoviedb`` 的 ``_prepare_search_names`` 写::

            zh_name = zhconv_convert(meta.cn_name, "zh-hans") if meta.cn_name else None
            return list(dict.fromkeys([k for k in [meta.cn_name, zh_name, meta.en_name] if k]))

        两点必须跟住：

        1. **绝不拿 ``meta.title`` 检索** —— 它是原始文件名（容器内实测
           ``MetaInfo('雾锁情迷 - S01E71.mp4')`` → ``title = '雾锁情迷 - S01E71.mp4'``、
           ``cn_name = '雾锁情迷'``）。以前我们读的就是 ``title``，脏串被一路带进三个
           地方：① 扔给搜索引擎（``site:… 雾锁情迷 - S01E71``）→ 召回更差；② 当 URL
           库的匹配键 → 库里存着「雾锁情迷」却查不回来（``UrlStore.match`` 比的是归一化
           后的**相等**）；③ 当检索节流的键（``_searched_at``）→ 同一个脏键刚查过就被
           ``SEARCH_RETRY_INTERVAL`` 挡 300s，日志上是「库里只有作品 0／本次不问引擎」，
           看着就像插件坏了。
        2. **中文名之外再补一个简体写法** —— TMDB 在链路里挨个试，第一个有结果就停
           （``themoviedb/__init__.py`` 的 ``SEARCH_NAME`` 循环）。本站是简体中文站，
           而文件名与引擎结果都可能带繁体，简体候选正好补这段差距。

        ⚠️ **英文名不给候选**（TMDB 那份清单里有，我们不照抄）：本站只收中文短剧，
           英文名既搜不到又会白白打一次搜索引擎（引擎侧有 3 秒最小间隔）。

        ⚠️ ``cn_name`` 缺失时才退回 ``name`` / ``title``：宿主的部分入口（搜索框、订阅）
        会直接 ``MetaInfo(title=关键词)``，那时只有这两个字段有值，而且还可能是带扩展名
        的原始串，所以一律过一遍 :func:`parser.video_name_of`。
        """
        cn = video_name_of(getattr(meta, "cn_name", "") or "")
        if not cn:
            for attr in ("name", "title"):
                cn = video_name_of(getattr(meta, attr, "") or "")
                if cn:
                    break
        names: List[str] = []
        for value in (cn, cls._to_simplified(cn)):
            if value and value not in names:
                names.append(value)
        return names[:MAX_META_KEYWORDS]

    @staticmethod
    def _to_simplified(text: str) -> str:
        """繁体 → 简体（宿主 TMDB 源同一入口）。拿不到就返回空串，交给别的候选。"""
        if not text or zhconv_convert is None:
            return ""
        try:
            return _clean(zhconv_convert(text, "zh-hans"))
        except Exception as err:  # pragma: no cover - 宿主 native 转换异常
            logger.debug(f"{PLUGIN_NAME} 简繁转换失败：{err}")
            return ""

    def recognize_media(
        self,
        media_source: Any = None,
        media_id: str = "",
        meta: Any = None,
        **kwargs: Any,
    ) -> Any:
        """按 ``media_id``（``duanju:<id>``，兼容旧前缀 ``org:``）或片名识别一部短剧。

        ⚠️ ``media_source`` 不是本来源时**必须返回 None** —— 宿主默认识别源是 TMDB，
        插件绝不能把别的来源的识别请求接过来。
        """
        if not self._enabled or not self._is_our_source(media_source):
            return None
        keywords = self._meta_keywords(meta) if meta is not None else []
        record = None
        if _clean(media_id):
            record = self._resolve_item(media_id=_clean(media_id))
        if record is None:
            # 与宿主 TMDB 源同款：候选名挨个试，**第一个有结果就停**
            # （``themoviedb/__init__.py`` 的 ``SEARCH_NAME`` 循环）
            for keyword in keywords:
                record = self._resolve_item(
                    keyword=keyword,
                    year=_clean(getattr(meta, "year", "")),
                )
                if record is not None:
                    break
        if record is None:
            logger.debug(
                f"{PLUGIN_NAME} 识别未命中：media_id={_clean(media_id) or '-'}"
                f" 片名={'/'.join(keywords) or '-'}"
            )
            return None
        logger.debug(
            f"{PLUGIN_NAME} 识别命中：{record.get('media_id')}《{record.get('title')}》"
            f"（完整度 {self._richness(record)}）"
        )
        return build_media_info(record, self._tmdb_identity(record))

    async def async_recognize_media(self, *args: Any, **kwargs: Any) -> Any:
        return await asyncio.to_thread(self.recognize_media, *args, **kwargs)

    # ── 模块接口：检索（宿主静态合同）─────────────────────────────

    def search_medias(
        self,
        meta: Any = None,
        media_source: Any = None,
        **kwargs: Any,
    ) -> List[Any]:
        """按片名返回候选列表（宿主搜索框 / 订阅 / 别的插件都能用）。

        未限定 ``media_source`` 时视为宿主**全局检索**，由 ``search_in_global`` 决定
        是否参与；点名的其它来源一律不接手。
        """
        if not self._enabled:
            return []
        if media_source is None:
            if not self._search_in_global:
                return []
        elif not self._is_our_source(media_source):
            return []
        keywords = self._meta_keywords(meta) if meta is not None else []
        if not keywords:
            return []
        year = _clean(getattr(meta, "year", ""))
        query = ""
        works: List[Dict[str, Any]] = []
        # 与识别同一份「候选名挨个试」的口径（照宿主 TMDB 源的 SEARCH_NAME 循环）
        for candidate in keywords:
            works, _ = self._resolve(candidate)
            if works:
                query = candidate
                break
        if not works:
            logger.debug(f"{PLUGIN_NAME} 检索「{keywords[0]}」没有拿到作品候选")
            return []
        scored: List[Tuple[int, Dict[str, Any]]] = []
        for row in works:
            score = _match_title(_clean(row.get("label") or row.get("title") or ""), query)
            if score <= 0:
                # 站外索引召回本来就不稳（实测「王石」会带出「王碩」），字面对不上的
                # 候选一律不留 —— 否则宿主搜索页会冒出一堆与片名无关的条目
                continue
            if year and str(row.get("year") or "") == str(year):
                score += 10
            scored.append((score, row))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        # 分数相同时用「数据完整度」破平：站点会给同一部剧建多条记录（真人版 / AI 版），
        # 标题一字不差，只有抓下详情才知道谁全 —— 让全的那条排在前面。
        pairs: List[Tuple[int, int, int, Any]] = []
        for index, (score, row) in enumerate(scored[:MAX_CANDIDATES]):
            native_id = _clean(str(row.get("native_id") or ""))
            record: Optional[Dict[str, Any]] = None
            # 前两条抓详情（有 TTL 缓存，命中时零请求），其余用库里的标题给轻量候选
            if index < 2:
                record = self._fetch_detail(native_id, str(row.get("url") or ""))
            if record is None:
                title = _clean(row.get("label") or "")
                if not title or not native_id:
                    continue
                # 详情页没抓到也要给一条**可路由**的候选：``media_id`` 是宿主的身份键，
                # 缺了它这条记录连构造都构造不出来（会被整条丢掉）
                record = {
                    "media_id": f"{MEDIA_ID_PREFIX}:{native_id}",
                    "title": title,
                    "url": str(row.get("url") or ""),
                    "native_id": native_id,
                }
            info = build_media_info(record, self._tmdb_identity(record))
            if info is not None:
                pairs.append((score, self._richness(record), index, info))
        pairs.sort(key=lambda item: (-item[0], -item[1], item[2]))
        if pairs:
            logger.info(
                f"{PLUGIN_NAME} 检索「{query}」命中 {len(pairs)} 条候选"
                f"（最高分 {pairs[0][0]}，完整度 {pairs[0][1]}）"
            )
        else:
            logger.debug(f"{PLUGIN_NAME} 检索「{query}」候选全部与片名对不上，已剔除")
        return [info for _, _, _, info in pairs]

    async def async_search_medias(self, *args: Any, **kwargs: Any) -> List[Any]:
        return await asyncio.to_thread(self.search_medias, *args, **kwargs)

    # ── 模块接口：补图（宿主静态合同）─────────────────────────────

    def obtain_images(self, mediainfo: Any = None, **kwargs: Any) -> Any:
        """补齐海报 / 背景图。

        两件事：缺海报时按 ``media_id`` 重新解析一次；缺背景图时用海报顶上 ——
        宿主媒体详情页的大图位用的正是 ``backdrop``，空着就是一片灰。

        未启用、来源不是本插件、或压根没给对象时**原样透传**：宿主会直接把返回值
        并入媒体信息，透传比返回 None 更保险（调用方不需要额外判空）。
        """
        if not self._enabled or mediainfo is None:
            return mediainfo
        if not self._is_our_source(getattr(mediainfo, "media_source", None)):
            return mediainfo
        if not _clean(getattr(mediainfo, "poster_path", "")):
            record = self._resolve_item(media_id=_clean(getattr(mediainfo, "media_id", "")))
            poster = _normalize_image((record or {}).get("poster"))
            if poster:
                try:
                    mediainfo.poster_path = poster
                except Exception as err:  # pragma: no cover - 只读模型兜底
                    logger.debug(f"{PLUGIN_NAME} 写入海报失败：{err}")
        if not _clean(getattr(mediainfo, "backdrop_path", "")) and _clean(
            getattr(mediainfo, "poster_path", "")
        ):
            try:
                mediainfo.backdrop_path = mediainfo.poster_path
            except Exception as err:  # pragma: no cover - 只读模型兜底
                logger.debug(f"{PLUGIN_NAME} 写入背景图失败：{err}")
        return mediainfo

    async def async_obtain_images(self, *args: Any, **kwargs: Any) -> Any:
        return await asyncio.to_thread(self.obtain_images, *args, **kwargs)

    # ── 演员数据（供其它插件调用）────────────────────────────────

    def search_actors(self, name: str = "", **kwargs: Any) -> List[Dict[str, Any]]:
        """按姓名查演员候选：``actor_id`` / ``name`` / ``media_id`` / ``url``。

        走 URL 库（库里没有就查一次引擎并入库），**不抓演员页** —— 要看作品用
        :meth:`actor_works`。
        """
        query = _clean(name)
        if not query or not self._enabled:
            return []
        _, actors = self._resolve(query)
        if not actors:
            logger.debug(f"{PLUGIN_NAME} 演员检索「{query}」没有候选")
            return []
        ranked: List[Tuple[int, Dict[str, Any]]] = []
        for row in actors:
            label = _clean(row.get("label") or "")
            score = _match_title(label, query)
            if score <= 0:
                continue
            ranked.append((score, row))
        ranked.sort(key=lambda pair: pair[0], reverse=True)
        results: List[Dict[str, Any]] = []
        for _, row in ranked[:MAX_ACTOR_CANDIDATES]:
            actor_id = _clean(str(row.get("native_id") or ""))
            if not actor_id:
                continue
            results.append({
                "actor_id": actor_id,
                "name": _clean(row.get("label") or ""),
                "media_id": f"{ACTOR_ID_PREFIX}:{actor_id}",
                "url": _clean(row.get("url") or ""),
                "source": "web_index",
            })
        logger.debug(f"{PLUGIN_NAME} 演员检索「{query}」回 {len(results)} 位候选")
        return results

    async def async_search_actors(self, *args: Any, **kwargs: Any) -> List[Dict[str, Any]]:
        return await asyncio.to_thread(self.search_actors, *args, **kwargs)

    def _resolve_actor(self, actor_id: str = "", name: str = "") -> Optional[Dict[str, Any]]:
        """演员 ID 或姓名 → 演员档案（抓页面并解析）。"""
        native_id = self._actor_native_id(actor_id)
        url = ""
        if native_id:
            url = self._url_for_native("actor", native_id)
        if not native_id and _clean(name):
            candidates = self.search_actors(name=_clean(name))
            if candidates:
                native_id = _clean(candidates[0].get("actor_id") or "")
                url = _clean(candidates[0].get("url") or "")
        if not native_id:
            return None
        return self._fetch_actor(native_id, url)

    def _enrich_works(
        self,
        profile: Dict[str, Any],
        limit: int = ACTOR_WORKS_ENRICH_LIMIT,
    ) -> int:
        """给演员档案里的作品条目**补详情页字段**，返回补了几部。

        演员页卡片是摘要：题材标签只印 1~3 个、没有版权方、没有简介与剧照。要这些
        只能抓详情页 —— 一个演员动辄几十部作品（实测曹天恺 42 部），全抓一遍既不现实
        也容易撞站点风控，所以限量补前 ``limit`` 部；详情有 TTL 缓存，补过的零成本。

        只覆盖**详情页才有**的字段，卡片上已有的（片名 / 海报 / 集数 / 评分 / 热度）
        保持不动 —— 补抓是为了补齐，不是为了改写。
        """
        works = profile.get("works") or []
        if not isinstance(works, list) or limit <= 0:
            return 0
        fields = (
            "tags", "studio", "release_date", "year", "episode_count",
            "duration_minutes", "episode_minutes", "overview", "backdrop",
        )
        filled = 0
        for work in works[:limit]:
            if not isinstance(work, dict):
                continue
            native_id = _clean(work.get("native_id"))
            if not native_id:
                continue
            detail = self._fetch_detail(native_id, _clean(work.get("url")))
            if not detail:
                continue
            for field in fields:
                if _has_value(detail.get(field)):
                    work[field] = detail[field]
            filled += 1
        if filled:
            logger.info(
                f"{PLUGIN_NAME} 演员「{profile.get('name') or '?'}」作品补全 {filled} 部"
                f"（共 {len(works)} 部，上限 {limit}）：补上完整标签 / 首播 / 版权方 / 时长"
            )
        return filled

    def actor_works(self, actor_id: str = "", name: str = "", **kwargs: Any) -> List[Dict[str, Any]]:
        """查一位演员参演的全部作品（**跨插件调用的主入口**）。

        ``actor_works(actor_id="371")`` 最省事（库里直接有 URL，零引擎请求）；
        只有姓名时先解析出 ID 再抓演员页。

        ``enrich=True`` 时给作品条目补抓详情页（完整标签 / 首播 / 版权方 / 时长），
        最多补 ``ACTOR_WORKS_ENRICH_LIMIT`` 部 —— 默认**不补**：跨插件批量调用不该
        为了几个标签搭上几十次请求。
        """
        if not self._enabled:
            return []
        profile = self._resolve_actor(actor_id=actor_id, name=name)
        if not profile:
            logger.debug(
                f"{PLUGIN_NAME} 取不到演员档案：actor_id={_clean(actor_id) or '-'}"
                f" 姓名={_clean(name) or '-'}"
            )
            return []
        if kwargs.get("enrich"):
            self._enrich_works(profile)
        works = [dict(work) for work in (profile.get("works") or [])]
        logger.debug(
            f"{PLUGIN_NAME} 演员「{profile.get('name')}」（{profile.get('actor_id') or _clean(actor_id)}）"
            f"回 {len(works)} 部作品"
        )
        return works

    async def async_actor_works(self, *args: Any, **kwargs: Any) -> List[Dict[str, Any]]:
        return await asyncio.to_thread(self.actor_works, *args, **kwargs)

    def actor_profile(
        self, actor_id: str = "", name: str = "", enrich: bool = False
    ) -> Dict[str, Any]:
        """取演员完整档案（含全部作品与合作演员）—— 纯 JSON，供外部消费。

        ``enrich=True`` 时给作品条目补抓详情页（完整标签 / 首播 / 版权方 / 时长），
        最多补 ``ACTOR_WORKS_ENRICH_LIMIT`` 部。
        """
        if not self._enabled:
            return {}
        profile = self._resolve_actor(actor_id=actor_id, name=name)
        if not profile:
            return {}
        if enrich:
            self._enrich_works(profile)
        return build_public_actor(profile)

    # ── HTTP 接口 ─────────────────────────────────────────────────

    def get_api(self) -> List[Dict[str, Any]]:
        """插件自有 HTTP 接口。

        ⚠️ 全部声明 ``auth: "bear"``：宿主把它映射成 ``verify_token``，而那个依赖
        **同时接受 JWT（面板登录态）与 ``X-API-KEY``（外部脚本）** —— 一套接口两边通吃。
        """
        return [
            {
                "path": "/lookup",
                "methods": ["GET"],
                "endpoint": self.api_lookup,
                "summary": "面板搜索框的后端：一个关键词，作品与演员两边一起回",
                "auth": "bear",
            },
            {
                "path": "/recognize",
                "methods": ["GET"],
                "endpoint": self.api_recognize,
                "summary": "作品出口：media_id 或 keyword 取一条完整作品记录（纯 JSON）",
                "auth": "bear",
            },
            {
                "path": "/actor",
                "methods": ["GET"],
                "endpoint": self.api_actor,
                "summary": "演员出口：actor_id 或 name 取演员档案与全部作品（纯 JSON）",
                "auth": "bear",
            },
            {
                "path": "/urls",
                "methods": ["GET"],
                "endpoint": self.api_urls,
                "summary": "URL 库：统计 + 最近入库记录，或按关键词查询",
                "auth": "bear",
            },
            {
                "path": "/urls/clear",
                "methods": ["POST"],
                "endpoint": self.api_urls_clear,
                "summary": "清空 URL 库：不给参数＝整库清空，可只清某一类或某个关键词",
                "auth": "bear",
            },
            {
                "path": "/status",
                "methods": ["GET"],
                "endpoint": self.api_status,
                "summary": "运行状态：URL 库容量、缓存、站外索引配置",
                "auth": "bear",
            },
            {
                "path": "/config",
                "methods": ["GET"],
                "endpoint": self.api_get_config,
                "summary": "读配置与候选值（面板配置页回显）",
                "auth": "bear",
            },
            {
                "path": "/config",
                "methods": ["PUT"],
                "endpoint": self.api_update_config,
                "summary": "存配置（逐键合并 + 归一化）",
                "auth": "bear",
            },
            {
                "path": "/probe",
                "methods": ["GET"],
                "endpoint": self.api_probe,
                "summary": "连通性自检：URL 库 / 引擎 / 详情页 / 演员页逐项报告",
                "auth": "bear",
            },
        ]

    def api_lookup(self, keyword: str = "", year: str = "") -> Dict[str, Any]:
        """``GET /lookup`` —— 面板**唯一那个搜索框**的后端：一个词，两边都试。

        先查 URL 库（命中即零引擎请求），库里没有才检索一次；一次检索的结果同时喂给
        「作品」与「演员」两条解析路。
        """
        query = _clean(keyword)
        if not query:
            return {"success": False, "message": "缺少 keyword 参数",
                    "keyword": "", "titles": [], "actors": []}
        if not self._enabled:
            return {"success": False, "message": "插件未启用",
                    "keyword": query, "titles": [], "actors": []}
        works, actors = self._resolve(query)
        # 先把**全部**候选打完分再截断：先截断后打分会让一条低分候选把真正对得上的挤出去
        ranked_titles: List[Tuple[int, Dict[str, Any]]] = []
        for row in works:
            native_id = _clean(str(row.get("native_id") or ""))
            if not native_id:
                continue
            title = _clean(row.get("label") or "")
            score = _match_title(title, query)
            if score <= 0:
                # 召回不稳是这条通道的固有属性，字面对不上的候选不该占着面板位置
                continue
            ranked_titles.append((score, {
                "media_id": f"{MEDIA_ID_PREFIX}:{native_id}",
                "title": title,
                "native_id": native_id,
                "url": _clean(row.get("url") or ""),
                "from": _clean(row.get("from") or ""),
                "score": score,
            }))
        # 面板上写着「按匹配分排序」，这里就必须真排（此前只有演员那半边排了）
        ranked_titles.sort(key=lambda pair: pair[0], reverse=True)
        titles = [row for _, row in ranked_titles[:MAX_CANDIDATES]]
        # 同名多版本：站点会给同一部剧建多条记录（实测真人版 40445 与 AI版 40354 标题
        # 一字不差），面板得能提示「这条还有别的版本」，否则用户无从判断该点哪一条。
        title_counts: Dict[str, int] = {}
        for row in titles:
            key = _normalize_title(row["title"])
            title_counts[key] = title_counts.get(key, 0) + 1
        for row in titles:
            count = title_counts[_normalize_title(row["title"])]
            if count > 1:
                row["same_title"] = count
        ranked_actors: List[Tuple[int, Dict[str, Any]]] = []
        for row in actors:
            label = _clean(row.get("label") or "")
            score = _match_title(label, query)
            if score > 0:
                ranked_actors.append((score, row))
        ranked_actors.sort(key=lambda pair: pair[0], reverse=True)
        cast: List[Dict[str, Any]] = []
        for score, row in ranked_actors[:MAX_ACTOR_CANDIDATES]:
            native_id = _clean(str(row.get("native_id") or ""))
            if not native_id:
                continue
            cast.append({
                "actor_id": native_id,
                "media_id": f"{ACTOR_ID_PREFIX}:{native_id}",
                "name": _clean(row.get("label") or ""),
                "url": _clean(row.get("url") or ""),
                "from": _clean(row.get("from") or ""),
                "score": score,
            })
        hit = bool(titles or cast)
        if not hit:
            # 面板 0 命中是最常被反馈的现象，把**原因**留在日志里（界面上只给一句提示）
            logger.info(f"{PLUGIN_NAME} 面板搜索「{query}」0 命中：{self._miss_reason(query)}")
        return {
            "success": hit,
            "message": "" if hit else self._miss_reason(query),
            "keyword": query,
            "year": _clean(year),
            "titles": titles,
            "actors": cast,
        }

    def _miss_reason(self, query: str) -> str:
        """「没搜到」按**真实原因**给提示 —— 开关关着却怪引擎召回差会把人带偏。"""
        if not self._web_index_search:
            return "没搜到：站外索引已关闭。到插件设置里打开「搜索引擎检索」再试。"
        if not self._web_index.available:
            return "没搜到：宿主环境里没有搜索引擎依赖（ddgs），站外索引不可用。"
        return (
            f"没搜到「{query}」：片名与演员名都走的「搜索引擎 site: 收录」，"
            "它召回不稳定、也基本只认完整名字 —— 换成完整片名或演员全名再试一次。"
        )

    def api_recognize(self, media_id: str = "", keyword: str = "", year: str = "") -> Dict[str, Any]:
        """``GET /recognize`` —— 作品出口（纯 JSON，供其它插件与脚本消费）。"""
        if not _clean(media_id) and not _clean(keyword):
            return {"success": False, "message": "需要 media_id 或 keyword 之一", "record": None}
        record = self._resolve_item(media_id=_clean(media_id), keyword=_clean(keyword), year=_clean(year))
        if record is None:
            return {"success": False, "message": "没找到对应作品", "record": None}
        return {"success": True, "record": build_public_record(record, origin="detail")}

    def api_actor(self, actor_id: str = "", name: str = "", enrich: str = "") -> Dict[str, Any]:
        """``GET /actor`` —— 演员出口（纯 JSON，含全部作品与合作演员）。

        ``enrich=1`` 时给作品条目补抓详情页（完整标签 / 首播 / 版权方 / 时长），最多补
        ``ACTOR_WORKS_ENRICH_LIMIT`` 部 —— 面板上是按需补（点哪部补哪部），这个参数
        给外部脚本一次性拿全用。
        """
        if not _clean(actor_id) and not _clean(name):
            return {"success": False, "message": "需要 actor_id 或 name 之一", "actor": None}
        profile = self.actor_profile(
            actor_id=_clean(actor_id),
            name=_clean(name),
            enrich=_clean(enrich).lower() in ("1", "true", "yes", "on"),
        )
        if not profile:
            return {"success": False, "message": "没找到该演员", "actor": None}
        return {"success": True, "actor": profile}

    def api_urls(self, keyword: str = "", kind: str = "", limit: str = "50") -> Dict[str, Any]:
        """``GET /urls`` —— 查看 URL 库（统计 + 最近记录 / 按关键词查）。

        「按关键词查」走的是宽松匹配（键 / 标题 / 触发词任一命中）：一个页面只留一条记录，
        面板上按片名能查出这部剧以及搜它时顺带发现的演员。
        """
        store = self._store()
        if store is None:
            return {"success": False, "message": "插件数据库不可用",
                    "stats": self._store_count(), "records": []}
        query = _clean(keyword)
        records: List[Dict[str, Any]] = []
        if query:
            key = _normalize_title(query)
            for entry_kind in ([_clean(kind)] if _clean(kind) else ["work", "actor"]):
                records.extend(row.as_dict() for row in store.match(entry_kind, key))
        else:
            records = store.recent(limit=int(_as_int(limit, 50) or 50), kind=_clean(kind))
        return {"success": True, "stats": self._store_count(), "records": records}

    def api_urls_clear(self, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """``POST /urls/clear`` —— 清库（面板上的「清空库」按钮与脚本共用）。

        范围由 ``kind`` / ``keyword`` 决定：两个都不给＝**整库清空**；只给 ``kind`` ＝
        清掉该类全部；两个都给＝清掉该关键词的记录。

        清完顺手把「最近问过引擎」的时间戳清掉 —— 否则刚清完再搜同一个词会被
        ``SEARCH_RETRY_INTERVAL`` 挡住，界面上只是「没搜到」，很容易误判成插件坏了。
        """
        body = payload if isinstance(payload, dict) else {}
        if payload is not None and not isinstance(payload, dict):
            # 非字典请求体（数组 / 字符串）当成空对象会**静默整库清空** —— 这是破坏性接口，
            # 宁可报错也不能猜
            return {"success": False, "message": "请求体必须是 JSON 对象",
                    "removed": 0, "stats": self._store_count()}
        kind = _clean(str(body.get("kind") or ""))
        keyword = _clean(str(body.get("keyword") or ""))
        if kind and kind not in ("work", "actor"):
            return {"success": False, "message": "kind 只能是 work 或 actor",
                    "removed": 0, "stats": self._store_count()}
        store = self._store()
        if store is None:
            return {"success": False, "message": "插件数据库不可用",
                    "removed": 0, "stats": self._store_count()}
        try:
            removed = store.forget(kind, _normalize_title(keyword) if keyword else "")
        except Exception as err:  # pragma: no cover - 数据库异常
            logger.warning(f"{PLUGIN_NAME} 清库失败：{err}")
            return {"success": False, "message": f"清库失败：{err}",
                    "removed": 0, "stats": self._store_count()}
        if not keyword:
            self._searched_at.clear()  # 允许马上重新检索同一个词
        scope = "、".join(part for part in (
            f"类型 {kind}" if kind else "", f"关键词「{keyword}」" if keyword else "") if part) or "整库"
        logger.warning(f"{PLUGIN_NAME} 手动清库（{scope}）：删除 {removed} 条")
        return {
            "success": True,
            "message": f"已清空 {scope}，删除 {removed} 条",
            "removed": removed,
            "scope": scope,
            "stats": self._store_count(),
        }

    def api_status(self) -> Dict[str, Any]:
        """``GET /status`` —— 运行状态（面板读它画实况条）。"""
        return {
            "enabled": self._enabled,
            "domain": self._domain,
            "version": PLUGIN_VERSION,
            "store": self._store_count(),
            "cache": {
                "detail": sum(1 for key in self._cache if key.startswith("detail:")),
                "actor": sum(1 for key in self._cache if key.startswith("actor:")),
            },
            "web_index": {
                "available": self._web_index.available,
                "enabled": self._web_index_search,
                "backend": self._web_index_backend,
            },
            "follow_links": self._follow_links,
            "actor": {
                "enabled": bool(self._enabled and self._web_index_search and self._web_index.available),
                "max_candidates": MAX_ACTOR_CANDIDATES,
            },
        }

    @staticmethod
    def _config_options() -> Dict[str, Any]:
        """配置页的候选值（前端不该硬编码引擎后端清单）。"""
        return {"web_index_backends": list(WEB_INDEX_BACKENDS)}

    def api_get_config(self) -> Dict[str, Any]:
        """``GET /config`` —— 当前配置 + 候选值。"""
        return {
            "success": True,
            "config": self._current_config(),
            "options": self._config_options(),
        }

    def api_update_config(self, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """``PUT /config`` —— 逐键合并后落库，并重建运行状态。

        非字典的请求体（``null`` / 数组 / 字符串）一律拒绝：静默当成空对象会把
        「客户端发错了」伪装成「保存成功但什么都没变」。
        """
        if not isinstance(payload, dict):
            return {"success": False, "message": "请求体必须是 JSON 对象", "config": None}
        merged = self._current_config()
        for key in self._default_config():
            if key in payload:
                merged[key] = payload[key]
        normalized = {
            "enabled": bool(merged.get("enabled")),
            "domain": self._as_domain(merged.get("domain"), ORG_DEFAULT_DOMAIN),
            "search_in_global": self._as_bool(merged.get("search_in_global"), True),
            "timeout": self._as_range(merged.get("timeout"), DEFAULT_TIMEOUT, 5, 120),
            "cache_ttl": self._as_range(merged.get("cache_ttl"), DEFAULT_CACHE_TTL, 0, 2592000),
            "web_index_search": self._as_bool(merged.get("web_index_search"), True),
            "web_index_backend": self._as_choice(
                merged.get("web_index_backend"), DEFAULT_WEB_INDEX_BACKEND, WEB_INDEX_BACKENDS
            ),
            "proxy": bool(merged.get("proxy")),
            "follow_links": self._as_bool(merged.get("follow_links"), True),
        }
        self.update_config(normalized)
        self.init_plugin(normalized)
        # 配置保存会重跑 init_plugin（去重 / 重新注册图片域名），记一条便于事后回溯
        # 「用户什么时候改过设置」—— 很多现象（库突然变少、搜索突然没结果）都源自这里
        logger.info(
            f"{PLUGIN_NAME} 配置已更新：启用={normalized['enabled']} "
            f"域名={normalized['domain']} 站外索引={normalized['web_index_backend']}"
            f"｜顺带入库={normalized['follow_links']}"
        )
        return {"success": True, "config": normalized}

    def api_probe(self, keyword: str = "魏依珂") -> Dict[str, Any]:
        """``GET /probe`` —— 连通性自检（逐项给出可诊断的结果，而不是一个布尔值）。"""
        query = _clean(keyword)
        report: Dict[str, Any] = {
            "plugin": PLUGIN_NAME,
            "version": PLUGIN_VERSION,
            "enabled": self._enabled,
            "media_source": MEDIA_SOURCE_KEY,
            "domain": self._domain,
        }
        store = self._store()
        report["store_available"] = store is not None

        works, actors = self._resolve(query) if query else ([], [])
        report["lookup"] = {
            "keyword": query,
            "works": len(works),
            "actors": len(actors),
            "work_sample": [row.get("label") for row in works[:5]],
            "actor_sample": [row.get("label") for row in actors[:5]],
        }
        # 统计算在检索**之后**：检索本身会往库里写 URL，先算会恒定显示 0 条
        report["store"] = self._store_count()

        sample_url = works[0].get("url") if works else ""
        sample_id = str(works[0].get("native_id") or "") if works else PROBE_SAMPLE_MEDIA_ID.split(":")[-1]
        detail = self._fetch_detail(sample_id, sample_url)
        report["detail"] = {
            "media_id": f"{MEDIA_ID_PREFIX}:{sample_id}",
            "title": (detail or {}).get("title", ""),
            "rating": (detail or {}).get("rating"),
            "heat": (detail or {}).get("heat"),
            "play_count": (detail or {}).get("play_count"),
            "episode_count": (detail or {}).get("episode_count"),
            "actors": len((detail or {}).get("actors") or []),
            "related": len((detail or {}).get("related") or []),
            "fields": len(detail or {}),
        }

        actor_id = str(actors[0].get("native_id") or "") if actors else ""
        actor_url = str(actors[0].get("url") or "") if actors else ""
        profile = self._fetch_actor(actor_id, actor_url) if actor_id else None
        report["actor"] = {
            "actor_id": actor_id,
            "name": (profile or {}).get("name", ""),
            "works": (profile or {}).get("works_count", 0),
            "coactors": (profile or {}).get("coactors_count", 0),
        }
        report["ok"] = bool(report["detail"]["title"] or report["actor"]["name"])
        return report

    # ── 配置 ─────────────────────────────────────────────────────

    @staticmethod
    def _default_config() -> Dict[str, Any]:
        """默认配置（须与 ``init_plugin`` 的读取键完全一致）。"""
        return {
            "enabled": False,
            "domain": ORG_DEFAULT_DOMAIN,
            "search_in_global": True,
            "timeout": DEFAULT_TIMEOUT,
            "cache_ttl": DEFAULT_CACHE_TTL,
            "web_index_search": True,
            "web_index_backend": DEFAULT_WEB_INDEX_BACKEND,
            "proxy": False,
            "follow_links": True,
        }

    def _current_config(self) -> Dict[str, Any]:
        """当前生效的配置（键与 ``_default_config`` 完全一致）。"""
        return {
            "enabled": bool(self._enabled),
            "domain": self._domain,
            "search_in_global": bool(self._search_in_global),
            "timeout": self._timeout,
            "cache_ttl": self._cache_ttl,
            "web_index_search": bool(self._web_index_search),
            "web_index_backend": self._web_index_backend,
            "proxy": bool(self._proxy),
            "follow_links": bool(self._follow_links),
        }

    def get_form(self) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Vue 模式下只下发配置模型，配置界面由远程 ``./Config`` 组件渲染。"""
        return [], self._current_config()

    def get_page(self) -> List[Dict[str, Any]]:
        """Vue 模式下页面 JSON 恒为空（详情弹窗由远程 ``./Page`` 组件渲染）。"""
        return []

    # ── HTTP 底座 ─────────────────────────────────────────────────

    def _request(self, url: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """发起一次 GET，失败返回 None（绝不抛异常打断宿主链路）。"""
        if _RequestUtils is None:  # pragma: no cover - 极端兜底
            logger.warning(f"{PLUGIN_NAME} 宿主未提供 HTTP 入口")
            return None
        headers = {
            "User-Agent": USER_AGENT,
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;q=0.9,"
                "image/avif,image/webp,image/apng,*/*;q=0.8"
            ),
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            # 浏览器特征头：让请求更像真实浏览器，免得站点风控收紧时把我们当脚本。
            # ⚠️ Accept-Encoding 故意不设：交给宿主 HTTP 客户端决定。
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

    def _get(self, url: str, params: Optional[Dict[str, Any]] = None) -> Tuple[str, Optional[int]]:
        """取页面正文与状态码（撞风控或 4xx/5xx 时只返回空文本，不改任何状态）。"""
        response = self._request(url, params=params)
        if response is None:
            return "", None
        status = getattr(response, "status_code", None)
        text = getattr(response, "text", "") or ""
        if is_cloudflare_challenge(text, status):
            # 站点风控收紧是**会变的**（实测站内检索页现在恒 403），默认日志级别下
            # 也得看得见，否则只表现为「搜什么都没有」
            logger.warning(f"{PLUGIN_NAME} {url} 撞到站点风控（status={status}）")
            return "", status
        if status is not None and status >= 400:
            logger.debug(f"{PLUGIN_NAME} {url} 返回 {status}（正文 {len(text)} 字节）")
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

    # ── 工具 ─────────────────────────────────────────────────────

    @staticmethod
    def _native_id(media_id: Any) -> str:
        """``duanju:40105`` / ``40105`` → ``40105``；别的前缀一律不认。

        ⚠️ 前缀必须是**白名单**：宿主或别的插件可能把历史形态的复合 ID（``net:duanju:123``）
        塞进来，照单全收会让一个不属于本站的 ID 悄悄变成「本插件的作品 123」，
        白白发一次无关请求。非数字的尾巴同样判空 —— 站点 ID 恒为裸数字。

        ⚠️ ``org:`` 是**历史前缀**（早期版本用过），宿主库里可能还留着按它存的订阅与识别
        记录 —— 继续接受，新产出一律用 :data:`MEDIA_ID_PREFIX`。
        """
        text = _clean(media_id)
        if not text:
            return ""
        head, sep, tail = text.partition(":")
        if sep:
            prefix = head.strip().lower()
            if prefix != MEDIA_ID_PREFIX and prefix not in LEGACY_MEDIA_ID_PREFIXES:
                return ""
            text = _clean(tail)
        return text if text.isdigit() else ""

    @staticmethod
    def _actor_native_id(actor_id: Any) -> str:
        """``actor:371`` / ``371`` → ``371``；别的前缀一律不认（同 :meth:`_native_id`）。"""
        text = _clean(actor_id)
        if not text:
            return ""
        head, sep, tail = text.partition(":")
        if sep:
            if head.strip().lower() != ACTOR_ID_PREFIX:
                return ""
            text = _clean(tail)
        return text if text.isdigit() else ""

    @staticmethod
    def _is_our_source(media_source: Any) -> bool:
        """宿主给的来源可能是枚举、字符串、集合或 None；只有点名本来源时才接手。

        集合形态要一并接住：宿主在「多来源」场景下会把候选来源打包成 list / tuple
        传下来，那种情况应当视为**有**本来源。
        """
        if media_source is None:
            return False
        if isinstance(media_source, (list, tuple, set, frozenset)):
            return any(ShortDramaBaikeSource._is_our_source(item) for item in media_source)
        value = getattr(media_source, "value", media_source)
        return str(value).strip().lower() in MEDIA_SOURCE_ALIASES

    def _domain_host(self) -> str:
        """站点主机名（``https://www.duanjubaike.org/x`` → ``duanjubaike.org``）。"""
        text = _clean(self._domain)
        host = text.split("//")[-1].split("/")[0].strip().lower()
        return host[4:] if host.startswith("www.") else host

    @staticmethod
    def _as_domain(value: Any, default: str) -> str:
        text = _clean(value)
        if not text:
            return default
        if not text.startswith(("http://", "https://")):
            text = "https://" + text
        return text.rstrip("/")

    @staticmethod
    def _as_bool(value: Any, default: bool) -> bool:
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "yes", "on", "开", "是"}

    @staticmethod
    def _as_range(value: Any, default: int, low: int, high: int) -> int:
        try:
            number = int(float(str(value).strip()))
        except (TypeError, ValueError):
            return default
        return max(low, min(high, number))

    @staticmethod
    def _as_choice(value: Any, default: str, options: Tuple[str, ...]) -> str:
        text = _clean(value).lower()
        return text if text in options else default

    @staticmethod
    def _register_image_domains() -> None:
        """把图片站域名补进宿主白名单（否则图片代理会拒收我们的图）。"""
        if _settings is None:  # pragma: no cover - 宿主版本差异
            return
        domains = getattr(_settings, "SECURITY_IMAGE_DOMAINS", None)
        if not isinstance(domains, list):
            return
        added = []
        for domain in IMAGE_DOMAINS:
            if domain not in domains:
                domains.append(domain)
                added.append(domain)
        if added:
            logger.debug(f"{PLUGIN_NAME} 已把图片域名补进宿主白名单：{', '.join(added)}")


def _as_int(value: Any, default: Optional[int] = None) -> Optional[int]:
    """宽容地把入参转成整数（供接口的 query 参数用）。"""
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default
