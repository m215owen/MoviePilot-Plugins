// 插件开发模板 —— Vite 模块联邦（remote）配置
//
// 遵循 MoviePilot-Frontend 官方《模块联邦开发指南》与 V3 插件文档的联邦约束：
//   1. 不要显式指定 rollupOptions.input —— 交给 federation 插件生成
//      `__federation_expose_<Name>-<hash>.js`，主程序联邦加载器按此命名约定查找。
//   2. shared 只共享主程序已提供的运行时（vue / vuetify / vuetify/styles），
//      且必须 generate: false，避免 remote 重复打包基础样式造成全局污染。
//   3. build.target 必须为 esnext（联邦产物含顶层 await）。
//   4. postcss 过滤掉 .v-* / .mdi-* 规则，主程序已有完整 Vuetify 样式。
//   5. 部署只上传 __federation_* / _plugin-vue_export-helper-* / remoteEntry.js。
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import federation from '@originjs/vite-plugin-federation'

export default defineConfig({
  // 联邦 remote 不需要 HTML 入口
  appType: 'custom',
  plugins: [
    vue(),
    federation({
      // 联邦名称必须与插件类名一致
      name: 'PluginTemplate',
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
        // 只共享 vue：Vuetify 组件由主程序 `app.use(vuetify)` 全局注册，
        // 联邦 remote 不需要（也不应）打包它——运行时直接从主程序实例取用。
        // 这样同时天然满足“联邦组件不得发布 Vuetify/MDI 全局基础样式”的硬约束。
        vue: { requiredVersion: false, generate: false, singleton: true },
      },
      format: 'esm',
    }),
  ],
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
          // 移除来自 vuetify / @mdi 的全局样式与所有 .v-* / .mdi-* 规则
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
    port: 5001,
    cors: true,
    origin: 'http://localhost:5001',
  },
})
