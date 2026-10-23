"""魔搭魔粒签到（MoviePilot V3 插件）。

为什么需要它
------------
魔搭社区（modelscope.cn）每天登录送 200 魔粒（绑定阿里云账号再 +50），但**短期魔粒
24 小时过期**，必须天天记得打开站点，断一天就白丢。本插件把这个动作自动化。

机制（2026-10-21 实测，不是猜的）
--------------------------------
* **没有签到接口**。+200/+50 是「当天首次带登录态访问站点」的后端副作用，服务端自己去重。
  所以插件做的是「模拟打开一次站点」（首页 + 我的概览 + 魔粒用量页），而不是 POST 签到。
* 是否真的发了，**只认流水**：``GET /openapi/v1/magicubes/transactions`` 里当天出现
  ``type=EARN`` + ``rule_key=daily_active``（200）与 ``rule_key=aliyun_bindlogin``（50）。
  访问返回 200 不代表发了，所以判定不靠状态码。
* 余额 ``GET /openapi/v1/magicubes/balance`` 只作参考 —— 24h 过期会把余额差搅乱，
  收益一律按流水算。

登录态来源
----------
默认走**宿主的 CookieCloud**（``.modelscope.cn`` 域），完全不用手填、也随 CookieCloud
自动续期；CookieCloud 里没有魔搭 cookie 时才需要用手填兜底。

不做什么
--------
不实现「点赞/收藏刷魔粒」（star → unstar 循环）。那是明确的刷分滥用，违反社区条款、
有封号风险，收益也只有 40/天。本插件只领「登录就有的那一份」。
"""

from __future__ import annotations

import asyncio
import base64
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from apscheduler.triggers.cron import CronTrigger

from app.sdk import scheduler as scheduler_sdk
from app.sdk.logging import logger
from app.sdk.plugin import _PluginBase

from .api import ApiMixin as _ApiMixin
from .chart import render_wave_svg
from .constants import (
    DEFAULT_CRON,
    DEFAULT_REFRESH_CRON,
    DEFAULT_TIMEOUT,
    LOGIN_SOURCE_COOKIECLOUD,
    LOGIN_SOURCE_LABELS,
    LOGIN_SOURCE_MANUAL,
    LOGIN_SOURCES,
    PLUGIN_ID,
    PLUGIN_NAME,
)
from .service import (
    BALANCE_SAMPLE_LIMIT,
    ClaimOutcome,
    StatusSnapshot,
    build_balance_samples,
    fetch_status,
    now_str,
    resolve_cookie,
    run_claim,
    summarize_records,
    today_str,
)

# 消息类型枚举在宿主版本间改过名（MessageType / NotificationType），做一次兼容导入，
# 避免因枚举改名导致整个插件加载失败。
try:  # pragma: no cover - 取决于宿主版本
    from app.schemas.types import MessageType as _MessageType
except ImportError:  # pragma: no cover
    from app.schemas.types import NotificationType as _MessageType  # type: ignore

#: 持久化状态（最近一次执行 + 最近一次状态快照）的键
_STATE_KEY = "magicube_daily_state"

#: 定时服务 ID（必须稳定且全局唯一）
_SERVICE_ID = f"{PLUGIN_ID}.daily"
#: 余额/状态刷新服务 ID
_REFRESH_SERVICE_ID = f"{PLUGIN_ID}.refresh"
#: 启动后立即刷一次快照的一次性任务 ID
_REFRESH_ON_START_ID = "refresh_on_start"


