# TMDB 演员订阅（DoubanActorSubscribe）

订阅 **TMDB 演员**，抓取该演员的**最新影视作品**并展示在面板中；面板上的每个作品都带**订阅按钮**，
一点即提交到 MoviePilot 订阅系统（按 **TMDB 身份**精确订阅）。也支持按类型/评分阈值**自动订阅**新作品。

> **插件 ID 仍是 `DoubanActorSubscribe`（历史沿革）**：目录名、类名、联邦名、远程命令、配置前缀
> 一律保持不变 —— ID 一改，用户已保存的配置与订阅归属会全部丢失。v1.15.0 只改了**显示名**
> （豆瓣演员订阅 → TMDB演员订阅）与**发现源**。

---

## 1. 数据来源：TMDB

| 项 | 说明 |
|---|---|
| 凭据 | 沿用宿主「系统设置 → 媒体数据源」里的 **`TMDB_API_KEY`**，插件侧不需要任何登录态 |
| 接口域名 | 取宿主的 `TMDB_API_DOMAIN`（国内实例常指向自建反代），缺失时回落 `api.themoviedb.org` |
| 图片域名 | 取宿主的 `TMDB_IMAGE_DOMAIN`（常与接口分开部署），缺失时回落 `image.tmdb.org` |
| 语言 | 请求统一带 `language=zh-CN`：中文名才能和宿主识别结果、媒体库条目对得上 |
| 演员作品 | `GET /3/person/{id}?append_to_response=combined_credits` —— **一次请求拿全**人物详情与参演作品 |
| 候选范围 | 只取 `combined_credits.cast`（演员本人参演），**不含** `crew`（编剧 / 导演） |

因为整条链路都不依赖登录态，所以**不再有搜索限流、Cookie 失效、24 小时搜索冷却**这些问题
（v1.14.0 及之前走豆瓣时，这些正是主要的失败来源）。

---

## 2. 功能一览

| 功能 | 说明 |
|---|---|
| 演员配置 | 支持**TMDB 人物主页链接**（推荐，直接解析出 ID，不消耗搜索）、**演员名称**（自动搜索并缓存人物 ID）或直接填**人物 ID**（纯数字）。配置页为**固定高度的文本域**：多位演员用**逗号分隔**（兼容换行 / 顿号 / 分号），内部滚动，演员再多也不撑长页面 |
| 名称核对 | 按名称添加时若 TMDB **没有同名演员**，插件不会默默换成另一个人：演员 chip 会显示「配置名 **→** 实际解析到的名字」并带 ⚠/❓ 标记，悬停可见候选名单，提示改用人物 ID 精确指定 |
| 作品抓取 | 人物详情 → `combined_credits.cast` → 归一化标题 / 原名 / 年份 / 类型 / 评分 / 海报 / 角色名 |
| 作品墙 | 海报卡片墙，可按演员筛选；卡片角上标「新」「已订阅」「已入库」；工具栏带「只看未入库」开关 |
| 一键订阅 | 前端调用宿主 `subscribe/` 接口，携带 `media_source=themoviedb` + `media_id`，归属当前登录用户；订阅偏好（下载路径 / **下载器** / 站点）在配置页统一维护，面板沿用 |
| 取消订阅 | 已订阅的作品卡片上按钮变为**取消订阅**，点一下即按 TMDB 身份（`media_source` + `media_id`）取消该作品的订阅；详情页、侧栏全页与仪表板三处行为一致 |
| 打开详情 | 作品卡片上的按钮不外链 TMDB，改为在**新标签页打开 MoviePilot 自带的媒体详情页**（与探索页点进媒体是同一个页面）：识别结果、订阅状态、站点资源一眼看完；类型识别不出的作品才退回 TMDB 条目页 |
| 忽略 / 恢复 | 卡片上的「忽略」把作品移出面板且**不参与自动订阅**；数据仍留在快照里，面板顶部可随时恢复 |
| 自动订阅 | 按类型白名单 + 最低评分 + 单次上限筛选；首次抓取某演员只建立基线，不会一次性订阅其全部历史作品 |
| 媒体库检查 | 每部作品标注是否**已在媒体库**，判定与宿主**媒体详情页完全同源**（复用宿主的 `MediaServerOper.get_item_id`）；已在库的作品只标记，并在自动订阅时跳过 |
| 仪表板 / 侧栏 | 仪表板小组件 + 主界面侧栏两个全页入口（作品面板、运行状态） |
| 智能体工具 | `douban_actor_latest_works`：让 AI 查询已跟踪演员的最新作品 |

### 界面版式

