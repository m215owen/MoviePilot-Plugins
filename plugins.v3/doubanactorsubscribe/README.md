# 豆瓣演员订阅（DoubanActorSubscribe）

订阅豆瓣演员，抓取该演员的**最新影视作品**并展示在面板中；面板上的每个作品都带**订阅按钮**，
一点即提交到 MoviePilot 订阅系统（按**豆瓣 ID 精确订阅**）。也支持按类型/评分阈值**自动订阅**新作品。

```
配置演员 → 定时/手动刷新 → 抓取作品快照 → 仪表板 + 侧栏面板展示 → 一键订阅 / 自动订阅
```

## 功能

| 能力 | 说明 |
| --- | --- |
| 演员配置 | 支持**豆瓣人物主页链接**（推荐，最稳，直接解析出 ID，不消耗搜索配额）、**演员名称**（自动搜索并缓存豆瓣人物 ID）或直接填**豆瓣人物 ID**（纯数字） |
| 作品抓取 | 豆瓣 Frodo API：人物详情 → 影视作品集 → 作品列表，归一化标题/年份/类型/评分/海报/职务 |
| 面板展示 | **统一作品墙**（跨演员按时/新作品排序，卡片标出**出演演员**，演员以 chip 筛选代替分组）+ 完整筛选 + 批量订阅 |
| 异常提示 | 面板异常**显示 5 秒后自动收起**为「N 项异常（点击查看）」小标签，内容变化会重新计时 |
| 一键订阅 | 前端调用宿主 `subscribe/` 接口，携带 `media_source=douban` + `media_id`，归属当前登录用户 |
| 自动订阅 | 定时刷新后按「只订阅新作品 / 类型白名单 / 最低评分 / 每次上限」自动调用订阅链落库 |
| 通知 | 可通过宿主通知渠道推送刷新结果与自动订阅明细 |
| 智能体工具 | `douban_actor_latest_works`：让 AI 查询已跟踪演员的最新作品 |

## 配置项

| 字段 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| `enabled` | bool | `false` | 启用插件 |
| `actors` | str | 空 | 演员列表，一行一个；**推荐直接粘贴豆瓣人物主页链接**（如 `https://www.douban.com/personage/37871253/`），也支持人物 ID 或名称（分隔符可用逗号/顿号/分号/换行） |
| `subscribe_save_path` | str | 空 | 面板订阅时默认保存路径（透传给宿主 `subscribe/`） |
| `subscribe_sites` | list | `[]` | 面板订阅时默认站点白名单（留空表示全部站点） |
| `max_works` | int | `10` | 每位演员保留的作品条数（5–10）。上限 10 是豆瓣接口限制，不是插件限制 |
| `sort_by` | str | `time` | 豆瓣侧排序：`time` 按时间（最新作品优先）/ `collection` 豆瓣默认；其余取值回退 `time` |
| `cron` | str | `0 8 * * *` | 刷新周期（cron 表达式） |
| `proxy` | bool | `false` | 走宿主配置的代理访问豆瓣 |
| `notify` | bool | `false` | 刷新完成后发送通知 |
| `auto_subscribe` | bool | `false` | 自动订阅开关 |
| `auto_only_new` | bool | `true` | 只订阅新出现的作品；首次抓取仅建立基线 |
| `auto_types` | str | `电影,电视剧` | 自动订阅的媒体类型白名单 |
| `auto_min_vote` | float | `0` | 自动订阅的最低豆瓣评分（0 表示不限） |
| `auto_max_per_run` | int | `5` | 单次刷新最多自动订阅的条数 |
| `douban_cookie` | str | 空 | 手工粘贴的豆瓣 Cookie（留空则自动尝试宿主 CookieCloud）。**搜索额度明显更高** |
| `onlyonce` | bool | `false` | 保存配置后立即刷新一次（勾选后自动复位） |

## HTTP 接口

