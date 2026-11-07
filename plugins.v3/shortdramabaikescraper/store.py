"""``baike``（站点注册表）+ ``baike_ext``（外部 id 表）的仓储层。

纪律（计划 §3 / §4）：

* 查询结果在会话释放前**物化成 dict**，绝不把 ORM 原文带出装饰器。
* 站点行（``baike``）只存站点自己的东西；豆瓣 / TMDB 属作品级属性，只存
  ``baike_ext`` **一份**（2026-11-04 用户口径「外部 id 单独记录，不在站点单独记录」），
  读取时**按名字**现挂到行 dict 上，上层拿到的字典形状不变。
* 入库用「存在即忽略」，绝不用新名字覆盖旧名字（同名跨类型合法，先到先得）。
* 不在此层做名字归一化或模糊匹配打分——``WHERE name = ?`` 原样匹配。
"""

from __future__ import annotations

import logging
from typing import Iterable, Optional

from sqlalchemy import delete as sa_delete
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import db_query, db_update

from . import constants
from .models import Baike, BaikeExt
from .models import ensure_table as _ensure_table

logger = logging.getLogger(__name__)

# 外部 id 的两个来源分类 → 表里的列（`store.ext_page(source=...)` 用）。
# 面板把它们当两个独立分类看：豆瓣 id / TMDB id 各自分页、各自计数。
SOURCE_COLUMNS = {
    "douban": BaikeExt.douban,
    "tmdb": BaikeExt.tmdb,
}


def tmdb_composite(value: str) -> str:
    """TMDB 值统一成**复合 id**：作品 ``tmdb:{id}``、影人 ``tmdbp:{pid}``。

    2026-11-04 用户口径「豆瓣和 tmdb 的 id 也可以作为复合 id」：库里两个外部 id
    都带种类前缀（豆瓣本来就是 ``douban:`` / ``doubanp:``），面板一眼能看出是
    作品还是人物，也不会与裸数字混淆。已带前缀的值原样返回，空值仍空。
    """
    text = str(value or "").strip()
    if not text or ":" in text:
        return text
    return f"{constants.TMDB_WORK}:{text}"


def tmdb_number(value: str) -> str:
    """把 ``tmdb:{id}`` / 裸数字还原成**裸 TMDB 数字**（出网取详情、详情字段用）。"""
    text = str(value or "").strip()
    prefix, _, rest = text.partition(":")
    if prefix == constants.TMDB_WORK and rest:
        return rest
    return text


def _is_work(media_id: str) -> bool:
    """``media_id`` 是不是作品行（作品 / 人物共用一张表，靠前缀区分）。"""
    prefix = str(media_id or "").partition(":")[0]
    return prefix not in constants.ENTITY_PERSON


def _intrinsic_douban(media_id: str) -> str:
    """``douban:`` / ``doubanp:`` 行的豆瓣 id 就是它自己，不用查表。

    这类行是「从豆瓣条目反向登记进来的」，media_id 本身就是复合豆瓣 id；
    把它们也塞进 ``baike_ext`` 只会制造重复，还会让同名但不同条目的两部作品
    抢同一条外部记录（实测库里 4 组同名豆瓣作品就是这种情况）。
    """
    text = str(media_id or "")
    prefix = text.partition(":")[0]
    if prefix in (constants.DOUBAN_WORK, constants.DOUBAN_PERSON):
        return text
    return ""


def _value_fits(media_id: str, column: str, value: str) -> bool:
    """外部 id 的**种类**是否与该行相符（作品 id ↔ 作品行、影人 id ↔ 人物行）。

    前缀就是判据：``doubanp:`` / ``tmdbp:`` 恒为影人 id，其余为作品 id。
    历史脏数据（例如人物行误存了 ``douban:{sid}``）也不会被抄给同名的另一行。
    """
    text = str(value or "").strip()
    if not text:
        return False
    is_person_id = text.startswith(
        (f"{constants.DOUBAN_PERSON}:", f"{constants.TMDB_PERSON}:")
    )
    is_person_row = str(media_id or "").partition(":")[0] in constants.ENTITY_PERSON
    return is_person_id if is_person_row else not is_person_id


