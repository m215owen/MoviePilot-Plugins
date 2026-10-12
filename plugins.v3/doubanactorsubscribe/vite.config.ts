// 豆瓣演员订阅 —— Vite 模块联邦（remote）配置
//
// 遵循 MoviePilot-Frontend 官方《模块联邦开发指南》与 V3 插件文档的联邦约束：
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
 * 联邦插件选项。
 *
 * 同样抽成变量：@originjs 1.4.1 的 `VitePluginFederationOptions` 类型缺少
 * `format`，但运行时确实读取它（`format: item.format || "esm"`），
 * 而 V3 要求必须为 esm，因此不能删。写成变量可避开对象字面量的多余属性检查，
 * 同时其余字段仍按官方类型校验。
 */
const federationOptions = {
  // 联邦名称必须与插件类名一致
  name: 'DoubanActorSubscribe',
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
    // 多入口全页：nav_key = settings 时按名优先加载
    './AppPageSettings': './src/AppPageSettings.vue',
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
    rollupOptions: {
      output: {
        chunkFileNames: 'assets/[name]-[hash].js',
        assetFileNames: 'assets/[name]-[hash][extname]',
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
    port: 5002,
    cors: true,
    origin: 'http://localhost:5002',
  },
})
