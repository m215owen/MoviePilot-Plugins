# Vue-PT 监护台（VuePTMonitor）

展示 PT 站点运行状态、病危通知与站庆预告，并可把可添加站点写入 MoviePilot 站点管理。

> 本插件基于 [KoWming/MoviePilot-Plugins](https://github.com/KoWming/MoviePilot-Plugins) 的 `Savept`（Vue-PT监护室 v1.1.1）改造。
> 按插件发布约定更换了插件 ID 与名称，以避免与上游原版冲突。

## 相对原版的关键修复

原版 `_extract_site_cards` 用一条 20 余段串联的超长正则解析整页 HTML，页面结构稍有变化
（属性顺序变化、`data-*` 缺失、卡片改版）即触发**灾难性回溯**：正则在 C 层长时间运行且不释放 GIL，
导致整个 MoviePilot 进程假死——表现为页面打不开、`/health/ready` 超时、容器 `unhealthy`，
只能重启恢复，且每次打开该插件页面都会复现。

本版改动：

| 项目 | 原版 | 本版 |
|---|---|---|
| 站点卡片解析 | 超长正则 + `re.S` | **BeautifulSoup 结构化提取**，线性时间 |
| 年份分组解析 | `.*?`(re.S) 跨行匹配 | BS4 优先，正则兜底且用**有界字符类**（≤200 字符） |
| 名称候选拆分 | `.*?` | 有界字符类 `[^）)\]】]*` |
| 页面体积 | 无限制 | **>2MB 直接拒绝解析**并走缓存 |
| 解析耗时 | 无监控 | 超过 3s 记录告警日志 |

## 新增能力

### 1. 一键写入 MP 站点

快照会为每个站点标注与 MP 站点体系的关系：

- `MP已拥有`：已在 MP 站点管理中
- `MP可添加`：MP 内建索引器已支持该站，但你还没添加
- `MP未收录`：MP 没有该站的索引器定义

对 `MP可添加` 的站点可直接写入 MP 站点管理：

```
POST /api/v1/plugin/VuePTMonitor/sites/add
{"domains": ["example.com"]}   # domains 省略则处理全部可添加站点
```

### 2. 站点启停

```
POST /api/v1/plugin/VuePTMonitor/sites/toggle
{"domain": "example.com", "active": false}
```

### 3. 按站点状态联动（可选，默认关闭）

| 配置项 | 默认 | 说明 |
|---|---|---|
| `auto_add_available` | 关 | 每次刷新快照后自动把「MP可添加」站点写入站点管理 |
| `sync_mp_active` | 关 | 站点状态为「死亡」时自动禁用 MP 中对应站点 |
| `sync_mp_restore` | 关 | 站点恢复「健康」时自动重新启用 MP 中对应站点 |

联动采用保守策略：只处理已明确判定的状态，任何异常都被隔离，不影响快照生成。

### 4. 开放注册探测

面板直接给出「哪些站点现在开放注册」。

探测方式：后台线程池并发访问各站点的注册页（依次尝试 `/signup.php`、`/register.php`、
`/register`、`/signup`），按页面特征判定状态：

| 状态 | 判定依据 |
|---|---|
| `open` 开放注册 | 存在可填写的注册表单（`<form action>` 指向 signup/register 且含密码框，或 NexusPHP 的 `wantusername` 字段） |
| `invite` 仅限邀请 | 命中邀请类提示（只允许邀请注册 / 仅限邀请 / 邀请码 / invite only 等），**优先于**「关闭」判定，因为「自由注册关闭，只允许邀请注册」对用户更有用的是「仅限邀请」 |
| `closed` 未开放 | 命中关闭类提示（自由注册当前关闭 / 注册已关闭 / 暂停注册 / registration closed 等） |
| `blocked` 访问受限 | Cloudflare 盾（`just a moment`、`challenge-platform`）、备案阻断、HTTP 401/403 |
| `unknown` 无法确认 | 页面无可判定特征、仅呈现登录页、404 无注册页、5xx |
| `error` 探测失败 | 连接超时 / TLS 错误等网络异常 |

面板展示：

- 头部新增「可注册」计数
- 站点卡片对开放注册的站点加 `开放注册` 徽标
- 筛选栏新增「开放注册」开关，可一键只看可注册站点
- 「探测注册」按钮：启动后台探测并轮询进度（`探测中 106/137`），完成后自动刷新列表

结果写入插件存储（`signup_results`），重启不丢失；已关站的站点不再发起请求。
刷新站点快照时会按 **6 小时间隔**自动复检一次（`signup_auto`，可在配置里关闭）。

## 配置迁移

插件首次加载时会自动从旧插件 `Savept` 继承配置项（源站地址、超时、Cron、代理、浏览器仿真等）
与上一次的站点快照缓存，迁移只执行一次（以 `legacy_inherited` 标记）。新增的联动开关与探测开关
不参与继承。

## 配置项

| 键 | 说明 |
|---|---|
| `enabled` | 是否启用 |
| `source_url` | 监护源站地址，默认 `https://savept.icu/` |
| `request_timeout` | 抓取超时（秒），最小 5 |
| `default_internal_only` | 默认仅展示内站 |
| `notify` | 是否发送定时公告通知 |
| `cron` | 公告推送 Cron，默认 `0 8 * * *` |
| `use_proxy` | 是否走系统代理（注册探测同样遵循此开关） |
| `use_browser_emulation` | 是否用浏览器仿真抓取监护源站 |
| `auto_add_available` | 自动写入可添加站点 |
| `sync_mp_active` | 站点死亡时禁用 MP 站点 |
| `sync_mp_restore` | 站点恢复时启用 MP 站点 |
| `signup_check` | 是否启用开放注册探测，默认开 |
| `signup_auto` | 刷新快照时自动复检（6 小时一次），默认开 |
| `signup_cron` | 定时探测 Cron，默认空（不注册任务） |
| `signup_concurrency` | 探测并发数，默认 6，上限 10 |

## 接口

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/config` | 读取配置 |
| POST | `/config` | 保存配置 |
| GET | `/summary` | 概览统计 |
| GET | `/sites` | 站点列表 + 公告 + 注册状态 |
| POST | `/refresh` | 强制刷新快照 |
| POST | `/sites/add` | 写入可添加站点 |
| POST | `/sites/toggle` | 启用/禁用 MP 站点 |
| POST | `/signup/scan` | 启动开放注册探测（立即返回，后台执行） |
| GET | `/signup/status` | 探测进度、统计与逐站结果 |

### 实现注意

探测必须放在后台线程里跑，不能在请求线程里同步执行 137 个站点的抓取——那会长时间占住
worker，前端只能看到超时。同时**快照加载要在锁外完成**：`/signup/scan` 内部的快照加载
会触发「刷新后自动探测」回调，若把它放在锁内，同线程重入会自锁（已改为此顺序，并用
可重入锁兜底）。

## 致谢

原插件作者：KoWming（https://github.com/KoWming）
