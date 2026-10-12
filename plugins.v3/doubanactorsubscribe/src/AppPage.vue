<template>
  <div class="das-root pa-4">
    <div class="d-flex align-center mb-3 flex-wrap" style="gap: 12px">
      <v-icon icon="mdi-account-star-outline" class="mr-1" />
      <h2 class="text-h6 ma-0">豆瓣演员作品面板</h2>
      <v-chip size="small" variant="tonal">{{ pluginId || 'DoubanActorSubscribe' }} / {{ navKey || 'main' }}</v-chip>
      <v-spacer />
      <v-btn size="small" variant="tonal" color="primary" icon="mdi-refresh" :loading="refreshing" @click="refresh" />
    </div>

    <v-row dense class="mb-3">
      <v-col v-for="item in statCards" :key="item.label" cols="6" sm="3">
        <v-card variant="tonal" class="pa-3">
          <div class="text-caption">{{ item.label }}</div>
          <div class="text-h6">{{ item.value }}</div>
        </v-card>
      </v-col>
    </v-row>

    <v-alert v-if="!payload?.enabled" type="warning" variant="tonal" density="compact" class="mb-3">
      插件未启用或尚未配置演员，请先到配置页填写演员并保存。
    </v-alert>

    <!-- 筛选工具条 -->
    <v-card variant="outlined" class="mb-3">
      <v-card-text class="pb-2">
        <div class="d-flex align-center flex-wrap" style="gap: 8px">
          <v-chip-group v-model="actorFilter" mandatory>
            <v-chip size="small" variant="tonal" :value="ALL_ACTORS">全部演员</v-chip>
            <v-chip v-for="actor in actors" :key="actor.key" size="small" variant="tonal" :value="actor.key">
              {{ actor.name }}
            </v-chip>
          </v-chip-group>
        </div>

        <div class="d-flex align-center flex-wrap mt-2" style="gap: 12px">
          <v-btn-toggle v-model="typeFilter" density="compact" variant="outlined" divided>
            <v-btn size="small" value="">全部</v-btn>
            <v-btn size="small" value="电影">电影</v-btn>
            <v-btn size="small" value="电视剧">电视剧</v-btn>
          </v-btn-toggle>
          <v-checkbox v-model="onlyNew" label="只看新作品" density="compact" hide-details class="das-narrow" />
          <v-checkbox v-model="onlyUnsubscribed" label="只看未订阅" density="compact" hide-details class="das-narrow" />
          <v-btn-toggle v-model="sortMode" density="compact" variant="outlined" divided>
            <v-btn size="small" value="year">最新优先</v-btn>
            <v-btn size="small" value="new">新作品优先</v-btn>
          </v-btn-toggle>
          <v-text-field
            v-model="keyword"
            density="compact"
            variant="outlined"
            hide-details
            clearable
            prepend-inner-icon="mdi-magnify"
            placeholder="搜索作品名 / 演员名"
            class="das-search"
          />
          <v-spacer />
          <v-btn
            size="small"
            color="primary"
            variant="tonal"
            prepend-icon="mdi-plus-multiple"
            :disabled="busy || !pendingTargets.length"
            @click="subscribeMany(pendingTargets)"
          >
            订阅筛选结果（{{ pendingTargets.length }}）
          </v-btn>
        </div>
      </v-card-text>
    </v-card>

    <v-progress-linear v-if="loading" indeterminate color="primary" class="mb-3" />

    <div v-if="!visibleActors.length && !loading" class="text-center text-medium-emphasis py-8">
      没有符合条件的作品。
    </div>

    <v-card v-for="actor in visibleActors" :key="actor.key" variant="outlined" class="mb-4">
      <v-card-title class="d-flex align-center flex-wrap">
        <v-avatar size="34" class="mr-2">
          <v-img v-if="actor.avatar" :src="actor.avatar" />
          <v-icon v-else icon="mdi-account-outline" size="18" />
        </v-avatar>
        <span class="das-actor-name">{{ actor.name }}</span>
        <span class="text-caption das-dim ml-2">
          {{ (actor.works || []).length }} 部 · 新 {{ newCount(actor) }} 部
        </span>
        <v-spacer />
        <v-btn size="small" variant="text" color="primary" :href="doubanPersonUrl(actor.id)" target="_blank">
          豆瓣主页
        </v-btn>
      </v-card-title>
      <v-card-text>
        <v-alert v-if="actor.error" type="warning" variant="tonal" density="compact" class="mb-3">
          {{ actor.error }}
        </v-alert>
        <WorkGrid
          :works="actor.works || []"
          :subscribed-keys="subscribedKeys"
          :pending-key="pendingKey"
          :busy="busy"
          empty-text="该演员暂无符合条件的作品"
          @subscribe="subscribe"
        />
      </v-card-text>
    </v-card>
  </div>
