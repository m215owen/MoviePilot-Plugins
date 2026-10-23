"""滴滴能源签到 —— 站点访问与签到记录逻辑。

分层原则（按官方文档「控制导入副作用」的要求）：

* 本模块只放**纯逻辑 + 少量 await**，不持全局状态、不在导入期出网；
* ``sign_once`` 负责一次签到请求与结果判定；``sign_with_retry`` 负责重试编排；
* 签到记录（``sign_record``）的读写交给插件类经 ``save_data``/``get_data``
  落到插件数据区，本模块只提供纯函数做更新计算。
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx2
from app.sdk.logging import logger
from app.sdk.network import AsyncRequestUtils

from .constants import (
    BASE_URL,
    DO_SIGN_PATH,
    DUPLICATE_CODE,
    DUPLICATE_MSG_PATTERN,
    HISTORY_KEEP_DAYS,
    MAX_ATTEMPTS,
    REFERER,
    RETRY_DELAY_SECONDS,
    SIGN_PAGE_PATH,
    USER_AGENT,
)

__all__ = [
    "SignPage",
    "SignResult",
    "fetch_sign_page",
    "masked_ticket",
    "new_record",
    "normalize_record",
    "parse_sign_page",
    "parse_sign_payload",
    "sign_once",
    "sign_with_retry",
    "today_str",
    "update_record",
]


def today_str() -> str:
    """本地时区的今天（``YYYY-MM-DD``），与签到记录里的日期同格式。"""
    return datetime.now().strftime("%Y-%m-%d")


def now_str() -> str:
    """人类可读的当前时间。"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def masked_ticket(ticket: str) -> str:
    """脱敏展示：``abcdef...wxyz``，日志里不出现完整凭证。"""
    if len(ticket) <= 10:
        return ticket[:2] + "***"
    return ticket[:6] + "..." + ticket[-4:]


@dataclass
class SignResult:
    """一次签到的归一化结果。

    * ``ok``：今日任务完成（新签成功**或**站点明确返回已签到）；
    * ``is_ambiguous``：站点返回 ``DO_SIGN_ERROR`` 通用失败文案。**2026-10-22
      实测**：该账号当日已签时接口同样返回 ``DO_SIGN_ERROR``/「签到失败，请稍后重试」，
      并不会明确说"已签到"——所以这种返回无法区分"已签"与"真失败"，
      不能据此写签到记录（防止把没签上的日子标成已签）；
    * ``is_error``：请求层异常 / 非 200 / 响应不可解析，重试通常无效；
    * 其余情况为业务失败（可重试）。
    """

    ok: bool = False
    is_new_sign: bool = False
    is_duplicate: bool = False
    is_ambiguous: bool = False
    is_error: bool = False
    continuous_days: int = 0
    message: str = ""
    #: 站点原始返回（仅日志/排查用，不进通知正文，避免泄漏字段）
    raw: Dict[str, Any] = field(default_factory=dict)

    @property
    def has_coupon(self) -> bool:
        """连续签到满 5 天平台发券。"""
        return self.continuous_days >= 5

    @property
    def result_label(self) -> str:
        if self.is_error:
            return "异常"
        if self.is_new_sign:
            return "成功"
        if self.is_duplicate:
            return "已签到"
        if self.is_ambiguous:
            return "未确认（可能已签）"
        return "失败"


@dataclass
class SignPage:
    """签到页数据源（``sign/main``）的归一化状态。

    这是小程序签到页面渲染所用的同一个接口，因此其 ``signRecordDTOList``
    就是页面日历上「已签」的日期集合 —— 权威判定「今日是否已签」。
    """

    ok: bool = False
    signed_today: bool = False
    continuous_days: int = 0
    #: 本轮签到周期（连续模式一轮的天数，通常 5）
    period_days: int = 0
    period_start: str = ""
    period_end: str = ""
    #: 本轮已签日期（升序，站点原样）
    records: List[str] = field(default_factory=list)
    #: 活动标题（已剥掉 <red> 等富文本标签）
    main_title: str = ""
    message: str = ""


def _strip_rich_tags(text: str) -> str:
    """去掉站点文案里的 ``<red>``/``</red>`` 等富文本标签。"""
    return re.sub(r"</?[a-zA-Z][^>]*>", "", text or "").strip()


