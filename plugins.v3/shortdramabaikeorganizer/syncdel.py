"""反向联动：Emby 删除媒体 → 级联清理（2026-10-24 用户口径）。

链路顺序固定（用户指定）：

    ① Emby 删除媒体（外部动作，本模块只接收 Webhook 事件）
    ② 删插件整理历史（记录库里的该剧记录）
    ③ 删 MP 整理历史（宿主 TransferHistory 的该剧全部行）
    ④ 取消短剧演员订阅里的**作品订阅**（按 media_id，跨插件事件）
    ⑤ 删种子（可选：删种子时同步删除媒体）

设计约束（均来自用户明确要求）：

- **触发只有 Emby Webhook 的媒体移除事件**（``library.deleted``），
  不做定时兜底扫描；
- **白名单是记录库**：只有本插件整理过（``transferred`` 为真）的短剧才会被
  处理，其余媒体一概忽略；
- Emby 删除事件的 payload 字段稀疏（ProviderIds 常为空，官方论坛实证），
  所以匹配只靠路径（``Item.Path`` ↔ ``dest_dir``）与剧名（``Item.Name`` ↔
  ``title``），命中后媒体身份直接取记录里的 ``media_id``，不做宿主身份解析；
- 每一步独立容错：某一步失败只记日志并计入结果，不阻塞后续步骤。
"""

from __future__ import annotations

import shutil
import threading
import time
from pathlib import Path
from typing import Any, Optional

from app.sdk.logging import logger
from app.schemas.types import EventType, NotificationType

from .constants import (
    ACTOR_UNSUB_ACTION,
    BAIKE_MEDIA_SOURCE,
    CONF_SYNCDEL_DELETE_MEDIA,
    CONF_SYNCDEL_DOWNLOADERS,
    CONF_SYNCDEL_ENABLED,
    CONF_SYNCDEL_EXCLUDE_PATH,
    CONF_SYNCDEL_LIBRARY_PATH,
    CONF_SYNCDEL_MP_HISTORY,
    SYNCDEL_EVENTS,
    SYNCDEL_MTYPE_TV,
)

#: Webhook 事件里会被当作「整剧删除」的条目类型；单集 / 单季删除不联动
_WHOLE_DRAMA_TYPES = ("Series", "Folder", "Movie", "BoxSet", "")


def _text(value: Any) -> str:
    """转字符串并去空白（None 给空串）。"""
    if value is None:
        return ""
    return str(value).strip()


def _field(data: Any, name: str, default: Any = None) -> Any:
    """从事件载荷取字段：优先属性（pydantic 模型），其次字典键。"""
    value = getattr(data, name, None)
    if value is None and isinstance(data, dict):
        value = data.get(name)
    return default if value is None else value


def _norm(path: Any) -> str:
    """路径归一：统一分隔符、去尾部斜杠（保留根斜杠）。"""
    text = _text(path).replace("\\", "/")
    if len(text) > 1:
        text = text.rstrip("/")
    return text


def _under(path: str, root: str) -> bool:
    """``path`` 是否等于 ``root`` 或位于其下。"""
    if not path or not root:
        return False
    return path == root or path.startswith(root + "/")


def _as_list(value: Any) -> list[str]:
    """把配置里的多选值归一成字符串列表（容忍换行串 / 列表 / 对象）。"""
    if isinstance(value, str):
        raw = [item for line in value.splitlines() for item in line.split(",")]
    elif isinstance(value, (list, tuple, set)):
        raw = list(value)
    else:
        raw = []
    result: list[str] = []
    for item in raw:
        if isinstance(item, dict):
            text = _text(item.get("value") or item.get("title"))
        else:
            text = _text(item)
        if text and text not in result:
            result.append(text)
    return result


