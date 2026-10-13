<template>
  <div class="das-root das-dash">
    <v-hover>
      <template #default="{ isHovering, props: hoverProps }">
        <v-card v-bind="hoverProps" variant="flat" class="das-dash-card">
          <v-card-title class="d-flex align-center">
            <v-icon icon="mdi-account-star-outline" size="20" class="mr-2" />
            <span class="text-body-1">豆瓣演员订阅</span>
            <v-spacer />
            <v-btn
              v-if="allowRefresh"
              icon="mdi-refresh"
              variant="text"
              size="x-small"
              :loading="refreshing"
              @click="refresh"
            />
          </v-card-title>

          <v-card-text>
            <div v-if="!enabled" class="text-medium-emphasis text-body-2">
              插件未启用或尚未配置演员。
            </div>
            <template v-else>
              <div class="d-flex align-center mb-2" style="gap: 12px">
                <span class="text-caption">演员 <b>{{ stats.actor_count }}</b></span>
                <span class="text-caption">作品 <b>{{ stats.work_count }}</b></span>
                <span class="text-caption">
                  {{ stats.new_label }} <b class="das-new">{{ stats.new_count }}</b>
                </span>
              </div>

              <div v-if="!latest.length" class="text-caption text-medium-emphasis">
                暂无作品数据，点击右上角刷新。
              </div>
              <div
                v-for="item in latest"
                :key="workKey(item.work)"
                class="d-flex align-center py-1"
              >
                <span class="das-dot" :class="item.work.is_new ? 'das-dot-new' : ''" />
                <span class="das-name" :title="item.work.title">{{ item.work.title }}</span>
                <span class="text-caption das-dim ml-2">{{ item.work.year || '—' }}</span>
                <v-spacer />
                <v-btn
                  size="x-small"
                  variant="text"
                  :icon="isSubscribed(item.work) ? 'mdi-close' : 'mdi-plus'"
                  :color="isSubscribed(item.work) ? 'error' : 'primary'"
                  :loading="pendingKey === workKey(item.work)"
                  :title="isSubscribed(item.work) ? '取消订阅' : '订阅'"
                  @click="isSubscribed(item.work) ? unsubscribe(item.work) : subscribe(item.work)"
                />
                <SearchResourceButton :api="api" :work="item.work" size="x-small" variant="text" />
                <v-btn
                  size="x-small"
                  variant="text"
                  icon="mdi-eye-off-outline"
                  title="忽略这部作品：不再展示，也不会被自动订阅"
                  @click="ignore(item.work)"
                />
              </div>

              <div class="text-caption das-dim mt-2">
                {{ item0.actor }} 等 {{ stats.actor_count }} 位演员｜{{ formatTime(stats.updated_at) }}
              </div>
            </template>
          </v-card-text>

          <!-- 悬停时显示拖拽提示，与其他仪表板组件保持一致 -->
          <div v-show="isHovering" class="das-drag-hint">
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
 * 由宿主在仪表板中挂载；Vue 模式下后端 get_dashboard() 只提供卡片元信息，
 * 内容由本组件渲染。这里聚焦「新作品 + 一键订阅」这一最常用动作。
 */
import { computed, inject, onMounted, ref } from 'vue'
import SearchResourceButton from './SearchResourceButton.vue'
import {
  API_BASE,
  PLUGIN_ID,
  fetchSubscribedKeys,
  formatTime,
  ignoreWork,
  mergeWorks,
  resolveApi,
  sortWorks,
  submitSubscribe,
  unsubscribeWork,
  unwrap,
  waitForRefresh,
  workKey,
} from './api'
import type { ActorWork, ApiResult, PluginApi, PluginConfig, WorksPayload } from './types'

interface HostToast {
  success(message: string): unknown
  info(message: string): unknown
  warning(message: string): unknown
  error(message: string): unknown
}

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

const toast = inject<HostToast | null>('moviepilot:toast', null)

const LIMIT = 4

const loading = ref(false)
const refreshing = ref(false)
const pendingKey = ref('')
const payload = ref<WorksPayload | null>(null)
const subscribedKeys = ref<string[]>([])

const enabled = computed(() => payload.value?.enabled ?? props.config?.enabled !== false)

/** 「新作品」的口径（首次发现距今几天内）由后端下发，跟着一起展示，避免误判成坏了 */
const newWindowLabel = computed(() => {
  const days = Number(payload.value?.new_window_days || 0)
  return days > 0 ? `近 ${days} 天新作品` : '新作品'
})

const stats = computed(() => ({
  actor_count: payload.value?.actor_count ?? 0,
  work_count: payload.value?.work_count ?? 0,
  new_count: payload.value?.new_count ?? 0,
  updated_at: payload.value?.updated_at || '',
  new_label: newWindowLabel.value,
}))

