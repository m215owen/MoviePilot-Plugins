# 豆瓣演员订阅（DoubanActorSubscribe）

订阅豆瓣演员，抓取该演员的**最新影视作品**并展示在面板中；面板上的每个作品都带**订阅按钮**，
一点即提交到 MoviePilot 订阅系统（按**豆瓣 ID 精确订阅**）。也支持按类型/评分阈值**自动订阅**新作品。

```
配置演员 → 定时/手动刷新 → 抓取作品快照 → 仪表板 + 侧栏面板展示 → 一键订阅 / 自动订阅
```

## 功能

| 能力 | 说明 |
| --- | --- |
| 演员配置 | 支持**豆瓣人物主页链接**（推荐，最稳，直接解析出 ID，不消耗搜索配额）、**演员名称**（自动搜索并缓存豆瓣人物 ID）或直接填**豆瓣人物 ID**（纯数字）。配置页为**固定高度的文本域**：多位演员用**逗号分隔**（兼容换行 / 顿号 / 分号），内部滚动，演员再多也不撑长页面 |
| 名称核对 | 按名称添加时，若豆瓣上**没有同名演员**，插件不会默默换成另一个人：面板的演员 chip 会显示「配置名 **→** 实际解析到的豆瓣名」并带 ⚠/❓ 标记，悬停可见候选名单，提示改用人物 ID 精确指定 |
| 作品抓取 | 豆瓣 Frodo API：人物详情 → 影视作品集 → 作品列表，归一化标题/年份/类型/评分/海报/职务 |
| 面板展示 | **统一作品墙**（跨演员按时/新作品排序，卡片标出**出演演员**，演员以 chip 筛选代替分组，演员超过 12 位时折叠、可一键「展开全部」）+ 完整筛选 + 每页 20 部分页 + 批量订阅（需二次确认） |
| 移除演员 | 面板演员筛选的每个 chip 右侧带 **×** 按钮，确认后把该演员从订阅演员中移除，并**同步删除配置页里的同名条目**、清理其作品数据（已提交的订阅不受影响） |
| 忽略作品 | 每张作品卡片带「忽略」按钮；被忽略的作品不再展示、也不会被自动订阅（数据保留，面板顶部「已忽略 N 部」可随时恢复） |
| 异常提示 | 异常**只在配置页**呈现：先展示 5 秒，然后自动收起为「N 项异常（点击查看）」小标签；手动点开后**常驻展开**，不再自动缩起 |
| 一键订阅 | 前端调用宿主 `subscribe/` 接口，携带 `media_source=douban` + `media_id`，归属当前登录用户；订阅偏好（下载路径 / **下载器** / 站点）在配置页统一维护，面板沿用 |
| 取消订阅 | 已订阅的作品卡片上按钮变为**取消订阅**，点一下即按豆瓣身份（`media_source` + `media_id`）取消该作品的订阅；详情页、侧栏全页与仪表板三处行为一致 |
| 打开详情 | 作品卡片上的按钮不再外链豆瓣，改为在**新标签页打开 MoviePilot 自带的媒体详情页**（与探索页点进媒体是同一个页面）：识别结果、订阅状态、站点资源一眼看完；类型识别不出的作品才退回豆瓣条目页 |
| 搜索资源 | 作品卡片与仪表板上带「搜索资源」按钮：**先选站点、再打开 MoviePilot 自带的资源搜索页自动搜一遍**（站点清单与默认勾选取自宿主，见下）。地址里带上该作品的豆瓣身份做精确搜索，宿主未加载媒体源清单时退回按片名模糊搜索，打开即有结果 |
| 自动订阅 | 定时刷新后按「只订阅新作品 / 类型白名单 / 最低评分 / 每次上限」自动调用订阅链落库；被忽略的作品一律跳过 |
| 订阅失败→预订 | 未播出 / 信息尚未收录导致缺季集信息时，不判失败而是降级为**预订**（订阅状态置为「待定」，允许搜索、不允许完成），等影视播出后自动接管 |
| 通知 | 可通过宿主通知渠道推送刷新结果与自动订阅明细 |
| 智能体工具 | `douban_actor_latest_works`：让 AI 查询已跟踪演员的最新作品 |