- **作品面板**（`nav_key = main`）自上而下：作品墙 → 账本（自动订阅记录）→ 冷却/待解析。
  **不单列演员清单块** —— 演员只出现在作品墙的筛选 chip 行（「全部演员」+ 每位演员 + 作品数），
  悬停显示「TMDB 人物 ID｜N 部作品｜失败原因」；解析状态只留工具条下一句汇总。
- **运行状态**（`nav_key = settings`）为只读概览：统计卡（演员 / 作品 / 近 N 天新增 / 已在媒体库 / 上次刷新）
  + 订阅选项 + 快速配置（启用、演员、cron）+ 自动订阅历史。
- 宿主的全页壳只注入 `api` / `nav-key` / `plugin-id` / `source-plugin-id` / `native-subscribe`，
  **不提供设置入口**，因此标题栏自绘「设置」按钮，用 `v-dialog` 内嵌 `Config.vue`（复用同一联邦 chunk）。
  ⚠️ 必须**先 `fetchConfig` 再挂载弹窗**：`Config.vue` 只在 `onMounted` 读一次 `initialConfig`。
- 宿主另提供 `#/plugins?id=<插件ID>` 深链（切「已安装」tab 并展开卡片），但要两跳，不如自绘弹窗直接。

---

## 3. 配置项

| 键 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `enabled` | bool | `false` | 启用插件 |
| `sidebar_nav` | bool | `true` | 是否在 MoviePilot 主界面侧栏展示入口（关闭后插件照常运行） |
| `cron` | str | `0 8 * * *` | 定时刷新周期（5 段式 cron） |
| `actors` | str | 空 | 演员列表（后端以换行串存储，面板以**逗号分隔**编辑）；**推荐直接粘贴 TMDB 人物主页链接**（如 `https://www.themoviedb.org/person/1245`），也支持人物 ID 或名称（分隔符可用逗号/顿号/分号/换行） |
| `max_works` | int | `10` | 每位演员保留的作品条数（5–60）。TMDB 的参演表是完整的，上限由插件裁定，不是接口限制 |
| `sort_by` | str | `time` | `time` 按年份倒序（新的在前）/ `vote` 按评分倒序（同分再比年份） |
| `proxy` | bool | `false` | 走宿主配置的代理访问 TMDB |
| `notify` | bool | `false` | 刷新完成后发送通知 |
| `auto_subscribe` | bool | `false` | 开启自动订阅 |
| `auto_only_new` | bool | `true` | 只自动订阅**新出现**的作品（首次抓取只建立基线） |
| `auto_min_vote` | float | `0` | 自动订阅的最低 TMDB 评分（0 表示不限） |
| `auto_types` | str | `电影,电视剧` | 自动订阅的类型白名单（逗号分隔） |
| `auto_max_per_run` | int | `5` | 单次刷新的自动订阅上限 |
| `subscribe_save_path` | str | 空 | 订阅 / 预订时的保存路径；留空沿用宿主默认订阅配置 |
| `subscribe_downloader` | str | 空 | 订阅 / 预订使用的下载器名称（宿主 `/download/clients` 里的 name）；留空沿用宿主默认 |
| `subscribe_sites` | list[int] | `[]` | 订阅 / 预订时使用的站点 ID 列表；留空沿用宿主默认 |
| `onlyonce` | bool | `false` | 启用后立即执行一次（执行后退回 `false`） |

> ⚠️ v1.15.0 起配置里**不再有 `douban_cookie`**。旧配置里若残留该键，保存时会被自动丢弃。

---

## 4. 插件接口

