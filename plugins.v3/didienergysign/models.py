"""滴滴能源签到 —— 插件 API 的 Pydantic 模型。

按官方 API 专题要求：每个普通 JSON endpoint 都要声明与实际输出一致的
``response_model``，业务数据只放 ``data`` 区，不借用 ``message`` 传输。
"""

from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field

__all__ = ["RunData", "StatusData"]


class RunData(BaseModel):
    """``POST /run``（立即执行一次签到）的返回。"""

    ok: bool = Field(False, description="今日任务完成（新签成功或当日重复）")
    is_new_sign: bool = Field(False, description="本次为新签成功")
    is_duplicate: bool = Field(False, description="当日已签到（重复请求）")
    is_ambiguous: bool = Field(False, description="站点返回未明确（已签与失败同码，不能确认）")
    is_error: bool = Field(False, description="请求层异常（网络/HTTP/解析）")
    continuous_days: int = Field(0, description="连续签到天数")
    has_coupon: bool = Field(False, description="连续签到是否已满 5 天（发券）")
    message: str = Field("", description="站点消息或失败原因")
    skipped: bool = Field(False, description="今日已签，本次直接跳过")
    #: 本轮签到周期信息（来自签到页数据源；doSign 直签成功时 period_days 取目标天数）
    period_days: int = Field(0, description="本轮签到周期天数（满则发券）")
    period_start: str = Field("", description="本轮周期开始日期")
    period_end: str = Field("", description="本轮周期结束日期")
    signed_dates: List[str] = Field(default_factory=list, description="本轮已签日期列表")
    ran_at: str = Field("", description="执行时间")


class StatusData(BaseModel):
    """``GET /status``（签到记录快照）的返回。"""

    enabled: bool = Field(False, description="插件是否启用")
    has_ticket: bool = Field(False, description="是否已配置签到凭证")
    cron: str = Field("", description="定时执行周期")
    last_sign_date: str = Field("", description="最近一次签到日期")
    total_days: int = Field(0, description="累计签到天数")
    continuous_days: int = Field(0, description="当前连续签到天数")
    max_continuous_days: int = Field(0, description="最大连续签到天数")
    last_update_time: str = Field("", description="记录最近更新时间")
    sign_history: List[str] = Field(default_factory=list, description="最近签到日期（新→旧截断前）")
