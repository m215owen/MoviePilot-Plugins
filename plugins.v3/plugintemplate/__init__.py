"""
MoviePilot V3 插件开发模板（后端主类）。

这是一个可直接运行、可二次开发的完整骨架，覆盖了 MoviePilot V3 插件的常用扩展点：

- 生命周期：``init_plugin`` / ``get_state`` / ``stop_service``
- 页面：``get_form``（Vue 模式返回空）/ ``get_page`` / ``get_dashboard`` / ``get_dashboard_meta``
- 渲染模式：``get_render_mode`` 返回 ``("vue", "dist/assets")``，前端为 Vue 模块联邦组件
- 侧栏入口：``get_sidebar_nav``（演示单插件多入口）
- 后台能力：``get_service``（定时任务）/ ``get_command``（远程命令）/ ``get_api``（HTTP 接口）
- 事件联动：监听 ``EventType.PluginAction``
- 高级能力：``get_actions``（工作流动作）/ ``get_agent_tools``（智能体工具）
- 数据持久化：``save_data`` / ``get_data`` / ``get_data_path``

业务示例：按配置的 cron 周期执行一次“任务”，记录执行时间、触发方式与结果，
并可在详情页 / 仪表板 / 侧栏全页查看历史记录。

V3 契约要点（务必遵守）：
1. 插件与宿主同进程、同依赖环境，禁止在模块导入期做网络 / 数据库 / 任务启动。
2. 配置与数据一律走基类方法，以便兼容插件虚拟分身。
3. 运行时文件写入 ``get_data_path()``，不要写回插件源码目录。
4. 只从 ``app.sdk`` 等稳定入口导入，不要依赖宿主内部目录结构。
"""
from __future__ import annotations

import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from apscheduler.triggers.cron import CronTrigger

from app.schemas.types import EventType
from app.sdk.events import Event, eventmanager
from app.sdk.logging import logger
from app.sdk.plugin import _PluginBase

# 消息类型枚举在宿主版本间存在改名：V3.1+ 使用 MessageType，更早的实现使用 NotificationType。
# 这里做一次兼容性导入，避免因宿主版本差异导致插件整体加载失败。
try:  # pragma: no cover - 取决于宿主版本
    from app.schemas.types import MessageType as _MessageType
except ImportError:  # pragma: no cover
    from app.schemas.types import NotificationType as _MessageType  # type: ignore

from .agenttool import PluginTemplateStatusTool


