# 魔搭魔粒签到（MagicubeDaily）

每天自动「登录」魔搭社区（[modelscope.cn](https://www.modelscope.cn)）领取 **200 魔粒**，
绑定阿里云账号的账号再 **+50**。

## 为什么需要这个插件

魔粒（Magicube）是魔搭的全站算力积分，能直接抵扣 AIGC 生图/训练和 API-Inference 调用。
每日登录发放的那一份是**短期魔粒，24 小时过期**——今天不领就作废，而且余额不会累积。

手工每天开一次网页当然可以，但断一天就丢一天。本插件把它变成定时任务。

## 机制（实测，不是猜的）

| 事实 | 说明 |
| --- | --- |
| **没有签到接口** | `POST /signin` 之类并不存在；+200/+50 是「**当天首次带登录态访问站点**」的后端副作用，服务端自己去重 |
| 触发方式 | 带登录态访问首页 + `/my/overview` + `/magicube/usage`（一次 3 个页面，共约 3 个请求） |
| 发放核对 | `GET /openapi/v1/magicubes/transactions` 里当天出现 `type=EARN` + `rule_key=daily_active`（200）与 `rule_key=aliyun_bindlogin`（50） |
| 余额 | `GET /openapi/v1/magicubes/balance` → `total_balance / available_balance / frozen_amount` |
| 鉴权 | 只认**网站登录 cookie**（`m_session_id`），不接受 API Token / Bearer |

> **成功判定只看流水，不看 HTTP 状态码。** 访问返回 200 不代表发了魔粒，
> 流水里出现今天的 `daily_active` 才算真领到。

## 登录态：默认零配置

插件默认从**宿主的 CookieCloud** 里读 `.modelscope.cn` 的 cookie（含 `passport.` / `www.` 子域合并，
更具体的域覆盖更宽泛的域，与浏览器行为一致）。只要你浏览器登录过魔搭、CookieCloud 同步过，
插件就不用任何手工配置，而且 cookie 会随 CookieCloud 自动续期。

CookieCloud 里没有魔搭 cookie 时，把「登录态来源」改成**手动填写 Cookie**，
从浏览器 DevTools 复制 `Cookie:` 请求头粘进去即可（支持 `k=v; k2=v2`、Cookie-Editor JSON、
多行文本三种形态）。

## 配置项

| 项 | 默认 | 说明 |
| --- | --- | --- |
| 启用插件 | 关 | 关闭后不注册定时任务 |
| 发送通知 | 开 | 每次执行结果推送到已配置的通知渠道 |
| 领取周期 | `10 8 * * *` | 每天 08:10。魔粒 24h 过期，建议固定同一时间跑 |
| 余额刷新周期 | `*/30 * * * *` | 每 30 分钟**只读**刷新余额与账号（不触发发放）；留空则只在领取后更新 |
| 登录态来源 | CookieCloud | 或「手动填写 Cookie」 |
| 手动 Cookie | 空 | 仅手动模式使用 |
| 请求超时 | 20 秒 | CookieCloud 拉取另有 120 秒独立超时 |
| 代理地址 | 空 | 国内站点一般直连即可 |

## 面板显示什么

- **登录账号**：昵称（用户名），取自 `GET /openapi/v1/users/me`。CookieCloud 里可能躺着多个号的
  cookie，看到昵称才能确认领的是不是自己想领的那个。
- **当前余额 + 数据时间**：余额是最近一次刷新的数字，旁边写明刷新周期，不会让你误以为是实时值。
- **两张余额波浪图，数据只来自自动刷新的实测采样**：
  - **近 24 小时**：每跑一次余额刷新就落一个采样点，横轴按**真实时间比例**排布——
    30 分钟一个点，一天 48 个点；把刷新周期改成 5 分钟，点立刻就密起来。
  - **近 14 天**：每个日期取当天**最后一次刷新**的余额，有几天的实测就画几天。
  - **不做任何推算**：站点没有历史余额接口，插件也不去用流水反推。宁可图上暂时只有一两个点，
    也不给你一条算出来的假曲线——图上每个数字都是真采到的。代价是从启用那天开始积累。
  - SVG 在服务端算好后 base64 成 `data:` URI 交给 `VImg` 显示 —— 面板打开它不需要额外
    请求（图片请求不带登录态会 401），也不会把 apikey 暴露在页面里。
- **今日发放明细、最早到期时间、上次执行结果、近 N 天每日收益**。

## 行为细节

- **幂等**：先查流水，今日已发就直接跳过，不再访问站点（省请求，也更不惹眼）。
  想强制再访问一次，调 `POST /run?force=true`。
- **收益口径是流水，不是余额差**：短期魔粒 24h 过期会把余额差搅乱（今天入账 250、
  昨天那批同时过期，余额可能是负增长），所以「本次 +N」一律取流水总额差。
- **失败会归因**：`今日仍无发放记录` = 登录态可能过期；`登录态无效` = cookie 直接失效；
  所有触发页面都访问失败 = 站点不可达/被拦截。三种情况提示不同。

## API

路径前缀 `/api/v1/plugin/MagicubeDaily`，鉴权用 `X-API-KEY`（或 `?apikey=`）。

```bash
# 看状态：登录账号、今日发放、余额、近 7 天、余额走势（history）
curl -H "X-API-KEY: $TOKEN" "http://<host>:3002/api/v1/plugin/MagicubeDaily/status?days=7"

# 立即领取一次（今日已领则 skipped）
curl -X POST -H "X-API-KEY: $TOKEN" "http://<host>:3002/api/v1/plugin/MagicubeDaily/run"

# 强制再访问一次站点
curl -X POST -H "X-API-KEY: $TOKEN" "http://<host>:3002/api/v1/plugin/MagicubeDaily/run?force=true"

# 流水原始记录（排查「为什么今天没发」）
curl -H "X-API-KEY: $TOKEN" "http://<host>:3002/api/v1/plugin/MagicubeDaily/records?page_size=20"
```

`/status` 里与本轮新增相关的字段：

| 字段 | 含义 |
| --- | --- |
| `username` / `nickname` / `avatar_url` | 当前登录的魔搭账号 |
| `balance` / `available` / `frozen` | 余额三件套 |
| `checked_at` | 这份余额是哪个时刻查的 |
| `refresh_cron` | 后台刷新周期（空 = 只在领取后更新） |
| `history[]` | `{date, balance}` 数组，按日期升序，直接可喂给任何图表库 |

## 不做什么

**不实现点赞/收藏刷魔粒**（`star → unstar` 循环 20 次拿 40 魔粒）。那是明确的刷分滥用：
违反社区条款、有封号风险，收益只有登录那一份的 1/6。本插件只领「登录就该有的那一份」。

## 常见问题

**跑完只加 0，日志说「今日已发放」？**
正常。发放有去重，当天已经手动打开过魔搭就不会再发。插件会明确告诉你今日已领，不会误报成功。

**余额比昨天少？**
短期魔粒 24 小时过期，定时任务每天同一时刻跑，前一天那批常在本轮前后到期。收益请看流水，不看余额。

**提示登录态无效？**
浏览器重新登录魔搭 → CookieCloud 同步一次 → 插件下次执行自动恢复。走手动模式的话重新粘 cookie。

**会一直发通知吗？**
每次执行一条。不想收就关掉「发送通知」，结果仍然可在插件详情页看。
