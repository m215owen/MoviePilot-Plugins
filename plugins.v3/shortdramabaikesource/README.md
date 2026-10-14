# 短剧百科数据源（ShortDramaBaikeSource）

MoviePilot **V3** 插件。把「短剧百科」（`duanjubaike.org`）注册为 MoviePilot 的
**一等媒体数据源** —— 与 TMDB / 豆瓣 / Bangumi 在宿主里同级，而不是另起一套私有链路。
它自身**只提供数据与识别能力**：片名检索、详情识别、**演员档案与作品**；
发现之后要做什么（订阅、下载、整理）交给宿主或别的插件。

> **v1.0.0（首版）** —— 本插件仍在测试期，版本号定为首版，不跟随内部迭代次数往上堆。
> 当前形态：短剧百科注册为宿主一等媒体数据源，**无本地索引、无请求闸门、不注册后台任务**。
> 发现走**站外索引**（`site:<域名> <关键词>`，多引擎 ddgs，相邻两次至少隔 3 秒）；
> URL 落进**插件自有数据库**（取数库优先，命中即零引擎请求；只存 URL、页面实时解析；
> 一个页面一条记录；只有与搜索词**完全相等**的剧名才建库）；
> 解析取全量字段（评分 / 热度 / 播放 / 收藏 / 集数 / 全集时长 / 首播 / 类型 / 出品方 /
> 真人-AI 角标 / 剧照 / 演员阵容含角色 / 推荐位，演员页另有职务 / 性别 / 国籍 / 简介 /
> 全部作品 / 合作演员）；面板是 Vue 联邦前端，**一个搜索框**（片名与演员名都收，
> 一次检索出两块结果）+ URL 库查看器 + 每条结果的「原始数据」展开；
> 对外给宿主模块分发（`search_actors` / `actor_works`）与 9 条 HTTP 接口（全 `auth: "bear"`）。
> 实测驱动的三处硬约束：**地址一律归一化成 `/zh-Hans`**（否则演员作品静默解析出 0 部、
> `heat` 恒为 null）、**繁体标题候选补抓一次简体页换真标题**、**同名多版本取数据全的那条**。

## 面板：一个搜索框

插件详情弹窗（Vue 联邦组件 `./Page`）里只有一个输入框，
**片名与演员名都收** —— 一次检索同时给出两块结果，哪边命中就显示哪边（两边都命中就并排）：

| 结果块 | 链路 | 展示 |
| --- | --- | --- |
| **作品** | `GET /lookup?keyword=` 拿到作品候选（带匹配分与来源）→ 点「识别」→ `GET /recognize?media_id=` | 作品卡片：海报 / 年份 / 集数 / 全集时长 / 标签 / 评分 / **热度 / 播放 / 收藏** / 简介 / 主演 / **同页推荐**；上方是候选列表 |
| **演员** | 同一次 `/lookup` 返回的演员候选 → 点「看作品」→ `GET /actor?actor_id=` | 演员卡片（头像 / 职务 / 性别 / 国籍 / 简介 / 常合作演员）+ **全部作品墙**，每部作品一张卡 |
| **URL 库** | 搜索框那行的「URL 库」按钮 → `GET /urls` | 库容量统计 + 最近入库记录（一个页面一条，或按关键词 / 类型查），每条能直接打开站点页面；右上角「清空库」带二次确认（可整库 / 按类型 / 按关键词清） |

- 每条候选前面有两个小标：**匹配分**与**来源**（`库` = URL 库里已有、本次零引擎请求；
  `引擎` = 本次刚从搜索引擎发现并写进了库）。
- 每张卡片（作品 / 演员档案 / 作品墙里的单部作品）都有 **「原始数据」** 按钮，
  展开就是该条目**插件处理后的完整 JSON** —— 卡片是给人看的，展开是给你核对字段的。
- 每块只有 1 条候选时自动取详情，不用多点一次。
- 搜索结果里的 `media_id`（`org:<作品ID>`）可以直接喂给 `/recognize`，也就是别的插件能直接复用。

> ⚠️ **`/lookup` 必须只打一次引擎。** 片名与演员名共用同一条站外索引，而引擎侧有
> 3 秒的最小间隔 —— 分头查两次，第二次会被直接跳过，结果就是两块里**恒有一块是空的**。
> 所以后端一次检索把同一批原始结果同时抽成「作品 URL」与「演员 URL」
> （`discover.extract_urls`），两类**一起入库、一起返回**。

> ⚠️ **为什么必须用联邦前端**：宿主的 Vuetify（JSON）插件页面只支持静态组件树与
> 「点击 → 调接口」这类**无参**交互，承载不了会回传输入的搜索框 —— 实测宿主自带的
> 几十个插件里**没有一个**在 `get_page()` 里用 `VTextField`（扫描 `/app/app/plugins/*/__init__.py`
> 的 `get_page` 块，命中 0 个）。所以本插件的 `get_render_mode()` 返回 `("vue", "dist/assets")`，
> `get_form()` 只下发配置模型、`get_page()` 返回空列表。

## 核心能力

| 能力 | 宿主接口 | 说明 |
| --- | --- | --- |
| 声明数据源 | `get_media_source()` | 在识别 / 刮削 / 搜索界面的「媒体来源」里出现「短剧百科」 |
| 片名检索 | `search_medias` | 返回候选 `MediaInfo`，宿主搜索框、订阅都能用 |
| 详情识别 | `recognize_media` | 按 `media_id`（`org:<id>`）或片名取完整记录 |
| 补图 | `obtain_images` | 缺海报时按身份补抓，并把海报兜底填到背景图 |
| **演员档案** | `search_actors` / `actor_works` | 演员名 → 候选演员；演员 → **全部作品**（实测 21 部一次全渲染、不分页） |
| **URL 库** | `get_database_models()` | 插件自有数据库里存「关键词 → 页面 URL」，取数**库优先** |
| **插件面板** | `./Page` 联邦组件 | 一个搜索框 + 两块结果卡片 + URL 库查看器 + 可展开原始数据 |
| 配置页 | `./Config` 联邦组件 | 站点域名 / 站外索引 / URL 库 / 缓存等 9 项 |