挂载在 `/api/v1/plugin/DoubanActorSubscribe/<path>`，全部 `bear` 鉴权。

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/config` | 获取运行时配置（`actors` 以换行串、`auto_types` 以逗号串返回给前端） |
| PUT | `/config` | 合并更新配置，持久化后重新初始化插件 |
| GET | `/works` | 演员 + 作品快照 + 统计（面板数据源），含 `refreshing` 标记 |
| POST | `/run` | 立即刷新一次。**异步**：立即返回并置 `refreshing=true`；重复调用返回「刷新已在进行中」 |
| GET | `/search_actor?name=` | 解析演员：可传**主页链接 / 人物 ID / 名称**。链接与 ID 直接命中，不消耗搜索配额 |
| POST | `/clear` | 清空作品快照与自动订阅记录（不动配置） |

> 插件动态路由**不套宿主的 `Response[T]` 外壳**，因此插件接口一律自行返回 `{success, data}`。

## 其他扩展点

- **定时服务**：`get_service()` 注册 `<类名>.Refresh`，cron 由配置决定；未启用或未配置演员时不注册。
- **远程命令**：`/doubanactor` → `EventType.PluginAction` → `on_plugin_action`。
- **工作流动作**：`doubanactorsubscribe_refresh`。
- **侧栏入口**：`nav_key=main`（作品面板）与 `nav_key=settings`（运行状态），`section=subscribe`。
- **仪表板**：`key=works`，`cols/sm/md = 12/6/4`，刷新间隔 300s。

## 前端（Vue 模块联邦）

`get_render_mode()` 返回 `("vue", "dist/assets")`，宿主直接加载 `dist/assets/remoteEntry.js`。

```
src/
├── api.ts                 # 接口封装：插件 API + 宿主 subscribe/ 接口 + 图片代理 + 时间格式化
├── types.ts               # 与后端 payload 对齐的 TS 类型
├── WorkGrid.vue           # 作品海报墙（Page / AppPage 复用，带出演演员行与订阅按钮）
├── ErrorAlerts.vue        # 异常提示条：5s 后自动收起，可点击小标签再展开
├── SubscribePrefs.vue     # 订阅偏好（保存路径 / 站点），Config 与运行状态页共用
├── Page.vue               # 插件详情页（顶部固定操作条：刷新 / 配置插件 / 通知宿主刷新 / 关闭）
├── Config.vue             # 配置页（emit('save', cfg) 由宿主持久化）
├── Dashboard.vue          # 仪表板小组件
├── AppPage.vue            # 侧栏全页 · 作品面板（nav_key=main）
└── AppPageSettings.vue    # 侧栏全页 · 运行状态（nav_key=settings）
```

> **详情页布局**：操作按钮固定在页面**顶部**，作品墙再长也不需要滚到底找按钮。
> **图片**：海报走宿主 `system/img/0?imgurl=…`（与「探索」页同路径，**取 `1` 会强制走用户代理配置，
> 代理异常时图片会全挂**）；接口鉴权走浏览器资源 Cookie，服务端用 apikey 调它必定 401（预期行为）。
>
> **响应解包（易错点）**：宿主列表接口返回 `{success, data: [...]}` 信封。
> `unwrap()` 遇到带 `success` 的对象会**原样返回信封**（`submitSubscribe` 需要读 `success`/`message`，
> 所以不能改它），于是 `Array.isArray(信封)` 恒为假——这正是「下载保存路径 / 订阅站点下拉是空的」的原因。
> **凡是要取列表，一律用 `unwrapList<T>()`**，它同时兼容裸数组、`{data: [...]}` 信封与再套一层 axios response。
> `normalizeResult()` 则用于需要读 `success`/`message` 的场景。

构建：

```bash
npm install --ignore-scripts   # 沙箱内需跳过 postinstall
node node_modules/vite/bin/vite.js build
```

产物写入 `dist/`。**联邦产物必须随插件提交**（仓库根 `.gitignore` 忽略 `dist/`，提交时用 `git add -f`），
因为运行时不重新构建，宿主直接读取该目录。仓库内的 `.gitignore` 只忽略 `dist/assets/*.map`。

## 订阅实现说明

- **面板按钮**：前端 POST `subscribe/`（宿主公开接口），请求体
  `{name, year, media_source: 'douban', media_id, type}`；宿主用 `resolve_media_identity` 解析豆瓣身份，
  并把季号从标题中拆到 `begin_season`。订阅归属**当前登录用户**，复用宿主去重与校验。
- **自动订阅**：插件内直接走宿主订阅链

  ```python
  from app.chain.subscribe import SubscribeChain
  SubscribeChain().add(
      title=..., year=..., mtype=MediaType.MOVIE,
      media_source=MediaSource.Douban, media_id=...,
      season=MetaInfo(title).begin_season, exist_ok=True, username="豆瓣演员订阅",
  )
  ```

  与官方插件（`doubanrank` / `bangumicoll` / `maoyanrank` 等）一致；写入前用 `chain.exists(meta=meta)` 去重。
- **`is_new` 语义**：`first_seen` 从上一份快照继承，因此**首次刷新某演员时全部作品都是「新」**
  （面板会显示「新」徽标）；开启 `auto_only_new` 时首次刷新只建立基线，不会批量订阅历史作品。

## 豆瓣 Frodo 接口适配要点

实测（2026-10）豆瓣移动端接口的几个易错点，已在代码中处理：

| 事项 | 结论 |
| --- | --- |
| 签名路径 | `_sig` 必须覆盖**完整路径**（含 `/api/v2` 前缀）。只签相对路径会稳定返回 `400 Bad Request` |
| 媒体类型 | 作品条目里 `subject.type` 恒为 `"subject"`（实体种类），真实类型在 `subject.subtype`（`movie` / `tv`） |
| 年份 | 顶层无 `year`，位置是 `subject.extra.year` |
| 评分 | 位置是 `subject.extra.rating_group.rating.value`，无评分时为 `null`（需降级为 0） |
| 简介 | `subject.extra.short_info`，形如 `2026 / 中国大陆 / 犯罪 / 陈思诚 / 张译 马丽` |
| 分页 | `/elessar/work_collections/{id}/works` 单次最多 **10 条**，且 `start > 0` 恒返回 `{"total": 0, "works": []}` —— 即**不支持翻页**，每位演员只能取到最近 10 部 |
| 排序 | `sortby` 仅 `time` / `collection` 有效，`vote` 会返回**空数组**，已做白名单兜底 |
| 人物搜索 | `/search/subjects?type=person&q=` → `items[].target.{id,title,cover_img}` |
| 作品集 ID | 人物详情 `modules[].type == "work_collections"` → `payload.id`（标题实测为「作品集」） |
| 搜索限流 | `/search/subjects?type=person` 同一出口 IP **约 5 次**后返回 `403 {"msg":"need_login","code":103}`，**恢复窗口 > 90 秒**（恢复后可再用约 5–7 次） |
| 详情限流 | `/elessar/subject/{id}` 约 **10 次**后返回 `403 {"msg":"subject_ip_rate_limit","code":400010}`，但**窗口很短**（第 11 次失败、第 15 次已 200）→ 值得退避重试 |

### 限流应对（重点）

搜索配额只有 5 次/窗口，而配置里动辄上百位演员，因此插件做了四件事：

1. **优先走链接/ID**：`苏凝` 这类名字解析失败时，直接粘贴 `https://www.douban.com/personage/37871253/`
   或填 `37871253`，一步到位且**不消耗任何搜索配额**（`_extract_person_id()` → 支持 `personage` / `celebrity` 两种主页）。
2. **区分限流与「查无此人」**：客户端记录 `last_status` / `last_error` / `last_rate_limited`，
   只有**真正返回 0 条**才提示「豆瓣未搜索到该演员，请改用人物 ID」；
   被限流时提示「豆瓣搜索被限流，稍后会自动重试；也可直接填人物 ID 跳过搜索」并标 `retryable`。
3. **限流后中止本轮搜索**：某次按名称搜索一旦被限流，本轮**剩余尚未解析**的演员直接跳过并归入限流分组，
   不再对上百个名字空打必然失败的请求（`execute_task()` 里的 `search_blocked` / `skipped`）。
   已解析出 ID 的演员缓存在本地，**下轮不再搜索**，所以逐轮刷新会让已解析数单调上升。
4. **手动刷新改后台任务**：`POST /run` 只负责排一个一次性任务并立即返回，避免上百位演员的同步刷新
   触发 HTTP 超时；面板通过 `refreshing` 标记轮询到结束（`_is_refreshing()` 带 1800s 超时兜底）。

### 搜索冷却：每位演员 24 小时只搜 1 次

豆瓣的**按名称搜索**额度极紧（匿名约 5 次/窗口，登录态也只多几倍），而解析出人物 ID 后
本可长期复用。因此插件对「搜索」这一步加了冷却：

| 规则 | 说明 |
| --- | --- |
| 触发条件 | **搜索成功**（真的解析出人物 ID）才记账 |
| 冷却时长 | 24 小时，滚动窗口（`_SEARCH_COOLDOWN_SECONDS`） |
| 作用范围 | **只限制「按名称搜索」**；已解析出 ID 的演员本来就不搜索，其作品与详情仍按 cron / 手动刷新照常抓取 |
| 失败处理 | **失败不冷却**：限流 / `need_login` / 查无此人都不记账，下一轮刷新仍会重试（限流只是暂时的，锁死一整天会让演员长期解析不出来） |
| 记账存储 | 插件数据表 `search_log`：`{演员: epoch 秒}`，读取时自动丢弃超过 24 小时的记录 |

配套修复：**搜索已拿到人物 ID、但详情接口被限流**时，ID 现在也会立即落缓存。
早期版本在这条路径上直接 `return`，导致下一轮会为一个**已经解析好**的演员再花一次搜索额度。

面板顶部会显示 **`搜索冷却 N`** 徽标（`search_cooldown_count`），用来解释
「为什么这些演员还是未解析状态」；`POST /clear` 会一并清空搜索记账，相当于手动放行一次重搜。

### 提高额度：复用宿主 CookieCloud（推荐）

> **实测结论**：同一个出口 IP，匿名请求约 5 次即被 `403 {"msg":"need_login","code":103}` 挡下；
> 带上**已登录**的豆瓣 Cookie 后，连续 10 次搜索全部 200，而且**立即生效**。
> 说明匿名额度是硬瓶颈，而登录态额度绑账号、不绑 IP。

因此插件优先自动复用宿主已有的 **CookieCloud**，无需用户手工复制 Cookie：

1. `_resolve_douban_cookie()` 按 **手填 `douban_cookie` → 宿主 CookieCloud → 无** 的顺序取 Cookie，
   结果在内存里缓存 `_COOKIE_TTL = 1800` 秒（30 分钟），不落盘、不打日志。
2. CookieCloud 取值走 `POST {COOKIECLOUD_HOST}/get/{COOKIECLOUD_KEY}`，body `{"password": COOKIECLOUD_PASSWORD}`，
   直接拿**服务端已解密**的 `cookie_data`（插件**不实现 AES 解密**）。
   配置键读自宿主 `settings`：`COOKIECLOUD_HOST` / `COOKIECLOUD_KEY` / `COOKIECLOUD_PASSWORD`。
3. 只挑域名含 `douban.com` 的分组，同名 Cookie 保留第一个、跳过空值，拼成 `k=v; k=v` 传给 `RequestUtils(cookies=...)`。
4. 取不到时 `last_error` 会写明原因（未配置 / 只回密文 / 没有该域名 / HTTP 非 200 / 网络异常），
   面板与配置页把 `douban_cookie_source`（`manual` / `cookiecloud` / 空）原样展示出来。

面板标题栏与配置页都有 **Cookie 状态徽标**：

| 徽标 | 含义 |
| --- | --- |
| `Cookie：CookieCloud`（绿） | 已自动读取宿主豆瓣登录态，额度最佳 |
| `Cookie：手填`（绿） | 使用插件配置里手工粘贴的 Cookie |
| `Cookie：未取到`（黄） | 没有登录态，按名称搜索会被严格限流；悬浮可看具体原因 |

> 若 CookieCloud 服务端只返回 `encrypted`（未在服务端解密），插件不做本地解密，
> 此时请在插件配置里**手工粘贴**豆瓣 Cookie 兜底。

### 三类失败提示

`_DoubanClient.failure_hint()` 会区分失败根因，避免用户误操作：

| 触发条件 | 提示常量 | 文案要点 |
| --- | --- | --- |
| 未配 Cookie 且 `need_login` | `_NEED_LOGIN_HINT` | 去配 Cookie / 确认 CookieCloud，或直接填人物 ID |
| 配了 Cookie 仍 `need_login` | `_COOKIE_EXPIRED_HINT` | Cookie 可能已失效，重新登录豆瓣并同步 CookieCloud |
| 单纯限流（HTTP 403 且非 `need_login`） | `_RATE_LIMIT_HINT` | 稍后自动重试，或直接填人物 ID 跳过搜索 |

## 兼容性

- 目标宿主：MoviePilot **V3**（`>=3.0.0`），已在 **v3.1.3** 实测。
- 仅从稳定入口导入：`app.sdk.*` / `app.schemas.types` / `app.chain.subscribe` / `app.agent.tools.base`；
  不使用 `app.helper.*`、`app.utils.*`、`app.core.*`。
- `MessageType` 做了 try/except 兼容导入（旧版本名为 `NotificationType`）。
