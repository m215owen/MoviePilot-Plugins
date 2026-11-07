"""短剧百科整理器（MoviePilot V3 插件）。

设计基线（2026-10-22 重写，落实用户三条指令）：

1. **识别用短剧百科数据源（``djbaike``）**：调 ``ShortDramaBaikeScraper`` 的
   ``search_medias``（``media_source="djbaike"``），取返回的第一条候选作身份
   （站点已按「字面命中 → 年份 → 完整度」排好序，不再本地打分）。
   调用方式为**按插件 id 精确直调**（``PluginManager.get_plugin_modules(pid)``
   取方法表，见 ``_source_method``）：不走宿主 dispatcher 广播，避免每次识别
   都把 IMDb源 等其它插件拉进来；数据源不可用时明确失败，**不回退广播**
   （用户 2026-10-23「要指定短剧百科数据源 / 不要回退」）。
2. **目录扫描文件夹即剧名**：``source_dirs`` 下按 ``scan_depth`` 逐层把子目录当成
   一部剧，目录名即剧名（先剥站点尾巴再拿去识别）。
3. **整理完全不走系统的方式**：文件搬运由本插件直接用标准库完成（``shutil`` /
   ``os.link`` / ``os.symlink``），**不**调 ``TransferChain`` / ``manual_transfer``，
   也不进宿主整理队列。命名照搬宿主「短剧处理器」TV 惯例
   （``{剧名} ({年})/Season 1/{剧名} - S01E{NN}.ext``）。
4. **整理历史读写改走 ``TransferHistoryOper``**：去重与落盘记录统一走宿主
   ``app.db.oper.transferhistory.TransferHistoryOper``，系统整理历史是「哪些文件已整理」
   的唯一真源（详见 ``history.py``）。是否拿它做去重由配置开关 ``force_transfer``
   控制（默认关 = 命中历史的源文件跳过；打开 = 无视历史强制重整理）。
5. **配置页的目录靠选不靠手打**（2026-10-22 追加）：扫描目录与目标库目录都是
   ``VCombobox``，候选来自「系统配置里的整理目录（短剧条目优先）+ 这些目录的一级
   子目录（浏览）」两条路，同时保留直接输入任意路径的能力（详见 ``dirs.py``）。
6. **扫描成果入插件自有库**（2026-10-23 追加，用户「数据要入库做记录」）：每部剧
   一行（身份 / 目标目录 / 是否存在 / 是否刮削 / 是否已整理），表面板四类统计
   （已识别 / 已整理 / 未识别 / 未刮削）与「记录」列表，重启不丢（详见 ``store.py``）。
7. **刮削同样自包含**（2026-10-23 改）：目标目录已存在时检测是否刮削过
   （``organize.is_scraped``），没刮削的由面板「立即刮削」或整理后的自动刮削处理。
   素材直取 djbaike 数据源的 ``metadata_nfo`` / ``metadata_img``（身份唯一来源
   不变，不自己抓站），**落盘自己写**：只写 ``tvshow.nfo`` 与海报到剧目录，
   不发 ``MetadataScrape`` 事件、不进宿主刮削链（详见 ``scrape.py`` 的理由）。
"""

from __future__ import annotations

import json
import os
import re
import shutil
import threading
import time
import traceback
from pathlib import Path
from typing import Any, Optional

from app.sdk.media import MetaInfo
from app.sdk.events import Event, eventmanager
from app.sdk.logging import logger
from app.sdk.plugin import _PluginBase
from app.schemas.types import EventType, NotificationType

from . import constants, dirs, history, matcher, naming, organize, scrape, store, syncdel
from .constants import (
    BAIKE_MEDIA_SOURCE,
    BAIKE_SOURCE_PLUGIN_ID,
    CONF_AUTO_RENAME_EPISODE,
    CONF_ENABLED,
    CONF_EPISODE_WIDTH,
    CONF_FORCE_REORGANIZE,
    CONF_FORCE_TRANSFER,
    CONF_LIBRARY_DIR,
    CONF_MONITOR_ENABLED,
    CONF_MONITOR_INTERVAL,
    CONF_MONITOR_MODE,
    CONF_NOTIFY,
    CONF_SCAN_DEPTH,
    CONF_SCRAPE_ENABLED,
    CONF_SOURCE_DIRS,
    CONF_SYNCDEL_ENABLED,
    CONF_TRANSFER_TYPE,
    CATEGORY_SHORT_DRAMA,
    DEFAULT_CONFIG,
    MAX_DETAIL_ITEMS,
    MAX_PREVIEW_ITEMS,
    MAX_SCAN_ITEMS,
    MAX_STORE_SCAN,
    MONITOR_INTERVAL_CEIL,
    MONITOR_INTERVAL_FLOOR,
    MONITOR_MODE_POLL,
    MONITOR_MODE_WATCH,
    MONITOR_MODES,
)
from .matcher import MatchDecision
from .serialize import safe_int, safe_str

# tvshow.nfo 里的三样东西：身份（uniqueid type=djbaike）、标题、年份。
# 补图链路靠它们还原「这部库内的剧是谁」，不依赖记录库（老记录可能早已被清）。
_NFO_ID_RE = re.compile(
    r'<uniqueid[^>]*type="djbaike"[^>]*>\s*([^<\s]+)\s*</uniqueid>', re.IGNORECASE
)
_NFO_TITLE_RE = re.compile(r"<title>(.*?)</title>", re.IGNORECASE | re.DOTALL)
_NFO_YEAR_RE = re.compile(r"<year>\s*(\d{4})\s*</year>", re.IGNORECASE)