统一媒体身份：

- 作品 `media_source = "duanjubaike"`，`media_id = "org:<id>"`（裸数字 ID 等价）；
- 演员 `media_id` 形如 `actor:<id>`（裸数字也接受）—— 演员**不是**媒体条目，
  这个前缀只是让调用方一眼分清「演员 ID 还是作品 ID」。

> ⚠️ ID 前缀是**白名单**：`org:` 与 `actor:` 之外的前缀（例如历史形态的
> `net:duanju:123`）一律判空，尾巴不是纯数字也判空 —— 免得拿一个不属于本站的值
> 去拼地址、白发一次必然 404 的请求。

> **本插件不提供智能体工具**（`get_agent_tools()` 与 `agenttool.py` 已删除）。
> 面板搜索框 + HTTP 接口已经覆盖同样的能力，再挂两个智能体工具只会与面板职责重复。

## 为什么需要它

短剧在 TMDB / 豆瓣上大量没有条目，宿主识别器因此建不起媒体身份（本机实例实证：
站点能搜到剧名，但宿主 `media_info` 全为 null）。本插件补的正是这一段空白。

## 检索：库优先，库空了才打引擎

取数只有一条路，但**分两级**：

1. **URL 库**（插件自有数据库，见下节）—— 拿关键词直接查
   `site_url` 表（`kind` + `keyword`，命中即用，**零引擎请求、零网络等待**）。
   查的是**宽松匹配**（`UrlStore.match`）：键 / 标题 / 触发词任一命中都算 ——
   一个页面只留一条记录，那条记录的键落在哪儿取决于它先被哪条路发现；
   三个字段都认，「库优先」才真的成立（候选的先后仍由上层打分决定，不会污染结果）。
2. **站外索引**（`web_index_search`，默认开）—— 库里没有才把
   `site:<域名> <关键词>` 交给搜索引擎（`web_index_backend`，默认 `auto`），
   把新发现的 URL 写回库，下次就从第一级命中。

引擎返回的每条结果本来就是**带完整 URL 的结构化行**（`title` / `href` / `body`，
`href` 即详情页地址），插件从 `href` 的路径里匹配 `/drama/<数字>`（作品）或
`/actor/<数字>`（演员）取出站点 ID，`discover.extract_urls` 把同一批原始结果
**一次抽成「作品 URL」与「演员 URL」两类**，两类**一起入库、一起返回**；
主机名、路径形态与 ID 都照抄引擎那行 `href`，**唯一会被改写的是语言段**（见下）。
随后详情页 / 演员页走普通 HTTP 抓（无挑战、约 2 秒、不吃站点限流）。
相邻两次引擎检索至少隔 3 秒；详情页 / 演员页结果按关键词 + TTL 缓存；
演员页 / 图集页 / 榜单页与外域结果一律剔除。

> ⚠️ **地址一律归一化成 `/zh-Hans`（`parser.canonical_page_url`），这是必须的。**
> 实测引擎会给出三种写法：`/actor/371`（无前缀）、`/zh-Hant/actor/24243`、
> `/zh-Hant/drama/22049`——**全都会被站点 301 到繁体页**，而繁体页里
> 1) 作品链接写成 `/zh-Hant/drama/…`，卡片正则只认简体前缀 ⇒ 演员的**作品静默解析出 0 部**；
> 2) 统计标签是「熱度 / 評分」，简体正则匹配不到 ⇒ **`heat` 恒为 `null`**。
> 两种症状都不报错、只在数据上留一个洞，所以抓取与入库前统统换前缀。
> 路径形态（`/drama/` 还是 `/actor/`）与 ID 仍然完全来自页面 / 引擎给的那条 URL ——
> 这不是「按 ID 反拼」，只是把一个必须成立的前提写死。

> ⚠️ **标题也跟着 URL 走：非 `/zh-Hans` 那行的标题是繁体，必要时补抓一次简体页换掉。**
> 实测同一部剧在引擎里常有简体一行（`/zh-Hans/drama/40354`，标题简体）与繁体一行
> （`/drama/40445`，标题 `相親對象是遲來的心動`）—— 繁体那行按简体关键词打分**恒为 0**，
> 会被当无关候选丢掉，于是面板上只剩一条、用户根本不知道「这部剧还有一版」（见下节）。
> 所以 `discover.extract_urls` 给每行打一个 `simplified` 标记（**按引擎给的原地址判断**，
> 不是归一化之后的），`_discover` 只对「非简体地址 **且** 与关键词字数相同」的候选补抓
> 一次简体页、用页面自己给的标题替换（简繁是逐字转写 ⇒ 同名繁体写法字数必然一样；
> 字数不同的候选为它多抓一次页面不值得）。总数封顶 `DISCOVER_TITLE_ENRICH_LIMIT = 3`，
> 顺带把详情写进 TTL 缓存 —— 之后点「识别」不再出网。

### URL 库：存 URL，不存数据

`get_database_models()` 只声明一张表（`store.SiteUrl`），落在**宿主数据库**里
（PG 下是本插件专属 schema `plugin_shortdramabaikesource`，SQLite 下是插件自己的
`plugin.db`）。表里**只有 URL 与其出处**，不缓存任何解析结果：

