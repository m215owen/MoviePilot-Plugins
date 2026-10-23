"""短剧百科整理 · 记录库（插件自有数据库）。

**为什么另起一张表**（2026-10-23，落实用户「数据要入库做记录」）：

系统整理历史（``TransferHistoryOper``）只记「哪个文件搬成功了」，面板要的
「已识别 / 已整理 / 未识别 / 未刮削」四类统计与「目标目录 / 刮削状态」这些
**扫描期的知识**它一概不存 —— 重启后面板就只剩光秃秃的历史列表，每次都得重扫。
所以把每次扫描的成果按「一部剧一行」落进插件自有库：

* 表建在宿主**插件自有数据库**（``app.sdk.database.plugin_declarative_base``），
  与宿主表互不干扰；宿主缺该 SDK 时整库降级为不可用（功能退化为纯内存态，
  绝不影响扫描 / 整理主流程）；
* 一行一部剧，键是源目录 ``path``（同一目录重复扫描即更新，不堆行）；
* 只存**事实**（身份、目标目录、是否存在、是否刮削、是否已整理），不存解析结论；
* 每个操作各开一个短事务、不跨调用持有会话（插件会在 HTTP / 调度 / 前端三类
  线程里被调用）。
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from sqlalchemy import Integer, String, UniqueConstraint, delete, select
from sqlalchemy.orm import Mapped, Session, mapped_column

try:  # 宿主 V3 稳定 SDK；缺失时整库降级
    from app.sdk.database import plugin_declarative_base
except Exception:  # pragma: no cover - 只有缺 SDK 的老宿主会走到
    plugin_declarative_base = None  # type: ignore[assignment]

__all__ = ["DramaRecord", "RecordStore", "store_available"]


# 独立 MetaData：不与宿主 Base 抢注册表，也允许别的插件定义同名表。
# 插件热重载会重新执行本模块、重新调用工厂，因此每次都拿到干净的注册表。
PluginBase = plugin_declarative_base() if plugin_declarative_base is not None else None


def store_available() -> bool:
    """宿主是否具备建立插件自有表的能力（决定记录库是否可用）。"""
    return DramaRecord is not None


if PluginBase is not None:

    class DramaRecord(PluginBase):
        """一条「一部剧」的记录（扫描期知识 + 整理/刮削进展）。"""

        __tablename__ = "drama_record"

        id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
        # 源目录（一部剧一个目录，同一路径重复扫描走更新）
        path: Mapped[str] = mapped_column(String(512), nullable=False)
        # 目录名（展示用）
        drama: Mapped[str] = mapped_column(String(255), nullable=False, default="")
        # 识别状态：recognized / unrecognized
        state: Mapped[str] = mapped_column(String(32), nullable=False, default="unrecognized")
        # 百科身份（识别成功才有）
        media_id: Mapped[str] = mapped_column(String(64), nullable=False, default="")
        title: Mapped[str] = mapped_column(String(255), nullable=False, default="")
        year: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
        # 目标目录（库目录/剧名 (年)）；未识别时为空
        dest_dir: Mapped[str] = mapped_column(String(512), nullable=False, default="")
        # 目标目录当前是否存在（扫描时探测）
        dest_exists: Mapped[bool] = mapped_column(Integer, nullable=False, default=0)
        # 目标是否已刮削（有 nfo / 海报）
        scraped: Mapped[bool] = mapped_column(Integer, nullable=False, default=0)
        # 是否已整理（系统整理历史里该剧目录下有成功记录）
        transferred: Mapped[bool] = mapped_column(Integer, nullable=False, default=0)
        # 整理成功的文件数（最近一次）
        done_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
        # 剧的总集数（百科词条的集数；识别/整理时写入，老行为 0）
        episode_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
        # 已整理的不同集数（按 SxxEyy 去重，来自系统整理历史）
        organized_episodes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
        # 手动标记整理完成（2026-10-23：整理中的剧可人工敲定为完成，扫描时跳过）
        completed: Mapped[bool] = mapped_column(Integer, nullable=False, default=0)
        # 身份是人工指定的（2026-10-23：重扫识别失败时不许被降级成「未识别」）
        manual: Mapped[bool] = mapped_column(Integer, nullable=False, default=0)
        # 识别/整理失败等原因（展示用）
        reason: Mapped[str] = mapped_column(String(255), nullable=False, default="")
        created_at: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
        updated_at: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

        __table_args__ = (
            UniqueConstraint("path", name="uq_drama_record_path"),
        )

        def as_dict(self) -> Dict[str, Any]:
            """纯 JSON 形态（接口输出用）。"""
            return {
                "id": self.id,
                "drama": self.drama,
                "path": self.path,
                "state": self.state,
                "media_id": self.media_id,
                "title": self.title,
                "year": self.year or None,
                "dest_dir": self.dest_dir,
                "dest_exists": bool(self.dest_exists),
                "scraped": bool(self.scraped),
                "transferred": bool(self.transferred),
                "done_count": self.done_count,
                "episode_count": self.episode_count,
                "organized_episodes": self.organized_episodes,
                "completed": bool(self.completed),
                "manual": bool(self.manual),
                # 整理完成 = 手动标记过，或已整理集数与数据源集数对齐（都 >0）
                "done": bool(self.completed)
                or (
                    self.episode_count > 0
                    and self.organized_episodes >= self.episode_count
                ),
                "reason": self.reason,
                "updated_at": self.updated_at,
            }

else:  # pragma: no cover - 只有缺少 app.sdk.database 的宿主会走到
    DramaRecord = None  # type: ignore[assignment]


class RecordStore:
    """记录库读写门面。

    一个实例持有一个插件数据库句柄（宿主 ``_PluginBase.get_database()``），
    每次操作各开一个短事务，不跨调用持有会话。
    """

    def __init__(self, handle: Any) -> None:
        self._handle = handle
        # 老库补列只跑一次（失败也会重试，见 _ensure_columns）
        self._columns_ready = False

    # 后加列（2026-10-23「集数显示」）：宿主建表走 create_all，只建不补，
    # 已存在的 drama_record 表上不会自动出现，必须自己 ALTER TABLE 补上。
    _MIGRATE_COLUMNS: tuple[tuple[str, str], ...] = (
        ("episode_count", "INTEGER NOT NULL DEFAULT 0"),
        ("organized_episodes", "INTEGER NOT NULL DEFAULT 0"),
        ("completed", "INTEGER NOT NULL DEFAULT 0"),
        ("manual", "INTEGER NOT NULL DEFAULT 0"),
    )

    def _session(self) -> Session:
        self._ensure_columns()
        return self._handle.session()

    def _ensure_columns(self) -> None:
        """给老库补新增列（幂等：列已存在时 ALTER 报错被忽略）。

        只在首次会话前跑；任何失败都不抛（补不上时后续读写会报列错误，
        那也只影响展示字段，不拖垮扫描 / 整理主流程）。
        """
        if self._columns_ready:
            return
        self._columns_ready = True
        try:
            from sqlalchemy import text

            session = self._handle.session()
            try:
                bind = session.get_bind()
                for name, ddl in self._MIGRATE_COLUMNS:
                    try:
                        with bind.begin() as conn:
                            conn.execute(
                                text(f"ALTER TABLE drama_record ADD COLUMN {name} {ddl}")
                            )
                    except Exception:
                        # 列已存在（SQLite "duplicate column name" / PG "already exists"）
                        pass
            finally:
                session.close()
        except Exception:
            # 会话都拿不到（宿主缺 SDK 等）：记录库本来就不可用，无所谓
            pass

    # ── 写 ────────────────────────────────────────────────────────

    def upsert(self, item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """按 ``path`` 插入或更新一条剧记录，返回落库后的 dict。

        ``item`` 需要的键：``path`` / ``drama`` / ``state``；其余可选
        （``media_id`` / ``title`` / ``year`` / ``dest_dir`` / ``dest_exists`` /
        ``scraped`` / ``transferred`` / ``reason``）。传入才覆盖，不传保持原值
        （整理、刮削等增量更新靠这个语义）。
        """
        path = str(item.get("path") or "").strip()
        if not path or DramaRecord is None:
            return None
        now = int(time.time())
        session = self._session()
        try:
            row = session.execute(
                select(DramaRecord).where(DramaRecord.path == path)
            ).scalars().first()
            if row is None:
                row = DramaRecord(
                    path=path,
                    drama=str(item.get("drama") or ""),
                    state=str(item.get("state") or "unrecognized"),
                    media_id=str(item.get("media_id") or ""),
                    title=str(item.get("title") or ""),
                    year=int(item.get("year") or 0),
                    dest_dir=str(item.get("dest_dir") or ""),
                    dest_exists=1 if item.get("dest_exists") else 0,
                    scraped=1 if item.get("scraped") else 0,
                    transferred=1 if item.get("transferred") else 0,
                    done_count=int(item.get("done_count") or 0),
                    episode_count=int(item.get("episode_count") or 0),
                    organized_episodes=int(item.get("organized_episodes") or 0),
                    completed=1 if item.get("completed") else 0,
                    manual=1 if item.get("manual") else 0,
                    reason=str(item.get("reason") or ""),
                    created_at=now,
                    updated_at=now,
                )
                session.add(row)
            else:
                row.drama = str(item.get("drama") or row.drama)
                row.state = str(item.get("state") or row.state)
                if item.get("media_id"):
                    row.media_id = str(item.get("media_id") or "")
                if item.get("title"):
                    row.title = str(item.get("title") or "")
                if item.get("year"):
                    row.year = int(item.get("year") or 0)
                if item.get("dest_dir"):
                    row.dest_dir = str(item.get("dest_dir") or "")
                if "dest_exists" in item:
                    row.dest_exists = 1 if item.get("dest_exists") else 0
                if "scraped" in item:
                    row.scraped = 1 if item.get("scraped") else 0
                if "transferred" in item:
                    row.transferred = 1 if item.get("transferred") else 0
                if "done_count" in item:
                    row.done_count = int(item.get("done_count") or 0)
                if item.get("episode_count"):
                    row.episode_count = int(item.get("episode_count") or 0)
                if item.get("organized_episodes"):
                    row.organized_episodes = int(item.get("organized_episodes") or 0)
                if "completed" in item:
                    row.completed = 1 if item.get("completed") else 0
                # 只增不减：人工指定的身份一旦落下，后续扫描不许把它抹掉
                if item.get("manual"):
                    row.manual = 1
                if "reason" in item:
                    row.reason = str(item.get("reason") or "")
                row.updated_at = now
            session.commit()
            session.refresh(row)
            return row.as_dict()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def mark_scraped(self, path: str) -> bool:
        """标记一条记录的目标目录已刮削。"""
        return self._update_flag(path, "scraped", 1)

    def mark_completed(self, path: str, value: bool = True) -> bool:
        """手动标记 / 取消「整理完成」（顺带把 transferred 敲成 1，口径一致）。"""
        if not path or DramaRecord is None:
            return False
        now = int(time.time())
        session = self._session()
        try:
            row = session.execute(
                select(DramaRecord).where(DramaRecord.path == path)
            ).scalars().first()
            if row is None:
                return False
            row.completed = 1 if value else 0
            if value:
                row.transferred = 1
            row.updated_at = now
            session.commit()
            return True
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def done_paths(self) -> set:
        """全部「整理完成」的源目录 path 集合（扫描跳过用）。

        口径与 ``as_dict`` 的 ``done`` 一致：手动标记过，或已整理集数
        对齐数据源集数。
        """
        if DramaRecord is None:
            return set()
        session = self._session()
        try:
            rows = list(session.execute(select(DramaRecord)).scalars().all())
        finally:
            session.close()
        return {
            row.path
            for row in rows
            if row.completed
            or (row.episode_count > 0 and row.organized_episodes >= row.episode_count)
        }

    def mark_organized(self, path: str, dest_dir: str = "", done_count: int = 0) -> bool:
        """整理成功后更新：已整理、目标目录、文件数。"""
        if not path or DramaRecord is None:
            return False
        now = int(time.time())
        session = self._session()
        try:
            row = session.execute(
                select(DramaRecord).where(DramaRecord.path == path)
            ).scalars().first()
            if row is None:
                return False
            row.transferred = 1
            row.state = "recognized"
            if dest_dir:
                row.dest_dir = dest_dir
                row.dest_exists = 1
            if done_count:
                row.done_count = int(done_count)
            row.updated_at = now
            session.commit()
            return True
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def delete(self, path: str) -> bool:
        """按源目录删一条记录。"""
        if not path or DramaRecord is None:
            return False
        session = self._session()
        try:
            result = session.execute(
                delete(DramaRecord).where(DramaRecord.path == path)
            )
            session.commit()
            return bool(result.rowcount)
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def clear(self) -> int:
        """清空全部记录（面板「清空记录」用）。"""
        if DramaRecord is None:
            return 0
        session = self._session()
        try:
            result = session.execute(delete(DramaRecord))
            session.commit()
            return int(result.rowcount or 0)
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    # ── 读 ────────────────────────────────────────────────────────

    def all(self, limit: int = 500) -> List[Dict[str, Any]]:
        """全部记录（更新时间倒序），转成 JSON 友好 dict。"""
        if DramaRecord is None:
            return []
        session = self._session()
        try:
            rows = list(
                session.execute(
                    select(DramaRecord).order_by(DramaRecord.updated_at.desc())
                ).scalars().all()
            )
        finally:
            session.close()
        return [row.as_dict() for row in rows[: max(1, limit)]]

    def stats(self) -> Dict[str, int]:
        """面板四类统计：已识别 / 已整理 / 未识别 / 未刮削。

        「未刮削」只数**目标目录已存在但没刮削**的（不存在说明还没整理，不计）。
        """
        empty = {"recognized": 0, "transferred": 0, "unrecognized": 0, "unscraped": 0}
        if DramaRecord is None:
            return empty
        session = self._session()
        try:
            rows = list(session.execute(select(DramaRecord)).scalars().all())
        finally:
            session.close()
        stats = dict(empty)
        for row in rows:
            if row.state == "recognized":
                stats["recognized"] += 1
            else:
                stats["unrecognized"] += 1
            if row.transferred:
                stats["transferred"] += 1
            if row.dest_exists and not row.scraped:
                stats["unscraped"] += 1
        return stats

    # ── 内部 ──────────────────────────────────────────────────────

    def _update_flag(self, path: str, field: str, value: int) -> bool:
        if not path or DramaRecord is None:
            return False
        now = int(time.time())
        session = self._session()
        try:
            row = session.execute(
                select(DramaRecord).where(DramaRecord.path == path)
            ).scalars().first()
            if row is None:
                return False
            setattr(row, field, value)
            row.updated_at = now
            session.commit()
            return True
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