def parse_sign_page(payload: Any, today: str) -> SignPage:
    """把 ``sign/main`` 的返回解析成 :class:`SignPage`（纯函数）。

    结构（2026-10-22 实测）::

        data.signActivityMeta.title.mainTitle
        data.signInfo[].excitationId / signTaskDTO{
            signMode, signPeriod, startTime, endTime,
            signPrizeDTOList[], signRecordDTOList[{signDate, index}],
            continuousDays}
    """
    if not isinstance(payload, dict) or not payload.get("success"):
        message = ""
        if isinstance(payload, dict):
            message = str(payload.get("msg") or payload.get("message") or "")
        return SignPage(ok=False, message=message or "签到页状态请求失败")

    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}

    title = ""
    meta = data.get("signActivityMeta")
    if isinstance(meta, dict):
        title_meta = meta.get("title")
        if isinstance(title_meta, dict):
            title = _strip_rich_tags(str(title_meta.get("mainTitle") or ""))

    task: Dict[str, Any] = {}
    sign_info = data.get("signInfo")
    if isinstance(sign_info, list):
        for item in sign_info:
            if isinstance(item, dict) and isinstance(item.get("signTaskDTO"), dict):
                task = item["signTaskDTO"]
                break

    records: List[str] = []
    raw_records = task.get("signRecordDTOList")
    if isinstance(raw_records, list):
        for item in raw_records:
            if isinstance(item, dict) and item.get("signDate"):
                records.append(str(item["signDate"])[:10])
    records = sorted(set(records))

    def _int(value: Any) -> int:
        try:
            return max(0, int(value or 0))
        except (TypeError, ValueError):
            return 0

    return SignPage(
        ok=True,
        signed_today=today in records,
        continuous_days=_int(task.get("continuousDays")),
        period_days=_int(task.get("signPeriod")),
        period_start=str(task.get("startTime") or "")[:10],
        period_end=str(task.get("endTime") or "")[:10],
        records=records,
        main_title=title,
        message=str(payload.get("msg") or "服务运行成功"),
    )


def new_record() -> Dict[str, Any]:
    """空签到记录（与首次使用时的初始状态一致）。"""
    return {
        "last_sign_date": "",
        "total_days": 0,
        "continuous_days": 0,
        "max_continuous_days": 0,
        "last_update_time": "",
        "last_ambiguous_date": "",
        "sign_history": [],
    }


def normalize_record(raw: Any) -> Dict[str, Any]:
    """清洗从数据区读出的记录：字段缺失/类型漂移都归位，避免脏数据炸面板。"""
    record = new_record()
    if not isinstance(raw, dict):
        return record
    record["last_sign_date"] = str(raw.get("last_sign_date") or "")[:10]
    for key in ("total_days", "continuous_days", "max_continuous_days"):
        try:
            record[key] = max(0, int(raw.get(key) or 0))
        except (TypeError, ValueError):
            record[key] = 0
    record["last_update_time"] = str(raw.get("last_update_time") or "")
    record["last_ambiguous_date"] = str(raw.get("last_ambiguous_date") or "")[:10]
    history = raw.get("sign_history")
    if isinstance(history, list):
        record["sign_history"] = [
            str(item)[:10] for item in history if isinstance(item, str) and item
        ]
    return record


def update_record(record: Dict[str, Any], today: str, continuous_days: int) -> Dict[str, Any]:
    """签到完成后更新记录（纯函数，返回新 dict，不改入参）。

    * ``last_sign_date`` / ``continuous_days`` 直接覆盖；
    * ``total_days`` 只在今天不在历史里时 +1（防重复计数）；
    * ``sign_history`` 只保留最近 ``HISTORY_KEEP_DAYS`` 天；
    * ``max_continuous_days`` 取历史最大值。
    """
    updated = normalize_record(record)
    updated["last_sign_date"] = today
    updated["continuous_days"] = max(0, int(continuous_days or 0))

    if today not in updated["sign_history"]:
        updated["sign_history"].append(today)
        updated["total_days"] += 1
    updated["sign_history"] = updated["sign_history"][-HISTORY_KEEP_DAYS:]

    if updated["continuous_days"] > updated["max_continuous_days"]:
        updated["max_continuous_days"] = updated["continuous_days"]

    updated["last_update_time"] = now_str()
    return updated