| 列 | 说明 |
| --- | --- |
| `kind` + `keyword` | `work` / `actor` + **这条记录自己的名字**（作品＝片名，演员＝演员名，已归一化：去空格、去书名号、全角转半角） |
| `display` | **把它带出来的那个搜索词**原文（搜片名时顺带发现的演员，这里就是那部剧的片名） |
| `label` | 展示用标题（详情页 / 演员页的标题），供 `/urls` 直接看 |
| `url` | 页面地址（入库前已把语言段归一化成 `/zh-Hans`，见上） |
| `native_id` | 站点 ID（`45982` / `371`）—— **一个页面只留一条记录** |
| `origin` / `backend` | 来自 `search` 还是 `page`（页面里读到的链接）+ 哪个检索后端 |
| `hits` / `first_seen_at` / `last_used_at` | 被用了几次、首次与最近使用时间 |

- **一个页面只留一条记录**（`UrlStore._keeper_rank`）：同一个 `native_id` 被两条发现路径
  各写一遍时自动合并，插库时合并、插件启动时再整库合并一次（日志里报「去重合并 N 条」）。
  留下的那条按类型择优 —— **演员**留「按自己的名字建档」的那条（演员页的 URL 只有按名字
  才查得回来；早先按搜索词建档时，搜一部剧顺带发现的演员全挂在片名下，同一个人还会被
  「解析作品页顺带」再写一条，面板上就是两行）；**作品**留「引擎发现」的那条（它的键就是
  用户搜的那个词，下一次搜索用的正是同一个词）。被并掉那条的 `hits` 累加到留下的记录上。
- 同一 `kind + keyword + url` **幂等**：重复入库只刷新 `label / display / native_id / backend`，
  **不清零 `hits`**；每个关键词最多留 `MAX_URLS_PER_KEYWORD` 条（按 `hits` 择优淘汰）。
- **入库是唯一写入口**，地址在这里就归一化语言段，所以**库里的 URL 一定可以直接抓**；
  万一库里还留着旧版写下的繁体 / 无前缀地址，抓取前也会再归一化一次（双保险），
  合并时也会把留下的那条的地址归一化。
- **URL 库会自己长大**（配置 `follow_links`，默认开）：解析详情页时把页面里
  演员阵容的 `actor[].url` 写进库（`kind=actor`、`keyword=演员名`、`display=作品名`），
  解析演员页时把作品墙里每个 `works[].url` 写进库（`kind=work`、`keyword=作品名`、
  `display=演员名`）。于是「搜一部剧」顺手就把它的演员索引了、搜一个演员顺手就把他的作品
  索引了 —— 下一次搜这些名字**直接命中库**。
- 面板搜索框那行的「URL 库」按钮（`GET /urls`）能看库容量统计与最近入库记录，
  也能按关键词（键 / 标题 / 命中词）与类型查；每条右侧标出「命中词」＝它是搜哪个词时
  被带出来的（键与名字不同、或命中词与名字不同时才显示）。
- 面板右上角的 **「清空库」** 按钮（`POST /urls/clear`，**二次确认**）按当前筛选决定范围：
  填了关键词就只清那个词、只选了「作品 / 演员」就清该类、都没有就**整库清空**。
  清完顺手把「最近问过引擎」的时间戳一起清掉 —— 否则刚清完再搜同一个词会被
  `SEARCH_RETRY_INTERVAL` 挡住，界面上只是「没搜到」，很容易误判成插件坏了。

> URL 一直是从结果里**直接读**出来的，不存在「把 URL 当摘要文本再拼一次」：
> `urlparse(href).path` → 正则取末尾数字就是站点 ID。v1.8.1 顺手把两处「拿 ID 反拼 URL」
> 也去掉了（演员候选、详情记录），现在只有页面**自己没声明**地址时才回落成按 ID 拼的兜底值。
> v2.0.0 只在**语言段**上做了一次归一化（理由见上），主机 / 路径 / ID 依旧照抄来源。

> `site:<域名> <关键词>` 与宿主 Agent 工具 `search_web` 的 `site_url` 参数是**同一件事**：
> `search_web` 内部也是 `_build_search_query()` 拼出 `site:<domain>` 再交给
> `ddgs.text(query, …)`。插件代码里只有 `ddgs` 这一层可用（`text()` 只收一个 query 字符串、
> 没有 `site_url` 形参），所以域名限定就写成 `site:` —— 这不是替代语法，就是它落地的那套。
> 拼接顺序不影响语义（宿主追加在末尾，本插件放在开头）。
> 两者拿到的结果也一致（同样每行带完整 URL），`site_url` 省不掉「从结果里挑出目标页」——
> 作品页 / 演员页 / 图集页 / 外域本来就混在同一批结果里。

> ⚠️ **搜索引擎的召回不稳定，且基本只认完整名字。** 实测 `女足替补的滚烫夏天` 命中 1 条、
> `女足替补` 恒 0 条，同一句话连测两次结果还会变。所以「搜不到」先怀疑关键词不完整，
> 而不是插件坏了 —— 面板会把这句话直接写进提示。

> 结果标题会带站点后缀，形如 `<标题> - <中间段> - 短剧百科`。实测出现过的中间段有
> 「短剧 / 短剧演员 / 剧照」三种（繁体对应「短劇 / 短劇演員 / 劇照」），以后还可能再加
> —— 所以**不写死枚举**：`_strip_org_suffix` 用一条通用式剥掉末尾的「`- 若干短段 - 短剧百科`」，
> 并额外剥掉有些后端挂在最后的裸域名（`魏珂 - 短劇演員 - 短劇百科 - duanjubaike.org`）；
> 两类后缀**交替剥到不变**（顺序不固定）。剥净后的标题才是候选标签，也才能参与打分。
> ⚠️ 必须有前置分隔符才剥 —— 「重生之短剧百科」这种正常片名不该被动。

### 同名多版本：站点会给同一部剧建两条记录

实测 `2026-10-15`：`/zh-Hans/drama/40445` 与 `/zh-Hans/drama/40354` 的**标题、简介、
首播日期一字不差**，但

