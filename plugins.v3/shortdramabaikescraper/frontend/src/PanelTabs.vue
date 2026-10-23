<template>
  <!--
    面板外壳：四个分区（计划 §6.5）。

      ① 概览   `/status` 的计数与命中率 —— 打开面板第一眼就该知道「现状」
      ② ID 库  `baike` 表原样 4 列，可模糊搜 / 删单条 / 清空
      ③ 缓存   6 个 region 的原始键值，可删单条 / 清空全部
      ④ 查询   `/lookup`：id 出详情、名字出候选

    分区是**懒挂载 + 常驻**：第一次点开才发请求，之后切走不销毁（`v-show`），
    所以来回切不会反复打后端，也不会丢掉「我筛到哪一页了」这种现场。
  -->
  <div class="sdbs-tabs">
    <v-tabs v-model="active" density="compact" color="primary" show-arrows>
      <v-tab value="overview" prepend-icon="mdi-view-dashboard-outline">概览</v-tab>
      <v-tab value="baike" prepend-icon="mdi-database-outline">ID 库</v-tab>
      <v-tab value="cache" prepend-icon="mdi-cached">缓存</v-tab>
      <v-tab value="query" prepend-icon="mdi-magnify">查询</v-tab>
    </v-tabs>
    <v-divider />

    <div class="pa-3">
      <OverviewPanel v-if="visited.has('overview')" v-show="active === 'overview'" :api="props.api" />
      <BaikePanel
        v-if="visited.has('baike')"
        v-show="active === 'baike'"
        :api="props.api"
        @lookup="openLookup"
      />
      <CachePanel v-if="visited.has('cache')" v-show="active === 'cache'" :api="props.api" />
      <QueryPanel v-if="visited.has('query')" v-show="active === 'query'" ref="queryRef" :api="props.api" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'
import BaikePanel from './BaikePanel.vue'
import CachePanel from './CachePanel.vue'
import OverviewPanel from './OverviewPanel.vue'
import QueryPanel from './QueryPanel.vue'
import type { PanelTab, PluginApi } from './types'
// 四个分区共用的排版样式：全局一份、带 `.sdbs-` 前缀，只在此处引入一次
import './panel.css'

const props = defineProps<{
  /** 宿主注入的 axios 实例 */
  api?: PluginApi
}>()

const active = ref<PanelTab>('overview')
/** 已挂载过的分区（懒挂载的判据） */
const visited = ref<Set<PanelTab>>(new Set<PanelTab>(['overview']))

const queryRef = ref<InstanceType<typeof QueryPanel> | null>(null)

watch(active, (tab) => {
  // 先登记再渲染：`v-if` 依赖这份 set
  const next = new Set(visited.value)
  next.add(tab)
  visited.value = next
})

/**
 * ID 库里点「查详情」：切到查询分区，并直接把那个 media_id 查出来。
 *
 * 顺序很重要：先切分区 → 等 DOM 更新（`QueryPanel` 可能是第一次挂载，
 * 此时 `queryRef` 还是 null）→ 再调它的 `query()`。少一步就是「切过去了但没查」。
 */
async function openLookup(mediaId: string): Promise<void> {
  active.value = 'query'
  await nextTick()
  queryRef.value?.query(mediaId)
}
</script>
