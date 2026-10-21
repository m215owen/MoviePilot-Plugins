<template>
  <span v-if="count">
    <v-chip
      size="small"
      variant="tonal"
      prepend-icon="mdi-eye-off-outline"
      title="查看并恢复被忽略的作品"
      @click="open = true"
    >
      已忽略 {{ count }} 部
    </v-chip>

    <v-dialog v-model="open" max-width="640">
      <v-card>
        <v-card-title class="d-flex align-center">
          <v-icon icon="mdi-eye-off-outline" class="mr-2" />
          <span class="text-body-1">已忽略的作品</span>
          <v-spacer />
          <v-btn size="small" variant="text" @click="open = false">关闭</v-btn>
        </v-card-title>
        <v-divider />
        <v-card-text class="das-scroll">
          <div v-if="!list.length" class="text-medium-emphasis text-body-2 py-4 text-center">
            还没有忽略任何作品。
          </div>
          <div v-for="item in list" :key="item.key" class="d-flex align-center py-1">
            <span class="text-body-2 das-ellipsis" :title="item.title || item.key">
              {{ item.title || item.media_id || item.key }}
            </span>
            <span v-if="item.year" class="text-caption das-dim mx-2">{{ item.year }}</span>
            <v-chip v-if="item.type" size="x-small" variant="tonal" label class="mr-2">
              {{ item.type }}
            </v-chip>
            <v-spacer />
            <v-btn
              size="x-small"
              variant="text"
              color="primary"
              :loading="busyKey === item.key"
              :disabled="busyAll"
              @click="restore(item)"
            >
              恢复
            </v-btn>
          </div>
        </v-card-text>
        <v-divider />
        <v-card-actions>
          <span class="text-caption das-dim ml-2">恢复后下次刷新即会重新出现</span>
          <v-spacer />
          <v-btn
            size="small"
            variant="text"
            color="warning"
            :loading="busyAll"
            :disabled="!list.length"
            @click="restoreAll"
          >
            全部恢复
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </span>
</template>

<script setup lang="ts">
/**
 * 「已忽略的作品」入口与管理弹窗（内部复用组件，不作为联邦暴露入口）。
 *
 * 作品的忽略状态由后端持久化，这里只负责查看与恢复——
 * 有恢复入口才不会让一次误点变成永久丢失。
 */
import { computed, inject, ref } from 'vue'
import { PLUGIN_ID, resolveApi, unignoreWork } from './api'
import type { IgnoredWork, PluginApi } from './types'

interface HostToast {
  success(message: string): unknown
  info(message: string): unknown
  warning(message: string): unknown
  error(message: string): unknown
}

const props = defineProps<{
  api?: PluginApi
  /** 已忽略作品明细 */
  ignored?: IgnoredWork[]
  /** 已忽略数量（后端给的总数） */
  count?: number
}>()

const emit = defineEmits<{ (e: 'changed'): void }>()

const toast = inject<HostToast | null>('moviepilot:toast', null)

const open = ref(false)
const busyKey = ref('')
const busyAll = ref(false)

const list = computed<IgnoredWork[]>(() => props.ignored || [])

function notify(type: 'success' | 'error', message: string): void {
  const handler = toast && (toast as unknown as Record<string, unknown>)[type]
  if (typeof handler === 'function') {
    ;(handler as (msg: string) => unknown).call(toast, message)
    return
  }
  console[type === 'error' ? 'warn' : 'info'](`[${PLUGIN_ID}] ${message}`)
}

/** 恢复单部作品 */
async function restore(item: IgnoredWork): Promise<void> {
  const api = resolveApi(props)
  if (!api) return
  busyKey.value = item.key
  try {
    const res = await unignoreWork(api, item.key)
    notify(res.ok ? 'success' : 'error', res.message)
    if (res.ok) emit('changed')
  } finally {
    busyKey.value = ''
  }
}

/** 一次性恢复全部被忽略的作品 */
async function restoreAll(): Promise<void> {
  const api = resolveApi(props)
  if (!api) return
  busyAll.value = true
  try {
    const res = await unignoreWork(api, '', true)
    notify(res.ok ? 'success' : 'error', res.message)
    if (res.ok) emit('changed')
  } finally {
    busyAll.value = false
  }
}
</script>

<style scoped>
.das-dim {
  opacity: 0.75;
}

.das-scroll {
  max-height: 60vh;
  overflow-y: auto;
}

.das-ellipsis {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0;
  flex: 1 1 auto;
}
</style>
