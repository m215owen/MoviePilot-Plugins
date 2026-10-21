"""魔搭魔粒签到 —— 常量与默认值。

所有「站点事实」集中在这里，改站点时只动本文件。站点事实均于 2026-10-21 实测：

* **没有签到接口**。每日 200 魔粒（绑定阿里云再 +50）是「当天首次带登录态访问站点」
  的后端副作用，服务端自己去重。所以插件做的是「模拟打开一次站点」而不是 POST 某个签到。
* 余额：``GET /openapi/v1/magicubes/balance``
  → ``{"success":true,"data":{"total_balance":250,"available_balance":250,"frozen_amount":0}}``
* 流水：``GET /openapi/v1/magicubes/transactions?page_number=1&page_size=20``
  → ``data.records[]`` 含 ``gmt_created / type / rule_key / total_amount / expire_at``，
  每日发放的两条 ``type=EARN`` + ``rule_key=daily_active``（200）与
  ``rule_key=aliyun_bindlogin``（50）。
* 这两个接口认**网站登录 cookie**（``m_session_id``），不接受 API Token / Bearer。
"""

from __future__ import annotations

__all__ = [
    "ALIYUN_RULE_KEY",
    "BASE_URL",
    "COOKIE_CACHE_TTL",
    "COOKIE_DOMAIN_SUFFIX",
    "DAILY_RULE_KEYS",
    "DAILY_RULE_TITLES",
    "DEFAULT_CRON",
    "DEFAULT_REFRESH_CRON",
    "DEFAULT_TIMEOUT",
    "LOGIN_SOURCE_COOKIECLOUD",
    "LOGIN_SOURCE_MANUAL",
    "LOGIN_SOURCES",
    "LOGIN_SOURCE_LABELS",
    "PLUGIN_ID",
    "PLUGIN_NAME",
    "REQUIRED_COOKIE_NAMES",
    "SESSION_COOKIE_NAME",
    "TOUCH_PATHS",
    "USER_AGENT",
    "USER_INFO_PATH",
]

#: 插件 ID（= 目录名 / 类名小写，也是 API 路径里的 ``<PluginID>``）
PLUGIN_ID = "MagicubeDaily"

#: 插件展示名
PLUGIN_NAME = "魔搭魔粒签到"

#: 站点根地址（``www`` 子域才带完整登录态，别用裸域）
BASE_URL = "https://www.modelscope.cn"

#: CookieCloud 里魔搭 cookie 的域名后缀（含 ``passport.`` / ``www.`` 等子域）
COOKIE_DOMAIN_SUFFIX = "modelscope.cn"

#: 登录态的关键 cookie。缺了它整条链路必然 401，提前判掉能省两次出网。
SESSION_COOKIE_NAME = "m_session_id"

#: 判「已登录」必须同时存在的 cookie（缺失时给出明确提示）
REQUIRED_COOKIE_NAMES = (SESSION_COOKIE_NAME,)

#: 登录态来源
LOGIN_SOURCE_COOKIECLOUD = "cookiecloud"
LOGIN_SOURCE_MANUAL = "manual"
LOGIN_SOURCES = (LOGIN_SOURCE_COOKIECLOUD, LOGIN_SOURCE_MANUAL)
LOGIN_SOURCE_LABELS = {
    LOGIN_SOURCE_COOKIECLOUD: "CookieCloud（自动，推荐）",
    LOGIN_SOURCE_MANUAL: "手动填写 Cookie",
}

#: 每日发放的两条规则（顺序即展示顺序）
DAILY_RULE_KEYS = ("daily_active", "aliyun_bindlogin")
DAILY_RULE_TITLES = {
    "daily_active": "注册并登录",
    "aliyun_bindlogin": "绑定阿里云账号",
}
#: 「绑定阿里云」那条：不是每个账号都有，缺失不算失败
ALIYUN_RULE_KEY = "aliyun_bindlogin"

#: 触发每日发放要访问的页面。
#: 实测机制是「当天首次带登录态访问站点」⇒ 首页 + 两个用户态页面足够；
#: 多访问几个不同路径只是让触发更稳（成本可忽略，一天只跑一次）。
TOUCH_PATHS = ("/", "/my/overview", "/magicube/usage")

#: 交易流水只看最近这么多条（20 条够覆盖今天 + 昨天 + 几次消费）
TRANSACTIONS_PAGE_SIZE = 20

#: 默认执行周期：每天 08:10（魔粒 24 小时过期，固定早上跑最不容易踩到过期边界）
DEFAULT_CRON = "10 8 * * *"

#: 单次请求超时（秒）。CookieCloud 远端拉取较慢，单独给 120 秒。
DEFAULT_TIMEOUT = 20
COOKIECLOUD_TIMEOUT = 120

#: 桌面 UA：站点对无 UA/爬虫 UA 会直接 302 到登录页
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
)

#: 余额接口路径
BALANCE_PATH = "/openapi/v1/magicubes/balance"
#: 流水接口路径
TRANSACTIONS_PATH = "/openapi/v1/magicubes/transactions"
#: 当前登录用户（实测 200，data 里是 ``username / nickname / avatar_url / email / description``）
USER_INFO_PATH = "/openapi/v1/users/me"

#: 余额 / 今日状态的后台刷新周期。
#: 为什么需要它：插件详情页是**同步**的 ``get_page()``，不能在渲染时出网，
#: 所以余额靠一个只读的周期任务刷新到持久化快照里，打开面板就能看到较新的数字。
DEFAULT_REFRESH_CRON = "*/30 * * * *"

#: CookieCloud 登录态在进程内的复用时长（秒）。
#: 远端 CC 拉取实测约 20 秒，每 30 分钟刷一次余额时不能每次都重新拉。
COOKIE_CACHE_TTL = 900

