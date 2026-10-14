# 短剧百科数据源（ShortDramaBaikeSource）

MoviePilot **V3** 插件。把「短剧百科」（`duanjubaike.org`）注册为 MoviePilot 的
**一等媒体数据源** —— 与 TMDB / 豆瓣 / Bangumi 在宿主里同级，而不是另起一套私有链路。
它自身**只提供数据与识别能力**：片名检索、详情识别、**演员档案与作品**；
发现之后要做什么（订阅、下载、整理）交给宿主或别的插件。

> **v1.6.0**：删除全部索引功能与请求闸门，检索改为按需走站外索引。
> **v1.7.0**：面板改成 **Vue 联邦前端**（有搜索框才能收输入），**删除两个智能体工具**。
> **v1.7.1**：修「设置与探索页对不上」。
> **v1.8.0**：删掉「榜单快照」与「宿主探索页」两条线，插件不再注册任何后台任务；
> 面板从两个搜索框合并成**一个**（片名与演员名都收，`GET /lookup` 一次检索两边出结果）。

## 面板：一个搜索框

插件详情弹窗（Vue 联邦组件 `./Page`）里只有一个输入框，
**片名与演员名都收** —— 一次检索同时给出两块结果，哪边命中就显示哪边（两边都命中就并排）：

| 结果块 | 链路 | 展示 |
| --- | --- | --- |
| **作品** | `GET /lookup?keyword=` 拿到作品候选（带匹配分）→ 点「识别」→ `GET /recognize?media_id=` | 作品卡片：海报 / 年份 / 集数 / 单集时长 / 标签 / 评分 / 简介 / 主演；上方是候选列表 |
| **演员** | 同一次 `/lookup` 返回的演员候选 → 点「看作品」→ `GET /actor?actor_id=` | 演员卡片（头像 / 职务 / 性别 / 国籍 / 简介 / 常合作演员）+ **全部作品墙**，每部作品一张卡 |

- 每张卡片（作品 / 演员档案 / 作品墙里的单部作品）都有 **「原始数据」** 按钮，
  展开就是该条目**插件处理后的完整 JSON** —— 卡片是给人看的，展开是给你核对字段的。
- 每块只有 1 条候选时自动取详情，不用多点一次。
- 搜索结果里的 `media_id`（`org:<作品ID>`）可以直接喂给 `/recognize`，也就是别的插件能直接复用。

> ⚠️ **`/lookup` 必须只打一次引擎。** 片名与演员名共用同一条站外索引，而引擎侧有
> 3 秒的最小间隔 —— 分头查两次，第二次会被直接跳过，结果就是两块里**恒有一块是空的**。
> 所以后端一次检索把同一批原始结果分别喂给「作品解析」与「演员解析」
> （`_search_via_web_index(query, rows)` / `_search_actors_via_web_index(query, rows)`）。

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
| **演员档案** | `search_actors` / `actor_works` | 演员名 → 候选演员；演员 → **全部作品**（实测 59 部一次全渲染、不分页） |
| **插件面板** | `./Page` 联邦组件 | 一个搜索框 + 两块结果卡片 + 可展开原始数据 |
| 配置页 | `./Config` 联邦组件 | 站点域名 / 站外索引 / 缓存等 9 项 |

统一媒体身份：

- 作品 `media_source = "duanjubaike"`，`media_id = "org:<id>"`（裸数字 ID 等价）；
- 演员 `media_id` 形如 `actor:<id>`（裸数字也接受）—— 演员**不是**媒体条目，
  这个前缀只是让调用方一眼分清「演员 ID 还是作品 ID」。

> **本插件不提供智能体工具**（`get_agent_tools()` 与 `agenttool.py` 已删除）。
> 面板搜索框 + HTTP 接口已经覆盖同样的能力，再挂两个智能体工具只会与面板职责重复。

## 为什么需要它

短剧在 TMDB / 豆瓣上大量没有条目，宿主识别器因此建不起媒体身份（本机实例实证：
站点能搜到剧名，但宿主 `media_info` 全为 null）。本插件补的正是这一段空白。

## 检索：只有一条路（站外索引）

