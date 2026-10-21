"""魔粒领取编排：取登录态 → 触发访问 → 用流水复核 → 汇总状态。

分层原则：

* ``client`` 只管「怎么访问站点」；
* 本模块只管「什么时候访问、怎么判定成功」，全部纯逻辑 + 少量 await；
* 插件类只管配置、调度与展示。

「成功」的判据**只认流水**（``rule_key=daily_active`` 且日期是今天），不认
「访问返回 200」：站点发放是后端副作用，200 不代表发了，流水有记录才算发了。
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from app.sdk.logging import logger

from .client import MagicubeClient, cookie_header, load_cookie_from_cookiecloud, parse_cookie_input
from .constants import (
    ALIYUN_RULE_KEY,
    COOKIE_CACHE_TTL,
    DAILY_RULE_KEYS,
    DAILY_RULE_TITLES,
    DEFAULT_TIMEOUT,
    LOGIN_SOURCE_MANUAL,
    LOGIN_SOURCE_COOKIECLOUD,
    PLUGIN_NAME,
    TOUCH_PATHS,
)

__all__ = [
    "BALANCE_SAMPLE_HOURS",
    "BALANCE_SAMPLE_LIMIT",
    "ClaimOutcome",
    "StatusSnapshot",
    "TodaySummary",
    "build_balance_samples",
    "build_daily_series",
    "build_days",
    "fetch_status",
    "invalidate_cookie_cache",
    "now_str",
    "resolve_cookie",
    "run_claim",
    "summarize_records",
    "today_str",
]

#: 触发访问后等多久再复核流水（站点记流水是异步的，给 1.5 秒足够）
_RECHECK_DELAY = 1.5

#: CookieCloud 登录态的进程内缓存。
#: 远端 CC 单次拉取实测约 20 秒，而余额刷新默认每 30 分钟一次 —— 不缓存的话
#: 每次刷新都要等 20 秒，还会给 CookieCloud 服务端平白增加压力。
_COOKIE_CACHE: Dict[str, Any] = {"value": "", "at": 0.0}


def invalidate_cookie_cache() -> None:
    """登录态被判失效时调用，让下一次取 cookie 重新拉 CookieCloud。"""
    _COOKIE_CACHE["value"] = ""
    _COOKIE_CACHE["at"] = 0.0


def today_str() -> str:
    """本地时区的今天（``YYYY-MM-DD``），与站点流水的 ``gmt_created`` 同格式"""
    return datetime.now().strftime("%Y-%m-%d")


def now_str() -> str:
    """人类可读的当前时间"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@dataclass
class TodaySummary:
    """某一天的发放汇总（只统计 ``type=EARN``）"""

    date: str
    total: int = 0
    #: ``rule_key -> 金额``
    rule_amounts: Dict[str, int] = field(default_factory=dict)
    #: 原始记录（按 rule_key 去重，保留首条）
    items: List[Dict[str, Any]] = field(default_factory=list)
    #: 今日发放最早到期时间（短期魔粒 24h 过期，这是「什么时候会烂掉」）
    expire_at: str = ""

    @property
    def login_done(self) -> bool:
        """今日「注册并登录」是否已发放 —— 这就是插件要拿的那一条"""
        return int(self.rule_amounts.get("daily_active") or 0) > 0

    @property
    def aliyun_done(self) -> bool:
        """今日「绑定阿里云」是否已发放（未绑定的账号没有这条，不算异常）"""
        return int(self.rule_amounts.get(ALIYUN_RULE_KEY) or 0) > 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "date": self.date,
            "total": self.total,
            "login_done": self.login_done,
            "aliyun_done": self.aliyun_done,
            "expire_at": self.expire_at,
            "items": self.items,
        }


