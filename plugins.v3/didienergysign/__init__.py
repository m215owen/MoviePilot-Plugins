"""滴滴能源签到（MoviePilot V3 插件）。

为什么需要它
------------
滴滴能源（小桔充电）小程序里「每日签到领券」活动要求连续手动打卡，断一天
连续天数就清零重来。本插件把这一步自动化：按周期用签到凭证调用小程序侧
签到接口，本地记录签到进度，连续满 5 天平台发券。

凭证（ticket）来源
------------------
微信小程序的登录凭证，需自行抓包获取（请求头/请求体里的 ``ticket`` 字段）。
凭证由站点侧下发、有效期由站点控制；失效时签到会返回业务失败，插件会通过
通知与日志提示重新抓取填写。

机制说明
--------
* 每个周期先读本地签到记录：今天已签则直接跳过，不重复出网；
* 本地没记录时，先拉**签到页数据源**（``sign/main``，即小程序签到页面
  渲染所用接口）确认站点侧今日是否已签——已签直接写记录收工；
* 确认未签才调 doSign；doSign 返回 ``DO_SIGN_ERROR`` 通用文案时（实测
  「已签」与「失败」同码），**回查签到页**仲裁：页面显示今天已签即按
  重复成功处理，否则标记「未确认」、不写记录，下次再试；
* 签到记录（累计/连续/最大连续/最近 30 天历史）经 ``save_data`` 持久化在
  插件数据区，不写源码目录。

不做什么
--------
不做多账号轮询（一个实例一个凭证，需要多号用宿主「虚拟分身」建多实例）；
不代理任何支付/下单行为，只做签到打卡。
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from apscheduler.triggers.cron import CronTrigger

from app import schemas
from app.sdk.logging import logger
from app.sdk.plugin import _PluginBase

from . import models
from .constants import (
    COUPON_TARGET_DAYS,
    DEFAULT_CITY_ID,
    DEFAULT_CRON,
    DEFAULT_EXCITATION_ID,
    DEFAULT_TIMEOUT,
    PLUGIN_ICON,
    PLUGIN_ID,
    PLUGIN_NAME,
    RECORD_KEY,
)
from .service import (
    SignResult,
    build_notify_text,
    fetch_sign_page,
    masked_ticket,
    normalize_record,
    now_str,
    sign_with_retry,
    today_str,
    update_record,
)

# 消息类型：V3 全系宿主（system_version >=3.0.0）均提供 MessageType，
# 直接使用；不再兜底 NotificationType（宿主诊断会提示旧路径）。
from app.schemas.types import MessageType as _MessageType  # noqa: E402

#: 定时服务 ID（必须稳定且全局唯一；虚拟分身场景由宿主按实例隔离）
_SERVICE_ID = f"{PLUGIN_ID}.daily"


class DidiEnergySign(_PluginBase):
    # ── 插件元数据（宿主用 AST 静态解析，必须是字面量）────────────────
    plugin_name = PLUGIN_NAME
    plugin_desc = (
        "每日自动完成滴滴能源（小桔充电）小程序签到，本地记录累计/连续天数，"
        "连续满 5 天领平台优惠券；凭证失效时通知提醒。"
    )
    plugin_icon = PLUGIN_ICON
    plugin_version = "1.0.0"
    plugin_author = "m215owen"
    author_url = "https://github.com/m215owen"
    plugin_config_prefix = "didienergysign_"
    plugin_order = 94
    auth_level = 1

    # ── 运行时状态（init_plugin 全部重置，保证可重复调用）──────────────
    _enabled: bool = False
    _ticket: str = ""
    _city_id: str = DEFAULT_CITY_ID
    _excitation_id: str = DEFAULT_EXCITATION_ID
    _cron: str = DEFAULT_CRON
    _notify: bool = False
    _notify_success: bool = False
    _timeout: int = DEFAULT_TIMEOUT
    _proxy: str = ""
    #: 最近一次执行摘要（面板展示用，重启后从持久化状态恢复）
    _last_run_at: str = ""
    _last_result: str = ""
    _last_message: str = ""

    def init_plugin(self, config: dict | None = None) -> None:
        """读配置、恢复状态。必须允许重复调用（宿主保存配置时会再次触发）。"""
        self._enabled = False
        self._ticket = ""
        self._city_id = DEFAULT_CITY_ID
        self._excitation_id = DEFAULT_EXCITATION_ID
        self._cron = DEFAULT_CRON
        self._notify = False
        self._notify_success = False
        self._timeout = DEFAULT_TIMEOUT
        self._proxy = ""
        self._last_run_at = ""
        self._last_result = ""
        self._last_message = ""

        config = config or {}
        self._enabled = bool(config.get("enabled", False))
        self._ticket = str(config.get("ticket") or "").strip()
        self._city_id = str(config.get("city_id") or "").strip() or DEFAULT_CITY_ID
        self._excitation_id = (
            str(config.get("excitation_id") or "").strip() or DEFAULT_EXCITATION_ID
        )
        self._cron = str(config.get("cron") or DEFAULT_CRON).strip() or DEFAULT_CRON
        self._notify = bool(config.get("notify", False))
        self._notify_success = bool(config.get("notify_success", False))
        try:
            self._timeout = max(5, int(config.get("timeout") or DEFAULT_TIMEOUT))
        except (TypeError, ValueError):
            self._timeout = DEFAULT_TIMEOUT
        self._proxy = str(config.get("proxy") or "").strip()

        # 恢复上次执行摘要（重启后面板不至于空白）
        try:
            state = self.get_data("last_run_state") or {}
        except Exception as err:  # noqa: BLE001 - 老数据损坏不该阻断启动
            logger.debug(f"{PLUGIN_NAME}：读取持久化状态失败（忽略）：{err}")
            state = {}
        if isinstance(state, dict):
            self._last_run_at = str(state.get("last_run_at") or "")
            self._last_result = str(state.get("last_result") or "")
            self._last_message = str(state.get("last_message") or "")

        logger.info(
            f"{PLUGIN_NAME}：初始化完成（启用={self._enabled}，"
            f"凭证={'已配置' if self._ticket else '未配置'}，"
            f"城市={self._city_id}，周期={self._cron}）"
        )

    def get_state(self) -> bool:
        return bool(self._enabled and self._ticket)

    def stop_service(self) -> None:
        """本插件不自建线程/调度器/连接池（网络请求按次创建），无可释放资源。

        保留该方法以明确「重复调用安全」。
        """
        logger.debug(f"{PLUGIN_NAME}：stop_service 已调用（无可释放资源）")

    # ── 定时服务 ──────────────────────────────────────────────────

    def get_service(self) -> List[Dict[str, Any]]:
        """注册每日签到定时任务；未启用或未配置凭证时不注册。"""
        if not self.get_state():
            return []
        try:
            trigger = CronTrigger.from_crontab(self._cron)
        except Exception as err:  # noqa: BLE001 - cron 写错不该让插件整体不可用
            logger.error(f"{PLUGIN_NAME}：执行周期 cron 无效（{self._cron}）：{err}")
            return []
        return [
            {
                "id": _SERVICE_ID,
                "name": f"{PLUGIN_NAME} 每日签到",
                "trigger": trigger,
                "func": self._service_sign,
                "kwargs": {},
            }
        ]

    async def _service_sign(self) -> None:
        """定时入口：跑一次签到并落盘结果。异常一律吞掉留日志，不污染调度器。"""
        try:
            await self._sign_once(reason="定时")
        except Exception as err:  # noqa: BLE001
            logger.error(f"{PLUGIN_NAME}：定时签到异常：{err}")
            self._record_run("异常", f"定时执行异常：{err}")

    # ── 核心动作 ──────────────────────────────────────────────────

    async def _sign_once(self, force: bool = False, reason: str = "") -> models.RunData:
        """执行一次「查记录 → 签到 → 更新记录 → 通知」的完整流程。

        :param force: 为 True 时忽略**本地记录**的「今日已签」判断再走一遍流程
            （用于核对凭证）；但签到页数据源仍会检查——站点侧显示今天已签时
            不会重复调 doSign（用户规则：今天已签到今天就不再执行）。
        """
        today = today_str()
        record = normalize_record(self.get_data(RECORD_KEY))

        # 1) 本地记录显示今日已签（且非强制）：直接跳过，不重复出网。
        #    注意：即便 force=true，后面的签到页检查依然生效——站点侧今天已签
        #    时不会重复调 doSign。
        if not force and record.get("last_sign_date") == today:
            logger.info(
                f"{PLUGIN_NAME}：今日（{today}）已签到（本地记录），跳过执行；"
                f"累计 {record['total_days']} 天 / 连续 {record['continuous_days']} 天"
            )
            self._record_run("跳过", "今日已签到（本地记录）")
            if self._notify and self._notify_success:
                self._send_notify(
                    title=f"【{self.plugin_name}】今日已完成签到",
                    text=(
                        f"结果：已签到（跳过）\n签到日期：{record['last_sign_date']}\n"
                        f"累计签到：{record['total_days']} 天\n"
                        f"连续签到：{record['continuous_days']} 天"
                    ),
                )
            return models.RunData(
                ok=True,
                is_duplicate=True,
                message="今日已签到（本地记录）",
                skipped=True,
                continuous_days=record["continuous_days"],
                period_days=COUPON_TARGET_DAYS,
                ran_at=self._last_run_at,
            )

        # 2) 凭证检查
        if not self._ticket:
            message = "未配置签到凭证（ticket），无法签到"
            logger.warning(f"{PLUGIN_NAME}：{message}")
            self._record_run("失败", message)
            return models.RunData(ok=False, message=message, ran_at=self._last_run_at)

        # 3) 先拉签到页数据源（小程序签到页渲染用的同一接口）确认站点侧状态。
        #    已签 → 直接写记录收工，不盲打 doSign（打也是返回模糊错误）。
        page = await fetch_sign_page(
            self._ticket,
            self._city_id,
            self._excitation_id,
            timeout=self._timeout,
            proxy=self._proxy,
        )
        if page.ok and page.signed_today:
            record = update_record(record, today, page.continuous_days)
            self._save_record(record)
            message = f"今日已签到（签到页确认，连续 {page.continuous_days} 天）"
            logger.info(f"{PLUGIN_NAME}：{message}；本轮 {page.period_start}~{page.period_end}")
            self._record_run("已签到", message)
            if self._notify and self._notify_success:
                self._send_notify(
                    title=f"【{self.plugin_name}】今日已完成签到",
                    text=build_notify_text(
                        SignResult(
                            ok=True, is_duplicate=True, continuous_days=page.continuous_days
                        ),
                        record,
                        today,
                    ),
                )
            return models.RunData(
                ok=True,
                is_duplicate=True,
                skipped=True,
                continuous_days=page.continuous_days,
                has_coupon=page.continuous_days >= COUPON_TARGET_DAYS,
                message=message,
                period_days=page.period_days or COUPON_TARGET_DAYS,
                period_start=page.period_start,
                period_end=page.period_end,
                signed_dates=page.records,
                ran_at=self._last_run_at,
            )
        if not page.ok:
            logger.warning(
                f"{PLUGIN_NAME}：签到页状态不可用（{page.message}），降级为直接签到"
            )

        # 4) 请求签到（业务失败自动重试一次）
        logger.info(
            f"{PLUGIN_NAME}：账号 [{masked_ticket(self._ticket)}] 开始签到"
            f"（{reason or '手动'}，城市 {self._city_id}）"
        )
        result = await sign_with_retry(
            self._ticket,
            self._city_id,
            self._excitation_id,
            timeout=self._timeout,
            proxy=self._proxy,
        )

        # 5) doSign 的模糊错误（已签/失败同码）→ 回查签到页仲裁；
        #    新签成功 → 也回查一次页面，把本轮周期/已签日历带给面板进度展示
        page_data = None
        if result.is_ambiguous or result.is_new_sign:
            page2 = await fetch_sign_page(
                self._ticket,
                self._city_id,
                self._excitation_id,
                timeout=self._timeout,
                proxy=self._proxy,
            )
            if page2.ok and page2.signed_today:
                page_data = page2
            if result.is_ambiguous:
                if page2.ok and page2.signed_today:
                    result = SignResult(
                        ok=True,
                        is_duplicate=True,
                        continuous_days=page2.continuous_days,
                        message="今日已签到（doSign 模糊错误，签到页回查确认）",
                    )
                    logger.info(f"{PLUGIN_NAME}：模糊结果已由签到页仲裁为「已签」")
                else:
                    page_data = None
                    logger.info(
                        f"{PLUGIN_NAME}：doSign 返回未明确（{result.message}）且签到页未确认已签"
                        f"——本次不写入签到记录，下次执行会再试"
                    )

        # 6) 只有确认完成（新签/确认重复）才写 last_sign_date
        if result.ok:
            record = update_record(record, today, result.continuous_days)
            self._save_record(record)
        elif result.is_ambiguous:
            record["last_ambiguous_date"] = today
            self._save_record(record)

        self._record_run(result.result_label, result.message)

        # 7) 通知：失败必发；成功只在「成功也通知」开启时发
        if self._notify and (self._notify_success or not result.ok):
            title = (
                f"【{self.plugin_name}】签到{'成功' if result.is_new_sign else result.result_label}"
            )
            self._send_notify(title=title, text=build_notify_text(result, record, today))

        return models.RunData(
            ok=result.ok,
            is_new_sign=result.is_new_sign,
            is_duplicate=result.is_duplicate,
            is_ambiguous=result.is_ambiguous,
            is_error=result.is_error,
            continuous_days=result.continuous_days,
            has_coupon=result.has_coupon,
            message=result.message,
            period_days=(
                (page_data.period_days if page_data else 0) or COUPON_TARGET_DAYS
            ),
            period_start=page_data.period_start if page_data else "",
            period_end=page_data.period_end if page_data else "",
            signed_dates=page_data.records if page_data else [],
            ran_at=self._last_run_at,
        )

    # ── 结果落盘与通知 ─────────────────────────────────────────────

    def _save_record(self, record: Dict[str, Any]) -> None:
        """签到记录落盘；失败只留日志，不影响本次执行结果展示。"""
        try:
            self.save_data(RECORD_KEY, record)
        except Exception as err:  # noqa: BLE001
            logger.warning(f"{PLUGIN_NAME}：保存签到记录失败：{err}")

    def _record_run(self, result: str, message: str) -> None:
        """把一次执行摘要写进运行时状态 + 持久化（面板/重启后可见）。"""
        self._last_run_at = now_str()
        self._last_result = result
        self._last_message = message
        try:
            self.save_data(
                "last_run_state",
                {
                    "last_run_at": self._last_run_at,
                    "last_result": self._last_result,
                    "last_message": self._last_message,
                },
            )
        except Exception as err:  # noqa: BLE001
            logger.debug(f"{PLUGIN_NAME}：保存执行状态失败（忽略）：{err}")

    def _send_notify(self, title: str, text: str) -> None:
        """发一条插件消息；通知渠道未配置只是一条 warning，不影响主流程。"""
        try:
            self.post_message(mtype=_MessageType.Plugin, title=title, text=text)
        except Exception as err:  # noqa: BLE001
            logger.warning(f"{PLUGIN_NAME}：发送通知失败：{err}")

    # ── 配置表单 ──────────────────────────────────────────────────

    def get_form(self) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """配置页（Vuetify JSON 模式）+ 默认配置模型。"""
        return (
            [
                {
                    "component": "VForm",
                    "content": [
                        {
                            "component": "VRow",
                            "content": [
                                {
                                    "component": "VCol",
                                    "props": {"cols": 12, "md": 3},
                                    "content": [
                                        {
                                            "component": "VSwitch",
                                            "props": {
                                                "model": "enabled",
                                                "label": "启用插件",
                                                "default": False,
                                            },
                                        }
                                    ],
                                },
                                {
                                    "component": "VCol",
                                    "props": {"cols": 12, "md": 3},
                                    "content": [
                                        {
                                            "component": "VSwitch",
                                            "props": {
                                                "model": "notify",
                                                "label": "发送通知",
                                                "default": False,
                                                "hint": "失败必发；成功是否发看下一项",
                                            },
                                        }
                                    ],
                                },
                                {
                                    "component": "VCol",
                                    "props": {"cols": 12, "md": 3},
                                    "content": [
                                        {
                                            "component": "VSwitch",
                                            "props": {
                                                "model": "notify_success",
                                                "label": "成功也通知",
                                                "default": False,
                                                "hint": "关闭时仅失败/异常发通知",
                                            },
                                        }
                                    ],
                                },
                                {
                                    "component": "VCol",
                                    "props": {"cols": 12, "md": 3},
                                    "content": [
                                        {
                                            "component": "VCronField",
                                            "props": {
                                                "model": "cron",
                                                "label": "执行周期",
                                                "placeholder": DEFAULT_CRON,
                                                "hint": "5 位 cron，建议每天固定时间一次",
                                                "persistent-hint": True,
                                            },
                                        }
                                    ],
                                },
                            ],
                        },
                        {
                            "component": "VRow",
                            "content": [
                                {
                                    "component": "VCol",
                                    "props": {"cols": 12},
                                    "content": [
                                        {
                                            "component": "VTextField",
                                            "props": {
                                                "model": "ticket",
                                                "label": "签到凭证（ticket）",
                                                "type": "password",
                                                "placeholder": "从小程序抓包获取",
                                                "hint": "微信小程序「滴滴能源」请求里的 ticket 字段；站点下发、可能过期，失效后需重新抓取",
                                                "persistent-hint": True,
                                            },
                                        }
                                    ],
                                },
                            ],
                        },
                        {
                            "component": "VRow",
                            "content": [
                                {
                                    "component": "VCol",
                                    "props": {"cols": 12, "md": 4},
                                    "content": [
                                        {
                                            "component": "VTextField",
                                            "props": {
                                                "model": "city_id",
                                                "label": "城市 ID",
                                                "placeholder": DEFAULT_CITY_ID,
                                                "hint": "默认 5",
                                                "persistent-hint": True,
                                            },
                                        }
                                    ],
                                },
                                {
                                    "component": "VCol",
                                    "props": {"cols": 12, "md": 8},
                                    "content": [
                                        {
                                            "component": "VTextField",
                                            "props": {
                                                "model": "excitation_id",
                                                "label": "活动 ID",
                                                "placeholder": DEFAULT_EXCITATION_ID,
                                                "hint": "签到活动 excitationId，一般不用改",
                                                "persistent-hint": True,
                                            },
                                        }
                                    ],
                                },
                            ],
                        },
                        {
                            "component": "VRow",
                            "content": [
                                {
                                    "component": "VCol",
                                    "props": {"cols": 12, "md": 4},
                                    "content": [
                                        {
                                            "component": "VTextField",
                                            "props": {
                                                "model": "timeout",
                                                "label": "请求超时（秒）",
                                                "type": "number",
                                                "placeholder": str(DEFAULT_TIMEOUT),
                                            },
                                        }
                                    ],
                                },
                                {
                                    "component": "VCol",
                                    "props": {"cols": 12, "md": 8},
                                    "content": [
                                        {
                                            "component": "VTextField",
                                            "props": {
                                                "model": "proxy",
                                                "label": "代理地址（可选）",
                                                "placeholder": "http://192.168.1.1:7890",
                                                "hint": "国内站点一般直连即可；留空表示直连",
                                                "persistent-hint": True,
                                            },
                                        }
                                    ],
                                },
                            ],
                        },
                        {
                            "component": "VRow",
                            "content": [
                                {
                                    "component": "VCol",
                                    "props": {"cols": 12},
                                    "content": [
                                        {
                                            "component": "VAlert",
                                            "props": {
                                                "type": "info",
                                                "variant": "tonal",
                                                "text": (
                                                    "连续签到满 5 天平台发放优惠券，断一天连续天数清零。"
                                                    "本插件每天定时签到一次；每个凭证一个实例，"
                                                    "多账号请用宿主「虚拟分身」建多个分身分别配置。"
                                                    "\n手动触发：详情页「立即执行」，或 POST "
                                                    "/api/v1/plugin/DidiEnergySign/run"
                                                ),
                                                "style": "white-space: pre-line;",
                                            },
                                        }
                                    ],
                                }
                            ],
                        },
                    ],
                }
            ],
            {
                "enabled": self._enabled,
                "ticket": self._ticket,
                "city_id": self._city_id,
                "excitation_id": self._excitation_id,
                "cron": self._cron,
                "notify": self._notify,
                "notify_success": self._notify_success,
                "timeout": self._timeout,
                "proxy": self._proxy,
            },
        )

    # ── 详情页 ────────────────────────────────────────────────────

    def get_page(self) -> List[Dict[str, Any]]:
        """详情页只展示本地记录与上次执行摘要，不在这里出网（get_page 是同步的）。"""
        content: List[Dict[str, Any]] = []

        if not self.get_state():
            content.append(
                {
                    "component": "VAlert",
                    "props": {
                        "type": "warning",
                        "variant": "tonal",
                        "text": (
                            "插件未就绪：请启用插件并配置签到凭证（ticket），"
                            "保存后会按执行周期自动签到。"
                        ),
                    },
                }
            )

        record = normalize_record(self.get_data(RECORD_KEY))

        # 「立即执行」按钮：用宿主的 events 声明式事件（get_page 的 onclick 字符串
        # 在当前宿主前端不被解析，点击无反应——v3.1.8 实测）。宿主 PageRender 会把
        # {"click": {api, method, params}} 绑到组件点击事件上，经带登录态的 API
        # 客户端请求，执行期间显示原生进度弹窗，完成后自动重载详情页。
        content.append(
            {
                "component": "VRow",
                "props": {"class": "mb-1"},
                "content": [
                    {
                        "component": "VCol",
                        "props": {"cols": "auto"},
                        "content": [
                            {
                                "component": "VBtn",
                                "props": {
                                    "color": "primary",
                                    "variant": "flat",
                                    "prepend-icon": "mdi-check-circle-outline",
                                },
                                "text": "立即执行",
                                "events": {
                                    "click": {
                                        "api": "plugin/DidiEnergySign/run",
                                        "method": "POST",
                                        "params": {},
                                    }
                                },
                            }
                        ],
                    },
                    {
                        "component": "VCol",
                        "props": {"cols": "auto", "class": "text-medium-emphasis align-self-center"},
                        "content": [
                            {
                                "component": "span",
                                "text": "执行中显示进度，完成后详情自动刷新（见下方「上次执行」）。",
                            }
                        ],
                    },
                ],
            }
        )

        has_record = bool(record.get("last_sign_date"))
        if not has_record:
            content.append(
                {
                    "component": "VAlert",
                    "props": {
                        "type": "info",
                        "variant": "outlined",
                        "text": (
                            "还没有签到记录。点「立即执行」（或 POST "
                            "/api/v1/plugin/DidiEnergySign/run）跑一次即可生成。"
                        ),
                    },
                }
            )
            return content

        today = today_str()
        signed_today = record.get("last_sign_date") == today
        lines = [
            f"最近签到：{record['last_sign_date']}"
            + ("（今天已签 ✅）" if signed_today else "（今天还没签）"),
            f"累计签到：{record['total_days']} 天 · "
            f"当前连续：{record['continuous_days']} 天 · "
            f"最大连续：{record['max_continuous_days']} 天",
        ]
        history = record.get("sign_history") or []
        if history:
            recent = " · ".join(date[5:] for date in history[-7:])
            lines.append(f"最近 7 次：{recent}")
        if not signed_today and record.get("last_ambiguous_date") == today:
            lines.append(
                "今天有一次结果未确认：站点对「已签」与「失败」返回同一错误码；"
                "可在小程序里核对，确认未签可点「立即执行」再试"
            )
        if record.get("continuous_days") >= COUPON_TARGET_DAYS:
            lines.append("🎉 连续签到已满 5 天，优惠券已发放")
        else:
            lines.append(
                f"再连续签到 {COUPON_TARGET_DAYS - record['continuous_days']} 天可领优惠券"
            )
        if self._last_run_at:
            lines.append(
                f"上次执行：{self._last_run_at} · {self._last_result or '—'}"
                + (f" · {self._last_message}" if self._last_message else "")
            )
        content.append(
            {
                "component": "VAlert",
                "props": {
                    "type": "success" if signed_today else "info",
                    "variant": "tonal",
                    "text": "\n".join(lines),
                    "style": "white-space: pre-line;",
                },
            }
        )
        return content

    # ── 插件 API ──────────────────────────────────────────────────

    def get_api(self) -> List[Dict[str, Any]]:
        """插件 API：面板按钮与外部自动化分路鉴权。

        * ``/run`` 用 ``bear``（面板详情页按钮经 ``window.MoviePilotAPI`` 调用，
          携带的是登录态）；
        * ``/trigger`` 是同一执行入口的 ``apikey`` 版本（外部脚本/自动化用）；
        * ``response_model`` 必须与实际返回**同型**：端点返回
          ``schemas.Response[...]`` 信封，声明也必须是信封类型——
          声明成裸数据模型会被 FastAPI 按声明序列化，拍成全默认值（实测踩过）。
        """
        return [
            {
                "path": "/run",
                "endpoint": self.api_run,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "立即执行一次签到（详情页按钮；今日已签则跳过，force=true 仅跳过本地记录判断）",
                "response_model": schemas.Response[models.RunData],
            },
            {
                "path": "/trigger",
                "endpoint": self.api_run,
                "methods": ["POST"],
                "auth": "apikey",
                "summary": "外部触发一次签到（同 /run，apikey 鉴权）",
                "response_model": schemas.Response[models.RunData],
            },
            {
                "path": "/status",
                "endpoint": self.api_status,
                "methods": ["GET"],
                "auth": "apikey",
                "summary": "签到记录快照（不出网，只读本地记录）",
                "response_model": schemas.Response[models.StatusData],
            },
        ]

    async def api_run(self, force: bool = False) -> "schemas.Response[models.RunData]":
        """手动/外部触发一次签到。"""
        data = await self._sign_once(force=bool(force), reason="手动")
        return schemas.Response(success=True, data=data)

    async def api_status(self) -> "schemas.Response[models.StatusData]":
        """读取本地签到记录快照。查询正常但无记录也返回 success=true。"""
        record = normalize_record(self.get_data(RECORD_KEY))
        return schemas.Response(
            success=True,
            data=models.StatusData(
                enabled=self._enabled,
                has_ticket=bool(self._ticket),
                cron=self._cron,
                last_sign_date=record["last_sign_date"],
                total_days=record["total_days"],
                continuous_days=record["continuous_days"],
                max_continuous_days=record["max_continuous_days"],
                last_update_time=record["last_update_time"],
                sign_history=record["sign_history"],
            ),
        )
