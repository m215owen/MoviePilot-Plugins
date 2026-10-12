<template>
  <div class="das-root das-page pa-2">
    <!-- 顶部操作条：所有动作都固定在顶部，作品再多也不必滚到最后一行 -->
    <v-card variant="outlined" class="mb-3">
      <v-card-title class="d-flex align-center flex-wrap das-titlebar">
        <v-icon icon="mdi-account-star-outline" class="mr-1" />
        <span>豆瓣演员订阅</span>
        <v-chip v-if="actors.length" size="small" variant="tonal">{{ actors.length }} 位演员</v-chip>
        <v-chip v-if="visibleWorks.length" size="small" variant="tonal">
          {{ visibleWorks.length }} 部作品
        </v-chip>
        <v-chip
          size="small"
          variant="tonal"
          :color="cookieChip.color"
          :prepend-icon="cookieChip.icon"
          :title="cookieChip.title"
        >
          {{ cookieChip.text }}
        </v-chip>
        <v-chip
          v-if="cooldownCount"
          size="small"
          variant="tonal"
          color="info"
          prepend-icon="mdi-timer-sand"
          :title="`${cooldownCount} 位演员在 24 小时内成功搜索过，需等冷却结束后才会重试；直接填人物 ID 可跳过搜索`"
        >
          搜索冷却 {{ cooldownCount }}
        </v-chip>
        <v-spacer />
        <v-btn
          size="small"
          variant="tonal"
          color="primary"
          prepend-icon="mdi-refresh"
          :loading="refreshing || Boolean(payload?.refreshing)"
          @click="refresh"
        >
          {{ payload?.refreshing ? '刷新中…' : '刷新作品' }}
        </v-btn>
        <v-btn size="small" variant="text" prepend-icon="mdi-cog-outline" @click="emit('switch')">
          配置插件
        </v-btn>
        <v-btn size="small" variant="text" prepend-icon="mdi-open-in-app" @click="emit('action')">
          通知宿主刷新
        </v-btn>
        <v-btn size="small" variant="text" @click="emit('close')">关闭</v-btn>
      </v-card-title>

      <v-card-text class="pt-0">
        <v-alert
          v-if="!payload?.enabled"
          type="warning"
          variant="tonal"
          density="compact"
          class="mb-2"
        >
          插件未启用或尚未配置演员，请先在配置页填写演员并保存。
        </v-alert>

        <v-alert v-if="payload?.refreshing" type="info" variant="tonal" density="compact" class="mb-2">
          正在后台刷新演员作品（演员较多时需要几分钟），完成后此页会自动更新…
        </v-alert>
        <v-alert
          v-else-if="payload?.pending_refresh"
          type="info"
          variant="tonal"
          density="compact"
          class="mb-2"
        >
          演员列表已变更，正在后台刷新作品，稍候会自动更新…
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

        <!-- 异常提示：展示 5 秒后自动收起，避免长列表被提示刷屏 -->
        <ErrorAlerts :errors="errorList" class="mt-3" />
      </v-card-text>
    </v-card>

    <!-- 订阅选项：下载保存路径 + 订阅站点 -->
    <SubscribePrefs
      v-model:save-path="subscribeSavePath"
      v-model:sites="subscribeSites"
      :api="props.api"
      @saved="onPrefsSaved"
    />

    <!-- 筛选工具条 -->
    <v-card variant="outlined" class="mb-3">
      <v-card-text class="pb-2">
        <!-- 演员筛选：作品墙统一展示，分类交给这一列 -->
        <div class="das-chips">
          <v-chip-group v-model="actorFilter" mandatory>
            <v-chip size="small" variant="tonal" :value="ALL_ACTORS">全部演员</v-chip>
            <v-chip
              v-for="actor in actors"
              :key="actor.key"
              size="small"
              variant="tonal"
              :value="actor.key"
              :title="actor.error || actor.name"
            >
              <v-icon
                v-if="actor.error"
                icon="mdi-alert-circle-outline"
                size="14"
                color="warning"
                class="mr-1"
              />
              {{ actor.name }}
              <span class="ml-1 das-dim">{{ (actor.works || []).length }}</span>
            </v-chip>
          </v-chip-group>
        </div>

        <div class="d-flex align-center flex-wrap mt-2 das-toolbar">
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
          <v-checkbox
            v-model="onlyUnsubscribed"
            label="只看未订阅"
            density="compact"
            hide-details
            class="das-checkbox"
          />
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

    <v-progress-linear
      v-if="loading || payload?.refreshing"
      indeterminate
      color="primary"
      class="mb-3"
    />

    <div
      v-if="!visibleWorks.length && !loading"
      class="text-center text-medium-emphasis py-6"
    >
      暂无数据，点击顶部「刷新作品」抓取演员最新作品。
    </div>

    <!-- 统一作品墙：按作品去重，卡片上标注出演演员 -->
    <WorkGrid
      v-else
      :works="visibleWorks"
      :subscribed-keys="subscribedKeys"
      :pending-key="pendingKey"
      :busy="busy"
      empty-text="没有符合条件的作品"
      @subscribe="subscribe"
    />
  </div>