def summarize_records(records: List[Dict[str, Any]], date: str = "") -> TodaySummary:
    """把流水记录收敛成「某一天的发放汇总」。

    只认 ``type=EARN``（消费 / 过期 / 冻结不计入「今日收益」）；
    ``rule_key`` 不在每日发放名单里的也计入总额，但不会让 ``login_done`` 变真。
    """
    target = date or today_str()
    summary = TodaySummary(date=target)
    seen: set[str] = set()

    for record in records or []:
        if not isinstance(record, dict):
            continue
        created = str(record.get("gmt_created") or "")[:10]
        if created != target:
            continue
        if str(record.get("type") or "").upper() != "EARN":
            continue
        rule_key = str(record.get("rule_key") or "").strip()
        try:
            amount = int(record.get("total_amount") or 0)
        except (TypeError, ValueError):
            amount = 0
        summary.total += amount
        if rule_key:
            summary.rule_amounts[rule_key] = summary.rule_amounts.get(rule_key, 0) + amount
        expire_at = str(record.get("expire_at") or "")
        if expire_at and (not summary.expire_at or expire_at < summary.expire_at):
            summary.expire_at = expire_at
        if rule_key in seen:
            continue
        seen.add(rule_key)
        summary.items.append(
            {
                "rule_key": rule_key,
                "title": str(record.get("title") or DAILY_RULE_TITLES.get(rule_key, rule_key)),
                "amount": amount,
                "expire_at": expire_at,
                "is_daily": rule_key in DAILY_RULE_KEYS,
            }
        )

    # 每日发放的两条固定排在前面，其它（如点赞、评论）按流水顺序跟在后面
    summary.items.sort(key=lambda item: DAILY_RULE_KEYS.index(item["rule_key"]) if item["rule_key"] in DAILY_RULE_KEYS else 99)
    return summary


async def resolve_cookie(
    login_source: str, manual_cookie: str, use_cache: bool = True
) -> Tuple[str, str]:
    """按配置取登录态，返回 ``(cookie 请求头, 错误说明)``。

    手动模式直读配置（无需缓存）；CookieCloud 模式带进程内缓存（``COOKIE_CACHE_TTL``），
    令牌失效时由调用方 ``invalidate_cookie_cache()`` 主动作废。
    """
    if (login_source or "").strip() == LOGIN_SOURCE_MANUAL:
        jar = parse_cookie_input(manual_cookie)
        if not jar:
            return "", "手动 Cookie 为空或格式无法解析"
        cookie = cookie_header(jar)
        if "m_session_id=" not in cookie:
            return "", f"手动 Cookie 缺少登录态 m_session_id（共解析出 {len(jar)} 个字段）"
        return cookie, ""

    now = time.monotonic()
    cached = str(_COOKIE_CACHE.get("value") or "")
    cached_at = float(_COOKIE_CACHE.get("at") or 0.0)
    if use_cache and cached and (now - cached_at) < COOKIE_CACHE_TTL:
        return cached, ""

    cookie, err = await load_cookie_from_cookiecloud()
    if cookie:
        _COOKIE_CACHE["value"] = cookie
        _COOKIE_CACHE["at"] = now
    return cookie, err


@dataclass
class ClaimOutcome:
    """一次「领取」动作的结果"""

    ok: bool = False
    #: True = 今日已领过，本次没有触发访问（幂等跳过）
    skipped: bool = False
    message: str = ""
    error: str = ""
    login_source: str = ""
    date: str = ""
    today_before: Optional[TodaySummary] = None
    today_after: Optional[TodaySummary] = None
    balance: Optional[int] = None
    available: Optional[int] = None
    frozen: Optional[int] = None
    touched: List[Dict[str, Any]] = field(default_factory=list)
    ran_at: str = ""
    #: 当前登录用户 ``{username, nickname, avatar_url}``；取不到就是空字典，不影响领取
    user: Dict[str, str] = field(default_factory=dict)

    @property
    def gained(self) -> int:
        """本次真正新增的魔粒（= 复核后总额 − 访问前总额）"""
        if not (self.today_before and self.today_after):
            return 0
        return max(0, self.today_after.total - self.today_before.total)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "skipped": self.skipped,
            "message": self.message,
            "error": self.error,
            "login_source": self.login_source,
            "date": self.date,
            "gained": self.gained,
            "balance": self.balance,
            "available": self.available,
            "touched": self.touched,
            "ran_at": self.ran_at,
            "user": self.user,
            "today_before": self.today_before.to_dict() if self.today_before else None,
            "today_after": self.today_after.to_dict() if self.today_after else None,
        }