def parse_sign_payload(payload: Any) -> SignResult:
    """把站点返回解析成 :class:`SignResult`（纯函数）。

    判定规则（2026-10-22 实测校准）：

    * ``success=true`` → 新签成功，连续天数取 ``data.signResult.continuousDays``；
    * ``code=DO_SIGN_ERROR`` 且消息含「已签到/已经签到/重复签到」→ 当日重复；
    * ``code=DO_SIGN_ERROR`` 其余消息（如「签到失败，请稍后重试」）→ **未确认**：
      实测当日已签也返回这个形态，无法与真失败区分，调用方不得据此写签到记录；
    * 其余 → 业务失败（``message`` 透传站点消息）。
    """
    if not isinstance(payload, dict):
        return SignResult(is_error=True, message="响应不是 JSON 对象", raw={})

    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    sign_result = data.get("signResult") if isinstance(data.get("signResult"), dict) else {}
    try:
        continuous_days = max(0, int(sign_result.get("continuousDays") or 0))
    except (TypeError, ValueError):
        continuous_days = 0

    message = str(payload.get("msg") or payload.get("message") or "")

    if payload.get("success"):
        return SignResult(
            ok=True,
            is_new_sign=True,
            continuous_days=continuous_days,
            message=message or "签到成功",
            raw=payload,
        )

    code = str(payload.get("code") or "")
    if code == DUPLICATE_CODE and DUPLICATE_MSG_PATTERN.search(message):
        return SignResult(
            ok=True,
            is_duplicate=True,
            continuous_days=continuous_days,
            message="今日已签到",
            raw=payload,
        )

    if code == DUPLICATE_CODE:
        # 实测：当日已签时站点也返回 DO_SIGN_ERROR +「签到失败，请稍后重试」，
        # 无法与真失败区分 → 标记为未确认，不写签到记录。
        return SignResult(
            ok=False,
            is_ambiguous=True,
            continuous_days=continuous_days,
            message=message or "站点未明确返回（可能已签到，也可能失败）",
            raw=payload,
        )

    return SignResult(
        ok=False,
        continuous_days=continuous_days,
        message=message or "签到失败",
        raw=payload,
    )


def _client(ticket: str, timeout: int, proxy: str) -> AsyncRequestUtils:
    """按次创建小程序侧请求客户端（不持连接池）。"""
    return AsyncRequestUtils(
        headers={
            "Referer": REFERER,
            "Content-Type": "application/json",
        },
        ua=USER_AGENT,
        timeout=timeout,
        proxies=proxy or None,
    )


def _request_kwargs(ticket: str) -> Dict[str, Any]:
    """小程序侧接口的公共请求参数（query + ticket 请求头）。"""
    return {
        "params": {"source": 2, "ttid": "wx", "ticket": ticket},
        "headers": {"ticket": ticket},
        "raise_exception": True,
    }


async def sign_once(
    ticket: str,
    city_id: str,
    excitation_id: str,
    timeout: int = 10,
    proxy: str = "",
) -> SignResult:
    """执行一次签到请求并解析结果。请求层异常一律转成 ``is_error`` 结果。"""
    utils = _client(ticket, timeout, proxy)
    try:
        response = await utils.post_res(
            BASE_URL + DO_SIGN_PATH,
            json={
                "source": 2,
                "ticket": ticket,
                "token": ticket,
                "tokenId": ticket,
                "cityId": city_id,
                "excitationId": excitation_id,
            },
            **_request_kwargs(ticket),
        )
    except httpx2.RequestError as err:
        logger.warning(f"滴滴能源签到：请求异常（{masked_ticket(ticket)}）：{err}")
        return SignResult(is_error=True, message=f"请求异常：{err}")

    if response is None:
        return SignResult(is_error=True, message="无响应（网络层拦截）")
    if response.status_code != 200:
        return SignResult(
            is_error=True,
            message=f"HTTP {response.status_code}",
        )
    try:
        payload = response.json()
    except Exception as err:  # noqa: BLE001 - 站点偶发非 JSON 响应
        return SignResult(is_error=True, message=f"响应解析失败：{err}")

    result = parse_sign_payload(payload)
    logger.info(
        f"滴滴能源签到：{masked_ticket(ticket)} → {result.result_label}"
        f"（连续 {result.continuous_days} 天）{result.message}"
    )
    return result