## 配置项

| 字段 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| `enabled` | bool | `false` | 启用插件 |
| `sidebar_nav` | bool | `true` | 是否在 MoviePilot 主界面侧栏显示插件入口。关闭后插件**照常运行**（定时刷新、自动订阅都不受影响），只是不再占用侧栏位置 |
| `actors` | str | 空 | 演员列表（后端以换行串存储，面板以**逗号分隔**编辑）；**推荐直接粘贴豆瓣人物主页链接**（如 `https://www.douban.com/personage/37871253/`），也支持人物 ID 或名称（分隔符可用逗号/顿号/分号/换行） |
| `subscribe_save_path` | str | 空 | 面板订阅时默认保存路径（透传给宿主 `subscribe/`） |
| `subscribe_downloader` | str | 空 | 面板订阅时默认下载器，取宿主已配置下载客户端的名字（来自 `download/clients`），留空沿用宿主默认订阅配置 |
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
| POST | `/reserve` | 把**订阅失败的作品转为预订**（待定）：面板订阅被宿主拒绝后的兜底入口（body：`title`/`year`/`type`/`media_source`/`media_id`，可带 `poster`/`vote`/`save_path`/`downloader`/`sites`） |
| POST | `/unsubscribe` | **取消订阅**：按豆瓣身份删除该作品的订阅记录（body：`media_source`/`media_id`/`title`，可带 `season` 只取消某一季）。查不到记录时如实返回失败，避免界面误报「已取消」 |
| POST | `/ignore` | 忽略一部作品（body：`media_source`/`media_id`/`title`/`year`/`type`）。忽略后在快照中**过滤**，但原始数据保留，且自动订阅会跳过它 |
| POST | `/unignore` | 恢复被忽略的作品（body：`key="douban:123"`，或 `{"all": true}` 清空整份忽略列表） |
| POST | `/actor/remove` | 从订阅演员中移除一位并**同步删除配置里的同名条目**（body：`actor`＝配置里写的原文，可带 `actor_id` 兜底）。随后丢弃其作品快照并安排一次后台补刷新 |
| POST | `/clear` | 清空作品快照与自动订阅记录（不动配置） |

> 插件动态路由**不套宿主的 `Response[T]` 外壳**，因此插件接口一律自行返回 `{success, data}`。
>
> 宿主是用 `router.add_api_route(**api)` 注册这些路由的，参数由 **FastAPI 注入**：
> `Optional[Dict[str, Any]] = None` 会被识别成 **requestBody**（`anyOf: [object, null]`，参数名随意），
> `name: str = ""` 则是 **query** 参数。可在实例的 `/openapi.json` 里直接核对归属。

## 其他扩展点

- **定时服务**：`get_service()` 注册 `<类名>.Refresh`，cron 由配置决定；未启用或未配置演员时不注册。

  ⚠️ 传给被调函数的参数必须写在 **`func_kwargs`** 里，**不能写成 `kwargs`**。宿主注册服务时会把
  `service["kwargs"]` 原样展开给 `scheduler.add_job()`（见宿主 `scheduler/reconcile.py` 的
  `update_plugin_job`），而 `trigger` 正是 `add_job` 自己的形参名 —— 写成 `kwargs` 会让
  `add_job()` 收到两个 trigger 并抛 `got multiple values for argument 'trigger'`，
  **注册被静默拒绝、定时刷新永远不会执行**（宿主只写一条 ERROR 日志）。
  宿主内置插件（`popularsubscribe` / `brushflow` / `strmredirect`）用的都是 `func_kwargs`。
  一次性任务 `add_plugin_once_job(...)` 的关键字参数同样叫 `func_kwargs`。
- **远程命令**：`/doubanactor` → `EventType.PluginAction` → `on_plugin_action`。
- **工作流动作**：`doubanactorsubscribe_refresh`。
- **侧栏入口**：`nav_key=main`（作品面板）与 `nav_key=settings`（运行状态），`section=subscribe`；
  受配置项 `sidebar_nav` 与 `enabled` 双重控制（任一为关则不注册）。
- **仪表板**：`key=works`，`cols/sm/md = 12/6/4`，刷新间隔 300s。

