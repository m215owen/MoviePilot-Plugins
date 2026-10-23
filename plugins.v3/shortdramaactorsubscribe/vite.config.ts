// 短剧演员订阅 —— Vite 模块联邦（remote）配置
//
// 遵循 MoviePilot-Frontend 的《模块联邦开发指南》与 V3 插件文档的联邦约束：
//   1. 不要显式指定 rollupOptions.input —— 交给 federation 插件生成
//      `__federation_expose_<Name>-<hash>.js`，主程序联邦加载器按此命名约定查找。
//   2. shared 只共享主程序已提供的运行时（vue），且必须 generate: false，
//      避免 remote 重复打包运行时造成实例分裂。
//   3. build.target 必须为 esnext（联邦产物含顶层 await）。
//   4. postcss 过滤掉主程序已提供的组件库基础样式规则，避免联邦组件污染全局主题。
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import federation from '@originjs/vite-plugin-federation'

/**
 * 共享的 vue 运行时配置。
 *
 * 单独抽出为常量是为了绕开一个类型定义缺陷：@originjs 的 `SharedConfig` 把
 * `singleton` 注释掉了，但「只保留一份 vue 实例」正是这里需要的语义，
 * 因此保留该键（写成变量后不再触发对象字面量的多余属性检查），
 * 以便将来更换联邦实现时语义不丢失。
 */
const sharedVue = { requiredVersion: false, generate: false, singleton: true } as const

/**
 * 产物子目录名（``a1``、``a2``…）：同时是浏览器缓存键。
 *
 * 宿主给联邦入口拼的 URL 是 `/plugin/file/<id>/<dist 目录>/remoteEntry.js?v=<plugin_version>`；
 * 测试阶段版本号冻结（`?v=` 不变），浏览器强缓存 / Service Worker 会一直复用旧
 * `remoteEntry.js` —— 表现是「代码改了但组件加载失败 / 还是旧界面」。于是把目录名当
 * 缓存键：**每次前端有实质改动就递增一位**（a1 → a2 → a3…），URL 随之变化，缓存天然
 * 失效，不需要用户手动注销 SW。后端 `get_render_mode()` 会扫描 `dist/` 下序号最大且
 * 含 `remoteEntry.js` 的 `a<N>` 目录，Python 侧不用改。
 */
const ASSETS_DIR = 'a51'

/**
 * 联邦插件选项。
 *
 * 同样抽成变量：@originjs 1.4.1 的 `VitePluginFederationOptions` 类型缺少
 * `format`，但运行时确实读取它（`format: item.format || "esm"`），
 * 而 V3 要求必须为 esm，因此不能删。
 */
const federationOptions = {
  // 联邦名称必须与插件类名一致
  name: 'ShortDramaActorSubscribe',
  filename: 'remoteEntry.js',
  exposes: {
    // 插件管理中的详情弹窗
    './Page': './src/Page.vue',
    // 插件配置页
    './Config': './src/Config.vue',
    // 仪表盘小组件
    './Dashboard': './src/Dashboard.vue',
    // 主界面侧栏全页（nav_key = main）
    './AppPage': './src/AppPage.vue',
  },
  shared: {
    // 只共享 vue：UI 组件库由主程序全局注册，联邦 remote 不需要（也不应）打包它，
    // 运行时直接从主程序实例取用，从而天然满足“联邦组件不得发布全局基础样式”的硬约束。
    vue: sharedVue,
  },
  format: 'esm',
}

export default defineConfig({
  // 联邦 remote 不需要 HTML 入口
  appType: 'custom',
  plugins: [vue(), federation(federationOptions)],
  build: {
    target: 'esnext',
    minify: false,
    cssCodeSplit: true,
    sourcemap: false,
    assetsDir: ASSETS_DIR,
    rollupOptions: {
      output: {
        chunkFileNames: `${ASSETS_DIR}/[name]-[hash].js`,
        assetFileNames: `${ASSETS_DIR}/[name]-[hash][extname]`,
      },
    },
  },
  css: {
    postcss: {
      plugins: [
        {
          postcssPlugin: 'internal:charset-removal',
          AtRule: {
            charset: (atRule: any) => {
              if (atRule.name === 'charset') atRule.remove()
            },
          },
        },
        {
          // 移除来自组件库与图标库的全局样式，以及所有组件库类名前缀的基础规则
          postcssPlugin: 'vuetify-filter',
          Root(root: any) {
            const sourcePath = (root.source?.input?.file || '').replaceAll('\\', '/')
            if (
              sourcePath.includes('/node_modules/vuetify/') ||
              sourcePath.includes('/node_modules/@mdi/')
            ) {
              root.nodes = []
              return
            }
            root.walkRules((rule: any) => {
              if (
                rule.selector &&
                (rule.selector.includes('.v-') || rule.selector.includes('.mdi-'))
              ) {
                rule.remove()
              }
            })
          },
        },
      ],
    },
  },
  server: {
    port: 5003,
    cors: true,
    origin: 'http://localhost:5003',
  },
})