async def run_claim(
    login_source: str,
    manual_cookie: str,
    timeout: int = DEFAULT_TIMEOUT,
    proxy: str = "",
    force: bool = False,
) -> ClaimOutcome:
    """执行一次领取。

    :param force: 今日已领时是否仍要再访问一次站点（默认不访问，省请求也更不惹眼）
    """
    outcome = ClaimOutcome(login_source=login_source, ran_at=now_str(), date=today_str())

    cookie, err = await resolve_cookie(login_source, manual_cookie)
    if not cookie:
        outcome.error = err or "未能获取登录态"
        outcome.message = "登录态获取失败"
        logger.warning(f"{PLUGIN_NAME}：{outcome.error}")
        return outcome

    client = MagicubeClient(cookie, timeout=timeout, proxy=proxy)

    # 1) 先看今天是否已发：已发就不必再访问站点
    records, read_err = await client.transactions()
    if read_err:
        if "登录态无效" in read_err:
            # cookie 可能刚在 CookieCloud 更新过，作废缓存让下次重取
            invalidate_cookie_cache()
        outcome.error = read_err
        outcome.message = "读取魔粒流水失败"
        logger.warning(f"{PLUGIN_NAME}：读取流水失败 - {read_err}")
        return outcome
    outcome.today_before = summarize_records(records, outcome.date)
    outcome.user, _ = await client.user_info()

    if outcome.today_before.login_done and not force:
        outcome.ok = True
        outcome.skipped = True
        balance, _ = await client.balance()
        _apply_balance(outcome, balance)
        outcome.today_after = outcome.today_before
        outcome.message = (
            f"今日已领取，无需重复操作（今日累计 {outcome.today_before.total} 魔粒）"
        )
        logger.info(f"{PLUGIN_NAME}：{outcome.message}")
        return outcome

    # 2) 触发：带登录态访问站点若干页面（这就是发放的触发条件）
    outcome.touched = await client.touch(TOUCH_PATHS)
    ok_pages = sum(1 for item in outcome.touched if item.get("ok"))
    logger.info(
        f"{PLUGIN_NAME}：已访问 {ok_pages}/{len(outcome.touched)} 个页面 "
        f"（{'/'.join(str(item.get('path')) for item in outcome.touched)}）"
    )

    # 3) 复核：站点记流水有延迟，等一会儿再读
    await asyncio.sleep(_RECHECK_DELAY)
    records_after, read_err_after = await client.transactions()
    if read_err_after:
        outcome.today_after = outcome.today_before
        outcome.error = read_err_after
        outcome.message = "触发后复核流水失败"
        logger.warning(f"{PLUGIN_NAME}：复核流水失败 - {read_err_after}")
        _apply_balance(outcome, (await client.balance())[0])
        return outcome
    outcome.today_after = summarize_records(records_after, outcome.date)

    # 4) 余额只作参考（短期魔粒 24h 过期，余额差不能当收益，收益一律看流水）
    balance, _ = await client.balance()
    _apply_balance(outcome, balance)

    if outcome.today_after.login_done:
        outcome.ok = True
        if outcome.gained > 0:
            detail = " + ".join(
                f"{DAILY_RULE_TITLES.get(item['rule_key'], item['rule_key'])} {item['amount']}"
                for item in outcome.today_after.items
                if item.get("is_daily")
            )
            outcome.message = f"领取成功，本次 +{outcome.gained} 魔粒（{detail}）"
        else:
            outcome.message = (
                f"今日已发放（累计 {outcome.today_after.total} 魔粒），本次无新增"
            )
        logger.info(f"{PLUGIN_NAME}：{outcome.message}")
        return outcome

    # 访问成功但流水没动 → 归因写清楚，别让用户以为「跑成功了」
    outcome.ok = False
    if ok_pages == 0:
        outcome.error = "所有触发页面访问失败（站点不可达或被拦截）"
    else:
        outcome.error = "已访问站点，但今日仍无发放记录"
    outcome.message = (
        f"{outcome.error}；可能是登录态已过期（请重新登录魔搭后同步 CookieCloud），"
        "或站点调整了每日发放规则"
    )
    logger.warning(f"{PLUGIN_NAME}：{outcome.message}")
    return outcome


