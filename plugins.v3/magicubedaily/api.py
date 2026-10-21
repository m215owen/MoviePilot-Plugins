"""插件 HTTP 接口：``/status`` 看状态、``/run`` 立即领取、``/records`` 看流水。

路径统一是 ``/api/v1/plugin/MagicubeDaily/<path>``（宿主前缀由插件 ID 自动拼）。
鉴权用 ``apikey``：这些路由的消费者是外部脚本 / 自动化（``X-API-KEY`` 或 ``?apikey=``），
面板本身不调它们 —— 插件详情页走的是同步的 ``get_page()``，不经过 HTTP。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app import schemas
from app.sdk.logging import logger

from . import models
from .constants import LOGIN_SOURCE_LABELS, PLUGIN_NAME
from .service import (
    build_days,
    fetch_status,
    now_str,
    run_claim,
    summarize_records,
    today_str,
)

__all__ = ["ApiMixin"]


class ApiMixin:
    # ── 路由声明 ──────────────────────────────────────────────────

    def get_api(self) -> List[Dict[str, Any]]:
        return [
            {
                "path": "/status",
                "endpoint": self.api_status,
                "methods": ["GET"],
                "auth": "apikey",
                "summary": "魔粒状态：登录态 / 今日发放 / 余额 / 近几天收益",
                "response_model": models.StatusResponse,
            },
            {
                "path": "/run",
                "endpoint": self.api_run,
                "methods": ["POST"],
                "auth": "apikey",
                "summary": "立即执行一次领取（今日已领则跳过）",
                "response_model": models.RunResponse,
            },
            {
                "path": "/records",
                "endpoint": self.api_records,
                "methods": ["GET"],
                "auth": "apikey",
                "summary": "魔粒流水原始记录（新→旧）",
                "response_model": models.HistoryResponse,
            },
        ]

    # ── 实现 ─────────────────────────────────────────────────────

    async def api_status(self, days: int = 7) -> "schemas.Response[models.StatusData]":
        """只读状态：不触发任何发放。"""
        wanted = max(1, min(30, int(days or 7)))
        snapshot = await fetch_status(
            self._login_source,
            self._cookie,
            timeout=self._timeout,
            proxy=self._proxy,
            days=wanted,
            history=self._balance_history,
        )
        today = snapshot.today or summarize_records([], today_str())
        user = snapshot.user or {}
        # 顺手把快照留下：详情页（同步方法）就不必再出网
        self._record_snapshot(snapshot)
        return schemas.Response(
            success=True,
            data=models.StatusData(
                enabled=self._enabled,
                logged_in=snapshot.logged_in,
                login_source=self._login_source,
                source_label=LOGIN_SOURCE_LABELS.get(self._login_source, self._login_source),
                error=snapshot.error,
                username=str(user.get("username") or ""),
                nickname=str(user.get("nickname") or ""),
                avatar_url=str(user.get("avatar_url") or ""),
                balance=snapshot.balance,
                available=snapshot.available,
                frozen=snapshot.frozen,
                today=models.TodayData(**today.to_dict()),
                days=[models.DayRow(**row) for row in snapshot.days],
                history=[models.BalancePoint(**row) for row in snapshot.history],
                samples=[models.BalanceSample(**row) for row in snapshot.samples],
                cron=self._cron,
                refresh_cron=self._refresh_cron,
                checked_at=now_str(),
                last_run_at=self._last_run_at,
                last_result=self._last_result,
                last_message=self._last_message,
            ),
        )

    async def api_run(self, force: bool = False) -> "schemas.Response[models.RunData]":
        """立即领取一次。``force=true`` 时即便今日已领也会再访问一次站点。"""
        outcome = await self._claim_once(force=bool(force), reason="手动")
        today = outcome.today_after or outcome.today_before or summarize_records([], today_str())
        return schemas.Response(
            success=True,
            data=models.RunData(
                ok=outcome.ok,
                skipped=outcome.skipped,
                message=outcome.message,
                error=outcome.error,
                date=outcome.date,
                ran_at=outcome.ran_at,
                gained=outcome.gained,
                balance=outcome.balance,
                available=outcome.available,
                username=str((outcome.user or {}).get("username") or ""),
                nickname=str((outcome.user or {}).get("nickname") or ""),
                touched=[models.TouchRow(**row) for row in outcome.touched],
                today=models.TodayData(**today.to_dict()),
            ),
        )

    async def api_records(self, page_size: int = 50) -> "schemas.Response[models.HistoryData]":
        """站点流水的原始条目，用于排查「为什么今天没发」。"""
        from .client import MagicubeClient  # 局部导入，避免模块级循环

        cookie, err = await self._resolve_cookie()
        if not cookie:
            return schemas.Response(
                success=False,
                error=err or "未能获取登录态",
                data=models.HistoryData(),
            )
        client = MagicubeClient(cookie, timeout=self._timeout, proxy=self._proxy)
        size = max(1, min(200, int(page_size or 50)))
        records, read_err = await client.transactions(page_size=size)
        if read_err:
            return schemas.Response(success=False, error=read_err, data=models.HistoryData())
        return schemas.Response(
            success=True,
            data=models.HistoryData(total=len(records), records=records),
        )
