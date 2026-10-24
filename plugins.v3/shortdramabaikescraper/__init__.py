"""短剧百科刮削源（MoviePilot V3 插件）。

把「短剧百科」（``www.duanjubaike.net``）注册成 MoviePilot 的一等媒体来源
``djbaike``。

P0 范围（计划 §8）：

* 插件骨架：生命周期、``get_media_source`` / ``get_module`` / ``get_api`` / 配置页；
* ``baike`` 表建表 + 仓储 + 缓存门面；
* ``media_id`` 的解析与反推（八类百科实体 + 豆瓣复合前缀）；
* ``/status`` 状态概览、``/cache/clear``。

识别管线（六层）与详情解析在 P1/P2 填充，P0 的 ``recognize_media`` /
``search_medias`` 只做**来源归属判断**后返回空，绝不劫持其它来源。
"""

from __future__ import annotations

import json
import re
from typing import Any, Optional

from app import schemas
from app.schemas import MediaInfo
from app.schemas.types import MediaSource, MediaType
from app.sdk.logging import logger
from app.sdk.plugin import _PluginBase

from . import classify, constants, pages, scrape, whitelist
from .api_models import (
    BaikePageData,
    BaikePageResponse,
    CacheItem,
    CacheItemsData,
    CacheItemsResponse,
    ConfigData,
    ConfigResponse,
    LookupResponse,
    OpResponse,
    OpResult,
    PersonData,
    PersonResponse,
    NovelData,
    NovelResponse,
    NovelWork,
    SearchResponse,
    StatusData,
    StatusResponse,
)
from .cache import CacheFacade
from .hostmedia import to_host_media, to_host_media_list
from .media_id import (
    detail_url,
    image_url,
    is_drama,
    is_known,
    is_novel,
    is_person,
    media_id_of,
)
from .service import (
    DetailService,
    _name_alike,
    _name_key,
    _name_related,
    candidate_to_media_info,
    run_sync,
    shutdown_sync_loop,
)
from .store import BaikeStore
from .title_clean import clean_candidates, has_season_suffix, primary_name, season_of_text

PLUGIN_ID = "ShortDramaBaikeScraper"
SOURCE = MediaSource(constants.MEDIA_SOURCE_ID)


