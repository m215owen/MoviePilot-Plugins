# 短剧百科数据源（ShortDramaBaikeSource）

MoviePilot **V3** 插件。把「短剧百科」（`duanjubaike.org`）注册为 MoviePilot 的
**一等媒体数据源** —— 与 TMDB / 豆瓣 / Bangumi 在宿主里同级，而不是另起一套私有链路。
它自身**只提供数据源**：片名检索 + 详情识别；发现之后要做什么（订阅、下载、整理）
交给宿主或别的插件。

## 为什么需要它

短剧在 TMDB / 豆瓣上大量没有条目，宿主识别器因此建不起媒体身份（本机实例实证：
站点能搜到剧名，但宿主 `media_info` 全为 null）。本插件补的正是这一段空白。

## 核心能力

| 能力 | 宿主接口 | 说明 |
| --- | --- | --- |
| 声明数据源 | `get_media_source()` | 在识别 / 刮削 / 搜索界面的「媒体来源」里出现「短剧百科」 |
| 片名检索 | `search_medias` | 返回候选 `MediaInfo`（含海报），宿主搜索框、探索页、订阅都能用 |
| 详情识别 | `recognize_media` | 按 `media_id`（`org:<id>`）或片名取完整记录 |
| 补图 | `obtain_images` | 缺海报时按身份补抓，并把海报兜底填到背景图 |
| **「探索」页来源** | `DiscoverSource` 事件 + `/explore` | 在 MoviePilot 的「探索」菜单里多出一个「短剧百科」来源，可切换榜单浏览；**打开时会按需回填少量作品的简介 / 年份 / 类型 / 演员 / 评分** |
| 跨插件调用 | 见下节 | 其它插件、脚本、AI 智能体都能直接复用同一套识别 |

统一媒体身份：`media_source = "duanjubaike"`，`media_id = "org:<id>"`（裸数字 ID 等价）。

## 在 MoviePilot 的「探索」页里浏览

宿主 `GET /api/v1/discover/source` 会广播 `ChainEventType.DiscoverSource` 事件收集来源
（宿主源码 `api/endpoints/discover.py`），插件把 `DiscoverMediaSource` 追加进
`event_data.extra_sources` 就成为一个来源；前端随后按它的 `api_path` 拉 `List[MediaInfo]`。

- **来源名**：短剧百科；**可见位置**：MoviePilot 侧栏「探索」菜单
- **筛选条**：「榜单」chips —— `热播榜` / `新剧榜` / …（你勾了哪些就有哪些）+ `全部短剧`
  （本地目录索引，按站点 ID 倒序，即最新在前）
- **数据来源**：本地榜单快照 + 目录索引；榜单页 HTML 里只有「标题 + 海报 + 集数」，
  所以插件会对**当前这一页**按需回填少量作品详情，让条目带上 TMDB 级的
  「简介 / 年份 / 类型 / 演员 / 评分」；**评分与标签还会先按 ID 从本地索引借**
  （同一部作品在榜单页与目录页 ID 相同，零请求）
- **卡片评分**：探索页卡片右上角的评分徽章读的是 `vote_average` —— 索引/详情能取到
  分值的作品会直接显示
- **回填配额纪律**：每次请求最多 `explore_detail_fetch` 部（默认 2，0 = 完全不请求），
  且**至少给识别留 2 次额度**；额度不足或撞 CF 时立即停手，退回卡片字段照常返回
- **点开作品后的详情**：见下节「详情页能显示什么」
- **端点**：`GET /api/v1/plugin/ShortDramaBaikeSource/explore?top_key=hot&page=1&count=30`

要看到更多榜单，去「配置 → 榜单快照范围」把榜单勾上（每个榜单花一次站点请求配额，
所以默认只刷热播榜 + 新剧榜）。

## 「点开作品」后的详情页能显示什么（重要）