| | `/drama/40445` | `/drama/40354` |
| --- | --- | --- |
| `kind`（h1 角标） | **真人短剧** | **AI短剧** |
| 集数 / 时长 | 74 集 / 152 分钟 | 无 |
| 出品方 | 网易羚羊 | 无 |
| 演员 | 黄云云、李卓扬 | **无** |
| 热度 / 播放 | 376 万 / 975 | 无 |

两个页面**互不引用**（`同系列短剧 / 同IP短剧 / 同小说短剧` 三个区块在两页都是空注释），
站点也不提供任何「谁是正版」的标注。所以插件按两条规矩处理：

1. **并列时取「数据全」的那条**（`_fetch_best_detail` + `_richness`）：按片名打分并列的候选
   会逐条抓下来比字段完整度（权重：演员 4 > 集数 ≈ 时长 2 > 其余 1），取更全的那条 ——
   否则识别会认到 AI 版那条**没有演员、没有集数**的空壳上。同名并列最多多抓 1 条，
   且第二条会进 TTL 缓存。宿主搜索列表（`search_medias`）也按同样规则把更全的排前面。
2. **候选上标出「同名 N 版」**：`/lookup` 的候选带 `same_title`（仅当 >1 时出现），
   面板渲染成橙色小标 —— 否则用户看着两条一模一样的标题，无从判断该点哪一条。

> ⚠️ 别把这一步做成「按 `kind` 硬选真人短剧」：站点上的 AI 短剧也有**只此一条**的时候，
> 按数据完整度择优是客观判据，按类型筛则是猜测用户意图。

> v1.8.0 之前还有一级「榜单快照」（本地缓存，零请求）。它随宿主探索页一起删除了：
> 榜单页只有「标题 + 海报 + 集数」，为它维持一份持久化快照与一个定时任务不划算。

### 为什么不用站内检索

`/zh-Hans/drama/search` 是 **Cloudflare 托管挑战**（`cType=managed` + Turnstile）。
2026-10-15 在 NAS 上把所有能试的都试过了：

| 手段 | 结果 |
| --- | --- |
| 普通 HTTP（全套 `sec-ch-ua` / `Sec-Fetch-*`、`Referer`、预热 cookie、走宿主代理、`curl_cffi` 指纹） | 恒 403 |
| 宿主浏览器仿真 **无头**（`cloakbrowser`，站点「浏览器仿真」的实现） | 等 87 秒仍是 `Just a moment...` |
| 宿主浏览器仿真 **有头**（虚拟显示 + `humanize` + `zh-CN`/`Asia/Shanghai`） | 等 105 秒仍是挑战页，`cf_clearance` 一个都没落下 |

挑战页自述「验证成功，正在等待响应」，但浏览器始终拿不到放行 cookie ⇒ **这条路不通**。
相关代码与开关（原 `use_browser_search`）已删除，改走上面的站外索引。

## 演员数据

演员名 → 演员 ID **先查 URL 库**（库里没有才走 `site:<域名> <演员名>` → 结果里的
`/actor/<id>`，并把新 URL 写回库），拿到 ID 后抓演员页并**复用作品卡片解析器**取出全部作品。

```python
actors = self.run_module("search_actors", name="魏依珂")   # → [{"actor_id","name","media_id","url","source"}, …] 按名字打分排序
works  = self.run_module("actor_works", actor_id="371")    # → 该演员的全部作品（作品卡片字段）
works  = self.run_module("actor_works", name="魏依珂")      # 名字也可以，内部先解析成 ID
```

`search_actors` **只出候选、不抓演员页**（候选里带 `url` 与 `source`，`source` 标明
`from` 是 `库` 还是 `引擎`）；要看作品用 `actor_works`。

`actor_works` 回的是**作品卡片**字段（与 `parse_org_cards` 一致，实测 21 部作品里的分布）：
`media_id` / `native_id` / `title` / `poster` / `url` / `kind` / `heat` / `play_count` 每条都有，
`episode_count`（20/21）、`tags`（19/21）、`rating`（19/21）部分有，`badge` 少见。
**热度（`heat`）与播放量（`play_count`）是 v2.0.0 新增解析的**，此前只解析了片名/海报/集数这几种。

演员档案（`build_public_actor`，即 `/actor` 的 `actor` 载荷）形状 —— 下面是真机返回的字段：

```json
{
  "success": true, "message": "",
  "actor": {
    "actor_id": "371", "media_id": "actor:371", "name": "魏依珂",
    "job_title": "短剧演员", "gender": "Female", "nationality": "中国",
    "profile": "https://cdn.duanjubaike.org/avatar/2026/07/…jpg",
    "bio": "魏依珂，中国内地女演员。代表作《一眼见到你》、《将心锁玉》等。",
    "url": "https://duanjubaike.org/zh-Hans/actor/371",
    "works": [
      {"media_id": "org:45982", "native_id": "45982", "title": "女足替补的滚烫夏天",
       "poster": "https://cdn.duanjubaike.org/cover/2026/09/…jpg?width=400",
       "url": "https://duanjubaike.org/zh-Hans/drama/45982", "kind": "真人短剧",
       "episode_count": 41, "tags": ["逆袭"], "heat": 3540000.0, "play_count": 996.0}
    ],
    "works_count": 21,
    "coactors": [{"id": "2121", "name": "王石", "profile_path": "https://cdn.duanjubaike.org/avatar/2026/05/…jpg"}]
  }
}
```

> `job_title`（职务）/ `gender`（性别）/ `nationality`（国籍）都是 v2.0.0 新增解析的
> —— 来自演员页 JSON-LD `Person`，缺失时再用「基本信息」区块的 `dt/dd` 兜底。
> 内部解析结果（`parse_org_actor`）里另有 `works_count` 与 `coactors_count` 两个计数；
> 对外载荷的 `works_count` 是**按实际上榜作品数重算**的（`build_public_actor`），
> 所以它与页面顶部那个「21」可能不完全相等。