## 前端（Vue 模块联邦）

`get_render_mode()` 返回 `("vue", "dist/assets")`，宿主直接加载 `dist/assets/remoteEntry.js`。

```
src/
├── api.ts                 # 接口封装：插件 API + 宿主 subscribe/ 接口 + 图片代理 + 时间格式化
├── types.ts               # 与后端 payload 对齐的 TS 类型
├── WorkGrid.vue           # 作品海报墙（Page / AppPage 复用，带出演演员行 + 订阅 / 详情 / 搜索资源 / 忽略按钮）
├── SearchResourceButton.vue # 「搜索资源」按钮 + 站点选择框（两步式，与宿主媒体详情页一致）
├── SitePickDialog.vue     # 站点选择框（清单与默认勾选都取自宿主，见下）
├── IgnoredManager.vue     # 「已忽略的作品」入口与恢复弹窗
├── ErrorAlerts.vue        # 异常提示条：5s 后自动收起，可点击小标签再展开
├── SubscribePrefs.vue     # 订阅偏好（保存路径 / 下载器 / 站点），Config 与运行状态页共用
├── Page.vue               # 插件详情页（顶部固定操作条：刷新 / 配置插件 / 通知宿主刷新 / 关闭）
├── Config.vue             # 配置页（emit('save', cfg) 由宿主持久化）
├── Dashboard.vue          # 仪表板小组件
├── AppPage.vue            # 侧栏全页 · 作品面板（nav_key=main）
└── AppPageSettings.vue    # 侧栏全页 · 运行状态（nav_key=settings）
```