/** 展平后的作品：按作品去重（同一部作品可能挂在多位演员名下），新作品优先 */
const flattened = computed(() => {
  const works = mergeWorks(payload.value?.actors || [])
  return sortWorks(works, 'new').map((work) => ({
    actor: (work.actorNames || [])[0] || '—',
    work,
  }))
})

const latest = computed(() => flattened.value.slice(0, LIMIT))
const item0 = computed(() => ({ actor: latest.value[0]?.actor || '未配置演员' }))

function isSubscribed(work: ActorWork): boolean {
  return subscribedKeys.value.includes(workKey(work))
}

function notify(type: 'success' | 'error', message: string): void {
  const handler = toast && (toast as unknown as Record<string, unknown>)[type]
  if (typeof handler === 'function') {
    ;(handler as (msg: string) => unknown).call(toast, message)
    return
  }
  console.warn(`[${PLUGIN_ID}] ${message}`)
}

async function load(): Promise<void> {
  const api = resolveApi(props)
  if (!api) return
  loading.value = true
  try {
    const raw = await api.get(`${API_BASE}/works`)
    const res = unwrap<ApiResult<WorksPayload>>(raw)
    if (res?.success && res.data) payload.value = res.data
    subscribedKeys.value = await fetchSubscribedKeys(api)
  } catch (err) {
    console.warn(`[${PLUGIN_ID}] 仪表板加载失败`, err)
  } finally {
    loading.value = false
  }
}

async function refresh(): Promise<void> {
  const api = resolveApi(props)
  if (!api) return
  refreshing.value = true
  try {
    const raw = await api.post(`${API_BASE}/run`)
    const res = unwrap<ApiResult<WorksPayload>>(raw)
    if (res?.data) payload.value = res.data
    subscribedKeys.value = await fetchSubscribedKeys(api)
    // 刷新已改为后台任务，这里轮询到结束再落最终数据
    if (payload.value?.refreshing || payload.value?.pending_refresh) {
      waitForRefresh(api, (data) => {
        payload.value = data
      })
    }
  } catch (err) {
    console.warn(`[${PLUGIN_ID}] 仪表板刷新失败`, err)
  } finally {
    refreshing.value = false
  }
}

async function subscribe(work: ActorWork): Promise<void> {
  const api = resolveApi(props)
  if (!api) return
  const key = workKey(work)
  pendingKey.value = key
  try {
    // 复用插件配置里的订阅偏好（下载路径 / 下载器 / 站点），留空则跟随宿主默认
    const res = await submitSubscribe(api, work, {
      savePath: payload.value?.subscribe_save_path || props.config?.subscribe_save_path || '',
      downloader:
        payload.value?.subscribe_downloader || props.config?.subscribe_downloader || '',
      sites: payload.value?.subscribe_sites || props.config?.subscribe_sites || [],
    })
    if (res.ok) {
      if (!subscribedKeys.value.includes(key)) subscribedKeys.value.push(key)
      notify('success', res.message)
    } else {
      notify('error', `${work.title} 订阅失败：${res.message}`)
    }
  } finally {
    pendingKey.value = ''
  }
}

/** 取消订阅：仪表板上已订阅的作品再点一次就是取消，与详情页行为一致 */
async function unsubscribe(work: ActorWork): Promise<void> {
  const api = resolveApi(props)
  if (!api) return
  const key = workKey(work)
  pendingKey.value = key
  try {
    const res = await unsubscribeWork(api, work)
    if (res.ok) {
      subscribedKeys.value = subscribedKeys.value.filter((item) => item !== key)
      notify('success', res.message)
    } else {
      notify('error', `${work.title} 取消订阅失败：${res.message}`)
    }
  } finally {
    pendingKey.value = ''
  }
}

/** 忽略一部作品：与详情页/侧栏一致，忽略状态由后端持久化 */
async function ignore(work: ActorWork): Promise<void> {
  const api = resolveApi(props)
  if (!api) return
  const res = await ignoreWork(api, work)
  notify(res.ok ? 'success' : 'error', res.message)
  if (res.ok) await load()
}

onMounted(load)
</script>

<style scoped>
/* 为绝对定位的拖拽提示提供定位上下文；不要编写全局生效的选择器 */
.das-root {
  position: relative;
}

.das-dash-card {
  height: 100%;
}

.das-drag-hint {
  position: absolute;
  right: 12px;
  top: 12px;
  opacity: 0.6;
  cursor: move;
}

.das-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background-color: rgba(128, 128, 128, 0.5);
  margin-right: 8px;
  flex: 0 0 auto;
}

.das-dot-new {
  background-color: rgb(var(--v-theme-error, 244 67 54));
}

.das-name {
  font-size: 0.8rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.das-dim {
  opacity: 0.7;
}

.das-new {
  color: rgb(var(--v-theme-error, 244 67 54));
}
</style>