class ShortDramaBaikeScraper(_PluginBase):
    """短剧百科数据源插件。"""

    plugin_name = constants.SOURCE_NAME
    plugin_desc = constants.SOURCE_DESC
    plugin_icon = "Moviepilot_A.png"
    plugin_version = "0.1.6"
    plugin_author = "m216owen"
    author_url = "https://github.com/m215owen"
    plugin_config_prefix = "shortdramabaikescraper_"
    plugin_order = 50
    auth_level = 1

    _enabled: bool = False
    _cache: Optional[CacheFacade] = None
    _detail: Optional[DetailService] = None
    #: 宿主传进来的原始配置（`/config` 端点回读用；`update_config` 会触发
    #: `init_plugin` 重新填充，所以这里始终是「当前生效的那份」）
    _config: dict = {}
    _store = BaikeStore()

    # ── 生命周期 ─────────────────────────────────────────────────────
    def init_plugin(self, config: Optional[dict] = None) -> None:
        """读取配置并准备本次运行状态；必须允许重复调用。"""
        config = config or {}
        self._config = dict(config)
        self._enabled = bool(config.get("enabled", False))

        if self._cache is None:
            self._cache = CacheFacade()
        else:
            # 全插件统一 TTL 跟随系统设置：每次 init（含保存配置）重读一遍
            self._cache.refresh()
        self._detail = DetailService(self._cache, self._store)

        try:
            self._store.ensure_table()
        except Exception as err:  # pragma: no cover - 建表失败不阻断插件加载
            logger.error(f"{constants.SOURCE_NAME} 建表失败：{err}")

        # 海报要能显示：把图床域名登记进宿主的「安全图片域名」
        # （停用时撤回，见 stop_service；失败只 warning，不影响识别）
        whitelist.sync(self._enabled)

        logger.info(
            f"{constants.SOURCE_NAME} 已初始化：启用={self._enabled}"
            f"｜来源标识={constants.MEDIA_SOURCE_ID}"
        )

    def get_state(self) -> bool:
        """返回插件当前是否启用。"""
        return self._enabled

    def get_command(self) -> list[dict]:
        """本插件不注册远程命令。"""
        return []

    def stop_service(self) -> None:
        """释放缓存客户端、停掉同步事件循环并撤回图片白名单；可重复调用。"""
        if self._cache is not None:
            self._cache.close()
        # 同步入口专用 loop 必须一起收掉，否则重载后旧 loop 的 Redis 连接还挂着
        shutdown_sync_loop()
        self._enabled = False
        # 停用后不再需要放行本站图床：只撤本插件登记的那两条
        whitelist.sync(False)
        logger.info(f"{constants.SOURCE_NAME} 已停止")

    # ── 来源声明与模块方法 ───────────────────────────────────────────
    def get_media_source(self) -> list[dict]:
        """声明媒体来源：只支持电视剧（短剧 / 漫剧），并登记来源专有分类字段。

        分类字段（``extensions.djbaike.kind`` = 短剧/漫剧）让规则不再依赖
        ``identity.media_source`` —— 那玩意会被 TMDB 重识别覆盖，按来源写的规则会漏。
        """
        try:
            return [
                schemas.MediaSourceInfo(
                    name=constants.SOURCE_NAME,
                    media_source=SOURCE,
                    media_types=[MediaType.TV],
                    classification_fields=classify.classification_fields(),
                ).model_dump()
            ]
        except Exception as err:  # pragma: no cover - 声明失败只降级
            logger.error(f"{constants.SOURCE_NAME} 来源声明失败：{err}")
            return []

    def get_module(self) -> dict:
        """注册宿主可调用的模块方法。

        ``async_*`` 两个必须有：宿主的识别与搜索端点都是**异步**链路，dispatcher 按
        契约方法名逐插件问，缺了就等于该链路里没有这个插件（搜索界面尤其明显：
        只实现同步版时永远 0 条）。

        ``search_actors`` / ``actor_profile`` / ``actor_works`` / ``list_people`` 是
        **跨插件消费契约**
        （短剧演员订阅按插件 ID 精确取本插件的方法表调用，不走宿主 dispatcher 广播）；
        人物不是 ``MediaInfo``，宿主的识别/搜索契约装不下，单开这四个名字。

        ``metadata_nfo`` / ``metadata_img`` 是**宿主刮削链**的两个出口（整理/手动刮削
        写盘前问）。两个契约都是插件优先 + 非空短路，不实现就只会在日志里留下
        「NFO 文件生成失败」——2026-10-23 补，实现与取舍见 :mod:`scrape`。
        """
        return {
            "recognize_media": self.recognize_media,
            "async_recognize_media": self.async_recognize_media,
            "search_medias": self.search_medias,
            "async_search_medias": self.async_search_medias,
            "search_actors": self.module_search_actors,
            "actor_profile": self.module_actor_profile,
            "actor_works": self.module_actor_works,
            "list_people": self.module_list_people,
            "list_ranks": self.module_list_ranks,
            "rank_medias": self.module_rank_medias,
            "metadata_nfo": self.metadata_nfo,
            "metadata_img": self.metadata_img,
        }

    @staticmethod
    def _is_our_source(media_source: Any) -> bool:
        """判断传入来源是否**包含**本插件；``None`` 视为不匹配。

        宿主 `MediaSourceSelection = Union[MediaSource, Tuple[MediaSource, ...]]` ——
        搜索/识别链路经常传**元组**（多选，甚至只有我们自己一个也包成元组），
        只按单个枚举判身份会把整批请求误判成「非本来源」而静默放弃。
        """
        if media_source is None:
            return False
        items = (
            media_source
            if isinstance(media_source, (tuple, list, set, frozenset))
            else (media_source,)
        )
        for item in items:
            if str(getattr(item, "value", item)).strip() == constants.MEDIA_SOURCE_ID:
                return True
        return False

    @staticmethod
    def _meta_title(meta: Any) -> str:
        """从宿主 ``MetaInfo`` 取**最可信**的候选标题。

        顺序是 ``cn_name → title → name → original_title``，**中文名优先**：

        * 宿主 ``MetaInfoPath`` 会把 ``title`` 覆盖成**整条文件名**
          （``顾机长，太太说自己已守寡三年.Gu.Ji.Zhang…S01E66.1080p…mp4``），
          干净的中文名在 ``cn_name``；拼音在 ``name``。本站只收中文名，拿前两者检索
          必然 0 结果 —— 这是「整理入库识别不到」最直接的一条原因。
        * 入参本来就是纯标题（``MetaInfo("在八月盛夏")``）时三者相同，顺序无影响。
        """
        for attr in ("cn_name", "title", "name", "original_title"):
            value = getattr(meta, attr, None)
            if isinstance(value, str) and value.strip():
                return value.strip()
        if isinstance(meta, dict):
            for key in ("cn_name", "title", "name", "original_title"):
                value = meta.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
        return ""

    @classmethod
    def _meta_titles(cls, meta: Any) -> list[str]:
        """``meta`` 上的全部候选标题，按可信度排序、按「洗干净的剧名」去重。

        识别时逐个试而不是只取一个：``cn_name`` 偶发为空/不全（宿主版本差异），
        退到 ``title`` 由 :mod:`title_clean` 自己洗也能救回来。去重很关键——
        ``cn_name`` 与 ``title`` 洗净后是**同一个**名字，不折叠就会白跑一趟网络。
        """
        out: list[str] = []
        seen_key: set[str] = set()
        seen_raw: set[str] = set()
        for attr in ("cn_name", "title", "name", "original_title"):
            value = getattr(meta, attr, None)
            if not isinstance(value, str) or not value.strip():
                continue
            text = value.strip()
            if text in seen_raw:
                continue
            seen_raw.add(text)
            key = primary_name(text) or text
            if key in seen_key:
                continue
            seen_key.add(key)
            out.append(text)
        if isinstance(meta, dict):
            for name in ("cn_name", "title", "name", "original_title"):
                value = meta.get(name)
                if isinstance(value, str) and value.strip():
                    text = value.strip()
                    if text in seen_raw:
                        continue
                    seen_raw.add(text)
                    key = primary_name(text) or text
                    if key in seen_key:
                        continue
                    seen_key.add(key)
                    out.append(text)
        # 本站只收**中文名**：只要有中文候选，纯 ASCII 的（拼音 / 英文原名）就不必试了，
        # 白跑一趟网络还会占掉「前几个候选」的预算。
        chinese = [name for name in out if re.search(r"[\u4e00-\u9fa5]", name)]
        return chinese or out

    @staticmethod
    def _meta_year(meta: Any) -> str:
        """从宿主 ``MetaInfo`` 取年份（用于同名消歧）。"""
        value = getattr(meta, "year", None)
        if value is None and isinstance(meta, dict):
            value = meta.get("year")
        text = str(value or "").strip()
        return text if text.isdigit() else ""

    @staticmethod
    def _meta_season(meta: Any) -> Optional[int]:
        """季号：宿主解析出的 ``begin_season`` 优先，否则从标题/目录名文本里挖。

        整理插件（``ShortDramaBaikeOrganizer``）按**目录名**直调本插件识别
        （``MetaInfo(title=原始目录名)``），上面没有 ``begin_season`` —— 季号只在
        名字里（``隐身侍卫 S02（90集） 宣嘉橙&金鑫欣 - SKIT``）。不自己挖，
        第 2 季起的发布全部错认到第一季词条（2026-10-23 实测：S02 的 90 集以
        S01E## 落进 Season 1，与真第一季撞车）。
        """
        value = getattr(meta, "begin_season", None)
        if value is None and isinstance(meta, dict):
            value = meta.get("begin_season")
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            parsed = None
        if parsed and parsed >= 1:
            return parsed
        texts: list[str] = []
        for attr in ("org_string", "title", "cn_name", "name", "original_title", "season_episode"):
            text = getattr(meta, attr, None)
            if isinstance(text, str) and text.strip():
                texts.append(text)
        if isinstance(meta, dict):
            for key in ("org_string", "title", "cn_name", "name", "original_title", "season_episode"):
                text = meta.get(key)
                if isinstance(text, str) and text.strip():
                    texts.append(text)
        for text in texts:
            hit = season_of_text(text)
            if hit and hit >= 1:
                return hit
        return None

    @staticmethod
    def _meta_source(meta: Any) -> Any:
        """取 ``meta`` 自带的来源（宿主有时放这里，而不是 ``recognize_media`` 入参）。"""
        if meta is None:
            return None
        value = getattr(meta, "media_source", None)
        if value is None and isinstance(meta, dict):
            value = meta.get("media_source")
        return value or None

    @staticmethod
    def _meta_media_id(meta: Any) -> str:
        """取 ``meta`` 自带的 ``media_id``（宿主批量整理时可能放在这）。"""
        if meta is None:
            return ""
        value = getattr(meta, "media_id", None)
        if value is None and isinstance(meta, dict):
            value = meta.get("media_id")
        return str(value or "").strip()

    @staticmethod
    def _looks_like_short_drama(meta: Any, title: str) -> bool:
        """判断「这条有没有短剧的样子」——用于**未指定来源**时避免劫持其它来源。

        宿主批量整理/自动整理广播给所有插件时不带 ``media_source``；此时如果无条件按名
        识别，任何与站点同名的正剧都会被本插件认领。所以只在标题/原始文件名带明显短剧
        特征时才出网：``《X》``、``短剧/漫剧``、``SKIT/GodDramas``、``（80集）/全80集``。
        """
        parts = [title]
        for attr in ("org_string", "name", "cn_name", "subtitle"):
            value = getattr(meta, attr, None)
            if isinstance(value, str) and value.strip():
                parts.append(value.strip())
        if isinstance(meta, dict):
            for key in ("org_string", "name", "cn_name", "subtitle"):
                value = meta.get(key)
                if isinstance(value, str) and value.strip():
                    parts.append(value.strip())
        text = " ".join(parts)
        if not text.strip():
            return False
        if re.search(r"短剧|漫剧|SKIT|GodDramas", text, re.I):
            return True
        if re.search(r"[（(]\s*全?\s*\d{1,4}\s*集", text):
            return True
        return bool(re.search(r"全\s*\d{1,4}\s*集", text))

    @staticmethod
    def _meta_snapshot(meta: Any) -> dict:
        """抓 ``meta`` 的关键字段（核对宿主实际传参用，DEBUG 级）。"""
        keys = (
            "title",
            "name",
            "cn_name",
            "en_name",
            "original_title",
            "year",
            "org_string",
            "subtitle",
        )
        if hasattr(meta, "model_dump"):
            data = meta.model_dump()
        elif isinstance(meta, dict):
            data = meta
        else:
            return {}
        return {key: data.get(key) for key in keys if data.get(key)}

    def _resolve(self, target: str):
        """按 ``media_id`` 取单条：理解本插件复合 id，也接受裸豆瓣 id。"""
        if not target or self._detail is None:
            return None
        if is_known(target):
            return self._detail.recognize_sync(target)
        if target.isdigit():
            # 宿主可能把豆瓣裸 id 当 media_id 传进来（订阅从豆瓣导入很常见）
            return run_sync(self._detail.recognize_external(douban_id=target))
        return None

    async def _resolve_async(self, target: str):
        """``_resolve`` 的异步版本。"""
        if not target or self._detail is None:
            return None
        if is_known(target):
            return await self._detail.recognize(target)
        if target.isdigit():
            return await self._detail.recognize_external(douban_id=target)
        return None

    def _pick_guarded_id(self, title: str, meta: Any, candidates: list) -> str:
        """无来源时的选优：**站内结果按名字把关，站内没有就交给豆瓣兜底**。

        站内检索是模糊的，名字对不上就不认（避免把同名正剧劫持过来）；而豆瓣是
        「百科没有时的唯一出口」，它的候选不再按名字筛，直接进选优。

        ⚠️ 把关用的键必须来自**清洗后的候选**（``clean_candidates``），不能拿原始
        ``title``：整理链路给的是整条文件名（``X.Gu.Ji.Zhang…GodDramas.mp4``），
        拿它跟站内的干净剧名比对，长度占比永远过不了 0.6，站内结果会被整批误杀
        → 落进豆瓣 → 认错片或直接「未识别」。
        """
        wanted_keys = [key for key in (_name_key(name) for name in clean_candidates(title)) if key]
        if not wanted_keys:
            return ""
        check = _name_related if self._looks_like_short_drama(meta, title) else _name_alike
        # ⚠️ "mixed" 必须算站内来源。``find_candidates`` 只要站内搜索有结果就把 origin
        # 标成 "mixed"（无论本地是否命中），而这里原先只认 ("local", "site") —— 漏掉
        # mixed 会让「ID 库未收录 + 站内有结果」的候选**整批丢弃**，只剩豆瓣兜底；
        # 豆瓣一旦限流，整体就返回 None。2026-10-22 容器内对照实验实测：
        # origin=local/site/douban 都能选中，origin=mixed 恒返回空。
        site = [c for c in candidates if c.get("origin") in ("local", "site", "mixed")]
        douban_rows = [c for c in candidates if c.get("origin") == "douban"]
        kept = [
            c
            for c in site
            if any(check(wanted, _name_key(c.get("name", ""))) for wanted in wanted_keys)
        ]
        best = self._detail.pick_best(
            kept or douban_rows, year=self._meta_year(meta), season=self._meta_season(meta)
        )
        return str((best or {}).get("media_id") or "")

    def _recognize_by_name_guarded(self, title: str, meta: Any):
        """同步版：按名识别（本地→站内→豆瓣），返回 ``detail`` 之后的 ``MediaInfo``。"""
        candidates = run_sync(
            self._detail.find_candidates(title, season=self._meta_season(meta))
        )
        media_id = self._pick_guarded_id(title, meta, candidates)
        return self._resolve(media_id) if media_id else None

    async def _recognize_by_name_guarded_async(self, title: str, meta: Any):
        """异步版：同上。"""
        candidates = await self._detail.find_candidates(
            title, season=self._meta_season(meta)
        )
        media_id = self._pick_guarded_id(title, meta, candidates)
        return await self._resolve_async(media_id) if media_id else None

    def recognize_media(
        self,
        meta: Any = None,
        media_source: Any = None,
        media_id: Any = None,
        **kwargs: Any,
    ) -> Optional[MediaInfo]:
        """识别：给 ``media_id`` 直取；否则按名跑 ③④⑤⑥ 并收敛成唯一一条。

        ⚠️ **「没有来源」到插件手里已经变成主视频源**。宿主
        ``chain/media/recognition.py`` 有一句::

            if not media_source and isinstance(meta, MetaBase):
                video_kwargs["media_source"] = self._video_primary_source

        （出厂 ``themoviedb``）。所以 ``media_source=themoviedb`` + **无 media_id**
        并不代表「用户选了 TMDB」，而是「自动」。这类请求必须照样参与识别，否则整理
        入库永远轮不到本插件 —— 只按官方 FAQ 的「来源不匹配就让位」写，会把自动识别
        整条链路误杀（2026-10-22 实测：整理预览里 plugin 收到的是 themoviedb）。
        """
        if not self._enabled or self._detail is None:
            return None
        # 宿主有时把「用户选的来源」放在 meta 上而不是入参里，两处都认
        raw_source = media_source if media_source is not None else self._meta_source(meta)
        ours = raw_source is not None and self._is_our_source(raw_source)

        target = str(media_id or "").strip() or self._meta_media_id(meta)
        titles = self._meta_titles(meta)
        # 季号：站点一季一条独立词条，第 2 季起的发布认错季全部错在这儿
        season = self._meta_season(meta)
        if target:
            if not is_known(target):
                # 其它来源的原生 id（tmdbid 之类）不是我们的活
                return None
            try:
                return to_host_media(self._resolve(target))
            except Exception as err:  # pragma: no cover - 异常降级交给下一个来源
                logger.error(f"{constants.SOURCE_NAME} 识别失败 {target}：{err}")
                return None

        if not titles:
            return None
        # ① 本地精确同名：**任何来源都允许认领**（0 网络、同名即准，不会误伤别的来源）
        for title in titles:
            try:
                local_id = self._detail.local_match_seasonal(title, season)
            except Exception as err:  # pragma: no cover
                logger.error(f"{constants.SOURCE_NAME} 本地同名匹配失败 {title}：{err}")
                continue
            if not local_id:
                continue
            try:
                resolved = self._resolve(local_id)
            except Exception as err:  # pragma: no cover
                logger.error(f"{constants.SOURCE_NAME} 本地命中取详情失败 {local_id}：{err}")
                continue
            if resolved is not None:
                return to_host_media(resolved)
        # ② 联网兜底：非本来源又不像短剧时让位，避免把其它来源的正剧劫持过来
        looks = self._looks_like_short_drama(meta, titles[0])
        if not ours and not looks:
            logger.debug(f"{constants.SOURCE_NAME} 非本来源且不像短剧，让位：{titles[0]!r}")
            return None
        logger.debug(f"{constants.SOURCE_NAME} 按名识别入参：{self._meta_snapshot(meta)}")
        for title in titles:
            try:
                if ours:
                    info = self._detail.recognize_by_name_sync(
                        title, year=self._meta_year(meta), season=season
                    )
                else:
                    info = self._recognize_by_name_guarded(title, meta)
            except Exception as err:  # pragma: no cover
                logger.error(f"{constants.SOURCE_NAME} 按名识别失败 {title}：{err}")
                continue
            if info is not None:
                return to_host_media(info)
        return None

    async def async_recognize_media(
        self,
        meta: Any = None,
        media_source: Any = None,
        media_id: Any = None,
        **kwargs: Any,
    ) -> Optional[MediaInfo]:
        """异步版本：宿主异步识别链路优先走这里（判定逻辑与同步版完全一致）。"""
        # 静默返回（未启用 / 非本来源 / 无标题）是最难查的一类"识别不到"：
        # 一条 DEBUG 把三个判据的现场都留下，事后不用再猜宿主传了什么。
        logger.debug(
            f"{constants.SOURCE_NAME} 异步识别入参：enabled={self._enabled} "
            f"source={media_source!r} media_id={media_id!r} title={self._meta_title(meta)!r}"
        )
        if not self._enabled or self._detail is None:
            return None
        raw_source = media_source if media_source is not None else self._meta_source(meta)
        ours = raw_source is not None and self._is_our_source(raw_source)

        target = str(media_id or "").strip() or self._meta_media_id(meta)
        titles = self._meta_titles(meta)
        # 季号：站点一季一条独立词条，第 2 季起的发布认错季全部错在这儿
        season = self._meta_season(meta)
        if target:
            if not is_known(target):
                return None
            try:
                return to_host_media(await self._resolve_async(target))
            except Exception as err:  # pragma: no cover
                logger.error(f"{constants.SOURCE_NAME} 异步识别失败 {target}：{err}")
                return None

        if not titles:
            return None
        # ① 本地精确同名：任何来源都允许认领（0 网络）
        for title in titles:
            try:
                local_id = self._detail.local_match_seasonal(title, season)
            except Exception as err:  # pragma: no cover
                logger.error(f"{constants.SOURCE_NAME} 异步本地同名匹配失败 {title}：{err}")
                continue
            if not local_id:
                continue
            try:
                resolved = await self._resolve_async(local_id)
            except Exception as err:  # pragma: no cover
                logger.error(f"{constants.SOURCE_NAME} 异步本地命中取详情失败 {local_id}：{err}")
                continue
            if resolved is not None:
                return to_host_media(resolved)
        # ② 联网兜底：非本来源又不像短剧时让位
        looks = self._looks_like_short_drama(meta, titles[0])
        if not ours and not looks:
            logger.debug(f"{constants.SOURCE_NAME} 异步非本来源且不像短剧，让位：{titles[0]!r}")
            return None
        logger.debug(f"{constants.SOURCE_NAME} 异步按名识别入参：{self._meta_snapshot(meta)}")
        for title in titles:
            try:
                if ours:
                    info = await self._detail.recognize_by_name(
                        title, year=self._meta_year(meta), season=season
                    )
                else:
                    info = await self._recognize_by_name_guarded_async(title, meta)
            except Exception as err:  # pragma: no cover
                logger.error(f"{constants.SOURCE_NAME} 异步按名识别失败 {title}：{err}")
                continue
            if info is not None:
                return to_host_media(info)
        return None

    def search_medias(
        self,
        meta: Any = None,
        media_source: Any = None,
        **kwargs: Any,
    ) -> list[MediaInfo]:
        """按名搜索：**原样返回全部候选**（同名多条都列出，不做选优）。"""
        if not self._enabled or self._detail is None:
            return []
        raw_source = media_source if media_source is not None else self._meta_source(meta)
        if raw_source is not None and not self._is_our_source(raw_source):
            return []
        title = self._meta_title(meta) or str(
            kwargs.get("keyword") or kwargs.get("name") or kwargs.get("title") or ""
        ).strip()
        if not title:
            return []
        try:
            return to_host_media_list(run_sync(self._detail.search(title)))
        except Exception as err:  # pragma: no cover
            logger.error(f"{constants.SOURCE_NAME} 搜索失败 {title}：{err}")
            return []

    # ── 搜索契约：异步按名搜索（宿主 dispatcher 按契约方法名调用，无需事件装饰） ──
    async def async_search_medias(
        self,
        meta: Any = None,
        media_source: Any = None,
        **kwargs: Any,
    ) -> list[MediaInfo]:
        """按名搜索的**异步**契约方法：宿主 ``/api/v1/media/search`` 走这里。

        为什么必须单独实现（宿主 v3.1.8 实测）：搜索链路是
        ``chain/media/search.py: async_search → async_search_medias``，dispatcher 按
        **契约方法名**逐个问插件。只实现同步的 ``search_medias`` 时，日志里只会出现
        「请求系统模块执行：async_search_medias」，本插件在**搜索界面**等于不存在
        （识别界面走 ``async_recognize_media``，所以那边正常、这边 0 条）。
        """
        if not self._enabled or self._detail is None:
            return []
        raw_source = media_source if media_source is not None else self._meta_source(meta)
        if raw_source is not None and not self._is_our_source(raw_source):
            return []
        title = self._meta_title(meta) or str(
            kwargs.get("keyword") or kwargs.get("name") or kwargs.get("title") or ""
        ).strip()
        if not title:
            return []
        try:
            return to_host_media_list(await self._detail.search(title))
        except Exception as err:  # pragma: no cover
            logger.error(f"{constants.SOURCE_NAME} 异步搜索失败 {title}：{err}")
            return []

    # ── HTTP API ─────────────────────────────────────────────────────
    def get_api(self) -> list[dict]:
        """注册插件路由（路径最终为 ``/api/v1/plugin/<ID>/<path>``）。"""
        return [
            {
                "path": "/config",
                "endpoint": self.api_get_config,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "读取插件配置（Vue 配置页用）",
                "response_model": ConfigResponse,
            },
            {
                "path": "/config",
                "endpoint": self.api_update_config,
                "methods": ["PUT"],
                "auth": "bear",
                "summary": "保存插件配置（整体替换，缺失键取默认值）",
                "response_model": ConfigResponse,
            },
            {
                "path": "/status",
                "endpoint": self.api_status,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "插件状态与 ID 库概览",
                "response_model": StatusResponse,
            },
            {
                "path": "/lookup",
                "endpoint": self.api_lookup,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "按 media_id 查详情 / 按 name 搜候选（作品与演员）",
                "response_model": LookupResponse,
            },
            {
                "path": "/person",
                "endpoint": self.api_person,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "人物档案 + 作品清单（演员 / 导演 / 编剧）",
                "response_model": PersonResponse,
            },
            {
                "path": "/novel",
                "endpoint": self.api_novel,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "原著档案 + 改编作品清单（传剧 id 或原著 id 均可）",
                "response_model": NovelResponse,
            },
            {
                "path": "/search",
                "endpoint": self.api_search,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "本地检索 ID 库（0 网络，供面板自动补全）",
                "response_model": SearchResponse,
            },
            {
                "path": "/baike/list",
                "endpoint": self.api_baike_list,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "ID 库分页（原始 4 列，支持 q 模糊与 entity 过滤）",
                "response_model": BaikePageResponse,
            },
            {
                "path": "/baike/del",
                "endpoint": self.api_baike_del,
                "methods": ["DELETE"],
                "auth": "bear",
                "summary": "删除单条 ID 并联动清其详情缓存",
                "response_model": OpResponse,
            },
            {
                "path": "/baike/clear",
                "endpoint": self.api_baike_clear,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "清空 ID 库",
                "response_model": OpResponse,
            },
            {
                "path": "/cache/del",
                "endpoint": self.api_cache_del,
                "methods": ["DELETE"],
                "auth": "bear",
                "summary": "删除单条缓存",
                "response_model": OpResponse,
            },
            {
                "path": "/cache/clear",
                "endpoint": self.api_cache_clear,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "清空本插件全部缓存 region",
                "response_model": OpResponse,
            },
            {
                "path": "/cache/items",
                "endpoint": self.api_cache_items,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "枚举某 region 的原始缓存键值",
                "response_model": CacheItemsResponse,
            },
        ]

    def api_status(self) -> StatusResponse:
        """``/status``：启用状态 + 各实体计数 + 可检索比例 + 缓存 region 清单与条数。"""
        counts: dict = {}
        try:
            counts = self._store.counts()
        except Exception as err:  # pragma: no cover - 库未就绪时仍返回状态
            logger.error(f"{constants.SOURCE_NAME} 统计失败：{err}")
        # 缓存条数（面板「缓存分布」饼图）：缓存没起来就按全 0 报，不报错
        by_region: dict[str, int] = {name: 0 for name in constants.ALL_REGIONS}
        if self._cache is not None:
            try:
                by_region = self._cache.counts()
            except Exception as err:  # pragma: no cover - 后端差异
                logger.error(f"{constants.SOURCE_NAME} 缓存统计失败：{err}")
        data = StatusData(
            enabled=self._enabled,
            version=self.plugin_version,
            media_source=constants.MEDIA_SOURCE_ID,
            total=int(counts.get("total", 0)),
            searchable=int(counts.get("searchable", 0)),
            by_entity=dict(counts.get("by_entity", {})),
            regions=list(constants.ALL_REGIONS),
            by_region=dict(by_region),
        )
        return schemas.Response(success=True, message="", data=data)

    async def api_lookup(
        self,
        media_id: str = "",
        name: str = "",
        remote: int = 0,
        type: str = "",
    ) -> LookupResponse:
        """``/lookup``：``media_id`` 直查单条；``name`` 搜作品/演员返回候选列表。

        ``media_id`` 优先级最高。``name`` 分支默认只查本地（0 网络），``remote=1``
        才联网补全（走 ④ 站内搜索 → ⑤ 豆瓣）。
        """
        target = (media_id or "").strip()
        if target:
            if not is_known(target) and not target.isdigit():
                return schemas.Response(
                    success=False, message=f"不认识的 media_id：{target}", data=None
                )
            if not self._enabled or self._detail is None:
                return schemas.Response(success=False, message="插件未启用", data=None)
            # 人物不是「一部片」，塞不进 MediaInfo —— 明确指路，别让面板拿到一个
            # 莫名其妙的 data=null（那会看起来像"查不到"）
            if is_person(target) and not target.startswith(f"{constants.DOUBAN_PERSON}:"):
                return schemas.Response(
                    success=False,
                    message="人物档案请用 /person 查询（人物不是 MediaInfo）",
                    data=None,
                )
            try:
                info = await self._resolve_async(target)
            except Exception as err:  # pragma: no cover - 异常降级为未找到
                logger.error(f"{constants.SOURCE_NAME} lookup 失败 {target}：{err}")
                info = None
            return schemas.Response(success=True, message="", data=info)

        keyword = (name or "").strip()
        if not keyword:
            return schemas.Response(success=True, message="", data=None)
        if not self._enabled or self._detail is None:
            return schemas.Response(success=False, message="插件未启用", data=None)
        try:
            candidates = await self._detail.find_candidates(
                keyword,
                remote=bool(remote),
                include_person=True,
                include_novel=True,
                # 手动查询：联网时把本地结果并入，用户要看全同名版本
                merge_remote=bool(remote),
            )
        except Exception as err:  # pragma: no cover
            logger.error(f"{constants.SOURCE_NAME} lookup 搜索失败 {keyword}：{err}")
            candidates = []
        chosen = self._filter_by_type(candidates, type)
        return schemas.Response(
            success=True,
            message="",
            data=[candidate_to_media_info(item) for item in chosen],
        )

    async def api_person(self, media_id: str = "") -> PersonResponse:
        """``/person``：人物档案 + 作品清单（演员 / 导演 / 编剧）。

        接受 ``yanyuan:`` / ``daoyan:`` / ``bianju:`` 三种 media_id。人物**不是**
        ``MediaInfo``，所以单开一个端点；``/lookup?media_id=`` 遇到人物会明确指路到这里。
        """
        target = (media_id or "").strip()
        if not target:
            return schemas.Response(success=False, message="缺少 media_id", data=None)
        if not is_person(target):
            return schemas.Response(
                success=False, message=f"不是人物 media_id：{target}", data=None
            )
        if not self._enabled or self._detail is None:
            return schemas.Response(success=False, message="插件未启用", data=None)
        try:
            person = await self._detail.get_person(target)
        except Exception as err:  # pragma: no cover - 异常降级为未找到
            logger.error(f"{constants.SOURCE_NAME} 人物档案失败 {target}：{err}")
            person = None
        if not person:
            return schemas.Response(
                success=False,
                message="取不到人物档案：页面无效（软 404）或抓取失败",
                data=None,
            )
        return schemas.Response(success=True, message="", data=PersonData(**person))

    async def api_novel(self, media_id: str = "") -> NovelResponse:
        """``/novel``：原著档案 + 改编作品清单。

        传**剧** media_id（取详情里标注的原著）或**原著** media_id 均可；
        页面没标原著时 ``data=null``（面板据此决定要不要显示「改编档案」按钮）。
        原著不是 ``MediaInfo``，所以与 ``/person`` 一样单开端点。
        """
        target = (media_id or "").strip()
        if not target:
            return schemas.Response(success=False, message="缺少 media_id", data=None)
        if not is_known(target) or is_person(target):
            return schemas.Response(
                success=False, message=f"不是作品 / 原著 media_id：{target}", data=None
            )
        if not self._enabled or self._detail is None:
            return schemas.Response(success=False, message="插件未启用", data=None)
        try:
            novel = await self._detail.get_novel(target)
        except Exception as err:  # pragma: no cover - 异常降级为未找到
            logger.error(f"{constants.SOURCE_NAME} 原著档案失败 {target}：{err}")
            novel = None
        if not novel:
            # 区分两种「没拿到原著」：
            # * 传的是**剧** id（探测它有没有标原著）→ 没标，文案面向探测方，面板静默忽略；
            # * 传的是**原著** id（直接进入原著档案）→ 是原著页本身抓取失败，文案须准确，
            #   不能再叫「未标注原著」（那会让人以为这页不是原著），否则原路返回时误导。
            message = (
                "原著页加载失败（或页面已失效）"
                if is_novel(target)
                else "页面未标注原著"
            )
            return schemas.Response(
                success=False,
                message=message,
                data=None,
            )
        adaptations = []
        for work in novel.get("adaptations", []):
            adaptations.append(
                NovelWork(
                    media_id=str(work.get("media_id") or ""),
                    name=str(work.get("name") or ""),
                    kind=str(work.get("kind") or ""),
                    poster=image_url(work.get("media_id", "")),
                    date=str(work.get("date") or ""),
                    episodes=int(work.get("episodes") or 0),
                )
            )
        data = NovelData(
            media_id=str(novel.get("media_id") or ""),
            name=str(novel.get("name") or ""),
            kind="原著",
            author=str(novel.get("author") or ""),
            aka=str(novel.get("aka") or ""),
            words=str(novel.get("words") or ""),
            overview=str(novel.get("overview") or ""),
            poster=image_url(str(novel.get("media_id") or "")),
            detail_url=str(novel.get("detail_url") or ""),
            adaptations=adaptations,
            adaptation_count=len(adaptations),
            novel_id_of="" if is_novel(target) else target,
        )
        return schemas.Response(success=True, message="", data=data)

    # ── 跨插件消费契约（模块方法） ───────────────────────────────────
    # 短剧演员订阅按插件 ID 精确取本插件方法表（见它模块头的「为什么不用 run_module」），
    # 这里把服务层能力包成它期望的同步契约。字段名与它两侧的归一层对齐：
    # 候选 / 档案 → 它的 ``profile_fields_of`` 别名表，作品卡 → 它的 ``source_card``。

    @staticmethod
    def _person_gender_of(role: str) -> str:
        """站点身份文案（女演员 / 男演员）→ 性别（女 / 男）；认不出给空。"""
        return {"女演员": "女", "男演员": "男"}.get(str(role or "").strip(), "")

    def module_search_actors(self, name: str = "", **kwargs: Any) -> list[dict]:
        """演员候选（契约名 ``search_actors``）。

        返回 ``[{media_id, name, poster, url}]``；只收**百科人物**
        （yanyuan / daoyan / bianju）—— 豆瓣影人是另一套身份体系，不收。
        候选来自本地 ID 库 + 站内搜索（合并模式，与 ``/lookup?name=`` 同一条链路）。
        """
        keyword = str(name or "").strip()
        if not keyword or not self._enabled or self._detail is None:
            return []
        try:
            candidates = run_sync(
                self._detail.find_candidates(
                    keyword,
                    remote=True,
                    include_person=True,
                    include_novel=False,
                    merge_remote=True,
                )
            )
        except Exception as err:  # pragma: no cover - 检索失败按无候选处理
            logger.error(f"{constants.SOURCE_NAME} 演员候选检索失败 {keyword}：{err}")
            return []
        rows: list[dict] = []
        for item in candidates:
            media_id = str(item.get("media_id") or "")
            if media_id.partition(":")[0] not in constants.ENTITY_PERSON:
                continue
            rows.append(
                {
                    "media_id": media_id,
                    "name": str(item.get("name") or ""),
                    "poster": str(item.get("poster") or "") or image_url(media_id),
                    "url": detail_url(media_id),
                }
            )
        return rows

    def _person_target(self, actor_id: str = "", name: str = "") -> str:
        """演员标识解析：给 id 用 id；只给名字时按候选**精确同名**收敛。"""
        target = str(actor_id or "").strip()
        if target:
            return target
        keyword = str(name or "").strip()
        if not keyword:
            return ""
        for row in self.module_search_actors(name=keyword):
            if str(row.get("name") or "").strip() == keyword:
                return str(row.get("media_id") or "")
        return ""

    async def _module_actor_profile_async(
        self, actor_id: str, name: str
    ) -> Optional[dict]:
        target = self._person_target(actor_id, name)
        if (
            not target
            or not is_person(target)
            or target.startswith(f"{constants.DOUBAN_PERSON}:")
            or not self._enabled
            or self._detail is None
        ):
            return None
        try:
            person = await self._detail.get_person(target)
        except Exception as err:  # pragma: no cover - 档案失败按没有处理
            logger.error(f"{constants.SOURCE_NAME} 人物档案失败 {target}：{err}")
            return None
        if not person:
            return None
        return {
            "media_id": str(person.get("media_id") or target),
            "name": str(person.get("name") or ""),
            "gender": self._person_gender_of(str(person.get("role") or "")),
            "bio": str(person.get("intro") or ""),
            "poster": str(person.get("avatar") or ""),
            "url": str(person.get("detail_url") or ""),
            "works_count": int(person.get("work_count") or 0),
            # 刻意不给 job_title：消费方按「分类 + 性别」补「女演员 / 导演 / 编剧」，
            # 给了反而会把「女演员」顶成笼统的「演员」
        }

    def module_actor_profile(
        self,
        actor_id: str = "",
        name: str = "",
        enrich: bool = False,
        **kwargs: Any,
    ) -> Optional[dict]:
        """人物档案（契约名 ``actor_profile``）。

        返回键与消费方 ``profile_fields_of`` 的别名表对齐：
        ``media_id / name / gender / bio / poster / url / works_count``。
        ``enrich`` 收下但不使用 —— 作品清单由 ``actor_works`` 单独给，别在这一趟白补。
        """
        return run_sync(
            self._module_actor_profile_async(
                str(actor_id or "").strip(), str(name or "").strip()
            )
        )

    async def _module_actor_works_async(
        self, actor_id: str, name: str
    ) -> list[dict]:
        target = self._person_target(actor_id, name)
        if (
            not target
            or not is_person(target)
            or target.startswith(f"{constants.DOUBAN_PERSON}:")
            or not self._enabled
            or self._detail is None
        ):
            return []
        try:
            person = await self._detail.get_person(target)
        except Exception as err:  # pragma: no cover - 作品失败按没有处理
            logger.error(f"{constants.SOURCE_NAME} 人物作品失败 {target}：{err}")
            return []
        cards: list[dict] = []
        for work in person.get("works") or []:
            if not isinstance(work, dict):
                continue
            media_id = str(work.get("media_id") or "")
            kind = media_id.partition(":")[0]
            # 百科剧集身份（duanju/manju/hema/huolong）与豆瓣融合身份（douban:）都放行。
            # 豆瓣作品是豆瓣源原生身份：宿主订阅链 / 媒体库探针原生支持
            # （media_source=douban + 裸 subject id → douban tv_detail 识别），
            # 消费方（短剧演员订阅）按 ``douban:`` 前缀把来源分流到宿主豆瓣源。
            if kind not in constants.ENTITY_DRAMA and kind != constants.DOUBAN_WORK:
                continue
            tags = [str(tag).strip() for tag in (work.get("tags") or []) if str(tag).strip()]
            # 站点卡日期在 ``date``；豆瓣融合卡只有 ``year``（fusion 追加时 date 为空）
            date = str(work.get("date") or work.get("year") or "")
            rating = work.get("rating")
            cards.append(
                {
                    "media_id": media_id,
                    "title": str(work.get("name") or ""),
                    "episodes": int(work.get("episodes") or 0),
                    "badge": str(work.get("kind") or ""),
                    # 「真人 / AI」角标站点人物卡不带 —— 留空，消费方出占位
                    "kind": "",
                    "poster": str(work.get("poster") or "") or image_url(media_id),
                    "url": detail_url(media_id),
                    "rating": float(rating) if rating else 0,
                    "release_date": date,
                    "year": date[:4],
                    "genres": tags,
                    "genres_text": " / ".join(tags),
                    # 站点人物卡不印热度 / 播放 / 出品方 / 平台 —— 按缺数据给
                    "heat": 0,
                    "play_count": 0,
                    "studio": "",
                    "platform": "",
                }
            )
        return cards

    def module_actor_works(
        self, actor_id: str = "", name: str = "", **kwargs: Any
    ) -> list[dict]:
        """人物全部作品（契约名 ``actor_works``）。

        作品卡字段名与消费方 ``source_card`` 对齐（``badge``=角标 / ``episodes``=集数 /
        ``genres``+``genres_text``=题材 / ``release_date``=首播）；人物页作品卡自带的
        日期 / 集数 / 标签一并带上，热度 / 播放 / 出品方 / 平台站点没有，按 0 / 空给。
        百科剧集身份（``duanju:`` 等）与豆瓣融合身份（``douban:``）都放行：豆瓣作品
        由消费方按 ``douban:`` 前缀分流到宿主豆瓣源（识别/订阅/探针原生支持）。
        """
        return run_sync(
            self._module_actor_works_async(
                str(actor_id or "").strip(), str(name or "").strip()
            )
        )

    def module_list_people(
        self, kind: str = "yanyuan", page: int = 1, **kwargs: Any
    ) -> dict:
        """人物目录（契约名 ``list_people``）—— 站点 ``/<kind>/list.html`` 翻页目录。

        2026-10-22 实测：三类目录页（演员 / 导演 / 编剧）均支持 ``?page=N``，
        每页 24 条、页间零重叠，分页导航给出尾页号（演员 1396 / 导演 333 /
        编剧 211）。因此本方法对三类分类、任意页码都可供给：

        * ``people``：当前页人物（按页面顺序、去重），字段对齐消费方
          ``_source_people`` 的读取：``name / media_id / url / poster`` 必给；
          ``gender`` / ``job_title`` / ``works_count`` 留空 —— 消费方会按
          分类补「演员」标签，目录卡上没有的数字不硬凑。
        * ``has_more``：还有下一页（``page < 总页数``）。
        * 目录页抓取失败 → 空页 + ``has_more=False``（消费方按空页收敛，不报错）。
        """
        kind_key = str(kind or "").strip().lower() or "yanyuan"
        page_no = int(page or 1) or 1
        empty = {"kind": kind_key, "page": page_no, "has_more": False, "people": []}
        if (
            kind_key not in constants.PEOPLE_KINDS
            or page_no < 1
            or not self._enabled
            or self._detail is None
        ):
            return empty
        try:
            people, has_more = run_sync(self._people_page(kind_key, page_no))
        except Exception as err:  # pragma: no cover - 目录失败按空页处理
            logger.error(f"{constants.SOURCE_NAME} 人物目录（{kind_key} p{page_no}）失败：{err}")
            return empty
        return {
            "kind": kind_key,
            "page": page_no,
            "has_more": has_more,
            "people": people,
        }

    async def _people_page(self, kind: str, page: int) -> tuple[list[dict], bool]:
        """目录页 HTML → ``([人物行], has_more)``。

        2026-10-23 用户口径：目录页**不缓存**（页面目录一次一翻，缓存没有意义，
        还占一个 region），每次现抓。抓取失败返回空列表（调用方降级为空页）。
        """
        html = await pages.fetch_people_list_html(kind, page)
        if not html:
            return [], False
        cards, total_pages = pages.parse_people_page(html, kind)
        people = [
            {
                "name": name,
                "media_id": media_id,
                "url": detail_url(media_id),
                "poster": image_url(media_id) or "",
                "gender": "",
                "job_title": "",
                "works_count": 0,
            }
            for media_id, name in cards
            if name
        ]
        return people, page < total_pages

    # ── 榜单（跨插件契约 list_ranks / rank_medias，2026-10-23 恢复） ──

    def module_list_ranks(self, **kwargs: Any) -> dict:
        """榜单目录（契约名 ``list_ranks``）—— 站点排行榜清单与「推荐」页（``/tuijian.html``）。

        纯静态目录、零网络。2026-10-23 用户口径：榜单解析归**数据源**统一供给，
        消费方（短剧演员订阅等）经跨插件模块方法取，不再各自抓页面。
        """
        return {
            "ranks": [
                {"key": key, "name": name}
                for key, (name, _path) in constants.RANK_CATALOG.items()
            ],
            "message": "",
        }

    async def _rank_medias(
        self, key: str, page: int = 1, page_size: int = 30
    ) -> tuple[list[dict], str, bool]:
        """榜单 key + 页码 → ``([卡行], message, has_more)``。

        两种取法（2026-10-24 实测 + 用户口径「其他榜单也要按需加载」）：

        - **可翻页榜单**（推荐页，:data:`constants.PAGEABLE_RANKS`）：站点自己
          分页（``/tuijian.html?page=N``，每页 30 部、共 130 页），逐页抓、逐页
          缓存（键 ``tuijian:p2``）。
        - **不分页榜单**（``/paihang/*``）：站点一页给全部（99 部），这里把整份
          卡行按 ``page_size`` 切片返回，消费方拿到的仍是「每页 30 部 + has_more」，
          加载节奏与作品页一致；整份卡行缓存在 ``key`` 上，后续页零网络。

        缓存有效期与全插件统一（见 ``cache.unified_ttl``）。抓取失败返回空列表。
        """
        page_no = max(1, int(page or 1))
        size = max(1, int(page_size or 30))
        cache = self._cache.rank if self._cache is not None else None
        pageable = key in constants.PAGEABLE_RANKS

        if pageable:
            cache_key = key if page_no <= 1 else f"{key}:p{page_no}"
            cached = cache.get(cache_key) if cache is not None else None
            if isinstance(cached, dict) and cached.get("cards"):
                return cached["cards"], "", bool(cached.get("has_more"))
            html = await pages.fetch_rank_html(key, page_no)
            parser = pages.RANK_PARSERS.get(key, pages.DEFAULT_RANK_PARSER)
            cards = parser(html) if html else []
            has_more = bool(
                html
                and page_no < pages.rank_total_pages(html)
                and cards
            )
            message = "" if cards else f"榜单页暂时取不到（{key}）"
            if cards and cache is not None:
                cache.set(cache_key, {"cards": cards, "has_more": has_more})
            return cards, message, has_more

        # 不分页榜单：整份卡行缓存一次，按 page_size 切片模拟分页
        cached = cache.get(key) if cache is not None else None
        if isinstance(cached, list) and cached:
            all_cards = cached
        else:
            html = await pages.fetch_rank_html(key)
            parser = pages.RANK_PARSERS.get(key, pages.DEFAULT_RANK_PARSER)
            all_cards = parser(html) if html else []
            if all_cards and cache is not None:
                cache.set(key, all_cards)
        message = "" if all_cards else f"榜单页暂时取不到（{key}）"
        start = (page_no - 1) * size
        cards = all_cards[start:start + size]
        has_more = bool(all_cards) and (start + size) < len(all_cards)
        return cards, message, has_more

    def module_rank_medias(
        self, rank: str = "", page: int = 1, **kwargs: Any
    ) -> dict:
        """一个榜单的作品卡（契约名 ``rank_medias``）。

        返回::

            {"rank": "tuijian", "name": "推荐", "page": 1, "has_more": true,
             "medias": [<按实际页面解析的卡行>], "message": ""}

        2026-10-23 用户口径：卡形**不与 ``actor_works`` 对齐**，按实际页面取
        必要字段 —— ``media_id / title / badge / episodes / date /
        actors_text``；热度 / 评分 / 题材不要，``poster`` / ``url`` 由
        ``media_id`` 现推后附加（缓存里不存）。抓不到时 ``medias`` 空 +
        ``message`` 说明，不算异常。

        2026-10-24：``page`` 只对 :data:`constants.PAGEABLE_RANKS`（推荐页）有效，
        排行榜页忽略页码并返回 ``has_more=False``。
        """
        key = str(rank or "").strip().lower()
        page_no = max(1, int(page or 1))
        name = constants.RANK_CATALOG.get(key, ("", ""))[0]
        if not name:
            return {
                "rank": key,
                "name": "",
                "page": page_no,
                "has_more": False,
                "medias": [],
                "message": f"未知榜单：{key}",
            }
        if not self._enabled or self._detail is None:
            return {
                "rank": key,
                "name": name,
                "page": page_no,
                "has_more": False,
                "medias": [],
                "message": f"{constants.SOURCE_NAME} 未启用",
            }
        try:
            medias, message, has_more = run_sync(self._rank_medias(key, page_no))
        except Exception as err:  # pragma: no cover - 榜单失败按空榜处理
            logger.error(f"{constants.SOURCE_NAME} 榜单（{key} p{page_no}）失败：{err}")
            return {
                "rank": key,
                "name": name,
                "page": page_no,
                "has_more": False,
                "medias": [],
                "message": f"榜单获取失败：{err}",
            }
        # 缓存里只放必要字段；海报 / 链接由 media_id 现推（2026-10-23 用户口径：
        # poster 和 url 能用 media_id 反推，不占缓存）
        for card in medias:
            media_id = str(card.get("media_id") or "")
            card["poster"] = image_url(media_id)
            card["url"] = detail_url(media_id)
        return {
            "rank": key,
            "name": name,
            "page": page_no,
            "has_more": has_more,
            "medias": medias,
            "message": message,
        }

    # ── 宿主刮削出口（NFO / 图片，2026-10-23 新增）──────────────────────

    def metadata_nfo(
        self,
        meta: Any = None,
        mediainfo: Any = None,
        season: Optional[int] = None,
        episode: Optional[int] = None,
        **kwargs: Any,
    ) -> Optional[str]:
        """宿主刮削链的 NFO 出口：剧级 / 季级 / 单集三种根节点。

        契约（``contracts.py:506``）：``required=("meta","mediainfo","season","episode")``、
        ``FIRST_NON_EMPTY``、``plugin_short_circuit=True`` ⇒ 本方法返回非空即短路，
        内置生成器不再被问。``meta`` 只用于别源补分集信息，本站没有分集级数据，
        用不上（``del`` 明确表态，免得以后以为漏传了参数）。
        """
        del meta, kwargs
        if not self._enabled:
            return None
        return scrape.build_nfo(mediainfo, season=season, episode=episode)

    def metadata_img(
        self,
        mediainfo: Any = None,
        season: Optional[int] = None,
        episode: Optional[int] = None,
        **kwargs: Any,
    ) -> Optional[dict]:
        """宿主刮削链的图片出口：剧级 ``poster`` / 季级 ``season{NN}-poster``。

        季词条自己的海报就是该季海报（季号从词条名派生进 ``season`` 字段）；
        单集剧照站点没有 ⇒ ``episode`` 有值返回空 dict（真实无素材）。
        非本来源返回 ``None`` 让位——空 dict 也会短路，不能拿来让位。
        """
        del kwargs
        if not self._enabled:
            return None
        return scrape.build_images(mediainfo, season=season, episode=episode)

    def api_search(self, name: str = "", type: str = "") -> SearchResponse:
        """``/search``：**纯本地**检索（0 网络），给面板自动补全用。

        与 ``/lookup?name=`` 的关系：本端点是它的本地子集，永不联网。
        """
        keyword = (name or "").strip()
        if not keyword or not self._enabled or self._detail is None:
            return schemas.Response(success=True, message="", data=[])
        try:
            candidates = run_sync(
                self._detail.find_candidates(
                    keyword,
                    remote=False,
                    include_person=True,
                    include_novel=True,
                )
            )
        except Exception as err:  # pragma: no cover
            logger.error(f"{constants.SOURCE_NAME} 本地检索失败 {keyword}：{err}")
            candidates = []
        chosen = self._filter_by_type(candidates, type)
        return schemas.Response(
            success=True, message="", data=[candidate_to_media_info(item) for item in chosen]
        )

    @staticmethod
    def _filter_by_type(candidates: list[dict], type: str) -> list[dict]:
        """按 ``type=work|person`` 过滤候选；空值不过滤。"""
        kind = (type or "").strip().lower()
        if kind not in ("work", "person"):
            return candidates
        want_person = kind == "person"
        return [
            item
            for item in candidates
            if (is_person(item["media_id"]) if want_person else is_drama(item["media_id"]))
        ]

    async def api_cache_clear(self) -> OpResponse:
        """``/cache/clear``：清空全部 region（id 库是持久数据，保留）。"""
        if self._cache is None:
            return schemas.Response(
                success=False, message="缓存未初始化", data=OpResult(ok=False)
            )
        cleared = self._cache.clear_all()
        return schemas.Response(
            success=True,
            message="",
            data=OpResult(ok=True, detail=",".join(cleared), affected=len(cleared)),
        )

    # ── 管理面板：ID 库 ──────────────────────────────────────────────
    def api_baike_list(
        self,
        q: str = "",
        entity: str = "",
        offset: int = 0,
        limit: int = 50,
    ) -> BaikePageResponse:
        """``/baike/list``：ID 库分页，返回**原始 4 列**（不翻译、不清洗）。"""
        size = max(1, min(int(limit or 50), 200))
        start = max(0, int(offset or 0))
        try:
            total, rows = self._store.page(
                q=(q or "").strip(), entity=(entity or "").strip(), offset=start, limit=size
            )
        except Exception as err:  # pragma: no cover - 库未就绪时返回空页
            logger.error(f"{constants.SOURCE_NAME} 读取 ID 库失败：{err}")
            total, rows = 0, []
        return schemas.Response(
            success=True,
            message="",
            data=BaikePageData(total=total, offset=start, limit=size, items=rows),
        )

    def api_baike_del(self, media_id: str = "") -> OpResponse:
        """``/baike/del``：删单条 ID，并联动删它的详情/人物缓存。"""
        target = (media_id or "").strip()
        if not target:
            return schemas.Response(
                success=False, message="缺少 media_id", data=OpResult(ok=False)
            )
        try:
            removed = self._store.delete(media_id=target)
        except Exception as err:  # pragma: no cover
            logger.error(f"{constants.SOURCE_NAME} 删 ID 失败 {target}：{err}")
            return schemas.Response(
                success=False, message=f"删除失败：{err}", data=OpResult(ok=False)
            )
        if removed and self._cache is not None:
            # 联动清缓存，避免「库里删了但详情还在」的不一致
            self._cache.delete(constants.REGION_DETAIL, target)
            self._cache.delete(constants.REGION_PERSON, target)
        return schemas.Response(
            success=True,
            message="" if removed else "该 media_id 不存在",
            data=OpResult(ok=bool(removed), affected=1 if removed else 0),
        )

    def api_baike_clear(self) -> OpResponse:
        """``/baike/clear``：清空 ID 库（危险）。"""
        try:
            affected = self._store.clear()
        except Exception as err:  # pragma: no cover
            logger.error(f"{constants.SOURCE_NAME} 清空 ID 库失败：{err}")
            return schemas.Response(
                success=False, message=f"清空失败：{err}", data=OpResult(ok=False)
            )
        return schemas.Response(
            success=True, message="", data=OpResult(ok=True, affected=int(affected or 0))
        )

    def api_cache_del(self, region: str = "", key: str = "") -> OpResponse:
        """``/cache/del``：删单条缓存（``region`` + ``key``）。"""
        if not region or not key:
            return schemas.Response(
                success=False, message="缺少 region 或 key", data=OpResult(ok=False)
            )
        if self._cache is None:
            return schemas.Response(
                success=False, message="缓存未初始化", data=OpResult(ok=False)
            )
        if region not in constants.ALL_REGIONS:
            return schemas.Response(
                success=False, message=f"未知 region：{region}", data=OpResult(ok=False)
            )
        ok = self._cache.delete(region, key)
        return schemas.Response(
            success=True,
            message="" if ok else "删除失败或键不存在",
            data=OpResult(ok=bool(ok), affected=1 if ok else 0),
        )

    def api_cache_items(
        self, region: str = "", limit: int = 100, search: str = ""
    ) -> CacheItemsResponse:
        """``/cache/items``：枚举某 region 的键值（面板「看原始数据」）。

        2026-10-23 用户口径：
        - ``search``：按**缓存键或值内容**模糊筛（不区分大小写）—— 在榜单区搜
          剧名能定位到它落在哪本榜里（整份卡行数组一起命中）；
        - **榜单仍按数组存**（一条缓存 = 一本榜的全部卡行），这里只补一个可读的
          ``label``（「推荐（30 部）」）供面板显示，不再摊开成一条一行。
        """
        if self._cache is None or not region:
            return schemas.Response(
                success=True,
                message="",
                data=CacheItemsData(region=region, total=0, items=[]),
            )
        cap = max(1, min(int(limit or 100), 500))
        raw = self._cache.items(region, limit=500)
        rows: list[dict] = []
        for item in raw:
            key = str(item.get("key") or "")
            value = item.get("value")
            label = ""
            # 榜单区：值是整本榜的卡行（可翻页的榜按页存 {"cards": […], "has_more": …}）
            cards = value.get("cards") if isinstance(value, dict) else None
            if isinstance(value, list) or isinstance(cards, list):
                count = len(cards if isinstance(cards, list) else value)
                rank_key, _, page_part = key.partition(":p")
                rank_name = constants.RANK_CATALOG.get(rank_key.lower(), ("", ""))[0]
                page_no = int(page_part) if page_part.isdigit() else 0
                if rank_name:
                    where = f" 第{page_no}页" if page_no else ""
                    label = f"{rank_name}{where}（{count} 部）"
                else:
                    label = f"数组 · {count} 项"
            rows.append({"key": key, "value": value, "parent": "", "label": label})
        query = str(search or "").strip().lower()
        if query:
            def _hit(row: dict) -> bool:
                if query in str(row.get("key") or "").lower():
                    return True
                try:
                    text = json.dumps(row.get("value"), ensure_ascii=False)
                except Exception:  # noqa: BLE001 - 不可序列化就退回 str
                    text = str(row.get("value"))
                return query in text.lower()

            rows = [row for row in rows if _hit(row)]
        return schemas.Response(
            success=True,
            message="",
            data=CacheItemsData(
                region=region,
                total=len(rows),
                items=[CacheItem(**row) for row in rows[:cap]],
            ),
        )

    # ── 配置页与详情页 ───────────────────────────────────────────────
    @staticmethod
    def get_render_mode() -> tuple[str, str]:
        """声明 Vue 联邦构建产物目录。

        **不实现 `get_sidebar_nav()`**（用户明确要求不接入侧栏）：宿主的
        ``/api/v1/plugin/remotes`` 只按本方法筛选，不依赖侧栏声明，所以面板仍可经
        ``#/plugin-app/<插件ID>/main`` 直接访问。
        """
        # 动态取 dist 下序号最大的 a<N> 目录：目录名变 = URL 变 = 浏览器缓存自动失效
        # （测试阶段版本号冻结，靠它代替 ?v= 的破缓存作用）
        return "vue", constants.frontend_dist()

    # ── 配置读写（Vue 配置页 `./Config` 用；同时注册成 /config） ─────────
    @staticmethod
    def _default_config() -> dict:
        """配置默认值：键必须与 `get_form()` 的字段一一对应。"""
        return {
            "enabled": False,
        }

    def _live_config(self) -> dict:
        """当前生效的配置（默认值兜底 + 布尔归一）。"""
        raw = dict(self._config or {})
        merged = self._default_config()
        merged.update({key: raw[key] for key in list(merged) if key in raw})
        merged["enabled"] = bool(merged.get("enabled"))
        return merged

    def api_get_config(self) -> ConfigResponse:
        """``GET /config``：给 Vue 配置页回读当前配置。"""
        return schemas.Response(
            success=True, message="", data=ConfigData(**self._live_config())
        )

    def api_update_config(self, payload: Optional[dict] = None) -> ConfigResponse:
        """``PUT /config``：保存配置（**整体替换**语义，缺失键取默认值）。

        ``update_config`` 由基类负责持久化与回调；这里再显式调一次 ``init_plugin``
        是为了保证「本次进程内立即生效」，不依赖宿主的回调时序。
        """
        incoming = payload if isinstance(payload, dict) else {}
        base = self._default_config()
        merged = {key: incoming.get(key, base[key]) for key in base}
        try:
            self.update_config(merged)
        except Exception as err:  # pragma: no cover - 持久化失败也要让内存态生效
            logger.error(f"{constants.SOURCE_NAME} 保存配置失败：{err}")
        self.init_plugin(merged)
        return schemas.Response(
            success=True, message="", data=ConfigData(**self._live_config())
        )

    def get_form(self) -> tuple[list[dict], dict]:
        """配置页：只有一个启用开关（探索页榜单功能已于 2026-10-23 移除）。"""
        return [
            {
                "component": "VForm",
                "content": [
                    {
                        "component": "VSwitch",
                        "props": {"model": "enabled", "label": "启用插件"},
                    },
                ],
            }
        ], {
            "enabled": False,
        }

    def get_page(self) -> list[dict]:
        """详情页：一行文字概览（图表/面板留给 P2.5 的 Vue 远程组件）。"""
        try:
            counts = self._store.counts()
        except Exception:  # pragma: no cover
            counts = {}
        by_entity = counts.get("by_entity", {}) or {}
        detail = "｜".join(f"{key} {value}" for key, value in by_entity.items() if value)
        return [
            {
                "component": "VAlert",
                "props": {
                    "type": "info",
                    "variant": "tonal",
                    "text": (
                        f"来源标识 {constants.MEDIA_SOURCE_ID}｜"
                        f"ID 库 {counts.get('total', 0)} 条（可检索 {counts.get('searchable', 0)}）"
                        + (f"｜{detail}" if detail else "")
                    ),
                },
            }
        ]
