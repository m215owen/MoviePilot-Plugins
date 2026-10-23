// 短剧百科整理 —— Vite 模块联邦（remote）配置
//
// 约定与仓库其它联邦插件一致：
//   1. 不指定 rollupOptions.input，交给 federation 生成 `__federation_expose_<Name>-<hash>.js`；
//   2. shared 只共享宿主提供的 vue 运行时，且 generate: false（否则 remote 自带一份实例）；
//   3. build.target 必须是 esnext（联邦产物含顶层 await）；
//   4. 产物目录 `dist/a<N>`：目录名即浏览器缓存键（版本号测试期冻结，`?v=` 不会变）。
//
// ⚠️ 只暴露 ./Page 与 ./Config（V3 Vue 模式下两者都是必需项），不注册侧栏全页入口。
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import federation from '@originjs/vite-plugin-federation'

/**
 * 产物目录序号：前端**有实质改动**就递增（a1 → a2 …）。
 *
 * 宿主拼的联邦入口是 `/plugin/file/<id>/dist/a<N>/remoteEntry.js?v=<plugin_version>`，
 * 版本号测试期冻结 → `?v=` 不变时浏览器强缓存/Service Worker 会复用旧入口
 * （表现为界面停在旧版或「无法加载组件」）。改目录名即可强制换 URL。
 * 改这里必须同步 `constants.FRONTEND_DIST` 的兜底值（当前 `dist/a1/assets`）。
 */
const ASSETS_DIR = 'a21'

const sharedVue = { requiredVersion: false, generate: false, singleton: true } as const

const federationOptions = {
  // 联邦名称必须与插件类名一致
  name: 'ShortDramaBaikeOrganizer',
  filename: 'remoteEntry.js',
  exposes: {
    // 插件详情面板（插件管理里点插件卡片弹出；Vue 模式必需）
    './Page': './src/Page.vue',
    // 配置页（Vue 模式必需）
    './Config': './src/Config.vue',
  },
  shared: {
    // 只共享 vue：vuetify / mdi 由主程序全局注册，remote 不打包也不发全局样式
    vue: sharedVue,
  },
  format: 'esm',
}

export default defineConfig({
  appType: 'custom',
  plugins: [vue(), federation(federationOptions)],
  build: {
    target: 'esnext',
    minify: false,
    cssCodeSplit: true,
    sourcemap: false,
    outDir: `dist/${ASSETS_DIR}`,
    emptyOutDir: true,
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
          // 去掉 vuetify / mdi 的全局基础样式，避免联邦组件污染主程序主题
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
    port: 5005,
    cors: true,
    origin: 'http://localhost:5005',
  },
})
