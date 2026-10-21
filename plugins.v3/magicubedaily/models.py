"""插件 API 的响应模型（FastAPI ``response_model`` 必须具体，不能用 dict/Any）。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from app import schemas

__all__ = [
    "BalancePoint",
    "BalanceSample",
    "DailyItem",
    "DayRow",
    "HistoryData",
    "HistoryResponse",
    "RunData",
    "RunResponse",
    "StatusData",
    "StatusResponse",
    "TodayData",
    "TouchRow",
]


class DailyItem(BaseModel):
    """今日发放规则中的一条（如「注册并登录 200」）"""

    rule_key: str = ""
    title: str = ""
    amount: int = 0
    expire_at: str = ""
    #: 是否属于「每日发放」名单（false = 点赞/评论等其它收益）
    is_daily: bool = False


class TodayData(BaseModel):
    """今日发放汇总"""

    date: str = ""
    total: int = 0
    #: 今日「注册并登录」是否已发放 —— 插件唯一必须拿到的这一条
    login_done: bool = False
    #: 今日「绑定阿里云」是否已发放（未绑阿里云的账号恒 false，不算异常）
    aliyun_done: bool = False
    #: 今日短期魔粒最早到期时间（24 小时过期，过期即作废）
    expire_at: str = ""
    items: List[DailyItem] = []


class DayRow(BaseModel):
    """按天聚合的历史收益"""

    date: str = ""
    total: int = 0
    login_done: bool = False
    aliyun_done: bool = False


class BalancePoint(BaseModel):
    """余额走势上的一个点（按天，来自自动刷新实测）"""

    date: str = ""
    balance: int = 0


class BalanceSample(BaseModel):
    """一次余额刷新的采样点（按刷新周期，来自自动刷新实测）"""

    ts: str = ""
    balance: int = 0


class StatusData(BaseModel):
    """``GET /status``"""

    enabled: bool = False
    #: 登录态（cookie）是否有效 —— 由站点接口回答，不是本地猜的
    logged_in: bool = False
    login_source: str = ""
    source_label: str = ""
    #: 登录态或接口错误（empty = 正常）
    error: str = ""
    #: 当前登录的魔搭账号（``/openapi/v1/users/me``）
    username: str = ""
    nickname: str = ""
    avatar_url: str = ""
    balance: Optional[int] = None
    available: Optional[int] = None
    frozen: Optional[int] = None
    today: TodayData = TodayData()
    #: 近几天的发放，按日期倒序（``days`` 参数控制，默认 7）
    days: List[DayRow] = []
    #: 余额走势（按天取最后一次自动刷新的值，升序）
    history: List[BalancePoint] = []
    #: 余额采样（近 24 小时每次自动刷新的值，按时间升序）
    samples: List[BalanceSample] = []
    cron: str = ""
    #: 余额/状态的后台刷新周期（空 = 只在领取后更新）
    refresh_cron: str = ""
    #: 状态查询时间（余额是这个时刻的数字）
    checked_at: str = ""
    #: 最近一次执行
    last_run_at: str = ""
    last_result: str = ""
    last_message: str = ""


class TouchRow(BaseModel):
    """一次触发访问的结果"""

    path: str = ""
    ok: bool = False
    status: Optional[int] = None
    size: int = 0


class RunData(BaseModel):
    """``POST /run``"""

    ok: bool = False
    #: True = 今日已领过，本次跳过了站点访问
    skipped: bool = False
    message: str = ""
    error: str = ""
    date: str = ""
    ran_at: str = ""
    #: 本次新增魔粒（取流水差，不受 24h 过期影响）
    gained: int = 0
    balance: Optional[int] = None
    available: Optional[int] = None
    #: 当前登录的魔搭账号
    username: str = ""
    nickname: str = ""
    touched: List[TouchRow] = []
    today: TodayData = TodayData()


class HistoryData(BaseModel):
    """``GET /records``"""

    total: int = 0
    #: 站点流水的原始条目（字段原样透出，便于排查）
    records: List[Dict[str, Any]] = []


StatusResponse = schemas.Response[StatusData]
RunResponse = schemas.Response[RunData]
HistoryResponse = schemas.Response[HistoryData]
