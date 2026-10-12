<template>
  <div class="pt-plugin-root pa-2">
    <v-card variant="outlined" class="pa-4">
      <div class="d-flex align-center mb-3">
        <v-icon icon="mdi-cog-outline" class="mr-2" />
        <h3 class="ma-0">插件开发模板 · 设置</h3>
        <v-spacer />
        <v-btn
          icon="mdi-close"
          variant="text"
          size="small"
          title="关闭"
          @click="emit('close')"
        />
      </div>

      <v-switch
        v-model="local.enabled"
        label="启用插件"
        color="primary"
        hide-details
        class="mb-2"
      />

      <v-text-field
        v-model="local.message"
        label="示例文本"
        hint="业务代码可将其替换为真实配置项"
        persistent-hint
        density="comfortable"
        class="mb-4"
      />

      <v-row dense>
        <v-col cols="12" md="6">
          <v-select
            v-model="cronPreset"
            :items="cronPresets"
            item-title="label"
            item-value="value"
            label="定时周期预设"
            density="comfortable"
          />
        </v-col>
        <v-col cols="12" md="6">
          <v-text-field
            v-model="local.cron"
            label="cron 表达式"
            hint="5 段式，例如 0 */6 * * * 表示每 6 小时"
            persistent-hint
            density="comfortable"
          />
        </v-col>
      </v-row>

      <v-text-field
        v-model.number="local.max_records"
        type="number"
        label="执行记录保留条数"
        min="5"
        max="500"
        density="comfortable"
        class="mt-4"
      />

      <v-switch
        v-model="local.notify"
        label="任务完成后发送系统通知"
        color="primary"
        hide-details
      />

      <v-checkbox
        v-model="local.onlyonce"
        label="保存后立即执行一次"
        hide-details
        density="compact"
        class="mb-3"
      />

      <v-alert type="info" variant="tonal" density="compact" class="mb-3">
        保存由宿主完成：本组件只向宿主抛出 <code>save</code> 事件，
        宿主会调用 <code>api.put('plugin/{id}', cfg)</code> 持久化并重新初始化插件。
      </v-alert>

      <div class="d-flex">
        <v-btn color="primary" :loading="saving" @click="saveConfig">保存配置</v-btn>
        <v-btn variant="text" class="ml-2" @click="emit('switch')">查看详情</v-btn>
      </div>
    </v-card>
  </div>
</template>

<script setup lang="ts">
/**
 * 插件配置页（联邦暴露名 ./Config）。
 *
 * 保存方式遵循官方约定：`emit('save', cfg)`，由宿主统一持久化，
 * 不要在组件内自行拼接 `api/v1/plugin/...` 路径。
 */
import { computed, onMounted, reactive, ref } from 'vue'
import type { PluginApi, PluginConfig } from './types'

const props = defineProps<{
  /** 宿主传入的初始配置 */
  initialConfig?: Partial<PluginConfig>
  /** 宿主注入的 axios 实例 */
  api?: PluginApi
}>()

const emit = defineEmits(['save', 'close', 'switch'])

const saving = ref(false)

const defaults: PluginConfig = {
  enabled: false,
  cron: '0 */6 * * *',
  notify: false,
  message: 'Hello MoviePilot',
  max_records: 50,
  onlyonce: false,
}

const local = reactive<PluginConfig>({ ...defaults })

/** 常用 cron 预设，便于快速选择 */
const cronPresets = [
  { label: '每 30 分钟', value: '*/30 * * * *' },
  { label: '每 1 小时', value: '0 * * * *' },
  { label: '每 6 小时', value: '0 */6 * * *' },
  { label: '每天 03:00', value: '0 3 * * *' },
  { label: '每周一 03:00', value: '0 3 * * 1' },
  { label: '每月 1 日 03:00', value: '0 3 1 * *' },
]

/** 预设与自定义 cron 的双向绑定 */
const cronPreset = computed({
  get: () => (cronPresets.some((item) => item.value === local.cron) ? local.cron : ''),
  set: (value: string) => {
    if (value) local.cron = value
  },
})

/** 提交保存：交给宿主持久化 */
function saveConfig() {
  saving.value = true
  emit('save', JSON.parse(JSON.stringify(local)))
  // 宿主保存是异步的，这里给出即时反馈并复位按钮状态
  window.setTimeout(() => {
    saving.value = false
  }, 600)
}

onMounted(() => {
  const initial = props.initialConfig
  if (initial && typeof initial === 'object') {
    Object.keys(defaults).forEach((key) => {
      const value = (initial as Record<string, unknown>)[key]
      if (value !== undefined) {
        ;(local as Record<string, unknown>)[key] = value
      }
    })
  }
})
</script>

<style scoped>
/* 仅 scoped 样式：不要编写会全局生效的选择器（Vuetify 组件类名、html、body、:root） */
</style>
