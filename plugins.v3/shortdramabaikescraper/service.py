"""编排层：详情取数（缓存优先）+ 顺带登记 + 按名识别（六层管线的 ③④⑤⑥）。

取详情的顺序（计划 §0 链路）：

1. ``media_id`` 合法 → 查 ``djbaike.detail`` 缓存，命中即返回（0 网络）；
2. 负缓存命中 → 直接 ``None``（软 404 / 无结果 1 小时内不再探测）；
3. 百科前缀 → 拼详情页 URL 抓取 → 解析 → 写缓存 → 回写 ``baike``（名字 + 顺带登记）；
4. 豆瓣前缀（``douban:{sid}``）→ 宿主豆瓣 ``tv_detail`` → 写缓存 → 自映射入库。

按名识别的顺序（§5.1 六层，代价从低到高）：

* ③ ``baike.name`` 精确匹配（最干净候选优先，命中即停，0 网络）；
* ④ 站内 ``/so.html``（一次网络，**全量登记**本页候选）；
* ⑤ 百科 0 结果才转豆瓣 ``tv_search``（《情靡》《绾骨灯》都是百科没收录但有豆瓣条目）。

两个入口对「多条」的处置不同（§5.1）：``search_medias`` 原样返回全部候选，
``recognize_media`` 按确定性规则收敛成唯一一条。
"""

from __future__ import annotations

import asyncio
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Iterable, Optional

from app.sdk.logging import logger

from . import classify, constants, douban, orgadapt, orgsite, search, tmdb
from .fetcher import Fetcher
from .harvest import harvest_page
from .media_id import (
    detail_url,
    entity_of,
    image_url,
    is_drama,
    is_known,
    is_novel,
    is_person,
    native_id_of,
)
from .parser import detail_to_media_info, parse_detail, parse_person
from .store import tmdb_composite, tmdb_number
from .title_clean import _has_cjk, clean_candidates, has_season_suffix, season_suffixes

# 作品类型偏好（§5.1 选优第 4 步）：短剧优先，纯豆瓣条目排最后
# ``drama`` 是 .org 的作品前缀，语义与 ``duanju`` 同为「短剧」，排同一档
_ENTITY_PREFERENCE = {
    "duanju": 0,
    "drama": 0,
    "manju": 1,
    "hema": 2,
    "huolong": 3,
    "douban": 4,
}

#: 「排除」开关（配置键仍是 ``exclude_manju``，由 ``init_plugin`` 设置）。
#:
#: 站点口径不同（2026-11-03 用户口径）：老站排**漫剧**、新站排 **AI 剧** ——
#: 两个站的分类标注不是一回事，同一个开关按身份前缀各自生效（见
#: :func:`is_excluded_item`），所以配置页只有一个开关就够。
#:
#: 用模块级开关而不是逐层传参：判定发生在 ``_site_search`` 这种编排层深处，
#: 而配置值只有一个（宿主同一插件类只实例化一份），不存在多实例互相污染。
#: ⚠️ 这个开关管的是**入库**：被判为排除的搜索结果**不登记进 ID 库** ——
#: 否则它会以「本地命中」的身份在后续检索里复活（本地行没有角标 / AI 标，
#: 无法再判类型）。
_exclude_manju: bool = True


def set_exclude_manju(value: bool) -> None:
    """设置「排除漫剧（老站）/ AI 剧（新站）」开关。"""
    global _exclude_manju
    _exclude_manju = bool(value)


def exclude_manju() -> bool:
    """当前是否开启了「排除」开关。"""
    return _exclude_manju


def is_excluded_item(item: dict) -> bool:
    """单条候选 / 卡行是否属于「排除」目标（**只看身份与标注，不看开关**）。

    判据按 ``media_id`` 前缀分派，与「主站」配置无关 —— 同一份候选里可能
    同时躺着 ``drama:``（新站）与 ``duanju:``（老站）条目，各按各的站的口径算：

    * ``drama:`` / ``actor:``（.org）→ 卡片标题行的 ``AI短剧`` 标，即 ``is_ai``
    * 其余（.net 的 ``duanju:`` / ``manju:`` / ``hema:`` / ``huolong:``）
      → 卡片右下角角标，即 ``kind == "漫剧"``

    ``kind`` 对 .org 条目也顺带认一次：新站没有「漫剧」角标，个别卡片会在题材里
    标「漫剧」，有就一起排掉，没有不影响。
    """
    media_id = str(item.get("media_id") or "").strip()
    if not media_id:
        return False
    kind = str(item.get("kind") or "").strip()
    if entity_of(media_id) in constants.ORG_ENTITIES:
        return bool(item.get("is_ai")) or kind == "漫剧"
    return kind == "漫剧"

# 名字比对前先去掉标点/空白，避免《情靡》与「情靡」这类差异误判
_NAME_NOISE = re.compile(r"[\s·:：,，.。!！?？、\-—_（）()\[\]【】《》\"'’“”]+")


def _name_key(text: object) -> str:
    """标题归一成比对键（只用于**判断是否同一部**，不改存储、不改查询）。"""
    return _NAME_NOISE.sub("", str(text or "")).casefold()


def _name_alike(wanted: str, candidate: str) -> bool:
    """两个名字是否像同一部：完全相同，或一方包含另一方且长度占比 ≥ 0.6。

    用于过滤豆瓣 ``tv_search`` 的模糊结果——它连完全不相干的剧都会返回。
    """
    if not wanted or not candidate:
        return False
    if wanted == candidate:
        return True
    short, long = (wanted, candidate) if len(wanted) <= len(candidate) else (candidate, wanted)
    return short in long and len(short) / len(long) >= 0.6


def _name_related(wanted: str, candidate: str) -> bool:
    """比 :func:`_name_alike` 宽一档：站内名带季号/版本后缀也算同一部。

    只用于**站内检索结果**（站点自己按关键词命中，本来就以同名为主）；豆瓣那边仍用严格版，
    避免把不相干的条目认成同一部。
    """
    if _name_alike(wanted, candidate):
        return True
    return bool(wanted and candidate and wanted in candidate)


# ── 同步入口的事件循环复用 ──────────────────────────────────────────────
# 宿主缓存后端把 Redis 异步客户端按**事件循环**缓存
# （``app.adapters.cache.redis`` 里的 ``WeakKeyDictionary[loop -> client]``）。
# 同步识别（宿主刮削逐集调 ``recognize_media``）如果每次 ``asyncio.run`` 新建
# 一个 loop，就等于每次新建一个连接池：日志里每集一条
# ``Successfully connected to Redis (async)``，旧连接随 loop 丢弃还会漏 fd
# （实测把容器 ``Max open files=1024`` 撑爆过一次）。
# 因此这里固定**一个后台 loop** 承载所有同步调用，连接只建一次。
_LOOP_LOCK = threading.Lock()
_LOOP: Optional[asyncio.AbstractEventLoop] = None
_LOOP_THREAD: Optional[threading.Thread] = None

#: 人物外部 id 绑定判定的版本（缓存里的 ``bind_ver``）。**判定逻辑一改就 +1**：
#: 缓存里只存「人物档案按哪一版判定试过」，不存 id 本身（id 只存 ID 库、按名查）——
#: 旧缓存里 ``douban_id=""`` 那种「旧判定下绑不上」的结论已不作为判据；
#: 升版本号让每份缓存**多补跑一次**绑定，之后照旧按 TTL 生效。
#: v2（2026-11-04）：豆瓣影人加「候选里唯一精确同名」兜底。
BIND_VERSION = 2


def _ensure_loop() -> asyncio.AbstractEventLoop:
    """取（必要时创建）那个唯一的后台事件循环。"""
    global _LOOP, _LOOP_THREAD
    with _LOOP_LOCK:
        if _LOOP is None or _LOOP.is_closed() or _LOOP_THREAD is None or not _LOOP_THREAD.is_alive():
            loop = asyncio.new_event_loop()
            thread = threading.Thread(
                target=loop.run_forever,
                name="djbaike-sync-loop",
                daemon=True,
            )
            thread.start()
            _LOOP, _LOOP_THREAD = loop, thread
        return _LOOP


def run_sync(coro):
    """把协程跑成同步结果，**复用同一个后台事件循环**。

    不要在事件循环里直接 ``asyncio.run``：宿主缓存/网络客户端的连接池都绑 loop。
    """
    loop = _ensure_loop()
    if threading.current_thread() is _LOOP_THREAD:
        # 极少数情况：调用方本身就在这个 loop 线程里，不能自己等自己
        with ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, coro).result()
    return asyncio.run_coroutine_threadsafe(coro, loop).result()


def shutdown_sync_loop() -> None:
    """停止并关闭后台事件循环（插件停止时调用，可重复）。"""
    global _LOOP, _LOOP_THREAD
    with _LOOP_LOCK:
        loop, thread = _LOOP, _LOOP_THREAD
        _LOOP, _LOOP_THREAD = None, None
    if loop is None:
        return
    try:
        loop.call_soon_threadsafe(loop.stop)
    except Exception:  # pragma: no cover - loop 已关闭
        pass
    if thread is not None:
        thread.join(timeout=2)
    try:
        if not loop.is_closed():
            loop.close()
    except Exception:  # pragma: no cover - 关闭异常不影响停用
        pass


def candidate_to_media_info(candidate: dict):
    """候选 dict → 轻量 ``MediaInfo``（不抓详情，海报按前缀反推 / 用豆瓣封面）。"""
    from app.schemas import MediaInfo
    from app.schemas.types import MediaSource, MediaType

    media_id = candidate.get("media_id") or ""
    info = MediaInfo(
        type=MediaType.TV.value,
        title=candidate.get("name") or native_id_of(media_id) or media_id,
        media_source=MediaSource(constants.MEDIA_SOURCE_ID),
        media_id=media_id,
        poster_path=candidate.get("poster") or None,
    )
    # 候选卡片也带上分类事实：宿主在「搜索→选择→分类」链路上用的是同一份 MediaInfo
    return classify.attach(info)


