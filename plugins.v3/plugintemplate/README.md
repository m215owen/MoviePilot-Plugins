# 插件开发模板（PluginTemplate）

面向 **MoviePilot V3** 的插件开发模板，Vue 模块联邦 UI，可直接运行、可二次开发。

## 覆盖的扩展点

| 能力 | 实现处 |
| --- | --- |
| 生命周期（可重复初始化 / 资源释放） | `init_plugin` / `get_state` / `stop_service` |
| 配置页 | `get_form`（Vue 模式返回 `([], 默认配置)`）+ `src/Config.vue` |
| 详情页 | `get_page`（Vue 模式返回 `[]`）+ `src/Page.vue` |
| 仪表板组件 | `get_dashboard` / `get_dashboard_meta` + `src/Dashboard.vue` |
| 侧栏全页（多入口） | `get_sidebar_nav` + `src/AppPage.vue` / `src/AppPageSettings.vue` |
| 定时服务 | `get_service`（`CronTrigger`） |
| 远程命令 | `get_command` + 监听 `EventType.PluginAction` |
| 插件 HTTP API | `get_api`（`bear` 鉴权） |
| 工作流动作 | `get_actions` |
| 智能体工具 | `get_agent_tools` + `agenttool.py` |
| 数据持久化 | `save_data` / `get_data` / `get_data_path` |
| 系统通知 | `post_message` + `MessageType.Plugin` |

## 目录结构

```
plugintemplate/
├── __init__.py            # 插件主类（后端全部扩展点）
├── agenttool.py           # 智能体工具
├── package.json           # 前端依赖（Vue 3 + Vite 6 + 模块联邦）
├── vite.config.ts         # 联邦构建配置
├── tsconfig.json
├── index.html             # 本地调试占位页
├── src/                   # 联邦远程组件源码
│   ├── Page.vue           #   ./Page
│   ├── Config.vue         #   ./Config
│   ├── Dashboard.vue      #   ./Dashboard
│   ├── AppPage.vue        #   ./AppPage（nav_key = main）
│   ├── AppPageSettings.vue#   ./AppPageSettings（nav_key = settings）
│   ├── api.ts             #   api prop 解析与响应归一化
│   └── types.ts           #   前后端共享类型
└── dist/assets/           # 联邦构建产物（remoteEntry.js 等）
```

## 二次开发步骤

1. **改名字**：把类名 `PluginTemplate`、目录名 `plugintemplate`、
   `plugin_config_prefix`、`vite.config.ts` 中的 `federation.name`、
   `package.v3.json` 的键名、前端 `src/api.ts` 的 `PLUGIN_ID` **同步**替换。
   目录名必须是类名的小写形式。
2. **写业务**：把 `execute_task()` 里的示例逻辑替换为真实实现；
   需要配置项时，同时改 `_default_config()`、`Config.vue` 的 `defaults` 与 `types.ts`。
3. **加接口**：在 `get_api()` 中声明路由，在 `src/*.vue` 中通过 `api` prop 调用。
4. **构建前端**：

   ```bash
   npm install
   npm run build     # 产物输出到 dist/assets
   ```

   本地联调可用 `npm run dev`（等价于 `vite build --watch`），
   配合宿主 `PLUGIN_AUTO_RELOAD=true` 实现热更新。
5. **校验版本一致性**：`__init__.py` 的 `plugin_version`、
   `package.v3.json` 的 `version`、`history` 顶部键必须一致。

## 构建产物说明

联邦 remote 只需上传以下文件到宿主可见位置（本模板即插件目录下的 `dist/assets`）：

- `remoteEntry.js`
- `__federation_*`
- `_plugin-vue_export-helper-*`

**不需要**上传 `__federation_shared_vuetify` 以及 `index-` / `date-` / `runtime-` 前缀文件。

## 注意事项（V3 契约）

- 插件与宿主同进程，**不要**在模块导入期做网络请求、连库或启动线程。
- 前端组件**不得**打包 `vuetify/styles` 或 MDI 全量样式，也不得声明
  全局 `.v-*`、`.mdi-*`、`html`、`body`、`:root` 规则；本模板已在
  `vite.config.ts` 的 postcss 中过滤，请勿删除。
- 配置与数据一律走基类方法，运行时文件写入 `get_data_path()`，不要写回源码目录。
- 只从 `app.sdk.*`、`app.schemas.*`、`app.agent.*` 等稳定入口导入。
