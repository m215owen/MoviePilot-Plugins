<template>
  <div class="das-root das-page pa-2">
    <!-- 概览 -->
    <v-card variant="outlined" class="mb-3">
      <v-card-title class="d-flex align-center flex-wrap">
        <v-icon icon="mdi-account-star-outline" class="mr-2" />
        <span>豆瓣演员订阅</span>
        <v-spacer />
        <v-btn
          size="small"
          variant="tonal"
          color="primary"
          prepend-icon="mdi-refresh"
          :loading="refreshing"
          @click="refresh"
        >
          刷新作品
        </v-btn>
      </v-card-title>

      <v-card-text>
        <v-alert
          v-if="!payload?.enabled"
          type="warning"
          variant="tonal"
          density="compact"
          class="mb-3"
        >
          插件未启用或尚未配置演员，请先在配置页填写演员并保存。
        </v-alert>

        <v-row dense>
          <v-col v-for="item in statCards" :key="item.label" cols="6" sm="3">
            <v-card variant="tonal" class="pa-3">
              <div class="text-caption">{{ item.label }}</div>
              <div class="text-h6">{{ item.value }}</div>
            </v-card>
          </v-col>
        </v-row>

        <div class="text-caption das-dim mt-2">
          上次刷新：{{ formatTime(payload?.updated_at) }}
          <span v-if="payload?.auto_subscribe">
            ｜自动订阅：{{ payload?.auto_only_new ? '仅新作品' : '含存量作品' }}
            ・评分 ≥ {{ payload?.auto_min_vote || 0 }}
            ・{{ (payload?.auto_types || []).join('/') || '全部类型' }}
          </span>
        </div>

        <v-alert
          v-for="(err, index) in payload?.errors || []"
          :key="index"
          type="error"
          variant="tonal"
          density="compact"
          class="mt-2"
        >
          {{ err }}
        </v-alert>
      </v-card-text>
    </v-card>

    <!-- 筛选 -->
    <v-card variant="outlined" class="mb-3">
      <v-card-text class="pb-2">
        <div class="d-flex align-center flex-wrap" style="gap: 12px">
          <v-chip-group v-model="actorFilter" mandatory class="das-chips">
            <v-chip size="small" variant="tonal" :value="ALL_ACTORS">全部演员</v-chip>
            <v-chip
              v-for="actor in actors"
              :key="actor.key"
              size="small"
              variant="tonal"
              :value="actor.key"
            >
              {{ actor.name }}
              <span class="ml-1 das-dim">（{{ (actor.works || []).length }}）</span>
            </v-chip>
          </v-chip-group>
        </div>

        <div class="d-flex align-center flex-wrap mt-2" style="gap: 12px">
          <v-btn-toggle v-model="typeFilter" density="compact" variant="outlined" divided>
            <v-btn size="small" value="">全部</v-btn>
            <v-btn size="small" value="电影">电影</v-btn>
            <v-btn size="small" value="电视剧">电视剧</v-btn>
          </v-btn-toggle>
          <v-checkbox
            v-model="onlyNew"
            label="只看新作品"
            density="compact"
            hide-details
            class="das-checkbox"
          />
          <v-text-field
            v-model="keyword"
            density="compact"
            variant="outlined"
            hide-details
            clearable
            prepend-inner-icon="mdi-magnify"
            placeholder="搜索作品名"
            class="das-search"
          />
        </div>
      </v-card-text>
    </v-card>

    <!-- 演员作品 -->
    <v-progress-linear v-if="loading" indeterminate color="primary" class="mb-3" />

    <div v-if="!visibleActors.length && !loading" class="text-center text-medium-emphasis py-6">
      暂无数据，点击「刷新作品」抓取演员最新作品。
    </div>

    <v-card
      v-for="actor in visibleActors"
      :key="actor.key"
      variant="outlined"
      class="mb-3"
    >
      <v-card-title class="d-flex align-center flex-wrap">
        <v-avatar size="36" class="mr-2">
          <v-img v-if="actor.avatar" :src="actor.avatar" />
          <v-icon v-else icon="mdi-account-outline" />
        </v-avatar>
        <div class="das-actor-name">
          {{ actor.name }}
          <span class="das-dim text-caption ml-2">
            共 {{ (actor.works || []).length }} 部 · 新 {{ newCount(actor) }} 部
          </span>
        </div>
        <v-spacer />
        <v-btn
          size="small"
          variant="tonal"
          color="primary"
          prepend-icon="mdi-plus-multiple"
          :disabled="busy || !unsubscribed(actor).length"
          @click="subscribeMany(unsubscribed(actor))"
        >
          订阅全部未订阅（{{ unsubscribed(actor).length }}）
        </v-btn>
      </v-card-title>

      <v-card-text>
        <v-alert
          v-if="actor.error"
          type="warning"
          variant="tonal"
          density="compact"
          class="mb-3"
        >
          {{ actor.error }}
        </v-alert>
        <div v-if="actor.biography" class="text-caption das-dim mb-3">{{ actor.biography }}</div>

        <WorkGrid
          :works="actor.works || []"
          :subscribed-keys="subscribedKeys"
          :pending-key="pendingKey"
          :busy="busy"
          empty-text="该演员暂无匹配的作品"
          @subscribe="subscribe"
        />
      </v-card-text>
    </v-card>

    <!-- 宿主交互：switch 切到配置页，close 关闭弹窗，action 通知宿主刷新 -->
    <div class="d-flex mt-3 flex-wrap" style="gap: 4px">
      <v-btn size="small" variant="text" prepend-icon="mdi-cog-outline" @click="emit('switch')">
        配置插件
      </v-btn>
      <v-btn size="small" variant="text" prepend-icon="mdi-refresh" @click="emit('action')">
        通知宿主刷新
      </v-btn>
      <v-btn size="small" variant="text" @click="emit('close')">关闭</v-btn>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * 插件详情页（联邦暴露名 ./Page）。
 *
 * 数据来源：
 *   GET  plugin/DoubanActorSubscribe/works   演员与作品快照
 *   POST plugin/DoubanActorSubscribe/run     立即刷新作品
 *   POST subscribe/                          提交订阅（宿主原生接口，归属当前用户）
 */
