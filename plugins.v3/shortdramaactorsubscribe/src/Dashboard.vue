<template>
  <div class="sdas-root sdas-dash">
    <v-card variant="flat" class="sdas-dash-card">
      <div class="d-flex align-center pa-3 pb-1">
        <v-icon icon="mdi-movie-star-outline" size="20" class="mr-2" />
        <span class="text-body-1">短剧演员订阅</span>
        <v-spacer />
        <v-btn
          v-if="props.allowRefresh !== false"
          icon="mdi-refresh"
          variant="text"
          size="x-small"
          :loading="running"
          title="立即运行一轮"
          @click="doRun"
        />
      </div>

      <div class="px-3 pb-3">
        <div v-if="!enabled" class="text-medium-emphasis text-body-2">
          插件未启用或尚未配置演员 / 搜索站点。
        </div>
        <template v-else>
          <div class="d-flex align-center flex-wrap mb-2" style="gap: 12px">
            <span class="text-caption">演员 <b>{{ summary.actor_count || 0 }}</b></span>
            <span class="text-caption">已下载 <b>{{ summary.downloaded_count || 0 }}</b></span>
            <span class="text-caption">已整理 <b>{{ summary.organized_count || 0 }}</b></span>
            <span v-if="summary.cooldown_count" class="text-caption sdas-dim">
              冷却 {{ summary.cooldown_count }}
            </span>
          </div>

          <div v-if="!latest.length" class="text-caption text-medium-emphasis">
            还没有下载记录，点右上角运行一轮。
          </div>
          <div v-for="row in latest" :key="row.key" class="d-flex align-center py-1">
            <span class="sdas-dot" :class="row.organized ? 'sdas-dot-done' : ''" />
            <span class="sdas-name" :title="row.torrent_title || row.title">{{ row.title }}</span>
            <span class="text-caption sdas-dim ml-2">{{ row.year || '—' }}</span>
            <v-spacer />
            <span class="text-caption sdas-dim">{{ row.organized ? '已整理' : '已下载' }}</span>
          </div>

          <div class="text-caption sdas-dim mt-2">
            {{ summary.actor_count || 0 }} 位演员｜{{ formatTime(summary.last_run) }}
          </div>
        </template>
      </div>
    </v-card>
  </div>
</template>

<script setup lang="ts">
/**
 * 仪表板小组件（联邦暴露名 ./Dashboard）。
 *
 * 由宿主在仪表板中挂载；Vue 模式下后端 `get_dashboard()` 只提供卡片元信息，
 * 内容由本组件渲染。这里聚焦「近况一瞥 + 一键运行」这一最常用动作。
 */
import { computed, onMounted, ref } from 'vue'
import { fetchStatus, formatTime, PLUGIN_ID, resolveApi, runOnce } from './api'
import type { PluginApi, PluginConfig, StatusPayload } from './types'

const props = defineProps<{
  /** 插件配置 */
  config?: Partial<PluginConfig>
  /** 是否显示运行按钮 */
  allowRefresh?: boolean
  /** 宿主注入的 axios 实例 */
  api?: PluginApi
  /** 当前插件实例 ID */
  pluginId?: string
}>()

const LIMIT = 4

const running = ref(false)
const payload = ref<StatusPayload | null>(null)

const enabled = computed(() => payload.value?.enabled ?? props.config?.enabled ?? false)
const summary = computed(() => payload.value?.summary || ({} as StatusPayload['summary']))
const latest = computed(() => (payload.value?.ledger || []).slice(0, LIMIT))

function apply(data: StatusPayload): void {
  payload.value = data
}

async function load(): Promise<void> {
  const api = resolveApi(props)
  if (!api) return
  try {
    const data = await fetchStatus(api)
    if (data) apply(data)
  } catch (err) {
    console.warn(`[${PLUGIN_ID}] 仪表板加载失败`, err)
  }
}

async function doRun(): Promise<void> {
  const api = resolveApi(props)
  if (!api) return
  running.value = true
  try {
    const before = String(summary.value.last_run || '')
    await runOnce(api, apply, before)
    await load()
  } finally {
    running.value = false
  }
}

onMounted(load)
</script>

<style scoped>
/* 只使用 scoped 样式；不要编写全局生效的选择器 */
.sdas-root {
  position: relative;
}

.sdas-dash-card {
  height: 100%;
}

.sdas-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background-color: rgba(128, 128, 128, 0.5);
  margin-right: 8px;
  flex: 0 0 auto;
}

.sdas-dot-done {
  background-color: rgb(var(--v-theme-success, 76 175 80));
}

.sdas-name {
  font-size: 0.8rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sdas-dim {
  opacity: 0.7;
}
</style>
