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
| 跨插件调用 | 见下节 | 其它插件、脚本、AI 智能体都能直接复用同一套识别 |

统一媒体身份：`media_source = "duanjubaike"`，`media_id = "org:<id>"`（裸数字 ID 等价）。

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
| `use_browser_search` | 关 | 实验：用宿主浏览器仿真打站内检索 |