> 合作演员来自演员页的「合作演员」区，字段是 ``id`` / ``name`` / ``profile_path``；
> 作品页阵容里的同名字段另带 ``character`` / ``kind``（饰谁、主演还是配角）。
> 这是**两处不同来源的字段名**，不要互相套用 —— 套错会把内容整条清空、只剩 ``name``。

> ⚠️ **演员页必须抓 `/zh-Hans`。** 不带会被 301 到 `/zh-Hant`，页面内的作品链接随之变成
> `/zh-Hant/drama/<id>`，而卡片正则只认 `/zh-Hans/drama/` ⇒ 结果是**资料字段照常正确、
> 作品静默解析出 0 部**（极难发现）。v2.0.0 起由 `parser.canonical_page_url` 在
> 入库与抓取两处统一保证（详见上文「检索」一节）。

搜索引擎结果里会混入模糊匹配（搜「王石」会带出「王碩」），所以候选一律按名字打分排序后返回。

## 「点开作品」后的详情页能显示什么（重要）

从宿主的搜索框 / 媒体页点开一部作品，前端会跳到
`/media?media_source=duanjubaike&media_id=org:<id>`，
再由宿主调 `GET /api/v1/media/{media_id}?media_source=…&type_name=…` →
`recognize_media` 取数。**宿主前端对自定义来源是有结构性限制的**（v3.1.5 实测）：

| 详情页区块 | 渲染条件 | 本插件 |
| --- | --- | --- |
| 海报 / 背景图 / 标题 / 年份 | 无条件 | ✅ |
| 时长 + **类型标签**（`289 分钟 \| 东方仙侠、玄幻脑洞`） | 无条件（读 `runtime` + `genres`） | ✅ |
| **简介** | 无条件 | ✅ |
| **评分（星条）**、TMDB/豆瓣 ID、出品方、状态 | 仅当媒体有 `tmdb_id` | ❌ 结构上不渲染 |
| 评分 / 豆瓣 ID | 仅当有 `douban_id` | ❌ 同上 |
| 评分 / 来源 ID | 仅当有 `bangumi_id` / `anilist_id` | ❌ 同上 |
| **演职员**（`tmdb/credits/{id}` 等列表） | 同上，三选一 | ❌ 同上 |
| 分季分集、剧照、推荐 | 同上（TMDB 专有数据） | ❌ 同上 |

也就是说：**评分区与演职员区是前端按 TMDB / 豆瓣 / Bangumi 三个来源硬编码的**，
自定义来源拿不到这两个位置 —— 这不是插件能通过字段补上的缺口（试图伪造 `tmdb_id`
只会把页面连到 TMDB 上另一部剧）。v2.0~v2.1 曾把「评分 · 全 N 集 · 主演…」写进
`tagline`（简介上方那行摘要）作补偿，**v2.2.1 起按用户要求整体移除**：`tagline`
一律不写，详情页只保留标题与简介。完整的「评分 / 演员 / 剧照」字段一直都在
`recognize_media()` / `/actor` 的返回值里，面板的「原始数据」与其它插件都可以照常取用。

## 供其它插件调用

两条通道，内部共用同一套实现（`_resolve` / `_resolve_item` / `actor_profile` / `_fetch_detail`
/ `_fetch_actor`，数据统一从 URL 库出发）。

### 1. 宿主模块分发（首选，进程内、零序列化）

宿主的分发器同时挂了模块目录与**插件目录**
（`app/chain/base.py`：`module_dispatcher_factory(module_catalog=self.modulemanager,
plugin_catalog=self.pluginmanager, …)`），而每个插件都是 `ChainBase` 子类，所以直接：

```python
# 在另一个插件里（self 是任意插件实例 / 任意 Chain）
infos  = self.run_module("search_medias", meta=meta, media_source="duanjubaike")
info   = self.run_module("recognize_media", media_source="duanjubaike", media_id="org:40105")
img    = self.run_module("obtain_images", mediainfo=info)
actors = self.run_module("search_actors", name="魏依珂")
works  = self.run_module("actor_works", actor_id="371")
```

`media_source` 写 `duanjubaike` / `shortdramabaike` / `shortdramabaikesource` 任一都能命中
（见 `MEDIA_SOURCE_ALIASES`）。作品类方法返回宿主 `MediaInfo`。

`search_actors` / `actor_works` 是**自定义模块方法名**（不在宿主 `module_method` 合同里）。
宿主对未登记的名字走 legacy 契约（`public_to_plugins=True`，聚合 = 有序列表合并），
且分发器按 `plugin.get_module()[method]` 取函数、**没有该方法名的插件会被跳过** ⇒
新增自定义名不会影响别的插件。两个方法都**返回列表**（legacy 聚合对列表做 `extend`）。

### 2. HTTP 纯 JSON 出口（面板与外部脚本共用）

```bash
# 面板用登录态调，脚本用 X-API-KEY 调 —— 同一批接口，鉴权声明是 auth: "bear"
GET  /api/v1/plugin/ShortDramaBaikeSource/recognize?media_id=org:40105
GET  /api/v1/plugin/ShortDramaBaikeSource/recognize?keyword=万妖图录传&year=2026
GET  /api/v1/plugin/ShortDramaBaikeSource/actor?actor_id=371
GET  /api/v1/plugin/ShortDramaBaikeSource/actor?name=魏依珂
GET  /api/v1/plugin/ShortDramaBaikeSource/lookup?keyword=魏依珂
GET  /api/v1/plugin/ShortDramaBaikeSource/urls?keyword=魏依珂&kind=actor
```

> ⚠️ 全部接口声明 `auth: "bear"`，宿主把它映射成 `verify_token` —— 那个依赖
> **同时接受 JWT（浏览器登录态）与 `X-API-KEY`**，所以面板与脚本可以共用同一套接口，
> 不必开两套。用 `X-API-KEY` 调时注意 `/config` 也是同样的鉴权。

