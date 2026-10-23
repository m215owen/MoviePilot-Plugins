<template>
  <!--
    主界面全页面板（联邦暴露名 `./AppPage`，路由 `#/plugin-app/ShortDramaBaikeScraper/main`）。

    **本插件不实现 `get_sidebar_nav()`**：按用户要求不往左侧导航加入口，
    但宿主按 `get_render_mode()` 返回 `vue` 就会把这个路由配上，
    所以书签（或直接输地址）能进本页。
  -->
  <div class="sdbs-root pa-4">
    <div class="d-flex align-center flex-wrap mb-2" style="gap: 8px">
      <v-icon icon="mdi-television-classic" class="mr-1" />
      <h2 class="text-h6 ma-0">短剧百科刮削源</h2>
      <v-chip size="small" variant="tonal" color="primary">djbaike</v-chip>
      <v-chip size="small" variant="tonal">duanjubaike.net</v-chip>
      <v-spacer />
      <span class="text-caption sdbs-dim">
        ID 库与缓存是来源级全局数据（不按虚拟分身隔离）
      </span>
    </div>

    <PanelTabs :api="props.api" />
  </div>
</template>

<script setup lang="ts">
import PanelTabs from './PanelTabs.vue'
import type { PluginApi } from './types'

const props = defineProps<{
  /** 宿主注入的 axios 实例 */
  api?: PluginApi
  /** 插件 ID（宿主注入，本插件内为常量，仅为对齐官方入参） */
  pluginId?: string
  /** 侧栏入口 key（本插件无侧栏，恒为 main） */
  navKey?: string
}>()
</script>