`web_index_search`（默认开）：把 `site:<域名> <关键词>` 交给搜索引擎
（`web_index_backend`，默认 `auto`），从**已收录的 URL** 里取出数字 ID ——
`/drama/<数字>` 是作品、`/actor/<数字>` 是演员，两条解析路吃同一批原始结果。
随后详情页 / 演员页走普通 HTTP 抓（无挑战、约 2 秒、不吃站点限流）。
相邻两次检索至少隔 3 秒；结果按关键词缓存；演员页 / 图集页 / 榜单页与外域结果一律剔除。

> `site:<域名> <关键词>` 与宿主 Agent 工具 `search_web` 的 `site_url` 参数是**同一件事**：
> `search_web` 内部也是 `_build_search_query()` 拼出 `site:<domain>` 再交给
> `ddgs.text(query, …)`。插件代码里只有 `ddgs` 这一层可用（`text()` 只收一个 query 字符串、
> 没有 `site_url` 形参），所以域名限定就写成 `site:` —— 这不是替代语法，就是它落地的那套。
> 拼接顺序不影响语义（宿主追加在末尾，本插件放在开头）。

> ⚠️ **搜索引擎的召回不稳定，且基本只认完整名字。** 实测 `女足替补的滚烫夏天` 命中 1 条、
> `女足替补` 恒 0 条，同一句话连测两次结果还会变。所以「搜不到」先怀疑关键词不完整，
> 而不是插件坏了 —— 面板会把这句话直接写进提示。

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

演员名 → 演员 ID 走同一条站外索引（`site:<域名> <演员名>` → 结果里的 `/actor/<id>`），
拿到 ID 后抓演员页并**复用作品卡片解析器**取出全部作品。

```python
actors = self.run_module("search_actors", name="魏依珂")   # → [{"actor_id","name","media_id","url","source"}, …] 按名字打分排序
works  = self.run_module("actor_works", actor_id="371")    # → 该演员的全部作品（作品卡片字段）
works  = self.run_module("actor_works", name="魏依珂")      # 名字也可以，内部先解析成 ID
```

`actor_works` 回的是**作品卡片**字段（与 `parse_org_cards` 一致，实测 21 部作品里的分布）：
`media_id` / `native_id` / `title` / `poster` / `url` / `kind` / `heat` / `play_count` 每条都有，
`episode_count`（20/21）、`tags`（19/21）、`rating`（19/21）部分有，`badge` 少见。

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

> 合作演员来自演员页的「合作演员」区，字段是 ``id`` / ``name`` / ``profile_path``；
> 作品页阵容里的同名字段另带 ``character`` / ``kind``（饰谁、主演还是配角）。
> 这是**两处不同来源的字段名**，不要互相套用 —— 套错会把内容整条清空、只剩 ``name``。

> ⚠️ **演员页 URL 必须显式带 `/zh-Hans` 前缀。** 不带会被 301 到 `/zh-Hant`，
> 页面内的作品链接随之变成 `/zh-Hant/drama/<id>`，而卡片正则只认 `/zh-Hans/drama/` ⇒
> 结果是**资料字段照常正确、作品静默解析出 0 部**（极难发现）。插件已固定写死前缀。

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
只会把页面连到 TMDB 上另一部剧）。插件因此走了一个折中：

- **详情页摘要行**（配置 `detail_facts`，默认开）：把「评分 · 全 N 集 · 主演 X、Y」
  写进 `tagline` —— 这是整页里唯一能给自定义来源承载这类信息的自由文本位
  （渲染在「简介」标题正上方）。关掉它即可让详情页完全回到宿主默认样貌。
- 完整的「评分 / 演员 / 剧照」字段一直都在 `recognize_media()` / `/actor` 的返回值里，
  面板的「原始数据」与其它插件都可以照常取用。

## 供其它插件调用

