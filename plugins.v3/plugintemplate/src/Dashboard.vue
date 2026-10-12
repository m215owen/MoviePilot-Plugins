<template>
  <div class="pt-plugin-root">
    <v-hover>
      <template #default="{ isHovering, props: hoverProps }">
        <v-card v-bind="hoverProps" variant="flat">
          <v-card-title class="d-flex align-center">
            <v-icon icon="mdi-puzzle-outline" size="20" class="mr-2" />
            {{ title }}
            <v-spacer />
            <v-btn
              v-if="allowRefresh"
              icon="mdi-refresh"
              variant="text"
              size="x-small"
              :loading="loading"
              @click="load"
            />
          </v-card-title>
          <v-card-text>
            <div v-if="!enabled" class="text-medium-emphasis text-body-2">
              插件未启用。
            </div>
            <template v-else>
              <div class="d-flex align-center mb-1">
                <span class="text-caption mr-2">累计执行</span>
                <span class="text-h6">{{ total }}</span>
              </div>
              <div class="text-caption">最近执行：{{ lastTime }}</div>
              <div v-if="lastDetail" class="text-caption text-medium-emphasis mt-1">
                {{ lastDetail }}
              </div>
            </template>
          </v-card-text>
          <!-- 悬停时显示拖拽提示，与其他仪表板组件保持一致 -->
          <div v-show="isHovering" class="pt-drag-hint">
            <v-icon icon="mdi-drag" size="18" />
          </div>
        </v-card>
      </template>
    </v-hover>
  </div>
</template>

<script setup lang="ts">
/**
 * 仪表板小组件（联邦暴露名 ./Dashboard）。
 *
 * 由宿主在仪表板中挂载，通过 `api` prop 拉取插件状态；
 * Vue 模式下后端 get_dashboard() 只提供卡片元信息，内容由本组件渲染。
 */
import { computed, onMounted, ref } from 'vue'
import { API_BASE, resolveApi, unwrap } from './api'
import type { ApiResult, PluginApi, PluginConfig, RunRecord } from './types'

const props = defineProps<{
  /** 插件配置 */
  config?: Partial<PluginConfig>
  /** 是否显示刷新按钮 */
  allowRefresh?: boolean
  /** 宿主注入的 axios 实例 */
  api?: PluginApi
  /** 当前插件实例 ID */
  pluginId?: string
}>()

const loading = ref(false)
const records = ref<RunRecord[]>([])

const title = computed(() => '插件开发模板')
const enabled = computed(() => props.config?.enabled !== false)
const total = computed(() => props.config?.run_count ?? records.value.length)
const lastTime = computed(() => records.value[0]?.time || '暂无记录')
const lastDetail = computed(() => records.value[0]?.detail || '')

/** 拉取最近记录 */
async function load() {
  const api = resolveApi(props)
  if (!api) return
  loading.value = true
  try {
    const raw = await api.get(`${API_BASE}/records`, { params: { limit: 5 } })
    const res = unwrap<ApiResult<RunRecord[]>>(raw)
    if (res?.success) records.value = res.data || []
  } catch (err) {
    console.warn('[PluginTemplate] 仪表板加载失败', err)
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
/* 为绝对定位的拖拽提示提供定位上下文；不要编写全局生效的选择器 */
.pt-plugin-root {
  position: relative;
}
.pt-drag-hint {
  position: absolute;
  right: 12px;
  top: 12px;
  opacity: 0.6;
  cursor: move;
}
</style>
