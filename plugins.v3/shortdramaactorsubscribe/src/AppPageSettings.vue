<template>
  <!--
    主界面侧栏「运行状态」全页（联邦暴露名 ./AppPageSettings，nav_key = settings）。

    与主面板（AppPage）同源，只是切到只读概览模式：看运行摘要、演员解析状态与当前配置，
    不做任何写操作，适合放在侧栏当「一眼看状态」的入口。
  -->
  <Panel
    :api="props.api"
    :config="props.config"
    :plugin-id="props.pluginId"
    :nav-key="props.navKey"
    mode="status"
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