两条通道，内部共用同一套实现（`_resolve_item` / `_search_by_title` / `_fetch_detail`
/ `_fetch_actor`）。

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
    "url": "https://duanjubaike.org/zh-Hans/drama/61818",
    "actors": [{"id": "2014", "name": "刘清心", "character": "苏晚", "profile_path": "…", "kind": "主演"}]
  }
}
```

`origin` 说明数据来自 `detail`（详情页，字段全）还是 `search`（仅检索结果，字段少）。

`/lookup` 是面板搜索框的后端，回的是**两块候选**（都不是完整记录，取第一条再喂
`/recognize` 或 `/actor`）：

```json
{
  "success": true, "message": "", "keyword": "魏依珂",
  "titles": [{"media_id": "org:45982", "title": "女足替补的滚烫夏天", "score": 100, "poster": null, "episode_count": null}],
  "actors": [{"actor_id": "371", "media_id": "actor:371", "name": "魏依珂", "score": 100}]
}
```

搜「完全不存在的东西」时 `success=false`，`message` 是一句可照着做的提示（换成完整片名 / 演员全名再试）。

## 站点能力边界（实测）

| 路径 | 能力 |
| --- | --- |
| `/zh-Hans/drama/{id}` | 详情页：JSON-LD（`TVSeries` + `PerformanceRole` 演员）+ HTML（演员阵容、剧照、播放/收藏、集数/时长/首播时间/出品方）。**最可靠的一条路** |
| `/zh-Hans/actor/{id}` | 演员页：JSON-LD `Person`（姓名/简介/头像/性别/国籍/职务）+ 作品网格（实测 59 部一次全渲染、不分页）+ 合作演员区。⚠️ 必须带 `/zh-Hans` 前缀 |
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

## HTTP 接口

挂载在 `/api/v1/plugin/ShortDramaBaikeSource/`（全部 `auth: "bear"`）。

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/recognize` | **作品出口**：`media_id` 或 `keyword`(+`year`) → 纯 JSON 作品记录 |
| GET | `/actor` | **演员出口**：`actor_id` 或 `name` → 纯 JSON 演员档案（含全部作品与合作演员） |
| GET | `/lookup` | 一个 `keyword` 同时找作品与演员（面板唯一那个搜索框用它） |
| GET | `/status` | 运行情况：域名 / 站外索引配置 / 缓存条数（面板顶部 chip 与配置页读它） |
| GET | `/config` | 读当前配置 + 候选值（面板配置页回显） |
| PUT | `/config` | 存配置（逐键合并 + 归一化后落盘，并重建运行状态） |
| GET | `/probe` | 连通性自检：robots / 站外索引 / 详情页 / 演员页各自的状态码与解析条数 |

> 接口一共 7 条。旧的 `/search`、`/actor_search` 已并入 `/lookup`，
> `/explore` 随宿主探索页一起删除 —— 都是 v1.8.0 的事。

## 数据来源与合规

- 站点：`duanjubaike.org`（可在面板设置里改域）。
- **不抓** `/zh-Hans/drama/search` 与 `/auth`（`robots.txt` 明确 `Disallow`）。
- 不建立本地全量索引、不批量扫目录页 —— 只按需抓取用户实际要看的那几部作品与演员。

## 主要配置

面板的「设置」按钮打开配置页（联邦组件 `./Config`）。

| 配置 | 默认 | 说明 |
| --- | --- | --- |
| `enabled` | 关 | 启用插件 |
| `search_in_global` | 开 | 参与宿主的全局检索（未限定来源时） |
| `domain` | `duanjubaike.org` | 站点域名 |
| `timeout` | 15 | 单次请求超时（秒） |
| `cache_ttl` | 604800 | 详情页缓存（秒，默认 7 天） |
| `detail_facts` | 开 | 详情页「简介」上方显示一行「评分 · 全 N 集 · 主演 X、Y」 |
| `web_index_search` | 开 | **站外索引检索**：`site:` 限定检索片名 / 演员名，从收录的 URL 取 ID |
| `web_index_backend` | `auto` | 检索后端（`auto` / `duckduckgo` / `yandex` / `google` / `brave` / `mojeek`） |
| `proxy` | 关 | 出站请求是否走系统代理 |

共 9 项（v1.8.0 删掉了榜单范围、榜单刷新间隔、探索页详情回填三项）。
保存是**逐键合并**的：payload 里缺的键沿用当前生效值，只翻一个开关不会把其它配置冲回默认。

> **没有后台任务。** `get_service()` 恒返回空列表 —— 没有榜单要刷、没有索引要建，
> 缓存只在被查询时按需重建。配置页底部会显示一行运行实况（启用状态 / 站外索引开关与后端 /
> 缓存条数），直接读 `GET /status`。

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