import { computed, inject, onMounted, ref } from 'vue'
import WorkGrid from './WorkGrid.vue'
import {
  API_BASE,
  PLUGIN_ID,
  fetchSubscribedKeys,
  formatTime,
  resolveApi,
  submitSubscribe,
  unwrap,
  workKey,
} from './api'
import type { ActorGroup, ActorWork, ApiResult, PluginApi, WorksPayload } from './types'

/** 宿主统一 Toast（键名固定为 moviepilot:toast） */
interface HostToast {
  success(message: string): unknown
  info(message: string): unknown
  warning(message: string): unknown
  error(message: string): unknown
}

const props = defineProps<{
  /** 宿主注入的 axios 实例（实例作用域） */
  api?: PluginApi
  /** 宿主原生订阅交互（本插件改用订阅接口，保留以示意可用能力） */
  nativeSubscribe?: (mediaInfo: Record<string, unknown>) => Promise<unknown>
  /** 当前插件实例 ID */
  pluginId?: string
}>()

const emit = defineEmits(['action', 'switch', 'close'])

const toast = inject<HostToast | null>('moviepilot:toast', null)

const loading = ref(false)
const refreshing = ref(false)
const busy = ref(false)
const pendingKey = ref('')
const payload = ref<WorksPayload | null>(null)
const subscribedKeys = ref<string[]>([])

/** 演员筛选的「全部」哨兵值：chip-group 处于 mandatory 模式，需要一个真实值 */
const ALL_ACTORS = '__all__'

const actorFilter = ref(ALL_ACTORS)
const typeFilter = ref('')
const onlyNew = ref(false)
const keyword = ref('')

const actors = computed<ActorGroup[]>(() => payload.value?.actors || [])

const statCards = computed(() => [
  { label: '演员', value: payload.value?.actor_count ?? actors.value.length },
  { label: '作品', value: payload.value?.work_count ?? 0 },
  { label: '新作品', value: payload.value?.new_count ?? 0 },
  { label: '累计刷新', value: payload.value?.run_count ?? 0 },
])