class PluginTemplate(_PluginBase):
    """插件开发模板：演示 MoviePilot V3 插件的完整扩展点。"""

    # ─── 插件元数据（需与 package.v3.json 保持一致） ──────────────────
    plugin_name = "插件开发模板"
    plugin_desc = (
        "MoviePilot V3 插件开发模板：内置配置页、详情页、仪表板、侧栏全页、"
        "定时服务、远程命令、插件 API、工作流动作与智能体工具，可直接二次开发。"
    )
    plugin_icon = (
        "https://raw.githubusercontent.com/m215owen/MoviePilot-Plugins/main/icons/Moviepilot_A.png"
    )
    plugin_version = "1.0.0"
    plugin_author = "m215owen"
    author_url = "https://github.com/m215owen"
    plugin_label = "示例模板"
    # 配置项前缀：由宿主按运行实例保证唯一，插件表单字段名不要另起前缀
    plugin_config_prefix = "plugintemplate_"
    # 加载顺序，数值越小越早
    plugin_order = 50
    # 市场可见权限级别
    auth_level = 1

    # ─── 运行时状态（统一由 init_plugin 重建，保证可重复初始化） ──────
    _enabled: bool = False
    _cron: str = "0 */6 * * *"
    _notify: bool = False
    _message: str = "Hello MoviePilot"
    _max_records: int = 50
    _run_count: int = 0

    # 执行记录在插件数据表中的键名
    _DATA_KEY: str = "run_records"
    # 一次性任务的标识
    _ONCE_JOB_ID: str = "run_once"

    # ─── 生命周期 ────────────────────────────────────────────────

    def init_plugin(self, config: dict | None = None) -> None:
        """读取配置并重建运行状态；宿主会在启动和保存配置时调用，必须可重复执行。"""
        # 先释放上一轮运行可能遗留的资源，再按新配置重建
        self.stop_service()

        cfg: Dict[str, Any] = dict(config or {})
        self._enabled = bool(cfg.get("enabled"))
        self._cron = str(cfg.get("cron") or "0 */6 * * *")
        self._notify = bool(cfg.get("notify"))
        self._message = str(cfg.get("message") or "Hello MoviePilot")
        try:
            self._max_records = max(5, min(500, int(cfg.get("max_records") or 50)))
        except (TypeError, ValueError):
            self._max_records = 50
        # 运行计数从持久化记录推导，避免重启后仪表板统计归零
        self._run_count = len(self._load_records())

        # 把当前运行实例注入智能体工具，避免工具依赖进程级单例查找
        PluginTemplateStatusTool.bind(self)

        # 勾选“启用后立即执行一次”时，交给宿主调度器延迟执行，而不是自建线程
        if self._enabled and cfg.get("onlyonce"):
            if self._add_once_job():
                cfg["onlyonce"] = False
                self.update_config(cfg)

        logger.info(
            f"{self.plugin_name} 初始化完成：enabled={self._enabled}，cron={self._cron}"
        )

    def get_state(self) -> bool:
        """返回插件当前是否启用。"""
        return self._enabled

    def stop_service(self) -> None:
        """停用或卸载插件时释放后台资源；需保证可重复、安全地调用。"""
        self._enabled = False
        # 取消由本插件登记、尚未执行的一次性任务
        try:
            from app.sdk import scheduler as scheduler_sdk  # 延迟导入，避免版本差异影响加载

            remove_job = getattr(scheduler_sdk, "remove_plugin_once_job", None)
            if remove_job:
                remove_job(self.__class__.__name__, self._ONCE_JOB_ID)
        except Exception as err:  # pragma: no cover - 宿主版本差异兜底
            logger.debug(f"{self.plugin_name} 清理一次性任务时跳过：{err}")

    # ─── 页面与渲染模式 ──────────────────────────────────────────

    @staticmethod
    def get_render_mode() -> Tuple[str, str]:
        """声明使用 Vue 联邦远程组件渲染，产物目录为 dist/assets。"""
        return "vue", "dist/assets"

    def get_form(self) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Vue 模式下配置页由远程 Config 组件渲染，后端只需返回默认配置模型。"""
        return [], self._default_config()

    def get_page(self) -> List[Dict[str, Any]]:
        """Vue 模式下详情页由远程 Page 组件渲染，后端返回空列表。"""
        return []

    def get_dashboard_meta(self) -> Optional[List[Dict[str, str]]]:
        """声明仪表板窗口；插件未启用时不注册。"""
        if not self.get_state():
            return None
        return [{"key": "summary", "name": f"{self.plugin_name} · 概览"}]

    def get_dashboard(
        self, key: str = "", **kwargs: Any
    ) -> Optional[Tuple[Dict[str, Any], Dict[str, Any], List[dict]]]:
        """声明仪表板内容，返回 ``(列配置, 全局配置, 页面 JSON)`` 三元组。

        Vue 联邦插件通过前端 Dashboard 组件呈现内容，因此这里返回空的页面 JSON。
        """
        if not self.get_state():
            return None
        if key and key != "summary":
            return None
        return (
            {"cols": 12, "sm": 6, "md": 4},
            {
                "title": f"{self.plugin_name} · 概览",
                "subtitle": f"累计执行 {self._run_count} 次",
                "refresh": 60,
                "border": True,
            },
            [],
        )

    def get_sidebar_nav(self) -> List[Dict[str, Any]]:
        """声明主界面侧栏全页入口；仅 Vue 渲染模式的插件会被聚合。

        ``section`` 仅接受 start / discovery / subscribe / organize / system；
        ``permission`` 仅接受 subscribe / discovery / search / manage / admin。
        """
        if not self.get_state():
            return []
        return [
            {
                "nav_key": "main",
                "title": self.plugin_name,
                "icon": "mdi-view-dashboard-variant",
                "section": "system",
                "permission": "manage",
                "order": 20,
            },
            {
                "nav_key": "settings",
                "title": f"{self.plugin_name} · 设置",
                "icon": "mdi-cog-outline",
                "section": "system",
                "permission": "manage",
                "order": 21,
            },
        ]

    # ─── 后台能力：定时服务 / 远程命令 / HTTP 接口 ────────────────

    def get_service(self) -> List[Dict[str, Any]]:
        """注册定时任务；启用后出现在「设定 - 服务」中可查看状态与手动启动。"""
        if not self.get_state() or not self._cron:
            return []
        try:
            trigger = CronTrigger.from_crontab(self._cron)
        except Exception as err:
            logger.error(f"{self.plugin_name} cron 表达式不合法（{self._cron}）：{err}")
            return []
        return [
            {
                # 服务 ID 必须稳定且唯一
                "id": f"{self.__class__.__name__}.Run",
                "name": f"{self.plugin_name}定时任务",
                "trigger": trigger,
                "func": self.execute_task,
                "kwargs": {"trigger": "cron"},
            }
        ]

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        """注册远程命令，实际动作通过 EventType.PluginAction 事件路由。"""
        return [
            {
                "cmd": "/plugintemplate_run",
                "event": EventType.PluginAction,
                "desc": "执行插件开发模板任务",
                "category": "插件命令",
                # data.action 是插件之间区分动作的可靠标识
                "data": {"action": "plugintemplate_run"},
            }
        ]

    @eventmanager.register(EventType.PluginAction)
    def on_plugin_action(self, event: Event) -> None:
        """响应远程命令；仅处理属于本插件的 action。"""
        event_data = event.event_data or {}
        if event_data.get("action") != "plugintemplate_run":
            return
        self.execute_task(trigger="command")

    def get_api(self) -> List[Dict[str, Any]]:
        """声明插件 HTTP 接口，最终挂载在 ``/api/v1/plugin/<PluginID>/<path>``。

        面向前端联邦组件的接口使用 ``bear`` 鉴权；如需对外系统调用可改用 ``apikey``。
        """
        return [
            {
                "path": "/config",
                "endpoint": self.api_get_config,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "获取插件配置",
            },
            {
                "path": "/config",
                "endpoint": self.api_update_config,
                "methods": ["PUT"],
                "auth": "bear",
                "summary": "更新插件配置",
            },
            {
                "path": "/records",
                "endpoint": self.api_get_records,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "查询执行记录",
            },
            {
                "path": "/run",
                "endpoint": self.api_run,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "立即执行一次任务",
            },
            {
                "path": "/clear",
                "endpoint": self.api_clear,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "清空执行记录",
            },
        ]

    # ─── 高级能力：工作流动作 / 智能体工具 ────────────────────────

    def get_actions(self) -> List[Dict[str, Any]]:
        """注册工作流动作，可供工作流「调用插件」组件串联使用。

        宿主约定：动作函数第一个参数固定为 ``ActionContent``，返回 ``(是否成功, ActionContent)``。
        这里用鸭子类型（默认参数 + ``**kwargs``）承接，避免强依赖宿主的类型导入路径。
        """
        return [
            {
                "id": "plugintemplate_run",
                "name": f"{self.plugin_name} · 执行任务",
                "func": self.action_run,
                "kwargs": {},
            }
        ]

    def action_run(self, action: Any = None, **kwargs: Any) -> Tuple[bool, Any]:
        """工作流动作实现：执行一次任务并原样回传 ActionContent。"""
        ok = self.execute_task(trigger="workflow")
        return ok, action

    def get_agent_tools(self) -> List[type]:
        """注册智能体工具，供 MoviePilot 的 AI 智能体查询插件状态。"""
        PluginTemplateStatusTool.bind(self)
        return [PluginTemplateStatusTool]

    # ─── 业务逻辑 ────────────────────────────────────────────────

    def execute_task(self, trigger: str = "manual") -> bool:
        """执行一次示例任务并写入记录。

        :param trigger: 触发来源，取值 manual / cron / command / workflow / api
        :return: 是否执行成功
        """
        if not self.get_state():
            logger.info(f"{self.plugin_name} 未启用，跳过执行")
            return False

        started = time.time()
        success = True
        try:
            # 这里替换为真实业务逻辑；示例中只构造一条说明文本
            detail = f"示例任务执行成功，配置文本：{self._message}"
        except Exception as err:  # pragma: no cover - 业务异常兜底
            success = False
            detail = f"执行异常：{err}"
            logger.error(f"{self.plugin_name} 任务执行失败：{err}")

        record = {
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "trigger": trigger,
            "success": success,
            "elapsed_ms": int((time.time() - started) * 1000),
            "detail": detail,
        }
        self._append_record(record)
        self._run_count += 1

        if self._notify:
            self._send_notify(success, detail)

        logger.info(f"{self.plugin_name} 任务完成（{trigger}）：{detail}")
        return success

    def get_records(self, limit: int = 20) -> List[Dict[str, Any]]:
        """按时间倒序返回最近的执行记录。"""
        try:
            size = max(1, int(limit))
        except (TypeError, ValueError):
            size = 20
        return self._load_records()[:size]

    # ─── 数据读写 ────────────────────────────────────────────────

    def _load_records(self) -> List[Dict[str, Any]]:
        """从插件数据表读取执行记录。"""
        data = self.get_data(self._DATA_KEY)
        return list(data) if isinstance(data, list) else []

    def _append_record(self, record: Dict[str, Any]) -> None:
        """插入一条记录并按上限裁剪，仅保留最近的若干条。"""
        records = self._load_records()
        records.insert(0, record)
        self.save_data(self._DATA_KEY, records[: self._max_records])

    def _send_notify(self, success: bool, detail: str) -> None:
        """通过宿主通知渠道发送消息；通知失败不影响主流程。"""
        try:
            self.post_message(
                mtype=_MessageType.Plugin,
                title=f"【{self.plugin_name}】{'执行成功' if success else '执行失败'}",
                text=detail,
            )
        except Exception as err:  # pragma: no cover - 未配置通知渠道时兜底
            logger.warning(f"{self.plugin_name} 发送通知失败：{err}")

    def _add_once_job(self) -> bool:
        """向宿主调度器登记一次性任务，返回是否登记成功。

        “立即执行一次”应交给宿主调度器，不要自建 BackgroundScheduler。
        """
        try:
            from app.sdk import scheduler as scheduler_sdk

            add_once = getattr(scheduler_sdk, "add_plugin_once_job", None)
            if not add_once:
                logger.warning(f"{self.plugin_name} 当前宿主不支持一次性任务接口")
                return False
            add_once(
                self.__class__.__name__,
                self._ONCE_JOB_ID,
                self.execute_task,
                f"{self.plugin_name}立即执行一次",
                delay_seconds=3,
                kwargs={"trigger": "once"},
            )
            return True
        except Exception as err:  # pragma: no cover - 宿主版本差异兜底
            logger.warning(f"{self.plugin_name} 登记一次性任务失败：{err}")
            return False

    # ─── 插件 API 实现 ───────────────────────────────────────────

    def api_get_config(self) -> Dict[str, Any]:
        """返回当前运行时配置，供前端 Config 组件回显。"""
        return {
            "enabled": self._enabled,
            "cron": self._cron,
            "notify": self._notify,
            "message": self._message,
            "max_records": self._max_records,
            "run_count": self._run_count,
        }

    def api_update_config(self, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """接收前端提交的配置，持久化后重新初始化插件。"""
        if not config or not isinstance(config, dict):
            return {"success": False, "message": "请求体不是合法对象"}

        merged = {**self.api_get_config(), **config}
        merged["enabled"] = bool(merged.get("enabled"))
        merged["notify"] = bool(merged.get("notify"))
        merged["cron"] = str(merged.get("cron") or "0 */6 * * *")
        merged["message"] = str(merged.get("message") or "")
        try:
            merged["max_records"] = max(5, min(500, int(merged.get("max_records") or 50)))
        except (TypeError, ValueError):
            merged["max_records"] = 50
        # run_count 属于运行时统计，不落盘
        merged.pop("run_count", None)

        if not self.update_config(merged):
            return {"success": False, "message": "配置持久化失败"}

        self.init_plugin(merged)
        return {"success": True, "data": self.api_get_config()}

    def api_get_records(self, limit: int = 20) -> Dict[str, Any]:
        """查询最近的执行记录。"""
        return {"success": True, "data": self.get_records(limit=limit)}

    def api_run(self) -> Dict[str, Any]:
        """手动触发一次任务。"""
        ok = self.execute_task(trigger="api")
        return {
            "success": ok,
            "message": "执行完成" if ok else "执行失败（插件可能未启用）",
            "data": {"run_count": self._run_count},
        }

    def api_clear(self) -> Dict[str, Any]:
        """清空执行记录与计数。"""
        self.save_data(self._DATA_KEY, [])
        self._run_count = 0
        return {"success": True, "message": "记录已清空"}

    # ─── 默认配置 ────────────────────────────────────────────────

    @staticmethod
    def _default_config() -> Dict[str, Any]:
        """返回配置页默认值，字段名需与 ``plugin_config_prefix`` 前缀约定一致。"""
        return {
            "enabled": False,
            "cron": "0 */6 * * *",
            "notify": False,
            "message": "Hello MoviePilot",
            "max_records": 50,
            "onlyonce": False,
        }