class DetailService:
    """详情取数、候选检索与登记的编排。"""

    def __init__(self, cache, store, fetcher: Optional[Fetcher] = None) -> None:
        self._cache = cache
        self._store = store
        self._fetcher = fetcher or Fetcher()

    # ── ⓪ 「排除」开关（老站漫剧 / 新站 AI 剧） ──────────────────────
    def _is_excluded(self, item: dict) -> bool:
        """单条候选是否要剔；本地行没有标注时用**详情缓存**（零网络）补判一次。

        为什么要补：ID 库里只有 ``media_id + name``，没有 ``is_ai`` 列（表结构不动）。
        新站条目从本地命中回来时 ``is_ai`` 恒为空，只看它等于「排除开关对新站失效」。
        详情缓存里有 ``is_ai``（详情解析产物），命中就直接按它判；没缓存就算了 ——
        拿不到标注时**不误杀**，宁可放过。
        """
        if is_excluded_item(item):
            return True
        media_id = str(item.get("media_id") or "").strip()
        if not media_id or entity_of(media_id) not in constants.ORG_ENTITIES:
            return False
        if self._cache is None:
            return False
        cached = self._cache.get_detail(media_id) or {}
        return bool(cached.get("is_ai"))

    def drop_excluded(self, items: list[dict]) -> list[dict]:
        """按配置剔除（开关关闭时原样返回），并记一条日志。"""
        if not _exclude_manju or not items:
            return items
        kept = [item for item in items if not self._is_excluded(item)]
        dropped = len(items) - len(kept)
        if dropped:
            logger.info(f"{constants.SOURCE_NAME} 已按排除开关剔除 {dropped} 条结果")
        return kept

    # ── ① 详情（缓存优先） ───────────────────────────────────────────
    @staticmethod
    def _pick_drama_row(rows: Optional[list]) -> Optional[str]:
        """从同名多行里挑百科实体（``_ENTITY_PREFERENCE`` 最小 rank）。

        同名可能有**多行**（``duanju:…`` 与豆瓣兜底留下的 ``douban:…`` 同名），
        ``by_name`` 按 media_id 字典序返回，``douban:`` 会排在前面。选中豆瓣条目
        会连带**丢掉分类事实**（``douban:`` 不产出 ``extensions.djbaike.*``），
        归类直接掉到「未分类」。
        """
        best: Optional[str] = None
        best_rank = 99
        for row in rows or []:
            media_id = str(row.get("media_id") or "")
            if not media_id or not is_drama(media_id):
                continue
            rank = _ENTITY_PREFERENCE.get(entity_of(media_id), 9)
            if rank < best_rank:
                best, best_rank = media_id, rank
        return best

    def local_match(self, name: str) -> Optional[str]:
        """只看本地 ``baike`` 的精确同名（0 网络），返回作品 ``media_id``。

        用途：宿主批量整理**不带来源**广播时，只要本地已有同名作品就能认领；
        没有本地命中再交给 ``_looks_like_short_drama`` 决定要不要出网。
        """
        for key in clean_candidates(name):
            best = self._pick_drama_row(self._store.by_name(name=key))
            if best:
                return best
        return None

    def local_match_seasonal(self, name: str, season: Optional[int] = None) -> Optional[str]:
        """季号感知的本地匹配（0 网络）。

        站点把第 N 季拆成**独立词条**（``隐身侍卫`` / ``隐身侍卫第二季``），基名
        精确匹配永远只中第一季。季号 >= 2 时先按 ``{基名}第N季``（中文/阿拉伯
        两种写法）**精确**查库，命中即用 —— 那条就是该季的专属词条。

        ⚠️ 必须精确查、不能把后缀名丢给 ``local_match``：``clean_candidates`` 的
        ``_drop_season`` 步骤正好把季号后缀洗掉，走普通匹配反而命中基名（第一季）
        那条。没有独立季词条才退回基名匹配 —— 站点把多季并入同一条目时
        （``seasons`` 带多个季），基名才是对的。
        """
        if season and season >= 2:
            for key in clean_candidates(name):
                for suffix in season_suffixes(season):
                    best = self._pick_drama_row(self._store.by_name(name=f"{key}{suffix}"))
                    if best:
                        return best
        return self.local_match(name)

    async def get_detail(self, media_id: str) -> Optional[dict]:
        """按 media_id 取详情（缓存优先）；不可解析的 id 返回 ``None``。"""
        target = (media_id or "").strip()
        if not target or not is_known(target):
            return None
        entity = entity_of(target)
        # 百科八类走页面解析；douban:{sid} 走豆瓣通道；doubanp 属 P3
        if entity not in constants.ENTITY_ALL and entity != constants.DOUBAN_WORK:
            return None

        cached = self._cache.get_detail(target) if self._cache else None
        if cached:
            # 命中缓存也补一次登记：缓存是内存态（reload / 重启就没了），而 ID 库是持久的。
            # 不补的话会出现「面板查过、详情也看了，可 ID 库里没有」的观感（用户 22:48 提过）。
            # 纯 DB upsert、零网络，幂等。
            self._register(target, cached.get("name", ""))
            # 外部 id **不在缓存里**（2026-11-04 用户口径「站点 id 查缓存，外部 id 按名
            # 回 ID 库查」）—— 每次返回前从库里现取，缺的顺手补，改了库立刻生效。
            return await self._with_external(cached, target)

        if self._cache and self._cache.is_negative(target):
            return None

        if entity == constants.DOUBAN_WORK:
            detail = await self._load_douban(target)
        else:
            detail = await self._load_baike(target)
        if not detail:
            return None
        return await self._with_external(detail, target)

    async def _with_external(self, detail: dict, media_id: str) -> dict:
        """把 ID 库里的外部 id 挂到**返回副本**上；缓存原件一个 id 都不留。

        站点 id（``media_id``）负责查详情缓存；豆瓣 / TMDB 属作品级资产，按名存
        ``baike_ext``（2026-11-04 用户口径）。库里缺哪一半就**顺手补哪一半**
        （同日「详情页顺手补」）——判据、风控、搜索缓存全交给
        :meth:`fill_external_ids`，这里不另起一套；补到的只写库，缓存里仍不留 id。
        """
        # 旧格式缓存（外部 id 曾随详情一起存）就地清掉：库是唯一真源，
        # 留着副本只会出现「改了库、详情还是旧 id」
        detail.pop("douban_id", None)
        detail.pop("tmdb_id", None)
        payload = dict(detail)
        try:
            row = self._store.get(media_id=media_id) or {}
        except Exception as err:  # pragma: no cover - 读库失败按无绑定处理
            logger.warning(f"{constants.SOURCE_NAME} 读外部 id 失败 {media_id}：{err}")
            row = {}
        douban_ref = str(row.get("douban") or "")
        tmdb_ref = str(row.get("tmdb") or "")
        name = str(detail.get("name") or "").strip()
        if name and not (douban_ref and tmdb_ref):
            try:
                filled = await self.fill_external_ids(
                    media_id, name, douban_now=douban_ref, tmdb_now=tmdb_ref
                )
            except Exception as err:  # pragma: no cover - 补 id 失败不影响详情
                logger.warning(f"{constants.SOURCE_NAME} 详情顺手补外部 id 失败 {media_id}：{err}")
                filled = {}
            douban_ref = douban_ref or str(filled.get("douban") or "")
            tmdb_ref = tmdb_ref or str(filled.get("tmdb") or "")
        payload["douban_id"] = (
            douban_ref.partition(":")[2]
            if douban_ref.startswith(f"{constants.DOUBAN_WORK}:")
            else ""
        )
        payload["tmdb_id"] = tmdb_number(tmdb_ref)
        return payload

    # ── ①'' 原著档案（改编档案） ────────────────────────────────────────
    async def get_novel(self, media_id: str) -> Optional[dict]:
        """原著档案：传入**剧** id 或**原著** id 均可。

        * 剧（duanju/manju/...）→ 取详情里的 ``novel`` 链接再抓原著页；
        * 原著（xiaoshuo）→ 直接抓原著页。

        返回 parser 的原著 detail dict（含 ``author / aka / words / adaptations``
        —— ``adaptations`` 是「改编拍摄的系列短剧」区块解析出来的改编清单）。
        页面没标原著（或原著页抓不到）返回 ``None``。改编作品会登记进 ID 库，
        这样从原著档案点进任一部改编短剧都走得了详情。
        """
        target = (media_id or "").strip()
        if not target or not is_known(target):
            return None
        if is_novel(target):
            novel_id = target
        else:
            detail = await self.get_detail(target)
            novel_id = str(((detail or {}).get("novel") or {}).get("media_id") or "")
            if not novel_id:
                return None
        novel = await self._load_baike(novel_id)
        if not novel:
            return None
        self._register(novel_id, novel.get("name", ""))
        # 改编作品登记入库：原著档案点改编短剧 → /lookup 直查
        for work in novel.get("adaptations", []):
            if work.get("media_id") and work.get("name"):
                self._register(work["media_id"], work["name"])
        return novel

    async def recognize(self, media_id: str):
        """取详情并转成宿主 ``MediaInfo``。"""
        detail = await self.get_detail(media_id)
        if not detail:
            return None
        return detail_to_media_info(detail)

    def recognize_sync(self, media_id: str):
        """同步版本（宿主同步识别链路用）。"""
        return run_sync(self.recognize(media_id))

    # ── ①' 人物档案（演员 / 导演 / 编剧） ─────────────────────────────
    async def get_person(self, media_id: str) -> Optional[dict]:
        """人物档案：缓存优先 → 抓页 → 解析 → 写缓存 + 顺带登记。

        与作品详情分开缓存（``djbaike.person``，TTL 24h）：人物页体积大（演员页
        100KB 上下）、作品清单会随站点更新，但不像剧集详情那样频繁变化。

        **人物不是 ``MediaInfo``**（宿主那个结构描述的是"一部片"），所以它只走
        ``/person`` 端点给面板看，不参与 ``recognize_media`` 的返回。
        """
        target = (media_id or "").strip()
        if not target or not is_person(target):
            return None
        # 豆瓣影人 id（``doubanp:{pid}``）是外部 id 库里的一等身份：点开就该出档案，
        # 不需要站点页（2026-11-04 用户口径「外部 id 记录的这些 id，豆瓣人物和作品都能用」）
        if entity_of(target) == constants.DOUBAN_PERSON:
            return await self._douban_person(target)
        # 负缓存用**独立前缀**：作品链路（``_load_baike``）曾把人标记成"取不到详情"，
        # 若共用 key，人物档案会被那条无关的负缓存永久挡住（实测踩过）。
        negative_key = f"person:{target}"
        if self._cache:
            cached = self._cache.get_person(target)
            if cached:
                # 缓存里**没有外部 id**（2026-11-04 用户口径）：只有「按当前判定试过
                # 没有」的版本号，绑定结论一律回 ID 库取。``works`` 拷一份，避免
                # 融合时 append 到缓存原件上。
                person = {**cached, "works": list(cached.get("works") or [])}
                person = await self._refresh_person_bindings(person)
                # 缓存命中也补一次登记：缓存是内存态（reload / 重启就没了），
                # ID 库是持久的 —— 不补会出现「详情看过、库里没有」的观感。
                self._register(target, person.get("name", ""))
                self._register_person_works(person)
                self._register_person_people(person)
                return self._with_person_external(person, target)
            if self._cache.is_negative(negative_key):
                return None

        url = detail_url(target)
        if not url:
            return None
        html = await self._fetcher.get_html(url)
        if not html:
            if self._cache:
                self._cache.mark_negative(negative_key)
            return None

        # 人物页同样按前缀路由：``actor:`` 走 .org 解析器（Alpine + JSON-LD）
        if entity_of(target) in constants.ORG_ENTITIES:
            person = orgadapt.person_detail(
                target, orgsite.parse_actor(html, url=url)
            )
            if not person.get("name"):
                person = None
        else:
            person = parse_person(target, html)
        if not person:
            if self._cache:
                self._cache.mark_negative(negative_key)
            return None

        # 豆瓣影人作品合并（展示层融合，存储仍是两条记录）：绑定失败不影响档案本体
        try:
            person = await self._fuse_douban_person(person)
        except Exception as err:  # pragma: no cover - 合并失败不影响档案
            logger.warning(f"{constants.SOURCE_NAME} 豆瓣人物作品合并失败 {target}：{err}")

        # TMDB 影人只绑 id、不合并作品（TMDB 侧长短剧混排，合进来会污染作品清单）
        try:
            person = await self._fuse_tmdb_person(person)
        except Exception as err:  # pragma: no cover - 绑定失败不影响档案
            logger.warning(f"{constants.SOURCE_NAME} TMDB 人物绑定失败 {target}：{err}")
        # 记下判定版本：之后命中缓存时不必再补跑（除非 BIND_VERSION 又升了）。
        # 这只是状态位，外部 id 本体不进缓存。
        person["bind_ver"] = BIND_VERSION

        if self._cache:
            self._cache.set_person(target, person)
        self._register(target, person.get("name", ""))
        # 人物页的作品卡自带日期/集数/演员/标签 → 顺带把这一页的剧都登记进 ID 库
        self._harvest(html)
        # 作品清单本身再显式登记一次（2026-11-03 用户口径「演员详情附带的 id」）：
        # ``_harvest`` 靠 HTML 里能匹配到的链接，`.org` 的人物页作品来自页面内嵌
        # JSON（Alpine 数据），纯链接抓取会整段漏掉 —— 表现就是「演员详情里明明
        # 有作品 id，ID 库里却一条都没有」。有名字才入（仓储层也会丢空名）。
        self._register_person_works(person)
        # 侧栏「XX合作的演员」同理显式登记（``.org`` 链接形态 ``_harvest`` 认不出）
        self._register_person_people(person)
        return self._with_person_external(person, target)

    async def _douban_person(self, media_id: str) -> Optional[dict]:
        """``doubanp:{pid}`` 人物档案：直接走豆瓣影人页，不碰站点。

        外部 id 库里存着一批 ``doubanp:`` 值（人物的豆瓣绑定），它们本身就是可用
        的        身份 —— 点开就该出档案（2026-11-04 用户口径「外面 id 记录的这些 id，
        豆瓣人物和作品都能用」）。作品清单每部都是 ``douban:{sid}``，点开走豆瓣
        作品通道；字段与站点人物档案对齐，``origin="douban"`` 供展示层区分。

        老式 7 位 celebrity id 宿主读不了（见下面的回落），那时交出的是**同名站点
        人物档案**：入口不同、内容同一个人的完整档案，点开不会扑空。
        """
        cached = self._cache.get_person(media_id) if self._cache else None
        if cached:
            return self._with_person_external(dict(cached), media_id)
        if self._cache and self._cache.is_negative(f"person:{media_id}"):
            return None
        data = await douban.person_detail(media_id.partition(":")[2])
        if not data:
            # 老式影人 id（``/celebrity/1337644/`` 这种 7 位）宿主读不了：它的
            # ``person_detail`` 走新 ``elessar`` 接口，只认 8 位新 id。库里这类值
            # 有 51 条（演职员表回填留下的），与其给死链，不如落到同名站点人物行
            # 的档案 —— 那份档案本来就带着自己的豆瓣新 id 与作品清单。
            for row in self._store.by_douban(douban=media_id) or []:
                mid = str(row.get("media_id") or "").strip()
                if mid.partition(":")[0] in constants.ENTITY_PERSON:
                    return await self.get_person(mid)
            # 通道异常 / 条目不存在都按取不到处理，负缓存挡住 TTL 内的重复请求
            if self._cache:
                self._cache.mark_negative(f"person:{media_id}")
            return None
        works: list[dict] = []
        for item in data.get("works") or []:
            if not isinstance(item, dict) or not item.get("media_id"):
                continue
            works.append(
                {
                    "media_id": str(item.get("media_id") or ""),
                    "name": str(item.get("name") or ""),
                    "kind": "",
                    "poster": str(item.get("poster") or ""),
                    "date": "",
                    "episodes": 0,
                    "actors": [],
                    "tags": [str(t) for t in item.get("roles") or [] if t],
                    "origin": constants.DOUBAN_WORK,
                    "year": str(item.get("year") or ""),
                    "rating": float(item.get("rating") or 0.0),
                }
            )
        person = {
            "media_id": media_id,
            "name": str(data.get("name") or ""),
            "role": "",
            "kind": "",
            "avatar": str(data.get("avatar") or ""),
            "intro": str(data.get("desc") or ""),
            "works": works,
            "work_count": len(works),
            "people": [],
            "detail_url": str(data.get("url") or ""),
            "douban_info": [
                f"{key}：{value}" for key, value in (data.get("info") or {}).items()
            ],
        }
        if self._cache:
            self._cache.set_person(media_id, person)
        self._register(media_id, person["name"])
        self._register_person_works(person)
        return self._with_person_external(dict(person), media_id)

    # ── ①' 豆瓣影人融合（人物档案用） ────────────────────────────────
    async def _refresh_person_bindings(self, person: dict) -> dict:
        """缓存命中时按判定版本补跑一次外部 id 绑定（不重抓主站页面）。

        ``bind_ver`` 记的是「按哪一版判定试过」——**不是外部 id**，只是防重搜的
        状态位。绑定结论（``doubanp:`` / ``tmdbp:``）只写 ID 库，返回前由
        :meth:`_with_person_external` 按名回库取。
        """
        target = str(person.get("media_id") or "").strip()
        # 旧格式缓存里带过 douban_id / tmdb_id —— 清掉（``bind_ver`` 是判定版本位，
        # 留着；外部 id 一律从 ID 库取，写回缓存时也不带）
        legacy = [key for key in ("douban_id", "tmdb_id") if key in person]
        for key in legacy:
            person.pop(key, None)
        if int(person.get("bind_ver") or 0) >= BIND_VERSION:
            if legacy and target and self._cache:
                # 顺便把干净的副本写回缓存，旧副本不再留外部 id
                self._cache.set_person(target, person)
            return person
        try:
            person = await self._fuse_douban_person(person)
        except Exception as err:  # pragma: no cover - 补融合失败不影响档案
            logger.warning(f"{constants.SOURCE_NAME} 缓存人物补融合失败 {target}：{err}")
        try:
            person = await self._fuse_tmdb_person(person)
        except Exception as err:  # pragma: no cover
            logger.warning(f"{constants.SOURCE_NAME} 缓存人物补 TMDB 失败 {target}：{err}")
        person["bind_ver"] = BIND_VERSION
        if target and self._cache:
            # 副本写回缓存：缓存里仍然只有站点数据 + 判定版本，没有外部 id
            self._cache.set_person(target, person)
        return person

    def _with_person_external(self, person: dict, media_id: str) -> dict:
        """按名从 ID 库挂影人的外部 id（``doubanp:{pid}`` / ``tmdbp:{pid}``）。

        站点 id 只用于查人物缓存；外部 id 每次现查库 —— 面板里改过 id，下一次
        打开档案就是新值（2026-11-04 用户口径）。返回**副本**：调用方可能拿到的是
        缓存里那份 dict，原地挂 id 会把外部 id 又带进缓存。
        """
        try:
            row = self._store.get(media_id=media_id) or {}
        except Exception as err:  # pragma: no cover - 读库失败按未绑定返回
            logger.warning(f"{constants.SOURCE_NAME} 读影人外部 id 失败 {media_id}：{err}")
            row = {}
        out = dict(person)
        out["douban_id"] = str(row.get("douban") or "")
        out["tmdb_id"] = str(row.get("tmdb") or "")
        return out

    async def bind_person_by_name(self, media_id: str, name: str) -> dict:
        """给人物**ID 库行**按名直绑外部 id（不抓人物页）。

        批量补 id 的快速通道（2026-11-04）。走一个人物页要 5~6 秒，而页面带回来的
        作品清单对「补 id」这件事几乎没有增量 —— 短剧演员的百科作品绝大多数还没
        绑豆瓣 sid，作品交集判据在库里根本没有原料。所以先按名试一次：

        * 豆瓣：候选里**唯一精确同名** → 写 ``doubanp:{pid}``；同名多于一个 →
          ``need_page=True``（交给人物页按作品交集消歧）；零候选 → 什么都不做
          （多半是风控，不占位，下次再试）；
        * TMDB：同一口径，唯一同名才写 ``tmdbp:{pid}``。

        返回 ``{"douban": bool, "tmdb": bool, "need_page": bool}``，
        两个 bool 只表示**这一次新绑上**（已绑好的不算命中）。
        """
        out = {"douban": False, "tmdb": False, "need_page": False}
        mid = str(media_id or "").strip()
        title = str(name or "").strip()
        if not mid or not title:
            return out
        try:
            row = self._store.get(media_id=mid) or {}
        except Exception:  # pragma: no cover - 读库失败按未绑定处理
            row = {}
        has_douban = str(row.get("douban") or "").startswith(f"{constants.DOUBAN_PERSON}:")
        has_tmdb = str(row.get("tmdb") or "").startswith(f"{constants.TMDB_PERSON}:")

        async def _douban_side() -> None:
            exact: list[str] = []
            for cand in await douban.person_search(title):
                pid = str(cand.get("media_id") or "").partition(":")[2]
                if pid.isdigit() and _name_key(cand.get("name")) == _name_key(title):
                    if pid not in exact:
                        exact.append(pid)
            if len(exact) > 1:
                out["need_page"] = True
            elif exact:
                composite = f"{constants.DOUBAN_PERSON}:{exact[0]}"
                try:
                    out["douban"] = bool(
                        self._store.set_external_ids(media_id=mid, douban=composite)
                    )
                except Exception as err:  # pragma: no cover - 写库失败不影响这一轮
                    logger.warning(
                        f"{constants.SOURCE_NAME} 按名绑影人失败 {mid}：{err}"
                    )

        async def _tmdb_side() -> None:
            exact_t: list[str] = []
            for cand in await tmdb.person_search(title):
                pid = str(cand.get("id") or "").strip()
                if pid.isdigit() and _name_key(cand.get("name")) == _name_key(title):
                    if pid not in exact_t:
                        exact_t.append(pid)
            if len(exact_t) > 1:
                out["need_page"] = True
            elif exact_t:
                composite_t = f"{constants.TMDB_PERSON}:{exact_t[0]}"
                try:
                    out["tmdb"] = bool(
                        self._store.set_external_ids(media_id=mid, tmdb=composite_t)
                    )
                except Exception as err:  # pragma: no cover
                    logger.warning(
                        f"{constants.SOURCE_NAME} 按名绑 TMDB 影人失败 {mid}：{err}"
                    )

        # 两条通道互不相干，并发跑：一条一搜各约 1 秒，串行就是白等
        jobs = []
        if not has_douban and not douban.search_blocked():
            jobs.append(_douban_side())
        if not has_tmdb:
            jobs.append(_tmdb_side())
        if jobs:
            await asyncio.gather(*jobs)
        return out

    async def _fuse_douban_person(self, person: dict) -> dict:
        """把豆瓣影人的作品并进百科人物档案（展示层合并，存储不合并）。

        绑定策略（宁缺毋滥 —— 短剧演员重名极多，绑错人比不合并更糟）：

        1. ID 库已有绑定（``yanyuan`` 行 ``douban`` 列 = ``doubanp:{pid}``）→ 直接用；
        2. 否则 ``person_search(name)`` 取候选，逐个拉豆瓣人物档案，与
           「已回填豆瓣 id 的百科作品」比 **subject id 交集**（精确，权重高），
           其次比作品名交集；零交集就不绑定、不合并；
        3. 绑定成功后把 ``doubanp:{pid}`` 回写 ID 库，下次 0 搜索直接用。

        豆瓣独有的作品追加进作品清单（``origin="douban"``），并登记进 ID 库
        （自映射 ``douban:{sid}``）——点开即可走豆瓣详情通道。
        注意豆瓣载荷只带**最近约 10 部**（翻页接口已废），不能代表全部作品。
        """
        name = str(person.get("name") or "").strip()
        if not name:
            return person
        works: list[dict] = [w for w in person.get("works") or [] if isinstance(w, dict)]

        # 已回填豆瓣 id 的百科作品：sid -> 百科作品名（消歧的主要依据）
        known: dict[str, str] = {}
        for w in works:
            mid = str(w.get("media_id") or "")
            if not mid:
                continue
            row = self._store.get(media_id=mid) or {}
            ref = str(row.get("douban") or "")
            if ref.startswith(f"{constants.DOUBAN_WORK}:"):
                known[ref.partition(":")[2]] = str(w.get("name") or "")

        pid = ""
        dperson = None
        mid = str(person.get("media_id") or "")
        # ① 库里已有绑定（自己那行；外部记录按 person 存一份，与站无关）
        self_row = self._store.get(media_id=mid) or {}
        bound = str(self_row.get("douban") or "")
        if bound.startswith(f"{constants.DOUBAN_PERSON}:"):
            pid = bound.partition(":")[2]
            dperson = await douban.person_detail(pid)
        # ② 搜索消歧
        if dperson is None:
            best_score = 0
            cands = await douban.person_search(name)
            # 候选里**精确同名**的那些（豆瓣影人重名极多，多于一个就绝不猜）
            exact_pids: list[str] = []
            for cand in cands or []:
                cand_pid = str(cand.get("media_id") or "").partition(":")[2]
                if not cand_pid or _name_key(cand.get("name")) != _name_key(name):
                    continue
                if cand_pid not in exact_pids:
                    exact_pids.append(cand_pid)
            if len(exact_pids) == 1:
                # **唯一精确同名 → 直接认**（2026-11-04）。先决理由是实测到的现实：
                # 短剧演员的百科作品绝大多数还没绑豆瓣 sid，`known` 是空的，作品
                # 交集判据永远打 0 分，于是「演员的豆瓣 id 一条都补不上」。
                # 顺带也是最快的一条路：不用把 4 个候选逐个拉档案（一次约 1 秒）。
                # 多个同名才回到交集打分，一个都不像就占位。
                cd = await douban.person_detail(exact_pids[0])
                if cd:
                    pid, dperson, best_score = exact_pids[0], cd, 1
            if dperson is None:
                for cand in (cands or [])[:4]:
                    cand_pid = str(cand.get("media_id") or "").partition(":")[2]
                    if not cand_pid:
                        continue
                    cd = await douban.person_detail(cand_pid)
                    if not cd:
                        continue
                    sids = {
                        str(w.get("media_id") or "").partition(":")[2]
                        for w in cd.get("works") or []
                    }
                    names = {_name_key(w.get("name")) for w in cd.get("works") or []}
                    score = (
                        len(sids & set(known)) * 10
                        + len(names & {_name_key(w.get("name")) for w in works})
                    )
                    if score > best_score:
                        best_score, pid, dperson = score, cand_pid, cd
            if best_score <= 0 or dperson is None:
                # 绑不上就什么都不写：外部 id 不落缓存（只存 ID 库），重试节奏由
                # ``bind_ver`` 的版本号管 —— BIND_VERSION 升一次才重新试一次。
                # 「一个候选都没搜到」多半是风控 / 通道忙（宿主把 403 吞成 None），
                # 那种情况本来就该留待下轮。
                return person

        # 绑定回写 ID 库（外部 id 反查 doubanp:{pid} 能落到这行）
        try:
            self._store.set_external_ids(
                media_id=str(person.get("media_id") or ""),
                douban=f"{constants.DOUBAN_PERSON}:{pid}",
            )
        except Exception as err:  # pragma: no cover - 绑定失败不影响合并
            logger.warning(f"{constants.SOURCE_NAME} 豆瓣影人绑定失败 {name}：{err}")

        # 合并豆瓣独有作品（sid 命中 / 同名的一律视为同片，不重复出卡）
        known_names = {str(w.get("name") or "") for w in works}
        known_sids = set(known)
        register: list[tuple[str, str]] = []
        for w in dperson.get("works") or []:
            wid = str(w.get("media_id") or "")
            sid = wid.partition(":")[2]
            wname = str(w.get("name") or "")
            if not wid or sid in known_sids or (wname and wname in known_names):
                continue
            works.append(
                {
                    "media_id": wid,
                    "name": wname,
                    "kind": "",
                    "poster": str(w.get("poster") or ""),
                    "date": "",
                    "episodes": 0,
                    "actors": [],
                    "tags": [str(t) for t in w.get("roles") or [] if t],
                    "origin": "douban",
                    "year": str(w.get("year") or ""),
                    "rating": float(w.get("rating") or 0.0),
                }
            )
            known_names.add(wname)
            register.append((wid, wname))

        # 豆瓣独有作品登记进 ID 库：自映射 douban:{sid}，面板点开即走豆瓣详情
        if register:
            try:
                self._store.upsert_many(rows=register)
                for mid, _ in register:
                    self._store.set_external_ids(media_id=mid, douban=mid)
            except Exception as err:  # pragma: no cover - 登记失败不影响合并
                logger.warning(f"{constants.SOURCE_NAME} 豆瓣作品登记失败 {name}：{err}")

        for w in works:
            w.setdefault("origin", "baike")
        person["works"] = works
        person["work_count"] = len(works)
        person["douban_info"] = [
            f"{key}：{value}" for key, value in (dperson.get("info") or {}).items()
        ]
        return person

    async def _fuse_tmdb_person(self, person: dict) -> dict:
        """给人物绑 TMDB 影人 id（``baike.tmdb`` 列写 ``tmdbp:{pid}``）。

        走宿主 ``TmdbApi.async_search_persons`` / ``async_get_person_credits``
        （2026-11-03 用户提醒「系统有人物搜索的接口」）—— 之前只接了豆瓣一条腿，
        ``actor`` 行的 ``tmdb`` 列永远是空的。

        判据与豆瓣侧同口径，宁缺毋滥：

        1. 库里已有 ``tmdbp:{pid}`` 绑定 → 直接用（0 搜索）；
        2. ``person_search(name)`` 取候选，**优先精确同名**；没有精确同名时只在
           「唯一候选」时才继续（拼音名 / 英文名的唯一匹配），多候选一律不猜；
        3. 逐个用 ``known_for``（代表作）与本人百科作品名求交集，交集为零再拉
           完整 credits 补算；取分数最高的一个，**最高分并列不绑**；
        4. 零交集 / 并列 → 落空串占位（TTL 内不重试）；候选为空（通道异常）
           不占位，留待下轮。

        只绑 id，**不合并 TMDB 作品**：TMDB 上短剧与长剧、电影混在一起，
        合进来会把「作品清单」污染成非短剧。
        """
        media_id = str(person.get("media_id") or "")
        name = str(person.get("name") or "").strip()
        if not media_id or not name:
            return person
        try:
            row = self._store.get(media_id=media_id) or {}
        except Exception:  # pragma: no cover - 读库失败按未绑定处理
            row = {}
        bound = str(row.get("tmdb") or "")
        if bound.startswith(f"{constants.TMDB_PERSON}:"):
            # 已绑：不用再搜（值由 ``_with_person_external`` 统一从库挂上）
            return person

        works = {
            str(w.get("name") or "").strip() for w in person.get("works") or []
        }
        works.discard("")
        cands = await tmdb.person_search(name)
        if not cands:
            # 通道异常 / 空结果：不占位，下次还能重试（与豆瓣侧同一纪律）
            return person
        pool = [cand for cand in cands if cand["name"] == name]
        if not pool:
            if len(cands) != 1:
                # 搜到了人但都不是同名 —— 重名极多，不猜（结论只由 bind_ver 记节奏）
                return person
            pool = cands

        best_pid, best_score, tie = "", 0, False
        for cand in pool[:4]:
            score = len(set(cand["works"]) & works)
            if not score:
                score = len(set(await tmdb.person_credits(cand["id"])) & works)
            if score > best_score:
                best_pid, best_score, tie = cand["id"], score, False
            elif score == best_score and score > 0:
                tie = True
        if best_score <= 0 or tie or not best_pid:
            return person

        composite = f"{constants.TMDB_PERSON}:{best_pid}"
        try:
            self._store.set_external_ids(media_id=media_id, tmdb=composite)
        except Exception as err:  # pragma: no cover - 写库失败不影响档案
            logger.warning(
                f"{constants.SOURCE_NAME} 回填 TMDB 影人失败 {media_id}：{err}"
            )
        return person

    def _cast_person_id(self, name: str) -> str:
        """演职员名字 → ID 库里的**人物行** ``media_id``（没有就回空串）。

        豆瓣演职员表给的是老式 celebrity id（``/celebrity/1337644/``），宿主豆瓣
        通道的 ``person_detail`` 走的是新 ``elessar`` 接口，**读不了老 id**（实测
        ``1337644`` / ``1318061`` 一律空响应，只有 ``35092145`` 这类新 id 能出档）。
        拿老 id 拼 ``doubanp:`` 只会得到一条点开即失败的链接，所以这里改成按名回
        本站 ID 库找人物行：有同名人物就用它的 ``media_id``（点开是完整的站点档案，
        里面自然带着豆瓣作品），没有就留空 —— 宁可不可点，也不给死链。
        """
        key = str(name or "").strip()
        if not key:
            return ""
        try:
            rows = self._store.by_name(name=key)
        except Exception as err:  # pragma: no cover - 读库失败按未收录处理
            logger.warning(f"{constants.SOURCE_NAME} 演职员按名查库失败 {key}：{err}")
            return ""
        for row in rows or []:
            mid = str(row.get("media_id") or "").strip()
            if mid.partition(":")[0] in constants.ENTITY_PERSON:
                return mid
        return ""

    async def _attach_douban_cast(self, detail: dict, sid: str) -> None:
        """把豆瓣演职员表并进详情（``tv_detail`` 只给名字、不给 id）。

        豆瓣作品详情的 ``actors`` 是 ``[{"name": "卡戎"}]``、``directors`` 常常是空
        数组 —— 照原样返回，面板上的演员就是**点不开的纯文字**；而站点作品的演员
        都带 ``url``，点开就是人物档案。两边都是「作品」，这一半不该缺（2026-11-04
        用户口径「豆瓣作品为什么不一起处理」）。

        带影人 id 的只有 ``/tv/{sid}/celebrities``，所以这里补一次：按站点作品同款
        结构写回，``detail_to_media_info`` 就能反推出人物页地址，点演员走 ``/person``。
        那个 id 是**老式 celebrity id**，宿主的豆瓣通道读不了，所以 ``media_id``
        取 ``cast_person_id``（同名人物行的站点身份），见该方法的说明。
        演职员表按 sid 缓存在 ``djbaike.douban``（搜索同一个 region），TTL 内不重抓；
        通道被限流时 ``tv_celebrities`` 返回 ``None``，**保持原样**，不写空列表、
        不留标记。
        """
        if not sid:
            return
        key = f"cred:{sid}"
        creds = self._cache.douban.get(key) if self._cache else None
        if not isinstance(creds, list):
            creds = await douban.tv_celebrities(sid)
            if creds and self._cache:
                self._cache.douban.set(key, creds)
        if not creds:
            return
        actors: list[dict] = []
        directors: list[dict] = []
        for cred in creds:
            pid = str(cred.get("pid") or "").strip()
            name = str(cred.get("name") or "").strip()
            if not pid or not name:
                continue
            item = {
                "media_id": self._cast_person_id(name),
                "name": name,
                "role": str(cred.get("role") or "").strip(),
                "poster": str(cred.get("avatar") or "").strip(),
            }
            (directors if cred.get("kind") == "director" else actors).append(item)
        if actors:
            detail["actors"] = actors
        if directors:
            detail["directors"] = directors

    async def _load_douban(self, media_id: str) -> Optional[dict]:
        """豆瓣剧集详情：``tv_detail`` → 补演职员表 → 写缓存 → 自映射入库。"""
        sid = native_id_of(media_id)
        detail = await douban.tv_detail(sid)
        if not detail:
            if self._cache:
                self._cache.mark_negative(media_id)
            return None
        # 演职员表补 id：豆瓣详情只给名字，不补的话演员点不开（与站点作品不对称）
        await self._attach_douban_cast(detail, sid)
        if self._cache:
            self._cache.set_detail(media_id, detail)
        self._register(
            media_id, detail.get("name", ""), ai=is_excluded_item(detail)
        )
        # 豆瓣条目的 ``douban`` 列是**自映射**：``douban:{sid}`` 即它自己
        try:
            self._store.set_external_ids(media_id=media_id, douban=media_id)
        except Exception as err:  # pragma: no cover - 回填失败不影响主流程
            logger.error(f"{constants.SOURCE_NAME} 回填豆瓣 id 失败 {media_id}：{err}")
        return detail

    async def backfill_person_douban(self, *, limit: int = 20, after: str = "") -> dict:
        """按豆瓣**演职员表**给人物行补 ``doubanp:{pid}``（2026-11-03 实装）。

        为什么必须走这条路：豆瓣作品详情 ``tv_detail`` 的 ``actors`` 只有名字
        （``[{"name": "卡戎"}]``）、``directors`` 常为空 —— **不带 id**；唯一带
        影人 id 的是 ``/tv/{sid}/celebrities``。所以链路反过来走：

        1. 从 ID 库取**已绑豆瓣 sid 的作品**（``douban:{sid}`` 或自映射的
           ``douban:`` 行）；
        2. 逐部拉演职员表，攒 ``name → {pid}`` 池；
        3. 池里**影人 id 唯一**的名字，去 ID 库找同名人物行，``douban`` 列空着
           的就写上 ``doubanp:{pid}``。

        判据硬在「同一部作品里同名」：百科说这部片的演员是 N，豆瓣说这部片的
        演员里有个 N（id 明确），那就是同一个人 —— 比 ``person_search`` +
        「影人作品交集打分」准得多，也不用猜重名。**同名出现多个 pid 的一律
        跳过**（可能真是两个人），宁可先不绑。

        ``limit`` 是**作品条数**（不是人物条数），``after`` 是作品 media_id 游标。
        返回 ``{"scanned","bound","remaining","cursor","throttled"}``。
        """
        total, rows = self._store.works_with_douban(limit=limit, after=after)
        pool: dict[str, set[str]] = {}
        scanned = 0
        cursor = after
        throttled = False
        miss_streak = 0
        for row in rows:
            media_id = str(row.get("media_id") or "").strip()
            cursor = media_id or cursor
            ref = str(row.get("douban") or "")
            if not ref.startswith(f"{constants.DOUBAN_WORK}:"):
                continue
            sid = ref.partition(":")[2]
            if not sid:
                continue
            creds = await douban.tv_celebrities(sid)
            if creds is None:
                # 宿主把 404 和限流**一起吞成 None**，插件侧分不出「这条 sid 失效」
                # 与「通道被限」。实测（2026-11-03）库里 92 部已绑豆瓣的作品有
                # **28 部的 sid 根本取不到演职员表**（早期按名匹配错绑的老条目），
                # 阈值定小了会在坏 sid 密集段误判成限流、整轮停在原地（scanned=0）；
                # 定大了真限流时会白打十几次。取 10：坏 sid 连号也很少凑够。
                miss_streak += 1
                if miss_streak >= 10:
                    throttled = True
                    break
                continue
            miss_streak = 0
            scanned += 1
            for cred in creds:
                pool.setdefault(str(cred.get("name") or ""), set()).add(
                    str(cred.get("pid") or "")
                )
            # 演职员表比搜索宽松，但仍是一次外站请求：一秒一部，别把通道打热
            await asyncio.sleep(1.0)

        bound = 0
        for name, pids in pool.items():
            if not name or len(pids) != 1:
                continue
            pid = next(iter(pids))
            if not pid.isdigit():
                continue
            try:
                same_name = self._store.by_name(name=name)
            except Exception as err:  # pragma: no cover - 单条读库失败不影响整轮
                logger.warning(f"{constants.SOURCE_NAME} 按名查人物失败 {name}：{err}")
                continue
            for person in same_name or []:
                mid = str(person.get("media_id") or "").strip()
                if mid.partition(":")[0] not in constants.ENTITY_PERSON:
                    continue
                if str(person.get("douban") or ""):
                    continue
                try:
                    if self._store.set_external_ids(
                        media_id=mid, douban=f"{constants.DOUBAN_PERSON}:{pid}"
                    ):
                        bound += 1
                except Exception as err:  # pragma: no cover
                    logger.warning(
                        f"{constants.SOURCE_NAME} 写人物豆瓣 id 失败 {mid}：{err}"
                    )
        if bound:
            logger.info(
                f"{constants.SOURCE_NAME} 演职员表回填人物豆瓣 id：扫 {scanned} 部作品，"
                f"补上 {bound} 个人物{'（通道限流提前收工）' if throttled else ''}"
            )
        return {
            "scanned": scanned,
            "bound": bound,
            "remaining": total,
            "cursor": cursor,
            "throttled": throttled,
        }

    async def fill_external_ids(
        self,
        media_id: str,
        name: str,
        *,
        douban_now: str = "",
        tmdb_now: str = "",
    ) -> dict:
        """给**库里已有的一行**补外部 id（不抓页面、不建详情缓存）。

        为什么需要它（2026-11-03 用户口径「豆瓣 / TMDB 一个都没补上」）：
        库里的行绝大多数来自榜单 / 人物作品 / 顺带登记，豆瓣 / TMDB 两列一直是
        空的 —— 实测 3874 行里 ``drama:`` 的 ``douban`` 列一条都没有值。

        两个入口共用它：读详情时缺哪一半顺手补（:meth:`_with_external`），
        以及 ``/baike/extids`` 批量补（跑完库、不走详情）。

        判据与详情链路**完全一致**：名字去空白后必须完全相等（短剧同名极多，
        写错 id 比没有更糟），所以只做「精确匹配」，不做相似度猜测。

        TMDB 有两条路：详情缓存里有 ``year`` 就按年搜（最准）；没有年份
        （库里绝大多数行都没取过详情）就不限年搜一次，但只在**精确同名且唯一**
        时才认 —— 命中率实测 4/6，多条同名一律跳过。

        返回 ``{"douban": "douban:38393056"|"", "tmdb": "tmdb:317820"|"", "throttled": bool}``。
        """
        out = {"douban": "", "tmdb": "", "throttled": False}
        mid = str(media_id or "").strip()
        title = str(name or "").strip()
        if not mid or not title:
            return out
        # 豆瓣被风控（code=103，宿主会把它吞成 None）时**只跳过豆瓣这一半**，
        # 继续把 TMDB 那条通道跑完 —— 两条通道互不相干，没理由一起停。
        # （2026-11-03 实测：豆瓣 403 need_login 会持续十几分钟甚至更久，
        #  若整轮直接放弃，TMDB 也一条都补不上。）
        douban_blocked = bool(not douban_now and douban.search_blocked())
        if douban_blocked:
            out["throttled"] = True

        # 豆瓣已经补过的行不再搜（批量是按「任一为空」取货的，不跳过就白烧配额）
        cache_key = f"search:{title}"
        items = None if douban_now else (self._cache.douban.get(cache_key) if self._cache else None)
        if not douban_now and not isinstance(items, list):
            items = await douban.tv_search(title, 10)
            if self._cache and items:
                self._cache.douban.set(cache_key, items)
        for item in items or []:
            if not isinstance(item, dict):
                continue
            if str(item.get("name") or "").strip() != title:
                continue
            sid = str(item.get("media_id") or "").rsplit(":", 1)[-1]
            if not sid.isdigit():
                continue
            composite = f"{constants.DOUBAN_WORK}:{sid}"
            try:
                self._store.set_external_ids(media_id=mid, douban=composite)
            except Exception as err:  # pragma: no cover - 写库失败不影响这一轮
                logger.error(f"{constants.SOURCE_NAME} 批量回填豆瓣 id 失败 {mid}：{err}")
                break
            out["douban"] = composite
            break

        cached = self._cache.get_detail(mid) if self._cache else None
        year = str((cached or {}).get("year") or "").strip()[:4]
        if tmdb_now:
            return out
        # TMDB：有年份就按年份搜（最准）；没有就**不限年**搜一次，但只在
        # 「精确同名且唯一」时才认（实测 6 部里 4 部能这样命中，多条同名一律跳过
        # —— 同名一般都同剧，撞名才是例外，所以「唯一」这条硬杠够用）。
        tmdb_key = f"tmdb:{title}:{year or 'any'}"
        tmdb_items = self._cache.douban.get(tmdb_key) if self._cache else None
        if not isinstance(tmdb_items, list):
            tmdb_items = await tmdb.tv_search(title, year)
            if self._cache and tmdb_items:
                self._cache.douban.set(tmdb_key, tmdb_items)
        exact: list[dict] = []
        for item in tmdb_items or []:
            if not isinstance(item, dict):
                continue
            if str(item.get("name") or "").strip() != title:
                continue
            item_year = str(item.get("year") or "").strip()[:4]
            if year and item_year and item_year != year:
                continue
            if not str(item.get("id") or "").strip().isdigit():
                continue
            exact.append(item)
        if exact and (year or len(exact) == 1):
            tmid = str(exact[0].get("id") or "").strip()
            try:
                self._store.set_external_ids(media_id=mid, tmdb=tmid)
                out["tmdb"] = tmdb_composite(tmid)
            except Exception as err:  # pragma: no cover
                logger.error(f"{constants.SOURCE_NAME} 批量回填 TMDB id 失败 {mid}：{err}")
        return out

    async def _load_baike(self, media_id: str) -> Optional[dict]:
        """百科详情页：抓取 → 解析 → 写缓存 → 回写 baike + 顺带登记。"""
        url = detail_url(media_id)
        if not url:
            return None
        html = await self._fetcher.get_html(url)
        if not html:
            if self._cache:
                self._cache.mark_negative(media_id)
            return None

        # 解析器按**身份前缀**选，与主站配置无关：``drama:`` 永远是 .org 的页面
        # （两站编号空间不同，拿 .net 的正则去解 .org 页面只会得到空壳），
        # 这样换站也不会把已入库的旧身份解析坏。
        if entity_of(media_id) in constants.ORG_ENTITIES:
            detail = orgadapt.work_detail(
                media_id, orgsite.parse_work(html, url=url)
            ) if is_drama(media_id) else None
        else:
            detail = (
                parse_detail(media_id, html)
                if (is_drama(media_id) or is_novel(media_id))
                else None
            )
        if not detail:
            # 人物页不归这里管（走 get_person），**不能**标负缓存：那会把人物档案
            # 一起废掉（两者共用 media_id 当 key 时尤其致命，见 get_person 注释）
            if not is_person(media_id) and self._cache:
                self._cache.mark_negative(media_id)
            self._harvest(html)
            return None

        # 外部 id **不进详情缓存**（2026-11-04 用户口径）：站点 id 只当缓存键，
        # 豆瓣 / TMDB 一律回 ID 库按名查 —— 每次都从库读、缺的顺手补，
        # 缓存里不留副本、也不留"补过没有"的标记。
        detail.pop("douban_id", None)
        detail.pop("tmdb_id", None)

        if self._cache:
            self._cache.set_detail(media_id, detail)
        self._register(
            media_id, detail.get("name", ""), ai=is_excluded_item(detail)
        )
        self._harvest(html, detail)
        return detail

    # ── ② 外部 id 反查（douban 裸 id） ───────────────────────────────
    async def recognize_external(self, douban_id: str = "", tmdb_id: str = ""):
        """按豆瓣 / TMDB id 反查并取详情（宿主常带 ``doubanid``）。"""
        sid = str(douban_id or "").strip()
        tid = str(tmdb_id or "").strip()

        if sid:
            # 作品与人物共用 subject 空间 → 两个复合前缀各查一次
            for prefix in (constants.DOUBAN_WORK, constants.DOUBAN_PERSON):
                composite = f"{prefix}:{sid}"
                rows = self._store.by_douban(douban=composite)
                if rows:
                    return await self.recognize(rows[0]["media_id"])
            # 库里没有映射：先按作品取详情，取到就自映射入库
            return await self.recognize(f"{constants.DOUBAN_WORK}:{sid}")

        if tid:
            rows = self._store.by_tmdb(tmdb=tid)
            if rows:
                # tmdb 是系列级，可能多条；取类型优先 + id 字典序的第一条
                return await self.recognize(sorted(rows, key=_candidate_sort_key)[0]["media_id"])
        return None

    # ── ③④⑤ 候选检索 ────────────────────────────────────────────────
    async def find_candidates(
        self,
        name: str,
        *,
        remote: bool = True,
        pages: int = 1,
        include_person: bool = False,
        include_novel: bool = False,
        douban_fallback: bool = True,
        merge_remote: bool = False,
        season: Optional[int] = None,
        site_kinds: tuple = ("drama",),
    ) -> list[dict]:
        """按名找候选：③ 本地精确 → ④ 站内搜索 → ⑤ 豆瓣（百科 0 结果才走）。

        返回 ``[{media_id, name, kind, poster, origin}]``；默认剔除人物与原著。

        ``merge_remote=False``（识别用）：本地精确命中即返回——同名即准，没必要联网；
        ``merge_remote=True``（手动搜索用）：本地结果**并入**站内搜索结果，让用户看到
        同名的其它版本（如「以爱为家」本地只有 2 条精确同名，站内其实有 14 条）。

        ``season`` >= 2 时本地先认「第N季」独立词条（站点一季一条的存法），
        选优（``pick_best``）也按季号收敛，避免同基名的第 N 季发布被选回第一季。
        """
        keys = clean_candidates(name)
        if not keys:
            return []

        # ③ 本地：最干净候选优先，命中即停（季号 >= 2 先认「第N季」独立词条）
        local: list[dict] = []
        if season and season >= 2:
            for key in keys:
                for suffix in season_suffixes(season):
                    rows = self._store.by_name(name=f"{key}{suffix}")
                    if rows:
                        local = rows
                        break
                if local:
                    break
        if not local:
            for key in keys:
                rows = self._store.by_name(name=key)
                if rows:
                    local = rows
                    break
        if local and not merge_remote:
            return self._filter(self._pack(local, origin="local"), include_person, include_novel)

        if not remote:
            return self._filter(self._pack(local, origin="local"), include_person, include_novel)

        # **只拿含中文的候选去搜站内**：本数据源只收中文名，拼音/英文候选（宿主的
        # ``title`` 常是「中文名.拼音.规格」整串，洗出来的 ASII 段）打站内必然 0 结果，
        # 让它们占掉「前 3 次」的预算纯属浪费网络。
        site_keys = [key for key in keys if _has_cjk(key)] or keys
        keyword = site_keys[0]

        # ④ 站内搜索（缓存 6h；命中页全量登记）；合并模式下与本地结果并集
        #
        # **候选逐个试，命中即停（前 3 个）**：短剧种子常把营销标签放在最前的方括号里
        # （``[2X免费]实习生掌权，三月干垮整家公司（57集） - SKIT``），此时首位候选是
        # ``2X免费`` —— 拿它搜站内必然 0 结果，而真正的剧名就排在第 2、3 位。
        # 只试 3 个是为了兜住网络成本：正常种子首位就命中，一次即停。
        site_rows: list[dict] = []
        for candidate in site_keys[:3]:
            if len(candidate) < 2:
                continue
            # ``site_kinds`` 只在 .org 生效（新站作品 / 人物分两个检索端点）；
            # .net 一个 ``/so.html`` 同回两块，多传的 kind 会被忽略
            rows: list[dict] = []
            kinds = site_kinds if constants.is_org_site() else ("",)
            for site_kind in kinds:
                rows.extend(
                    await self._site_search(candidate, pages=pages, kind=site_kind)
                )
            if rows:
                site_rows = rows
                keyword = candidate
                break
        merged: list[dict] = []
        merged_map: dict[str, dict] = {}
        for row in list(local) + list(site_rows):
            media_id = str(row.get("media_id") or "")
            if not media_id:
                continue
            base = merged_map.get(media_id)
            if base is None:
                merged_map[media_id] = dict(row)
                merged.append(merged_map[media_id])
                continue
            # 本地行（ID 库）没有海报列，站内搜索行有（.org 的 CDN 绝对地址不能反推）
            # —— 同一部剧两处都命中时，把后到一方的缺项补进去，别让空海报的那份赢。
            for key in ("poster", "kind", "is_ai"):
                if not base.get(key) and row.get(key):
                    base[key] = row[key]
        if merged:
            origin = "local" if not site_rows else "mixed"
            packed = self._filter(self._pack(merged, origin=origin), include_person, include_novel)
            if packed:
                return packed

        # ⑤ 百科 0 结果 → 豆瓣 tv_search（不能直接判"不存在"）
        if not douban_fallback:
            return []
        db_rows = await self._douban_search(keyword)
        return self._filter(self._pack(db_rows, origin="douban"), include_person, include_novel)

    async def _site_search(
        self, keyword: str, *, pages: int = 1, kind: str = ""
    ) -> list[dict]:
        """站内检索：先查缓存，未命中抓取并**全量登记**本页候选。

        ``kind`` 只对 ``.org`` 有意义：新站作品与人物是**两个端点**
        （``/drama/search`` / ``/actor/search``），不传按作品端点。缓存 key 带上
        ``kind``，避免两种端点互相污染。
        """
        kind_key = str(kind or "").strip().lower()
        cache_key = f"search:{keyword}" if kind_key in ("", "drama") else f"search:{kind_key}:{keyword}"
        if self._cache:
            cached = self._cache.search.get(cache_key)
            # 旧缓存（「排除 AI 剧」改造之前写入）的行没有 ``is_ai`` 键：新站靠它
            # 判 AI 剧，读旧行等于让开关失效。再后来（搜索带海报改造）的行没有
            # ``poster`` 键：新站海报只能随卡拿，读旧行等于搜索结果永远无图。
            # 两者都当未命中，重抓一次（自然覆盖）。
            if isinstance(cached, list) and not (
                constants.is_org_site()
                and any(
                    "is_ai" not in row or "poster" not in row for row in cached
                )
            ):
                return cached
            if self._cache.is_negative(cache_key):
                return []

        rows: list[dict] = []
        seen: set[str] = set()
        for page in range(1, max(1, int(pages or 1)) + 1):
            # .org 的检索页不分页（URL 只有 q）——再翻就是同一页，白跑一趟请求
            if page > 1 and constants.is_org_site():
                break
            cards = await search.search_cards(
                keyword, page, fetcher=self._fetcher, kind=kind_key
            )
            if not cards:
                break
            for entity, native_id, name, kind, is_ai, poster in cards:
                media_id = f"{entity}:{native_id}"
                if media_id in seen:
                    continue
                seen.add(media_id)
                # kind 来自卡片上的原始标注（短剧/漫剧/原著），拿不到就给空串，
                # 后面 `_pack` 会退回按 media_id 前缀推。
                # is_ai 只有 .org 卡片才有（标题行 ``AI短剧`` 标），老站恒 False。
                # poster 只有 .org 卡片才有（CDN 绝对地址，不能按 id 反推）；
                # 老站恒空串，`_pack` 会退回 image_url 按前缀反推。
                rows.append(
                    {
                        "media_id": media_id,
                        "name": name,
                        "kind": kind,
                        "is_ai": is_ai,
                        "poster": poster,
                    }
                )
            if len(cards) < search.PAGE_SIZE:
                break

        if not rows:
            if self._cache:
                self._cache.mark_negative(cache_key)
            return []
        # 全量登记（不只选中的那一条）——搜索页/目录页都是索引生长入口。
        # ⚠️ 但**被排除的条目不入库**：一旦入库，它下次会以「本地命中」的身份
        # 复活（本地行没有角标 / AI 标，判不了类型），等于绕过整条排除规则。
        # 判据与检索侧同一份：`is_excluded_item`（老站看漫剧角标、新站看 AI 标）。
        register = [
            (row["media_id"], row["name"])
            for row in rows
            if not (_exclude_manju and is_excluded_item(row))
        ]
        try:
            self._store.upsert_many(rows=register)
            # 标注落库：开关关着也记下「这是 AI/漫剧」，开关一开库里就能判
            ai_ids = [row["media_id"] for row in rows if is_excluded_item(row)]
            if ai_ids:
                self._store.mark_ai(media_ids=ai_ids)
        except Exception as err:  # pragma: no cover
            logger.error(f"{constants.SOURCE_NAME} 登记搜索候选失败：{err}")
        if self._cache:
            self._cache.search.set(cache_key, rows)
        return rows

    async def _douban_search(self, keyword: str) -> list[dict]:
        """豆瓣 ``tv_search``：直出 ``douban:{sid}``，并建自映射入库。

        ⚠️ **不要按名字硬过滤**：百科/站内都没有时，豆瓣是唯一还能取到详情的通道；
        模糊检索虽然会带出不相干条目，但交给上层（``pick_best`` / 用户确认）裁决，
        比直接判「不存在」好得多。
        """
        items = await douban.tv_search(keyword)
        if not items:
            return []
        rows: list[dict] = []
        for item in items:
            media_id = item.get("media_id") or ""
            name = item.get("name") or ""
            if not media_id:
                continue
            rows.append(
                {
                    "media_id": media_id,
                    "name": name,
                    "poster": item.get("cover_url") or "",
                }
            )
        try:
            self._store.upsert_many(rows=[(row["media_id"], row["name"]) for row in rows])
            for row in rows:
                self._store.set_external_ids(
                    media_id=row["media_id"], douban=row["media_id"]
                )
        except Exception as err:  # pragma: no cover
            logger.error(f"{constants.SOURCE_NAME} 登记豆瓣候选失败：{err}")
        return rows

    # ── 选优与组装 ───────────────────────────────────────────────────
    def pick_best(
        self,
        candidates: Iterable[dict],
        *,
        year: Any = None,
        season: Optional[int] = None,
    ) -> Optional[dict]:
        """按 §5.1 的确定性规则把多候选收敛成唯一一条（绝不随机）。

        ``season`` >= 2 时**季号词条优先**：站内模糊搜索同基名会把「第N季」独立
        词条一起返回（``隐身侍卫`` 与 ``隐身侍卫第二季``），不先按季号收敛就会
        按年份/热度把第二季的发布选回第一季词条。
        """
        items = [item for item in candidates or [] if item.get("media_id")]
        if season and season >= 2:
            seasonal = [
                item for item in items
                if has_season_suffix(str(item.get("name") or ""), season)
            ]
            if seasonal:
                items = seasonal
        dramas = [item for item in items if is_drama(item["media_id"])]
        if not dramas:
            return None
        year_text = str(year or "").strip()

        def sort_key(item: dict) -> tuple:
            media_id = item["media_id"]
            cached = self._cache.get_detail(media_id) if self._cache else None
            cached_year = str((cached or {}).get("year") or "").strip()
            # ① 年份消歧（只有缓存里才有 year，未知不参与比较）
            year_hit = 0 if (year_text and cached_year and cached_year == year_text) else 1
            # ② 已有详情缓存的优先（省一次抓取，且详情更全）
            cached_rank = 0 if cached else 1
            # ③ entity 偏好 → ④ media_id 字典序
            entity_rank = _ENTITY_PREFERENCE.get(entity_of(media_id), 9)
            return (year_hit, cached_rank, entity_rank, media_id)

        return sorted(dramas, key=sort_key)[0]

    async def recognize_by_name(
        self, name: str, *, year: Any = None, season: Optional[int] = None
    ):
        """按名识别：候选 → 选优 → 取详情；详情失败则回退轻量 ``MediaInfo``。"""
        candidates = await self.find_candidates(name, season=season)
        # 同 `search()`：这条链路不经过 `_filter_by_type`，被排除的条目要在这里
        # 自己剔，否则识别会把一部漫剧 / AI 剧当成短剧收下、一路走到刮削。
        candidates = self.drop_excluded(candidates)
        best = self.pick_best(candidates, year=year, season=season)
        if not best:
            return None
        info = await self.recognize(best["media_id"])
        return info or candidate_to_media_info(best)

    def recognize_by_name_sync(
        self, name: str, *, year: Any = None, season: Optional[int] = None
    ):
        """``recognize_by_name`` 的同步版本。"""
        return run_sync(self.recognize_by_name(name, year=year, season=season))

    async def search(self, name: str, *, remote: bool = True, pages: int = 1) -> list:
        """按名搜索候选 → ``MediaInfo`` 列表（原样返回，不选优）。

        用**合并模式**：本地命中也继续联网，让用户看到同名其它版本。

        ⚠️ **这里必须自己剔**：宿主「搜索媒体」界面走的是
        ``async_search_medias`` → ``DetailService.search``，**不经过**
        ``_filter_by_type``（那是 HTTP ``/lookup`` / ``/search`` 的出口）。
        漏了这一步就会出现「插件面板搜不到、系统搜索却照样出」。
        判据与别处一致：``drop_excluded``（老站看漫剧角标、新站看 AI 标）。
        """
        candidates = await self.find_candidates(name, remote=remote, pages=pages, merge_remote=True)
        candidates = self.drop_excluded(candidates)
        return [candidate_to_media_info(item) for item in candidates]

    # ── 内部 ────────────────────────────────────────────────────────
    @staticmethod
    def _pack(rows: Iterable[dict], *, origin: str) -> list[dict]:
        """仓储/网络行 → 统一候选结构（去重、保序）。"""
        out: list[dict] = []
        seen: set[str] = set()
        for row in rows or []:
            media_id = str(row.get("media_id") or "").strip()
            if not media_id or media_id in seen:
                continue
            seen.add(media_id)
            out.append(
                {
                    "media_id": media_id,
                    "name": str(row.get("name") or ""),
                    # kind **只取行里带的值** —— 即站内搜索卡片右下角那个分类角标。
                    # 2026-10-27 用户口径：判断是否漫剧，这个角标是唯一依据；
                    # 不做前缀兜底（``hema`` 区约 7% 实为短剧，前缀会误判），
                    # 卡片没角标就是空串，不会被当成漫剧。
                    "kind": str(row.get("kind") or "").strip(),
                    # AI 标：只有 .org 卡片带（标题行 ``AI短剧``）。老站 / 本地行恒 False，
                    # 所以「排除 AI 剧」只按卡片事实判，不按站点猜。
                    "is_ai": bool(row.get("is_ai")),
                    # 百科八类海报按前缀反推；豆瓣条目用搜索结果里的封面
                    "poster": str(row.get("poster") or "") or image_url(media_id),
                    "origin": origin,
                }
            )
        return out

    @staticmethod
    def _filter(
        candidates: list[dict],
        include_person: bool,
        include_novel: bool,
    ) -> list[dict]:
        """剔除人物与原著（默认都不进作品候选）。"""
        out: list[dict] = []
        for item in candidates:
            media_id = item["media_id"]
            if is_novel(media_id) and not include_novel:
                continue
            if not include_person and not (is_drama(media_id) or is_novel(media_id)):
                continue
            out.append(item)
        return out

    def _register(self, media_id: str, name: str, *, ai: bool = False) -> None:
        """把当前条目本身写进 ``baike``（存在即忽略，不覆盖旧名字）。

        ``ai=True`` 时顺手把该行标成 ``is_ai``（「排除」开关在库里要判得出
        新站的 AI 剧，只有详情里才带这个标）。
        """
        try:
            self._store.upsert_many(rows=[(media_id, name)])
            if ai:
                self._store.mark_ai(media_ids=[media_id])
        except Exception as err:  # pragma: no cover
            logger.error(f"{constants.SOURCE_NAME} 登记 {media_id} 失败：{err}")

    def _register_person_works(self, person: dict) -> None:
        """把人物档案里的**作品清单**登记进 ID 库（2026-11-03 用户口径）。

        演员详情的作品有两份来源：人物页 HTML 里的卡片（``.net`` 走这条，
        ``_harvest`` 能按 ``info-{id}.html`` 认出来）与页面内嵌 JSON 解析出的
        ``person["works"]``（``.org`` 全走这条）。后者不登记的话，用户在演员
        详情里看到的每个作品 id 都不在库里。
        """
        rows = [
            (str(work.get("media_id") or "").strip(), str(work.get("name") or "").strip())
            for work in (person.get("works") or [])
            if isinstance(work, dict) and str(work.get("media_id") or "").strip()
        ]
        if not rows:
            return
        try:
            self._store.upsert_many(rows=rows)
        except Exception as err:  # pragma: no cover
            logger.error(f"{constants.SOURCE_NAME} 登记人物作品失败：{err}")

    def _register_person_people(self, person: dict) -> None:
        """把人物档案里「XX合作的演员」登记进 ID 库（2026-11-03 用户口径）。

        ``.org`` 人物页侧栏那块合作演员是静态卡片，20 位的 ``actor:<id>``
        解析层已经拿到（``orgsite._coop_people``），但 ``_harvest`` 只认 ``.net``
        的 ``info-{id}.html`` → ``.org`` 的 ``/zh-Hans/actor/136`` 一条都认不出来。
        实测抓一次 ``actor:2`` 的 20 位合作演员只入库 1 位（碰巧被别的链路带到）。
        所以这里和作品清单一样显式登记一次：有名字才入，失败只记日志。
        """
        rows = [
            (str(item.get("media_id") or "").strip(), str(item.get("name") or "").strip())
            for item in (person.get("people") or [])
            if isinstance(item, dict)
            and str(item.get("media_id") or "").strip()
            and str(item.get("name") or "").strip()
        ]
        if not rows:
            return
        try:
            self._store.upsert_many(rows=rows)
        except Exception as err:  # pragma: no cover
            logger.error(f"{constants.SOURCE_NAME} 登记合作演员失败：{err}")

    def _harvest(self, html: str, detail: Optional[dict] = None) -> None:
        """顺带登记页面里出现的其它 id（演员、编剧、原著、推荐位）。"""
        try:
            added = harvest_page(html, self._store)
            if added:
                logger.debug(f"{constants.SOURCE_NAME} 顺带登记 {added} 条")
        except Exception as err:  # pragma: no cover
            logger.error(f"{constants.SOURCE_NAME} 顺带登记失败：{err}")
        # 原著与演员是强关系，明确补一次（避免卡片结构变化时漏登记）
        if not detail:
            return
        for item in list(detail.get("actors", [])) + list(detail.get("directors", [])):
            media_id = item.get("media_id", "")
            if media_id and is_known(media_id) and item.get("name"):
                self._register(media_id, item["name"])
        novel = detail.get("novel")
        if novel and novel.get("media_id"):
            self._register(novel["media_id"], novel.get("name", ""))


def _candidate_sort_key(row: dict) -> tuple:
    """仓储行排序键（tmdb 反查可用多条时用）。"""
    media_id = str(row.get("media_id") or "")
    return (_ENTITY_PREFERENCE.get(entity_of(media_id), 9), media_id)