def _apply_balance(outcome: ClaimOutcome, balance: Optional[Dict[str, Any]]) -> None:
    """把 balance 接口的三个数字塞进结果对象（接口失败就留 None，不当错误）"""
    if not isinstance(balance, dict):
        return
    for attr, key in (
        ("balance", "total_balance"),
        ("available", "available_balance"),
        ("frozen", "frozen_amount"),
    ):
        try:
            value = balance.get(key)
            setattr(outcome, attr, int(value) if value is not None else None)
        except (TypeError, ValueError):
            setattr(outcome, attr, None)


@dataclass
class StatusSnapshot:
    """只读状态快照（面板 / ``GET /status`` 用）"""
    logged_in: bool = False
    error: str = ""
    today: Optional[TodaySummary] = None
    balance: Optional[int] = None
    available: Optional[int] = None
    frozen: Optional[int] = None
    recent: List[Dict[str, Any]] = field(default_factory=list)
    #: 按天聚合的发放（新→旧），长度由 ``fetch_status(days=)`` 决定
    days: List[Dict[str, Any]] = field(default_factory=list)
    #: 当前登录用户 ``{username, nickname, avatar_url}``
    user: Dict[str, str] = field(default_factory=dict)
    #: 余额走势 ``[{date, balance}]``，按日期升序 —— 面板画「近 N 天」波浪图用
    history: List[Dict[str, Any]] = field(default_factory=list)
    #: 余额采样 ``[{ts, balance}]``，按时间升序 —— 面板画「近 N 小时」波浪图用
    samples: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "logged_in": self.logged_in,
            "error": self.error,
            "today": self.today.to_dict() if self.today else None,
            "balance": self.balance,
            "available": self.available,
            "frozen": self.frozen,
            "recent": self.recent,
            "days": self.days,
            "user": self.user,
            "history": self.history,
            "samples": self.samples,
        }


def build_days(records: List[Dict[str, Any]], days: int = 7) -> List[Dict[str, Any]]:
    """按天聚合发放，返回最近 ``days`` 天（新→旧）。

    只用流水里出现过的日期，空白天不补零 —— 面板上不出现一整列 0 更有信息量。
    """
    wanted = max(1, int(days or 7))
    dates = sorted(
        {
            str(record.get("gmt_created") or "")[:10]
            for record in records or []
            if isinstance(record, dict)
            and str(record.get("gmt_created") or "")[:10]
            and str(record.get("type") or "").upper() == "EARN"
        },
        reverse=True,
    )[:wanted]
    rows: List[Dict[str, Any]] = []
    for date in dates:
        summary = summarize_records(records, date)
        rows.append(
            {
                "date": date,
                "total": summary.total,
                "login_done": summary.login_done,
                "aliyun_done": summary.aliyun_done,
            }
        )
    return rows


#: 「近 N 天」视图最多回看多少天
BALANCE_DAILY_DAYS = 14

#: 采样点视图默认回看多少小时（按「刷新周期」的粒度看余额）
BALANCE_SAMPLE_HOURS = 24

#: 采样点最多保留多少个（每 30 分钟一个 ⇒ 24 小时 48 个；留余量给更密的周期）
BALANCE_SAMPLE_LIMIT = 500


