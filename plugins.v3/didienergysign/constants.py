"""滴滴能源签到 —— 常量与默认值（站点事实集中地）。

站点事实（doSign 来自青龙脚本；sign/main 于 2026-10-22 持真实 ticket 实测核实）：

* 签到接口：``POST /am/marketing/api/member/charge/activity/sign/doSign``
  请求体带 ``ticket``（即登录凭证，同时作为 token/tokenId 与请求头）、
  ``cityId``、``excitationId``；query 带 ``source=2&ttid=wx&ticket=<ticket>``。
* **签到页数据源**：``POST /am/marketing/api/member/charge/activity/sign/main``
  返回签到活动页面的全部状态（活动标题、本轮周期、已签记录、连续天数），
  是判定「今日是否已签」的权威来源。实测当日已签时 doSign 返回
  ``DO_SIGN_ERROR``/「签到失败，请稍后重试」，**不会**明确说"已签到"。
* 判定：``success=true`` 为新签成功；当日重复以 ``sign/main`` 的
  ``signRecordDTOList`` 是否包含今天为准，不猜 doSign 的模糊错误文案。
* 连续签到天数：doSign 成功取 ``data.signResult.continuousDays``，
  页面态取 ``signTaskDTO.continuousDays``；满 5 天平台发券。
* 接口是微信小程序侧接口，需携带小程序 UA 与 ``servicewechat.com`` Referer。
"""

from __future__ import annotations

import re

__all__ = [
    "BASE_URL",
    "COUPON_TARGET_DAYS",
    "DEFAULT_CITY_ID",
    "DEFAULT_CRON",
    "DEFAULT_EXCITATION_ID",
    "DEFAULT_TIMEOUT",
    "DO_SIGN_PATH",
    "DUPLICATE_CODE",
    "DUPLICATE_MSG_PATTERN",
    "HISTORY_KEEP_DAYS",
    "MAX_ATTEMPTS",
    "PLUGIN_ICON",
    "PLUGIN_ID",
    "PLUGIN_NAME",
    "RECORD_KEY",
    "REFERER",
    "RETRY_DELAY_SECONDS",
    "SIGN_PAGE_PATH",
    "USER_AGENT",
]

#: 插件 ID（= 类名 / 目录名大写形式 / API 路径里的 ``<PluginID>``）
PLUGIN_ID = "DidiEnergySign"

#: 插件展示名
PLUGIN_NAME = "滴滴能源签到"

#: 插件图标（随插件仓库 icons 目录发布）
PLUGIN_ICON = (
    "https://raw.githubusercontent.com/m215owen/MoviePilot-Plugins/main/"
    "icons/DiDiEnergySign.png"
)

#: 站点根地址
BASE_URL = "https://energy.xiaojukeji.com"

#: 签到接口路径
DO_SIGN_PATH = "/am/marketing/api/member/charge/activity/sign/doSign"

#: 签到页数据源路径（返回活动标题/本轮周期/已签记录/连续天数）
SIGN_PAGE_PATH = "/am/marketing/api/member/charge/activity/sign/main"

#: 默认城市 ID（来自青龙脚本默认值）
DEFAULT_CITY_ID = "5"

#: 默认活动 ID（来自青龙脚本默认值）
DEFAULT_EXCITATION_ID = "144115195993789098"

#: 优惠券目标天数：连续签到满 5 天平台发券
COUPON_TARGET_DAYS = 5

#: 微信小程序侧接口需要小程序 UA
USER_AGENT = (
    "Mozilla/5.0 (Linux; Android 13; Mi 10 Pro Build/TKQ1.221114.001; wv) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/116.0.0.0 "
    "Mobile Safari/537.36 XWEB/1160117 MMWEBSDK/20240501 MMWEBID/6004 "
    "MicroMessenger/8.0.49.2685(0x28003135) WeChat/arm64 Weixin GPVersion/1 "
    "NetType/5G Language/zh_CN ABI/arm64 MiniProgramEnv/android"
)

#: 小程序 Referer
REFERER = "https://servicewechat.com/wx06cb940499986937/453/page-frame.html"

#: 「今日已签到」的业务码与消息特征
DUPLICATE_CODE = "DO_SIGN_ERROR"
DUPLICATE_MSG_PATTERN = re.compile(r"已签到|已经签到|重复签到")

#: 默认执行周期：每天 08:10
DEFAULT_CRON = "10 8 * * *"

#: 单次请求超时（秒）
DEFAULT_TIMEOUT = 10

#: 失败重试：业务失败时最多重试 2 次（共 3 次尝试），间隔递增 5s→10s
MAX_ATTEMPTS = 3
RETRY_DELAY_SECONDS = 5

#: 签到历史只保留最近 N 天，防止状态无限增长
HISTORY_KEEP_DAYS = 30

#: 签到记录在插件数据区的持久化键（save_data/get_data）
RECORD_KEY = "sign_record"