</template>

<script setup lang="ts">
/**
 * 插件详情页（联邦暴露名 ./Page）。
 *
 * 数据来源：
 *   GET  plugin/DoubanActorSubscribe/works   演员与作品快照
 *   POST plugin/DoubanActorSubscribe/run     立即刷新作品（后台执行，靠 refreshing 轮询）
 *   POST subscribe/                          提交订阅（宿主原生接口，归属当前用户）
 *
 * 作品墙是「统一视图」：不再按演员分卡片，因为演员筛选 chip 已经承担了分类职责，
 * 按演员重复展示会让列表随演员数量线性膨胀。
 */
import { computed, inject, onMounted, ref } from 'vue'
import ErrorAlerts from './ErrorAlerts.vue'
import SubscribePrefs from './SubscribePrefs.vue'
import WorkGrid from './WorkGrid.vue'
import {
  API_BASE,
  PLUGIN_ID,
  fetchSubscribedKeys,
  formatTime,
  mergeWorks,
  resolveApi,
  sortWorks,
  submitSubscribe,
  unwrap,
  waitForRefresh,
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
/** 订阅偏好：下载保存路径与订阅站点，提交订阅时一并带上 */
const subscribeSavePath = ref('')
const subscribeSites = ref<number[]>([])

/** 演员筛选的「全部」哨兵值：chip-group 处于 mandatory 模式，需要一个真实值 */
const ALL_ACTORS = '__all__'

const actorFilter = ref(ALL_ACTORS)
const typeFilter = ref('')
const onlyNew = ref(false)
const onlyUnsubscribed = ref(false)
const sortMode = ref('year')
const keyword = ref('')

const actors = computed<ActorGroup[]>(() => payload.value?.actors || [])

/** 尚未解析出豆瓣人物 ID 的演员数（豆瓣搜索限流会让这个数逐步下降） */
const unresolvedCount = computed(() => actors.value.filter((actor) => !actor.id).length)

const statCards = computed(() => {
  const rows = [
    { label: '演员', value: actors.value.length },
    { label: '作品', value: payload.value?.work_count ?? 0 },
    { label: '新作品', value: payload.value?.new_count ?? 0 },
  ]
  // 有未解析演员时优先暴露这个数：它才是「为什么作品这么少」的真正原因
  if (unresolvedCount.value) {
    rows.push({ label: '未解析演员', value: unresolvedCount.value })
  } else {
    rows.push({ label: '累计刷新', value: payload.value?.run_count ?? 0 })
  }
  return rows
})

/**
 * 豆瓣 Cookie 状态徽标。
 *
 * 它回答的是「额度够不够用」这个根因：匿名只能搜几次，用上登录态后额度明显更高。
 * 取不到时把原因原样带出来，用户才知道是去配 CookieCloud 还是去更新 Cookie。
 */
const cookieChip = computed(() => {
  const source = payload.value?.douban_cookie_source
  const hint = payload.value?.douban_cookie_hint || ''
  if (source === 'manual') {
    return { text: 'Cookie：手填', color: 'success', icon: 'mdi-cookie', title: '使用插件内手工粘贴的豆瓣 Cookie' }
  }
  if (source === 'cookiecloud') {
    return {
      text: 'Cookie：CookieCloud',
      color: 'success',
      icon: 'mdi-cookie',
      title: '已自动从宿主 CookieCloud 读取豆瓣登录态，搜索额度更高',
    }
  }
  return {
    text: 'Cookie：未取到',
    color: 'warning',
    icon: 'mdi-cookie-alert',
    title: hint || '未取到豆瓣登录态，按名称搜索演员会被严格限流；可在配置页手工粘贴 Cookie',
  }
})

/** 仍处于 24 小时搜索冷却中的演员数；为 0 时不显示徽标 */
const cooldownCount = computed(() => payload.value?.search_cooldown_count ?? 0)

/** 异常提示：把「可重试」与「需改配置」的提示排在前面，便于一眼看到 */
const errorList = computed(() => {
  const items = payload.value?.errors || []
  return [...items].sort((a, b) => {
    const rank = (text: string) => (text.includes('人物 ID') ? 1 : 0)
    return rank(a) - rank(b)
  })
})

function isSubscribed(work: ActorWork): boolean {
  return subscribedKeys.value.includes(workKey(work))
}

function actorMatches(actor: ActorGroup): boolean {
  return !actorFilter.value || actorFilter.value === ALL_ACTORS
    ? true
    : actor.key === actorFilter.value || actor.id === actorFilter.value
}

/**
 * 统一作品列表：先按演员筛选，再合并去重，最后叠加类型/新作品/关键词筛选与排序。
 * 关键词同时匹配作品名与出演演员名——合并视图下作品不再挂在演员卡片里，
 * 只搜作品名会让「按演员找作品」失去入口。
 */
const visibleWorks = computed<ActorWork[]>(() => {
  const groups = actors.value.filter(actorMatches)
  let works = mergeWorks(groups)
  if (typeFilter.value) works = works.filter((work) => work.type === typeFilter.value)
  if (onlyNew.value) works = works.filter((work) => work.is_new)
  if (onlyUnsubscribed.value) works = works.filter((work) => !isSubscribed(work))
  const kw = keyword.value.trim().toLowerCase()
  if (kw) {
    works = works.filter(
      (work) =>
        String(work.title || '').toLowerCase().includes(kw) ||
        (work.actorNames || []).some((name) => String(name).toLowerCase().includes(kw))
    )
  }
  return sortWorks(works, sortMode.value)
})

/** 当前筛选结果里所有未订阅的作品，作为「订阅筛选结果」的目标 */
const pendingTargets = computed<ActorWork[]>(() => visibleWorks.value.filter((work) => !isSubscribed(work)))

function notify(type: 'success' | 'error' | 'info', message: string): void {
  const handler = toast && (toast as unknown as Record<string, unknown>)[type]
  if (typeof handler === 'function') {
    ;(handler as (msg: string) => unknown).call(toast, message)
    return
  }
  if (type === 'error') console.warn(`[${PLUGIN_ID}] ${message}`)
  else console.info(`[${PLUGIN_ID}] ${message}`)
}

/** 用最新快照覆盖面板数据，并同步后端下发的订阅偏好 */
function applyPayload(data: WorksPayload): void {
  payload.value = data
  subscribeSavePath.value = data.subscribe_save_path || ''
  subscribeSites.value = data.subscribe_sites || []
}

/** 订阅选项保存回调 */
function onPrefsSaved(ok: boolean, message: string): void {
  notify(ok ? 'success' : 'error', message)
}

/** 读取作品快照与已有订阅 */
async function load(showSpinner = true): Promise<void> {
  const api = resolveApi(props)
  if (!api) return
  if (showSpinner) loading.value = true
  try {
    const raw = await api.get(`${API_BASE}/works`)
    const res = unwrap<ApiResult<WorksPayload>>(raw)
    if (res?.success && res.data) applyPayload(res.data)
    subscribedKeys.value = await fetchSubscribedKeys(api)
    // 后台正在刷新（含配置变更补刷新）时轮询到结束
    if (payload.value?.pending_refresh || payload.value?.refreshing) {
      waitForRefresh(api, applyPayload)
    }
  } catch (err) {
    console.warn(`[${PLUGIN_ID}] 加载作品失败`, err)
  } finally {
    loading.value = false
  }
}

/** 立即刷新一次作品（后端改为后台执行，这里轮询等待结果） */
async function refresh(): Promise<void> {
  const api = resolveApi(props)
  if (!api) return
  refreshing.value = true
  try {
    const raw = await api.post(`${API_BASE}/run`)
    const res = unwrap<ApiResult<WorksPayload>>(raw)
    if (res?.data) applyPayload(res.data)
    if (res?.success) notify('success', res.message || '已开始刷新演员最新作品')
    else notify('error', res?.message || '刷新失败')
    subscribedKeys.value = await fetchSubscribedKeys(api)
    if (payload.value?.refreshing || payload.value?.pending_refresh) {
      waitForRefresh(api, applyPayload)
    }
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
    const res = await submitSubscribe(api, work, {
      savePath: subscribeSavePath.value,
      sites: subscribeSites.value,
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
      const res = await submitSubscribe(api, work, {
        savePath: subscribeSavePath.value,
        sites: subscribeSites.value,
      })
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

.das-titlebar {
  flex-wrap: wrap;
  gap: 8px;
  row-gap: 4px;
}

.das-chips {
  max-height: 96px;
  overflow-y: auto;
}

.das-toolbar {
  gap: 12px;
}

.das-dim {
  opacity: 0.75;
}

.das-search {
  max-width: 220px;
}

.das-checkbox {
  max-width: 130px;
}
</style>
