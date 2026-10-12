# 豆瓣演员订阅（DoubanActorSubscribe）

订阅豆瓣演员，抓取该演员的**最新影视作品**并展示在面板中；面板上的每个作品都带**订阅按钮**，
一点即提交到 MoviePilot 订阅系统（按**豆瓣 ID 精确订阅**）。也支持按类型/评分阈值**自动订阅**新作品。

```
配置演员 → 定时/手动刷新 → 抓取作品快照 → 仪表板 + 侧栏面板展示 → 一键订阅 / 自动订阅
```

## 功能

| 能力 | 说明 |
| --- | --- |
| 演员配置 | 支持**演员名称**（自动搜索并缓存豆瓣人物 ID）或直接填**豆瓣人物 ID**（纯数字，最精确） |
| 作品抓取 | 豆瓣 Frodo API：人物详情 → 影视作品集 → 作品列表，归一化标题/年份/类型/评分/海报/职务 |
| 面板展示 | 仪表板小组件（Top 4 + 新作品徽标）、侧栏全页（完整筛选 + 批量订阅） |
| 一键订阅 | 前端调用宿主 `subscribe/` 接口，携带 `media_source=douban` + `media_id`，归属当前登录用户 |
| 自动订阅 | 定时刷新后按「只订阅新作品 / 类型白名单 / 最低评分 / 每次上限」自动调用订阅链落库 |
| 通知 | 可通过宿主通知渠道推送刷新结果与自动订阅明细 |
| 智能体工具 | `douban_actor_latest_works`：让 AI 查询已跟踪演员的最新作品 |

## 配置项

| 字段 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| `enabled` | bool | `false` | 启用插件 |
| `actors` | str | 空 | 演员列表，一行一个，支持名称或豆瓣人物 ID（也支持逗号/分号分隔） |
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
| `onlyonce` | bool | `false` | 保存配置后立即刷新一次（勾选后自动复位） |

## HTTP 接口

挂载在 `/api/v1/plugin/DoubanActorSubscribe/<path>`，全部 `bear` 鉴权。

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/config` | 获取运行时配置（`actors` 以换行串、`auto_types` 以逗号串返回给前端） |
| PUT | `/config` | 合并更新配置，持久化后重新初始化插件 |
| GET | `/works` | 演员 + 作品快照 + 统计（面板数据源） |
| POST | `/run` | 立即刷新一次 |
| GET | `/search_actor?name=` | 按名称搜索豆瓣演员，辅助填写配置 |
| POST | `/clear` | 清空作品快照与自动订阅记录（不动配置） |

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
├── api.ts                 # 接口封装：插件 API + 宿主 subscribe/ 接口 + 时间格式化
├── types.ts               # 与后端 payload 对齐的 TS 类型
├── WorkGrid.vue           # 作品海报墙（Page / AppPage 复用，带订阅按钮）
├── Page.vue               # 插件详情页
├── Config.vue             # 配置页（emit('save', cfg) 由宿主持久化）
├── Dashboard.vue          # 仪表板小组件
├── AppPage.vue            # 侧栏全页 · 作品面板（nav_key=main）
└── AppPageSettings.vue    # 侧栏全页 · 运行状态（nav_key=settings）
```

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

## 兼容性

- 目标宿主：MoviePilot **V3**（`>=3.0.0`），已在 **v3.1.3** 实测。
- 仅从稳定入口导入：`app.sdk.*` / `app.schemas.types` / `app.chain.subscribe` / `app.agent.tools.base`；
  不使用 `app.helper.*`、`app.utils.*`、`app.core.*`。
- `MessageType` 做了 try/except 兼容导入（旧版本名为 `NotificationType`）。