挂载在 `api/v1/plugin/DoubanActorSubscribe/<path>`（`bear` 鉴权）。

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/config` | 读取当前运行时配置（含订阅偏好回显） |
| PUT | `/config` | 合并保存配置并重建运行状态（运行时统计不落盘） |
| GET | `/works` | 演员与作品快照 + 统计（`new_count` / `new_actor_count` / `library_count` / `library_known` / `unresolved_count` …） |
| POST | `/run` | 立即刷新一次（后台执行，前端靠 `refreshing` 轮询） |
| GET | `/search_actor` | 按名称搜索 TMDB 演员（直接给 ID / 链接时不发请求） |
| POST | `/reserve` | 把订阅失败的作品转为**预订**（待定 `P`） |
| POST | `/unsubscribe` | 按 TMDB 身份删除该作品的全部订阅记录（可带 `season` 收窄） |
| POST | `/ignore` | 忽略某部作品（不再展示、自动订阅也跳过） |
| POST | `/unignore` | 恢复被忽略的作品（`key="themoviedb:123"`，或 `{"all": true}` 清空） |
| POST | `/actor/remove` | 从订阅演员中移除一位（同步删除配置里的同名条目） |
| POST | `/clear` | 清空作品快照与自动订阅记录（配置不受影响） |

### 远程命令 / 工作流

- **远程命令**：`/doubanactor` → `EventType.PluginAction` → `on_plugin_action`。
- **工作流动作**：`doubanactorsubscribe_refresh`。

---

## 5. 「新」的判定口径

两套判定**彼此独立**，任何一处都不会带歪另一处：

- **新演员**：看 `joined_at` —— 只在「解析缓存里原本查无此人」时写入，距今不超过 3 天则 chip 标「新」。
  升级前就在订阅列表里的老演员不会被补标（他们的加入时间不可考，宁可什么都不标）。
- **新作品**：`first_seen` **晚于**该演员的 `baseline_at`（即「演员加入之后才出现」），且距今不超过 3 天。
  同一轮刷新里建立的基线作品，其 `first_seen` 与 `baseline_at` 取**同一个时间戳**，因此基线作品天然不算「新」。
- 口径字段随载荷下发（`new_window_days`），面板把「近 N 天新增（演员 / 作品）」写进统计卡。
- ⚠️ 刷新通知里的「本次新收录 N 部」是**另一口径**（含刚建立基线的作品），与面板的「新作品」分开写。

---

## 6. 媒体库存在性检查

判定与宿主**媒体详情页**完全同源：复用宿主的 `MediaServerOper().get_item_id()`，
先在本地库表里按「规范媒体身份 + 类型」精确匹配，未命中且有片名时按「片名 + 类型 + 年份」回退。

- **三态**：`true` / `false` / **缺省 = 未知**（旧快照或查库失败）。
  未知状态下不标记、不计数、不跳过订阅，「只看未入库」也不排除它。
  任何一处塌缩成两态，都会把异常显示成结论。
- 一轮刷新内按作品去重缓存：同一部作品挂在多位演员名下也只查一次、只算一次。
- 自动订阅会跳过**明确在库**的作品（`in_library is True`）。
- 查库失败时清掉上一轮留下的旧标记，避免把过期结论继续展示。

---

## 7. 升级到 v1.15.0（发现源切换）的影响

发现源由豆瓣整体换成 TMDB，人物 ID / 作品 ID 是两套完全无关的编号，
拿旧的豆瓣 ID 去查 TMDB 轻则查不到、重则**查到另一个人**，因此升级时做**一次性迁移**：

| 数据 | 处理 | 原因 |
|---|---|---|
| 旧作品快照 `works` | **清空**，下次刷新重建 | 旧条目的身份是豆瓣编号 |
| 演员解析缓存 `actors` | 清掉身份字段（`id` / 姓名 / 头像 / 简介 / 来源），**保留 `joined_at`** | 旧 ID 不能用；但「加入时间」与发现源无关，删了会把上百位老演员补成「新演员」 |
| 基线时刻 `baseline_at` | **重置** | 新身份下这批作品即为新基线，否则「旧基线 + 全新 first_seen」会让整屏作品被标「新」 |
| 忽略记录 `ignored_works` | **清空** | 键是 `douban:<subject_id>`，无法映射到 TMDB ID，留着只是死条目 |
| 自动订阅去重表 `auto_seen` | **清空** | 同上；清空后由「只订阅新作品」的基线逻辑兜住，不会误订阅历史作品 |
| 自动订阅历史 `auto_subscribed` | **保留** | 属于用户的历史记录 |
| 演员配置 / 订阅偏好 / 各类开关 | **保留** | 与发现源无关 |
| 解析缓存里的空壳条目 | **清空**（每次都做，见下） | 只有 `key` 一条、不承载任何状态 |

迁移只做一次（数据目录里的 `schema` 键标记）。首次迁移后会自动安排一次后台刷新，
把面板从旧的豆瓣数据整体换成 TMDB 数据。

> 除了这次迁移，运行时还有**第二道防线**：解析缓存里若出现不带 TMDB 来源标记的身份
> （例如恢复了旧备份），刷新时会自动丢弃并重新解析。

### 空壳缓存清理（`_prune_orphan_cache`）

历史版本在解析失败或调整演员列表时只写了键、没写值，缓存里于是堆了一批形如
`{"key": "张译"}` 的空壳（`key` 只是键名的副本，不承载状态）。线上实测：115 条缓存里
**112 条是空壳**。`init_plugin` 每次都会顺手清掉它们（无变化时不写盘、不打日志）。

判定刻意保守：`id` / `joined_at` / `baseline_at` 三者**一个都不剩**才删。三者分别承载
「这个人是谁」「什么时候加的」「新作品基线」，任意一个还在就说明条目还担着状态。

清理还顺手修掉一个隐蔽问题：`_refresh_actor` 用 `first_sight = not actor` 判断「是否新加入
的演员」，而 `{"key": "x"}` 是非空字典 —— 会让一位其实**从没解析成功过**的演员冒充老演员，
永远拿不到 `joined_at`（chip 上永不标「新」）。删掉空壳恰好把这条语义交还给事实。

> 面板上看不到新界面时请 **Ctrl+F5 强刷**（联邦产物带版本号缓存）。

---

## 8. 关键实现约定

- **订阅链**：`_add_subscribe` 走官方 `app.chain.subscribe.SubscribeChain`，
  `media_source=MediaSource.TMDB`，`username=PLUGIN_NAME`；
  订阅偏好留空时传 `None`，由宿主按系统默认配置补全。
- **预订兜底**：未播出 / TMDB 信息不全的作品会被订阅链以「缺季集信息」拒掉。
  这不是「作品有问题」而是「信息还没到」，因此自动降级为**预订**（状态 `P` + 占位总集数），
  等影视播出、信息补全后照常参与搜索。与信息无关的失败（分类无效等）**不**走这条路。
- **状态兜底**：宿主建完订阅后可能把 `state` 回写成 `N`（待订阅），
  插件会回读并补写一次 `P`，避免预订语义丢失。
- **刷新落盘顺序**：先标注媒体库状态，再统一 `save_data("works", snapshot)`，
  保证标记随之持久化。
- **配置合并**：`api_update_config` 只落盘业务配置，
  `run_count` / `pending_refresh` / `refreshing` / `douban_cookie` 一律剔除。
- **不在导入期做网络 / 数据库 / 任务启动**；宿主的 `MediaServerOper` 惰性导入，
  宿主版本缺少该模块时插件仍能正常加载（只是不标注入库状态）。
- **无 Cookie / 无签名 / 无限流逻辑**：凭据与域名全部来自宿主 `settings`，缺失时逐项回落官方域名。

---

## 9. 前端构建（Vue 联邦）

```bash
cd plugins.v3/doubanactorsubscribe
npm install
npm run typecheck   # vue-tsc --noEmit
npm run build       # 产物在 dist/assets
```

- 联邦名 `DoubanActorSubscribe`，`remoteEntry.js` 暴露
  `./Page` `./Config` `./Dashboard` `./AppPage` `./AppPageSettings`。
- `shared` 只共享 `vue`（`generate: false`），UI 组件库由主程序全局注册，不重复打包。
- `build.target` 必须为 `esnext`（联邦产物含顶层 await）。
- 不要显式指定 `rollupOptions.input`，交给联邦插件生成 `__federation_expose_<Name>-<hash>.js`。
- 海报地址由后端按宿主的 `TMDB_IMAGE_DOMAIN` 拼成完整 URL（`w300`，卡片宽约 134px 足够清晰），
  前端直接 `<img src>`；拼不出时返回空串，由前端决定是否回退。
- 作品名点击的去向：有类型 → 宿主媒体详情页
  （`<应用基址>#/media?media_source=themoviedb&media_id=…&title=…&year=…&type=…`）；
  类型缺失 → `https://www.themoviedb.org/{movie|tv}/{id}`。

