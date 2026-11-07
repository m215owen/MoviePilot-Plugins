# 短剧百科刮削源（ShortDramaBaikeScraper）

MoviePilot V3 插件：把 [短剧百科](https://www.duanjubaike.net) 注册为一等媒体来源
`djbaike`。（探索页榜单功能已于 2026-10-23 按用户要求整体移除。）

## 站点：.net / .org 二选一（2026-11-03）

配置项 `site` 决定**检索 / 人物目录 / 榜单**走哪个站：

| | `net`（默认） | `org` |
| --- | --- | --- |
| 域名 | `www.duanjubaike.net` | `duanjubaike.org` |
| `media_id` 前缀 | `duanju` / `manju` / `hema` / `huolong` / `yanyuan` / `daoyan` / `bianju` / `xiaoshuo` | `drama` / `actor` |
| 检索 | `/so.html?keyword=` | `/{lang}/drama/search?q=`、`/{lang}/actor/search?q=`（人物独立端点） |
| 详情页 | `/{kind}/info-{id}.html` | `/{lang}/drama/{id}`、`/{lang}/actor/{id}` |
| 解析 | 正则 + 文本切片（`parser.py`） | Alpine SSR + **JSON-LD**（`orgsite.py`，DOM 保底） |
| 海报 | 按身份反拼图床模板 | 页面自带 CDN 绝对地址（`cdn.duanjubaike.org`），**不能反拼** |
| 榜单 | 8 本（`/paihang/*` + `/tuijian`） | **暂未接入**（`rank_url` 返回空串，按空榜降级） |
| 原著 | 独立 `xiaoshuo:` 词条 | 只有页面区块（书名 / 封面 / 题材，无 id） |

**关键：详情与图片按 `media_id` 前缀路由，与配置无关。** `drama:` / `actor:` 恒走
`.org` 页面与解析器，其余前缀恒走 `.net` —— 换站不会让已入库的旧身份失效，两站
编号空间天然隔离（`drama:13502` 与 `duanju:7696405989787978814` 不是同一条）。

换站时会自动清空**检索缓存**（含负缓存）：旧站的「无结果」结论不能拿来判新站，
否则表现为「新站明明有，却一直 0 条且不发请求」。

配置页的两个站点选项在 Vue 配置面板（`./Config` 的「数据源 · 主站」）与宿主原生
表单（`get_form()` 的 `VSelect`）里都有一份，值同为 `net` / `org`。

## 外部 id 单独记录（2026-11-04 晚）

**豆瓣 / TMDB 不再挂在站点行上**，单独一张 `baike_ext` 表，**主键就是名字**，
一个名字只存一条：

| 表 | 存什么 | 粒度 |
| --- | --- | --- |
| `baike` | `media_id` / `name` / `is_ai` | 一行一个站点身份（新老站各一行，**不能合并**：`media_id` 是宿主识别身份，已散落在宿主库与 NFO 里） |
| `baike_ext` | `name` / `douban` / `tmdb` / `owner` | 一行一个名字（**与站在哪边、作品还是人物都无关**） |

* 读：`get` / `by_name` / `pending_external` / `works_with_douban` / `by_douban` /
  `by_tmdb` 这些**服务端内部**路径由 `store._attach_ext` **按名字**批量挂上
  `douban` / `tmdb`，上层拿到的字典形状不变。
* **面板的 `/baike/list` 不挂外部 id**：它只回站点行自己的原始值
  （`media_id` / `name`）。外部 id 另有端点：`GET /baike/extlist?q=&offset=&limit=&source=`
  → `{name, douban, tmdb}`（`store.ext_page`）。
* **外部 id 在面板上拆成两个分类**（2026-11-04 晚用户口径「拆为 tmdb 和豆瓣分类」）：
  「豆瓣 id」与「TMDB id」各一个 chip，`source=douban|tmdb` 让后端只回**该列非空**
  的行，各自独立分页；条数来自 `/status.ext_douban` / `ext_tmdb`（`ext_total` 仍给
  总记录数）。同一条记录两列都有值时，两个分类里都能看到它，行内只显示本分类那列，
  另一列在副标题里以「另有 …」提示。
* **按名取**：`store.external_ids(name)` / `GET /baike/ext?name=…` —— 直接回
  `{name, douban, tmdb}`，不用先有站点行。
* 写：`store.set_external_ids` 只写空值（绑定是严格判据匹配来的，先写下的就是
  答案），落进 `baike_ext`；**一次写入两站同时可见**，不再需要“同步给对站”。
* 读路径**不再「按名去别的行抄 id」**（2026-11-04 晚用户口径：从新站补 id 不需要了）：
  `_fill_douban_id` / `_fill_tmdb_id` / `_fuse_douban_person` / `_fuse_tmdb_person` /
  `bind_person_by_name` 一律读**自己这条 `media_id`** 挂上的外部记录（`store.get` 已经
  由 `_attach_ext` 挂好），读不到就正常出网搜。抄写既多余（同名共享同一条
  `baike_ext`），又会把同名不同人的误配固化下来 —— `store.external_id_by_name` 已删。
* 省一半出网：`pending_external` 按「名字 + 种类」去重 —— 同一部剧两站各有一行，
  批量补 id 时只搜一次（之前两行各搜一遍）。
* `douban:` / `doubanp:` 本体行（`media_id` 就是复合豆瓣 id）的豆瓣那半**不写表**，
  读时现算（`store._intrinsic_douban`）：否则会把同名但不同条目的豆瓣作品塞进
  同一条外部记录（实测库里 4 组同名不同 sid）。
* **两个外部 id 都是复合 id**（2026-11-04 晚用户口径「豆瓣和 tmdb 的 id 也可以作为
  复合 id」）：豆瓣 `douban:{sid}` / `doubanp:{pid}`，TMDB `tmdb:{id}` / `tmdbp:{pid}`
  —— 一眼能看出作品还是人物，也不会和裸数字混淆。写入由 `store.tmdb_composite`
  兜底补前缀（裸数字自动变 `tmdb:…`），历史裸数字由 `store.normalize_ext_tmdb`
  在启动时一次性改写（幂等）；读取端 `store.tmdb_number` 剥前缀，
  详情字段 `tmdb_id` 与 `by_tmdb` 反查两种形态都吃得下。
* 类型串台靠 `store._value_fits` 卡住：`doubanp:` / `tmdbp:` 只挂人物行，
  作品 id 只挂作品行（读写两端都复核一次，同名撞车也不会串）。
* 老库升级：`store._migrate_ext_columns` 在首次启动时把 `baike.douban/tmdb`
  搬进 `baike_ext`（按名字聚合，自带豆瓣 id 的行跳过豆瓣值），随后 `DROP COLUMN`；
  之后再启动是空操作。
* 删 `baike` 某一行**不动**外部记录（作品级数据，同名行还在用）；`/baike/clear`
  **只清站点行**，外部 id 表保留（2026-11-04：外部 id 是独立资产，清库不连带）。

> `baike.alt_id` 列也已删除（同日更早）：它把同名对站行互指，但写入来源就是同名
> 匹配、读取端一处都没有 —— 属于把「按名查一次」物化成一个会陈旧的字段。

## 「排除」开关按主站换口径（2026-11-03）

配置项 `exclude_manju`（配置页标签随主站变：老站「排除漫剧」/ 新站「排除 AI 剧」）
**一根开关、两套判据**，按条目的 `media_id` 前缀分派 —— 与当前主站配置无关：

| 身份 | 判据 | 来源 |
| --- | --- | --- |
| `duanju:` / `manju:` / `hema:` / `huolong:`（.net） | 卡片右下角角标 `kind == "漫剧"` | `search._card_kinds` |
| `drama:` / `actor:`（.org） | 卡片标题行的 `AI短剧` 标 `is_ai` | `orgsite._card_is_ai` |

生效面：识别候选（`recognize_by_name`）、面板 `/lookup`、宿主「搜索媒体」
（`DetailService.search` 自己剔，不经过 `/lookup` 的出口）、阵营作品清单
（`actor_works`）、原著改编清单。被判为排除的条目**也不登记进 ID 库**（否则下次
会以「本地命中」身份复活）；ID 库没有 `is_ai` 列，本地命中的新站条目改用
**详情缓存**补判一次（零网络，拿不到标注就不误杀）。

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
| ID 库 | `/baike/list`、`/baike/del`、`/baike/clear`、`/baike/extids` | 服务端模糊搜（media_id/name）+ 实体 chips + offset 分页；展开看**原始 4 列**（连空串都如实显示）；删单条（联动清详情/人物缓存）；清空有确认对话框；**批量补豆瓣 / TMDB id**（按名精确匹配、分批限量、带游标推进） |
| 缓存 | `/cache/items`、`/cache/del`、`/cache/clear` | 按 region 枚举原始键值、展开看缓存对象 JSON 原文、删单条（region+key）、清空全部有确认对话框 |
| 查询 | `/lookup`（原文走 `/lookup` 未拆信封响应） | 含 `:` 或纯数字 → 按 `media_id` 直取；其它 → 按名出候选（`remote` 开关 / 作品·人物过滤）；可跳宿主详情页、可看原始响应全文 |
| 查询 · 人物 | `/person` | 点人类型候选（`yanyuan:`/`daoyan:`/`bianju:`/`actor:`）→ 人物档案：姓名、身份（女演员/导演/编剧）、头像、简介、**作品清单**（每部带日期/集数/演员表/标签）、**合作演员**（`people`，`.org` 侧栏区块最多 20 位，带 `actor:` 身份与头像）；作品行可点回查该剧详情 |

> **分类跟着主站走**（2026-11-03）：新老站的 `media_id` 编号空间互不相通（老站
> `duanju:` / `yanyuan:` / `manju:`…，新站只有 `drama:` / `actor:`）。ID 库的实体
> chips、概览的实体分布、缓存行上的分类标签都按**当前主站**的实体清单给，中文名带
> 站点后缀（「短剧（新站）」「演员（老站）」）以免两站词撞名；切站不清库，所以库里
> 残留的别站前缀只要**有条目**就会追加在清单末尾，不会凭空消失。

> **批量补豆瓣 / TMDB id**（2026-11-03）：外部 id 原先只在「取详情」链路顺手补，
> 而库里绝大多数行是榜单 / 人物作品 / 顺带登记进来的，从没走过详情，于是几千条
> `drama:` 的 `douban` 列全空。`POST /baike/extids` 专治这个：每次取一批
> 「`douban` 或 `tmdb` 任一为空」的行（`entity` 可按前缀过滤、`limit` 上限 100），
> 逐条按名去豆瓣 / TMDB 搜，**只认名字完全相等**（短剧同名极多，写错 id 比没有更糟）；
> 返回 `scanned/douban/tmdb/remaining/cursor/throttled`，把 `cursor` 当下次的 `after`
> 传回来即可继续往下扫；重复调用直到 `remaining` 不再下降（短剧在豆瓣 / TMDB 上
> 本来就有大量未收录，补不上是常态，不当失败处理）。
> 豆瓣**只走宿主 `DoubanApi`（Frodo 通道）**，不另开旁路接口；限流与通道异常共用
> 一套指数退避冷却（5 分钟起、翻倍、封顶 30 分钟，成功一次即复位）。豆瓣被风控时
> **只跳过豆瓣那半条通道**，TMDB 照跑，响应里回 `throttled=true` 提示过一会儿再点。注意宿主的 `_handle_response` 会把非 200 与
> `code != 0`（含 103）**一律吞成 `None`**，所以插件侧看到 `None` 就按「通道忙」降温，
> 否则批量回填会一条接一条地继续打，把偶发被限打成全灭。
> TMDB 侧有年份就按年搜，没有年份则不限年搜一次，只在「精确同名且结果唯一」时才认。
> **按前缀分派**：`drama:` 等作品行走「剧集搜索」；`actor:` / `yanyuan:` 等人物行**两段式**：
> 先走 `bind_person_by_name` 按名直绑（豆瓣 / TMDB 各自「候选里**唯一精确同名**」才写
> `doubanp:{pid}` / `tmdbp:{pid}`，**不抓人物页**，一条约 2 秒）；同名多于一个才回落到
> `get_person`（抓人物页，按**作品交集**消歧）。不拿演员名去搜剧集（撞上同名剧集会把
> `douban:<剧集sid>` 写错到人物行）；`doubanp` 行直接跳过（它本身就是豆瓣影人，没有可补的 id）。
>
> 为什么加这条快路（2026-11-04 用户口径「演员的豆瓣 id 好像没有补」）：原判定要求
> 「作品交集打分 > 0」才绑，而短剧演员的百科作品绝大多数还没绑豆瓣 sid —— `known` 是空的，
> 交集永远 0 分，于是 1560 个新站演员只绑上 88 个。改成「唯一精确同名直接认」后单批
> 6 个演员的豆瓣命中从 1~2 个提到 4 个；缓存里的旧结论靠 `BIND_VERSION`（`service.BIND_VERSION`，
> 判定一改就 +1）让每份旧缓存**多补跑一次**，不会空到 TTL 到期。

> **人物豆瓣 id：演职员表硬链**（2026-11-03，`POST /baike/person_extids`）：
> ⚠️ 面板「补 id」在人物分类下**不再**调这个端点（它只覆盖已绑豆瓣 sid 的作品，
> 且游标单位是作品）；它保留在 API 上供全库批扫。
> 豆瓣**作品详情** `tv_detail` 的 `actors` 只有名字（`[{"name":"卡戎"}]`）、
> `directors` 常为空——**完全不带 id**；唯一带影人 id 的入口是
> `/tv/{sid}/celebrities`（`actors`/`directors` 每项都有 `id`、`character`、`avatar`）。
> 所以链路反过来走：取库里已绑豆瓣 sid 的作品 → 逐部拉演职员表 → 攒
> `name → {pid}` 池 → **影人 id 唯一**的同名人物行写 `doubanp:{pid}`。
> 判据硬在「同一部作品里同名 = 同一个人」，不用 person_search、不用作品交集打分；
> 一部剧一次请求能覆盖几十号人。`limit` 是**作品条数**（1~50），`after` 是作品
> `media_id` 游标，返回结构与 `/baike/extids` 相同。实测：92 部已绑作品里 64 部
> 取得到演职员表（其余是早期错绑的失效 sid），644 个人物槽位对上 51 个新绑定，
> `actor` 行豆瓣 id 7 → 58；同一批里 `character` 还带角色行当（导演 /「饰 安欣」）。
> 宿主把 404 与限流**一起吞成 `None`**，插件侧按「连续 10 部都拿不到」才判限流收工
> （库里坏 sid 较多，阈值小了会误停）。豆瓣对老 `celebrity` 档案（`/elessar/subject/`）
> 经常查无数据：绑定的 id 本身可靠（来自演职员表），只是档案接口没收录，展示层融合
> 暂时拿不到那些人的豆瓣详情。

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
  出图形态由配置 `use_baidu_image_proxy` 决定：**开（默认）** = 保留站点原始的百度
  gimg 中转（`gimg0.baidu.com/gimg?...&src=img.duanjubaike.net/...`），**关** = 直连
  `img.duanjubaike.net`。站点没有 backdrop / 分季海报 / 分集剧照，季/单集返回空 dict。
  ⚠️ **这个开关只对老站（.net）生效**：新站（.org）的海报是页面自带的
  `cdn.duanjubaike.org` 绝对地址，既不经百度中转、也不走 `img.duanjubaike.net`
  模板 —— 配置页在新站下会把它置灰并给出说明，`image_url("drama:…")` 直接返回空串
  （由调用方退回详情里的 CDN 地址）。
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
- **★ 图片域名要进宿主白名单**：`img.duanjubaike.net`（具体主机）、`doubanio.com`（父域，
  图床主机名随条目变）与 `gimg0.baidu.com`（百度图床代理，配置 `use_baidu_image_proxy`
  打开时才有）由 `whitelist.py` 在**启用时自动登记**进 `SECURITY_IMAGE_DOMAINS`，
  停用 / 关闭代理时按全集撤回，不留残留。不登记的话宿主图片代理会 `Blocked unsafe
  image URL: reason=domain_not_allowed`，面板与宿主里的海报全是空白。
  只放图床、不放 `www`，所以 `duanjubaike.net` / `baidu.com` 父域**都不能**写进去。
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
