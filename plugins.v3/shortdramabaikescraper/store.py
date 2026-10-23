"""``baike`` 表的仓储层：只做「id ↔ 名字 / 外部 id」的读写与统计。

纪律（计划 §3 / §4）：

* 查询结果在会话释放前**物化成 dict**，绝不把 ORM 对象带出装饰器。
* 入库用「存在即忽略」，绝不用新名字覆盖旧名字（同名跨类型合法，先到先得）。
* 不在此层做名字归一化或模糊匹配打分——``WHERE name = ?`` 原样匹配。
"""

from __future__ import annotations

from typing import Iterable, Optional

from sqlalchemy import delete as sa_delete
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import db_query, db_update

from . import constants
from .models import Baike, ensure_table as _ensure_table


class BaikeStore:
    """``baike`` 表的全部数据访问入口。"""

    @staticmethod
    def ensure_table() -> None:
        """建表（``checkfirst=True``，只补缺失表，不改已有列）。"""
        _ensure_table()

    # ── 写 ───────────────────────────────────────────────────────────
    @db_update
    def upsert_many(
        self,
        db: Optional[Session] = None,
        *,
        rows: Iterable[tuple[str, str]] = (),
    ) -> int:
        """批量登记 ``(media_id, name)``，已存在的行原样保留。

        返回真正新增的行数。``douban`` / ``tmdb`` 两列保持空串，等取详情时回填。

        **名字为空的 id 一律不入库**（2026-10-21 用户要求）：这类行既不可检索
        （``/search``、按名识别全靠 ``name``），也不会被后续流程补上名字
        （``upsert`` 不覆盖已有行），属于纯死数据。抓页顺带登记时列表卡偶尔只有
        id 没名字，就地丢弃；等真正带名字的那次抓取再入。
        """
        assert db is not None
        pairs = [
            (mid, (name or "").strip())
            for mid, name in rows
            if mid and (name or "").strip()
        ]
        if not pairs:
            return 0
        # 同一批内去重，避免主键冲突
        unique: dict[str, str] = {}
        for mid, name in pairs:
            unique.setdefault(mid, name)

        ids = list(unique)
        existing: set[str] = set()
        # 分批查，避免超长 IN 列表
        for start in range(0, len(ids), 500):
            chunk = ids[start : start + 500]
            existing.update(
                db.execute(select(Baike.media_id).where(Baike.media_id.in_(chunk)))
                .scalars()
                .all()
            )

        new_rows = [
            Baike(media_id=mid, name=name)
            for mid, name in unique.items()
            if mid not in existing
        ]
        if not new_rows:
            return 0
        db.add_all(new_rows)
        db.flush()
        return len(new_rows)

    @db_update
    def set_external_ids(
        self,
        db: Optional[Session] = None,
        *,
        media_id: str,
        douban: Optional[str] = None,
        tmdb: Optional[str] = None,
    ) -> bool:
        """回填 ``douban`` / ``tmdb`` 两列（只在拿到值时才写，不覆盖已有非空值）。"""
        assert db is not None
        row = db.get(Baike, media_id)
        if row is None:
            return False
        if douban and not row.douban:
            row.douban = douban
        if tmdb and not row.tmdb:
            row.tmdb = str(tmdb)
        db.flush()
        return True

    @db_update
    def delete(self, db: Optional[Session] = None, *, media_id: str) -> bool:
        """删单条；返回是否真的删掉了。"""
        assert db is not None
        row = db.get(Baike, media_id)
        if row is None:
            return False
        db.delete(row)
        return True

    @db_update
    def clear(self, db: Optional[Session] = None) -> int:
        """清空整表，返回删除行数（危险操作，调用方必须二次确认）。"""
        assert db is not None
        total = db.execute(select(func.count()).select_from(Baike)).scalar_one()
        db.execute(sa_delete(Baike))
        return int(total or 0)

    # ── 读 ───────────────────────────────────────────────────────────
    @db_query
    def get(self, db: Optional[Session] = None, *, media_id: str) -> Optional[dict]:
        """按 media_id 取一行。"""
        assert db is not None
        row = db.get(Baike, media_id)
        return row.as_dict() if row else None

    @db_query
    def by_name(
        self,
        db: Optional[Session] = None,
        *,
        name: str,
        limit: int = 50,
    ) -> list[dict]:
        """按名精确匹配（原样，不做归一化）。同名跨类型时返回多行。"""
        assert db is not None
        if not name:
            return []
        rows = (
            db.execute(
                select(Baike).where(Baike.name == name).order_by(Baike.media_id).limit(limit)
            )
            .scalars()
            .all()
        )
        return [row.as_dict() for row in rows]

    @db_query
    def by_douban(
        self,
        db: Optional[Session] = None,
        *,
        douban: str,
        limit: int = 20,
    ) -> list[dict]:
        """按复合豆瓣 id 反查（``douban:{sid}`` / ``doubanp:{pid}``）。"""
        assert db is not None
        if not douban:
            return []
        rows = (
            db.execute(select(Baike).where(Baike.douban == douban).limit(limit))
            .scalars()
            .all()
        )
        return [row.as_dict() for row in rows]

    @db_query
    def by_tmdb(
        self,
        db: Optional[Session] = None,
        *,
        tmdb: str,
        limit: int = 20,
    ) -> list[dict]:
        """按 tmdb id 反查（tmdb 是系列级，可能多条命中）。"""
        assert db is not None
        if not tmdb:
            return []
        rows = (
            db.execute(select(Baike).where(Baike.tmdb == str(tmdb)).limit(limit))
            .scalars()
            .all()
        )
        return [row.as_dict() for row in rows]

    @db_query
    def counts(self, db: Optional[Session] = None) -> dict:
        """按实体前缀计数 + 可检索条数（``name`` 非空）。"""
        assert db is not None
        ids = db.execute(select(Baike.media_id)).scalars().all()
        by_entity = {entity: 0 for entity in sorted(constants.ENTITY_ALL)}
        by_entity[constants.DOUBAN_WORK] = 0
        by_entity[constants.DOUBAN_PERSON] = 0
        for media_id in ids:
            entity = media_id.partition(":")[0]
            if entity in by_entity:
                by_entity[entity] += 1
        searchable = db.execute(
            select(func.count()).select_from(Baike).where(Baike.name != "")
        ).scalar_one()
        return {
            "total": len(ids),
            "searchable": int(searchable or 0),
            "by_entity": by_entity,
        }

    @db_query
    def page(
        self,
        db: Optional[Session] = None,
        *,
        q: str = "",
        entity: str = "",
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[int, list[dict]]:
        """分页面板用：可选 ``q`` 模糊（media_id / name）与实体前缀过滤。"""
        assert db is not None
        stmt = select(Baike)
        count_stmt = select(func.count()).select_from(Baike)
        if q:
            like = f"%{q}%"
            cond = Baike.media_id.like(like) | Baike.name.like(like)
            stmt = stmt.where(cond)
            count_stmt = count_stmt.where(cond)
        if entity:
            prefix = f"{entity}:%"
            stmt = stmt.where(Baike.media_id.like(prefix))
            count_stmt = count_stmt.where(Baike.media_id.like(prefix))
        total = int(db.execute(count_stmt).scalar_one() or 0)
        rows = (
            db.execute(stmt.order_by(Baike.media_id).offset(max(offset, 0)).limit(limit))
            .scalars()
            .all()
        )
        return total, [row.as_dict() for row in rows]