### 本地单测

```bash
python scripts/run_tests_local.py tests/v3/doubanactorsubscribe   # 无需宿主源码树
```

---

## 10. 设计备忘

- **按名称解析的模糊命中**：TMDB 人物搜索是模糊匹配，配置「宋星颐」可能返回
  「宋星翰 / 宋星成…」。插件记下 `fuzzy` 与候选名，面板显式提示
  「配置名 → 实际解析到的名字」，由用户决定是否改用人物 ID。
  同名判断同时比 `name` 与 `original_name`（`name` 受 `language` 影响）。
- **作品身份去重**：`_work_unique()` 用 `media_source:media_id`，
  必须与前端 `workKey()` 完全一致，否则「忽略 / 已订阅」会对不上。
- **张冠李戴的现算**：`fuzzy` 在展示时按「来源是名称搜索 且 配置名 ≠ TMDB 名」现算，
  这样 `fuzzy` 字段出现之前写入的旧缓存同样能被标出来；
  直接填人物 ID 的配置名是数字，必须按 `resolved_from` 先排除，否则全是误报。
- **自动订阅的「首次」判定**：`had_previous` 看的是「上一份快照里有没有这位演员的作品」，
  而不是「这一轮有没有新作品」，因此首次抓取只会建立基线，不会把历史作品一网打尽。
- **解析失败的展示口径**：面板**不逐条铺错误**。后端 `classify_error()` 把失败文案归成原因码、
  `record_state()` 写成 `''` / `waiting` / `empty`，前端只给一句汇总、chip 至多一个淡沙漏图标；
  完整原因仍存在 `actors[].errors` 里可查。
- **失败与空结果的区分**：TMDB 请求失败（网络 / 凭据 / 5xx）一律 `retryable`，
  提示「稍后会自动重试」；只有「确实没有搜到这个人」才建议改用人物 ID。
