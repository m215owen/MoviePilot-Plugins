// 短剧百科刮削源 —— Vite 模块联邦（remote）配置
//
// 遵循 MoviePilot-Frontend《模块联邦开发指南》与 V3 插件文档的联邦约束：
//   1. 不显式指定 rollupOptions.input，交给 federation 生成
//      `__federation_expose_<Name>-<hash>.js`（主程序加载器按此命名查找）。
//   2. shared 只共享主程序已提供的 vue 运行时，且必须 generate: false。
//   3. build.target 必须 esnext（联邦产物含顶层 await）。
//   4. postcss 过滤组件库/图标库的基础样式，避免联邦组件污染全局主题。
//
// ⚠️ federation 的 `name` 必须与后端插件类名一致（ShortDramaBaikeScraper）。
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import federation from '@originjs/vite-plugin-federation'

/** 只保留一份 vue 实例；@originjs 的类型定义里 singleton 被注释，故写成变量 */
const sharedVue = { requiredVersion: false, generate: false, singleton: true } as const

/**
 * 产物子目录名 —— 同时充当**浏览器缓存键**。
 *
 * 宿主给联邦入口拼的 URL 是 `/plugin/file/<id>/<dist 目录>/remoteEntry.js?v=<plugin_version>`；
 * 测试阶段版本号冻结（`?v` 不变），只要改这个目录名，URL 就变了，Service Worker 与强缓存
 * 的键不同 → 自动重新拉取，不需要用户手动注销 SW。
 *
 * 规则：**每次前端有实质改动就递增**（a1 → a2 → a3…），后端 `constants.frontend_dist()`
 * 会自动扫描 dist 下最大的 `a<数字>` 目录，不用改 Python。
 */
const ASSETS_DIR = 'a14'

/** @originjs 1.4.1 的类型缺 `format`，运行时确实读取，V3 要求 esm */
const federationOptions = {
  // 必须与插件类名一致：宿主按插件 ID 注册联邦入口
  name: 'ShortDramaBaikeScraper',
  filename: 'remoteEntry.js',
  exposes: {
    // 主界面全页面板（#/plugin-app/ShortDramaBaikeScraper/main）
    './AppPage': './src/AppPage.vue',
    // 插件管理里的详情弹窗（Vue 模式下没有它弹窗会是空的）
    './Page': './src/Page.vue',
    // 插件管理的「配置」页（Vue 模式下没有它 = 配置页打不开，官方 §8.2 明确要求）
    './Config': './src/Config.vue',
  },
  shared: {
    // 只共享 vue：Vuetify 由主程序全局注册，remote 不打包它，
    // 从而天然满足「联邦组件不得发布全局基础样式」的硬约束。
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
    // 产物落到插件根的 dist/<ASSETS_DIR>（后端 get_render_mode() 动态取该目录名）
    outDir: '../dist',
    assetsDir: ASSETS_DIR,
    emptyOutDir: true,
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
          // 移除组件库/图标库来源的整份 CSS，以及所有 .v-/.mdi- 基础规则
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
    port: 5010,
    cors: true,
    origin: 'http://localhost:5010',
  },
})