在探索页点一张卡片，前端会跳到 `/media?media_source=duanjubaike&media_id=org:<id>`，
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
- **评分**另外会出现在探索页**卡片右上角**的徽章上。
- 完整的「评分 / 演员 / 剧照」字段一直都在 `recognize_media()` 的返回值里，
  其它插件与 Agent 可以照常取用（见下节）。

## 供其它插件调用（本插件同时是「短剧识别服务」）

三条通道，**共用同一个配额闸门**，谁调都不会绕过限流：

### 1. 宿主模块分发（首选，进程内、零序列化）

宿主的分发器同时挂了模块目录与**插件目录**
（`app/chain/base.py`：`module_dispatcher_factory(module_catalog=self.modulemanager,
plugin_catalog=self.pluginmanager, …)`），而每个插件都是 `ChainBase` 子类，所以直接：

```python
# 在另一个插件里（self 是任意插件实例 / 任意 Chain）
infos = self.run_module("search_medias", meta=meta, media_source="duanjubaike")
info  = self.run_module("recognize_media", media_source="duanjubaike", media_id="org:40105")
info  = self.run_module("obtain_images", mediainfo=info)
```

`media_source` 写 `duanjubaike` / `shortdramabaike` / `shortdramabaikesource` 都能命中。
返回的是宿主 `MediaInfo`（与 TMDB / 豆瓣模块同一个领域模型）。

### 2. HTTP 纯 JSON 出口（脚本 / 外部程序）

```bash
GET /api/v1/plugin/ShortDramaBaikeSource/recognize?media_id=org:40105
GET /api/v1/plugin/ShortDramaBaikeSource/recognize?keyword=万妖图录传&year=2026
```

响应形状固定且只含标量（`build_public_record`），不会被 `MediaInfo` 的字段版本绑住：

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
    "actors": [{"id": "2014", "name": "刘清心", "role": "苏晚", "kind": "主演"}]
  }
}
```

`origin` 说明数据来自 `detail`（详情页，字段全）还是 `index`（仅本地索引，字段少）。

### 3. 智能体工具

`short_drama_identify`（`get_agent_tools()`）：AI 智能体用片名或 `media_id` 识别短剧。

## 站点能力边界（实测 2026-10-14）

| 路径 | 能力 |
| --- | --- |
| `/zh-Hans/drama/{id}` | 详情页：JSON-LD（`TVSeries` + `PerformanceRole` 演员）+ HTML（演员阵容、剧照、播放/收藏、集数/时长/首播时间/出品方） |
| `/zh-Hans/drama/list?page=N` | **全量目录**，30 部/页，站内自述「共 1879 页」⇒ 全库约 5.6 万部；卡片自带海报、真人/AI 角标、状态角标、评分、系列季、集数、热度/播放、标签 |
| `/zh-Hans/drama` | 首页式**精选页**：固定 30 条（`?page=N` 无效） |
| `/zh-Hans/top/{key}` | 17 个榜单：**数量固定、不分页** |
| `/zh-Hans/drama/search` | 站内检索：**Cloudflare JS 挑战**，服务端直连恒 403（正文 `Just a moment...`） |
| `robots.txt` | `Disallow` 全部 `/search`（drama/actor/director/writer/producer）与 `/auth`，并声明 `Sitemap` |

## 配额：本插件设计的核心约束

站点的 Cloudflare 风控**按 IP 计**，普通 HTTP 与宿主浏览器同等生效。实测：

- 以 **1.5 秒**间隔连抓，**第 6 次**即 403；
- 把间隔放宽到 **10 秒**，**仍然是第 6 次** 403；
- ⇒ 卡的是「一个窗口内几次」，不是「每秒几次」；冷却数分钟后恢复。

因此本插件用**滚动窗口配额闸门**（`_take_slot`）管住所有出站请求：

- 窗口 `quota_window_minutes`（默认 **5** 分钟）内最多 `quota_max_requests` 次
  （默认 **5** 次，即实测值）；
- 后台任务（索引 / 榜单）多留一个额度（`reserve=1`），**把最后的额度让给识别与检索**
  —— 否则后台把额度吃光，用户点一次识别就直接撞 403；
- 真撞上 403 时进冷却（`cooldown_minutes`，默认 10 分钟），期间所有请求短路，
  免得反复试错把 IP 拖进更长的封禁。

## 检索是三级降级

1. **本地目录索引**（主力）：后台任务按配额一小步一小步地把 `/zh-Hans/drama/list`
   抓成本地索引并持久化，检索时在本地做片名匹配 —— 这是唯一能在配额内做到
   「全库片名检索」的路子。
2. **榜单快照**：榜单的最近快照（默认 6 小时刷新），覆盖最新与热门。
3. **实时目录扫描**（`scan_pages`）：实在没有索引时，现场抓目录前 N 页做匹配。

站内检索（`use_browser_search`，默认**关闭**）是实验开关：宿主浏览器仿真有时能跑掉
Cloudflare 的 JS 挑战，但在 NAS 上尚未验证稳定，失败一律静默返回空。

## HTTP 接口

挂载在 `/api/v1/plugin/ShortDramaBaikeSource/`。

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/explore` | **探索页数据源**：`top_key`(+`page`/`count`) → `Response[List[MediaInfo]]`（读本地快照 + 按需回填当前页详情） |
| GET | `/recognize` | **跨插件出口**：`media_id` 或 `keyword`(+`year`) → 纯 JSON 作品记录 |
| GET | `/search` | 按片名试搜，返回候选与匹配分（排障用） |
| GET | `/probe` | 连通性自检：robots / 目录页 / 榜单 / 详情页各自的状态码与解析条数 |
| GET | `/index` | 手动推进一次本地目录索引（`pages` 省略则用配置值） |
| GET | `/status` | 索引条数、抓取进度、榜单快照、配额与冷却状态 |

