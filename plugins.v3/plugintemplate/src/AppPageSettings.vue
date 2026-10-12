<template>
  <div class="pt-plugin-root pa-4">
    <div class="d-flex align-center mb-3">
      <v-icon icon="mdi-cog-outline" class="mr-2" />
      <h2 class="text-h6 ma-0">插件开发模板 · 设置全页</h2>
      <v-chip size="small" variant="tonal" class="ml-3">
        {{ pluginId || 'PluginTemplate' }} / {{ navKey || 'settings' }}
      </v-chip>
      <v-spacer />
      <v-btn size="small" variant="tonal" icon="mdi-refresh" :loading="loading" @click="load" />
    </div>

    <v-card variant="outlined" class="pa-4" max-width="820">
      <v-alert type="info" variant="tonal" density="compact" class="mb-3">
        本页演示「多 nav_key 全页」与「组件内直接调用插件 API」：
        保存通过 <code>PUT {{ API_BASE }}/config</code> 完成。
      </v-alert>

      <v-switch v-model="local.enabled" label="启用插件" color="primary" hide-details class="mb-2" />

      <v-text-field
        v-model="local.message"
        label="示例文本"
        density="comfortable"
        class="mb-2"
      />

      <v-text-field
        v-model="local.cron"
        label="cron 表达式"
        hint="5 段式，例如 0 */6 * * *"
        persistent-hint
        density="comfortable"
        class="mb-3"
      />

      <v-text-field
        v-model.number="local.max_records"
        type="number"
        label="执行记录保留条数"
        min="5"
        max="500"
        density="comfortable"
        class="mb-2"
      />

      <v-switch v-model="local.notify" label="任务完成后发送系统通知" color="primary" hide-details />

      <div class="d-flex mt-3">
        <v-btn color="primary" :loading="saving" @click="save">保存配置</v-btn>
        <v-btn variant="text" class="ml-2" @click="load">放弃修改</v-btn>
      </div>
    </v-card>
  </div>
</template>

<script setup lang="ts">
/**
 * 侧栏全页 · 设置入口（联邦暴露名 ./AppPageSettings，对应 nav_key = settings）。
 *
 * 主程序按 nav_key 的 PascalCase 优先解析暴露名，因此 `settings` → `./AppPageSettings`。
 * 与 Config.vue 不同，这里演示在组件内直接调用插件 API 保存配置，
 * 并通过宿主注入的 Toast 反馈结果。
 */
import { inject, onMounted, reactive, ref } from 'vue'
import { API_BASE, resolveApi, unwrap } from './api'
import type { ApiResult, PluginApi, PluginConfig } from './types'

/** 宿主统一 Toast（键名固定为 moviepilot:toast） */
interface HostToast {
  success(message: string): unknown
  info(message: string): unknown
  warning(message: string): unknown
  error(message: string): unknown
}

const props = defineProps<{
  api?: PluginApi
  nativeSubscribe?: (mediaInfo: Record<string, unknown>) => Promise<unknown>
  navKey?: string
  pluginId?: string
}>()

const toast = inject<HostToast | null>('moviepilot:toast', null)

const loading = ref(false)
const saving = ref(false)

const defaults: PluginConfig = {
  enabled: false,
  cron: '0 */6 * * *',
  notify: false,
  message: 'Hello MoviePilot',
  max_records: 50,
}

const local = reactive<PluginConfig>({ ...defaults })

/** 读取当前配置 */
async function load() {
  const api = resolveApi(props)
  if (!api) {
    toast?.error('宿主 API 未就绪')
    return
  }
  loading.value = true
  try {
    const raw = await api.get(`${API_BASE}/config`)
    const res = unwrap<ApiResult<PluginConfig>>(raw)
    if (res?.success && res.data) Object.assign(local, res.data)
  } catch (err) {
    toast?.error('读取配置失败')
    console.warn('[PluginTemplate] 读取配置失败', err)
  } finally {
    loading.value = false
  }
}

/** 保存配置到插件后端 */
async function save() {
  const api = resolveApi(props)
  if (!api) {
    toast?.error('宿主 API 未就绪')
    return
  }
  saving.value = true
  try {
    const raw = await api.put(`${API_BASE}/config`, { ...local })
    const res = unwrap<ApiResult<PluginConfig>>(raw)
    if (res?.success) {
      if (res.data) Object.assign(local, res.data)
      toast?.success('配置已保存')
    } else {
      toast?.error(res?.message || '保存失败')
    }
  } catch (err) {
    toast?.error('保存失败')
    console.warn('[PluginTemplate] 保存配置失败', err)
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<style scoped>
/* 仅使用 scoped 样式 */
.pt-plugin-root {
  max-width: 1400px;
}
</style>
