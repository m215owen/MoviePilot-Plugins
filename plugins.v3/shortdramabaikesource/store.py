"""短剧百科数据源 · URL 库（插件自有数据库）。

**库里只存 URL**，不存解析结果：实测 ddgs 每行就是 ``title`` / ``href`` / ``body``，
``href`` 即详情页或演员页的完整地址；把「关键词 → URL」存下来，下次同名关键词就
不必再打搜索引擎（引擎有 3 秒最小间隔、召回还不稳定）。页面内容照旧由插件实时抓取
解析 —— 站点随时在更新，缓存解析结果只会让数据过期。

两个字段的分工要分清（这是库里能不能**按名字查回来**的关键）：
``keyword`` 是**这条记录自己的名字**（作品＝片名，演员＝演员名），``display`` 是
**把它带出来的那个搜索词**。演员往往是搜一部剧时「顺带」发现的 —— 要是把片名当
演员的键，按演员名就查不到它，同一个人还会因为两条路径各写一遍而重复占行。

**一个页面只留一条记录**：``add()`` 与 :meth:`UrlStore.dedupe` 都会把同一个
``(kind, native_id)`` 的多条合并成一条（见 :meth:`UrlStore._keeper_rank`）。

表建在宿主的**插件自有数据库**里（``app.sdk.database.plugin_declarative_base``）：
SQLite 下是 ``<插件数据目录>/plugin.db``，PostgreSQL 下是宿主库里的独立 schema，
建表由宿主在插件启动时按 ``get_database_models()`` 的声明完成，本模块只读写。
"""
from __future__ import annotations

import time
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from sqlalchemy import Index, Integer, String, UniqueConstraint, delete, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.sdk.database import plugin_declarative_base
from app.sdk.logging import logger

from .constants import EXACT_TITLE_SCORE, MAX_URLS_PER_KEYWORD, PLUGIN_NAME
from .parser import _clean, _match_title, _normalize_title, canonical_page_url

__all__ = ["PluginBase", "SiteUrl", "UrlStore"]


# 独立 MetaData：既不与宿主 ``Base`` 抢注册表，也允许别的插件定义同名表。
# 插件热重载会重新执行本模块、重新调用工厂，因此每次都拿到干净的注册表。
PluginBase = plugin_declarative_base()


class SiteUrl(PluginBase):
    """一条「页面」记录。

    ``kind`` 只有两种：``work``（作品详情页）与 ``actor``（演员页）。同一个关键词可以
    有多条记录（多季、同名不同剧、重名演员），因此唯一键是 (kind, keyword, url)；
    而同一个**页面**（同一个 ``native_id``）只留一条，见 :meth:`UrlStore.add`。
    """

    __tablename__ = "site_url"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    # 这条记录**自己的名字**（作品＝片名；演员＝演员名），归一化写法，见 parser.normalize_title
    keyword: Mapped[str] = mapped_column(String(255), nullable=False)
    # 把它带出来的**搜索词**原文（可能是片名，也可能是当时搜的那部剧）
    display: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    # 页面标题（已剥掉站点后缀）
    label: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    url: Mapped[str] = mapped_column(String(512), nullable=False)
    # 站点 ID（作品 ID / 演员 ID），从 URL 路径取出
    native_id: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    # 发现渠道：search（搜索引擎）/ page（从页面里的链接顺带发现）
    origin: Mapped[str] = mapped_column(String(16), nullable=False, default="search")
    # 搜索引擎后端（origin=search 时有值）
    backend: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    hits: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    first_seen_at: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_used_at: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    __table_args__ = (
        UniqueConstraint("kind", "keyword", "url", name="uq_site_url_kind_keyword_url"),
        Index("ix_site_url_kind_keyword", "kind", "keyword"),
        Index("ix_site_url_kind_native", "kind", "native_id"),
    )

    def as_dict(self) -> Dict[str, Any]:
        """纯 JSON 形态（接口输出用）。"""
        return {
            "kind": self.kind,
            "keyword": self.keyword,
            "display": self.display,
            "label": self.label,
            "url": self.url,
            "native_id": self.native_id,
            "origin": self.origin,
            "backend": self.backend,
            "hits": self.hits,
            "first_seen_at": self.first_seen_at,
            "last_used_at": self.last_used_at,
        }


