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

from . import classify, constants, douban, search, tmdb
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
from .title_clean import _has_cjk, clean_candidates, has_season_suffix, season_suffixes

# 作品类型偏好（§5.1 选优第 4 步）：短剧优先，纯豆瓣条目排最后
_ENTITY_PREFERENCE = {"duanju": 0, "manju": 1, "hema": 2, "huolong": 3, "douban": 4}

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
            # 命中缓存也补一次外部 id：旧缓存的 detail dict 里没有 douban_id /
            # tmdb_id 键（回填机制晚于这些缓存写入），fill 后键会写回**同一个
            # dict 对象**（TTLCache 存的是引用），后续命中不再重复搜索。
            try:
                await self._fill_douban_id(cached)
                await self._fill_tmdb_id(cached)
            except Exception as err:  # pragma: no cover - 补 id 失败不影响详情
                logger.warning(f"{constants.SOURCE_NAME} 命中缓存补外部 id 失败 {target}：{err}")
            return cached

        if self._cache and self._cache.is_negative(target):
            return None

        if entity == constants.DOUBAN_WORK:
            return await self._load_douban(target)
        return await self._load_baike(target)

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
        # 负缓存用**独立前缀**：作品链路（``_load_baike``）曾把人标记成"取不到详情"，
        # 若共用 key，人物档案会被那条无关的负缓存永久挡住（实测踩过）。
        negative_key = f"person:{target}"
        if self._cache:
            cached = self._cache.get_person(target)
            if cached:
                # 旧缓存（融合功能上线前写入）没有 douban_id 键 → 就地补一次融合，
                # 结果写回缓存；已有键的直接返回（含「绑不上」的情形，TTL 内不重试）。
                if "douban_id" not in cached:
                    try:
                        cached = await self._fuse_douban_person(cached)
                        self._cache.set_person(target, cached)
                    except Exception as err:  # pragma: no cover - 补融合失败不影响档案
                        logger.warning(f"{constants.SOURCE_NAME} 缓存人物补融合失败 {target}：{err}")
                return cached
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

        if self._cache:
            self._cache.set_person(target, person)
        self._register(target, person.get("name", ""))
        # 人物页的作品卡自带日期/集数/演员/标签 → 顺带把这一页的剧都登记进 ID 库
        self._harvest(html)
        return person

    # ── ①' 豆瓣影人融合（人物档案用） ────────────────────────────────
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
        # ① 库里已有绑定
        self_row = self._store.get(media_id=str(person.get("media_id") or "")) or {}
        bound = str(self_row.get("douban") or "")
        if bound.startswith(f"{constants.DOUBAN_PERSON}:"):
            pid = bound.partition(":")[2]
            dperson = await douban.person_detail(pid)
        # ② 搜索消歧
        if dperson is None:
            best_score = 0
            for cand in (await douban.person_search(name))[:4]:
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
                names = {str(w.get("name") or "") for w in cd.get("works") or []}
                score = (
                    len(sids & set(known)) * 10
                    + len(names & {str(w.get("name") or "") for w in works})
                )
                if score > best_score:
                    best_score, pid, dperson = score, cand_pid, cd
            if best_score <= 0 or dperson is None:
                # 绑不上：不打标记，档案原样返回（缓存里也如实如此，TTL 内不重试）
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
        person["douban_id"] = f"{constants.DOUBAN_PERSON}:{pid}"
        person["douban_info"] = [
            f"{key}：{value}" for key, value in (dperson.get("info") or {}).items()
        ]
        return person

    async def _load_douban(self, media_id: str) -> Optional[dict]:
        """豆瓣剧集详情：``tv_detail`` → 写缓存 → 自映射入库。"""
        detail = await douban.tv_detail(native_id_of(media_id))
        if not detail:
            if self._cache:
                self._cache.mark_negative(media_id)
            return None
        if self._cache:
            self._cache.set_detail(media_id, detail)
        self._register(media_id, detail.get("name", ""))
        # 豆瓣条目的 ``douban`` 列是**自映射**：``douban:{sid}`` 即它自己
        try:
            self._store.set_external_ids(media_id=media_id, douban=media_id)
        except Exception as err:  # pragma: no cover - 回填失败不影响主流程
            logger.error(f"{constants.SOURCE_NAME} 回填豆瓣 id 失败 {media_id}：{err}")
        return detail

    async def _fill_douban_id(self, detail: dict) -> None:
        """按「名称完全相等 + 年份一致」回填豆瓣 id（站点页面不提供）。

        实测（2026-10-21）：短剧百科的详情页**没有**任何 douban / tmdb 字样，
        所以这两个 id 只能外部补：

        * **豆瓣**：``tv_search`` 能按名搜到（「移巢」→ 38456682、「以爱为家」→ 38393056），
          所以这里补 ``detail["douban_id"]``（纯数字 sid）并写入 ``baike.douban`` 映射；
        * **TMDB**：站点无来源 → 由 ``_fill_tmdb_id`` 经宿主 TMDB 通道补
          （实测「以爱为家」→ 317820、「移巢」→ 333508）。

        判据故意严格：名称去空白后完全相等，且两边都有年份时必须相同 —— 写错 id
        比没有更糟（会导致关联到另一部片）。搜索走 ``djbaike.douban`` 缓存 3 天，
        同一部片只查一次；**真搜到结果但没匹配上**才写 ``douban_id=""`` 占位，
        避免缓存命中路径重复搜索；搜索报错 / 空结果不占位（留待重试）。
        """
        media_id = str(detail.get("media_id") or "")
        name = str(detail.get("name") or "").strip()
        if not media_id or not name or "douban_id" in detail:
            return

        cache_key = f"search:{name}"
        items = self._cache.douban.get(cache_key) if self._cache else None
        if not isinstance(items, list):
            items = await douban.tv_search(name, 10)
            if self._cache and items:
                self._cache.douban.set(cache_key, items)

        year = str(detail.get("year") or "").strip()[:4]
        for item in items or []:
            if not isinstance(item, dict):
                continue
            if str(item.get("name") or "").strip() != name:
                continue
            item_year = str(item.get("year") or "").strip()[:4]
            if year and item_year and year != item_year:
                continue
            sid = str(item.get("media_id") or "").rsplit(":", 1)[-1]
            if not sid.isdigit():
                continue
            detail["douban_id"] = sid
            try:
                self._store.set_external_ids(
                    media_id=media_id, douban=f"{constants.DOUBAN_WORK}:{sid}"
                )
            except Exception as err:  # pragma: no cover - 回填映射失败不影响详情
                logger.error(f"{constants.SOURCE_NAME} 回填豆瓣 id 失败 {media_id}：{err}")
            return

        # 只有**真搜到东西但没匹配上**才落空串占位（防缓存命中重复搜索）；
        # 搜索本身报错 / 被限流 / 空结果时什么都不写 —— 下一轮还能重试
        # （实测 2026-10-21：豆瓣搜索过频返回 code=103，空手占位会把
        #   「雪落时逢你 → 38121380」这类本可回填的 id 永久空置）。
        if items:
            detail["douban_id"] = ""

    async def _fill_tmdb_id(self, detail: dict) -> None:
        """经宿主 TMDB 通道回填 ``tmdb`` 列（站点页面不提供）。

        判据比豆瓣更严：**必须带年份**（``async_search_tvs`` 按年过滤，同名
        不同年的误配风险靠它压住），名字完全相等 + 年份一致才写库。搜过没
        匹配上的写 ``tmdb_id=""`` 占位，避免缓存命中路径重复搜索。
        """
        media_id = str(detail.get("media_id") or "")
        name = str(detail.get("name") or "").strip()
        year = str(detail.get("year") or "").strip()[:4]
        if not media_id or not name or not year or "tmdb_id" in detail:
            return

        cache_key = f"tmdb:{name}:{year}"
        items = self._cache.douban.get(cache_key) if self._cache else None
        if not isinstance(items, list):
            items = await tmdb.tv_search(name, year)
            if self._cache and items:
                self._cache.douban.set(cache_key, items)

        for item in items or []:
            if not isinstance(item, dict):
                continue
            if str(item.get("name") or "").strip() != name:
                continue
            item_year = str(item.get("year") or "").strip()[:4]
            if year and item_year and year != item_year:
                continue
            tmid = str(item.get("id") or "").strip()
            if not tmid.isdigit():
                continue
            detail["tmdb_id"] = tmid
            try:
                self._store.set_external_ids(media_id=media_id, tmdb=tmid)
            except Exception as err:  # pragma: no cover - 回填映射失败不影响详情
                logger.error(f"{constants.SOURCE_NAME} 回填 TMDB id 失败 {media_id}：{err}")
            return

        # 走到这说明搜过但没匹配上：只有真搜到东西才空串占位；
        # 搜索报错 / 空结果不占位，留待重试（与豆瓣回填同一纪律）
        if items:
            detail["tmdb_id"] = ""

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

        detail = parse_detail(media_id, html) if (is_drama(media_id) or is_novel(media_id)) else None
        if not detail:
            # 人物页不归这里管（走 get_person），**不能**标负缓存：那会把人物档案
            # 一起废掉（两者共用 media_id 当 key 时尤其致命，见 get_person 注释）
            if not is_person(media_id) and self._cache:
                self._cache.mark_negative(media_id)
            self._harvest(html)
            return None

        # 站点页面不给豆瓣 / TMDB id → 按名+年份补一次（查不到就不填，绝不猜）
        try:
            await self._fill_douban_id(detail)
            await self._fill_tmdb_id(detail)
        except Exception as err:  # pragma: no cover - 补 id 失败不影响详情
            logger.warning(f"{constants.SOURCE_NAME} 补外部 id 失败 {media_id}：{err}")

        if self._cache:
            self._cache.set_detail(media_id, detail)
        self._register(media_id, detail.get("name", ""))
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
            site_rows = await self._site_search(candidate, pages=pages)
            if site_rows:
                keyword = candidate
                break
        merged: list[dict] = []
        seen: set[str] = set()
        for row in list(local) + list(site_rows):
            media_id = str(row.get("media_id") or "")
            if not media_id or media_id in seen:
                continue
            seen.add(media_id)
            merged.append(row)
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

    async def _site_search(self, keyword: str, *, pages: int = 1) -> list[dict]:
        """站内 ``/so.html``：先查缓存，未命中抓取并**全量登记**本页候选。"""
        cache_key = f"search:{keyword}"
        if self._cache:
            cached = self._cache.search.get(cache_key)
            if isinstance(cached, list):
                return cached
            if self._cache.is_negative(cache_key):
                return []

        rows: list[dict] = []
        seen: set[str] = set()
        for page in range(1, max(1, int(pages or 1)) + 1):
            cards = await search.search_cards(keyword, page, fetcher=self._fetcher)
            if not cards:
                break
            for entity, native_id, name in cards:
                media_id = f"{entity}:{native_id}"
                if media_id in seen:
                    continue
                seen.add(media_id)
                rows.append({"media_id": media_id, "name": name})
            if len(cards) < search.PAGE_SIZE:
                break

        if not rows:
            if self._cache:
                self._cache.mark_negative(cache_key)
            return []
        # 全量登记（不只选中的那一条）——搜索页/目录页都是索引生长入口
        try:
            self._store.upsert_many(rows=[(row["media_id"], row["name"]) for row in rows])
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
        """
        candidates = await self.find_candidates(name, remote=remote, pages=pages, merge_remote=True)
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
                    "kind": constants.KIND_OF_ENTITY.get(entity_of(media_id), ""),
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

    def _register(self, media_id: str, name: str) -> None:
        """把当前条目本身写进 ``baike``（存在即忽略，不覆盖旧名字）。"""
        try:
            self._store.upsert_many(rows=[(media_id, name)])
        except Exception as err:  # pragma: no cover
            logger.error(f"{constants.SOURCE_NAME} 登记 {media_id} 失败：{err}")

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