响应形状固定且只含标量（`build_public_record` / `build_public_actor`），
不会被 `MediaInfo` 的字段版本绑住：

```json
{
  "success": true,
  "record": {
    "media_source": "duanjubaike", "origin": "detail",
    "media_id": "org:61818", "native_id": "61818",
    "title": "养了十二年的石头会喊爸了", "year": "2026",
    "poster": "https://cdn.duanjubaike.org/cover/…jpg?width=400",
    "episode_count": 106, "duration_minutes": 121,
    "tags": ["都市脑洞", "家庭", "女频衍生", "喜剧"],
    "kind": "真人短剧", "in_language": "zh-Hans",
    "heat": 3540000, "play_count": 996,
    "url": "https://duanjubaike.org/zh-Hans/drama/61818",
    "actors": [{"id": "2014", "name": "刘清心", "character": "苏晚", "profile_path": "…", "kind": "主演"}],
    "related": [{"media_id": "org:53935", "title": "东家落难，保姆王妈救场翻盘", "kind": "AI短剧",
                 "episode_count": 50, "heat": 40710000, "rating": "8.1"}]
  }
}
```

`origin` 说明数据来自 `detail`（详情页，字段全）还是 `search`（详情页没抓到，退回检索结果，
只有 ID 与片名，其余字段为空）。`related` 是详情页「推荐短剧」区块的同页关联作品
（口径与本记录一致，最多 `MAX_RELATED = 10` 条）。

`/lookup` 是面板搜索框的后端，回的是**两块候选**（都不是完整记录，取第一条再喂
`/recognize` 或 `/actor`）：

```json
{
  "success": true, "message": "", "keyword": "魏依珂", "year": "",
  "titles": [{"media_id": "org:45982", "native_id": "45982", "title": "女足替补的滚烫夏天",
              "url": "https://duanjubaike.org/zh-Hans/drama/45982", "from": "库", "score": 100}],
  "actors": [{"actor_id": "371", "media_id": "actor:371", "name": "魏依珂",
              "url": "https://duanjubaike.org/zh-Hans/actor/371", "from": "库", "score": 100}]
}
```

- `from` 是候选的**来源标**：`库`（URL 库里已有，本次零引擎请求）或 `引擎`
  （本次刚发现并已入库）。候选里带 `url`，面板上能直接「打开站点」核对。
- `same_title` 只在**同名多条**时出现（值 = 同名条数），面板渲染成「同名 N 版」小标 ——
  站点会给同一部剧建多条记录（真人版 / AI 版标题一字不差），详见上文「同名多版本」。
- `score <= 0` 的候选（字面对不上关键词，只被引擎模糊召回带来的）直接丢弃，
  不占面板位置。

搜「完全不存在的东西」时 `success=false`，`message` 是一句可照着做的提示
（并会区分「站外索引关着」/「宿主没有 `ddgs`」/「关键词不完整」三种原因）。

## 站点能力边界（实测）