</template>

<script setup lang="ts">
/**
 * 侧栏全页（联邦暴露名 ./AppPage，对应 nav_key = main）。
 *
 * 宿主路由为 `#/plugin-app/<pluginId>/<navKey>`，占据默认布局主内容区。
 * 相比详情弹窗，这里提供更宽的作品墙、更强的筛选与批量订阅能力。
 */
import { computed, inject, onMounted, ref } from 'vue'
import WorkGrid from './WorkGrid.vue'
import { API_BASE, PLUGIN_ID, fetchSubscribedKeys, resolveApi, submitSubscribe, unwrap, workKey } from './api'
import type { ActorGroup, ActorWork, ApiResult, PluginApi, WorksPayload } from './types'

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

const emit = defineEmits(['action'])

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
const onlyUnsubscribed = ref(false)
const sortMode = ref('year')
const keyword = ref('')

const actors = computed<ActorGroup[]>(() => payload.value?.actors || [])

const statCards = computed(() => [
  { label: '演员', value: payload.value?.actor_count ?? actors.value.length },
  { label: '作品', value: payload.value?.work_count ?? 0 },
  { label: '新作品', value: payload.value?.new_count ?? 0 },
  { label: '累计刷新', value: payload.value?.run_count ?? 0 },
])

function isSubscribed(work: ActorWork): boolean {
  return subscribedKeys.value.includes(workKey(work))
}

function newCount(actor: ActorGroup): number {
  return (actor.works || []).filter((work) => work.is_new).length
}

function doubanPersonUrl(id: string): string {
  return id ? `https://movie.douban.com/celebrity/${id}/` : 'https://movie.douban.com/'
}

/** 逐条应用筛选条件的谓词，供作品列表与批量目标复用 */
function matchWork(work: ActorWork): boolean {
  if (typeFilter.value && work.type !== typeFilter.value) return false
  if (onlyNew.value && !work.is_new) return false
  if (onlyUnsubscribed.value && isSubscribed(work)) return false
  return true
}

function matchActor(actor: ActorGroup): boolean {
  if (actorFilter.value && actorFilter.value !== ALL_ACTORS) {
    if (actor.key !== actorFilter.value && actor.id !== actorFilter.value) return false
  }
  const kw = keyword.value.trim().toLowerCase()
  if (!kw) return true
  return (
    String(actor.name || '').toLowerCase().includes(kw) ||
    (actor.works || []).some((work) => work.title.toLowerCase().includes(kw))
  )
}

/** 筛选后的演员与作品；排序方式在演员内部生效 */
const visibleActors = computed<ActorGroup[]>(() => {
  const kw = keyword.value.trim().toLowerCase()
  const filtering = Boolean(
    (actorFilter.value && actorFilter.value !== ALL_ACTORS) || typeFilter.value || onlyNew.value || onlyUnsubscribed.value
  )
  const result: ActorGroup[] = []
  for (const actor of actors.value) {
    if (!matchActor(actor)) continue
    let works = (actor.works || []).filter((work) => {
      if (!matchWork(work)) return false
      if (kw && !String(actor.name || '').toLowerCase().includes(kw)) {
        return work.title.toLowerCase().includes(kw)
      }
      return true
    })
    works = works.sort((a, b) => {
      if (sortMode.value === 'new') {
        const flag = Number(Boolean(b.is_new)) - Number(Boolean(a.is_new))
        if (flag) return flag
      }
      return (Number(b.year) || 0) - (Number(a.year) || 0)
    })
    if (!works.length && filtering) continue
    result.push({ ...actor, works })
  }
  return result
})

/** 当前筛选结果里所有未订阅的作品，作为「订阅筛选结果」的目标 */
const pendingTargets = computed<ActorWork[]>(() =>
  visibleActors.value.flatMap((actor) => (actor.works || []).filter((work) => !isSubscribed(work)))
)

function notify(type: 'success' | 'error' | 'info', message: string): void {
  const handler = toast && (toast as unknown as Record<string, unknown>)[type]
  if (typeof handler === 'function') {
    ;(handler as (msg: string) => unknown).call(toast, message)
    return
  }
  if (type === 'error') console.warn(`[${PLUGIN_ID}] ${message}`)
  else console.info(`[${PLUGIN_ID}] ${message}`)
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
    console.warn(`[${PLUGIN_ID}] 全页加载失败`, err)
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

onMounted(load)
</script>

<style scoped>
/* 仅使用 scoped 样式 */
.das-root {
  max-width: 1600px;
}

.das-dim {
  opacity: 0.75;
}

.das-actor-name {
  font-size: 1rem;
  font-weight: 600;
}

.das-search {
  max-width: 240px;
}

.das-narrow {
  max-width: 130px;
}
</style>