class MagicubeDaily(_ApiMixin, _PluginBase):
    # ── 插件元数据（宿主用 AST 静态解析，必须字面量）────────────────────
    plugin_name = PLUGIN_NAME
    plugin_desc = (
        "每天自动「登录」魔搭社区（modelscope.cn）领取 200 魔粒（绑定阿里云 +50）。"
        "魔粒 24 小时过期，断一天白丢一天。登录态默认复用宿主 CookieCloud，"
        "无需手填密码；执行结果按流水核对，领没领一目了然。"
    )
    plugin_icon = (
        "https://raw.githubusercontent.com/m215owen/MoviePilot-Plugins/main/"
        "icons/MagicubeDaily.png"
    )
    plugin_version = "1.0.0"
    plugin_author = "m215owen"
    author_url = "https://github.com/m215owen"
    plugin_config_prefix = "magicubedaily_"
    plugin_order = 92
    auth_level = 1

    # ── 运行时状态（init_plugin 全部重置，避免跨实例串味）──────────────
    _enabled: bool = False
    _login_source: str = LOGIN_SOURCE_COOKIECLOUD
    _cookie: str = ""
    _cron: str = DEFAULT_CRON
    #: 余额/今日状态的后台刷新周期（只读，不触发发放）；留空则不刷新
    _refresh_cron: str = DEFAULT_REFRESH_CRON
    _notify: bool = True
    _timeout: int = DEFAULT_TIMEOUT
    _proxy: str = ""
    _last_run_at: str = ""
    _last_result: str = ""
    _last_message: str = ""
    #: 最近一次状态快照（``/status`` 或领取后写入），供详情页展示，避免打开页面就出网
    _snapshot: Optional[Dict[str, Any]] = None
    #: 本地实测的每日余额 ``{YYYY-MM-DD: int}``，用于给「近 N 天」视图提供比反推更可信的点
    _balance_history: Dict[str, int] = {}
    #: 本地实测的**每次刷新采样** ``[{ts, balance}]``，用于给「近 N 小时」视图按刷新周期出点
    _balance_samples: List[Dict[str, Any]] = []

    def init_plugin(self, config: dict | None = None) -> None:
        """读取配置并恢复持久化状态。必须允许重复调用（宿主会多次触发）。"""
        self._enabled = False
        self._login_source = LOGIN_SOURCE_COOKIECLOUD
        self._cookie = ""
        self._cron = DEFAULT_CRON
        self._refresh_cron = DEFAULT_REFRESH_CRON
        self._notify = True
        self._timeout = DEFAULT_TIMEOUT
        self._proxy = ""
        self._last_run_at = ""
        self._last_result = ""
        self._last_message = ""
        self._snapshot = None
        self._balance_history = {}
        self._balance_samples = []

        config = config or {}
        self._enabled = bool(config.get("enabled", False))

        source = str(config.get("login_source") or LOGIN_SOURCE_COOKIECLOUD).strip()
        self._login_source = source if source in LOGIN_SOURCES else LOGIN_SOURCE_COOKIECLOUD

        self._cookie = str(config.get("cookie") or "").strip()
        self._cron = str(config.get("cron") or DEFAULT_CRON).strip() or DEFAULT_CRON
        # 刷新周期留空是「关掉自动刷新」，不能像 cron 那样回落到默认值
        raw_refresh = config.get("refresh_cron")
        self._refresh_cron = (
            DEFAULT_REFRESH_CRON if raw_refresh is None else str(raw_refresh).strip()
        )
        self._notify = bool(config.get("notify", True))
        try:
            self._timeout = max(5, int(config.get("timeout") or DEFAULT_TIMEOUT))
        except (TypeError, ValueError):
            self._timeout = DEFAULT_TIMEOUT
        self._proxy = str(config.get("proxy") or "").strip()

        # 恢复上次运行结果（重启后面板不会变成空白）
        try:
            state = self.get_data(_STATE_KEY) or {}
        except Exception as err:  # noqa: BLE001 - 老数据损坏不该阻断启动
            logger.debug(f"{PLUGIN_NAME}：读取持久化状态失败（忽略）：{err}")
            state = {}
        if isinstance(state, dict):
            self._last_run_at = str(state.get("last_run_at") or "")
            self._last_result = str(state.get("last_result") or "")
            self._last_message = str(state.get("last_message") or "")
            snapshot = state.get("snapshot")
            self._snapshot = snapshot if isinstance(snapshot, dict) else None
            self._balance_history = _clean_history(state.get("balance_history"))
            self._balance_samples = _clean_samples(state.get("balance_samples"))

        logger.info(
            f"{PLUGIN_NAME}：初始化完成（启用={self._enabled}，登录态来源="
            f"{LOGIN_SOURCE_LABELS.get(self._login_source, self._login_source)}，"
            f"领取周期={self._cron}，余额刷新={self._refresh_cron or '关'}）"
        )

        # 启用后尽快把余额/账号刷进快照 —— 否则面板要等第一个刷新周期才有数字。
        # 一次性任务交给宿主调度器托管（同 ID 重复登记会替换，不会堆积）。
        if self._enabled and self._refresh_cron:
            try:
                scheduler_sdk.add_plugin_once_job(
                    PLUGIN_ID,
                    _REFRESH_ON_START_ID,
                    self._service_refresh,
                    f"{PLUGIN_NAME} 启动刷新",
                    delay_seconds=8,
                )
            except Exception as err:  # noqa: BLE001 - 调度器未就绪时忽略
                logger.debug(f"{PLUGIN_NAME}：登记启动刷新失败（忽略）：{err}")

    def get_state(self) -> bool:
        return bool(self._enabled)

    def stop_service(self) -> None:
        """本插件不自建线程 / 调度器 / 连接池，无需释放资源。

        保留该方法是为了明确「重复调用安全」，也方便将来接入一次性任务时统一清理。
        """
        logger.debug(f"{PLUGIN_NAME}：stop_service 已调用（无可释放资源）")

    # ── 定时服务 ──────────────────────────────────────────────────

    def get_service(self) -> List[Dict[str, Any]]:
        """注册两个周期服务：

        1. **每日领取**（``cron``）：模拟打开站点触发 +200/+50；
        2. **余额刷新**（``refresh_cron``）：只读拉余额/今日/账号写进快照，
           让详情页打开就能看到**较新的余额与登录账号**，且绝不触发发放。
        """
        if not self._enabled:
            return []

        services: List[Dict[str, Any]] = []

        if self._cron:
            try:
                services.append(
                    {
                        "id": _SERVICE_ID,
                        "name": f"{PLUGIN_NAME} 每日领取",
                        "trigger": CronTrigger.from_crontab(self._cron),
                        "func": self._service_claim,
                        "kwargs": {},
                    }
                )
            except Exception as err:  # noqa: BLE001 - cron 写错不该让插件整体不可用
                logger.error(f"{PLUGIN_NAME}：领取周期 cron 无效（{self._cron}）：{err}")

        if self._refresh_cron:
            try:
                services.append(
                    {
                        "id": _REFRESH_SERVICE_ID,
                        "name": f"{PLUGIN_NAME} 余额刷新",
                        "trigger": CronTrigger.from_crontab(self._refresh_cron),
                        "func": self._service_refresh,
                        "kwargs": {},
                    }
                )
            except Exception as err:  # noqa: BLE001
                logger.error(f"{PLUGIN_NAME}：刷新周期 cron 无效（{self._refresh_cron}）：{err}")

        return services

    async def _service_claim(self) -> None:
        """定时入口：跑一次领取并记录结果。异常一律吞掉并留日志，不污染宿主调度器。"""
        try:
            await self._claim_once(reason="定时")
        except Exception as err:  # noqa: BLE001
            logger.error(f"{PLUGIN_NAME}：定时领取异常：{err}")
            self._record_failure(f"定时执行异常：{err}")

    async def _service_refresh(self) -> None:
        """只读刷新：余额、今日发放、登录账号 → 快照。**不访问首页、不触发发放、不发通知**。"""
        try:
            snapshot = await fetch_status(
                self._login_source,
                self._cookie,
                timeout=self._timeout,
                proxy=self._proxy,
                days=7,
                history=self._balance_history,
            )
        except Exception as err:  # noqa: BLE001
            logger.warning(f"{PLUGIN_NAME}：刷新余额异常：{err}")
            return

        self._record_snapshot(snapshot)
        if snapshot.error:
            logger.debug(f"{PLUGIN_NAME}：刷新余额未成功：{snapshot.error}")
        else:
            user = snapshot.user or {}
            logger.info(
                f"{PLUGIN_NAME}：余额已刷新 —— {user.get('nickname') or user.get('username') or '未知账号'}"
                f" / {snapshot.balance} 魔粒"
            )

    # ── 核心动作 ──────────────────────────────────────────────────

    async def _claim_once(self, force: bool = False, reason: str = "") -> ClaimOutcome:
        """执行一次领取，落盘结果并按需通知。"""
        try:
            outcome = await run_claim(
                self._login_source,
                self._cookie,
                timeout=self._timeout,
                proxy=self._proxy,
                force=force,
            )
        except Exception as err:  # noqa: BLE001 - 任何意外都转成可展示的失败结果
            logger.error(f"{PLUGIN_NAME}：领取过程异常：{err}")
            self._record_failure(f"领取过程异常：{err}")
            failed = ClaimOutcome(ok=False, error=f"领取过程异常：{err}", message="执行失败")
            return failed

        self._record_outcome(outcome)
        if self._notify:
            self._notify_result(outcome, reason=reason)
        return outcome

    async def _resolve_cookie(self) -> Tuple[str, str]:
        """给 ``/records`` 之类需要登录态的接口用。"""
        return await resolve_cookie(self._login_source, self._cookie)

    # ── 结果落盘与通知 ─────────────────────────────────────────────

    def _record_outcome(self, outcome: ClaimOutcome) -> None:
        """把一次执行结果写进运行时状态 + 持久化（面板 / 重启后可见）。"""
        self._last_run_at = outcome.ran_at
        self._last_result = "成功" if outcome.ok else ("跳过" if outcome.skipped else "失败")
        self._last_message = outcome.message or outcome.error
        self._remember_balance(outcome.balance)
        today = outcome.today_after or outcome.today_before
        self._remember_balance(outcome.balance)
        samples = build_balance_samples(self._balance_samples)
        if today is not None:
            self._snapshot = {
                "checked_at": outcome.ran_at,
                "logged_in": True,
                "error": outcome.error,
                "balance": outcome.balance,
                "available": outcome.available,
                "today": today.to_dict(),
                "gained": outcome.gained,
                "user": dict(outcome.user or {}),
                "samples": samples,
            }
        elif outcome.error:
            self._snapshot = {
                "checked_at": outcome.ran_at,
                "logged_in": False,
                "error": outcome.error,
                "user": dict(outcome.user or {}),
                "samples": samples,
            }
        self._persist_state()

    def _record_failure(self, message: str) -> None:
        self._last_run_at = _now()
        self._last_result = "失败"
        self._last_message = message
        self._persist_state()

    def _record_snapshot(self, snapshot: StatusSnapshot) -> None:
        """``/status`` 或后台刷新查完顺手把快照留下，详情页就不用再出网。"""
        self._remember_balance(snapshot.balance)
        # 采样点要在「本次」落盘之后重算，否则图上永远差最新那一个
        snapshot.samples = build_balance_samples(self._balance_samples)
        self._snapshot = {
            "checked_at": _now(),
            "logged_in": snapshot.logged_in,
            "error": snapshot.error,
            "balance": snapshot.balance,
            "available": snapshot.available,
            "today": snapshot.today.to_dict() if snapshot.today else None,
            "days": snapshot.days,
            "user": dict(snapshot.user or {}),
            "history": snapshot.history,
            "samples": snapshot.samples,
        }
        self._persist_state()

    def _remember_balance(self, balance: Optional[int]) -> None:
        """把这次实测到的余额记进本地历史。

        记两份粒度，分别服务两张图：

        * ``_balance_history``：按天，同一天覆盖 —— 喂「近 14 天」视图（比流水反推更可信）；
        * ``_balance_samples``：按**每次刷新**追加带时间戳的采样 —— 喂「近 24 小时」视图，
          刷新周期多密，图上的点就多密。
        """
        if balance is None:
            return
        try:
            value = int(balance)
        except (TypeError, ValueError):
            return

        history = dict(self._balance_history or {})
        history[today_str()] = value
        # 只留最近 60 天，避免状态无限增长
        for stale in sorted(history)[:-60]:
            history.pop(stale, None)
        self._balance_history = history

        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = {"ts": stamp, "balance": value}
        samples = [dict(item) for item in (self._balance_samples or []) if isinstance(item, dict)]
        if samples and samples[-1].get("ts") == stamp:
            # 同一秒内重复刷新只保留最后一次，别让图上叠点
            samples[-1] = entry
        else:
            samples.append(entry)
        self._balance_samples = samples[-BALANCE_SAMPLE_LIMIT:]

    def _persist_state(self) -> None:
        try:
            self.save_data(
                _STATE_KEY,
                {
                    "last_run_at": self._last_run_at,
                    "last_result": self._last_result,
                    "last_message": self._last_message,
                    "snapshot": self._snapshot,
                    "balance_history": self._balance_history,
                },
            )
        except Exception as err:  # noqa: BLE001
            logger.debug(f"{PLUGIN_NAME}：保存状态失败（忽略）：{err}")

    def _notify_result(self, outcome: ClaimOutcome, reason: str = "") -> None:
        """发一条插件消息。通知渠道没配也只是一条 warning，不影响主流程。"""
        try:
            today = outcome.today_after or outcome.today_before
            lines: List[str] = []
            account = str((outcome.user or {}).get("nickname") or (outcome.user or {}).get("username") or "")
            if account:
                lines.append(f"账号：{account}")
            if reason:
                lines.append(f"触发方式：{reason}")
            lines.append(f"结果：{outcome.message or outcome.error or '无'}")
            if outcome.error and outcome.message:
                lines.append(f"错误：{outcome.error}")
            if today is not None:
                lines.append(
                    f"今日累计：{today.total} 魔粒"
                    f"（登录 {'已发' if today.login_done else '未发'}"
                    f" / 阿里云 {'已发' if today.aliyun_done else '未发'}）"
                )
                if today.expire_at:
                    lines.append(f"最早到期：{today.expire_at}")
            if outcome.gained:
                lines.append(f"本次新增：+{outcome.gained}")
            if outcome.balance is not None:
                lines.append(f"当前余额：{outcome.balance}")
            self.post_message(
                mtype=_MessageType.Plugin,
                title=f"【{self.plugin_name}】{'领取成功' if outcome.ok else '领取未成功'}",
                text="\n".join(lines),
            )
        except Exception as err:  # noqa: BLE001 - 未配置通知渠道时兜底
            logger.warning(f"{PLUGIN_NAME}：发送通知失败：{err}")

    # ── 配置表单 ──────────────────────────────────────────────────

    def get_form(self) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        return [
            {
                "component": "VForm",
                "content": [
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 2},
                                "content": [
                                    {
                                        "component": "VSwitch",
                                        "props": {
                                            "model": "enabled",
                                            "label": "启用插件",
                                            "hint": "关闭后不再定时领取",
                                            "persistent-hint": True,
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 2},
                                "content": [
                                    {
                                        "component": "VSwitch",
                                        "props": {
                                            "model": "notify",
                                            "label": "发送通知",
                                            "hint": "每次执行结果推送到已配置的通知渠道",
                                            "persistent-hint": True,
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [
                                    {
                                        "component": "VCronField",
                                        "props": {
                                            "model": "cron",
                                            "label": "领取周期",
                                            "placeholder": "5 位 cron 表达式",
                                            "hint": "魔粒 24 小时过期，建议每天固定时间跑一次（默认 08:10）",
                                            "persistent-hint": True,
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [
                                    {
                                        "component": "VCronField",
                                        "props": {
                                            "model": "refresh_cron",
                                            "label": "余额刷新周期",
                                            "placeholder": "留空则只在领取后更新",
                                            "hint": "只读刷新余额与账号，不会触发发放（默认每 30 分钟）",
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
                                        "component": "VSelect",
                                        "props": {
                                            "model": "login_source",
                                            "label": "登录态来源",
                                            "items": [
                                                {
                                                    "title": LOGIN_SOURCE_LABELS[LOGIN_SOURCE_COOKIECLOUD],
                                                    "value": LOGIN_SOURCE_COOKIECLOUD,
                                                },
                                                {
                                                    "title": LOGIN_SOURCE_LABELS[LOGIN_SOURCE_MANUAL],
                                                    "value": LOGIN_SOURCE_MANUAL,
                                                },
                                            ],
                                            "hint": "推荐 CookieCloud：宿主已同步过魔搭登录态就不用管",
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
                                            "model": "cookie",
                                            "label": "手动 Cookie（仅手动模式使用）",
                                            "type": "password",
                                            "placeholder": "m_session_id=xxxx; 其它 cookie 可选",
                                            "hint": "从浏览器复制 Cookie 请求头即可；CookieCloud 模式下留空",
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
                                            "hint": "CookieCloud 拉取另有 120 秒独立超时",
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
                                                "魔搭没有「签到接口」：每日 200 魔粒（绑阿里云 +50）"
                                                "是当天首次带登录态访问站点时后端自动发放的，服务端会去重。"
                                                "本插件做的就是模拟打开一次站点，然后用魔粒流水核对是否真的到账。"
                                                "\n安装后可在详情页点「立即执行」或调用 "
                                                "/api/v1/plugin/MagicubeDaily/run 手动触发。"
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
        ], {
            "enabled": self._enabled,
            "notify": self._notify,
            "cron": self._cron,
            "refresh_cron": self._refresh_cron,
            "login_source": self._login_source,
            "cookie": self._cookie,
            "timeout": self._timeout,
            "proxy": self._proxy,
        }

    # ── 详情页 ────────────────────────────────────────────────────

    def get_page(self) -> List[Dict[str, Any]]:
        """详情页只展示**已经查到的**状态，不在这里出网（get_page 是同步的）。"""
        content: List[Dict[str, Any]] = []
        snapshot = self._snapshot or {}

        if not self._enabled:
            content.append(
                {
                    "component": "VAlert",
                    "props": {
                        "type": "warning",
                        "variant": "tonal",
                        "text": "插件未启用：不会定时领取。启用并保存后即可按周期自动执行。",
                    },
                }
            )

        if not snapshot:
            content.append(
                {
                    "component": "VAlert",
                    "props": {
                        "type": "info",
                        "variant": "outlined",
                        "text": (
                            "还没有状态快照。\n"
                            "点「立即执行」（或调用 POST /api/v1/plugin/MagicubeDaily/run）"
                            "跑一次，或在插件页刷新后调用 GET /status 拉取实时状态。"
                        ),
                        "style": "white-space: pre-line;",
                    },
                }
            )
            return content

        logged_in = bool(snapshot.get("logged_in"))
        error = str(snapshot.get("error") or "")
        today = snapshot.get("today") or {}
        user = snapshot.get("user") or {}
        username = str(user.get("username") or "")
        nickname = str(user.get("nickname") or "")

        # 首行给出「谁在领」—— 一个 CookieCloud 里可能同时躺着多个账号的 cookie，
        # 看到昵称才能确认领的是不是自己想领的那个号。
        if logged_in:
            if nickname and username and nickname != username:
                header = f"已登录：{nickname}（{username}）"
            elif nickname or username:
                header = f"已登录：{nickname or username}"
            else:
                header = "已登录（未能取到账号名）"
        else:
            header = "登录态无效"
        header += f"\n登录态来源：{LOGIN_SOURCE_LABELS.get(self._login_source, self._login_source)}"
        content.append(
            {
                "component": "VAlert",
                "props": {
                    "type": "success" if logged_in and not error else "error",
                    "variant": "tonal",
                    "text": header + (f"\n{error}" if error else ""),
                    "style": "white-space: pre-line;",
                },
            }
        )

        # 两张波浪图：近 24 小时按**刷新周期**出点，近 14 天取每天最后一次刷新。
        # 数据全部来自插件自己的自动刷新采样 —— 不做流水反推，图上每个数字都是真采到的。
        samples = [
            (str(item.get("ts") or ""), int(item.get("balance") or 0))
            for item in (snapshot.get("samples") or [])
            if isinstance(item, dict) and item.get("ts")
        ]
        daily = [
            (str(item.get("date") or ""), int(item.get("balance") or 0))
            for item in (snapshot.get("history") or [])
            if isinstance(item, dict) and item.get("date")
        ]
        interval_hint = (
            f"每 {self._refresh_cron} 刷新一次" if self._refresh_cron else "仅在领取后刷新"
        )
        content.append(
            _image_block(
                render_wave_svg(
                    samples,
                    title="近 24 小时余额",
                    subtitle=(
                        f"{interval_hint} · 已采 {len(samples)} 个点"
                        if samples
                        else f"{interval_hint} · 暂无采样"
                    ),
                    time_axis=True,
                )
            )
        )
        content.append(
            _image_block(
                render_wave_svg(
                    daily,
                    title="近 14 天余额",
                    subtitle=(
                        f"每天最后一次刷新的数值 · {len(daily)} 天"
                        if daily
                        else "每天最后一次刷新的数值 · 暂无数据"
                    ),
                )
            )
        )

        lines: List[str] = []
        checked_at = snapshot.get("checked_at") or "—"
        refresh_desc = (
            f"后台按 {self._refresh_cron} 自动刷新" if self._refresh_cron else "仅领取后更新"
        )
        balance = snapshot.get("balance")
        if balance is not None:
            # ── 余额大字卡：数字放大显眼，并直接给出「较上次测量」的增减 ──
            # 上一次测量取自采样序列（时间升序）：最后一条通常就是本次测量值，
            # 它的前一条才是「上次」；若最后一条与快照余额不一致（比如采样已按
            # 24 小时窗口裁剪），则最后一条本身就是上次测量。
            current = int(balance)
            prev_value: Optional[int] = None
            prev_ts = ""
            if samples:
                last_ts, last_value = samples[-1]
                if last_value == current:
                    if len(samples) >= 2:
                        prev_ts, prev_value = samples[-2]
                else:
                    prev_ts, prev_value = last_ts, last_value

            if prev_value is None:
                card_color, chip = "primary", "首次测量"
                trend = "还没有可比较的上次测量值，等下一次自动刷新"
            else:
                delta = current - prev_value
                if delta > 0:
                    card_color, chip = "success", f"▲ +{delta}"
                    trend = f"较上次测量（{prev_ts}）多了 {delta} 魔粒"
                elif delta < 0:
                    card_color, chip = "warning", f"▼ {delta}"
                    trend = f"较上次测量（{prev_ts}）少了 {abs(delta)} 魔粒"
                else:
                    card_color, chip = "primary", "— 持平"
                    trend = f"与上次测量（{prev_ts}）持平"

            sub_parts = [f"数据时间：{checked_at}"]
            if snapshot.get("available") is not None:
                sub_parts.append(f"可用 {snapshot.get('available')}")
            sub_parts.append(refresh_desc)
            sub_parts.append(trend)
            content.append(
                {
                    "component": "VCard",
                    "props": {"variant": "tonal", "color": card_color, "class": "mt-2 mb-1"},
                    "content": [
                        {
                            "component": "VCardText",
                            "props": {"class": "py-3"},
                            "content": [
                                {
                                    "component": "VRow",
                                    "props": {"align": "center", "no-gutters": True},
                                    "content": [
                                        {
                                            "component": "VCol",
                                            "props": {"cols": "auto"},
                                            "content": [
                                                {
                                                    "component": "VCardText",
                                                    "props": {
                                                        "class": "text-h3 font-weight-bold pa-0"
                                                    },
                                                    "text": str(current),
                                                }
                                            ],
                                        },
                                        {
                                            "component": "VCol",
                                            "props": {"cols": "auto", "class": "ml-1"},
                                            "content": [
                                                {
                                                    "component": "VCardText",
                                                    "props": {
                                                        "class": "text-body-1 text-medium-emphasis pa-0"
                                                    },
                                                    "text": "魔粒",
                                                }
                                            ],
                                        },
                                        {
                                            "component": "VCol",
                                            "props": {"cols": "auto", "class": "ml-auto"},
                                            "content": [
                                                {
                                                    "component": "VChip",
                                                    "props": {
                                                        "color": (
                                                            card_color
                                                            if card_color != "primary"
                                                            else "info"
                                                        ),
                                                        "variant": "flat",
                                                    },
                                                    "text": chip,
                                                }
                                            ],
                                        },
                                    ],
                                },
                                {
                                    "component": "VCardText",
                                    "props": {
                                        "class": "text-caption text-medium-emphasis pa-0 mt-1"
                                    },
                                    "text": " · ".join(sub_parts),
                                },
                            ],
                        }
                    ],
                }
            )
        else:
            lines.append(f"数据时间：{checked_at} · {refresh_desc}")
        if today:
            items = today.get("items") or []
            detail = " + ".join(
                f"{item.get('title')} {item.get('amount')}"
                for item in items
                if item.get("is_daily")
            )
            lines.append(
                f"今日（{today.get('date')}）：{today.get('total', 0)} 魔粒"
                f"{('（' + detail + '）') if detail else ''}"
            )
            lines.append(
                "今日登录奖励："
                + ("已发放" if today.get("login_done") else "未发放")
                + "；阿里云绑定奖励："
                + ("已发放" if today.get("aliyun_done") else "未发放（未绑阿里云时正常）")
            )
            if today.get("expire_at"):
                lines.append(f"最早到期：{today.get('expire_at')}（短期魔粒 24 小时）")
        if self._last_run_at:
            lines.append(
                f"上次执行：{self._last_run_at} · {self._last_result or '—'}"
                + (f" · {self._last_message}" if self._last_message else "")
            )
        content.append(
            {
                "component": "VAlert",
                "props": {
                    "type": "info",
                    "variant": "outlined",
                    "text": "\n".join(lines),
                    "style": "white-space: pre-line;",
                },
            }
        )

        days = snapshot.get("days") or []
        if isinstance(days, list) and days:
            rows = " · ".join(
                f"{str(row.get('date') or '')[-5:]} {row.get('total', 0)}"
                for row in days[:14]
                if isinstance(row, dict)
            )
            content.append(
                {
                    "component": "VAlert",
                    "props": {
                        "type": "success",
                        "variant": "outlined",
                        "text": f"近 {len(days)} 天发放：{rows}",
                    },
                }
            )
        return content


def _now() -> str:
    """本地时间字符串（插件内部用）"""
    return now_str()


def _image_block(svg: str) -> Dict[str, Any]:
    """把 SVG 包成 ``VImg`` 组件（base64 data URI）。

    面板是 Vuetify 组件 JSON，塞不了脚本、也发不了带登录态的图片请求，所以图只能
    这样内联。``cover=False`` 是必须的：``VImg`` 默认 ``object-fit: cover`` 会把曲线裁掉。
    """
    encoded = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return {
        "component": "VImg",
        "props": {
            "src": f"data:image/svg+xml;base64,{encoded}",
            "alt": "魔粒余额走势",
            "cover": False,
            "style": "width:100%;max-width:660px;height:auto;display:block;margin:4px 0 8px 0;",
        },
    }


def _clean_samples(raw: Any) -> List[Dict[str, Any]]:
    """清洗持久化的采样点：只留合法的 ``{ts, balance}``，按时间升序、去重、限量。"""
    if not isinstance(raw, (list, tuple)):
        return []
    rows: List[Tuple[str, int]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        ts = str(item.get("ts") or "").strip()
        try:
            datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
        try:
            rows.append((ts, int(item.get("balance"))))
        except (TypeError, ValueError):
            continue
    rows.sort(key=lambda pair: pair[0])
    deduped: List[Tuple[str, int]] = []
    for ts, balance in rows:
        if deduped and deduped[-1][0] == ts:
            deduped[-1] = (ts, balance)
        else:
            deduped.append((ts, balance))
    return [{"ts": ts, "balance": balance} for ts, balance in deduped[-BALANCE_SAMPLE_LIMIT:]]


def _clean_history(raw: Any) -> Dict[str, int]:
    """清洗持久化的余额历史：只留 ``YYYY-MM-DD`` 键与整数余额。"""
    if not isinstance(raw, dict):
        return {}
    cleaned: Dict[str, int] = {}
    for key, value in raw.items():
        text = str(key)[:10]
        if len(text) != 10:
            continue
        try:
            cleaned[text] = int(value)
        except (TypeError, ValueError):
            continue
    return cleaned