def _chunks(items: list, size: int = 200) -> Iterable[list]:
    for start in range(0, len(items), size):
        yield items[start : start + size]


class BaikeStore:
    """两张表的全部数据访问入口。"""

    @staticmethod
    def ensure_table() -> None:
        """建表 + 把老库的行内外部 id 搬进 ``baike_ext`` + 统一复合 id（幂等）。"""
        _ensure_table()
        BaikeStore._migrate_ext_columns()
        try:
            BaikeStore().normalize_ext_tmdb()
        except Exception as err:  # pragma: no cover - 归一化失败不挡启动
            logger.warning(f"[baike] TMDB 复合 id 归一化失败：{err}")

    @db_update
    def normalize_ext_tmdb(self, db: Optional[Session] = None) -> int:
        """把历史裸 TMDB id（``298016``）统一成复合 id（``tmdb:298016``）。

        2026-11-04 用户口径「豆瓣和 tmdb 的 id 也可以作为复合 id」：新写入由
        :func:`tmdb_composite` 保证，这里只补历史数据。幂等 —— 第二次跑改 0 行。
        """
        assert db is not None
        rows = (
            db.execute(
                select(BaikeExt).where(
                    BaikeExt.tmdb != "", ~BaikeExt.tmdb.contains(":")
                )
            )
            .scalars()
            .all()
        )
        for row in rows:
            row.tmdb = tmdb_composite(row.tmdb)
        if rows:
            db.flush()
            logger.info(f"[baike] TMDB id 统一为复合形式：{len(rows)} 条")
        return len(rows)

    @staticmethod
    def _migrate_ext_columns() -> dict[str, int]:
        """一次性搬家：``baike.douban/tmdb`` → ``baike_ext``，然后删掉这两列。

        2026-11-04 用户口径「外部 id 应该单独记录」：同一部剧在新老站各有一行，
        以前两行各存一份豆瓣 / TMDB（还要互相同步、只填空永不修正）；现在按
        「名字 + 种类」只存一份。迁移只跑一次（列删掉之后条件不成立）。
        """
        from sqlalchemy import inspect, text

        from app.db import Engine

        stats = {"douban": 0, "tmdb": 0, "dropped": 0}
        table = Baike.__tablename__
        ext_table = BaikeExt.__tablename__
        try:
            cols = {col["name"] for col in inspect(Engine).get_columns(table)}
            if not ({"douban", "tmdb"} & cols):
                return stats
            with Engine.begin() as conn:
                legacy = conn.execute(
                    text(
                        f"SELECT media_id, name, douban, tmdb FROM {table} "
                        "WHERE name <> '' AND (douban <> '' OR tmdb <> '')"
                    )
                ).all()
            groups: dict[str, dict[str, str]] = {}
            for media_id, name, douban, tmdb in legacy:
                key = str(name)
                slot = groups.setdefault(key, {"douban": "", "tmdb": "", "owner": media_id})
                douban_text = str(douban or "")
                # 自带豆瓣 id 的行（douban:/doubanp:）不写进外部表：读的时候现算
                if douban_text and not _intrinsic_douban(media_id):
                    slot["douban"] = slot["douban"] or douban_text
                tmdb_text = tmdb_composite(str(tmdb or ""))
                if tmdb_text:
                    slot["tmdb"] = slot["tmdb"] or tmdb_text
            with Engine.begin() as conn:
                for name, slot in groups.items():
                    if not (slot["douban"] or slot["tmdb"]):
                        continue
                    conn.execute(
                        text(
                            f"INSERT INTO {ext_table} (name, douban, tmdb, owner) "
                            "VALUES (:name, :douban, :tmdb, :owner) "
                            "ON CONFLICT (name) DO NOTHING"
                        ),
                        {"name": name, "owner": slot["owner"], **slot},
                    )
                    stats["douban"] += 1 if slot["douban"] else 0
                    stats["tmdb"] += 1 if slot["tmdb"] else 0
                for column in ("douban", "tmdb"):
                    if column in cols:
                        conn.execute(text(f"ALTER TABLE {table} DROP COLUMN {column}"))
                        stats["dropped"] += 1
            logger.info(
                f"[baike] 外部 id 已搬到 {ext_table}："
                f"豆瓣 {stats['douban']} 条｜TMDB {stats['tmdb']} 条"
                f"｜已删除 {stats['dropped']} 个旧列"
            )
        except Exception as err:  # pragma: no cover - 搬家失败不挡插件启动
            logger.error(f"[baike] 外部 id 搬家失败（下次启动再试）：{err}")
        return stats

    # ── 外部 id 表 ───────────────────────────────────────────────────
    @staticmethod
    def _ext_open(db: Session, name: str, owner: str = "") -> BaikeExt:
        """取（或建）一条外部 id 记录（主键就是名字）；调用方负责 flush。"""
        row = db.get(BaikeExt, name)
        if row is None:
            row = BaikeExt(name=name, douban="", tmdb="", owner=owner)
            db.add(row)
            db.flush()
        return row

    @staticmethod
    def _attach_ext(db: Session, rows: list[Baike]) -> list[dict]:
        """把外部 id **按名字**挂到站点行 dict 上（一次批量查，别逐行 get）。

        值的种类复核一次（``_value_fits``）：外部表不再分 work / person，
        同名撞车时也不能把剧集 sid 挂到演员行上。
        """
        out = [
            {
                "media_id": row.media_id,
                "name": row.name,
                "douban": "",
                "tmdb": "",
            }
            for row in rows
        ]
        keys = sorted({d["name"] for d in out if d["name"]})
        found: dict[str, BaikeExt] = {}
        for chunk in _chunks(keys):
            for ext in db.execute(
                select(BaikeExt).where(BaikeExt.name.in_(chunk))
            ).scalars():
                found[ext.name] = ext
        for item in out:
            ext = found.get(item["name"])
            douban = str(ext.douban or "") if ext else ""
            if douban and not _value_fits(item["media_id"], "douban", douban):
                douban = ""
            item["douban"] = douban or _intrinsic_douban(item["media_id"])
            tmdb = str(ext.tmdb or "") if ext else ""
            if tmdb and not _value_fits(item["media_id"], "tmdb", tmdb):
                tmdb = ""
            item["tmdb"] = tmdb
        return out

    @db_query
    def external_ids(self, db: Optional[Session] = None, *, name: str) -> dict:
        """**按名字**取外部 id（2026-11-04 用户口径）；没有这条记录就回空串。"""
        assert db is not None
        key = str(name or "").strip()
        if not key:
            return {"name": "", "douban": "", "tmdb": ""}
        ext = db.get(BaikeExt, key)
        return {
            "name": key,
            "douban": str(ext.douban or "") if ext else "",
            "tmdb": str(ext.tmdb or "") if ext else "",
        }

    # ── 写 ───────────────────────────────────────────────────────────
    @db_update
    def upsert_many(
        self,
        db: Optional[Session] = None,
        *,
        rows: Iterable[tuple[str, str]] = (),
    ) -> int:
        """批量登记 ``(media_id, name)``，已存在的行原样保留。

        返回真正新增的行数。外部 id 不在这一层写（它在 ``baike_ext``，等取详情 /
        批量补 id 时才落）。

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
        for chunk in _chunks(ids, 500):
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
    def mark_ai(self, db: Optional[Session] = None, *, media_ids: Iterable[str] = ()) -> int:
        """把**见过 AI / 漫剧标注**的行标成 ``is_ai=True``（只升不降）。

        为什么要落库：新站的「AI短剧」只体现在卡片标题行的角标上，详情页也有，
        但本地命中 / 面板列表读的是库里的行 —— 不落库，「排除」开关对新站条目
        在库里就判不出来（老站还能靠 ``manju`` / ``hema`` 前缀判）。
        只升不降：已经确认是 AI 剧的条目不会因为后来某次没带标注就回退。
        """
        assert db is not None
        ids = [m for m in {(mid or "").strip() for mid in media_ids} if m]
        if not ids:
            return 0
        changed = 0
        for chunk in _chunks(ids, 500):
            rows = (
                db.execute(
                    select(Baike).where(
                        Baike.media_id.in_(chunk), Baike.is_ai.is_(False)
                    )
                )
                .scalars()
                .all()
            )
            for row in rows:
                row.is_ai = True
                changed += 1
        if changed:
            db.flush()
        return changed

    @db_update
    def set_external_ids(
        self,
        db: Optional[Session] = None,
        *,
        media_id: str,
        douban: Optional[str] = None,
        tmdb: Optional[str] = None,
    ) -> bool:
        """把外部 id 写进 ``baike_ext``（按这一行的**名字 + 种类**定位）。

        只写空值：同一部作品已经绑过的不覆盖 —— 绑定本来就是严格判据匹配来的
        （作品看「名称完全相等 + 年份一致」，人物看「唯一精确同名 / 作品交集」），
        先写下的那份就是答案。``douban:`` / ``doubanp:`` 行的豆瓣 id 是它自己，
        不重复入库。

        返回该 ``media_id`` 是否存在（True = 记下 / 已记下），行不在或没名字时
        返回 False（没名字无法定位外部记录，硬写只会产生孤儿数据）。
        """
        assert db is not None
        mid = str(media_id or "").strip()
        row = db.get(Baike, mid) if mid else None
        if row is None:
            return False
        name = str(row.name or "").strip()
        if not name:
            return False
        written = False
        if douban and _value_fits(mid, "douban", douban):
            value = str(douban)
            if value != _intrinsic_douban(mid):
                ext = self._ext_open(db, name, mid)
                if not ext.douban:
                    ext.douban = value
                    written = True
        if tmdb and _value_fits(mid, "tmdb", tmdb):
            ext = self._ext_open(db, name, mid)
            # 统一成复合 id（`tmdb:{id}` / `tmdbp:{pid}`），裸数字会自动补前缀
            value_t = tmdb_composite(tmdb)
            if not ext.tmdb:
                ext.tmdb = value_t
                written = True
        if written:
            db.flush()
        return True

    @db_update
    def delete(self, db: Optional[Session] = None, *, media_id: str) -> bool:
        """删单条站点行；返回是否真的删掉了。

        外部 id 记录**不动**：它是作品级的（另一站那行还在用它）。
        """
        assert db is not None
        row = db.get(Baike, media_id)
        if row is None:
            return False
        db.delete(row)
        return True

    @db_update
    def clear(self, db: Optional[Session] = None) -> int:
        """清空**站点行**表，返回删除的行数（危险操作，调用方必须二次确认）。

        外部 id 表（``baike_ext``）**保留**（2026-11-04 用户口径「外部 id 单独
        记录」）：豆瓣 / TMDB 是独立于站点的资产，站点行清空后靠识别 / 检索
        重新生长时，同名行还能直接挂回已绑的 id，不用重新出网。
        """
        assert db is not None
        total = db.execute(select(func.count()).select_from(Baike)).scalar_one()
        db.execute(sa_delete(Baike))
        return int(total or 0)

    # ── 读 ───────────────────────────────────────────────────────────
    @db_query
    def get(self, db: Optional[Session] = None, *, media_id: str) -> Optional[dict]:
        """按 media_id 取一行（外部 id 已挂上）。"""
        assert db is not None
        row = db.get(Baike, media_id)
        if row is None:
            return None
        return self._attach_ext(db, [row])[0]

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
        return self._attach_ext(db, list(rows))

    @db_query
    def by_douban(
        self,
        db: Optional[Session] = None,
        *,
        douban: str,
        limit: int = 20,
    ) -> list[dict]:
        """按复合豆瓣 id 反查（``douban:{sid}`` / ``doubanp:{pid}``）。

        两个来源都算：本体行（``media_id`` 就是那个复合 id）+ 外部 id 表里绑到这个
        id 的同名站点行。
        """
        assert db is not None
        value = str(douban or "").strip()
        if not value:
            return []
        found: dict[str, Baike] = {}
        for row in db.execute(select(Baike).where(Baike.media_id == value)).scalars():
            found[row.media_id] = row
        for ext in db.execute(
            select(BaikeExt).where(BaikeExt.douban == value)
        ).scalars():
            rows = db.execute(select(Baike).where(Baike.name == ext.name)).scalars()
            for row in rows:
                if _value_fits(row.media_id, "douban", value):
                    found.setdefault(row.media_id, row)
        ordered = [found[key] for key in sorted(found)][: max(1, limit)]
        return self._attach_ext(db, ordered)

    @db_query
    def by_tmdb(
        self,
        db: Optional[Session] = None,
        *,
        tmdb: str,
        limit: int = 20,
    ) -> list[dict]:
        """按 tmdb id 反查（tmdb 是系列级，可能多条命中）。

        入参可以是复合 id（``tmdb:{id}``）也可以是裸数字；查库时两种形态都试
        —— 新数据存复合、旧数据是裸数字（2026-11-04 统一复合 id 后仍兼容）。
        """
        assert db is not None
        value = tmdb_number(str(tmdb or "").strip())
        if not value:
            return []
        candidates = [f"{constants.TMDB_WORK}:{value}", value]
        found: dict[str, Baike] = {}
        for ext in db.execute(
            select(BaikeExt).where(BaikeExt.tmdb.in_(candidates))
        ).scalars():
            rows = db.execute(select(Baike).where(Baike.name == ext.name)).scalars()
            for row in rows:
                if _value_fits(row.media_id, "tmdb", value):
                    found.setdefault(row.media_id, row)
        ordered = [found[key] for key in sorted(found)][: max(1, limit)]
        return self._attach_ext(db, ordered)

    @db_query
    def counts(self, db: Optional[Session] = None, *, exclude_manju: bool = False) -> dict:
        """按实体前缀计数 + 可检索条数（``name`` 非空）。

        ``exclude_manju`` 打开时漫剧类前缀（``manju`` / ``hema`` / ``huolong``）
        不计数 —— 与 :meth:`page` 同一口径，面板的 chip / 分布图才和列表对得上。
        """
        assert db is not None
        rows = db.execute(select(Baike.media_id, Baike.is_ai)).all()
        by_entity = {entity: 0 for entity in sorted(constants.ENTITY_ALL)}
        by_entity[constants.DOUBAN_WORK] = 0
        by_entity[constants.DOUBAN_PERSON] = 0
        skip = constants.MANJU_ENTITIES if exclude_manju else frozenset()
        total = 0
        for media_id, is_ai in rows:
            entity = media_id.partition(":")[0]
            if entity in skip or (exclude_manju and is_ai):
                continue
            total += 1
            if entity in by_entity:
                by_entity[entity] += 1
        search_stmt = select(func.count()).select_from(Baike).where(Baike.name != "")
        if exclude_manju:
            for prefix in sorted(constants.MANJU_ENTITIES):
                search_stmt = search_stmt.where(~Baike.media_id.like(f"{prefix}:%"))
            search_stmt = search_stmt.where(Baike.is_ai.is_(False))
        searchable = db.execute(search_stmt).scalar_one()
        # 外部 id 表的三项计数一次查完：总行数 + 各列非空行数
        # （面板把「豆瓣 id」「TMDB id」当两个独立分类，各自要显示条数）
        ext_douban, ext_tmdb, ext_total = db.execute(
            select(
                func.count(func.nullif(BaikeExt.douban, "")),
                func.count(func.nullif(BaikeExt.tmdb, "")),
                func.count(),
            ).select_from(BaikeExt)
        ).one()
        return {
            "total": total,
            "searchable": int(searchable or 0),
            "by_entity": by_entity,
            # 外部 id 表自己的计数（与站点行无关）：总记录数 / 有豆瓣 id / 有 TMDB id
            "ext_total": int(ext_total or 0),
            "ext_douban": int(ext_douban or 0),
            "ext_tmdb": int(ext_tmdb or 0),
        }

    @db_query
    def pending_external(
        self,
        db: Optional[Session] = None,
        *,
        entity: str = "",
        limit: int = 20,
        after: str = "",
    ) -> tuple[int, list[dict]]:
        """待补外部 id 的站点行：外部记录里豆瓣 / TMDB **任一为空**。

        2026-11-03 用户口径「豆瓣 / TMDB 一个都没补上」：回填原本只发生在
        **取详情**链路，而库里的行绝大多数是榜单 / 人物作品 / 顺带登记进来的，
        从没走过详情。

        为什么是「任一为空」而不是「两列全空」：豆瓣与 TMDB 是两条独立通道，
        豆瓣先补上之后如果按「两列全空」取货，那一行就再也不会被扫到、
        TMDB 永远补不上。已补的那一半由调用方传进 ``fill_external_ids`` 跳过。

        **同名同种类只出一行**（外部 id 按名字共享，两站各刷一遍就是白烧配额 ——
        这正是「外部 id 单独记录」要省掉的那一半）。``douban:`` 行的豆瓣 id 是它
        自己，只等 TMDB。

        ``after`` 是**游标**（上一批最后一条 media_id）：没有它会永远从最小的
        那几行开始，反复点也只补同一批。

        返回 ``(剩余待补总数, 本批行)``，按 ``media_id`` 排序。
        """
        assert db is not None
        prefix = f"{entity}:" if entity else ""
        ext_map = {
            ext.name: (str(ext.douban or ""), str(ext.tmdb or ""))
            for ext in db.execute(select(BaikeExt)).scalars().all()
        }
        seen: set[str] = set()
        picked: list[Baike] = []
        rows = db.execute(select(Baike).order_by(Baike.media_id)).scalars().all()
        for row in rows:
            mid = row.media_id
            if prefix and not mid.startswith(prefix):
                continue
            if not prefix and mid.startswith(f"{constants.DOUBAN_PERSON}:"):
                # 豆瓣影人本体没有可补的外部 id（豆瓣那列就是它自己，TMDB 侧又
                # 没有「百科作品」可做交集判定），留在队列里永远补不完
                continue
            name = str(row.name or "").strip()
            if not name:
                continue
            if after and mid <= after:
                continue
            key = name
            if key in seen:
                continue
            douban, tmdb = ext_map.get(key, ("", ""))
            if (douban or _intrinsic_douban(mid)) and tmdb:
                continue
            seen.add(key)
            picked.append(row)
        total = len(picked)
        return total, self._attach_ext(db, picked[: max(1, limit)])

    @db_query
    def works_with_douban(
        self,
        db: Optional[Session] = None,
        *,
        limit: int = 20,
        after: str = "",
    ) -> tuple[int, list[dict]]:
        """已绑豆瓣 sid 的**作品**（行里的 ``douban`` 是 ``douban:{sid}``），按 media_id 升序。

        用途（2026-11-03）：拿豆瓣**演职员表**反查人物的 ``doubanp`` id。
        豆瓣作品详情 ``tv_detail`` 的 ``actors`` **只有名字不带 id**，唯一带 id
        的入口是 ``/tv/{sid}/celebrities`` —— 所以必须先把「有 sid 的作品」筛出来。

        两个来源：``baike_ext`` 的 work 半边（同一部剧只有一条记录，按名字回到
        站点行取代表）+ 本体行（``media_id`` 就是 ``douban:{sid}``，豆瓣独有条目）。
        按 **sid** 去重：同一部剧两站共用一条外部记录，扫两遍就是白烧配额；
        不同 sid 的同名作品是两个豆瓣条目，都要扫。

        ``after`` 是作品 media_id 游标，语义同 :meth:`pending_external`：
        没有它每轮都从最小的那几部开始，反复点也只扫同一批。
        返回 ``(剩余作品总数, 本批行)``。
        """
        assert db is not None
        names = [
            ext.name
            for ext in db.execute(
                select(BaikeExt).where(
                    BaikeExt.douban.like(f"{constants.DOUBAN_WORK}:%")
                )
            )
            .scalars()
            .all()
        ]
        candidates: dict[str, Baike] = {}
        for row in db.execute(
            select(Baike).where(Baike.media_id.like(f"{constants.DOUBAN_WORK}:%"))
        ).scalars():
            candidates[row.media_id] = row
        for chunk in _chunks(sorted(names)):
            for row in db.execute(select(Baike).where(Baike.name.in_(chunk))).scalars():
                if not _is_work(row.media_id):
                    continue
                candidates.setdefault(row.media_id, row)
        if not candidates:
            return 0, []
        rows = self._attach_ext(db, list(candidates.values()))
        # 同一个 sid 只留一行（游标取最小的 media_id，保证续跑稳定）
        by_sid: dict[str, dict] = {}
        for item in rows:
            ref = str(item.get("douban") or "")
            if not ref.startswith(f"{constants.DOUBAN_WORK}:"):
                continue
            current = by_sid.get(ref)
            if current is None or item["media_id"] < current["media_id"]:
                by_sid[ref] = item
        ordered = sorted(by_sid.values(), key=lambda item: item["media_id"])
        remaining = [item for item in ordered if not after or item["media_id"] > after]
        return len(remaining), remaining[: max(1, limit)]

    @db_query
    def page(
        self,
        db: Optional[Session] = None,
        *,
        q: str = "",
        entity: str = "",
        offset: int = 0,
        limit: int = 50,
        exclude_manju: bool = False,
    ) -> tuple[int, list[dict]]:
        """站点库分页：只返回**站点自己的两列**（``media_id`` / ``name``）。

        外部 id（豆瓣 / TMDB）属 ``baike_ext``，不挂到站点行上 —— 面板把它们当
        两个分类分别看（2026-11-04 用户口径）。

        ``exclude_manju``（2026-11-04 用户口径）：排除开关打开时，面板里**看不到**
        漫剧类条目 —— 老站 ``manju`` / ``hema`` / ``huolong`` 三个前缀一律不返回、
        也不计入 ``total``。只做读过滤，**不删数据**：开关关掉后原样回来。
        """
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
        if exclude_manju:
            for prefix in sorted(constants.MANJU_ENTITIES):
                stmt = stmt.where(~Baike.media_id.like(f"{prefix}:%"))
                count_stmt = count_stmt.where(~Baike.media_id.like(f"{prefix}:%"))
            # 新站没有 manju 前缀，「AI短剧」只体现在卡片标注上 → 靠 is_ai 列
            stmt = stmt.where(Baike.is_ai.is_(False))
            count_stmt = count_stmt.where(Baike.is_ai.is_(False))
        total = int(db.execute(count_stmt).scalar_one() or 0)
        rows = (
            db.execute(stmt.order_by(Baike.media_id).offset(max(offset, 0)).limit(limit))
            .scalars()
            .all()
        )
        return total, [{"media_id": row.media_id, "name": row.name} for row in rows]

    @db_query
    def ext_page(
        self,
        db: Optional[Session] = None,
        *,
        q: str = "",
        offset: int = 0,
        limit: int = 50,
        source: str = "",
    ) -> tuple[int, list[dict]]:
        """外部 id 表分页：一行 = 名字 + 豆瓣 + TMDB。

        与站点库相互独立：这里一条记录对应一部作品 / 一个人，**不分站**，
        也不需要库里先有站点行（清空站点库后外部 id 仍在）。
        ``q`` 同时对名字 / 豆瓣 / TMDB 三列模糊。

        ``source``（2026-11-04 用户口径「外部 id 拆为 tmdb 和豆瓣分类」）：
        ``douban`` / ``tmdb`` 时只返回**那一列非空**的行，面板两个分类各自
        独立分页、独立计数；空串 = 全部。非法值按全部处理，不报错。
        """
        assert db is not None
        stmt = select(BaikeExt)
        count_stmt = select(func.count()).select_from(BaikeExt)
        column = SOURCE_COLUMNS.get((source or "").strip().lower())
        if column is not None:
            stmt = stmt.where(column != "")
            count_stmt = count_stmt.where(column != "")
        if q:
            like = f"%{q}%"
            cond = (
                BaikeExt.name.like(like)
                | BaikeExt.douban.like(like)
                | BaikeExt.tmdb.like(like)
            )
            stmt = stmt.where(cond)
            count_stmt = count_stmt.where(cond)
        total = int(db.execute(count_stmt).scalar_one() or 0)
        rows = (
            db.execute(
                stmt.order_by(BaikeExt.name).offset(max(offset, 0)).limit(limit)
            )
            .scalars()
            .all()
        )
        return total, [
            {
                "name": row.name,
                "douban": str(row.douban or ""),
                "tmdb": str(row.tmdb or ""),
            }
            for row in rows
        ]