> **详情页布局**：操作按钮固定在页面**顶部**，作品墙再长也不需要滚到底找按钮。
> **打开详情**：作品卡片的详情按钮跳宿主自带的媒体详情页，地址形如
> `<应用基址>#/media?media_source=douban&media_id=…&title=…&year=…&type=…`。
> 两处易错点：① 宿主前端用的是 **hash 路由**（`createWebHashHistory`，base 形如 `./#`），
> 直接拼 `/media?…` 只会落到站点根路径、被 SPA 兜底渲染成首页，看起来像「点了没反应」；
> ② 宿主详情页**强依赖 `type`**（中文的 电影 / 电视剧），缺它会渲染成空壳，
> 所以插件在类型缺失时退回豆瓣条目页。应用基址取「当前地址去掉 `#` 之后的部分」，
> 这样即使实例被反代到子路径也不会拼错。见 `api.ts` 的 `mediaPageUrl()`。
> **搜索资源**：作品卡片的搜索按钮跳宿主自带的**资源搜索页**，地址形如
> `<应用基址>#/resource?media_source=douban&media_id=…&keyword=…&title=…&year=…&type=…`。
> 宿主该页会**从 query 反解搜索条件并自动发起搜索**，因此可以当作「按作品搜资源」的深链。
> 两套参数同时带上是为了兜底：`media_source` + `media_id` 命中时走**精确搜索**
> （`search/media/{id}`，季集匹配更准），否则只要 `keyword` 非空就走**模糊搜索**（`search/title`）
> —— 宿主只在探索 / 媒体详情等路由预加载媒体源清单，用户直接进搜索页时清单可能为空、
> 精确搜索会被跳过，所以 `keyword` 这一手不能省。见 `api.ts` 的 `resourceSearchUrl()`。
>
> **搜索站点选择框（与宿主同源）**：点搜索按钮**先弹站点选择框**，确认后才带着
> `&sites=1,2,3` 跳转 —— 这与宿主媒体详情页「搜索资源」的两步式交互完全一致。
> 宿主的弹窗是主程序内部组件，联邦插件 import 不到（联邦只共享 `vue` / `vuetify`），
> 所以界面由插件自绘，但**数据与默认值都取自宿主**，所见与系统一致：
> - 站点清单：`site/media/{movie|tv|music}`（宿主按媒体类型裁剪出的**启用中**站点，
>   电视剧只列剧集站；返回体带站点 cookie，插件只取 `id`/`name`/`domain`）；
> - 默认勾选：`system/setting/public/IndexerSites`（系统设置里的「搜索站点」），
>   实例没配过时退回全选，避免一打开就是空；
> - 媒体类型映射与宿主同一套：只有 `电视剧→tv`、`音乐→music`，其余按 `movie`。
>
> 站点清单为空（实例没配站点）时**直接跳转、不弹空框**，与宿主行为一致；清单按媒体类型
> 缓存，同一部作品重复点开不会重复请求。见 `SearchResourceButton.vue` / `SitePickDialog.vue`。
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
- **「新」的语义**：两套标记彼此独立，都在输出时**现算**（面板载荷、仪表板统计、刷新落盘共用
  `_apply_new_flags` / `_is_fresh_actor`），各自有独立字段，改一个不会带歪另一个。

  | 标记 | 字段 | 判定 | 展示 |
  | --- | --- | --- | --- |
  | 新演员 | `joined_at` | 距今 ≤ `_NEW_WINDOW_SECONDS`（默认 3 天） | 演员 chip 上的「新」（悬停见加入时间） |
  | 新作品 | `baseline_at` + `first_seen` | 作品 `first_seen` **晚于**演员 `baseline_at`，且距今 ≤ 同一时间窗 | 作品卡片左上角的「新」 |

  关键在第二条：**只有演员加入之后才出现的作品才算「新」**。刚把上百位演员一次性导入时，
  他们过去几十年的作品属于「基线」，一张都不会标「新」（旧口径下 98 位演员 = 844 部全中，
  糊成一片且毫无信息量）。实现上靠「同一轮刷新里基线作品的 `first_seen` 与演员 `baseline_at`
  取同一个时间戳」来保证基线天然不达标，不需要额外的白名单。

  一条经验教训：`joined_at`（加入）与 `baseline_at`（基线）**不要合成一个字段**。
  合并时的版本会在升级瞬间给所有老演员补上「现在」当加入时间，于是 98 位演员的 chip
  一夜之间全被标成「新演员」——而他们其实早就订阅了大半年。现在 `joined_at` 只在
  **解析缓存里原本查无此人**（真正新加入）时才写；升级前就在列表里的老演员加入时间不可考，
  两个字段都不补（作品那边等下一轮刷新写下 `baseline_at` 即可），宁可什么都不标。
  中间版本遗留的 `added_at` 字段会在刷新时顺手清掉，读到旧值也不会被当成本次语义。

  ⚠️ 不要改回「相对上一轮快照新增」的口径。旧口径只活到下一次刷新为止：抓完新作品后随手点一次
  刷新、插件被重载、或定时任务跑一轮，`is_new` 就全被清零了 —— 于是计数长期是 0、
  勾上「只看新作品」一片空白，看起来就像插件没抓到东西（实测用户就是这么报障的）。

  通知文案里的「本次新收录 N 部」是**另一个口径**（只统计快照里第一次见到的作品，由
  `_refresh_actor` 的第 4 个返回值给出，含刚建立的基线），故与面板的「新作品」分开写：
  否则通知会天天报「新增 88 部」而面板显示 0。开启 `auto_only_new` 时首次刷新只建立基线，
  不会批量订阅历史作品；自动订阅只挑 `is_new` 的作品，因此也只会订阅真正后出现的那些。

  天数由 `_NEW_WINDOW_DAYS` 决定，随面板载荷下发（`new_window_days`）并显示在统计卡上
  （「近 3 天新增（演员 / 作品）」），避免用户看到 0 或很大的数时无从判断是坏了还是口径如此。
  不宜调得太大：一次性导入上百位演员时全部作品都会落在窗口内，标成「新」的会糊成一片。
- **名称解析的模糊命中**：豆瓣人物搜索是模糊匹配，配置「宋星颐」实际返回的是
  「宋星翰 / 宋星成 / 宋星辰…」。找不到**同名**候选时插件会退回第一个结果（否则这项配置
  直接报废），但会把这次退回记为 `fuzzy=True` 并带上 `candidates`（前 5 个候选名）：
  面板演员 chip 显示「配置名 → 豆瓣名」，前端 `mergeWorks` 也把两个名字都放进
  `actorNames`，用户按自己填的名字搜作品仍然搜得到。要彻底避免张冠李戴就填人物 ID。

### 订阅失败 → 自动改为「预订」