class ShortDramaBaikeOrganizer(_PluginBase):
    """短剧百科整理器：扫描 → 识别 → 自包含搬运 → 写系统整理历史。"""

    plugin_name = constants.PLUGIN_NAME
    plugin_desc = constants.PLUGIN_DESC
    plugin_icon = constants.PLUGIN_ICON
    plugin_version = constants.PLUGIN_VERSION
    plugin_author = constants.PLUGIN_AUTHOR
    plugin_config_prefix = constants.PLUGIN_CONFIG_PREFIX
    plugin_order = constants.PLUGIN_ORDER
    auth_level = constants.PLUGIN_AUTH_LEVEL

    _enabled: bool = False
    _conf: dict = {}
    _monitor_thread: Optional[threading.Thread] = None
    _monitor_stop: Optional[threading.Event] = None
    _lock = threading.Lock()
    # 记录库（插件自有数据库，惰性取句柄；宿主缺 SDK 时整库降级）
    _store: Optional[store.RecordStore] = None
    _store_lock = threading.Lock()
    # 扫描（后台线程 + 进度快照，面板「扫描」按钮用）
    _scan_thread: Optional[threading.Thread] = None
    _scan_stop: Optional[threading.Event] = None
    _scan_lock = threading.Lock()
    _scan_state: dict = {
        "state": "idle",
        "total": 0,
        "done": 0,
        "current": "",
        "message": "",
        "started_at": None,
        "finished_at": None,
        "counts": {"pending": 0, "unrecognized": 0},
        "items": [],
    }
    # 整理（后台线程 + 进度快照 + 每部剧详情，面板「整理」按钮用）
    # ⚠️ 为什么必须是后台任务：整理 = 逐部识别（每部一次百科网络请求）+ 逐文件搬运，
    # 130 部剧跑几分钟是常态。同步挂在 HTTP 请求上会被反代掐断 → 前端只看到
    # 「Request failed with status code 502」（2026-10-23 实测）。
    _organize_thread: Optional[threading.Thread] = None
    _organize_stop: Optional[threading.Event] = None
    # 本次整理任务是否走「已识别记录」模式（面板 = True；目录监控 = False）
    _organize_use_records: bool = False
    _organize_lock = threading.Lock()
    _organize_state: dict = {
        "state": "idle",
        # scan = 还在识别阶段；organize = 已在搬运阶段
        "phase": "",
        "total": 0,
        "done": 0,
        "current": "",
        "message": "",
        "started_at": None,
        "finished_at": None,
        "counts": {"dramas": 0, "done": 0, "skipped": 0, "failed": 0, "unrecognized": 0},
        "details": [],
    }
    # 补图（补齐缺失/残图封面，后台线程 + 进度快照，2026-11-06）
    #
    # 场景：图床故障期（2026-11 上旬）整理入库的剧，海报要么没落盘、要么是 52 字节
    # 占位图。正常重扫不会碰它们（已刮削判定为「有产物」），所以要一条独立链路。
    _repair_thread: Optional[threading.Thread] = None
    _repair_stop: Optional[threading.Event] = None
    _repair_lock = threading.Lock()
    _repair_state: dict = {
        "state": "idle",
        "total": 0,
        "done": 0,
        "current": "",
        "message": "",
        "started_at": None,
        "finished_at": None,
        "counts": {"repaired": 0, "failed": 0},
        "items": [],
    }

    # ── 生命周期 ─────────────────────────────────────────────────────
    # 目录监控（事件监听 / 轮询两模式共用）
    _monitor_thread: Optional[threading.Thread] = None
    _monitor_stop: Optional[threading.Event] = None
    _watch_thread: Optional[threading.Thread] = None
    _watch_observer: Optional[Any] = None
    _watch_lock = threading.Lock()
    # 脏目录表 {剧目录路径: {last_event, fp, checked_at, retries}}（事件模式）
    _watch_dirty: dict = {}

    def init_plugin(self, config: Optional[dict] = None) -> None:
        config = config or {}
        self._conf = dict(DEFAULT_CONFIG)
        self._conf.update({k: v for k, v in config.items() if k in DEFAULT_CONFIG})
        self._enabled = bool(self._conf.get(CONF_ENABLED, False))
        logger.info(
            f"{constants.PLUGIN_NAME} 已初始化：启用={self._enabled}"
            f"｜识别源={BAIKE_MEDIA_SOURCE}｜整理=自包含（不走 TransferChain）"
            f"｜历史=TransferHistoryOper（强制整理={self._cfg(CONF_FORCE_TRANSFER, False)}）"
            f"｜刮削={self._cfg(CONF_SCRAPE_ENABLED, True)}"
            f"｜记录库={'可用' if store.store_available() else '不可用（降级内存态）'}"
        )
        if self._enabled and bool(self._conf.get(CONF_MONITOR_ENABLED, False)):
            self._start_monitor()
        self._ensure_plugin_icon()

    def _ensure_plugin_icon(self) -> None:
        """把插件图标补到宿主的静态目录 ``/public/plugin_icon/``。

        宿主只在**市场安装**时把图标同步进镜像自带的静态目录，本地源码插件
        （``is_local``）不会同步，于是前端请求 ``/plugin_icon/<icon>`` 一律 404。
        容器重建后 ``/public`` 会回到镜像原样，所以每次插件初始化都自愈一次；
        任何失败都只记 debug，绝不影响插件加载。
        """
        try:
            icon = constants.PLUGIN_ICON
            if not icon:
                return
            source = Path(__file__).resolve().parent / icon
            target_dir = Path("/public/plugin_icon")
            target = target_dir / icon
            if not source.is_file() or target.exists() or not target_dir.is_dir():
                return
            target.write_bytes(source.read_bytes())
            logger.info(f"[图标] 已补到宿主静态目录：{target}")
        except Exception as err:  # noqa: BLE001 - 图标缺失不影响功能
            logger.debug(f"[图标] 补图标失败（忽略）：{err}")

    def get_state(self) -> bool:
        return self._enabled

    def stop_service(self) -> None:
        self._stop_monitor()
        if self._scan_stop is not None:
            self._scan_stop.set()
        self._scan_thread = None
        if self._organize_stop is not None:
            self._organize_stop.set()
        self._organize_thread = None
        self._enabled = False
        logger.info(f"{constants.PLUGIN_NAME} 已停止")

    def get_database_models(self) -> list[Any]:
        """声明插件自有数据库里的表（宿主在插件启动时建表）。

        宿主没有 ``app.sdk.database``（建不出模型基类）时**声明为空**：记录库整体
        停用，插件退化为纯内存态（扫描 / 整理照常，只是重启后丢扫描成果），
        不把 ``None`` 交给宿主的建表流程。
        """
        if not store.store_available():
            return []
        return [store.DramaRecord]

    # ── 渲染模式与配置页（Vue 联邦） ───────────────────────────────
    @staticmethod
    def get_render_mode() -> tuple[str, str]:
        """Vue 联邦模式：配置页要「浏览目录」弹窗，面板要进度条与结果表格。

        Vuetify JSON 表单做不出真正的目录浏览（按钮点了改不到表单模型），
        所以配置页与详情面板都交给远程组件 ``./Config`` / ``./Page``。
        """
        return "vue", constants.frontend_dist()

    def get_form(self) -> tuple[None, dict]:
        """Vue 模式下不下发 Vuetify 表单，只给远程组件一份默认配置模型。"""
        return None, self._form_defaults()


    # ── 命令（侧栏/聊天触发） ───────────────────────────────────────
    @staticmethod
    def get_command() -> list[dict]:
        return [
            {
                "cmd": "/sdbko_scan",
                "event": EventType.PluginAction,
                "desc": "扫描并整理全部待整理短剧",
                "category": "短剧",
                "data": {"action": "organize"},
            },
        ]

    def handle_command(self, event: Event) -> None:
        action = (event.event_data or {}).get("action")
        if action != "organize":
            return
        # 整理走后台线程：同步跑会独占事件线程好几分钟（130 部剧逐部识别），
        # 整理完成时 organize_all 自己会发通知，这里只提示「已启动」。
        started = self.start_organize(force=False)
        text = (
            "短剧百科整理已在后台启动，完成后会通知结果"
            if started.get("started")
            else f"未启动：{started.get('message') or '未知原因'}"
        )
        self.post_message(mtype=NotificationType.Organize, title="【短剧百科整理】", text=text)

    # ── 反向联动（Emby 删除媒体 → 级联清理） ───────────────────────
    _syncdel: Optional[syncdel.SyncDeleter] = None

    @property
    def _syncdel_runner(self) -> syncdel.SyncDeleter:
        """懒加载联动删除执行器（每个插件实例一份）。"""
        if self._syncdel is None:
            self._syncdel = syncdel.SyncDeleter(self)
        return self._syncdel

    @eventmanager.register(EventType.WebhookMessage)
    def on_webhook_message(self, event: Event) -> None:
        """Emby 媒体移除事件入口。

        只处理 ``library.deleted`` 且命中记录库白名单的短剧；触发方式仅此一种，
        不做定时兜底扫描（用户 2026-10-24 明确）。
        """
        self._syncdel_runner.on_webhook(event)

    # ── HTTP API ───────────────────────────────────────────────────
    def get_api(self) -> list[dict]:
        # 刻意不按 enabled 早退：面板要在「未启用」时也能显示状态并提示去配置页启用
        return [
            {"path": "/status", "endpoint": self.api_status, "methods": ["GET"], "auth": "bear",
             "summary": "插件状态与识别源探活"},
            {"path": "/scan", "endpoint": self.api_scan, "methods": ["GET"], "auth": "bear",
             "summary": "扫描进度快照（含已识别结果）"},
            {"path": "/scan/start", "endpoint": self.api_scan_start, "methods": ["POST"], "auth": "bear",
             "summary": "启动扫描（后台线程，只识别不搬运）"},
            {"path": "/scan/stop", "endpoint": self.api_scan_stop, "methods": ["POST"], "auth": "bear",
             "summary": "停止正在进行的扫描"},
            {"path": "/search", "endpoint": self.api_search, "methods": ["GET"], "auth": "bear",
             "summary": "按关键词搜短剧百科候选（未识别目录人工处理用）"},
            {"path": "/organize", "endpoint": self.api_organize, "methods": ["POST"], "auth": "bear",
             "summary": "整理：不传 path 后台整理全部；传 path 单剧整理（可指定身份/目标库/搬运方式）"},
            {"path": "/organize", "endpoint": self.api_organize_snapshot, "methods": ["GET"], "auth": "bear",
             "summary": "整理进度快照（含每部剧详情，面板「整理详情」数据源）"},
            {"path": "/organize/start", "endpoint": self.api_organize_start, "methods": ["POST"], "auth": "bear",
             "summary": "启动整理（后台线程，同步跑会撞反代超时 502）"},
            {"path": "/organize/stop", "endpoint": self.api_organize_stop, "methods": ["POST"], "auth": "bear",
             "summary": "停止正在进行的整理"},
            {"path": "/preview", "endpoint": self.api_preview, "methods": ["GET"], "auth": "bear",
             "summary": "按指定身份/目标库预演将整理哪些文件（重新整理前先看结果）"},
            {"path": "/details", "endpoint": self.api_details, "methods": ["GET"], "auth": "bear",
             "summary": "整理详情：传 path 给该剧文件级整理记录；不传给本次整理运行详情"},
            {"path": "/records", "endpoint": self.api_records, "methods": ["GET"], "auth": "bear",
             "summary": "读取系统整理历史（本插件写入的 djbaike 记录）"},
            {"path": "/records/delete", "endpoint": self.api_records_delete, "methods": ["POST"], "auth": "bear",
             "summary": "按 src 删除一条整理历史"},
            {"path": "/store", "endpoint": self.api_store, "methods": ["GET"], "auth": "bear",
             "summary": "记录库：五类统计 + 全部剧记录（含目标目录/刮削状态/集数）"},
            {"path": "/store/complete", "endpoint": self.api_store_complete, "methods": ["POST"], "auth": "bear",
             "summary": "手动标记 / 取消「整理完成」（value=0 取消）"},
            {"path": "/store/delete", "endpoint": self.api_store_delete, "methods": ["POST"], "auth": "bear",
             "summary": "按源目录删除一条记录库记录"},
            {"path": "/store/clear", "endpoint": self.api_store_clear, "methods": ["POST"], "auth": "bear",
             "summary": "清空记录库"},
            {"path": "/delete/history", "endpoint": self.api_delete_history, "methods": ["GET"], "auth": "bear",
             "summary": "删除任务台账（Emby 删除联动执行过的清理记录）"},
            {"path": "/delete/restore", "endpoint": self.api_delete_restore, "methods": ["POST"], "auth": "bear",
             "summary": "恢复一条删除任务（清墓碑标记，扫描/监控重新纳入该剧）"},
            {"path": "/scrape", "endpoint": self.api_scrape, "methods": ["POST"], "auth": "bear",
             "summary": "立即刮削：取 djbaike 素材写入目标目录（tvshow.nfo + 海报）"},
            {"path": "/repair", "endpoint": self.api_repair, "methods": ["GET"], "auth": "bear",
             "summary": "补图进度快照（缺失/残图封面补齐）"},
            {"path": "/repair/start", "endpoint": self.api_repair_start, "methods": ["POST"], "auth": "bear",
             "summary": "启动补图：补齐媒体库里缺失或残图的剧/季封面（后台线程）"},
            {"path": "/repair/stop", "endpoint": self.api_repair_stop, "methods": ["POST"], "auth": "bear",
             "summary": "停止正在进行的补图"},
            {"path": "/stop", "endpoint": self.api_stop, "methods": ["POST"], "auth": "bear",
             "summary": "停止目录监控"},
            {"path": "/dirs/browse", "endpoint": self.api_dirs_browse, "methods": ["GET"], "auth": "bear",
             "summary": "浏览一层目录（配置页「浏览目录」弹窗用）"},
            {"path": "/dirs/options", "endpoint": self.api_dirs_options, "methods": ["GET"], "auth": "bear",
             "summary": "配置页下拉候选（系统配置里的下载目录 / 媒体库目录）"},
        ]

    # ── 详情页 ─────────────────────────────────────────────────────
    def get_page(self) -> None:
        """Vue 模式下详情面板由远程 ``./Page`` 渲染，这里返回 None。

        注意：``get_page`` 是 ``_PluginBase`` 的抽象方法，**必须实现**，
        否则插件实例化直接失败（安装时报「插件加载失败」）。
        """
        return None


    # ── 配置读取助手 ───────────────────────────────────────────────
    def _cfg(self, key: str, default: Any = None) -> Any:
        val = self._conf.get(key, DEFAULT_CONFIG.get(key, default))
        return default if val is None else val

    def _source_dirs(self) -> list[str]:
        """扫描根列表：兼容旧的换行字符串、新的多选数组与 {title,value} 对象。"""
        return dirs.as_path_list(self._cfg(CONF_SOURCE_DIRS, ""))

    def _library_dir(self) -> str:
        """目标库目录：容错 VCombobox 可能存下的 {title,value} 对象。"""
        return dirs.as_path(self._cfg(CONF_LIBRARY_DIR, ""))

    def _form_defaults(self) -> dict:
        """配置页默认值：把历史遗留的字符串形态归一成表单要的形态。"""
        defaults = dict(DEFAULT_CONFIG)
        defaults.update(self._conf)
        defaults[CONF_SOURCE_DIRS] = self._source_dirs()
        defaults[CONF_LIBRARY_DIR] = self._library_dir()
        return defaults

    # ── 记录库（插件自有数据库） ────────────────────────────────────
    def _record_store(self) -> Optional[store.RecordStore]:
        """取记录库门面；宿主没给出数据库句柄时返回 None（降级内存态）。"""
        if not store.store_available():
            return None
        with self._store_lock:
            if self._store is not None:
                return self._store
            try:
                handle = self.get_database()
            except Exception as err:  # pragma: no cover - 宿主数据库异常
                logger.warning(f"[记录库] 取插件数据库失败，记录库停用：{err}")
                return None
            if handle is None:  # pragma: no cover - 极端兜底
                return None
            self._store = store.RecordStore(handle)
            return self._store

    def _save_record(self, item: dict) -> None:
        """扫描/整理成果入库（失败只记日志，绝不影响主流程）。

        词汇映射：扫描/整理链里「已识别」叫 ``pending``（快照与扫描列表用它），
        而记录库的统计（``store.stats``）与面板筛选用 ``recognized``。在这里
        统一翻过去 —— 少了这一步，130 部已识别的剧会全被算成「未识别」
        （2026-10-23 真机实测踩过）。
        """
        records = self._record_store()
        if records is None:
            return
        record = dict(item)
        if record.get("state") == "pending":
            record["state"] = "recognized"
        try:
            records.upsert(record)
        except Exception as err:  # pragma: no cover
            logger.warning(f"[记录库] 写入失败（忽略）：{err}")

    # ── 目录候选（系统配置 + 浏览） ────────────────────────────────
    def _directory_confs(self) -> list[dict]:
        """读取系统配置「设置 → 目录」里的整理目录（失败降级为空表）。

        宿主把整理目录存在 ``SystemConfigKey.Directories``，元素结构即
        ``TransferDirectoryConf``（download_path / library_path / media_category /
        library_category_folder ...）。官方 downloadtorrent 插件也是这么取的，
        避免依赖内部目录帮助类。
        """
        try:
            from app.schemas.types import SystemConfigKey

            raw = self.systemconfig.get(SystemConfigKey.Directories)
        except Exception as err:  # noqa: BLE001 - 读不到就只留手输
            logger.warning(f"[目录] 读取系统目录配置失败，回退为手工输入：{err}")
            return []
        return dirs.normalize_directory_confs(raw)

    def _source_dir_options(self) -> list[dict]:
        """扫描目录候选：系统配置的下载目录 + 其一级子目录 + 常见挂载。"""
        try:
            return dirs.download_options(self._directory_confs())
        except Exception as err:  # noqa: BLE001
            logger.warning(f"[目录] 生成扫描目录候选失败：{err}")
            return []

    def _library_dir_options(self) -> list[dict]:
        """媒体库目录候选：系统配置的媒体库目录 + 分类/一级子目录 + 常见挂载。"""
        try:
            return dirs.library_options(self._directory_confs())
        except Exception as err:  # noqa: BLE001
            logger.warning(f"[目录] 生成媒体库目录候选失败：{err}")
            return []

    # ── 识别（短剧百科 djbaike） ────────────────────────────────────
    def _source_method(self, method: str):
        """按插件 id **精确**取短剧百科数据源（``ShortDramaBaikeScraper``）的模块方法。

        为什么不用 ``self.chain.run_module``：宿主 dispatcher 对模块方法做**广播**，
        会把 ``recognize_media`` / ``search_medias`` 发给所有实现该方法的插件
        （IMDb源 等），每次识别都多一次跨插件调用与日志噪音（用户 2026-10-23
        「要指定短剧百科数据源」）。这里经公开投影
        ``PluginManager.get_plugin_modules(pid)`` 只取那一份方法表。

        **不回退广播**（用户 2026-10-23 明确）：取不到方法表（数据源未启用 /
        旧宿主无该 API）就返回 None，由调用方明确失败 —— 宁可报「数据源不可用」，
        也不把识别悄悄广播给别的插件。

        :return: 可调用对象；不可用返回 None
        """
        try:
            from app.sdk.plugin import PluginManager

            manager = PluginManager()
            try:
                catalog = manager.get_plugin_modules(BAIKE_SOURCE_PLUGIN_ID) or {}
            except TypeError:  # 老版本不收 pid：取全量再自己筛
                catalog = manager.get_plugin_modules() or {}
            for (plugin_id, _name), table in catalog.items():
                if plugin_id == BAIKE_SOURCE_PLUGIN_ID and isinstance(table, dict):
                    func = table.get(method)
                    if callable(func):
                        return func
            logger.warning(
                f"[数据源] {BAIKE_SOURCE_PLUGIN_ID} 未提供模块方法 {method}"
                f"（插件未启用或版本过旧），本次调用失败"
            )
        except Exception as err:  # noqa: BLE001 - 宿主版本差异不该把调用打成 500
            logger.warning(f"[数据源] 精确取 {BAIKE_SOURCE_PLUGIN_ID}.{method} 失败：{err}")
        return None

    def _probe_source(self) -> bool:
        """探活：短剧百科（djbaike）识别链路当前是否可用（最佳努力）。

        直接用一次轻量 ``search_medias`` 调用验证识别通路是否通畅；不要求返回命中，
        只确认 ``ShortDramaBaikeScraper`` 已挂上 ``djbaike`` 来源且调用不报错。
        真正的「来源是否启用 / 是否收录」在 ``recognize_drama`` 时由「有无候选」判定。
        """
        func = self._source_method("search_medias")
        if func is None:
            return False
        try:
            func(meta=MetaInfo(title="__probe__"), media_source=BAIKE_MEDIA_SOURCE)
            return True
        except Exception as err:  # noqa: BLE001
            logger.warning(f"[识别] 短剧百科探活异常：{err}")
            return False

    def _media_to_candidate(self, mi: Any) -> matcher.Candidate:
        def g(attr: str) -> Any:
            v = getattr(mi, attr, None)
            if v is None and hasattr(mi, "get"):
                try:
                    v = mi.get(attr)
                except Exception:  # pragma: no cover
                    v = None
            return v

        ep = g("number_of_episodes")
        if ep is None:
            ep = g("episode_count")
        return matcher.Candidate(
            media_id=safe_str(g("media_id")),
            title=safe_str(g("title")),
            year=safe_int(g("year")),
            episode_count=safe_int(ep),
            kind=safe_str(g("kind")),
        )

    def recognize_drama(self, raw_name: str) -> MatchDecision:
        """用短剧百科的**识别方法**（``recognize_media``）按目录名定唯一身份。

        目录名**原样使用**：不剥任何发布尾巴（用户 2026-10-23 明确要求，剥尾巴的函数
        已从 ``matcher.py`` 整体删除）。

        调用走**按插件 id 精确直调**（``_source_method``），不经过宿主 dispatcher
        广播 —— 只认 ``ShortDramaBaikeScraper`` 一个数据源，取不到方法表就明确
        失败，不回退成广播（用户 2026-10-23「要指定短剧百科数据源 / 不要回退」）。
        """
        name = str(raw_name or "").strip()
        if not name:
            return MatchDecision(matcher.ACTION_HOLD, reason="目录名为空")
        func = self._source_method("recognize_media")
        if func is None:
            return MatchDecision(
                matcher.ACTION_HOLD,
                reason=f"短剧百科数据源不可用（{BAIKE_SOURCE_PLUGIN_ID} 未启用或未提供 recognize_media）",
            )
        try:
            info = func(
                meta=MetaInfo(title=name),
                media_source=BAIKE_MEDIA_SOURCE,
            )
        except Exception as err:  # noqa: BLE001
            logger.error(f"[识别] 调用短剧百科识别失败：{err}")
            return MatchDecision(matcher.ACTION_HOLD, reason=f"识别调用异常：{err}")
        if not info:
            return MatchDecision(matcher.ACTION_HOLD, reason="短剧百科未识别（无匹配）")
        candidate = self._media_to_candidate(info)
        if not candidate.media_id:
            return MatchDecision(matcher.ACTION_HOLD, reason="识别结果缺少 media_id")
        return MatchDecision(matcher.ACTION_ADOPT, candidate=candidate, reason="短剧百科识别")

    # ── 扫描（后台线程 + 进度快照） ─────────────────────────────────
    def scan_dramas(
        self,
        progress=None,
        stop: Optional[threading.Event] = None,
    ) -> list[dict]:
        """扫描并识别全部待整理目录（同步实现，``progress`` 用于上报进度）。

        每部剧除识别结果外，还就地探测目标目录（``dest_dir`` / ``dest_exists`` /
        ``scraped``）与整理进展（``transferred``），并写入记录库 —— 面板的
        「已识别 / 已整理 / 未识别 / 未刮削」四类统计与「记录」列表以此为准，
        重启不丢（用户 2026-10-23「数据要入库做记录」）。

        :param progress: 可选回调 ``(done, total, current_name, item)``
        :param stop: **显式**传入的停止信号。刻意不读 ``self._scan_stop``：
            Event 一旦 set 就永久为真，停过一次扫描后那个 Event 会被后续所有
            扫描/整理当成「已停止」而瞬间退出。扫描任务、整理任务各传各的
            （监控循环不传 → 不受手动停止影响）。
        """
        source_dirs = self._source_dirs()
        if not source_dirs:
            return []
        depth = safe_int(self._cfg(CONF_SCAN_DEPTH, 1), 1) or 1
        library_dir = self._library_dir()
        dramas = organize.iter_drama_dirs(source_dirs, depth, excludes=[])[:MAX_SCAN_ITEMS]
        # 「整理完成」的目录直接跳过（2026-10-23 用户「扫描按钮重按跳过整理
        # 完成的目录」）：既不识别也不覆盖记录，重复扫描不再折腾已收齐的剧
        done_paths: set = set()
        ignored_paths: set = set()
        prior: dict = {}
        records = self._record_store()
        if records is not None:
            try:
                done_paths = records.done_paths()
            except Exception:  # pragma: no cover - 跳过逻辑失败不该拖垮扫描
                done_paths = set()
            try:
                # 「已删除」的剧永久跳过：Emby 删了但源目录还在，不能重新整理回来
                ignored_paths = records.ignored_paths()
            except Exception:  # pragma: no cover
                ignored_paths = set()
            try:
                prior = {
                    str(r.get("path") or ""): r
                    for r in records.all(limit=MAX_STORE_SCAN)
                }
            except Exception:  # pragma: no cover - 取不到旧记录就退回原行为
                prior = {}
        total = len(dramas)
        items: list[dict] = []
        for index, d in enumerate(dramas, start=1):
            if stop is not None and stop.is_set():
                break
            if str(d) in done_paths or str(d) in ignored_paths:
                continue
            decision = self.recognize_drama(d.name)
            if decision.adopted and decision.candidate:
                item = {
                    "drama": d.name,
                    "path": str(d),
                    "state": "pending",
                    "title": decision.candidate.title,
                    "year": decision.candidate.year,
                    "media_id": decision.candidate.media_id,
                    # 剧的总集数（百科词条带出来的，面板「共 X 集」用）
                    "episode_count": safe_int(decision.candidate.episode_count, 0) or 0,
                    "reason": decision.reason,
                    "dest_dir": "",
                    "dest_exists": False,
                    "scraped": False,
                    "transferred": False,
                }
                # 旧记录是人工指定身份的，标记要跟着走（只增不减）
                if (prior.get(str(d)) or {}).get("manual"):
                    item["manual"] = 1
                # 目标目录与刮削/整理进展（识别成功的才有目标可查）
                if library_dir:
                    try:
                        dest = naming.build_drama_dir(
                            library_dir, item["title"], item["year"]
                        )
                        item["dest_dir"] = str(dest)
                        item["dest_exists"] = dest.is_dir()
                        if item["dest_exists"]:
                            item["scraped"] = organize.is_scraped(dest)
                            item["transferred"] = history.has_transferred_dest(str(dest))
                    except Exception:  # pragma: no cover - 探测失败不该拖垮扫描
                        pass
            else:
                # 本次重识别失败：若这条路径**曾经识别成功过**（人工指定身份，或
                # 上一轮自动识别成功后来数据源抽风），就不许把记录降级成「未识别」
                # —— 2026-10-23 用户「已经人工处理的未识别的剧再扫描还会入未识别」。
                # 保留旧身份，目标目录/刮削/整理三态按文件系统事实复核。
                prev = prior.get(str(d)) or {}
                sticky = bool(prev) and (
                    bool(prev.get("manual"))
                    or (
                        str(prev.get("state") or "") == "recognized"
                        and bool(str(prev.get("media_id") or "").strip())
                    )
                )
                if sticky:
                    item = {
                        "drama": d.name,
                        "path": str(d),
                        "state": "pending",
                        "title": prev.get("title") or "",
                        "year": prev.get("year"),
                        "media_id": str(prev.get("media_id") or ""),
                        "episode_count": safe_int(prev.get("episode_count"), 0) or 0,
                        "reason": "沿用已识别身份（本次重识别失败）",
                        "dest_dir": str(prev.get("dest_dir") or ""),
                        "dest_exists": bool(prev.get("dest_exists")),
                        "scraped": bool(prev.get("scraped")),
                        "transferred": bool(prev.get("transferred")),
                    }
                    if prev.get("manual"):
                        item["manual"] = 1
                    dest = Path(item["dest_dir"]) if item["dest_dir"] else None
                    if dest is not None:
                        try:
                            item["dest_exists"] = dest.is_dir()
                            if item["dest_exists"]:
                                item["scraped"] = organize.is_scraped(dest)
                                item["transferred"] = history.has_transferred_dest(
                                    str(dest)
                                )
                        except Exception:  # pragma: no cover - 探测失败用旧值
                            pass
                else:
                    item = {
                        "drama": d.name,
                        "path": str(d),
                        "state": "unrecognized",
                        "title": "",
                        "year": None,
                        "media_id": "",
                        "episode_count": 0,
                        "reason": decision.reason,
                        "dest_dir": "",
                        "dest_exists": False,
                        "scraped": False,
                        "transferred": False,
                    }
            self._save_record(item)
            items.append(item)
            if callable(progress):
                try:
                    progress(index, total, d.name, item)
                except Exception:  # pragma: no cover - 进度上报不该拖垮扫描
                    pass
        return items

    def _scan_state_reset(self) -> None:
        with self._scan_lock:
            self._scan_state = {
                "state": "idle",
                "total": 0,
                "done": 0,
                "current": "",
                "message": "",
                "started_at": None,
                "finished_at": None,
                "counts": {"pending": 0, "unrecognized": 0},
                "items": [],
            }

    def scan_snapshot(self) -> dict:
        """当前扫描进度快照（前端轮询）。"""
        with self._scan_lock:
            snapshot = dict(self._scan_state)
            snapshot["counts"] = dict(self._scan_state.get("counts") or {})
            snapshot["items"] = list(self._scan_state.get("items") or [])
            return snapshot

    def scan_running(self) -> bool:
        thread = self._scan_thread
        return bool(thread and thread.is_alive())

    def start_scan(self) -> dict:
        """启动一次后台扫描（只识别、不搬运）。已在跑则直接返回当前快照。"""
        if self.scan_running():
            return {"started": False, "message": "扫描已在进行中", "scan": self.scan_snapshot()}
        if not self._source_dirs():
            return {"started": False, "message": "未配置扫描目录", "scan": self.scan_snapshot()}
        self._scan_stop = threading.Event()
        with self._scan_lock:
            self._scan_state = {
                "state": "running",
                "total": 0,
                "done": 0,
                "current": "",
                "message": "正在枚举待整理目录…",
                "started_at": time.time(),
                "finished_at": None,
                "counts": {"pending": 0, "unrecognized": 0},
                "items": [],
            }
        self._scan_thread = threading.Thread(
            target=self._scan_worker, daemon=True, name="SdbkoScan"
        )
        self._scan_thread.start()
        return {"started": True, "message": "扫描已启动", "scan": self.scan_snapshot()}

    def stop_scan(self) -> dict:
        if self._scan_stop is not None:
            self._scan_stop.set()
        with self._scan_lock:
            if self._scan_state.get("state") == "running":
                self._scan_state["state"] = "stopping"
                self._scan_state["message"] = "正在停止…"
        return {"stopped": True, "scan": self.scan_snapshot()}

    def _scan_worker(self) -> None:
        """扫描线程主体：逐部识别并实时更新快照。"""
        def progress(done: int, total: int, name: str, item: dict) -> None:
            with self._scan_lock:
                if self._scan_state.get("state") not in ("running", "stopping"):
                    return
                self._scan_state["total"] = total
                self._scan_state["done"] = done
                self._scan_state["current"] = name
                counts = self._scan_state.setdefault("counts", {"pending": 0, "unrecognized": 0})
                key = "pending" if item.get("state") == "pending" else "unrecognized"
                counts[key] = int(counts.get(key, 0)) + 1
                items = self._scan_state.setdefault("items", [])
                items.append(item)
                if len(items) > MAX_SCAN_ITEMS:
                    del items[0]
                self._scan_state["message"] = f"正在识别（{done}/{total}）…"

        try:
            items = self.scan_dramas(progress=progress, stop=self._scan_stop)
            with self._scan_lock:
                stopped = self._scan_stop is not None and self._scan_stop.is_set()
                self._scan_state["state"] = "stopped" if stopped else "done"
                self._scan_state["done"] = len(items)
                self._scan_state["total"] = self._scan_state.get("total") or len(items)
                self._scan_state["current"] = ""
                self._scan_state["finished_at"] = time.time()
                counts = self._scan_state.get("counts") or {}
                self._scan_state["message"] = (
                    f"扫描完成：{len(items)} 部（已识别 {counts.get('pending', 0)}，"
                    f"未识别 {counts.get('unrecognized', 0)}）"
                    if not stopped else f"已手动停止（已扫 {len(items)} 部）"
                )
        except Exception as err:  # pragma: no cover
            logger.error(f"[扫描] 线程异常：{err}\n{traceback.format_exc()}")
            with self._scan_lock:
                self._scan_state["state"] = "error"
                self._scan_state["message"] = f"扫描失败：{err}"
                self._scan_state["finished_at"] = time.time()

    # ── 整理（自包含） ──────────────────────────────────────────────
    def organize_drama(
        self,
        drama_path: str,
        decision: MatchDecision,
        force: bool = False,
        *,
        library_dir: Optional[str] = None,
        transfer_type: Optional[str] = None,
        ignore_force: bool = False,
        season: Optional[int] = None,
    ) -> dict:
        """整理一部剧（自包含搬运 + 写系统整理历史）。

        :param library_dir: 指定时**覆盖**配置的目标库根目录（面板「重新整理」
            可换目标库，2026-10-23 需求「可指定」）；不指定用配置值。
        :param transfer_type: 指定时覆盖配置的搬运方式（move/copy/link/softlink）。
        :param ignore_force: True = 无视「强制整理历史」等强制开关，恒尊重整理
            历史（目录监控专用：监控只处理新增/变化的文件，与强制整理无关，
            2026-10-23 用户明确）。
        :param season: **手动指定季号**（1~99，2026-11-03 用户要求「手动整理时
            支持指定季号」）。指定后库内按 ``Season N`` + ``S0NE0X`` 落盘与命名，
            同时 ``Season N/season.nfo`` 写该季号；不指定（None/0）沿用定稿口径
            「一季一个独立剧目录、内部恒 Season 1」。后台整理全部与目录监控
            不传，行为不变。
        """
        library_dir = (library_dir or "").strip() or self._library_dir()
        if not library_dir:
            return {"success": False, "error": "未配置目标库目录（library_dir）"}
        if not decision.adopted or not decision.candidate:
            return {"success": False, "error": "未识别到短剧百科身份，无法整理"}
        cand = decision.candidate
        # 「人工指定名称」（百科上没有的剧，2026-11-04 用户要求）：候选没有
        # media_id 也能整理 —— 搬运 / 命名 / 整理历史全照常，只是刮削没有素材
        # 来源，直接跳过。只有人工链路（reason=人工指定名称）允许无 id 候选，
        # 识别链路给不出 id 一律视为异常拒绝。
        manual_named = not (cand.media_id or "").strip()
        if manual_named and decision.reason != "人工指定名称":
            return {"success": False, "error": "候选缺少媒体 id，无法整理"}
        title = cand.title or Path(drama_path).name
        year = cand.year
        width = safe_int(self._cfg(CONF_EPISODE_WIDTH, 2), 2) or 2
        auto_rename = bool(self._cfg(CONF_AUTO_RENAME_EPISODE, True))
        transfer_type = (transfer_type or "").strip() or str(self._cfg(CONF_TRANSFER_TYPE, "move"))
        # 配置页「强制整理历史」（2026-10-23 起）：开 = 无视系统整理历史重新整理，
        # 命中记录的源文件先删旧记录再搬；关（默认）= 尊重历史，命中就跳过。
        # 目录监控调用恒尊重历史（ignore_force=True，与强制整理无关）
        force_re = False if ignore_force else bool(force or self._cfg(CONF_FORCE_REORGANIZE, False))
        force_transfer = False if ignore_force else bool(self._cfg(CONF_FORCE_TRANSFER, False))
        force_all = force_re or force_transfer
        scrape_enabled = bool(self._cfg(CONF_SCRAPE_ENABLED, True))

        # 先取一次剧级 MediaInfo（有 id 时直取，不联网）：历史记录要写海报、
        # 季号要从它的 season 拿、后面的自动刮削直接复用它，一部剧只识一次
        info = self._resolve_media(title=title, media_id=cand.media_id)
        # 一季一个独立剧目录（2026-10-23 用户改回）：词条剧名就是剧目录名
        # （``隐身侍卫第二季`` 不剥季号），括号年份仍剥掉交给目录名 (年) 后缀；
        # 季号供 Season NN 子目录与 SxxEyy 命名回落
        title, title_season, title_year = naming.parse_title_identity(title)
        if not year:
            # 手动身份的候选常缺年份（数据源搜索出口不带）：按 id 取回的
            # MediaInfo 上有（实测 duanju:7556163095597419545 → 2025），兜底
            year = safe_int(getattr(info, "year", None), 0) or title_year
        # 源侧季号：词条本身是第几季，只用于向数据源**按季取素材**
        src_season = safe_int(getattr(info, "season", None), 0) or title_season or 1
        src_season = max(1, min(99, src_season))
        # 库内季号：默认 **1** —— 一季一个独立剧目录（2026-10-23 用户定稿
        # 「第二季就按第二季剧名整理」，目录内 Season 1 + S01Exx）。
        # 手动整理可**显式指定季号**（2026-11-03 用户要求）：指定后按
        # ``Season N`` + ``S0NE0X`` 落盘与命名 —— 用途是源目录名推不出季、
        # 或要让同一部剧的多季并进同一剧目录（各占一个 Season 子目录）。
        manual_season = safe_int(season, 0)
        season_no = max(1, min(99, manual_season)) if manual_season else 1

        plans = organize.plan_files(
            Path(drama_path),
            title=title,
            year=year,
            library_dir=library_dir,
            episode_width=width,
            auto_rename=auto_rename,
            season=season_no,
        )
        if not plans:
            return {"success": True, "drama": title, "done": 0, "skipped": 0, "failed": 0,
                    "note": "没有可整理的视频文件（或都提不到集号且未开启补齐）"}

        dest_drama_dir = naming.build_drama_dir(library_dir, title, year)
        drama_info = {
            "media_source": BAIKE_MEDIA_SOURCE,
            "media_id": cand.media_id,
            "title": title,
            "year": year,
            "_poster_url": scrape.poster_url(info),
        }

        # 重新整理（强制）前：收集这部剧此前的目标目录，并**一次性**清掉它的
        # 全部旧整理记录。2026-10-27 用户「重新整理没有把老记录和老的媒体删除」：
        # 原先只逐 src 删记录，换标题/年份后旧目录与旧行都会残留。
        old_dests: list[str] = []
        if force_all:
            prev: dict = {}
            store_obj = self._record_store()
            if store_obj is not None:
                try:
                    prev = next(
                        (
                            row for row in store_obj.all(limit=MAX_STORE_SCAN)
                            if str(row.get("path") or "") == drama_path
                        ),
                        {},
                    ) or {}
                except Exception:  # noqa: BLE001
                    prev = {}
            if prev.get("dest_dir"):
                old_dests.append(str(prev["dest_dir"]))
            for row in history.list_records_by_src_dir(drama_path):
                guess = history.drama_dir_of(str(row.get("dest") or ""))
                if guess:
                    old_dests.append(guess)
            removed = history.delete_by_src_dir(drama_path)
            logger.info(f"[整理] 重新整理前清理旧整理记录 {removed} 条")

        done = skipped = failed = 0
        for src, target, episode in plans:
            if not force_all and history.is_transferred(str(src)):
                skipped += 1
                continue
            if organize.transfer_file(src, target, transfer_type):
                history.record_transfer(
                    str(src), str(target),
                    mode=transfer_type, title=title, year=year,
                    season=season_no, episode=episode, drama_info=drama_info,
                )
                done += 1
            else:
                failed += 1

        # 目标目录变了：旧媒体目录（软链/副本）与它的旧记录一并清掉
        if force_all and done > 0 and old_dests:
            for old in dict.fromkeys(old_dests):
                if not old or self._same_dir(old, str(dest_drama_dir)):
                    continue
                self._cleanup_old_media(
                    old, library_dir, drama_path, transfer_type, title
                )

        # 整理成果入库（面板统计与记录列表的数据源）。done=0（文件全命中历史
        # 被跳过）时**人工指定身份也要落库**：手动处理重跑才能把集数/年份刷新
        # 进记录（2026-10-23「重生1982 手动处理后集数怎么没有」实测）。
        if done > 0 or decision.reason == "人工指定身份":
            dest_exists = dest_drama_dir.is_dir()
            record_patch = {
                "path": drama_path,
                "drama": Path(drama_path).name,
                "state": "pending",
                "media_id": cand.media_id,
                "title": title,
                "year": year,
                "dest_dir": str(dest_drama_dir),
                "dest_exists": dest_exists,
                # done>0 必然已整理；done=0 时按目标目录现状探测
                "transferred": bool(done) or (
                    dest_exists and history.has_transferred_dest(str(dest_drama_dir))
                ),
                "done_count": done,
                # 剧的总集数：手动身份的搜索候选常是 0（数据源搜索出口不带集数），
                # 依次兜底按 id 取回的 MediaInfo（number_of_episodes / episode_count）；
                # 面板「共 X 集 / 已整理 Y 集」与「整理完成」判定都用它
                "episode_count": (
                    safe_int(getattr(cand, "episode_count", None), 0)
                    or safe_int(getattr(info, "number_of_episodes", None), 0)
                    or safe_int(getattr(info, "episode_count", None), 0)
                    or 0
                ),
                "reason": "",
            }
            # 人工指定身份打标：后续重识别失败时靠它保住身份，不被判成「未识别」
            # 「人工指定名称」（无百科身份）同样打标 —— 名字就是用户给的，不存在降级
            if decision.reason in ("人工指定身份", "人工指定名称"):
                record_patch["manual"] = 1
            # 已整理集数：按目标剧目录的整理历史去重统计（谁写的都算）
            organized_eps = history.count_distinct_episodes(str(dest_drama_dir))
            if organized_eps:
                record_patch["organized_episodes"] = organized_eps
            self._save_record(record_patch)
            # 自动刮削（默认开）。scrape_drama 内部会跳过已刮的剧级、只补缺的
            # 季级；``season`` 传**源侧季号**（是否取季素材），``lib_season`` 传
            # 库内季号（季产物落到哪一层，手动指定季号时就是它）。
            # 「人工指定名称」没有百科词条可问（media_id 为空），刮削整体跳过。
            if scrape_enabled and not manual_named:
                self.scrape_drama(
                    dest_drama_dir,
                    title=title,
                    year=year,
                    media_id=cand.media_id,
                    source_path=drama_path,
                    info=info,
                    season=src_season,
                    lib_season=season_no,
                )
            elif manual_named:
                logger.info(f"[整理] {title} 为人工指定名称（无百科身份），跳过自动刮削")

        return {
            "success": True,
            "drama": title,
            "done": done,
            "skipped": skipped,
            "failed": failed,
            "dest_dir": str(dest_drama_dir),
            **({"note": "已按手动命名整理（百科无此剧，未刮削）"} if manual_named else {}),
        }

    @staticmethod
    def _same_dir(left: str, right: str) -> bool:
        """两个目录路径是否指向同一处（归一后比较，跨平台分隔符）。"""
        return os.path.normcase(os.path.normpath(str(left))) == os.path.normcase(
            os.path.normpath(str(right))
        )

    def _cleanup_old_media(
        self,
        old_dir: str,
        library_dir: str,
        drama_path: str,
        transfer_type: str,
        title: str = "",
    ) -> bool:
        """删除重新整理前的旧媒体目录（软链/副本）与其整理记录。

        安全闸（缺一不可）：
        1. 搬运方式不是 ``move`` —— move 模式下源文件已搬进旧目录，删了就没副本；
        2. 旧目录必须位于**目标库根**之下（防止误删库外路径）；
        3. 不是新目标目录（调用方已比对）；
        4. 没有**其它**记录仍指向该目录（防止两部剧共用目录时误删）。
        """
        if (transfer_type or "").strip().lower() == "move":
            logger.info(f"[整理] 搬运方式是 move，保留旧目录：{old_dir}")
            return False
        target = Path(old_dir)
        if not old_dir or not (target.exists() or target.is_symlink()):
            return False
        try:
            target.resolve().relative_to(Path(library_dir).resolve())
        except Exception:  # noqa: BLE001 - 不在库根下就不动
            logger.warning(f"[整理] 旧目录不在目标库下，跳过清理：{old_dir}")
            return False
        store_obj = self._record_store()
        if store_obj is not None:
            try:
                others = [
                    row
                    for row in store_obj.all(limit=MAX_STORE_SCAN)
                    if self._same_dir(str(row.get("dest_dir") or ""), old_dir)
                    and str(row.get("path") or "") != drama_path
                ]
                if others:
                    logger.info(f"[整理] 旧目录仍被其它记录使用，跳过清理：{old_dir}")
                    return False
            except Exception:  # noqa: BLE001
                pass
        # 先登记抑制：删掉旧目录会让 Emby 发出「条目被移除」，不能让联动删除
        # 把这部剧的源文件和种子一起清掉（2026-10-27 事故）
        try:
            self._syncdel_runner.suppress(old_dir, drama_path, title)
        except Exception:  # noqa: BLE001
            pass
        removed = history.delete_by_dest_dir(old_dir)
        try:
            if target.is_symlink():
                target.unlink(missing_ok=True)
            else:
                shutil.rmtree(target, ignore_errors=True)
        except Exception as err:  # noqa: BLE001
            logger.warning(f"[整理] 删除旧目录失败 {old_dir}：{err}")
            return False
        logger.info(f"[整理] 已清理旧媒体目录：{old_dir}（旧记录 {removed} 条）")
        return True

    def _resolve_media(self, *, title: str = "", media_id: str = "") -> Any:
        """取剧级 MediaInfo：有 id 直取（数据源的 id 分支不联网），否则按名识别。

        整理与刮削都要它 —— 整理拿它写历史里的海报，刮削拿它问素材。抽成一个
        方法后，整理时取一次就能两处复用（130 部剧少 130 次识别）。
        取不到返回 ``None``：缺数据源 / 缺关键词都算，由调用方决定报什么错。
        """
        func = self._source_method("recognize_media")
        if func is None:
            return None
        target = (media_id or "").strip()
        if target:
            try:
                info = func(media_source=BAIKE_MEDIA_SOURCE, media_id=target)
                if info:
                    return info
            except Exception as err:  # noqa: BLE001 - id 分支失败回落按名
                logger.warning(f"[识别] 按 id 取媒体信息失败（回落按名）：{err}")
        keyword = (title or "").strip()
        if not keyword:
            return None
        try:
            return func(meta=MetaInfo(title=keyword), media_source=BAIKE_MEDIA_SOURCE)
        except Exception as err:  # noqa: BLE001 - 识别失败不该让整理中断
            logger.warning(f"[识别] 识别媒体信息失败：{err}")
            return None

    # ── 刮削（自包含：素材直取数据源，落盘自己写） ──────────────────
    def scrape_drama(
        self,
        dest_dir: str | Path,
        *,
        title: str = "",
        year: Optional[int] = None,
        media_id: str = "",
        source_path: str = "",
        info: Any = None,
        season: int = 0,
        lib_season: int = 0,
        repair: bool = False,
    ) -> dict:
        """对目标剧目录刮削（自包含：素材直取 djbaike 出口，落盘自己写）。

        :param info: 已取到的 MediaInfo（整理时先取过一次，这里直接复用，省一次识别）
        :param season: **源侧**季号（整理链传入；0 时回落 MediaInfo.season）。有季号
            就向数据源按季取一次素材（2026-10-23 用户「季的刮削要存到季的目录下」）
        :param lib_season: **库内**季号（季产物落到哪一层，0/缺省 = 1）。手动整理
            指定季号时传该值，``season.nfo`` 的 seasonnumber 与 ``Season N`` 目录
            一起跟随（2026-11-03 用户要求）

        **不发 ``MetadataScrape`` 事件、不进宿主刮削链**（2026-10-23 改，与
        「整理自包含」对齐）：素材仍来自 djbaike 数据源的 ``metadata_nfo`` /
        ``metadata_img``（身份唯一来源不变，不自己抓站），但落盘由本插件完成 ——
        只写 ``tvshow.nfo`` 与海报到剧目录，**同步返回、产物即刻可见**。

        绕开宿主刮削链的三点理由（均为 2026-10-23 实测）：
        1. 它是**广播事件、异步派发**，接口返回时产物还没落盘，只能靠轮询等；
        2. ``file_list`` 语义强耦合：为空拿不到 tvshow.nfo / poster，非空又会
           逐文件刮削 —— 为了 2 个想要的文件，得先塞 1 个无关文件去骗分支；
        3. djbaike 只做剧级（对 episode 有值一律返回 None），逐文件刮削注定
           产出 262 字节空壳 NFO：42 集 = 42 个垃圾文件 + 约 42 秒开销。

        :param media_id: 已知身份时**优先按 id 直取**（零搜索且精确）；为空才回落按名
        :param source_path: 源目录（传入时刮削结果回写记录库）
        :param repair: True = **补图模式**：即使剧级已刮过也重新取材，只补缺失/残图
            文件（已有的正常产物照旧跳过）。图床故障期的存量记录靠它补封面
            （2026-11-06）
        """
        dest = Path(dest_dir)
        if not dest.is_dir():
            return {"success": False, "error": f"目标目录不存在：{dest_dir}"}
        # 剧级已刮**不再重复写剧级产物，但季级补挂照走**（2026-10-23「隐身侍卫
        # 第二季为什么没有刮削信息」）：多季并入同一剧目录时，先整理的季刮了
        # 剧级，早返回会让后到的季永远缺 season.nfo / 季海报。
        drama_done = organize.is_scraped(dest)

        # 1) 取完整媒体信息（数据源两个出口都要 MediaInfo，不只是 media_id）
        if self._source_method("recognize_media") is None:
            return {
                "success": False,
                "error": f"短剧百科数据源不可用（{BAIKE_SOURCE_PLUGIN_ID} 未启用或未提供 recognize_media）",
            }
        if info is None:
            query = (title or "").strip() or dest.parent.name
            info = self._resolve_media(title=query, media_id=media_id)
        if not info:
            return {"success": False, "error": "短剧百科未识别，无法刮削"}

        # 季号分两个口径：``season`` 是**源侧季号**（词条本身第几季，按季取素材
        # 用）；``lib_season`` 是**落盘布局季号** —— 默认 1（一季一个独立剧目录，
        # 2026-10-23 用户定稿），手动指定季号时跟随指定值（2026-11-03）
        season_no = safe_int(season, 0) or safe_int(getattr(info, "season", None), 0) or 0
        lib_season = max(1, min(99, safe_int(lib_season, 0) or 1))
        # 一季一个独立剧目录（2026-10-23 用户改回「第二季就按第二季剧名整理」）：
        # 剧层（tvshow.nfo / 海报）由**本目录自己的词条**负责，不再有「只许第一季
        # 刮剧层」的限制 —— 那是多季并入同一目录时代的口径。剧级已刮仍不重写。
        drama_write = not drama_done or repair
        if drama_done and not season_no and not repair:
            return {"success": True, "skipped": True, "message": "目标已刮削，无需重复刮削"}

        # 2) 取素材（自包含：直调数据源两个出口，不发 MetadataScrape 事件）；
        #    剧级已刮时跳过剧级取材，只补季级
        nfo_func = self._source_method("metadata_nfo")
        img_func = self._source_method("metadata_img")
        if drama_write:
            nfo_text, images = scrape.fetch_material(nfo_func, img_func, info)
        else:
            nfo_text, images = "", {}

        # 2.5) 季级素材：有季号就向数据源**按季**再取一次（数据源按季给图的，
        #      一季一条词条）。取不到不报错 —— 数据源没上季出口时静默跳过。
        #
        # ⚠️ 请求季号必须用**数据源视角的词条季号**（``info.season``，缺省 1），
        # 不能用标题推导的 ``season_no``：数据源 2026-10-24 起出口不再携带季号
        # （``hostmedia.to_host_media`` 恒 None，标题季号只在识别入口用），而它的
        # 季图出口按 ``mediainfo.season == 请求季号`` 把关 —— 传标题推导的季号
        # （``隐身侍卫第二季`` → 2）会被判「词条不是这一季」而拿空（2026-11-02
        # 对照数据源 scrape.build_images 实证）。本插件的库内布局是「一季一个
        # 独立剧目录、内部恒 Season 1」，词条自己的详情就是这一季的素材，按词条
        # 季号（现恒 1）请求正好命中，且 season.nfo 的 seasonnumber 与目录一致。
        entry_season = safe_int(getattr(info, "season", None), 0) or 1
        season_material: tuple[str, dict[str, str]] = ("", {})
        if season_no:
            season_material = scrape.fetch_material(
                nfo_func, img_func, info, season=entry_season
            )

        if not drama_write and not nfo_text and not images and not season_material[0] and not season_material[1]:
            return {"success": False, "error": "短剧百科未提供刮削素材（nfo 与图片均为空）"}

        # 3) 落盘（同步完成，返回即可见产物）；剧级已刮时不再动剧级文件
        written = (
            {"skipped": True}
            if not drama_write
            else scrape.write_metadata(dest, nfo_text=nfo_text, images=images)
        )

        # 3.5) 季级产物落盘：season.nfo + 季海报进 Season NN 目录
        #      （Emby 剧集结构：季图在季文件夹里才会在剧集页按季显示）
        season_written: dict = {}
        if lib_season and (season_material[0] or season_material[1]):
            season_written = scrape.write_season_metadata(
                dest,
                lib_season,
                nfo_text=season_material[0],
                images=season_material[1],
            )
            for text in season_written.get("errors") or []:
                logger.warning(f"[刮削] 季级 {text}")
        scraped = bool(
            written.get("nfo")
            or written.get("images")
            or season_written.get("nfo")
            or season_written.get("images")
        )
        for text in written.get("errors") or []:
            logger.warning(f"[刮削] {text}")

        # 4) 回写记录库
        if source_path:
            records = self._record_store()
            if records is not None:
                try:
                    records.mark_scraped(source_path)
                except Exception as err:  # pragma: no cover
                    logger.warning(f"[记录库] 标记已刮削失败（忽略）：{err}")
        if not scraped:
            message = "产物已存在，无需重复刮削" if written.get("skipped") else "未写入任何产物"
        else:
            parts = []
            if written.get("nfo"):
                parts.append(scrape.NFO_FILENAME)
            parts.extend(written.get("images") or [])
            if season_written.get("nfo"):
                parts.append(f"{scrape.season_dir_name(lib_season)}/{scrape.SEASON_NFO_FILENAME}")
            for name in season_written.get("images") or []:
                parts.append(f"{scrape.season_dir_name(lib_season)}/{name}")
            message = f"已刮削：{'、'.join(parts)}"
        result = {
            "success": True,
            "scraped": scraped,
            "season": lib_season,
            "media_id": str(getattr(info, "media_id", "") or ""),
            "nfo": bool(written.get("nfo")),
            "images": written.get("images") or [],
            "skipped": written.get("skipped") or [],
            "errors": written.get("errors") or [],
            "message": message,
            "dest_dir": str(dest),
        }
        if season_written:
            result["season_nfo"] = bool(season_written.get("nfo"))
            result["season_images"] = season_written.get("images") or []
        return result

    # ── 补图（图床故障期缺失 / 残图封面） ──────────────────────────
    #
    # 背景（2026-11-06 用户）：图床故障那段时间整理入库的剧，海报要么根本没落盘，
    # 要么落成 52 字节占位图。它们的 tvshow.nfo 是好的，于是「已刮削」判定成立，
    # 常规重扫/重新整理都不会再去取图 —— 需要一条独立的「只补图、不动其它产物」
    # 链路，按库内目录逐个补，且不覆盖已有正常产物。
    #
    # 身份来源：优先 tvshow.nfo 的 uniqueid(djbaike)（零搜索、精确），缺失时按
    # nfo 标题 / 目录名回落按名识别。

    _COVER_NAMES: tuple = ("poster.jpg", "poster.jpeg", "poster.png", "poster.webp",
                           "folder.jpg", "folder.png")

    @staticmethod
    def _read_nfo_identity(dest: Path) -> tuple[str, str, Optional[int]]:
        """从 ``tvshow.nfo`` 读 ``(media_id, 标题, 年份)``；读不到用目录名兜底。"""
        media_id, title, year = "", "", None
        try:
            text = (dest / scrape.NFO_FILENAME).read_text(encoding="utf-8", errors="ignore")
        except OSError:
            text = ""
        if text:
            matched = _NFO_ID_RE.search(text)
            if matched:
                media_id = matched.group(1).strip()
            matched = _NFO_TITLE_RE.search(text)
            if matched:
                title = matched.group(1).strip()
            matched = _NFO_YEAR_RE.search(text)
            if matched:
                year = safe_int(matched.group(1))
        if not title:
            # 库内目录名口径是「剧名 (年份)」，剥掉尾巴当年份线索
            title = re.sub(r"\s*\(\d{4}\)\s*$", "", dest.name).strip()
        return media_id, title, year

    @classmethod
    def _drama_cover_ok(cls, dest: Path) -> bool:
        return any(scrape.image_ok(dest / name) for name in cls._COVER_NAMES)

    @staticmethod
    def _season_cover_ok(season_dir: Path, season: int) -> bool:
        """季目录里是否已有**有效**季海报。

        ⚠️ 命名有**两套并存**：数据源原始 key 是补零的 ``season01-poster.jpg``
        （2026-11-03 之前的产物），之后写入统一改成不补零的 ``season1-poster.jpg``。
        两种都算「已有」，否则补图会把全库三百多部判定成缺季图、重新下一遍
        （2026-11-06 实测踩过）。同目录还常见 ``.jpg``（占位残图）与 ``.webp``
        （真图）并存，所以按「季号 + 有效大小」判，不按扩展名。
        """
        pattern = re.compile(r"season0*(\d+)-poster\.(?:jpg|jpeg|png|webp)$", re.IGNORECASE)
        try:
            for entry in season_dir.iterdir():
                matched = pattern.match(entry.name)
                if matched and int(matched.group(1)) == int(season) and scrape.image_ok(entry):
                    return True
        except OSError:
            return False
        return False

    @staticmethod
    def _season_dir_numbers(dest: Path) -> list[int]:
        """剧目录下的一级 ``Season N`` 季号（短剧只有一层，多季并列也算）。"""
        numbers: list[int] = []
        try:
            for sub in dest.iterdir():
                if not sub.is_dir():
                    continue
                matched = re.fullmatch(r"Season\s*(\d+)", sub.name, re.IGNORECASE)
                if matched:
                    numbers.append(int(matched.group(1)))
        except OSError:
            return []
        return sorted(numbers)

    def _repair_plan(self, root: Path) -> list[dict]:
        """列出媒体库里「缺封面」的剧：``{dest, poster, seasons}``。

        只认**封面类**文件（poster/folder）当封面；``fanart`` 不算 —— Emby 的
        封面位取的是 poster，光有 fanart 照样显示空白。
        """
        plan: list[dict] = []
        try:
            children = sorted(p for p in root.iterdir() if p.is_dir() and not p.name.startswith("."))
        except OSError as err:
            logger.warning(f"[补图] 枚举媒体库失败：{err}")
            return plan
        for dest in children:
            seasons = self._season_dir_numbers(dest)
            if not seasons and not (dest / scrape.NFO_FILENAME).exists():
                continue  # 既不是季结构也没有 nfo，不像短剧目录，跳过
            missing_poster = not self._drama_cover_ok(dest)
            missing_seasons = [
                number for number in seasons
                if not self._season_cover_ok(dest / scrape.season_dir_name(number), number)
            ]
            if missing_poster or missing_seasons:
                plan.append({"dest": dest, "poster": missing_poster, "seasons": missing_seasons})
        return plan

    def repair_drama_assets(
        self,
        dest: Path,
        *,
        poster: bool = True,
        seasons: Optional[list[int]] = None,
    ) -> dict:
        """补一部剧的封面：剧级 poster + 指定季的季海报（已有的正常文件不动）。

        :return: ``{"ok": 是否补到东西, "written": [...], "errors": [...], "media_id": str}``
        """
        media_id, title, _year = self._read_nfo_identity(dest)
        info = self._resolve_media(title=title, media_id=media_id)
        if not info:
            return {"ok": False, "written": [], "errors": [f"短剧百科未识别（{title or dest.name}）"]}
        img_func = self._source_method("metadata_img")
        if img_func is None:
            return {"ok": False, "written": [], "errors": ["数据源不可用（未提供 metadata_img）"]}

        written: list[str] = []
        errors: list[str] = []
        resolved_id = str(getattr(info, "media_id", "") or "")

        if poster:
            _nfo, images = scrape.fetch_material(None, img_func, info)
            if not images:
                errors.append("数据源未提供剧级图片")
            else:
                # nfo_text 传空 = 不碰已有 tvshow.nfo，这条链路只补图
                result = scrape.write_metadata(dest, nfo_text="", images=images)
                written.extend(result.get("images") or [])
                errors.extend(result.get("errors") or [])

        season_list = [n for n in (seasons or []) if n >= 1]
        if season_list:
            # 季素材请求季号用**数据源视角**的词条季号（与 scrape_drama 同一口径）
            entry_season = safe_int(getattr(info, "season", None), 0) or 1
            _nfo, season_images = scrape.fetch_material(
                None, img_func, info, season=entry_season
            )
            if not season_images:
                errors.append("数据源未提供季级图片")
            else:
                for number in season_list:
                    result = scrape.write_season_metadata(
                        dest, number, nfo_text="", images=season_images
                    )
                    written.extend(
                        f"{scrape.season_dir_name(number)}/{name}"
                        for name in (result.get("images") or [])
                    )
                    errors.extend(result.get("errors") or [])

        return {
            "ok": bool(written),
            "written": written,
            "errors": errors,
            "media_id": resolved_id,
        }

    def _repair_state_reset(self) -> None:
        with self._repair_lock:
            self._repair_state = {
                "state": "idle",
                "total": 0,
                "done": 0,
                "current": "",
                "message": "",
                "started_at": None,
                "finished_at": None,
                "counts": {"repaired": 0, "failed": 0},
                "items": [],
            }

    def repair_snapshot(self) -> dict:
        """补图进度快照（前端轮询）。"""
        with self._repair_lock:
            snapshot = dict(self._repair_state)
            snapshot["counts"] = dict(self._repair_state.get("counts") or {})
            snapshot["items"] = list(self._repair_state.get("items") or [])
            return snapshot

    def repair_running(self) -> bool:
        thread = self._repair_thread
        return bool(thread and thread.is_alive())

    def start_repair(self, library_dir: str = "") -> dict:
        """启动一次后台补图（只补缺失/残图封面，不动集文件与已有产物）。"""
        if self.repair_running():
            return {"started": False, "message": "补图已在进行中", "repair": self.repair_snapshot()}
        root_text = (library_dir or "").strip() or self._library_dir()
        if not root_text:
            return {"started": False, "message": "未配置目标库目录", "repair": self.repair_snapshot()}
        root = Path(root_text)
        if not root.is_dir():
            return {"started": False, "message": f"目标库目录不存在：{root_text}", "repair": self.repair_snapshot()}
        if self._source_method("metadata_img") is None:
            return {
                "started": False,
                "message": f"短剧百科数据源不可用（{BAIKE_SOURCE_PLUGIN_ID} 未启用或未提供 metadata_img）",
                "repair": self.repair_snapshot(),
            }
        self._repair_stop = threading.Event()
        with self._repair_lock:
            self._repair_state = {
                "state": "running",
                "total": 0,
                "done": 0,
                "current": "",
                "message": "正在枚举媒体库目录…",
                "started_at": time.time(),
                "finished_at": None,
                "counts": {"repaired": 0, "failed": 0},
                "items": [],
            }
        self._repair_thread = threading.Thread(
            target=self._repair_worker, args=(root,), daemon=True, name="SdbkoRepair"
        )
        self._repair_thread.start()
        return {"started": True, "message": "补图已启动", "repair": self.repair_snapshot()}

    def stop_repair(self) -> dict:
        if self._repair_stop is not None:
            self._repair_stop.set()
        with self._repair_lock:
            if self._repair_state.get("state") == "running":
                self._repair_state["state"] = "stopping"
                self._repair_state["message"] = "正在停止…"
        return {"stopped": True, "repair": self.repair_snapshot()}

    def _repair_worker(self, root: Path) -> None:
        """补图线程主体：逐部取素材补缺失封面，实时更新快照。"""
        try:
            plan = self._repair_plan(root)
            with self._repair_lock:
                self._repair_state["total"] = len(plan)
                self._repair_state["message"] = (
                    f"待补 {len(plan)} 部，正在取素材…" if plan else "库内没有缺封面的剧"
                )
            if not plan:
                with self._repair_lock:
                    self._repair_state["state"] = "done"
                    self._repair_state["finished_at"] = time.time()
                return

            for index, target in enumerate(plan, start=1):
                if self._repair_stop is not None and self._repair_stop.is_set():
                    break
                dest = target["dest"]
                with self._repair_lock:
                    self._repair_state["current"] = dest.name
                    self._repair_state["done"] = index - 1
                    self._repair_state["message"] = f"正在补图（{index}/{len(plan)}）：{dest.name}"
                try:
                    item = self.repair_drama_assets(
                        dest, poster=target["poster"], seasons=target["seasons"]
                    )
                except Exception as err:  # noqa: BLE001 - 单部失败不该中断整批
                    item = {"ok": False, "written": [], "errors": [str(err)], "media_id": ""}
                success = bool(item.pop("ok", False))
                item.update({
                    "drama": dest.name,
                    "path": str(dest),
                    "seasons": target["seasons"],
                    "state": "repaired" if success else "failed",
                })
                with self._repair_lock:
                    self._repair_state["done"] = index
                    counts = self._repair_state.setdefault("counts", {"repaired": 0, "failed": 0})
                    counts[item["state"]] = int(counts.get(item["state"], 0)) + 1
                    items = self._repair_state.setdefault("items", [])
                    items.append(item)
                    if len(items) > MAX_SCAN_ITEMS:
                        del items[0]

            with self._repair_lock:
                stopped = self._repair_stop is not None and self._repair_stop.is_set()
                counts = self._repair_state.get("counts") or {}
                self._repair_state["state"] = "stopped" if stopped else "done"
                self._repair_state["current"] = ""
                self._repair_state["finished_at"] = time.time()
                summary = (
                    f"补图完成：{counts.get('repaired', 0)} 部已补，"
                    f"{counts.get('failed', 0)} 部失败"
                )
                self._repair_state["message"] = (
                    f"已手动停止（{summary}）" if stopped else summary
                )
            logger.info(f"[补图] {self.repair_snapshot().get('message')}")
        except Exception as err:  # pragma: no cover
            logger.error(f"[补图] 线程异常：{err}\n{traceback.format_exc()}")
            with self._repair_lock:
                self._repair_state["state"] = "error"
                self._repair_state["message"] = f"补图失败：{err}"
                self._repair_state["finished_at"] = time.time()

    def _items_from_records(self) -> Optional[list[dict]]:
        """从记录库取剧清单（整理全部「免重识别」模式的数据源）。

        行结构与 :meth:`scan_dramas` 的 item 保持一致，后面的整理循环零改动复用。
        记录库不可用、或一条已识别（有 ``media_id``）的记录都没有时返回 ``None``，
        调用方回落到完整扫描识别（首次使用 / 清空过记录的场景）。
        """
        records = self._record_store()
        if records is None:
            return None
        try:
            rows = records.all(limit=MAX_STORE_SCAN)
        except Exception as err:  # noqa: BLE001 - 记录库读不出来就老老实实重扫
            logger.warning(f"[整理] 记录库读取失败，回落扫描识别：{err}")
            return None
        items: list[dict] = []
        has_recognized = False
        for r in rows:
            path = str(r.get("path") or "").strip()
            if not path:
                continue
            media_id = str(r.get("media_id") or "").strip()
            # 人工指定身份可以只有剧名、没有 id（面板「人工处理」允许只填剧名），
            # 这种也算已识别，否则会被整理链当成未识别跳过（2026-10-23）
            title = str(r.get("title") or "").strip()
            if media_id or title:
                has_recognized = True
            items.append({
                "drama": r.get("drama") or Path(path).name,
                "path": path,
                "state": "pending" if (media_id or title) else "unrecognized",
                "media_id": media_id,
                "title": title,
                "year": r.get("year"),
                "reason": r.get("reason") or "",
            })
        return items if has_recognized else None

    def organize_all(
        self,
        force: bool = False,
        *,
        scan_progress=None,
        progress=None,
        stop: Optional[threading.Event] = None,
        use_records: bool = False,
    ) -> dict:
        """整理全部：逐部搬运（同步实现，供后台线程 / 命令 / 监控调用）。

        :param use_records: True = **直接用记录库里已识别的身份整理**，不重新
            扫描、不重新识别（2026-10-23 用户「整理按钮按下为什么要再扫描一次？
            应该执行对已识别的整理」）；记录库不可用或没有已识别记录时回落完整
            扫描识别。False = 完整扫描识别（目录监控用，负责发现新剧目录）。
        :param scan_progress: 识别阶段进度回调 ``(done, total, name, item)``
        :param progress: 搬运阶段进度回调 ``(index, total, drama, detail)``，
            ``detail`` 是一部剧的整理结果，会被面板「整理详情」窗口逐条展示。
        :param stop: 显式停止信号（同 :meth:`scan_dramas`，不读实例属性）
        """
        items: Optional[list[dict]] = None
        if use_records:
            items = self._items_from_records()
            if items is not None and callable(scan_progress):
                # 记录模式没有识别阶段，一次性把进度推满，让前端直接进搬运阶段
                scan_progress(len(items), len(items), "使用已识别记录，跳过识别", {})
        if items is None:
            items = self.scan_dramas(progress=scan_progress, stop=stop)
        total = {"scanned": len(items), "done": 0, "skipped": 0, "failed": 0, "unrecognized": 0}
        for index, it in enumerate(items, start=1):
            if stop is not None and stop.is_set():
                break
            if it["state"] != "pending":
                total["unrecognized"] += 1
                if callable(progress):
                    progress(
                        index,
                        len(items),
                        it["drama"],
                        {
                            "drama": it["drama"],
                            "path": it["path"],
                            "title": "",
                            "dest_dir": "",
                            "done": 0,
                            "skipped": 0,
                            "failed": 0,
                            "unrecognized": True,
                            "organized": False,
                            "error": it.get("reason") or "短剧百科未识别",
                            "note": "",
                        },
                    )
                continue
            decision = MatchDecision(
                matcher.ACTION_ADOPT,
                candidate=matcher.Candidate(
                    media_id=it["media_id"], title=it["title"], year=it["year"]
                ),
            )
            res = self.organize_drama(it["path"], decision, force=force)
            if res.get("success"):
                total["done"] += res.get("done", 0)
                total["skipped"] += res.get("skipped", 0)
                total["failed"] += res.get("failed", 0)
                detail = {
                    "drama": it["drama"],
                    "path": it["path"],
                    "title": res.get("drama") or it.get("title") or "",
                    "dest_dir": res.get("dest_dir") or "",
                    "done": res.get("done", 0),
                    "skipped": res.get("skipped", 0),
                    "failed": res.get("failed", 0),
                    "unrecognized": False,
                    "organized": True,
                    "error": "",
                    "note": res.get("note") or "",
                }
            else:
                total["failed"] += 1
                detail = {
                    "drama": it["drama"],
                    "path": it["path"],
                    "title": it.get("title") or "",
                    "dest_dir": "",
                    "done": 0,
                    "skipped": 0,
                    "failed": 0,
                    "unrecognized": False,
                    "organized": False,
                    "error": res.get("error") or "整理失败",
                    "note": "",
                }
            if callable(progress):
                progress(index, len(items), it["drama"], detail)
        if bool(self._cfg(CONF_NOTIFY, True)):
            self.post_message(
                mtype=NotificationType.Organize,
                title="【短剧百科整理】",
                text=f"扫描 {total['scanned']} 部，整理 {total['done']} 文件，"
                     f"跳过 {total['skipped']}，失败 {total['failed']}，未识别 {total['unrecognized']}",
            )
        return total

    # ── 整理任务（后台线程 + 进度快照） ──────────────────────────────
    #
    # 与扫描同一套路：POST 只当「按下开关」，界面一律以 GET /organize 的快照为准。
    # 这是 502 的根治办法 —— 整理比扫描更慢（多了逐文件搬运），同步挂在 HTTP 上
    # 必被反代掐断。
    def organize_snapshot(self) -> dict:
        """当前整理进度快照（前端轮询）。"""
        with self._organize_lock:
            snapshot = dict(self._organize_state)
            snapshot["counts"] = dict(self._organize_state.get("counts") or {})
            snapshot["details"] = list(self._organize_state.get("details") or [])
            return snapshot

    def organize_running(self) -> bool:
        thread = self._organize_thread
        return bool(thread and thread.is_alive())

    def start_organize(self, force: bool = False) -> dict:
        """启动一次后台整理（识别 + 搬运）。已在跑则直接返回当前快照。"""
        if self.organize_running():
            return {
                "started": False,
                "message": "整理已在进行中",
                "organize": self.organize_snapshot(),
            }
        if self.scan_running():
            return {
                "started": False,
                "message": "扫描进行中，请先停止扫描",
                "organize": self.organize_snapshot(),
            }
        if not self._source_dirs():
            return {
                "started": False,
                "message": "未配置扫描目录",
                "organize": self.organize_snapshot(),
            }
        self._organize_stop = threading.Event()
        self._organize_use_records = True
        with self._organize_lock:
            self._organize_state = {
                "state": "running",
                "phase": "scan",
                "total": 0,
                "done": 0,
                "current": "",
                "message": "正在按已识别记录准备整理…",
                "started_at": time.time(),
                "finished_at": None,
                "counts": {"dramas": 0, "done": 0, "skipped": 0, "failed": 0, "unrecognized": 0},
                "details": [],
            }
        self._organize_thread = threading.Thread(
            target=self._organize_worker, args=(force,), daemon=True, name="SdbkoOrganize"
        )
        self._organize_thread.start()
        return {"started": True, "message": "整理已启动", "organize": self.organize_snapshot()}

    def stop_organize(self) -> dict:
        if self._organize_stop is not None:
            self._organize_stop.set()
        with self._organize_lock:
            if self._organize_state.get("state") == "running":
                self._organize_state["state"] = "stopping"
                self._organize_state["message"] = "正在停止…"
        return {"stopped": True, "organize": self.organize_snapshot()}

    def _organize_worker(self, force: bool) -> None:
        """整理线程主体：识别阶段与搬运阶段共用一个进度条，逐部累积详情。"""
        stop = self._organize_stop

        def scan_progress(done: int, total: int, name: str, _item: dict) -> None:
            with self._organize_lock:
                state = self._organize_state
                if state.get("state") not in ("running", "stopping"):
                    return
                state["phase"] = "scan"
                state["total"] = total
                state["done"] = done
                state["current"] = name
                state["message"] = f"正在识别（{done}/{total}）…"

        def progress(index: int, total: int, drama: str, detail: dict) -> None:
            with self._organize_lock:
                state = self._organize_state
                if state.get("state") not in ("running", "stopping"):
                    return
                state["phase"] = "organize"
                state["total"] = total
                state["done"] = index
                state["current"] = drama
                counts = state.setdefault("counts", {})
                if detail.get("organized"):
                    counts["dramas"] = int(counts.get("dramas", 0)) + 1
                counts["done"] = int(counts.get("done", 0)) + int(detail.get("done") or 0)
                counts["skipped"] = int(counts.get("skipped", 0)) + int(detail.get("skipped") or 0)
                counts["failed"] = int(counts.get("failed", 0)) + int(detail.get("failed") or 0)
                if detail.get("unrecognized"):
                    counts["unrecognized"] = int(counts.get("unrecognized", 0)) + 1
                details = state.setdefault("details", [])
                details.append(detail)
                if len(details) > MAX_DETAIL_ITEMS:
                    del details[0]
                state["message"] = f"正在整理（{index}/{total}）…"

        try:
            self.organize_all(
                force=force,
                scan_progress=scan_progress,
                progress=progress,
                stop=stop,
                use_records=self._organize_use_records,
            )
            with self._organize_lock:
                stopped = stop is not None and stop.is_set()
                self._organize_state["state"] = "stopped" if stopped else "done"
                self._organize_state["phase"] = ""
                self._organize_state["current"] = ""
                self._organize_state["finished_at"] = time.time()
                counts = self._organize_state.get("counts") or {}
                self._organize_state["message"] = (
                    f"已手动停止（已处理 {len(self._organize_state.get('details') or [])} 部）"
                    if stopped
                    else (
                        f"整理完成：{counts.get('dramas', 0)} 部，文件成功 {counts.get('done', 0)}，"
                        f"跳过 {counts.get('skipped', 0)}，失败 {counts.get('failed', 0)}，"
                        f"未识别 {counts.get('unrecognized', 0)}"
                    )
                )
        except Exception as err:  # pragma: no cover
            logger.error(f"[整理] 线程异常：{err}\n{traceback.format_exc()}")
            with self._organize_lock:
                self._organize_state["state"] = "error"
                self._organize_state["phase"] = ""
                self._organize_state["message"] = f"整理失败：{err}"
                self._organize_state["finished_at"] = time.time()

    # ── 目录监控（快照比对，只处理新增/修改的文件） ────────────────
    #
    # 与宿主目录监控（app/monitor/monitor.py + snapshot.py + dispatcher.py）
    # 同一套实现语义：
    # 1. 监控启动后先建**基线快照**，「监控启动前已存在的文件」一律不处理，
    #    只处理基线之后新增/变化的剧目录（系统原话：「目录监控只处理新增和
    #    修改的文件，不会处理监控启动前已存在的文件」）；
    # 2. 每轮枚举源目录与快照比对（快照持久化到插件数据目录，重启不丢基线），
    #    只有新增/修改的目录进整理链；
    # 3. 目录指纹（文件数/总大小/最大 mtime）连续两轮一致才认为落盘稳定，
    #    等价于系统的文件稳定性等待 —— 下载中的目录不会被提前搬运；
    # 4. 未识别/整理失败的目录按周期重试，上限 60 次（同 dispatcher 的
    #    MAX_RETRY_ATTEMPTS），放弃后文件再变化会重新触发；
    # 5. 重复整理由整理历史 + 已整理集记录去重，与「强制整理」配置**无关**
    #    （监控调用恒 ignore_force，2026-10-23 用户明确「目录监控和强制整理
    #    无关，只监控新文件」）。
    MONITOR_SNAPSHOT_VERSION = 1
    MONITOR_RETRY_MAX = 60

    def _monitor_snapshot_file(self) -> Path:
        return Path(self.get_data_path()) / "monitor_snapshot.json"

    def _load_monitor_snapshot(self) -> Optional[dict]:
        try:
            return json.loads(self._monitor_snapshot_file().read_text("utf-8"))
        except FileNotFoundError:
            return None
        except Exception as err:  # noqa: BLE001 - 快照读失败按不存在处理（重建基线）
            logger.warning(f"[监控] 快照读取失败，将重建基线：{err}")
            return None

    def _save_monitor_snapshot(self, data: dict) -> None:
        try:
            self._monitor_snapshot_file().write_text(
                json.dumps(data, ensure_ascii=False), "utf-8"
            )
        except Exception as err:  # pragma: no cover
            logger.error(f"[监控] 快照保存失败：{err}")

    def _monitor_fingerprints(self) -> dict:
        """源目录下各剧目录的指纹 ``{path: "文件数:总大小:最大mtime"}``。"""
        source_dirs = self._source_dirs()
        if not source_dirs:
            return {}
        depth = safe_int(self._cfg(CONF_SCAN_DEPTH, 1), 1) or 1
        fps: dict = {}
        for d in organize.iter_drama_dirs(source_dirs, depth, excludes=[])[:MAX_SCAN_ITEMS]:
            fps[str(d)] = self._dir_fingerprint(d)
        return fps

    def _dir_fingerprint(self, d: Path) -> str:
        """单个剧目录的指纹 ``"文件数:总大小:最大mtime"``。"""
        files = size = 0
        mtime = 0.0
        try:
            for f in d.rglob("*"):
                if not f.is_file():
                    continue
                try:
                    st = f.stat()
                except OSError:  # pragma: no cover
                    continue
                files += 1
                size += st.st_size
                mtime = max(mtime, st.st_mtime)
        except OSError:  # pragma: no cover
            pass
        return f"{files}:{size}:{int(mtime)}"

    def _monitor_cycle(self) -> None:
        """监控一轮：比对快照 → 稳定判定 → 只处理新增/修改的目录。"""
        dirs = self._monitor_fingerprints()
        snap = self._load_monitor_snapshot()
        if not snap or snap.get("version") != self.MONITOR_SNAPSHOT_VERSION:
            self._save_monitor_snapshot({
                "version": self.MONITOR_SNAPSHOT_VERSION,
                "dirs": dirs,
                "pending": {},
            })
            logger.info(
                f"[监控] 基线快照已建立（{len(dirs)} 个剧目录），"
                "只处理之后新增/变化的文件"
            )
            return
        old: dict = snap.get("dirs") or {}
        # 目录已消失的，连带清掉待重试记录
        pending: dict = {
            p: v for p, v in (snap.get("pending") or {}).items() if p in dirs
        }
        ready: list = []
        for p, fp in dirs.items():
            changed = p not in old or old.get(p) != fp
            if not changed and p not in pending:
                continue  # 无变化也无待办：不处理（只处理新增/修改）
            ent = pending.get(p) or {}
            if ent.get("fp") == fp and not ent.get("retry"):
                ready.append(p)  # 变化后连续两轮指纹一致 → 落盘已稳定
            elif changed:
                pending[p] = {"fp": fp}  # 首次发现变化：等下一轮确认稳定
            elif int(ent.get("retries") or 0) < self.MONITOR_RETRY_MAX:
                ready.append(p)  # 上轮处理失败 → 重试
            else:
                pending.pop(p, None)  # 超过重试上限：放弃，文件再变会重新触发
                logger.warning(
                    f"[监控] 重试上限（{self.MONITOR_RETRY_MAX} 次），放弃：{Path(p).name}"
                )
        results = self._monitor_process(ready)
        for p, outcome in results.items():
            if outcome == "ok":
                pending.pop(p, None)
            else:
                ent = pending.get(p) or {}
                ent["fp"] = dirs.get(p, ent.get("fp"))
                ent["retries"] = int(ent.get("retries") or 0) + 1
                ent["retry"] = True
                pending[p] = ent
        self._save_monitor_snapshot({
            "version": self.MONITOR_SNAPSHOT_VERSION,
            "dirs": dirs,
            "pending": pending,
        })

    def _monitor_process(self, paths: list) -> dict:
        """处理稳定的新增/修改目录，返回 ``{path: "ok"|"retry"}``。"""
        results: dict = {}
        if not paths:
            return results
        records = self._record_store()
        prior: dict = {}
        done_paths: set = set()
        ignored_paths: set = set()
        if records is not None:
            try:
                prior = {
                    str(r.get("path") or ""): r
                    for r in records.all(limit=MAX_STORE_SCAN)
                }
            except Exception:  # noqa: BLE001
                prior = {}
            try:
                done_paths = records.done_paths()
            except Exception:  # noqa: BLE001
                done_paths = set()
            try:
                ignored_paths = records.ignored_paths()
            except Exception:  # noqa: BLE001
                ignored_paths = set()
        organized = 0
        for p in paths:
            if p in ignored_paths:
                results[p] = "ok"  # 已删除：永久跳过（同扫描口径）
                continue
            if p in done_paths:
                results[p] = "ok"  # 整理完成：跳过（同扫描口径）
                continue
            # 已识别过的直接用记录里的身份，不重新识别；没记录的才走识别
            row = prior.get(p) or {}
            media_id = str(row.get("media_id") or "").strip()
            title = str(row.get("title") or "").strip()
            if media_id or title:
                decision = MatchDecision(
                    matcher.ACTION_ADOPT,
                    candidate=matcher.Candidate(
                        media_id=media_id,
                        title=title,
                        year=safe_int(row.get("year"), 0) or None,
                        episode_count=safe_int(row.get("episode_count"), 0) or 0,
                    ),
                )
            else:
                decision = self.recognize_drama(Path(p).name)
            if not decision.adopted or not decision.candidate:
                logger.info(f"[监控] 目录暂未识别（将重试）：{Path(p).name}")
                results[p] = "retry"
                continue
            res = self.organize_drama(p, decision, force=False, ignore_force=True)
            if res.get("success"):
                organized += 1
                results[p] = "ok"
                logger.info(
                    f"[监控] 已处理新增/变化目录：{Path(p).name} → "
                    f"{res.get('dest_dir') or ''}"
                    f"（整理 {res.get('done', 0)}，跳过 {res.get('skipped', 0)}，"
                    f"失败 {res.get('failed', 0)}）"
                )
            else:
                logger.warning(
                    f"[监控] 处理失败（将重试）：{Path(p).name} - {res.get('error')}"
                )
                results[p] = "retry"
        if organized and bool(self._cfg(CONF_NOTIFY, True)):
            self.post_message(
                mtype=NotificationType.Organize,
                title="【短剧百科整理】目录监控",
                text=f"监控到 {len(paths)} 个新增/变化目录，已整理 {organized} 个",
            )
        return results

    def _start_monitor(self) -> None:
        if self._monitor_thread and self._monitor_thread.is_alive():
            return
        if getattr(self, "_watch_thread", None) and self._watch_thread.is_alive():
            return
        mode = str(self._cfg(CONF_MONITOR_MODE, MONITOR_MODE_WATCH) or MONITOR_MODE_WATCH)
        if mode == MONITOR_MODE_WATCH and self._start_watch():
            return
        # 事件监听不可用（watchdog 缺失 / 源目录为空）→ 回退轮询快照比对
        self._monitor_stop = threading.Event()
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop, daemon=True, name="SdbkoMonitor"
        )
        self._monitor_thread.start()
        logger.info("[监控] 目录监控线程已启动（轮询模式）")

    def _stop_monitor(self) -> None:
        self._stop_watch_observer()
        if self._monitor_stop:
            self._monitor_stop.set()
        watch_thread = getattr(self, "_watch_thread", None)
        if watch_thread and watch_thread.is_alive():
            watch_thread.join(timeout=5)
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=5)
        self._monitor_thread = None
        self._watch_thread = None
        self._monitor_stop = None

    # ── 事件监听（watchdog，与系统 LocalDirectoryWatcher 同思路） ────
    #
    # 文件事件只做一件事：把事件所属的剧目录标记为「脏」；真正的整理判定由
    # 判定线程做 —— 目录进入安静期（不再收到新事件）后采样指纹，与
    # WATCH_STABLE_GAP 秒前采样一致才算落盘稳定，稳定即送 _monitor_process
    # （已识别直接用记录身份、done 跳过、ignore_force 恒尊重历史）。
    # watchdog 缺失或启动失败自动回退轮询模式。
    WATCH_QUIET_SECONDS = 10.0  # 事件安静期：多久没有新事件才开始判定稳定
    WATCH_STABLE_GAP = 30.0     # 两次指纹采样的最小间隔（间隔内指纹一致才稳定）
    WATCH_TICK_SECONDS = 5.0    # 判定线程节拍
    _WATCH_TEMP_SUFFIXES = (".aria2", ".part", ".tmp", ".!ut", ".!qb", ".crdownload")

    def _watch_temp_file(self, p: Path) -> bool:
        """下载器临时文件不触发脏标记（指纹里也不会有它们）。"""
        name = p.name
        return name.startswith(".") or p.suffix.casefold() in self._WATCH_TEMP_SUFFIXES

    def _drama_dir_for(self, event_path) -> Optional[Path]:
        """把事件文件路径映射到所属剧目录（源根下第 N 层，N=扫描层级）。"""
        path = Path(event_path)
        depth = safe_int(self._cfg(CONF_SCAN_DEPTH, 1), 1) or 1
        for root in self._source_dirs():
            try:
                rel = path.relative_to(root)
            except ValueError:
                continue
            parts = rel.parts
            if not parts:
                continue
            return Path(root).joinpath(*parts[:min(depth, len(parts))])
        return None

    def _mark_dirty(self, event_path) -> None:
        """文件事件 → 标记所属剧目录为脏（只改内存，不做任何 IO）。"""
        try:
            p = Path(event_path)
            if self._watch_temp_file(p):
                return
            library_dir = self._library_dir()
            if library_dir and str(p).startswith(str(library_dir)):
                return  # 目标库自己的写入不回环触发
            drama = self._drama_dir_for(p)
            if drama is None:
                return
            with self._watch_lock:
                ent = self._watch_dirty.get(str(drama))
                if ent is None:
                    self._watch_dirty[str(drama)] = {
                        "last_event": time.time(), "fp": None,
                        "checked_at": 0.0, "retries": 0,
                    }
                    logger.info(f"[监控] 发现文件变化：{drama.name}")
                else:
                    ent["last_event"] = time.time()
                    ent["fp"] = None  # 又有新变化：推倒重新采样
        except Exception:  # noqa: BLE001 - 事件回调绝不能抛
            pass

    def _start_watch(self) -> bool:
        try:
            from watchdog.events import FileSystemEventHandler
            from watchdog.observers import Observer
        except Exception as err:  # noqa: BLE001
            logger.warning(f"[监控] watchdog 不可用（{err}），回退轮询模式")
            return False
        roots = self._source_dirs()
        if not roots:
            return False
        plugin = self

        class _Handler(FileSystemEventHandler):
            def on_created(self, event):
                if not event.is_directory:
                    plugin._mark_dirty(event.src_path)

            def on_modified(self, event):
                if not event.is_directory:
                    plugin._mark_dirty(event.src_path)

            def on_moved(self, event):
                if not event.is_directory:
                    plugin._mark_dirty(event.dest_path)

        observer = Observer(timeout=1.0)
        try:
            for root in roots:
                observer.schedule(_Handler(), root, recursive=True)
            observer.daemon = True
            observer.start()
        except Exception as err:  # noqa: BLE001
            logger.warning(f"[监控] 事件监听启动失败（{err}），回退轮询模式")
            return False
        self._watch_observer = observer
        self._watch_dirty = {}
        self._monitor_stop = threading.Event()
        self._watch_thread = threading.Thread(
            target=self._watch_loop, daemon=True, name="SdbkoWatch"
        )
        self._watch_thread.start()
        logger.info(f"[监控] 事件监听已启动（watchdog，{len(roots)} 个源目录）")
        return True

    def _stop_watch_observer(self) -> None:
        observer = getattr(self, "_watch_observer", None)
        if observer is not None:
            try:
                observer.stop()
                observer.join(timeout=5)
            except Exception:  # noqa: BLE001
                pass
            self._watch_observer = None

    def _watch_loop(self) -> None:
        while not (self._monitor_stop and self._monitor_stop.is_set()):
            try:
                self._watch_tick()
            except Exception as err:  # pragma: no cover
                logger.error(f"[监控] 事件判定异常：{err}\n{traceback.format_exc()}")
            if self._monitor_stop:
                self._monitor_stop.wait(self.WATCH_TICK_SECONDS)
        self._stop_watch_observer()

    def _watch_tick(self) -> None:
        """判定一轮：安静期 → 间隔采样 → 指纹一致才整理。"""
        if not self._enabled:
            return
        now = time.time()
        with self._watch_lock:
            dirty = dict(self._watch_dirty)
        if not dirty:
            return
        ready: list = []
        for path, ent in dirty.items():
            d = Path(path)
            if not d.is_dir():
                with self._watch_lock:
                    self._watch_dirty.pop(path, None)
                continue  # 目录已删（整理完移走等），不再跟踪
            if now - ent.get("last_event", 0) < self.WATCH_QUIET_SECONDS:
                continue  # 还有新事件进来，等安静
            fp = ent.get("fp")
            if fp is None:
                ent["fp"] = self._dir_fingerprint(d)
                ent["checked_at"] = now
                with self._watch_lock:
                    self._watch_dirty[path] = ent
                continue  # 第一次采样，下轮再比
            if now - ent.get("checked_at", 0) < self.WATCH_STABLE_GAP:
                continue
            cur = self._dir_fingerprint(d)
            if cur == fp:
                ready.append(path)  # 安静期 + 两次采样一致 → 落盘稳定
            else:
                ent["fp"] = cur  # 还在变，重新采样
                ent["checked_at"] = now
                with self._watch_lock:
                    self._watch_dirty[path] = ent
        if not ready or self.organize_running():
            return  # 手动整理进行中，下轮再判
        results = self._monitor_process(ready)
        with self._watch_lock:
            for p, outcome in results.items():
                if outcome == "ok":
                    self._watch_dirty.pop(p, None)
                    continue
                ent = self._watch_dirty.get(p) or {}
                ent["retries"] = int(ent.get("retries") or 0) + 1
                if int(ent["retries"]) >= self.MONITOR_RETRY_MAX:
                    self._watch_dirty.pop(p, None)
                    logger.warning(
                        f"[监控] 重试上限（{self.MONITOR_RETRY_MAX} 次），放弃：{Path(p).name}"
                    )
                else:
                    ent["fp"] = None  # 重新采样再判
                    ent["last_event"] = time.time()  # 重新等安静期
                    self._watch_dirty[p] = ent

    def _monitor_loop(self) -> None:
        while not (self._monitor_stop and self._monitor_stop.is_set()):
            interval = max(
                MONITOR_INTERVAL_FLOOR,
                min(MONITOR_INTERVAL_CEIL, safe_int(self._cfg(CONF_MONITOR_INTERVAL, 60), 60) or 60),
            )
            try:
                if self._enabled and not self.organize_running():
                    self._monitor_cycle()
            except Exception as err:  # pragma: no cover
                logger.error(f"[监控] 周期异常：{err}\n{traceback.format_exc()}")
            # 分段 sleep，便于快速响应停止信号
            waited = 0
            while waited < interval and not (self._monitor_stop and self._monitor_stop.is_set()):
                if self._monitor_stop:
                    self._monitor_stop.wait(min(5, interval - waited))
                waited += 5

    # ── 状态 ───────────────────────────────────────────────────────
    def get_status(self) -> dict:
        source_ok = False
        try:
            source_ok = self._probe_source()
        except Exception:  # pragma: no cover
            source_ok = False
        return {
            "enabled": self._enabled,
            "source": BAIKE_MEDIA_SOURCE,
            "source_provider": BAIKE_SOURCE_PLUGIN_ID,
            "source_ready": source_ok,
            "library_dir": self._library_dir(),
            "source_dirs": self._source_dirs(),
            "transfer_type": self._cfg(CONF_TRANSFER_TYPE, "move"),
            "episode_width": safe_int(self._cfg(CONF_EPISODE_WIDTH, 2), 2) or 2,
            "scrape_enabled": bool(self._cfg(CONF_SCRAPE_ENABLED, True)),
            "force_transfer": bool(self._cfg(CONF_FORCE_TRANSFER, False)),
            "monitor_enabled": bool(self._cfg(CONF_MONITOR_ENABLED, False)),
            "history_backend": "TransferHistoryOper",
            "store_available": store.store_available(),
            "note": "自包含整理（不走 TransferChain），历史写系统整理历史",
        }

    # ── API handlers ───────────────────────────────────────────────
    #
    # ⚠️ 参数必须**显式声明**成普通形参（``path: str = ""``）。
    # 写成 ``def api_x(self, request=None)`` 时 FastAPI 不会注入 ``Request`` 对象，
    # 只会当成一个名叫 request 的可选 query 参数 → 永远 None，query 参数全读不到
    # （实测：/dirs/browse?path=/media 照样回退到根目录）。
    def api_status(self) -> dict:
        return {"success": True, "data": self.get_status()}

    def api_scan(self) -> dict:
        """扫描进度快照（前端按钮点完轮询这个）。"""
        try:
            return {"success": True, "data": self.scan_snapshot()}
        except Exception as err:  # pragma: no cover
            return {"success": False, "message": str(err)}

    def api_scan_start(self) -> dict:
        """启动后台扫描：只识别、不搬运（同步扫描会拖到 HTTP 超时）。"""
        try:
            return {"success": True, "data": self.start_scan()}
        except Exception as err:  # pragma: no cover
            logger.error(f"[API] scan/start 异常：{err}\n{traceback.format_exc()}")
            return {"success": False, "message": str(err)}

    def api_scan_stop(self) -> dict:
        try:
            return {"success": True, "data": self.stop_scan()}
        except Exception as err:  # pragma: no cover
            return {"success": False, "message": str(err)}

    def api_organize(
        self,
        path: str = "",
        force: str = "",
        media_id: str = "",
        title: str = "",
        year: str = "",
        episode_count: str = "",
        library_dir: str = "",
        transfer_type: str = "",
        season: str = "",
        manual: str = "",
    ) -> dict:
        """整理入口（一个接口两种形态）。

        * **传了 ``path``**：整理单剧，同步返回（一部剧够快，撑不到反代超时）。
          ``media_id`` / ``title`` / ``year`` 表示**人工指定身份**（面板「重新整理」
          与「人工处理」用），``library_dir`` / ``transfer_type`` 表示**指定目标库
          与搬运方式**（留空则用配置值），``season`` 表示**手动指定季号**（留空
          沿用「一季一个剧目录、内部恒 Season 1」，2026-11-03 用户要求）。
          ``manual=1`` 表示**人工指定名称**（2026-11-04 用户要求）：百科上没有的
          剧，只按用户给的 ``title``（+ ``year`` / ``season``）整理，不依赖识别、
          不刮削 —— 此时必须带 ``title``。
        * **不传 ``path``**：启动后台整理全部，立刻返回（真正的结果去 GET /organize 拿）。
          ⚠️ 这里曾经是同步 ``organize_all`` —— 130 部剧跑几分钟，反代先超时，
          前端只看到 502（2026-10-23 实测），故改为后台任务。
        """
        try:
            force_flag = str(force).lower() in ("1", "true", "yes")
            target = (path or "").strip()
            if target:
                media = (media_id or "").strip()
                manual_named = str(manual).lower() in ("1", "true", "yes")
                if media:
                    decision = MatchDecision(
                        matcher.ACTION_ADOPT,
                        candidate=matcher.Candidate(
                            media_id=media,
                            title=(title or "").strip() or Path(target).name,
                            year=safe_int(year),
                            # 搜索候选带的集数（人工处理弹窗传进来）；不传则回落
                            # 数据源词条自己的值（2026-10-23「重生1982 手动处理后
                            # 集数怎么没有」：手动链路曾把它弄丢）
                            episode_count=safe_int(episode_count) or None,
                        ),
                        reason="人工指定身份",
                    )
                elif manual_named and (title or "").strip():
                    # 人工指定名称：无百科身份，media_id 留空（organize_drama
                    # 对该 reason 的无 id 候选放行，刮削跳过）
                    decision = MatchDecision(
                        matcher.ACTION_ADOPT,
                        candidate=matcher.Candidate(
                            media_id="",
                            title=(title or "").strip(),
                            year=safe_int(year) or None,
                            episode_count=safe_int(episode_count) or None,
                        ),
                        reason="人工指定名称",
                    )
                else:
                    decision = self.recognize_drama(Path(target).name)
                res = self.organize_drama(
                    target,
                    decision,
                    force=force_flag,
                    library_dir=(library_dir or "").strip() or None,
                    transfer_type=(transfer_type or "").strip() or None,
                    season=safe_int(season, 0) or None,
                )
                if not res.get("success"):
                    # 信封里带上原因：前端直接把 message 显示出来（「整理失败：未配置…」）
                    return {
                        "success": False,
                        "message": res.get("error") or "整理失败",
                        "data": res,
                    }
                return {"success": True, "data": res}
            return {"success": True, "data": self.start_organize(force=force_flag)}
        except Exception as err:  # pragma: no cover
            logger.error(f"[API] organize 异常：{err}\n{traceback.format_exc()}")
            return {"success": False, "message": str(err)}

    def api_organize_snapshot(self) -> dict:
        """整理进度快照（前端按钮点完轮询这个）。"""
        try:
            return {"success": True, "data": self.organize_snapshot()}
        except Exception as err:  # pragma: no cover
            return {"success": False, "message": str(err)}

    def api_organize_start(self, force: str = "") -> dict:
        """启动后台整理（识别 + 搬运）。"""
        try:
            force_flag = str(force).lower() in ("1", "true", "yes")
            return {"success": True, "data": self.start_organize(force=force_flag)}
        except Exception as err:  # pragma: no cover
            logger.error(f"[API] organize/start 异常：{err}\n{traceback.format_exc()}")
            return {"success": False, "message": str(err)}

    def api_organize_stop(self) -> dict:
        try:
            return {"success": True, "data": self.stop_organize()}
        except Exception as err:  # pragma: no cover
            return {"success": False, "message": str(err)}

    def api_preview(
        self,
        path: str = "",
        title: str = "",
        year: str = "",
        library_dir: str = "",
        media_id: str = "",
        season: str = "",
    ) -> dict:
        """按指定身份/目标库**预演**整理计划：将搬哪些文件、搬到哪、集号多少。

        面板「重新整理」在真正动手前调它 —— 「可指定」的意义在于**先看清楚再执行**：
        换目标库 / 换身份 / 换季号后目标路径与集号会变，先列出来给用户确认。
        """
        try:
            source = (path or "").strip()
            if not source:
                return {"success": False, "message": "缺少 path 参数"}
            library = (library_dir or "").strip() or self._library_dir()
            if not library:
                return {"success": False, "message": "未配置目标库目录"}
            name = (title or "").strip() or Path(source).name
            # 记录库里没年份时存的是 0：0 与空一样按「无年份」处理（目标目录不带 (年)）
            drama_year: Optional[int] = safe_int(year) if (year or "").strip() else None
            if not drama_year:
                drama_year = None
            width = safe_int(self._cfg(CONF_EPISODE_WIDTH, 2), 2) or 2
            auto_rename = bool(self._cfg(CONF_AUTO_RENAME_EPISODE, True))
            # 季号从**源数据**取（与 organize_drama 同口径）：有 media_id 按 id
            # 直取（不联网），否则按剧名识别一次；数据源不给 season 回落 1
            info = self._resolve_media(title=name, media_id=(media_id or "").strip())
            # 剧名以数据源识别结果为准（用户没手填 title 时）：站点一季一条
            # 词条（``隐身侍卫第二季``），剥季号后缀回基名，多季并入同一剧目录
            raw_title = str(getattr(info, "title", "") or "").strip() if info else ""
            plan_title = (title or "").strip() or raw_title or name
            plan_title, title_season, title_year = naming.parse_title_identity(plan_title)
            if not drama_year:
                drama_year = safe_int(getattr(info, "year", None), 0) or title_year or None
            # 库内季号：默认 1（一季一个独立剧目录，2026-10-23 用户定稿，目录内
            # 统一 Season 1 / S01Exx）；手动指定季号时按指定值预演，路径随之变
            manual_season = safe_int(season, 0)
            season_no = max(1, min(99, manual_season)) if manual_season else 1
            exists = Path(source).is_dir()
            plans = organize.plan_files(
                Path(source),
                title=plan_title,
                year=drama_year,
                library_dir=library,
                episode_width=width,
                auto_rename=auto_rename,
                season=season_no,
            )
            items = [
                {
                    "src": str(src),
                    "src_name": src.name,
                    "target": str(target),
                    "target_name": target.name,
                    "episode": episode,
                }
                for src, target, episode in plans[:MAX_PREVIEW_ITEMS]
            ]
            return {
                "success": True,
                "data": {
                    "exists": exists,
                    "library_dir": library,
                    "title": plan_title,
                    "year": drama_year,
                    "season": season_no,
                    # 解析出的总集数（识别出口的 MediaInfo 兜底；搜索候选常缺）
                    "episode_count": (
                        safe_int(getattr(info, "number_of_episodes", None), 0)
                        or safe_int(getattr(info, "episode_count", None), 0)
                        or 0
                    ),
                    "count": len(plans),
                    "items": items,
                },
            }
        except Exception as err:  # pragma: no cover
            logger.error(f"[API] preview 异常：{err}\n{traceback.format_exc()}")
            return {"success": False, "message": str(err)}

    def api_details(self, path: str = "", dest: str = "") -> dict:
        """整理详情（面板「整理详情」窗口的唯一数据源）。

        * 传 ``path``（源目录）或 ``dest``（目标剧目录）→ **单剧**文件级整理记录：
          哪几个文件搬到了哪、什么方式、什么时间（谁写的都算，含宿主内置短剧处理器）。
        * 都不传 → **本次整理运行**的详情：逐部剧的结果（剧名 / 目标目录 /
          成功·跳过·失败文件数 / 失败原因）。
        """
        try:
            source = (path or "").strip()
            dest_dir = (dest or "").strip()
            if source and not dest_dir:
                records = self._record_store()
                if records is not None:
                    for item in records.all(limit=MAX_STORE_SCAN):
                        if item.get("path") == source:
                            dest_dir = item.get("dest_dir") or ""
                            break
            if source or dest_dir:
                items = history.list_records_by_dest(dest_dir)
                return {
                    "success": True,
                    "data": {
                        "scope": "drama",
                        "dest_dir": dest_dir,
                        "count": len(items),
                        "items": items,
                    },
                }
            snapshot = self.organize_snapshot()
            return {
                "success": True,
                "data": {
                    "scope": "run",
                    "state": snapshot.get("state", "idle"),
                    "message": snapshot.get("message", ""),
                    "counts": snapshot.get("counts") or {},
                    "details": snapshot.get("details") or [],
                },
            }
        except Exception as err:  # pragma: no cover
            logger.error(f"[API] details 异常：{err}\n{traceback.format_exc()}")
            return {"success": False, "message": str(err)}

    def search_candidates(self, keyword: str, limit: int = 10) -> list[dict]:
        """按关键词搜短剧百科候选（未识别目录人工处理用，走站点搜索模块）。

        关键词原样送入搜索（不剥发布尾巴），与识别口径一致。
        同样按插件 id 精确直调数据源，不走宿主广播、不回退。
        """
        query = str(keyword or "").strip()
        if not query:
            return []
        func = self._source_method("search_medias")
        if func is None:
            return []
        metas = func(
            meta=MetaInfo(title=query),
            media_source=BAIKE_MEDIA_SOURCE,
        )
        result: list[dict] = []
        for meta in (metas or [])[: max(1, limit)]:
            candidate = self._media_to_candidate(meta)
            if not candidate.media_id:
                continue
            result.append(
                {
                    "media_id": candidate.media_id,
                    "title": candidate.title,
                    "year": candidate.year,
                    "episode_count": candidate.episode_count,
                }
            )
        return result

    def api_search(self, keyword: str = "", limit: str = "10") -> dict:
        try:
            items = self.search_candidates((keyword or "").strip(), safe_int(limit, 10) or 10)
            return {"success": True, "data": {"count": len(items), "items": items}}
        except Exception as err:  # pragma: no cover
            logger.error(f"[API] search 异常：{err}")
            return {"success": False, "message": str(err)}

    def api_records(self, title: str = "") -> dict:
        try:
            records = history.list_records(title=(title or "").strip() or None, limit=200)
            return {"success": True, "data": {"count": len(records), "items": records}}
        except Exception as err:  # pragma: no cover
            return {"success": False, "message": str(err)}

    def api_records_delete(self, src: str = "") -> dict:
        try:
            key = (src or "").strip()
            if not key:
                return {"success": False, "message": "缺少 src 参数"}
            ok = history.delete_by_src(key)
            return {"success": ok, "message": "已删除" if ok else "未找到记录"}
        except Exception as err:  # pragma: no cover
            return {"success": False, "message": str(err)}

    def _heal_flags(self, items: list[dict]) -> None:
        """把记录库里**过期的标志**就地补探一遍（每次最多补 20 行）。

        为什么需要：`dest_exists` / `transferred` 是**扫描期快照**，写下去就不再更新。
        历史筛选契约修好之前写的行全是 `transferred=0` —— 面板上「已整理」恒为 0，
        「重新整理」按钮一条都出不来（2026-10-23 实测）。逐个目录重新探一次很贵
        （每行一次历史查询），所以每次读列表只补一小批，面板多刷几次自然收敛。
        """
        records = self._record_store()
        if records is None:
            return
        budget = 20
        for item in items:
            if budget <= 0:
                break
            dest = item.get("dest_dir") or ""
            if not dest:
                continue
            exists = Path(dest).is_dir()
            patch: dict = {}
            if exists and not item.get("dest_exists"):
                item["dest_exists"] = True
                patch["dest_exists"] = True
            # 补「已刮削」标志（2026-10-23「未刮削的原因」）：scraped 是**行级**
            # 快照，兄弟源目录（同一目标剧目录）触发刮削时只回写自己那行，
            # 其余行的标志就停在 false。目标目录里实际有 nfo/海报就算刮过，
            # 纯文件系统探测，一次 stat 开销可忽略，不占历史查询预算。
            if exists and not item.get("scraped") and organize.is_scraped(Path(dest)):
                item["scraped"] = True
                patch["scraped"] = True
            # 只补「目标已存在但还没标已整理」的行：已标的不必再查
            if exists and not item.get("transferred"):
                budget -= 1
                if history.has_transferred_dest(dest):
                    item["transferred"] = True
                    patch["transferred"] = True
            # 补算「已整理集数」：本次改动前的旧行 / 宿主内置处理器整理的行
            # 没有这个值（=0），按目标剧目录的整理历史去重统计一次
            if exists and item.get("transferred") and not item.get("organized_episodes"):
                budget -= 1
                count = history.count_distinct_episodes(dest)
                if count:
                    item["organized_episodes"] = count
                    patch["organized_episodes"] = count
            if patch:
                patch["path"] = item.get("path") or ""
                try:
                    records.upsert(patch)
                except Exception as err:  # pragma: no cover - 补标志失败不影响展示
                    logger.warning(f"[记录库] 补标志失败（忽略）：{err}")

    def api_store_complete(self, path: str = "", value: str = "1") -> dict:
        """手动标记 / 取消「整理完成」（整理中的剧人工敲定）。"""
        records = self._record_store()
        if records is None:
            return {"success": False, "message": "记录库不可用"}
        if not path:
            return {"success": False, "message": "缺少 path 参数"}
        try:
            mark = str(value) not in ("0", "false", "False", "")
            ok = records.mark_completed(path, value=mark)
            message = ("已取消整理完成标记" if not mark else "已标记整理完成") if ok else "记录不存在"
            return {"success": ok, "message": message}
        except Exception as err:  # pragma: no cover
            return {"success": False, "message": str(err)}

    def api_store(self) -> dict:
        """记录库：四类统计（已识别/已整理/未识别/未刮削）+ 全部剧记录。"""
        records = self._record_store()
        if records is None:
            return {"success": True, "data": {"available": False, "stats": {
                "recognized": 0, "pending": 0, "transferred": 0, "completed": 0,
                "unrecognized": 0, "unscraped": 0,
            }, "items": []}}
        try:
            items = [
                row for row in records.all(limit=500)
                if not row.get("ignored")
            ]
            self._heal_flags(items)
            # 统计直接用**补过标志的** items，别再读一次 DB 拿旧值。
            # done 口径与 store.as_dict 一致：手动标记过，或已整理集数对齐数据源集数。
            def _is_done(it: dict) -> bool:
                return bool(it.get("completed")) or (
                    (it.get("episode_count") or 0) > 0
                    and (it.get("organized_episodes") or 0) >= it["episode_count"]
                )

            stats = {
                "recognized": sum(1 for i in items if i.get("state") == "recognized"),
                # 「待整理」= 已识别但还没整理过（target 目录都不存在），让
                # 已识别 = 待整理 + 整理中 + 整理完成 恒等，面板数字自洽
                "pending": sum(
                    1
                    for i in items
                    if i.get("state") == "recognized" and not i.get("transferred")
                ),
                # 「整理中」= 搬过但集数还没对齐（原「已整理」口径，2026-10-23 改名）
                "transferred": sum(
                    1 for i in items if i.get("transferred") and not _is_done(i)
                ),
                "completed": sum(1 for i in items if _is_done(i)),
                "unrecognized": sum(1 for i in items if i.get("state") != "recognized"),
                "unscraped": sum(1 for i in items if i.get("dest_exists") and not i.get("scraped")),
            }
            return {
                "success": True,
                "data": {"available": True, "stats": stats, "items": items},
            }
        except Exception as err:  # pragma: no cover
            logger.error(f"[API] store 异常：{err}\n{traceback.format_exc()}")
            return {"success": False, "message": str(err)}

    def api_store_delete(self, path: str = "") -> dict:
        records = self._record_store()
        if records is None:
            return {"success": False, "message": "记录库不可用"}
        try:
            key = (path or "").strip()
            if not key:
                return {"success": False, "message": "缺少 path 参数"}
            ok = records.delete(key)
            return {"success": ok, "message": "已删除" if ok else "未找到记录"}
        except Exception as err:  # pragma: no cover
            return {"success": False, "message": str(err)}

    def api_delete_history(self) -> dict:
        """删除任务台账：Emby 删除联动执行过的清理记录（最新在前）。"""
        try:
            history = self.get_data("delete_history") or []
            if not isinstance(history, list):
                history = []
            return {"success": True, "data": {"items": history[:100]}}
        except Exception as err:  # pragma: no cover
            return {"success": False, "message": str(err)}

    def api_delete_restore(self, time: str = "") -> dict:
        """恢复一条删除任务：从台账移除并清掉该剧的墓碑标记。"""
        key = (time or "").strip()
        if not key:
            return {"success": False, "message": "缺少 time 参数"}
        try:
            history = self.get_data("delete_history") or []
            if not isinstance(history, list):
                history = []
            target = next((item for item in history if str(item.get("time") or "") == key), None)
            if target is None:
                return {"success": False, "message": "未找到该删除任务"}
            records = self._record_store()
            restored = False
            if records is not None:
                # 按剧名找回墓碑记录（记录主键是源目录，台账里没存 path 时按标题匹配）
                for row in records.all(limit=500):
                    if not row.get("ignored"):
                        continue
                    if str(row.get("title") or "") == str(target.get("title") or ""):
                        records.mark_ignored(str(row.get("path") or ""), value=False)
                        restored = True
            remaining = [item for item in history if str(item.get("time") or "") != key]
            self.save_data("delete_history", remaining)
            return {
                "success": True,
                "message": "已恢复（该剧重新纳入扫描）" if restored else "已从台账移除",
            }
        except Exception as err:  # pragma: no cover
            return {"success": False, "message": str(err)}

    def api_store_clear(self) -> dict:
        records = self._record_store()
        if records is None:
            return {"success": False, "message": "记录库不可用"}
        try:
            count = records.clear()
            return {"success": True, "message": f"已清空 {count} 条记录", "data": {"count": count}}
        except Exception as err:  # pragma: no cover
            return {"success": False, "message": str(err)}

    def api_scrape(self, path: str = "", dest: str = "") -> dict:
        """立即刮削：传源目录 path（记录库键）或直接传目标目录 dest。

        前端对「目标已存在但未刮削」的行发起；走后端 :meth:`scrape_drama`。
        """
        try:
            records = self._record_store()
            source_path = (path or "").strip()
            dest_dir = (dest or "").strip()
            title = ""
            year: Optional[int] = None
            media_id = ""
            drama_name = ""
            if source_path and records is not None:
                # 从记录库取这条剧的身份与目标目录
                for item in records.all(limit=500):
                    if item.get("path") == source_path:
                        title = item.get("title") or ""
                        year = item.get("year")
                        media_id = item.get("media_id") or ""
                        drama_name = item.get("drama") or ""
                        if not dest_dir:
                            dest_dir = item.get("dest_dir") or ""
                        break
            if not dest_dir:
                return {"success": False, "message": "缺少目标目录（dest）或记录库无此记录"}
            result = self.scrape_drama(
                dest_dir,
                title=title,
                year=year,
                media_id=media_id,
                source_path=source_path,
            )
            if not title:
                result["drama"] = drama_name
            return {"success": bool(result.get("success")), "data": result}
        except Exception as err:  # pragma: no cover
            logger.error(f"[API] scrape 异常：{err}\n{traceback.format_exc()}")
            return {"success": False, "message": str(err)}

    def api_repair(self) -> dict:
        """补图进度快照（面板「补封面」按钮轮询）。"""
        return {"success": True, "data": self.repair_snapshot()}

    def api_repair_start(self, library_dir: str = "") -> dict:
        """启动后台补图：补齐媒体库里缺失 / 残图（52 字节占位图）的封面。

        只补图，不动集文件、不重写已有 tvshow.nfo / season.nfo；已正常的产物跳过。
        2026-11-06 用户「裂图时期整理的历史记录现在没封面」。
        """
        try:
            return {"success": True, "data": self.start_repair(library_dir=(library_dir or "").strip())}
        except Exception as err:  # pragma: no cover
            logger.error(f"[API] repair 异常：{err}\n{traceback.format_exc()}")
            return {"success": False, "message": str(err)}

    def api_repair_stop(self) -> dict:
        return {"success": True, "data": self.stop_repair()}

    def api_stop(self) -> dict:
        self._stop_monitor()
        return {"success": True, "message": "目录监控已停止"}

    def api_dirs_browse(self, path: str = "") -> dict:
        """浏览一层目录（页面选目录用）：当前路径、上级、子目录候选。"""
        try:
            return {"success": True, "data": dirs.browse((path or "").strip())}
        except Exception as err:  # pragma: no cover
            return {"success": False, "message": str(err)}

    def api_dirs_options(self) -> dict:
        """配置页下拉候选：系统配置里的下载目录、媒体库目录与下载器。"""
        try:
            return {
                "success": True,
                "data": {
                    "sources": self._source_dir_options(),
                    "libraries": self._library_dir_options(),
                    "downloaders": self._downloader_options(),
                },
            }
        except Exception as err:  # pragma: no cover
            return {"success": False, "message": str(err)}

    def _downloader_options(self) -> list[dict]:
        """下载器候选（联动删除的「指定下载器」用）。"""
        try:
            from app.sdk.services import DownloaderHelper

            services = DownloaderHelper().get_services() or {}
            return [{"title": str(name), "value": str(name)} for name in services]
        except Exception as err:  # noqa: BLE001
            logger.warning(f"[下载器] 读取下载器候选失败：{err}")
            return []
