# Vue-PT 监护台（VuePTMonitor）

展示 PT 站点运行状态、病危通知与站庆预告，并可把可添加站点写入 MoviePilot 站点管理。

> 本插件基于 [KoWming/MoviePilot-Plugins](https://github.com/KoWming/MoviePilot-Plugins) 的 `Savept`（Vue-PT监护室 v1.1.1）改造。
> 按插件发布约定更换了插件 ID 与名称，以避免与上游原版冲突。

## 相对原版的关键修复

原版 `_extract_site_cards` 用一条 20 余段串联的超长正则解析整页 HTML，页面结构稍有变化
（属性顺序变化、`data-*` 缺失、卡片改版）即触发**灾难性回溯**：正则在 C 层长时间运行且不释放 GIL，
导致整个 MoviePilot 进程假死——表现为页面打不开、`/health/ready` 超时、容器 `unhealthy`，
只能重启恢复，且每次打开该插件页面都会复现。

本版改动：

| 项目 | 原版 | 本版 |
|---|---|---|
| 站点卡片解析 | 超长正则 + `re.S` | **BeautifulSoup 结构化提取**，线性时间 |
| 年份分组解析 | `.*?`(re.S) 跨行匹配 | BS4 优先，正则兜底且用**有界字符类**（≤200 字符） |
| 名称候选拆分 | `.*?` | 有界字符类 `[^）)\]】]*` |
| 页面体积 | 无限制 | **>2MB 直接拒绝解析**并走缓存 |
| 解析耗时 | 无监控 | 超过 3s 记录告警日志 |

## 新增能力

### 1. 一键写入 MP 站点

快照会为每个站点标注与 MP 站点体系的关系：

- `MP已拥有`：已在 MP 站点管理中
- `MP可添加`：MP 内建索引器已支持该站，但你还没添加
- `MP未收录`：MP 没有该站的索引器定义

对 `MP可添加` 的站点可直接写入 MP 站点管理：

```
POST /api/v1/plugin/VuePTMonitor/sites/add
{"domains": ["example.com"]}   # domains 省略则处理全部可添加站点
```

### 2. 站点启停

```
POST /api/v1/plugin/VuePTMonitor/sites/toggle
{"domain": "example.com", "active": false}
```

### 3. 按站点状态联动（可选，默认关闭）

| 配置项 | 默认 | 说明 |
|---|---|---|
| `auto_add_available` | 关 | 每次刷新快照后自动把「MP可添加」站点写入站点管理 |
| `sync_mp_active` | 关 | 站点状态为「死亡」时自动禁用 MP 中对应站点 |
| `sync_mp_restore` | 关 | 站点恢复「健康」时自动重新启用 MP 中对应站点 |

联动采用保守策略：只处理已明确判定的状态，任何异常都被隔离，不影响快照生成。

## 配置迁移

插件首次加载时会自动从旧插件 `Savept` 继承配置项（源站地址、超时、Cron、代理、浏览器仿真等）
与上一次的站点快照缓存，迁移只执行一次（以 `legacy_inherited` 标记）。新增的三个联动开关默认关闭，
不会继承也不会自动开启。

## 配置项

| 键 | 说明 |
|---|---|
| `enabled` | 是否启用 |
| `source_url` | 监护源站地址，默认 `https://savept.icu/` |
| `request_timeout` | 抓取超时（秒），最小 5 |
| `default_internal_only` | 默认仅展示内站 |
| `notify` | 是否发送定时公告通知 |
| `cron` | 公告推送 Cron，默认 `0 8 * * *` |
| `use_proxy` | 是否走系统代理 |
| `use_browser_emulation` | 是否用浏览器仿真抓取 |
| `auto_add_available` | 自动写入可添加站点 |
| `sync_mp_active` | 站点死亡时禁用 MP 站点 |
| `sync_mp_restore` | 站点恢复时启用 MP 站点 |

## 接口

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/config` | 读取配置 |
| POST | `/config` | 保存配置 |
| GET | `/summary` | 概览统计 |
| GET | `/sites` | 站点列表 + 公告 |
| POST | `/refresh` | 强制刷新快照 |
| POST | `/sites/add` | 写入可添加站点 |
| POST | `/sites/toggle` | 启用/禁用 MP 站点 |

## 致谢

原插件作者：KoWming（https://github.com/KoWming）