## 数据来源与合规

- 站点：`duanjubaike.org`（默认可在配置里改域）。
- 抓取节奏受上述配额闸门与 `robots.txt` 约束：**不抓** `/search`、`/auth`。
- 全量目录采用「小步 + 冷却 + 断点续爬」，撞 403 时**不推进**页码，避免永久跳页。

## 主要配置

| 配置 | 默认 | 说明 |
| --- | --- | --- |
| `enabled` | 关 | 启用插件 |
| `search_in_global` | 开 | 参与宿主的全局检索（未限定来源时） |
| `index_enabled` | 开 | 后台建立本地目录索引 |
| `index_pages_per_run` | 4 | 每轮抓几页（**故意压在配额以内**，别调大） |
| `index_max_pages` | 700 | 索引抓取的最大深度（抓满后回到第 1 页追新） |
| `interval_minutes` | 5 | 后台服务的触发间隔（分钟） |
| `quota_window_minutes` / `quota_max_requests` | 5 / 5 | 滚动窗口额度（实测值，调大就等着 403） |
| `min_interval` | 3.0 | 相邻请求的最小间隔（秒） |
| `cooldown_minutes` | 10 | 撞 403 后的冷却时长 |
| `scan_pages` | 1 | 没有索引时的实时扫描页数 |
| `top_keys` | 热播榜 + 新剧榜 | **要刷哪些榜单**（17 个任选）= 探索页里能看到的来源；每个榜单一次请求配额 |
| `explore_detail_fetch` | 2 | 探索页每次请求最多回填几部作品的详情（简介 / 年份 / 类型 / 主演）；`0` = 不额外请求 |
| `detail_facts` | 开 | 详情页「简介」上方显示一行「评分 · 全 N 集 · 主演 X、Y」（宿主没给自定义来源留评分/演职员位，只能借 `tagline`） |
| `use_browser_search` | 关 | 实验：用宿主浏览器仿真打站内检索 |
