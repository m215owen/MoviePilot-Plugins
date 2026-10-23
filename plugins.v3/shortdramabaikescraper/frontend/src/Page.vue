<template>
  <!--
    插件管理里的详情弹窗（联邦暴露名 `./Page`）。

    Vue 渲染模式下**这个组件必须有**：管理面板弹出详情时宿主找的就是它，
    缺了就是一个空白弹窗。内容与全页同一套 `PanelTabs`，只是外面套一层紧凑标题栏
    （弹窗已经给了边框，这里不再加卡片，免得出现「框套框」）。
  -->
  <div class="sdbs-root pa-2">
    <div class="d-flex align-center flex-wrap mb-2" style="gap: 8px">
      <v-icon icon="mdi-television-classic" class="mr-1" />
      <h3 class="text-subtitle-1 ma-0">短剧百科刮削源</h3>
      <v-chip size="x-small" variant="tonal" color="primary">djbaike</v-chip>
      <v-spacer />
      <v-btn
        size="x-small"
        variant="text"
        prepend-icon="mdi-open-in-new"
        :href="appHref"
        target="_blank"
        rel="noreferrer noopener"
        title="在独立页面打开（书签可存）"
      >
        全页打开
      </v-btn>
    </div>

    <PanelTabs :api="props.api" />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { PLUGIN_ID } from './api'
import PanelTabs from './PanelTabs.vue'
import type { PluginApi } from './types'

const props = defineProps<{
  /** 宿主注入的 axios 实例 */
  api?: PluginApi
}>()

/**
 * 全页入口的地址。
 *
 * 不实现 `get_sidebar_nav()` 时左侧导航没有入口，`#/plugin-app/<id>/main`
 * 就是唯一去处 —— 在弹窗里给一个链接，用户才有办法把它存成书签。
 */
const appHref = computed(() => {
  const base = typeof window === 'undefined' ? '' : window.location.href.split('#')[0]
  return `${base}#/plugin-app/${PLUGIN_ID}/main`
})
</script>