async def fetch_sign_page(
    ticket: str,
    city_id: str,
    excitation_id: str,
    timeout: int = 10,
    proxy: str = "",
) -> SignPage:
    """拉取签到页数据源（``sign/main``），解析出「今日是否已签」等权威状态。

    任何请求层失败都归约为 ``SignPage(ok=False)``，调用方应降级为直接 doSign，
    不能因为状态接口抖动就不签到。
    """
    utils = _client(ticket, timeout, proxy)
    try:
        response = await utils.post_res(
            BASE_URL + SIGN_PAGE_PATH,
            json={
                "source": 2,
                "ticket": ticket,
                "token": ticket,
                "tokenId": ticket,
                "cityId": city_id,
                "excitationId": excitation_id,
            },
            **_request_kwargs(ticket),
        )
    except httpx2.RequestError as err:
        logger.warning(f"滴滴能源签到：签到页状态请求异常（{masked_ticket(ticket)}）：{err}")
        return SignPage(ok=False, message=f"请求异常：{err}")

    if response is None or response.status_code != 200:
        status = "无响应" if response is None else f"HTTP {response.status_code}"
        return SignPage(ok=False, message=f"签到页状态请求失败（{status}）")
    try:
        payload = response.json()
    except Exception as err:  # noqa: BLE001
        return SignPage(ok=False, message=f"签到页状态解析失败：{err}")

    page = parse_sign_page(payload, today_str())
    if page.ok:
        logger.info(
            f"滴滴能源签到：签到页状态（{masked_ticket(ticket)}）→ "
            f"今日{'已签' if page.signed_today else '未签'}，"
            f"连续 {page.continuous_days} 天，本轮 {page.period_start}~{page.period_end}"
        )
    else:
        logger.warning(f"滴滴能源签到：签到页状态不可用：{page.message}")
    return page


async def sign_with_retry(
    ticket: str,
    city_id: str,
    excitation_id: str,
    timeout: int = 10,
    proxy: str = "",
) -> SignResult:
    """带重试的签到编排：只有**业务失败**才值得重试。

    * 成功 / 当日重复 → 直接返回；
    * 请求层异常（网络不通、超时、非 200）→ 重试通常同样失败，直接返回；
    * 「未确认」（``DO_SIGN_ERROR`` 通用文案，已签与失败同码）→ 盲重试没有
      意义，交给调用方回查签到页状态确认；
    * 业务失败（凭证对但站点拒绝）→ 按 ``RETRY_DELAY_SECONDS × 尝试次数``
      递增间隔重试，最多 ``MAX_ATTEMPTS`` 次尝试。
    """
    result = await sign_once(ticket, city_id, excitation_id, timeout=timeout, proxy=proxy)
    attempt = 1
    while (
        attempt < MAX_ATTEMPTS
        and not result.ok
        and not result.is_error
        and not result.is_ambiguous
    ):
        delay = RETRY_DELAY_SECONDS * attempt
        logger.info(
            f"滴滴能源签到：第 {attempt} 次业务失败，{delay} 秒后重试（{result.message}）"
        )
        await asyncio.sleep(delay)
        attempt += 1
        result = await sign_once(ticket, city_id, excitation_id, timeout=timeout, proxy=proxy)
    return result


def build_notify_text(result: SignResult, record: Dict[str, Any], today: str) -> str:
    """按结果生成通知正文（纯函数）。"""
    lines = [f"结果：{result.result_label}"]
    if result.ok:
        lines.append(f"签到日期：{today}")
        lines.append(f"连续签到：{result.continuous_days} 天")
        lines.append(f"累计签到：{record.get('total_days', 0)} 天")
        if result.has_coupon:
            lines.append("🎉 已达成 5 天目标，优惠券已发放！")
        elif result.is_new_sign and result.continuous_days > 0:
            lines.append(f"再签到 {5 - result.continuous_days} 天可获得优惠券")
    else:
        lines.append(f"原因：{result.message}")
        if result.is_ambiguous:
            lines.append(
                "说明：站点对「当日已签」与「签到失败」返回同一错误码，本次不写入签到记录；"
                "若小程序里显示今天已签可忽略，否则请检查凭证是否失效"
            )
        elif result.continuous_days:
            lines.append(f"当前连续：{result.continuous_days} 天")
    return "\n".join(lines)
