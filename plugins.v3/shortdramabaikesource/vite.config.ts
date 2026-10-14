// 短剧百科数据源 —— Vite 模块联邦（remote）配置
//
// 沿用 MoviePilot 联邦插件的既有约定（与 ShortDramaActorSubscribe / DoubanActorSubscribe 同套）：
//   1. 不显式指定 rollupOptions.input —— 交给 federation 插件生成
//      `__federation_expose_<Name>-<hash>.js`，宿主的联邦加载器按这个命名约定查找。
//   2. shared 只共享宿主已提供的 vue 运行时，且必须 generate: false，
//      否则 remote 重复打包运行时会造成实例分裂。
//   3. build.target 必须为 esnext（联邦产物含顶层 await）。
//   4. postcss 过滤掉宿主已提供的组件库基础样式，避免联邦组件污染全局主题。
//
// ⚠️ 本插件**只暴露 ./Page 与 ./Config**：详情弹窗要放搜索框（所以必须走联邦，
// 见后端 get_render_mode 的说明），配置页则是 Vue 模式下宿主唯一认的配置入口。
// 不暴露 AppPage —— 本插件不在侧栏加全页入口。
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import federation from '@originjs/vite-plugin-federation'

/**
 * 共享的 vue 运行时配置。
 *
 * 单独抽出为常量是为了绕开一个类型定义缺陷：@originjs 的 `SharedConfig` 把
 * `singleton` 注释掉了，但「只保留一份 vue 实例」正是这里需要的语义，
 * 因此保留该键（写成变量后不再触发对象字面量的多余属性检查）。
 */
const sharedVue = { requiredVersion: false, generate: false, singleton: true } as const

/**
 * 联邦插件选项。
 *
 * 同样抽成变量：@originjs 1.4.1 的 `VitePluginFederationOptions` 类型缺少
 * `format`，但运行时确实读取它（`format: item.format || "esm"`），
 * 而 V3 要求必须为 esm，因此不能删。
 */
const federationOptions = {
  // 联邦名称必须与插件类名一致
  name: 'ShortDramaBaikeSource',
  filename: 'remoteEntry.js',
  exposes: {
    // 插件管理中的详情弹窗（两个搜索框都在这里）
    './Page': './src/Page.vue',
    // 插件配置页
    './Config': './src/Config.vue',
  },
  shared: {
    // 只共享 vue：UI 组件库由主程序全局注册，联邦 remote 不打包它，
    // 运行时直接从主程序实例取用，从而天然满足「联邦组件不得发布全局基础样式」的硬约束。
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
    port: 5004,
    cors: true,
    origin: 'http://localhost:5004',
  },
})