| 路径 | 能力 |
| --- | --- |
| `/zh-Hans/drama/{id}` | 详情页：JSON-LD（`TVSeries` + `PerformanceRole` 演员）+ HTML（演员阵容含**角色名与主/配角**、剧照、**热度 / 播放 / 收藏**、集数/时长/首播时间/出品方/语言/真人-AI 角标、**「推荐短剧」区块**）。**最可靠的一条路** |
| `/zh-Hans/actor/{id}` | 演员页：JSON-LD `Person`（姓名/简介/头像/**职务/性别/国籍**）+ 作品网格（实测一次全渲染、不分页，演员 371 为 21 部）+ **合作演员区**。⚠️ 必须带 `/zh-Hans` 前缀 |
| `/zh-Hans/top/{key}` | 17 个榜单页：**本插件不再使用**（只为曾经的探索页来源而抓）；实测 `search` 榜恒 403、`celebrity` 榜里没有作品链接 |
| `/zh-Hans/drama/search` | 站内检索：Cloudflare **托管挑战**，服务端恒 403 ⇒ **已弃用** |
| `/zh-Hans/drama/list` | 全量目录页（约 1879 页 / 5.6 万部）：**本插件不再使用** |
| `robots.txt` | `Disallow` 全部 `/search`（drama/actor/director/writer/producer）与 `/auth` |

## 限流：只有「目录页」一条路径有限制，而插件已经不用它

2026-10-14 在 NAS 与电信出口上做了多组对照：

| 路径 | 稠密连打 | 结论 |
| --- | --- | --- |
| `/zh-Hans/drama/list?page=N` | **第 6 次即 403**（正文 `Just a moment...`） | 有独立突发限流 |
| `/zh-Hans/top/{key}`、`/zh-Hans/drama/{id}`、`/zh-Hans/actor/{id}`、`/zh-Hans` | 0.3s × 20 次 **全 200** | 不受限 |

这条目录页限流**与客户端无关**（换出口 IP、`curl_cffi` 冒充 TLS 指纹、全套现代浏览器头、
真 Chromium 整页导航与页面内 `fetch`、撞墙后等挑战自动解开，全部无效）⇒ 是按 IP + 路径计的硬限流。

**目录页退出使用范围后，闸门失去存在理由，因此 v1.6.0 把请求闸门（额度窗口 / 最小间隔 /
撞 403 冷却）整体删除。** 现在 `_request` 就是一次裸 GET，撞到 403 的后果仅仅是当次拿不到
数据 —— 不写任何跨请求状态，识别与别的插件调用不会被「冻结」。

## 建库门槛：只有**完全匹配**的剧名才建库（v2.1.1）

曾经有个很误导人的现象：日志写「`相亲对象是迟来的心动` URL 库命中：作品 5」，
可打开 URL 库一看，那 5 行的片名是「深渊之花」「照片是舍友，網戀對象是繼承人」
「穿成炮灰後…」等**毫不相干**的剧。

原因是：**搜索引擎的召回不稳定**（`site:` 限定检索会返回同一站内不相干的页），而 v2.0.0
把搜到的作品**一律按「用户搜的那个词」建档** —— 于是攒下一批「键是这个搜索词、内容却是
别的剧」的错行，下次搜同一个词报「库命中 5」，其实一条都对不上。

现在的口径：

| 结果 | 是否返回给面板 | 是否建库 |
| --- | --- | --- |
| 标题与搜索词**完全相等** | ✅ | ✅ 按**它自己的片名**建档，触发词记在 `display` |
| 只是字面**沾边**（包含关系，如搜「万妖图录传」得到「万妖图录传第七季」） | ✅（由上层按片名打分排序） | ❌ |
| 标题与搜索词**毫不相干** | ✅（面板那一步会被剔除） | ❌ |

**宁可漏，不可错** —— 漏了下回再搜一次就补上；错了会一直污染库。
启动时还会顺手清掉**已经存下来**的历史错行（片名与它的键、与触发它的搜索词都不相等的
作品行），日志里记一条「URL 库清理错行：删除 N 条」。

⚠️ 演员**不受**这条门槛限制：它按自己的名字建档，搜一部剧时顺带发现的演员正是
「URL 会自己长大」的来源，不会污染库。

## 排障看日志：哪些情况会留下痕迹（v2.1.1）

本插件的好几类故障都是**静默**的 —— 界面上统一表现为「没搜到」，只有日志能区分。
日志落在插件自己的日志文件里（`插件 → 短剧百科数据源 → 日志`）。

> ⚠️ 宿主默认 `LOG_LEVEL='INFO'`、``DEBUG='False'`` ⇒ **DEBUG 级的追踪日志不会落盘**。
> 想看更细的每一步（缓存命中、解析摘要、入库整理），把宿主的 `LOG_LEVEL` 调到 `DEBUG`。
> 下面标「INFO」的都是默认级别下就能看到的。

| 级别 | 什么时候 | 为什么要记 |
| --- | --- | --- |
| WARNING | 演员页解析出 **0 部作品** | 本插件**最难发现**的故障：资料字段全对、只有作品为空。真因几乎总是抓到了繁体页（日志里会点明检查 `/zh-Hans` 前缀） |
| WARNING | 搜索引擎**报错** | 以前被静默吞掉。实测 `google` 后端恒抛 `DDGSException: No results found`，界面上只显示「没搜到」；日志里带上**后端名**，照着去面板换 `auto` / `yandex` |
| WARNING | 宿主环境缺 `ddgs` | 环境级问题（只报一次，不刷屏）：此时片名与演员名都发现不了新 URL，只能用库里已有的 |
| WARNING | URL **入库失败** | 静默降级：本次结果照常返回，只是下次还得再问一次引擎，容易被误判成「引擎召回时好时坏」 |
| WARNING | 详情页解析不出标题 / 页面撞 Cloudflare 风控 | 站点改版或风控收紧，默认级别下必须看得见 |
| WARNING | 手动清库 | 破坏性操作，记下范围与条数 |
| INFO | 启动 / 停止 / 配置保存 | 启动时给出域名、后端、URL 库容量、顺带入库开关、缓存时长 |
| INFO | **库命中**（零引擎请求） | 证实「库优先」真的生效了 |
| INFO | **本次不问引擎**及真实原因 | 「开关关着」「环境缺依赖」「Ns 前刚查过」三者表现一样（都是没结果），必须分开 |
| INFO | 引擎返回结果条数与分类 | 结果里混着图集页 / 榜单页 / 外域地址，「返回 10 条、能用 3 条」要看得见 |
| INFO | 本次**有几部与搜索词完全匹配**并入库 | 区分「搜到了 N 部」与「其中 M 部真的对得上、进了库」 |
| INFO | 启动时清理错行的条数 | 见上方「建库门槛」一节 |
| INFO | 候选标题**补抓简体页后替换** | 繁体那行按简体关键词打分恒为 0，换了才知道它其实命中了 |
| INFO | 检索命中条数、面板 0 命中的原因 | 界面只给一句提示，原因留在日志里 |
| DEBUG | 缓存命中、作品/演员解析摘要、入库整理、识别与检索的逐条结果 | 逐条追踪，默认不落盘（见上方警告） |

## HTTP 接口

挂载在 `/api/v1/plugin/ShortDramaBaikeSource/`（全部 `auth: "bear"`）。

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/recognize` | **作品出口**：`media_id` 或 `keyword`(+`year`) → 纯 JSON 作品记录 |
| GET | `/actor` | **演员出口**：`actor_id` 或 `name` → 纯 JSON 演员档案（含全部作品与合作演员） |
| GET | `/lookup` | 一个 `keyword` 同时找作品与演员（面板唯一那个搜索框用它） |
| GET | `/urls` | **URL 库出口**：无参回库容量统计 + 最近入库记录；带 `keyword` / `kind` / `limit` 查 |
| POST | `/urls/clear` | **清空 URL 库**（面板「清空库」按钮）：`{"kind": "actor"}` 清该类全部、`{"keyword": "某剧"}` 清该词、空对象＝整库清空 |
| GET | `/status` | 运行情况：域名 / 站外索引配置 / 缓存条数 / **URL 库统计**（面板顶部 chip 与配置页读它） |
| GET | `/config` | 读当前配置 + 候选值（面板配置页回显） |
| PUT | `/config` | 存配置（逐键合并 + 归一化后落盘，并重建运行状态） |
| GET | `/probe` | 连通性自检：robots / 站外索引 / 详情页 / 演员页各自的状态码与解析条数 |

> 接口一共 9 条。`/urls` 是 v2.0.0 新增的、`/urls/clear` 是 v2.1.0 新增的；
> 旧的 `/search`、`/actor_search` 已并入 `/lookup`，`/explore` 随宿主探索页一起删除
> —— 那都是 v1.8.0 的事。

`/urls` 的样子（无参 = 统计 + 最近 50 条）：

```json
{
  "success": true,
  "stats": {"total": 3, "work": 2, "actor": 1, "keywords": 2, "last_seen_at": 1760533451},
  "records": [
    {"kind": "work", "keyword": "女足替补的滚烫夏天", "display": "女足替补的滚烫夏天",
     "label": "女足替补的滚烫夏天", "url": "https://duanjubaike.org/zh-Hans/drama/45982",
     "native_id": "45982", "origin": "search", "backend": "duckduckgo",
     "hits": 2, "first_seen_at": 1760533400, "last_used_at": 1760533451}
  ]
}
```

> 时间戳是 **epoch 秒**（整数），面板负责转成人看的格式；`origin` 是 `search`
> （引擎发现）或 `page`（页面里顺带读到、`follow_links` 的产物）。
> 无参调 `/urls` 时 `records` 是最近 50 条；带 `keyword` 时是**该关键词的全部记录**
> （键 / 标题 / 命中词任一命中，`kind` 留空则作品与演员都查）。

`/urls/clear` 的样子：

```json
// POST {"kind": "actor"} →
{"success": true, "message": "已清空 类型 actor，删除 12 条", "removed": 12,
 "scope": "类型 actor", "stats": {"total": 8, "work": 8, "actor": 0, "keywords": 8, "last_seen_at": 1760533451}}
```

> ⚠️ 破坏性接口不猜参数：`kind` 只能是 `work` / `actor`，请求体不是 JSON 对象就直接报错，
> 不会退化成「整库清空」。空对象（或不带 body）才是整库清空 —— 面板上走二次确认。

## 数据来源与合规

- 站点：`duanjubaike.org`（可在面板设置里改域）。
- **不抓** `/zh-Hans/drama/search` 与 `/auth`（`robots.txt` 明确 `Disallow`）。
- 不建立本地全量索引、不批量扫目录页 —— 只按需抓取用户实际要看的那几部作品与演员。
- URL 库里存的**只是「关键词 → 页面 URL」**（外加出处与命中次数，**一个页面一条**），
  **不存任何解析后的作品 / 演员数据**，也不预扫站点。库只会随用户自己的查询（以及
  `follow_links` 顺带发现的同页链接）自然增长，每关键词上限 `MAX_URLS_PER_KEYWORD` 条；
  面板上的「清空库」可以随时把库按范围删干净。

## 主要配置

面板的「设置」按钮打开配置页（联邦组件 `./Config`）。

| 配置 | 默认 | 说明 |
| --- | --- | --- |
| `enabled` | 关 | 启用插件 |
| `search_in_global` | 开 | 参与宿主的全局检索（未限定来源时） |
| `domain` | `duanjubaike.org` | 站点域名 |
| `timeout` | 15 | 单次请求超时（秒） |
| `cache_ttl` | 604800 | 详情页缓存（秒，默认 7 天） |
| `web_index_search` | 开 | **站外索引检索**：库里没有时才 `site:` 限定检索片名 / 演员名，从收录的 URL 取 ID |
| `web_index_backend` | `auto` | 检索后端（`auto` / `duckduckgo` / `yandex` / `google` / `brave` / `mojeek`） |
| `follow_links` | 开 | **URL 库自己长大**：解析详情页 / 演员页时顺手把页面里的演员 URL、作品 URL 也入库 |
| `proxy` | 关 | 出站请求是否走系统代理 |

共 9 项（v2.2.1 删掉了 `detail_facts` 摘要行开关；v2.0.0 新增 `follow_links`；v1.8.0 删掉了榜单范围、榜单刷新间隔、探索页详情回填三项）。
保存是**逐键合并**的：payload 里缺的键沿用当前生效值，只翻一个开关不会把其它配置冲回默认。

> **没有后台任务。** `get_service()` 恒返回空列表 —— 没有榜单要刷、没有索引要建，
> URL 库只在被查询时被动增长，缓存只在被查询时按需重建。配置页底部会显示一行运行实况
> （启用状态 / 站外索引开关与后端 / 缓存条数 / **URL 库条数（作品 x / 演员 y）**），
> 直接读 `GET /status`。

## 前端工程（维护用）

`src/` 是 Vite 模块联邦工程，产物在 `dist/assets/`（`remoteEntry.js` +
`__federation_expose_Page-*.js` / `__federation_expose_Config-*.js`）。
**运行时只认 `dist/assets`，源码不参与运行。**

```bash
# 依赖目录复用同级插件的 node_modules（软链），改完源码后重新构建
node node_modules/vite/bin/vite.js build
```

暴露的组件只有两个：`./Page`（详情弹窗）与 `./Config`（配置页）。
新增组件要同时改 `vite.config.ts` 的 `exposes` 与本地文件。

⚠️ **前端引用了后端已经删掉的配置键 / 接口时不会报错**，只会静默留一块空面板 ——
所以测试里按字符串兜了一道：`test_frontend_no_longer_mentions_removed_features`
会扫 `src/` 下四个文件，出现 `top_keys` / `explore_detail_fetch` / `top_lists` /
`top_snapshot` / `actor_search` 之类已删符号就直接失败。

> 另外一个容易踩的坑（v1.7.1 修过）：**`v-select` 传对象数组时必须显式写 `item-title` /
> `item-value`**。宿主的 Vuetify 默认按 `title` 取显示文本，后端若下发 `{value, label}`
> 就会把整个对象当标题渲染出来。现在配置页的 `web_index_backends` 是**字符串数组**，
> 不受影响 —— 但以后再加对象型下拉时要记得写。