class UrlStore:
    """URL 库的读写门面。

    一个实例持有一个插件数据库句柄（宿主 ``_PluginBase.get_database()``），
    每次操作各开一个短事务，不跨调用持有会话 —— 插件会在 HTTP、调度与
    前端请求三类线程里被调用。
    """

    def __init__(self, handle: Any) -> None:
        self._handle = handle

    # ── 基础 ──────────────────────────────────────────────────────

    def _session(self) -> Session:
        return self._handle.session()

    # ── 写 ────────────────────────────────────────────────────────

    def add(self, entries: Iterable[Dict[str, Any]]) -> int:
        """批量入库（幂等 + 同页面自动合并）。返回**新增**条数。

        两级去重：

        1. 同 ``(kind, keyword, url)`` 只留一条：已存在时刷新 ``label`` / ``display`` /
           ``native_id`` / ``backend``，不清零 ``hits``。
        2. 同 ``(kind, native_id)``（**同一个页面**）只留一条：合并规则见
           :meth:`_keeper_rank`，被并掉那条的 ``hits`` 累加到留下的记录上。

        :param entries: 每项含 ``kind`` / ``keyword`` / ``url``，可选 ``display`` /
            ``label`` / ``native_id`` / ``origin`` / ``backend``
        """
        rows = [dict(row) for row in entries if row.get("url") and row.get("keyword")]
        if not rows:
            return 0
        now = int(time.time())
        added = 0
        pages: List[Tuple[str, str]] = []
        session = self._session()
        try:
            for row in rows:
                kind = str(row.get("kind") or "work")
                keyword = str(row["keyword"])
                url = str(row["url"])
                native_id = str(row.get("native_id") or "")
                if native_id:
                    pages.append((kind, native_id))
                existing = session.execute(
                    select(SiteUrl).where(
                        SiteUrl.kind == kind,
                        SiteUrl.keyword == keyword,
                        SiteUrl.url == url,
                    )
                ).scalars().first()
                if existing is None:
                    session.add(
                        SiteUrl(
                            kind=kind,
                            keyword=keyword,
                            display=str(row.get("display") or ""),
                            label=str(row.get("label") or ""),
                            url=url,
                            native_id=native_id,
                            origin=str(row.get("origin") or "search"),
                            backend=str(row.get("backend") or ""),
                            hits=0,
                            first_seen_at=now,
                            last_used_at=0,
                        )
                    )
                    added += 1
                else:
                    if row.get("label"):
                        existing.label = str(row["label"])
                    if row.get("display"):
                        existing.display = str(row["display"])
                    if row.get("native_id"):
                        existing.native_id = str(row["native_id"])
                    if row.get("backend"):
                        existing.backend = str(row["backend"])
            session.flush()  # 让新插入的行拿到 id，合并阶段才看得到它们
            merged = self._consolidate(session, pages)
            trimmed = self._trim(session, rows)
            session.commit()
        finally:
            session.close()
        if merged or trimmed:
            logger.debug(
                f"{PLUGIN_NAME} URL 库入库整理：合并同页面 {merged} 条"
                + (f"、超出上限清理 {trimmed} 条" if trimmed else "")
            )
        return added

    # ── 去重（同一个页面只留一条） ─────────────────────────────────

    @staticmethod
    def _keeper_rank(row: SiteUrl) -> Tuple[int, int, int, int]:
        """同页面多条记录里谁更该留下（排序键，越小越优先）。

        * **演员**优先留「按自己的名字建档」的那条（``keyword == label``）—— 演员页的
          URL 只有按名字才查得回来：搜片名时顺带发现的演员行原先挂在片名下，按演员名
          查不到，还会跟页面顺带写的那条重复。
        * **作品**优先留「引擎发现」的那条 —— 它的 ``keyword`` 就是用户当时搜的那个词，
          下一次搜索用的正是同一个词；页面顺带写的那条键是页面标题，用户多半不会那样搜。
        """
        named = bool(row.label) and _normalize_title(row.label) == (row.keyword or "")
        if row.kind == "actor":
            primary = 0 if named else 1
        else:
            primary = 0 if row.origin == "search" else 1
        return (primary, -(row.hits or 0), row.first_seen_at or 0, row.id or 0)

    @staticmethod
    def _page_rows(session: Session, kind: str, native_id: str) -> List[SiteUrl]:
        return list(
            session.execute(
                select(SiteUrl).where(SiteUrl.kind == kind, SiteUrl.native_id == native_id)
            ).scalars().all()
        )

    @classmethod
    def _consolidate(cls, session: Session, pages: Iterable[Tuple[str, str]]) -> int:
        """把同一个 ``(kind, native_id)`` 的多条记录并成一条，返回被并掉的条数。"""
        removed = 0
        for kind, native_id in dict.fromkeys((k, n) for k, n in pages if n):
            records = cls._page_rows(session, kind, native_id)
            if len(records) < 2:
                continue
            keeper = min(records, key=cls._keeper_rank)
            losers = [row for row in records if row.id != keeper.id]
            # ⚠️ 先立即删掉落选行再改留下的那条：两者可能撞上 (kind, keyword, url) 唯一键
            session.execute(delete(SiteUrl).where(SiteUrl.id.in_([row.id for row in losers])))
            for row in losers:
                keeper.hits = (keeper.hits or 0) + (row.hits or 0)
                keeper.last_used_at = max(keeper.last_used_at or 0, row.last_used_at or 0)
                seen = [value for value in (keeper.first_seen_at, row.first_seen_at) if value]
                keeper.first_seen_at = min(seen) if seen else 0
                if not keeper.label and row.label:
                    keeper.label = row.label
                if not keeper.display and row.display:
                    keeper.display = row.display
                if not keeper.backend and row.backend:
                    keeper.backend = row.backend
            # 语言前缀顺手归一化：早期版本把引擎给的无前缀 / 繁体地址原样存了下来
            keeper.url = canonical_page_url(keeper.url) or keeper.url
            removed += len(losers)
        return removed

    def dedupe(self) -> int:
        """整库去重：同一个页面只留一条。返回被合并掉的条数。

        插件启动时跑一次（见 ``init_plugin``），把历史遗留的重复行清掉 —— 需要一个页面
        一条记录，面板上一行就是一站剧，用户才数得清库里到底有什么。
        """
        session = self._session()
        try:
            pages = [
                (row.kind, row.native_id)
                for row in session.execute(select(SiteUrl)).scalars().all()
                if row.native_id
            ]
            removed = self._consolidate(session, pages)
            if removed:
                session.commit()
                logger.info(f"{PLUGIN_NAME} URL 库整库去重：合并同页面 {removed} 条")
            return removed
        finally:
            session.close()

    def prune_mismatched(self) -> int:
        """删掉「片名与键**不完全相等**」的作品行，返回删除条数。

        v2.0.0 曾把搜索引擎返回的作品**一律按搜索词**建档；而引擎召回不稳 —— 实测搜
        「相亲对象是迟来的心动」返回的是「深渊之花」「照片是舍友，網戀對象是繼承人」等
        五部毫不相干的剧 ⇒ 库里攒下一批「键是这个搜索词、内容却是别的剧」的错行，
        日志报「库命中 5」，其实一条都对不上。

        v2.1.1 起入库时就只收**完全匹配**的（见 ``ShortDramaBaikeSource._discover``），
        这里负责清理**已经存下来**的那些：作品行的片名与它的键、与触发它的搜索词
        都不相等，就说明这条是张冠李戴。幂等，可反复执行。

        ⚠️ 只动 ``work`` 行：演员行按自己的名字建档，不存在这种错行。
        """
        session = self._session()
        try:
            stale = [
                row
                for row in session.execute(
                    select(SiteUrl).where(SiteUrl.kind == "work")
                ).scalars().all()
                if _clean(row.label)
                and _match_title(row.label, row.keyword or "") < EXACT_TITLE_SCORE
                and _match_title(row.label, row.display or "") < EXACT_TITLE_SCORE
            ]
            if not stale:
                return 0
            session.execute(delete(SiteUrl).where(SiteUrl.id.in_([row.id for row in stale])))
            session.commit()
            return len(stale)
        finally:
            session.close()

    @staticmethod
    def _trim(session: Session, rows: Sequence[Dict[str, Any]]) -> int:
        """把每个关键词的记录数收到上限内（保留命中次数高的），返回删掉的条数。

        站点上一部剧可能有十几季，一一入库会把库撑成垃圾场；``MAX_URLS_PER_KEYWORD``
        之外的低频记录直接不留 —— 需要时再搜一次就会重新发现。
        """
        removed = 0
        keys = {(str(row.get("kind") or "work"), str(row["keyword"])) for row in rows}
        for kind, keyword in keys:
            records = list(
                session.execute(
                    select(SiteUrl)
                    .where(SiteUrl.kind == kind, SiteUrl.keyword == keyword)
                    .order_by(SiteUrl.hits.desc(), SiteUrl.first_seen_at.asc())
                ).scalars().all()
            )
            for extra in records[MAX_URLS_PER_KEYWORD:]:
                session.delete(extra)
                removed += 1
        return removed

    def touch(self, ids: Sequence[int]) -> None:
        """把用过的记录命中数 +1 并刷新使用时间。"""
        if not ids:
            return
        now = int(time.time())
        session = self._session()
        try:
            for record in session.execute(
                select(SiteUrl).where(SiteUrl.id.in_(list(ids)))
            ).scalars().all():
                record.hits = (record.hits or 0) + 1
                record.last_used_at = now
            session.commit()
        finally:
            session.close()

    def forget(self, kind: str = "", keyword: str = "") -> int:
        """删除记录：只给 ``kind`` 删该类全部，两个都给则精确到一个关键词。"""
        session = self._session()
        try:
            statement = delete(SiteUrl)
            if kind:
                statement = statement.where(SiteUrl.kind == kind)
            if keyword:
                statement = statement.where(SiteUrl.keyword == keyword)
            removed = session.execute(statement).rowcount or 0
            session.commit()
            return int(removed)
        finally:
            session.close()

    # ── 读 ────────────────────────────────────────────────────────

    def lookup(self, kind: str, keyword: str) -> List[SiteUrl]:
        """按 (类型, 关键词) 取 URL，命中次数高的在前。"""
        session = self._session()
        try:
            return list(
                session.execute(
                    select(SiteUrl)
                    .where(SiteUrl.kind == kind, SiteUrl.keyword == keyword)
                    .order_by(SiteUrl.hits.desc(), SiteUrl.first_seen_at.asc())
                ).scalars().all()
            )
        finally:
            session.close()

    def match(self, kind: str, keyword: str) -> List[SiteUrl]:
        """按关键词取记录：``keyword`` / ``label`` / ``display`` 任一命中即算。

        比 :meth:`lookup` 宽松是**故意的** —— 一个页面只留一条记录，那一条的键到底落在
        片名、演员名还是当时的搜索词上，取决于它先被哪条路径发现；三个字段都认，库里
        存着的 URL 才真的能用上（否则「库优先、零引擎请求」会因为键不对而失效）。
        多出来的候选由上层按片名/姓名打分筛，不会污染结果。

        库容量在几百条量级（一个页面一条），所以这里整类取回内存里比。关键词已归一化。
        """
        if not keyword:
            return []
        session = self._session()
        try:
            records = list(
                session.execute(select(SiteUrl).where(SiteUrl.kind == kind)).scalars().all()
            )
        finally:
            session.close()
        hits = [
            row
            for row in records
            if keyword in (row.keyword, _normalize_title(row.label), _normalize_title(row.display))
        ]
        # 显式带上 id：命中次数与入库时间常常并列，不能让数据库的返回顺序（走索引时是按
        # ID 字符串排的）决定候选顺序
        hits.sort(key=lambda row: (-(row.hits or 0), row.first_seen_at or 0, row.id or 0))
        return hits

    def by_native_id(self, kind: str, native_id: str) -> Optional[SiteUrl]:
        """按站点 ID 取一条记录（``recognize_media(media_id="org:45982")`` 用）。"""
        if not native_id:
            return None
        session = self._session()
        try:
            return session.execute(
                select(SiteUrl)
                .where(SiteUrl.kind == kind, SiteUrl.native_id == str(native_id))
                .order_by(SiteUrl.hits.desc(), SiteUrl.first_seen_at.asc())
            ).scalars().first()
        finally:
            session.close()

    def by_keywords(self, kind: str, keywords: Sequence[str]) -> List[SiteUrl]:
        """一次取回多个关键词的记录（面板/自检里的批量查询）。"""
        keys = [key for key in keywords if key]
        if not keys:
            return []
        session = self._session()
        try:
            return list(
                session.execute(
                    select(SiteUrl)
                    .where(SiteUrl.kind == kind, SiteUrl.keyword.in_(keys))
                    .order_by(SiteUrl.hits.desc(), SiteUrl.first_seen_at.asc())
                ).scalars().all()
            )
        finally:
            session.close()

    def count(self) -> Dict[str, Any]:
        """库容量统计：按类型计数 + 关键词数 + 最近写入时间。"""
        session = self._session()
        try:
            records = list(session.execute(select(SiteUrl)).scalars().all())
        finally:
            session.close()
        works = sum(1 for row in records if row.kind == "work")
        actors = sum(1 for row in records if row.kind == "actor")
        return {
            "total": len(records),
            "work": works,
            "actor": actors,
            "keywords": len({(row.kind, row.keyword) for row in records}),
            "last_seen_at": max((row.first_seen_at or 0 for row in records), default=0),
        }

    def recent(self, limit: int = 50, kind: str = "") -> List[Dict[str, Any]]:
        """最近入库的记录（面板/接口展示用）。"""
        session = self._session()
        try:
            statement = select(SiteUrl).order_by(SiteUrl.first_seen_at.desc())
            if kind:
                statement = statement.where(SiteUrl.kind == kind)
            records = list(session.execute(statement.limit(max(1, limit))).scalars().all())
        finally:
            session.close()
        return [row.as_dict() for row in records]
