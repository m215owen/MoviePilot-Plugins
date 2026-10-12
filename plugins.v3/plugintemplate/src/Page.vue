<template>
  <div class="pt-plugin-root pt-page pa-2">
    <!-- 运行状态概览 -->
    <v-card variant="outlined" class="mb-3">
      <v-card-title class="d-flex align-center">
        <v-icon icon="mdi-puzzle-outline" class="mr-2" />
        插件开发模板
        <v-spacer />
        <v-btn
          size="small"
          variant="text"
          icon="mdi-refresh"
          :loading="loading"
          @click="loadAll"
        />
      </v-card-title>
      <v-card-text>
        <v-alert
          :type="config.enabled ? 'success' : 'warning'"
          variant="tonal"
          density="compact"
          class="mb-3"
        >
          {{ config.enabled ? config.message : '插件未启用，执行任务会被跳过。' }}
        </v-alert>

        <v-row dense>
          <v-col cols="12" sm="4">
            <v-card variant="tonal" class="pa-3">
              <div class="text-caption">累计执行</div>
              <div class="text-h6">{{ records.length }}</div>
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
              <div class="text-caption">定时周期（cron）</div>
              <div class="text-body-2">{{ config.cron }}</div>
            </v-card>
          </v-col>
        </v-row>
      </v-card-text>
    </v-card>

    <!-- 执行记录 -->
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
        <v-table v-else density="compact">
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
                <v-chip size="x-small" variant="tonal">{{ triggerLabel(item.trigger) }}</v-chip>
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

    <!-- 宿主交互：switch 切到配置页，close 关闭弹窗，action 通知刷新 -->
    <div class="d-flex mt-3">
      <v-btn size="small" variant="text" @click="emit('switch')">配置插件</v-btn>
      <v-btn size="small" variant="text" @click="emit('action')">通知宿主刷新</v-btn>
      <v-btn size="small" variant="text" @click="emit('close')">关闭</v-btn>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * 插件详情页（联邦暴露名 ./Page）。
 *
 * 通过宿主注入的 `api` prop 调用插件后端接口：
 *   GET  plugin/PluginTemplate/config   读取配置
 *   GET  plugin/PluginTemplate/records  读取执行记录
 *   POST plugin/PluginTemplate/run      立即执行
 *   POST plugin/PluginTemplate/clear    清空记录
 */
import { onMounted, reactive, ref } from 'vue'
import { API_BASE, resolveApi, unwrap } from './api'
import type { ApiResult, PluginApi, PluginConfig, RunRecord } from './types'

const props = defineProps<{
  /** 宿主注入的 axios 实例（实例作用域） */
  api?: PluginApi
  /** 宿主原生订阅交互（本模板未使用，保留以示意可用能力） */
  nativeSubscribe?: (mediaInfo: Record<string, unknown>) => Promise<unknown>
  /** 当前插件实例 ID */
  pluginId?: string
}>()

const emit = defineEmits(['action', 'switch', 'close'])

const loading = ref(false)
const running = ref(false)
const records = ref<RunRecord[]>([])
const config = reactive<PluginConfig>({
  enabled: false,
  cron: '0 */6 * * *',
  notify: false,
  message: 'Hello MoviePilot',
  max_records: 50,
})

/** 触发方式的中文展示 */
function triggerLabel(trigger: string): string {
  const map: Record<string, string> = {
    manual: '手动',
    cron: '定时',
    command: '远程命令',
    workflow: '工作流',
    api: '接口',
    once: '启用即执行',
  }
  return map[trigger] || trigger
}

/** 读取配置与记录 */
async function loadAll() {
  const api = resolveApi(props)
  if (!api) return
  loading.value = true
  try {
    const [cfgRaw, recRaw] = await Promise.all([
      api.get(`${API_BASE}/config`),
      api.get(`${API_BASE}/records`, { params: { limit: 50 } }),
    ])
    const cfg = unwrap<ApiResult<PluginConfig>>(cfgRaw)
    if (cfg?.success && cfg.data) Object.assign(config, cfg.data)
    const rec = unwrap<ApiResult<RunRecord[]>>(recRaw)
    if (rec?.success) records.value = rec.data || []
  } catch (err) {
    // 读取失败不影响页面渲染，保留占位内容
    console.warn('[PluginTemplate] 加载数据失败', err)
  } finally {
    loading.value = false
  }
}

/** 立即执行一次任务 */
async function runNow() {
  const api = resolveApi(props)
  if (!api) return
  running.value = true
  try {
    await api.post(`${API_BASE}/run`)
    await loadAll()
    emit('action')
  } finally {
    running.value = false
  }
}

/** 清空执行记录 */
async function clearRecords() {
  const api = resolveApi(props)
  if (!api) return
  await api.post(`${API_BASE}/clear`)
  await loadAll()
  emit('action')
}

onMounted(loadAll)
</script>

<style scoped>
/* 仅使用 scoped 样式；不要编写会全局生效的选择器（Vuetify 组件类名、html、body、:root） */
.pt-page {
  max-width: 100%;
}
</style>
