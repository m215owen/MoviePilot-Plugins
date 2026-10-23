"""整理历史读写 —— 统一走宿主 ``TransferHistoryOper``。

设计要点（2026-10-22 重写，落实用户两条指令）：

* **整理完全不走系统的方式**：文件搬运由插件自己做，**不**调 ``TransferChain`` /
  ``manual_transfer``，也不进宿主整理队列。
* **整理历史读写改走 ``TransferHistoryOper``**：去重与落盘记录统一走宿主
  ``app.db.oper.transferhistory.TransferHistoryOper``，不再自持有 ``save_data``
  记录表。系统整理历史是「哪些文件已整理」的唯一真源，宿主的转移历史页面 /
  媒体库去重也以它为准。

所有方法都在 ``except`` 中吞掉异常并降级（历史查不到不等于整理失败），保证整理主流程
不被历史子系统拖垮。
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any, Optional

from .constants import BAIKE_MEDIA_SOURCE, CATEGORY_SHORT_DRAMA, MEDIA_TYPE_TV
from .serialize import jsonable, safe_int, safe_str


def _make_fileitem(path: Path) -> dict:
    """构造文件信息 JSON（与系统 transferhistory 格式一致）。"""
    stat = path.stat() if path.exists() else None
    return {
        "path": str(path),
        "storage": "local",
        "type": "file",
        "name": path.name,
        "basename": path.stem,
        "extension": path.suffix.lstrip("."),
        "size": stat.st_size if stat else 0,
        "modify_time": stat.st_mtime if stat else 0,
        "children": [],
        "fileid": None,
        "parent_fileid": None,
        "thumbnail": None,
        "pickcode": None,
        "drive_id": None,
        "url": None,
    }


def _resolve_media_identity(drama_info: dict) -> tuple[str, str]:
    """解析媒体主身份（media_source + media_id 成对）。

    V3 把通用媒体主身份收敛为这一对字段，两者必须同时有效
    （空串 / ``0`` / 半套身份都视为无身份），否则不写入。
    """
    source = drama_info.get("media_source")
    if hasattr(source, "value"):
        source = source.value
    source = safe_str(source)
    media_id = safe_str(drama_info.get("media_id"))
    if not source or not media_id or media_id == "0":
        return "", ""
    return source, media_id


def is_transferred(src_path: str) -> bool:
    """该源文件是否已在系统整理历史中存在成功记录（去重用）。"""
    try:
        from app.db.oper.transferhistory import TransferHistoryOper

        return TransferHistoryOper().get_success_by_src(src_path) is not None
    except Exception as err:  # pragma: no cover - 历史不可用不应阻断整理
        import logging

        logging.getLogger("ShortDramaBaikeOrganizer").warning(
            f"[历史] 查询整理历史失败，视为未整理：{err}"
        )
        return False


def has_transferred_dest(dest_dir: str) -> bool:
    """目标剧目录下是否已有整理历史记录（不论谁写的）。

    面板「已整理 / 未刮削」统计用：命中的可能是宿主内置短剧处理器写的记录
    （2026-10-23 撕夜实测：库里的 74 条软链就是它建的），所以只按 **dest 目录
    边界**匹配，不看 media_source。
    """
    if not dest_dir:
        return False
    try:
        boundary = os.path.normcase(os.path.normpath(str(dest_dir).rstrip("/\\"))) + os.sep
        # text 过滤是字面包含：用剧目录名缩小候选集，再按目录边界精确比对
        text = os.path.basename(os.path.normpath(str(dest_dir)))
        for record in _iter_records(text=text, limit=500):
            dest = getattr(record, "dest", "") or ""
            if dest and os.path.normcase(os.path.normpath(dest)).startswith(boundary):
                return True
        return False
    except Exception as err:  # pragma: no cover
        import logging

        logging.getLogger("ShortDramaBaikeOrganizer").warning(
            f"[历史] 查询目标目录整理记录失败，视为未整理：{err}"
        )
        return False


def count_distinct_episodes(dest_dir: str) -> int:
    """目标剧目录下**已整理的不同集数**（按 (seasons, episodes) 去重，只算成功记录）。

    面板记录行「已整理 X / Y 集」的 X：谁写的都算（含宿主内置短剧处理器），
    目录边界口径与 :func:`has_transferred_dest` / :func:`list_records_by_dest` 一致。
    """
    if not dest_dir:
        return 0
    try:
        boundary = os.path.normcase(os.path.normpath(str(dest_dir).rstrip("/\\"))) + os.sep
        # text 过滤是字面包含：用剧目录名缩小候选集，再按目录边界精确比对
        text = os.path.basename(os.path.normpath(str(dest_dir)))
        seen: set[tuple[str, str]] = set()
        for rec in _iter_records(text=text, limit=500):
            if not getattr(rec, "status", True):
                continue
            dest = getattr(rec, "dest", "") or ""
            if not dest or not os.path.normcase(os.path.normpath(dest)).startswith(boundary):
                continue
            episodes = getattr(rec, "episodes", "") or ""
            if episodes:
                seen.add((getattr(rec, "seasons", "") or "", episodes))
        return len(seen)
    except Exception as err:  # pragma: no cover
        import logging

        logging.getLogger("ShortDramaBaikeOrganizer").warning(
            f"[历史] 统计已整理集数失败，视为 0：{err}"
        )
        return 0


def record_transfer(
    src_path: str,
    dest_path: str,
    *,
    mode: str,
    title: str,
    year: Optional[int],
    season: int,
    episode: int,
    drama_info: dict,
    category: str = CATEGORY_SHORT_DRAMA,
) -> bool:
    """写入一条系统整理历史（成功）。

    :param drama_info: 识别得到的候选 dict（含 media_source / media_id 等）
    :param mode: move / copy / link / softlink
    :param season / episode: 当前集的季/集号（用于 seasons/episodes 列）
    """
    try:
        from app.db.oper.transferhistory import TransferHistoryOper

        src = Path(src_path)
        dest = Path(dest_path)
        seasons = f"S{max(1, int(season or 1)):02d}"
        episodes = f"E{max(1, int(episode or 1)):02d}"

        media_source, media_id = _resolve_media_identity(drama_info)
        # 识别源是短剧百科；若候选本身带了更具体的 media_source 也采用
        if not media_source:
            media_source = BAIKE_MEDIA_SOURCE

        payload: dict[str, Any] = {
            "src": src_path,
            "src_storage": "local",
            "src_fileitem": jsonable(_make_fileitem(src)),
            "dest": dest_path,
            "dest_storage": "local",
            "dest_fileitem": jsonable(_make_fileitem(dest)),
            "mode": mode or "move",
            "type": MEDIA_TYPE_TV,
            "category": category,
            "title": title,
            "year": "" if year is None else str(int(year)),
            "seasons": seasons,
            "episodes": episodes,
            "image": safe_str(drama_info.get("_poster_url")) or "",
            "status": True,
        }
        if media_source:
            payload["media_source"] = media_source
        if media_id:
            payload["media_id"] = media_id

        TransferHistoryOper().add(**payload)
        return True
    except Exception as err:  # pragma: no cover - 写入失败只记日志
        import logging

        logging.getLogger("ShortDramaBaikeOrganizer").error(f"[历史] 写入整理历史失败：{err}")
        return False


def delete_by_src(src_path: str) -> bool:
    """删除系统整理历史中指定 src 的记录（强制重整理前清旧记录用）。"""
    try:
        from app.db.oper.transferhistory import TransferHistoryOper

        oper = TransferHistoryOper()
        record = oper.get_by_src(src_path)
        if record is not None:
            oper.delete(record.id)
            return True
    except Exception as err:  # pragma: no cover
        import logging

        logging.getLogger("ShortDramaBaikeOrganizer").error(f"[历史] 删除整理记录失败：{err}")
    return False


def delete_by_title(title: str, library_dir: str, category: str = CATEGORY_SHORT_DRAMA) -> int:
    """按「媒体库/短剧/标题」目录边界匹配 dest 删除整理历史（同步删除时清记录用）。

    V3 筛选合同只支持 dest 精确匹配，所以先用 text 字面包含缩小候选集，再在本地按
    目录边界比对，避免标题子串误伤（如「走火」匹配到「走火炮」）。
    """
    if not title:
        return 0
    try:
        from app.db.oper.transferhistory import TransferHistoryOper

        series_dir = title.strip()
        if library_dir:
            boundary = os.path.join(str(library_dir).rstrip("/\\"), category, series_dir)
        else:
            boundary = os.path.join(os.sep, category, series_dir)
        boundary = os.path.normcase(os.path.normpath(boundary)) + os.sep

        oper = TransferHistoryOper()
        deleted = 0
        # text 过滤复用 TransferHistoryFilter（title/src/dest 字面包含）
        for record in _iter_records(text=series_dir):
            dest = getattr(record, "dest", "") or ""
            if not dest:
                continue
            if os.path.normcase(os.path.normpath(dest)).startswith(boundary):
                oper.delete(record.id)
                deleted += 1
        return deleted
    except Exception as err:  # pragma: no cover
        import logging

        logging.getLogger("ShortDramaBaikeOrganizer").error(f"[历史] 按标题删除记录失败：{err}")
    return 0


def _to_dict(rec: Any) -> dict:
    """整理历史 ORM 对象 → 面板可直接渲染的 dict。

    额外解出 ``src_name`` / ``dest_name``：前端「整理详情」按集号排序展示
    「源文件名 → 目标文件名」，不想让前端自己再切一次路径（跨平台分隔符）。
    """
    src = getattr(rec, "src", "") or ""
    dest = getattr(rec, "dest", "") or ""
    return {
        "id": getattr(rec, "id", None),
        "title": getattr(rec, "title", "") or "",
        "year": getattr(rec, "year", "") or "",
        "src": src,
        "src_name": _basename(src),
        "dest": dest,
        "dest_name": _basename(dest),
        "mode": getattr(rec, "mode", "") or "",
        "seasons": getattr(rec, "seasons", "") or "",
        "episodes": getattr(rec, "episodes", "") or "",
        "media_source": getattr(rec, "media_source", "") or "",
        "media_id": getattr(rec, "media_id", "") or "",
        "status": bool(getattr(rec, "status", True)),
        "date": str(getattr(rec, "date", "") or ""),
    }


def _basename(path: str) -> str:
    """跨平台取路径最后一段（历史里的路径可能是容器内的 POSIX 路径）。"""
    if not path:
        return ""
    return str(path).replace("\\", "/").rstrip("/").rsplit("/", 1)[-1]


def list_records(*, title: Optional[str] = None, limit: int = 200) -> list[dict]:
    """读取本插件写入的系统整理历史（media_source=djbaike），返回精简 dict 列表。

    用于面板展示与排障；按 id 倒序。
    """
    try:
        records = _iter_records(media_source=BAIKE_MEDIA_SOURCE, title=title, limit=limit)
        out = [_to_dict(rec) for rec in records]
        out.sort(key=lambda r: r.get("id") or 0, reverse=True)
        return out[:limit]
    except Exception as err:  # pragma: no cover
        import logging

        logging.getLogger("ShortDramaBaikeOrganizer").error(f"[历史] 读取记录失败：{err}")
        return []


def list_records_by_dest(dest_dir: str, limit: int = 500) -> list[dict]:
    """按**目标剧目录边界**取整理记录（谁写的都算）。

    面板「整理详情」用：同一部剧的历史可能一部分是本插件写的、另一部分是宿主内置
    短剧处理器写的（2026-10-23 实测），所以这里**不看 media_source**，只按
    ``dest`` 目录前缀筛 —— 与 :func:`has_transferred_dest` 口径一致。

    返回按集号（SxxExx）升序，前端直接按集序展示。
    """
    if not dest_dir:
        return []
    try:
        boundary = os.path.normcase(os.path.normpath(str(dest_dir).rstrip("/\\"))) + os.sep
        # text 过滤是字面包含：用剧目录名缩小候选集，再按目录边界精确比对
        text = os.path.basename(os.path.normpath(str(dest_dir)))
        out: list[dict] = []
        for rec in _iter_records(text=text, limit=limit):
            dest = getattr(rec, "dest", "") or ""
            if dest and os.path.normcase(os.path.normpath(dest)).startswith(boundary):
                out.append(_to_dict(rec))
        # 集号字符串（S01 / E018）按字典序即自然序，同集再用 id 兜底
        out.sort(key=lambda r: (r.get("seasons") or "", r.get("episodes") or "", r.get("id") or 0))
        return out
    except Exception as err:  # pragma: no cover
        import logging

        logging.getLogger("ShortDramaBaikeOrganizer").error(f"[历史] 读取目录记录失败：{err}")
        return []


def _iter_records(
    *,
    media_source: Optional[str] = None,
    title: Optional[str] = None,
    text: Optional[str] = None,
    limit: int = 200,
) -> list[Any]:
    """按 V3 只读查询合同分页读取整理历史，翻完全部页。"""
    from app.db.oper.transferhistory import TransferHistoryOper
    from app.schemas.query import QueryPageRequest, TransferHistoryFilter

    oper = TransferHistoryOper()
    # ⚠️ 契约字段是**非空 tuple**（``tuple[MediaSource, ...] = ()``），传 ``None``
    # 会直接 pydantic 校验失败（tuple_type）。这里是坑：只筛 text 的调用（比如
    # 按目标目录取记录）曾经传 ``media_sources=None`` → 查询整段抛异常 → 被上层
    # 吞掉 → 「已整理」统计恒为 0（2026-10-23 实测）。所以**只放非空条件**，
    # 不放 None，让缺省值 () 生效。
    kwargs: dict[str, Any] = {}
    if media_source:
        kwargs["media_sources"] = (media_source,)
    if title:
        kwargs["title"] = title
    if text:
        kwargs["text"] = text
    condition = TransferHistoryFilter(**kwargs)
    page, count = 1, 200
    records: list[Any] = []
    while True:
        batch, total = oper.query(condition, QueryPageRequest(page=page, count=count))
        if not batch:
            break
        records.extend(batch)
        if page * count >= total or len(records) >= limit:
            break
        page += 1
    return records