**背景**：未播出（或豆瓣条目刚建、TMDB 还没收录）的影视拿不到季集信息，宿主订阅链在
`__prepare_subscribe_episodes` 就会拒绝创建，报「媒体信息中没有季集信息」/「未获取到第 N 季的
总集数」/「未识别到媒体信息」。这类失败缺的是**信息**而不是作品有问题，直接判失败等于
把最需要占位的作品挡在门外。

因此命中这类原因时，插件会把作品降级为**预订**（宿主订阅状态 `P`-待定）：

| 订阅状态 | 含义 |
| --- | --- |
| `N` 新建 | 宿主默认初始态 |
| `R` 订阅中 | 正常订阅 |
| **`P` 待定** | **允许搜索、不允许完成** —— 即「预订」：不会在资源出现前被误判为已看完，也不会漏掉后续资源 |
| `S` 暂停 | 暂停自动调度 |

两级兜底（`_reserve_subscribe`）：

1. **仍走官方订阅链**，但多传 `state="P"` + 占位 `total_episode=1`。
   占位总集数让那条 `if not total_episode` 的季集补齐分支整段跳过，于是不再被拒；
   宿主刷新增量时会自动把总集数向上覆盖（**前提是 `manual_total_episode` 保持 0，所以绝不能顺手置 1**）。
2. 若连识别都过不去（TMDB 尚未收录），改用 `app.sdk._legacy.subscribe.SubscribeOper`
   **直接写一条待定订阅**：身份用豆瓣 `media_id`，状态 `P`，集数留占位值，等宿主刷新到真实信息后照常参与搜索。

两条路径都会回读一次订阅并**校正状态为 `P`**（`_ensure_pending_state`）——创建路径带的是宿主默认状态，
个别版本可能忽略调用方传入的 `state`，回读补写才能保证「预订」语义真的落地。

其他原因（分类无效、网络异常等）**不会**被包装成预订，仍如实上报失败。

> 面板按钮走的是宿主公开接口 `POST subscribe/`（为了让订阅归属当前登录用户），
> 但该接口的公开写入字段**把 `state` 排除在外**、也无法绕过季集识别，所以前端拿到
> 「缺季集信息」类失败后会回落到插件接口 `POST /reserve`，由插件建这条待定订阅。

## 订阅偏好：下载路径 / 下载器 / 站点

三个偏好都在配置页的「订阅选项」里维护（`subscribe_save_path` / `subscribe_downloader` /
`subscribe_sites`），提交订阅时一并带给宿主；**留空表示沿用宿主自己的默认订阅配置**。

- **下载路径**：可下拉选宿主已配置的下载目录（`download/paths`），也允许手填路径。
- **下载器**：从宿主已配置的下载客户端里选（`download/clients`，如 `qb` / `tr`），
  提交时写进订阅的 `downloader` 字段，宿主据此决定这条订阅下到哪个客户端。
  手填的名字若在宿主列表里不存在，配置页会给一条黄色提示——**但不会拦住保存**，
  因为下载器可以随时在宿主里改名 / 新增。
- **订阅站点**：多选站点白名单（`site/rss`），不选表示全部站点。

预订路径同样携带这三个偏好（`POST /reserve` 的 `save_path` / `downloader` / `sites`），
否则未播出的作品会被下到别的下载器里。

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

面板顶部会显示 **`待解析 N`** 徽标（`unresolved_count`），统计**还没解析出人物 ID** 的演员数；
悬停提示里会说明其中多少位仍在 24 小时冷却内（`search_cooldown_count`）。
这个数字会随解析进度**单调递减**，全部解析完即消失。

> 口径修正（v1.4.0）：早期版本把 `search_cooldown_count` 直接当作「有 24 小时搜索记录且仍在配置里的演员数」，
> **已解析出 ID、根本不会再搜的演员也被计入**，而搜索记录要满 24 小时才过期 →
> 徽标显示一个只涨不降的假数字，刷新多少次都不变。
> 现在统计与解析缓存取交集：**只有尚未解析出 ID 的演员才会被算作待解析 / 冷却中**。

`POST /clear` 会一并清空搜索记账，相当于手动放行一次重搜。

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