def build_balance_samples(
    samples: Any,
    hours: int = BALANCE_SAMPLE_HOURS,
) -> List[Dict[str, Any]]:
    """把本地记录的**每次刷新采样**收敛成图数据（时间升序）。

    这是「刷新周期」真正看得见的地方：每跑一次余额刷新就落一个 ``(时刻, 余额)``，
    图上点的疏密就等于刷新周期的疏密 —— 30 分钟一个点，一天 48 个点。

    :param samples: ``[{"ts": "YYYY-MM-DD HH:MM:SS", "balance": 250}, ...]``
    :param hours: 只保留最近多少小时
    :return: ``[{"ts": ..., "balance": ...}]``
    """
    if not isinstance(samples, (list, tuple)):
        return []
    window = max(1, int(hours or BALANCE_SAMPLE_HOURS))
    cutoff = datetime.now() - timedelta(hours=window)

    parsed: List[Tuple[datetime, int]] = []
    for item in samples:
        if not isinstance(item, dict):
            continue
        raw_ts = str(item.get("ts") or "").strip()
        try:
            stamp = datetime.strptime(raw_ts, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
        if stamp < cutoff:
            continue
        try:
            balance = int(item.get("balance"))
        except (TypeError, ValueError):
            continue
        parsed.append((stamp, balance))

    parsed.sort(key=lambda pair: pair[0])
    # 同一秒只留一条（重复刷新不该让图上出现重叠点）
    deduped: List[Tuple[datetime, int]] = []
    for stamp, balance in parsed:
        if deduped and deduped[-1][0] == stamp:
            deduped[-1] = (stamp, balance)
        else:
            deduped.append((stamp, balance))
    return [{"ts": stamp.strftime("%Y-%m-%d %H:%M:%S"), "balance": balance} for stamp, balance in deduped]


def build_daily_series(
    history: Optional[Dict[str, int]],
    days: int = BALANCE_DAILY_DAYS,
) -> List[Dict[str, Any]]:
    """按天汇总**自动刷新实测**的余额 —— 不做任何推算。

    用户口径（2026-10-21）：走势统计只用自动刷新的数据。所以这里只吃插件自己采到的
    ``{date: balance}``（每次刷新更新当天，同一天覆盖），既不用流水反推，也不补空白日。
    代价是「今天之前」可能没有点，但图上每个数字都是真采到的 —— 宁可空，也不给假曲线。

    :param history: ``{YYYY-MM-DD: balance}``，由 ``_remember_balance`` 维护
    :param days: 最多回看多少天（取最近 N 个有数据的日子）
    :return: ``[{"date": "YYYY-MM-DD", "balance": int}]``，按日期升序
    """
    if not isinstance(history, dict):
        return []
    wanted = max(2, min(180, int(days or BALANCE_DAILY_DAYS)))
    rows: List[Tuple[str, int]] = []
    for key, value in history.items():
        date = str(key)[:10]
        if len(date) != 10:
            continue
        try:
            rows.append((date, int(value)))
        except (TypeError, ValueError):
            continue
    rows.sort(key=lambda pair: pair[0])
    return [{"date": date, "balance": balance} for date, balance in rows[-wanted:]]



async def fetch_status(
    login_source: str,
    manual_cookie: str,
    timeout: int = DEFAULT_TIMEOUT,
    proxy: str = "",
    days: int = 7,
    history: Optional[Dict[str, int]] = None,
    samples: Any = None,
    sample_hours: int = BALANCE_SAMPLE_HOURS,
) -> StatusSnapshot:
    """查「现在什么状态」：登录态是否有效、今日发了多少、余额、最近几条流水。

    只读，不触发任何发放。
    """
    snapshot = StatusSnapshot()
    cookie, err = await resolve_cookie(login_source, manual_cookie)
    if not cookie:
        snapshot.error = err or "未能获取登录态"
        return snapshot

    wanted_days = max(1, min(30, int(days or 7)))
    client = MagicubeClient(cookie, timeout=timeout, proxy=proxy)
    records, read_err = await client.transactions(page_size=max(20, wanted_days * 4))
    if read_err:
        snapshot.error = read_err
        return snapshot
    snapshot.logged_in = True
    snapshot.today = summarize_records(records, today_str())
    snapshot.days = build_days(records, wanted_days)
    snapshot.user, _ = await client.user_info()
    snapshot.recent = [
        {
            "date": str(record.get("gmt_created") or ""),
            "type": str(record.get("type") or ""),
            "rule_key": str(record.get("rule_key") or ""),
            "title": str(record.get("title") or ""),
            "amount": record.get("total_amount"),
            "expire_at": str(record.get("expire_at") or ""),
        }
        for record in records[:10]
    ]
    balance, _ = await client.balance()
    if isinstance(balance, dict):
        for attr, key in (
            ("balance", "total_balance"),
            ("available", "available_balance"),
            ("frozen", "frozen_amount"),
        ):
            try:
                value = balance.get(key)
                setattr(snapshot, attr, int(value) if value is not None else None)
            except (TypeError, ValueError):
                setattr(snapshot, attr, None)
    snapshot.history = build_daily_series(history, days=max(wanted_days, BALANCE_DAILY_DAYS))
    snapshot.samples = build_balance_samples(samples, hours=sample_hours)
    return snapshot