/** 筛选后的演员与其作品（无匹配时不渲染该演员） */
const visibleActors = computed<ActorGroup[]>(() => {
  const kw = keyword.value.trim().toLowerCase()
  const filtering = Boolean(
    (actorFilter.value && actorFilter.value !== ALL_ACTORS) || typeFilter.value || onlyNew.value || kw
  )
  const result: ActorGroup[] = []
  for (const actor of actors.value) {
    if (actorFilter.value && actorFilter.value !== ALL_ACTORS) {
      if (actor.key !== actorFilter.value && actor.id !== actorFilter.value) continue
    }
    const works = (actor.works || []).filter((work) => {
      if (typeFilter.value && work.type !== typeFilter.value) return false
      if (onlyNew.value && !work.is_new) return false
      if (kw && !work.title.toLowerCase().includes(kw)) return false
      return true
    })
    if (!works.length && filtering) continue
    result.push({ ...actor, works })
  }
  return result
})

function isSubscribed(work: ActorWork): boolean {
  return subscribedKeys.value.includes(workKey(work))
}

function newCount(actor: ActorGroup): number {
  return (actor.works || []).filter((work) => work.is_new).length
}

function unsubscribed(actor: ActorGroup): ActorWork[] {
  return (actor.works || []).filter((work) => !isSubscribed(work))
}

function notify(type: 'success' | 'error' | 'info', message: string): void {
  const handler = toast && (toast as unknown as Record<string, unknown>)[type]
  if (typeof handler === 'function') {
    ;(handler as (msg: string) => unknown).call(toast, message)
    return
  }
  if (type === 'error') console.warn(`[${PLUGIN_ID}] ${message}`)
  else console.info(`[${PLUGIN_ID}] ${message}`)
}

/** 读取作品快照与已有订阅 */
async function load(showSpinner = true): Promise<void> {
  const api = resolveApi(props)
  if (!api) return
  if (showSpinner) loading.value = true
  try {
    const raw = await api.get(`${API_BASE}/works`)
    const res = unwrap<ApiResult<WorksPayload>>(raw)
    if (res?.success && res.data) payload.value = res.data
    subscribedKeys.value = await fetchSubscribedKeys(api)
  } catch (err) {
    console.warn(`[${PLUGIN_ID}] 加载作品失败`, err)
  } finally {
    loading.value = false
  }
}

/** 立即刷新一次作品 */
async function refresh(): Promise<void> {
  const api = resolveApi(props)
  if (!api) return
  refreshing.value = true
  try {
    const raw = await api.post(`${API_BASE}/run`)
    const res = unwrap<ApiResult<WorksPayload>>(raw)
    if (res?.data) payload.value = res.data
    if (res?.success) notify('success', '已刷新演员最新作品')
    else notify('error', res?.message || '刷新失败')
    subscribedKeys.value = await fetchSubscribedKeys(api)
    emit('action')
  } catch (err) {
    notify('error', '刷新失败，请查看后端日志')
    console.warn(`[${PLUGIN_ID}] 刷新失败`, err)
  } finally {
    refreshing.value = false
  }
}

/** 提交单个作品的订阅 */
async function subscribe(work: ActorWork): Promise<void> {
  const api = resolveApi(props)
  if (!api) return
  const key = workKey(work)
  pendingKey.value = key
  try {
    const res = await submitSubscribe(api, work)
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

/** 批量提交订阅（顺序执行，避免给宿主识别链造成瞬时压力） */
async function subscribeMany(works: ActorWork[]): Promise<void> {
  const api = resolveApi(props)
  if (!api || !works.length) return
  busy.value = true
  let success = 0
  const failures: string[] = []
  try {
    for (const work of works) {
      const key = workKey(work)
      pendingKey.value = key
      const res = await submitSubscribe(api, work)
      if (res.ok) {
        success += 1
        if (!subscribedKeys.value.includes(key)) subscribedKeys.value.push(key)
      } else {
        failures.push(`${work.title}：${res.message}`)
      }
      await new Promise((resolve) => window.setTimeout(resolve, 150))
    }
  } finally {
    pendingKey.value = ''
    busy.value = false
  }
  if (success) notify('success', `已提交 ${success} 部作品的订阅`)
  if (failures.length) notify('error', `${failures.length} 部订阅失败，例如 ${failures[0]}`)
}

onMounted(() => load())
</script>

<style scoped>
/* 仅使用 scoped 样式；不要编写会全局生效的选择器（组件库类名、html、body、:root） */
.das-page {
  max-width: 100%;
}

.das-dim {
  opacity: 0.75;
}

.das-actor-name {
  font-size: 1rem;
  font-weight: 600;
}

.das-search {
  max-width: 220px;
}

.das-checkbox {
  max-width: 140px;
}
</style>
