# 短剧百科刮削源（ShortDramaBaikeScraper）

MoviePilot V3 插件：把 [短剧百科](https://www.duanjubaike.net) 注册为一等媒体来源
`djbaike`。（探索页榜单功能已于 2026-10-23 按用户要求整体移除。）

## 能力

| 能力 | 说明 |
| --- | --- |
| 媒体来源 `djbaike` | 声明 `MediaType.TV`；`media_id` 形如 `duanju:7696405989787978814` |
| ID 注册表 `baike` | 4 列 `media_id / name / douban / tmdb`，`name` 存站点原文、不做归一化 |
| 按名识别（六层） | 剧名清洗 → 本地精确 → 站内 `/so.html` → 豆瓣 `tv_search`；`recognize_media` 收敛唯一一条 |
| 季号识别（2026-10-23 补，同日出口修订） | 站点**一季一条独立词条**（`隐身侍卫` / `隐身侍卫第二季`）。识别入参里的季号（`S02` / `第2季` / `第二季`）先按 `{基名}第N季` 精确查库，命中即认该季词条。**出口不做季号推断、不做标题归一**（词条名里的季是站点文本、非结构化数据）：`title` 保留词条原样、`season` 恒 `None`、`seasons={1: 1..集数}` 按第 1 季合成 |
| 剧名清洗 | `一品猎罪师（70集）潘子剑&上淇等 - SKIT` → `一品猎罪师`（剥集数/演员/Tag/季号） |
| 豆瓣兜底 | 百科未收录的剧（《情靡》《绾骨灯》）走豆瓣 `tv_detail`，出 `douban:{sid}` 条目 |
| 站内指标 | 热度 / 播放量 / 收藏数宿主 `MediaInfo` 无对应列，一律走 `extensions.djbaike.heat` / `play_count` / `favorite_count` **字符串事实**（站点原串，如 `383.37万`，不折算数字）；上线时间 → `release_date`、平台 → `networks` |
| 整理刮削 | `metadata_nfo` / `metadata_img` 两个宿主契约（2026-10-23 补，同日季级修订）：剧级 `tvshow.nfo`+`poster.jpg`；季级 `season.nfo`（`seasonnumber`）+ `season{NN}-poster.jpg`（季海报仅当 `mediainfo.season` 与请求季号一致才出——出口季号推断去除后恒 `None`，实际只出第 1 季）；单集 `episodedetails.nfo`（showtitle+季集号）；分集剧照站点无素材，单集图片返回空。复用宿主 `MediaScraperHelper` |
| 数据端点 | `/status`、`/lookup`、`/search`、`/cache/clear`、`/cache/items` |

## 实现进度

- **P0（完成）**：骨架、建表、`media_id` 解析/反推、`/status`、缓存门面
  （探索页榜单管线已于 2026-10-23 整体移除）。
- **P1（完成）**：`media_id` → 详情页 → 解析 → `MediaInfo`；缓存优先（二次调用 0 网络）；
  软 404 → 负缓存 1h；抓页顺带登记（一页 +10~15 条）；`/lookup` 按 id 查详情。
- **P2（完成）**：六层识别的 ③④⑤⑥（剧名清洗、本地精确、站内搜索、豆瓣 `tv_search`/`tv_detail`）；
  `search_medias` 返回全部候选、`recognize_media` 按确定性规则收敛唯一一条；
  `/lookup?name=` 与 `/search`（纯本地）；裸豆瓣 id 反查。
- **P2.5（完成）**：Vue 远程管理面板（**不注册侧栏**）。四个分区＝概览 / ID 库 / 缓存 / 查询，
  由 `frontend/` 构建为联邦 remote，产物 `dist/assets/remoteEntry.js`（暴露 `./AppPage` 与 `./Page`）。
- **刮削出口（2026-10-23 完成，同日季级修订）**：`metadata_nfo` / `metadata_img` 两个宿主刮削契约，
  季级素材按季词条产出（季号可从剧名识别），见下文「整理刮削出口」。
- **季号识别（2026-10-23 完成，同日出口修订）**：站点把第 N 季拆成独立词条，识别侧补季号感知
  （`_meta_season` 挖季号 → `local_match_seasonal` 精确查 `第N季` 词条 →
  `pick_best` 按季号收敛），修复「S02 发布错认成第一季词条」；
  出口侧的季号派生 / 标题归一**已按用户要求去除**（`title` 词条原样、`season=None`、
  `seasons` 恒按第 1 季合成）。
- P3：人物与豆瓣融合。

## 管理面板（P2.5）

前端在 `frontend/`（Vite + `@originjs/vite-plugin-federation`），**产物落在插件根 `dist/assets`**
—— 与 `constants.FRONTEND_DIST`、`get_render_mode()` 的第二个返回值必须一致，否则宿主按
`dist/assets/remoteEntry.js` 找不到入口（联邦组件加载失败 = 弹窗空白）。

```bash
cd frontend
npm install          # 首次
npm run build        # → ../dist/assets/{remoteEntry.js, __federation_expose_AppPage-*.js, ...}
npm run typecheck    # vue-tsc --noEmit
```

入口：
- 全页 `#/plugin-app/ShortDramaBaikeScraper/main`（**不实现 `get_sidebar_nav()`**，左侧导航没有入口，
  需书签或直接输地址；`Page.vue` 顶部给了「全页打开」链接）
- 插件管理里的详情弹窗（`./Page`，Vue 模式下缺了它弹窗就是空白）
- 插件管理里的「配置」页（`./Config`，Vue 模式下**缺了它配置页打不开**；官方
  `Plugin_Development.md` §8.2 的推荐 exposes 就列了 `./Page` + `./Config`）。
  它读写 `GET/PUT /config`（后端 `api_get_config` / `api_update_config`：
  `update_config` 持久化后立即 `init_plugin` 生效），字段与 `get_form()` 同源。

四个分区与数据来源：

| 分区 | 数据来源 | 能做什么 |
| --- | --- | --- |
| 概览 | `/status` | 总条数、可检索比例、豆瓣兜底、实体分布、缓存 region 清单、版本/来源 |
| ID 库 | `/baike/list`、`/baike/del`、`/baike/clear` | 服务端模糊搜（media_id/name）+ 实体 chips + offset 分页；展开看**原始 4 列**（连空串都如实显示）；删单条（联动清详情/人物缓存）；清空有确认对话框 |
| 缓存 | `/cache/items`、`/cache/del`、`/cache/clear` | 按 region 枚举原始键值、展开看缓存对象 JSON 原文、删单条（region+key）、清空全部有确认对话框 |
| 查询 | `/lookup`（原文走 `/lookup` 未拆信封响应） | 含 `:` 或纯数字 → 按 `media_id` 直查；其它 → 按名出候选（`remote` 开关 / 作品·人物过滤）；可跳宿主详情页、可看原始响应全文 |
| 查询 · 人物 | `/person` | 点人类型候选（`yanyuan:`/`daoyan:`/`bianju:`）→ 人物档案：姓名、身份（女演员/导演/编剧）、头像、简介、**作品清单**（每部带日期/集数/演员表/标签）；作品行可点回查该剧详情 |

> 人物**不是** `MediaInfo`（那个结构描述"一部片"），所以 `/lookup?media_id=yanyuan:…` 会明确回
> 「人物档案请用 /person 查询」而不是 `data: null`；面板按 `media_id` 前缀分派。

纪律：面板**只做展示与转发**——实体归类、类型判定、候选收敛全在后端；清空类破坏性操作
走前端确认对话框，后端直接执行。

**改动前端后要 bump `plugin_version`**：宿主给联邦入口拼的 URL 带 `?v=<plugin_version>`
（实测 `/plugin/file/<id>/dist/assets/remoteEntry.js?v=0.1.0`），版本不动的话浏览器与
Service Worker 可能继续用旧产物 —— 表现为「代码改了但页面没变」。

> **本项目当前处于测试阶段，版本号冻结在 `0.1.5`，不再逐次 bump**（用户 2026-10-21 明确要求）。
> 于是 `?v=` 永远不变，浏览器强缓存 / Service Worker 会一直复用旧 `remoteEntry.js`（表现：
> 「无法加载组件」或界面停在旧版，连请求都不发）。
>
> **破缓存机制：产物目录名当缓存键**。宿主拼的 URL 是
> `/plugin/file/<id>/<dist 子目录>/remoteEntry.js?v=<plugin_version>`，所以前端有实质改动时
> 只要把 `frontend/vite.config.ts` 里的 `ASSETS_DIR` 递增一位（`a1` → `a2`），URL 就变了，
> 缓存自然失效。Python 侧不用改：`constants.frontend_dist()` 会扫描 `dist/` 下序号最大、
> 且含 `remoteEntry.js` 的 `a<N>` 目录。发布正式版时再恢复「改前端就升版本」的规矩。

## 整理刮削出口（metadata_nfo / metadata_img）

宿主整理/手动刮削在写盘前问插件两件事（`chain/scraping.py`）：`metadata_nfo`（`:727`）与
`metadata_img`（`:750`，插件来源必走插件分支）。两个契约都是插件优先 + 非空短路
（`plugin_short_circuit` 默认 `True`，且 `is_valid_empty` 只认 `None`——**空 dict 也会短路**），
不实现就只会在日志里留「NFO 文件生成失败！」；而内置生成器全部按 `scrape_source` 自我过滤，
在本来源下恒返回 `None`。这就是「整理后没有 nfo 和封面」的根因。

实现在 `scrape.py`，复用宿主公开的 `app.domain.scraper.MediaScraperHelper`
（anilist / bangumi / imdb 同款姿势，不自己拼 XML）：

- **准入闸门 `is_own_media`**：`media_source == djbaike` 才出手；非本来源返回 `None`（不是 `{}`）
  让位给内置模块——否则会劫持 TMDB / 豆瓣的刮削。
- **NFO 只做剧级**：`tvshow`（电影则 `movie`）根节点，字段取统一 `MediaInfo`
  （标题/年份/简介/评分/类型/导演/演员带角色与头像/`uniqueid type=djbaike`）。
  `season` / `episode` 有值返回 `None`——站点没有分季/分集素材，写「根节点对、内容是剧级」的
  season.nfo / 单集 nfo 比不写更脏（媒体服务器自己会兜底）。后续要补是 `scrape.build_nfo`
  里删一行判断的事。
- **图片只出 `poster.jpg`**：地址就是 `poster_path`（图床按 id 反推，零请求）；
  站点没有 backdrop / 分季海报 / 分集剧照，季/单集返回空 dict。
- **演员后处理**（`_annotate_actors`）：宿主 helper 的 `<thumb>` 只认 `avatar`/`images` 键，
  我们的头像在 `profile_path`；顺带补 Nfo 规范的 `<order>`（番位）与 `<type>`。
  解析失败一律保持原文。

## 重要设计说明

**本插件不按虚拟分身隔离数据。** `baike` 表与 `djbaike.*` 缓存是「来源级全局数据」：
所有分身面对同一个站点，索引与缓存内容幂等，共享是设计预期（一个实例抓页，另一个
实例立刻命中）。配置（`enabled` 等）仍由宿主按实例隔离。这是官方 §7.4 允许的
「明确说明」边界，不是缺陷。

## 数据端点

```bash
GET  /api/v1/plugin/ShortDramaBaikeScraper/status
# 按 media_id 取单条详情（百科八类 + douban:{sid}；也接受裸豆瓣数字 id）
GET  /api/v1/plugin/ShortDramaBaikeScraper/lookup?media_id=duanju:7696405989787978814
# 按名搜作品/演员（默认只查本地；remote=1 联网补全，type=work|person 过滤）
GET  /api/v1/plugin/ShortDramaBaikeScraper/lookup?name=以爱为家&remote=1
# 纯本地检索（0 网络，供面板自动补全）
GET  /api/v1/plugin/ShortDramaBaikeScraper/search?name=以爱为家
GET  /api/v1/plugin/ShortDramaBaikeScraper/cache/items?region=djbaike.detail
POST /api/v1/plugin/ShortDramaBaikeScraper/cache/clear
```

普通 JSON 一律显式返回 `{success, message, data}`；调用方按宿主要求读取 `data`
（`List[MediaInfo]`）。

## 常见坑（实装时踩过）

- **软 404 必须按结构判**：错前缀的详情页返回 HTTP 200 + 约 40172 字节空壳（无 `<title>`/`<h1>`）。
  但**不能按字节数判**——无结果的搜索页也约 40.2 KB，按大小会误杀正常页。
- **豆瓣 `DoubanApi` 是弱单例**：`DoubanApi()` 拿的是宿主同一实例，**绝不 `close()`**。
- **目录/搜索页取名要锁卡片范围**：固定窗口 + `rfind(title|alt)` 会抓成上一张卡的名字。
- **剧名清洗只动输入**：`baike.name` 始终存站点原文，`WHERE name = ?` 原样匹配。
- **名字为空的 id 不入库**：`upsert_many` 直接丢弃空名行（不可检索、且 `upsert` 不会回填，
  属于纯死数据）。抓页顺带登记时列表卡偶尔只有 id，等带名字的那次再入。
- **★ 识别结果必须用 `app.sdk.media.MediaInfo`，不能用 `app.schemas.MediaInfo`**：
  v3.1.8 的识别收敛在 `application/classification/execution.py` 里调
  `finalized.set_library_category(...)`，这方法只在 domain dataclass 上 —— pydantic 的
  schemas 版没有 → `AttributeError` → `/media/recognize2` 500（界面表现就是「指定来源识别不到」）。
  转换集中在 `hostmedia.py`；HTTP 端点仍用 schemas 版作 `response_model`（domain 对象塞不进
  `schemas.Response[...]`，pydantic 不读 dataclass 属性）。
- **`seasons` 必须填**：宿主 `chain/download/existence.py` 判 `if not mediainfo.seasons` 就报
  「媒体信息中没有季集信息」并放弃缺集判定。短剧按「第 1 季 = 1..总集数」补（集数 0 时不编）。
  domain 的 `detail_link` 只是个恒为 `""` 的只读 property，不是字段 —— 传它构造会 TypeError。
- **★ 图片域名要进宿主白名单**：`img.duanjubaike.net`（具体主机）与 `doubanio.com`（父域，
  图床主机名随条目变）由 `whitelist.py` 在**启用时自动登记**进 `SECURITY_IMAGE_DOMAINS`，
  停用时只撤回这两条。不登记的话宿主图片代理会 `Blocked unsafe image URL:
  reason=domain_not_allowed`，面板与宿主里的海报全是空白。
  只放图床、不放 `www`，所以 `duanjubaike.net` 父域**不能**写进去。
- **前置方括号是标签不是名字**：`[2X免费]实习生掌权…（57集） - SKIT` 里方括号是营销标签，
  真正剧名在后面（与 `拼音…[念念归秦 | 全70集]` 恰好相反）。清洗按位置区分两种形态；
  站内搜索还会**逐个候选试（前 3 个）**，避免首位候选是标签时一击不中。

### 部署顺序（踩过的坑，务必照做）

1. `npm run build` → `../dist/`
2. `rsync -a --delete dist/ nas:<仓库>/dist/`（或 `scp -r`）
3. **等 10~15 秒**让宿主 `PluginChangeMonitor` 把仓库改动同步进运行目录；
   然后用 `docker exec moviepilot ls /app/app/plugins/<id>/dist/assets` 核对产物在不在。
4. 需要重载 `.py` 时再 `touch __init__.py`；**不要**在结果 `docker cp` 之后立刻 touch ——
   monitor 的「本地插件同步」会重建插件安装快照，与手工 cp 竞争时会把运行目录里的
   `dist/` 清掉。表现是静态端点 `/api/v1/plugin/file/<id>/dist/assets/remoteEntry.js`
   直接 **404**，前端报「**无法加载组件，请稍后再试**」（不是 401 —— 401 才是正常的未登录）。
5. 若手工 `docker cp` 过任何文件，必须 `docker exec -u root moviepilot chown -R 1000:1000 <运行目录>`，
   否则宿主的安装快照会因 `__pycache__` 属主是 root 而 `Permission denied`，导致**同步失败且不重载**。
