<template>
  <div class="pt-plugin-root pa-4">
    <div class="d-flex align-center mb-3">
      <v-icon icon="mdi-puzzle-outline" class="mr-2" />
      <h2 class="text-h6 ma-0">插件开发模板 · 全页视图</h2>
      <v-chip size="small" variant="tonal" class="ml-3">
        {{ pluginId || 'PluginTemplate' }} / {{ navKey || 'main' }}
      </v-chip>
      <v-spacer />
      <v-btn size="small" variant="tonal" icon="mdi-refresh" :loading="loading" @click="load" />
    </div>

    <v-row dense class="mb-3">
      <v-col cols="12" sm="4">
        <v-card variant="tonal" class="pa-3">
          <div class="text-caption">累计执行</div>
          <div class="text-h6">{{ config.run_count ?? records.length }}</div>
        </v-card>
      </v-col>
      <v-col cols="12" sm="4">
        <v-card variant="tonal" class="pa-3">
          <div class="text-caption">最近执行</div>
          <div class="text-body-2">{{ records[0]?.time || '暂无记录' }}</div>
        </v-card>
      </v-col>
      <v-col cols="12" sm="4">
        <v-card variant="tonal" class="pa-3">
          <div class="text-caption">插件状态</div>
          <div class="text-body-2">{{ config.enabled ? '已启用' : '未启用' }}</div>
        </v-card>
      </v-col>
    </v-row>

    <v-card variant="outlined">
      <v-card-title class="d-flex align-center flex-wrap">
        执行记录
        <v-spacer />
        <v-btn
          size="small"
          color="primary"
          variant="tonal"
          prepend-icon="mdi-play"
          :loading="running"
          @click="runNow"
        >
          立即执行
        </v-btn>
        <v-btn
          size="small"
          variant="tonal"
          class="ml-2"
          prepend-icon="mdi-delete-outline"
          @click="clearRecords"
        >
          清空
        </v-btn>
      </v-card-title>
      <v-card-text>
        <div v-if="!records.length" class="text-medium-emphasis">暂无执行记录。</div>
        <v-table v-else density="comfortable">
          <thead>
            <tr>
              <th>时间</th>
              <th>触发方式</th>
              <th>结果</th>
              <th>耗时</th>
              <th>说明</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(item, index) in records" :key="index">
              <td>{{ item.time }}</td>
              <td>
                <v-chip size="x-small" variant="tonal">{{ item.trigger }}</v-chip>
              </td>
              <td>
                <v-icon
                  :icon="item.success ? 'mdi-check-circle' : 'mdi-alert-circle'"
                  :color="item.success ? 'success' : 'error'"
                  size="18"
                />
              </td>
              <td>{{ item.elapsed_ms }} ms</td>
              <td class="text-body-2">{{ item.detail }}</td>
            </tr>
          </tbody>
        </v-table>
      </v-card-text>
    </v-card>
  </div>
</template>

<script setup lang="ts">
/**
 * 侧栏全页（联邦暴露名 ./AppPage，对应 nav_key = main）。
 *
 * 宿主路由为 `#/plugin-app/<pluginId>/<navKey>`，占据默认布局主内容区。
 * 与 Page 的区别：不嵌在插件管理弹窗中，可用于复杂交互与独立页面。
 */
import { onMounted, reactive, ref } from 'vue'
import { API_BASE, resolveApi, unwrap } from './api'
import type { ApiResult, PluginApi, PluginConfig, RunRecord } from './types'

const props = defineProps<{
  /** 宿主注入的 axios 实例 */
  api?: PluginApi
  /** 宿主原生订阅交互 */
  nativeSubscribe?: (mediaInfo: Record<string, unknown>) => Promise<unknown>
  /** 与侧栏声明的 nav_key 一致 */
  navKey?: string
  /** 当前插件实例 ID */
  pluginId?: string
}>()

const emit = defineEmits(['action'])

const loading = ref(false)
const running = ref(false)
const records = ref<RunRecord[]>([])
const config = reactive<PluginConfig>({
  enabled: false,
  cron: '',
  notify: false,
  message: '',
  max_records: 50,
})

/** 加载配置与记录 */
async function load() {
  const api = resolveApi(props)
  if (!api) return
  loading.value = true
  try {
    const [cfgRaw, recRaw] = await Promise.all([
      api.get(`${API_BASE}/config`),
      api.get(`${API_BASE}/records`, { params: { limit: 100 } }),
    ])
    const cfg = unwrap<ApiResult<PluginConfig>>(cfgRaw)
    if (cfg?.success && cfg.data) Object.assign(config, cfg.data)
    const rec = unwrap<ApiResult<RunRecord[]>>(recRaw)
    if (rec?.success) records.value = rec.data || []
  } catch (err) {
    console.warn('[PluginTemplate] 全页加载失败', err)
  } finally {
    loading.value = false
  }
}

/** 立即执行 */
async function runNow() {
  const api = resolveApi(props)
  if (!api) return
  running.value = true
  try {
    await api.post(`${API_BASE}/run`)
    await load()
    emit('action')
  } finally {
    running.value = false
  }
}

/** 清空记录 */
async function clearRecords() {
  const api = resolveApi(props)
  if (!api) return
  await api.post(`${API_BASE}/clear`)
  await load()
  emit('action')
}

onMounted(load)
</script>

<style scoped>
/* 仅使用 scoped 样式 */
.pt-plugin-root {
  max-width: 1400px;
}
</style>
