<template>
  <!--
    主界面侧栏全页（联邦暴露名 ./AppPage，nav_key = main）。

    宿主会在主界面左侧导航里挂一个入口，点击后加载本组件。面板本身与插件详情页完全同构，
    因此这里做成薄壳直接复用 Page，只额外开启整页留白（full）。
  -->
  <Panel
    :api="props.api"
    :config="props.config"
    :plugin-id="props.pluginId"
    :nav-key="props.navKey"
    mode="main"
    full
  />
</template>

<script setup lang="ts">
import Panel from './Page.vue'
import type { PluginApi, PluginConfig } from './types'

const props = defineProps<{
  /** 宿主注入的 axios 实例 */
  api?: PluginApi
  /** 插件配置 */
  config?: Partial<PluginConfig>
  /** 当前插件实例 ID */
  pluginId?: string
  /** 当前侧栏入口的 nav_key（main / settings…） */
  navKey?: string
}>()
</script>