class SyncDeleter:
    """Emby 删除事件 → 级联清理执行器（每插件一个实例）。"""

    def __init__(self, plugin: Any) -> None:
        self.plugin = plugin
        # 同一时刻只跑一条链路：删除动作涉及文件与下载器，串行更安全
        self._lock = threading.Lock()
        # 「自我清理抑制表」：本插件重新整理时删掉旧目录，Emby 会认为条目被删并
        # 发出 library.deleted；若不抑制，联动删除会把源文件和种子一起删掉
        # （2026-10-27 实测把《昼短夜长》整部剧删没了）。值为过期时间戳。
        self._suppress: dict[str, float] = {}
        self._suppress_ttl = 600.0

    # ── 自我清理抑制 ────────────────────────────────────────────────

    def suppress(self, *keys: str) -> None:
        """登记「本插件刚清理过的剧」：其删除事件在 TTL 内一律忽略。"""
        deadline = time.time() + self._suppress_ttl
        for key in keys:
            text = _norm(key)
            if text:
                self._suppress[text] = deadline

    def _is_suppressed(self, *keys: str) -> bool:
        """任一 key 命中抑制表（且未过期）即返回 True。"""
        now = time.time()
        for key in keys:
            text = _norm(key)
            if not text:
                continue
            deadline = self._suppress.get(text)
            if deadline and deadline > now:
                return True
        return False

    # ── 入口 ────────────────────────────────────────────────────────

    def on_webhook(self, event: Any) -> None:
        """Webhook 事件入口：只认媒体移除事件，重活转后台线程。"""
        if not bool(self.plugin._cfg(CONF_SYNCDEL_ENABLED, False)):
            return
        data = getattr(event, "event_data", None)
        if not data:
            return
        event_name = _text(_field(data, "event"))
        if event_name not in SYNCDEL_EVENTS:
            return
        threading.Thread(
            target=self._run_safe,
            args=(data,),
            daemon=True,
            name="SDBKO-SyncDel",
        ).start()

    def _run_safe(self, data: Any) -> None:
        """后台执行：任何异常都只记日志，绝不冒泡到事件总线。"""
        try:
            with self._lock:
                result = self.run(data)
            if result.get("matched"):
                self._save_history(result)
                self._notify(result)
        except Exception as err:  # noqa: BLE001 - 联动失败不影响宿主
            logger.error(f"[联动删除] 处理异常：{err}", exc_info=True)

    # ── 主链路 ──────────────────────────────────────────────────────

    def run(self, data: Any) -> dict[str, Any]:
        """执行五步链，返回各步结果（供通知与日志）。"""
        media_type = _text(_field(data, "media_type"))
        raw_path = _norm(self._map_path(_field(data, "item_path")))
        name = _text(_field(data, "item_name"))

        if media_type and media_type not in _WHOLE_DRAMA_TYPES:
            logger.info(f"[联动删除] 忽略非整剧删除事件（类型={media_type}，{name}）")
            return {"matched": False, "reason": f"类型 {media_type} 不是整剧"}

        if raw_path and self._excluded(raw_path):
            logger.info(f"[联动删除] 路径在排除名单内，忽略：{raw_path}")
            return {"matched": False, "reason": "路径已排除"}

        record = self._match_record(raw_path, name)
        if not record:
            logger.info(f"[联动删除] 事件不属于本插件整理的短剧，忽略：{name}｜{raw_path}")
            return {"matched": False, "reason": "不在记录库白名单"}

        title = _text(record.get("title")) or name
        # 本插件刚为「重新整理」清掉旧目录导致的事件：不是用户要删这部剧
        if self._is_suppressed(
            raw_path,
            _norm(record.get("dest_dir")),
            title,
            _norm(record.get("path")),
        ):
            logger.info(f"[联动删除] 该剧刚由本插件重新整理清理过，忽略删除事件：{title}")
            return {"matched": False, "reason": "自我清理抑制"}
        media_id = _text(record.get("media_id"))
        dest_dir = _norm(record.get("dest_dir"))
        src_dir = _norm(record.get("path"))
        logger.info(f"[联动删除] 命中记录：{title}｜media_id={media_id}｜dest={dest_dir}")

        result: dict[str, Any] = {
            "matched": True,
            "title": title,
            "media_id": media_id,
            "delete_media": bool(self.plugin._cfg(CONF_SYNCDEL_DELETE_MEDIA, False)),
            "steps": {},
        }

        # ② 插件整理历史：链路固有环节，无开关
        result["steps"]["plugin_history"] = self._mark_deleted_record(record)

        # ③ MP 整理历史：按开关；删之前先把源文件路径收集给⑤用
        src_paths, mp_ok = self._drop_mp_history(media_id, dest_dir, src_dir, title)
        result["steps"]["mp_history"] = mp_ok
        result["mp_rows"] = len(src_paths)

        # ④ 取消作品订阅：链路固有环节，无开关（幂等，不在清单里也不算失败）
        result["steps"]["unsubscribe"] = self._unsubscribe(media_id)

        # ⑤ 删种子（必做）+ 同步删除媒体（开关）
        outcome = self._handle_torrents(
            src_paths=src_paths,
            src_dir=src_dir,
            dest_dir=dest_dir,
        )
        result["steps"]["torrent"] = outcome.get("ok", False)
        result["torrents"] = outcome.get("torrents", 0)
        return result

    # ── 匹配与路径 ──────────────────────────────────────────────────

    def _map_path(self, path: Any) -> str:
        """按配置把 Emby 视角路径映射成容器内可访问的本地路径。"""
        text = _text(path)
        mapping = _text(self.plugin._cfg(CONF_SYNCDEL_LIBRARY_PATH, ""))
        if not text or not mapping:
            return text
        for line in mapping.splitlines():
            pair = line.strip().split(":", 1)
            if len(pair) != 2:
                continue
            source, target = _text(pair[0]), _text(pair[1])
            if source and text.startswith(source):
                return target + text[len(source):]
        return text

    def _excluded(self, path: str) -> bool:
        """排除路径前缀（逗号/换行分隔）命中即忽略。"""
        raw = _text(self.plugin._cfg(CONF_SYNCDEL_EXCLUDE_PATH, ""))
        if not raw:
            return False
        for item in raw.replace("\n", ",").split(","):
            prefix = _norm(item)
            if prefix and _under(path, prefix):
                return True
        return False

    def _records(self) -> list[dict[str, Any]]:
        """白名单：记录库里所有「已整理」的短剧记录。"""
        store_obj = self.plugin._record_store()
        if store_obj is None:
            return []
        try:
            rows = store_obj.all(limit=5000) or []
        except Exception as err:  # noqa: BLE001
            logger.warning(f"[联动删除] 读取记录库失败：{err}")
            return []
        return [
            row for row in rows
            if isinstance(row, dict) and row.get("transferred") and row.get("dest_dir")
        ]

    def _match_record(self, path: str, name: str) -> Optional[dict[str, Any]]:
        """在记录库白名单里匹配本次删除的短剧。

        优先级：路径（最长 dest_dir 前缀）> 剧名精确唯一 > 剧名包含唯一。
        多条命中说明有歧义，一律放弃（防误删）。
        """
        records = self._records()
        if not records:
            return None

        if path:
            hits = [
                (_norm(row.get("dest_dir")), row) for row in records
                if _under(path, _norm(row.get("dest_dir")))
            ]
            if hits:
                hits.sort(key=lambda item: len(item[0]), reverse=True)
                return hits[0][1]

        if name:
            normalized = _norm(name)
            exact = [row for row in records if _norm(row.get("title")) == normalized]
            if len(exact) == 1:
                return exact[0]
            loose = [
                row for row in records
                if _norm(row.get("title")) and _norm(row.get("title")) in normalized
            ]
            if len(loose) == 1:
                return loose[0]
            if len(loose) > 1:
                logger.warning(
                    f"[联动删除] 剧名 {name} 命中多条记录，放弃以防误删："
                    f"{[row.get('title') for row in loose]}"
                )
        return None

    # ── ② 插件整理记录（墓碑） ─────────────────────────────────────

    def _mark_deleted_record(self, record: dict[str, Any]) -> bool:
        """把这部剧标成「已删除」（墓碑），不再从记录库物理删除。

        2026-10-24 教训：删记录会让扫描/监控把它当新剧重新整理（删了又回来）。
        墓碑记录让扫描、监控永久跳过该源目录，面板「删除任务」里可见并可恢复。
        """
        key = _text(record.get("path"))
        store_obj = self.plugin._record_store()
        if not key or store_obj is None:
            return False
        try:
            return bool(store_obj.mark_ignored(key))
        except Exception as err:  # noqa: BLE001
            logger.warning(f"[联动删除] 标记已删除失败：{err}")
            return False

    # ── ③ MP 整理历史 ───────────────────────────────────────────────

    def _drop_mp_history(
        self, media_id: str, dest_dir: str, src_dir: str, title: str = ""
    ) -> tuple[list[str], bool]:
        """删除宿主整理历史里这部剧的全部行；返回 (源文件路径列表, 是否成功)。

        源文件列表在删除前收集，供第⑤步反查种子用。

        身份字段传**字符串** ``djbaike``：宿主 ``MediaSource`` 枚举没有该成员
        （2026-10-24 实测 ``MediaSource.djbaike`` 不存在），历史表里存的也是字符串，
        ``get_by`` 内部对字符串取 ``str()`` 后能精确命中。
        """
        if not bool(self.plugin._cfg(CONF_SYNCDEL_MP_HISTORY, True)):
            return [], True
        try:
            from app.db.oper.transferhistory import TransferHistoryOper

            oper = TransferHistoryOper()
            rows: list[Any] = []
            if media_id:
                rows = oper.get_by(
                    mtype=SYNCDEL_MTYPE_TV,
                    media_source=BAIKE_MEDIA_SOURCE,
                    media_id=media_id,
                ) or []
            if not rows and title:
                # 兜底：标题查询后再按身份过滤（同名的别家剧不会被误删）
                rows = [
                    row for row in (oper.get_by_title(title) or [])
                    if not _text(getattr(row, "media_id", None))
                    or _text(getattr(row, "media_id", None)) == media_id
                ]
            if not rows:
                logger.info("[联动删除] 宿主整理历史里没有该剧记录（可能已清过）")
                return [], True

            src_paths = [_text(row.src) for row in rows if _text(row.src)]
            for row in rows:
                oper.delete(row.id)
            logger.info(f"[联动删除] 已删除宿主整理历史 {len(rows)} 行")
            return src_paths, True
        except Exception as err:  # noqa: BLE001
            logger.warning(f"[联动删除] 删除宿主整理历史失败：{err}")
            return [], False

    # ── ④ 取消作品订阅 ──────────────────────────────────────────────

    def _unsubscribe(self, media_id: str) -> bool:
        """发跨插件事件让演员订阅插件按 media_id 取消作品订阅（幂等）。"""
        if not media_id:
            return False
        try:
            self.plugin.eventmanager.send_event(
                EventType.PluginAction,
                {"action": ACTOR_UNSUB_ACTION, "media_id": media_id},
            )
            logger.info(f"[联动删除] 已请求取消作品订阅：{media_id}")
            return True
        except Exception as err:  # noqa: BLE001
            logger.warning(f"[联动删除] 取消作品订阅事件发送失败：{err}")
            return False

    # ── ⑤ 删种子 / 同步删媒体 ───────────────────────────────────────

    def _handle_torrents(
        self, src_paths: list[str], src_dir: str, dest_dir: str
    ) -> dict[str, Any]:
        """定位并删除该剧的种子；``delete_media`` 开时同步删除媒体文件与目录。"""
        delete_media = bool(self.plugin._cfg(CONF_SYNCDEL_DELETE_MEDIA, False))
        allowed = _as_list(self.plugin._cfg(CONF_SYNCDEL_DOWNLOADERS, []))

        found = self._locate_torrents(src_paths=src_paths, src_dir=src_dir, allowed=allowed)
        # 安全阈值：一部短剧正常只有 1~2 个种子（正剧 + 可能的合集），
        # 命中过多说明匹配口径仍过于宽松，宁可不动（2026-10-24 事故防线）
        if len(found) > 3:
            logger.error(
                f"[联动删除] 匹配到 {len(found)} 个种子，超过安全阈值 3，放弃删种以防误删"
            )
            found = []
        ok = True
        if found:
            for downloader, hash_str in found:
                try:
                    self.plugin.chain.remove_torrents(
                        hashs=hash_str,
                        delete_file=delete_media,
                        downloader=downloader,
                    )
                    logger.info(
                        f"[联动删除] 已删除种子 {downloader}/{hash_str}"
                        f"（{'连文件' if delete_media else '仅注册项'}）"
                    )
                except Exception as err:  # noqa: BLE001
                    ok = False
                    logger.warning(f"[联动删除] 删除种子 {downloader}/{hash_str} 失败：{err}")
                # 辅种：开=删、关=停；按其记录里的下载器操作，不受指定下载器限制
                self._handle_reseeds(hash_str, delete_media)
        else:
            logger.info("[联动删除] 未找到该剧的种子（源文件可能不是下载器产物）")

        if delete_media:
            # 没找到种子时源文件不会由下载器删，这里自己清
            if not found:
                for src in src_paths:
                    self._unlink_file(src)
                self._remove_empty_dirs(src_dir)
            # 媒体库目录（软链/副本）随媒体一起清掉
            self._remove_tree(dest_dir)
        return {"ok": ok, "torrents": len(found)}

    def _locate_torrents(
        self, src_paths: list[str], src_dir: str, allowed: list[str]
    ) -> list[tuple[str, str]]:
        """定位该剧的种子（**宁漏勿错**）。

        2026-10-24 事故教训：早先版本用「源目录在种子保存路径之下」做包含判断，
        保存路径是短剧下载总目录的种子会全部命中，一次误删 169 个种子。现在只认
        两种强信号：

        1. 下载历史能按源文件全路径反查到 hash（最可靠，逐文件精确）；
        2. 种子名与剧源目录名指同一部剧（允许站点前缀/后缀，重叠度须足够），
           且种子保存路径是该剧目录本身或其祖先。
        """
        found: list[tuple[str, str]] = []
        seen: set[str] = set()

        # 1) 下载历史反查（最准：src 全路径 -> hash）
        try:
            from app.db.oper.downloadhistory import DownloadHistoryOper

            oper = DownloadHistoryOper()
            for src in src_paths:
                try:
                    hash_str = _text(oper.get_hash_by_fullpath(src))
                except Exception:  # noqa: BLE001
                    continue
                if not hash_str or hash_str in seen:
                    continue
                downloader = self._downloader_of_hash(hash_str, allowed)
                if downloader:
                    seen.add(hash_str)
                    found.append((downloader, hash_str))
        except Exception as err:  # noqa: BLE001
            logger.debug(f"[联动删除] 下载历史反查不可用（改为按名匹配）：{err}")

        if found:
            logger.info(f"[联动删除] 按下载历史匹配到 {len(found)} 个种子")
            return found

        # 2) 严格按种子名匹配（宁漏勿错）
        drama_dir = Path(src_dir).name.strip() if src_dir else ""
        if not drama_dir:
            return []
        normalized_src = _norm(src_dir)
        for name, instance in self._downloader_instances(allowed):
            try:
                torrents = instance.get_completed_torrents() or []
            except Exception as err:  # noqa: BLE001
                logger.debug(f"[联动删除] 读取下载器 {name} 种子失败：{err}")
                continue
            for torrent in torrents:
                torrent_name = _text(_torrent_attr(torrent, ("name",)))
                hash_str = _text(_torrent_attr(torrent, ("hash", "hashString")))
                save_path = _norm(
                    _torrent_attr(torrent, ("save_path", "downloadDir", "download_dir"))
                )
                if not torrent_name or not hash_str or hash_str in seen:
                    continue
                if not _same_drama_name(torrent_name, drama_dir):
                    continue
                if save_path and normalized_src and not (
                    save_path == normalized_src or _under(normalized_src, save_path)
                ):
                    continue
                seen.add(hash_str)
                found.append((name, hash_str))
        if found:
            logger.info(f"[联动删除] 按种子名匹配到 {len(found)} 个种子")
        return found

    def _downloader_instances(self, allowed: list[str]) -> list[tuple[str, Any]]:
        """取已启用下载器实例（``allowed`` 非空时只取名单内的）。"""
        result: list[tuple[str, Any]] = []
        try:
            from app.sdk.services import DownloaderHelper

            services = DownloaderHelper().get_services() or {}
        except Exception as err:  # noqa: BLE001
            logger.warning(f"[联动删除] 获取下载器列表失败：{err}")
            return result
        for name, service in services.items():
            if allowed and name not in allowed:
                continue
            instance = getattr(service, "instance", None)
            if instance is None:
                continue
            try:
                if instance.is_inactive():
                    continue
            except Exception:  # noqa: BLE001
                pass
            result.append((str(name), instance))
        return result

    def _downloader_of_hash(self, hash_str: str, allowed: list[str]) -> str:
        """在下载器里按 hash 找归属（找不到返回空串）。"""
        for name, instance in self._downloader_instances(allowed):
            try:
                torrents = instance.get_completed_torrents() or []
            except Exception:  # noqa: BLE001
                continue
            for torrent in torrents:
                if _text(_torrent_attr(torrent, ("hash", "hashString"))) == hash_str:
                    return name
        return ""

    def _handle_reseeds(self, hash_str: str, delete_media: bool) -> None:
        """处理 IYUU 辅种记录：删媒体时删辅种，否则暂停（递归到辅种的辅种）。"""
        seen: set[str] = set()

        def walk(key: str) -> None:
            try:
                records = self.plugin.get_data(key, plugin_id="IYUUAutoSeed") or []
            except Exception:  # noqa: BLE001
                return
            if not isinstance(records, list):
                records = [records]
            for record in records:
                if not isinstance(record, dict):
                    continue
                downloader = _text(record.get("downloader"))
                torrents = record.get("torrents")
                if not downloader or not torrents:
                    continue
                if not isinstance(torrents, list):
                    torrents = [torrents]
                for torrent in torrents:
                    torrent_hash = _text(torrent)
                    if not torrent_hash or torrent_hash in seen:
                        continue
                    seen.add(torrent_hash)
                    try:
                        if delete_media:
                            self.plugin.chain.remove_torrents(
                                hashs=torrent_hash, delete_file=False, downloader=downloader,
                            )
                            logger.info(f"[联动删除] 已删除辅种 {downloader}/{torrent_hash}")
                        else:
                            self.plugin.chain.stop_torrents(
                                hashs=torrent_hash, downloader=downloader,
                            )
                            logger.info(f"[联动删除] 已暂停辅种 {downloader}/{torrent_hash}")
                    except Exception as err:  # noqa: BLE001
                        logger.warning(f"[联动删除] 处理辅种 {torrent_hash} 失败：{err}")
                    walk(torrent_hash)

        walk(hash_str)

    # ── 文件清理 ────────────────────────────────────────────────────

    @staticmethod
    def _unlink_file(path: str) -> None:
        """删除单个文件或软链（不存在则忽略）。"""
        try:
            target = Path(path)
            if target.is_symlink() or target.is_file():
                target.unlink(missing_ok=True)
        except Exception as err:  # noqa: BLE001
            logger.debug(f"[联动删除] 删除文件失败 {path}：{err}")

    def _remove_empty_dirs(self, root: str) -> None:
        """自底向上清理空目录（不删根本身之外的任何非空目录）。"""
        base = Path(root) if root else None
        if not base or not base.is_dir():
            return
        try:
            for child in sorted(base.rglob("*"), key=lambda item: len(item.parts), reverse=True):
                if child.is_dir():
                    try:
                        child.rmdir()
                    except OSError:
                        pass
            try:
                base.rmdir()
            except OSError:
                pass
        except Exception as err:  # noqa: BLE001
            logger.debug(f"[联动删除] 清理空目录失败 {root}：{err}")

    def _remove_tree(self, root: str) -> None:
        """删除媒体库里的剧目录（软链/副本都清掉）。"""
        if not root:
            return
        target = Path(root)
        if not target.exists() and not target.is_symlink():
            return
        try:
            # 安全闸：只允许删媒体库根下的路径
            library = _norm(self.plugin._library_dir())
            if not library or not _under(_norm(root), library):
                logger.warning(f"[联动删除] 目录不在媒体库根下，跳过删除：{root}")
                return
            if target.is_symlink():
                target.unlink(missing_ok=True)
            else:
                shutil.rmtree(target, ignore_errors=True)
            logger.info(f"[联动删除] 已删除媒体目录：{root}")
        except Exception as err:  # noqa: BLE001
            logger.warning(f"[联动删除] 删除媒体目录失败 {root}：{err}")

    # ── 删除任务台账（面板展示） ────────────────────────────────────

    def _save_history(self, result: dict[str, Any]) -> None:
        """把一次删除任务写进插件数据，供面板「删除任务」列表展示。"""
        try:
            steps = result.get("steps") or {}
            entry = {
                "time": time.strftime("%Y-%m-%d %H:%M:%S"),
                "title": result.get("title") or "",
                "media_id": result.get("media_id") or "",
                "mp_rows": int(result.get("mp_rows") or 0),
                "torrents": int(result.get("torrents") or 0),
                "delete_media": bool(result.get("delete_media")),
                "ok": all(bool(value) for value in steps.values()),
            }
            history = self.plugin.get_data("delete_history") or []
            if not isinstance(history, list):
                history = []
            history.insert(0, entry)
            self.plugin.save_data("delete_history", history[:100])
        except Exception as err:  # noqa: BLE001
            logger.debug(f"[联动删除] 写删除台账失败（忽略）：{err}")

    # ── 通知 ────────────────────────────────────────────────────────

    def _notify(self, result: dict[str, Any]) -> None:
        """汇总各步结果发通知（失败项明确列出）。"""
        try:
            steps = result.get("steps") or {}
            lines = [f"《{result.get('title')}》"]
            lines.append("插件记录：" + ("已删" if steps.get("plugin_history") else "无/失败"))
            lines.append(f"宿主整理历史：{result.get('mp_rows', 0)} 行")
            lines.append("作品订阅：" + ("已取消" if steps.get("unsubscribe") else "未处理"))
            if steps.get("torrent"):
                media_note = "已删除（含媒体）" if result.get("delete_media") else "已删除种子"
                lines.append(f"种子与媒体：{media_note}")
            else:
                lines.append("种子与媒体：有失败项，见日志")
            self.plugin.post_message(
                mtype=NotificationType.Organize,
                title="【短剧百科·联动删除】",
                text="\n".join(lines),
            )
        except Exception as err:  # noqa: BLE001
            logger.debug(f"[联动删除] 通知发送失败（忽略）：{err}")


def _torrent_attr(torrent: Any, names: tuple[str, ...]) -> Any:
    """从种子对象取第一个可用字段（qb 用属性，tr 可能是 dict）。"""
    for name in names:
        value = getattr(torrent, name, None)
        if value is None and isinstance(torrent, dict):
            value = torrent.get(name)
        if value:
            return value
    return None


def _same_drama_name(torrent_name: str, folder_name: str) -> bool:
    """种子名与剧源目录名是否指同一部剧（允许站点前后缀，重叠度须足够）。

    2026-10-24 事故的防线之一：只用「名字实质相同」判定归属，绝不靠路径包含
    —— 保存路径常是整季/整站的公共父目录，路径包含会把别人的种子也算进来。
    """
    left = _norm(torrent_name).lower()
    right = _norm(folder_name).lower()
    if left.endswith(".torrent"):
        left = left[: -len(".torrent")]
    if not left or not right:
        return False
    if left == right:
        return True
    if right in left or left in right:
        shorter, longer = (left, right) if len(left) <= len(right) else (right, left)
        return len(shorter) / max(len(longer), 1) >= 0.6
    return False
