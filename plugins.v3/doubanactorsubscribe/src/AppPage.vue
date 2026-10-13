<template>
  <div class="das-root pa-4">
    <div class="d-flex align-center mb-3 flex-wrap das-titlebar">
      <v-icon icon="mdi-account-star-outline" class="mr-1" />
      <h2 class="text-h6 ma-0">豆瓣演员作品面板</h2>
      <v-chip size="small" variant="tonal">
        {{ pluginId || 'DoubanActorSubscribe' }} / {{ navKey || 'main' }}
      </v-chip>
      <!-- 豆瓣登录态徽标：直接说明当前搜索额度来源 -->
      <v-chip
        size="small"
        variant="tonal"
        class="ml-1"
        :color="cookieChip.color"
        :prepend-icon="cookieChip.icon"
        :title="cookieChip.title"
      >
        {{ cookieChip.text }}
      </v-chip>
      <!-- 解析进度徽标：只统计「还没解析出人物 ID」的演员，解析完就归零消失 -->
      <v-chip
        v-if="unresolvedCount"
        size="small"
        variant="tonal"
        color="warning"
        class="ml-1"
        prepend-icon="mdi-timer-sand"
        :title="unresolvedHint"
      >
        待解析 {{ unresolvedCount }}
      </v-chip>
      <IgnoredManager
        class="ml-1"
        :api="props.api"
        :ignored="payload?.ignored || []"
        :count="payload?.ignored_count || 0"
        @changed="load(false)"
      />
      <v-spacer />
      <!-- 侧栏快捷开关：直接启停插件，无需再进配置页 -->
      <v-switch
        v-model="enabled"
        color="primary"
        hide-details
        density="compact"
        :loading="toggling"
        :label="enabled ? '已启用' : '已停用'"
        class="das-switch"
        @update:model-value="toggleEnabled"
      />
      <v-btn
        size="small"
        variant="tonal"
        color="primary"
        icon="mdi-refresh"
        :loading="refreshing || Boolean(payload?.refreshing)"
        @click="refresh"
      />
    </div>

    <v-row dense class="mb-3">
      <v-col v-for="item in statCards" :key="item.label" cols="6" sm="3">
        <v-card variant="tonal" class="pa-3" :title="item.title">
          <div class="text-caption">{{ item.label }}</div>
          <div class="text-h6">{{ item.value }}</div>
        </v-card>
      </v-col>
    </v-row>

    <v-alert v-if="!payload?.enabled" type="warning" variant="tonal" density="compact" class="mb-3">
      插件未启用或尚未配置演员，请先到配置页填写演员并保存。
    </v-alert>

    <v-alert
      v-if="payload?.refreshing || payload?.pending_refresh"
      type="info"
      variant="tonal"
      density="compact"
      class="mb-3"
    >
      {{
        payload?.refreshing
          ? '正在后台刷新演员作品（演员较多时需要几分钟），完成后此页会自动更新…'
          : '演员列表已变更，正在后台刷新作品，稍候会自动更新…'
      }}
    </v-alert>

    <!-- 订阅选项（下载保存路径 / 订阅站点）只在插件配置页维护，
         面板提交订阅时直接沿用后端下发的默认值 -->

    <!-- 筛选工具条 -->
    <v-card variant="outlined" class="mb-3">
      <v-card-text class="pb-2">
        <!-- 演员筛选：作品墙统一展示，分类交给这一列。
             每个 chip 可关闭（×）——移除演员时会同步删掉配置里的同名条目，
             所以走确认弹窗，避免误删配置。
             这里刻意**不用 v-chip-group**：它是横向滑动容器（会渲染左右箭头，
             多出来的演员只能靠点箭头翻，展开也只是把横向内容拉长、看不出效果）。
             改成普通的 flex-wrap 换行布局后，超出高度直接用鼠标滚轮上下滚。
             演员多（几十上百位）时默认只列前若干位，需要时点「展开全部」，
             免得筛选区高到把作品墙挤下去；当前选中的演员始终保留在列表里。 -->
        <div class="das-chips" :class="{ 'das-chips-expanded': actorsExpanded }">
          <div class="das-actor-chips">
            <v-chip
              size="small"
              variant="tonal"
              :color="actorFilter === ALL_ACTORS ? 'primary' : undefined"
              @click="actorFilter = ALL_ACTORS"
            >
              全部演员
            </v-chip>
            <v-chip
              v-for="actor in visibleActors"
              :key="actor.key"
              size="small"
              variant="tonal"
              :color="isActorActive(actor) ? 'primary' : undefined"
              closable
              close-icon="mdi-close"
              :title="actorTitle(actor)"
              @click="actorFilter = actor.key"
              @click:close="askRemoveActor(actor)"
            >
              <v-icon
                v-if="actor.error"
                icon="mdi-alert-circle-outline"
                size="14"
                color="warning"
                class="mr-1"
              />
              <v-icon
                v-else-if="isFuzzyActor(actor)"
                icon="mdi-help-circle-outline"
                size="14"
                color="warning"
                class="mr-1"
              />
              <!-- 最近加入的演员在这里标「新」：作品墙不再逐张标新，
                   刚加的演员靠这个标记才找得到（点一下 chip 即可只看他/她） -->
              <span
                v-if="actor.is_new"
                class="das-chip-new"
                title="最近加入的演员"
              >新</span>
              <template v-if="isFuzzyActor(actor)">
                {{ actor.key }}
                <span class="das-dim mx-1">→</span>
                {{ actor.name }}
              </template>
              <template v-else>{{ actor.name }}</template>
              <span class="ml-1 das-dim">{{ (actor.works || []).length }}</span>
            </v-chip>
          </div>
        </div>
        <div v-if="actors.length > ACTOR_COLLAPSE_LIMIT" class="mt-1">
          <v-btn
            size="x-small"
            variant="text"
            color="primary"
            :append-icon="actorsExpanded ? 'mdi-chevron-up' : 'mdi-chevron-down'"
            @click="actorsExpanded = !actorsExpanded"
          >
            {{ actorsExpanded ? '收起' : `展开全部（共 ${actors.length} 位）` }}
          </v-btn>
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
            title="只显示在你订阅的演员加入之后才出现的作品；刚加入演员的历史作品属于基线，不算新。想看新加的演员，请点上方的「新」chip"
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
            @click="confirmSubscribeMany"
          >
            订阅筛选结果（{{ pendingTargets.length }}）
          </v-btn>
        </div>
      </v-card-text>
    </v-card>

    <!-- 批量订阅确认：一次性订阅 N 部作品是不可逆动作，误触代价高，必须先确认 -->
    <v-dialog v-model="confirmDialog" max-width="460">
      <v-card>
        <v-card-title>确认批量订阅？</v-card-title>
        <v-card-text>
          将把当前筛选结果里的 <strong>{{ pendingTargets.length }}</strong> 部未订阅作品
          一次性提交到订阅系统（按豆瓣 ID 精确订阅）。
          <template v-if="pendingTargets.length > 20">
            数量较多，确认后请耐心等待逐条提交完成。
          </template>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="confirmDialog = false">取消</v-btn>
          <v-btn color="primary" @click="doSubscribeMany">确认订阅</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- 移除演员确认：会同步删掉配置里的同名条目，不可逆，必须先确认 -->
    <v-dialog v-model="removeDialog" max-width="460">
      <v-card>
        <v-card-title>从订阅演员中移除？</v-card-title>
        <v-card-text>
          将移除演员
          <strong>{{ removeTarget?.name || removeTarget?.key }}</strong>，
          并<strong>同步删除配置页里的同名条目</strong>、清理它的作品数据。
          以后不会再抓取这位演员的作品；已经提交的订阅不受影响。
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="removeDialog = false">取消</v-btn>
          <v-btn color="error" variant="tonal" :loading="removing" @click="doRemoveActor">
            确认移除
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <v-progress-linear
      v-if="loading || payload?.refreshing"
      indeterminate
      color="primary"
      class="mb-3"
    />

    <div v-if="!visibleWorks.length && !loading" class="text-center text-medium-emphasis py-8">
      没有符合条件的作品。
    </div>

    <!-- 统一作品墙：按作品去重，卡片上标注出演演员 -->
    <WorkGrid
      v-else
      :works="pagedWorks"
      :subscribed-keys="subscribedKeys"
      :pending-key="pendingKey"
      :busy="busy"
      empty-text="没有符合条件的作品"
      @subscribe="subscribe"
      @unsubscribe="unsubscribe"
      @ignore="ignore"
    />

    <!-- 分页：作品多时每页只展示 PAGE_SIZE 个，避免长列表拖垮渲染。
         用 v-btn / v-chip 手写，而非 v-pagination：主程序按需导入 Vuetify 组件，
         v-pagination 未必被注册，联邦 remote 里会渲染成空元素导致分页失效。 -->
    <div v-if="pageCount > 1" class="d-flex align-center justify-center mt-3 ga-2">
      <v-btn
        size="small"
        variant="tonal"
        icon="mdi-chevron-left"
        :disabled="page <= 1"
        @click="page = Math.max(1, page - 1)"
      />
      <span class="das-page-info">第 {{ page }} / {{ pageCount }} 页</span>
      <v-btn
        size="small"
        variant="tonal"
        icon="mdi-chevron-right"
        :disabled="page >= pageCount"
        @click="page = Math.min(pageCount, page + 1)"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * 侧栏全页（联邦暴露名 ./AppPage，对应 nav_key = main）。
 *
 * 宿主路由为 `#/plugin-app/<pluginId>/<navKey>`，占据默认布局主内容区。
 * 作品墙是统一视图：不按演员分卡片，分类交给演员筛选 chip，
 * 卡片上标注出演演员，因此不会因为演员多而把列表撑爆。
 */
import { computed, inject, onMounted, ref, watch } from 'vue'
import IgnoredManager from './IgnoredManager.vue'
import WorkGrid from './WorkGrid.vue'
import {
  API_BASE,
  PLUGIN_ID,
  fetchSubscribedKeys,
  ignoreWork,
  mergeWorks,
  normalizeResult,
  removeActor,
  resolveApi,
  sortWorks,
  submitSubscribe,
  unsubscribeWork,
  unwrap,
  waitForRefresh,
  workKey,
} from './api'
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
/** 插件启用开关：与 payload.enabled 双向同步，点开关即写回配置 */
const enabled = ref(false)
const toggling = ref(false)
/** 订阅偏好：下载保存路径、下载器与订阅站点 */
const subscribeSavePath = ref('')
const subscribeDownloader = ref('')
const subscribeSites = ref<number[]>([])

/** 演员筛选的「全部」哨兵值：chip-group 处于 mandatory 模式，需要一个真实值 */
const ALL_ACTORS = '__all__'

const actorFilter = ref(ALL_ACTORS)
const typeFilter = ref('')
const onlyNew = ref(false)
const onlyUnsubscribed = ref(false)
const sortMode = ref('year')
const keyword = ref('')

/** 任何筛选条件变化都回到第一页，避免停留在越界/过时页 */
watch(
  [actorFilter, typeFilter, onlyNew, onlyUnsubscribed, sortMode, keyword],
  resetPage
)

const actors = computed<ActorGroup[]>(() => payload.value?.actors || [])

/** 演员筛选区超过这个数量就默认折叠，避免筛选区占掉大半屏 */
const ACTOR_COLLAPSE_LIMIT = 12

/** 演员筛选区是否展开显示全部 */
const actorsExpanded = ref(false)

/**
 * 演员筛选区实际渲染的演员列表。
 *
 * 折叠时只列前若干位；当前选中的演员强制保留——chip-group 是 mandatory，
 * 选中项被折叠掉会让用户看到「列表里没有任何选中」，误以为筛选失效。
 */
const visibleActors = computed<ActorGroup[]>(() => {
  const all = actors.value
  if (actorsExpanded.value || all.length <= ACTOR_COLLAPSE_LIMIT) return all
  const head = all.slice(0, ACTOR_COLLAPSE_LIMIT)
  const current = all.find(
    (actor) => actor.key === actorFilter.value || actor.id === actorFilter.value
  )
  if (current && !head.includes(current)) return [current, ...head]
  return head
})

/**
 * 「新」的口径由后端下发：演员自加入、作品自在演员加入之后出现起，不超过 N 天。
 * 只写「新作品」的话，用户看到 0 或一个很大的数时无从判断是坏了还是口径如此。
 */
const newWindowDays = computed(() => Number(payload.value?.new_window_days || 0))
const newWindowLabel = computed(() =>
  newWindowDays.value > 0 ? `近 ${newWindowDays.value} 天新增` : '近期新增'
)
/** 窗口内加入的演员数；旧版后端没有该字段时按快照自算 */
const newActorCount = computed(
  () => payload.value?.new_actor_count ?? actors.value.filter((actor) => actor.is_new).length
)

const statCards = computed(() => [
  // 每张卡都带 title 字段（可为空串），保证数组元素类型一致、模板里可安全取 item.title
  { label: '演员', value: payload.value?.actor_count ?? actors.value.length, title: '' },
  { label: '作品', value: payload.value?.work_count ?? 0, title: '' },
  {
    label: `${newWindowLabel.value}（演员 / 作品）`,
    value: `${newActorCount.value} / ${payload.value?.new_count ?? 0}`,
    title:
      `新演员 = 最近 ${newWindowDays.value} 天加入订阅列表的演员（chip 上标「新」）；` +
      '新作品 = 首次出现在该演员加入之后的作品。' +
      '刚加入的演员过去的老作品属于基线，不会逐张标「新」，' +
      '只有之后刷新才冒出来的作品才带「新」。',
  },
  { label: '累计刷新', value: payload.value?.run_count ?? 0, title: '' },
])

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

/** 还没解析出人物 ID 的演员数；为 0 时说明全部解析完毕，徽标不显示。
 *  优先用后端统计，旧版后端没有该字段时回退到按快照自算。 */
const unresolvedCount = computed(
  () => payload.value?.unresolved_count ?? actors.value.filter((actor) => !actor.id).length
)
/** 其中仍处于 24 小时搜索冷却内、要等冷却结束才会重试的数量 */
const cooldownCount = computed(() => payload.value?.search_cooldown_count ?? 0)
const unresolvedHint = computed(
  () =>
    `还有 ${unresolvedCount.value} 位演员没解析出人物 ID（共 ${actors.value.length} 位）：` +
    (cooldownCount.value
      ? `其中 ${cooldownCount.value} 位在 24 小时搜索冷却内，需等冷却结束后才会重试；`
      : `下次刷新会继续按名称搜索；`) +
    `直接填人物 ID 或主页链接可完全跳过搜索`
)

function isSubscribed(work: ActorWork): boolean {
  return subscribedKeys.value.includes(workKey(work))
}

function actorMatches(actor: ActorGroup): boolean {
  return !actorFilter.value || actorFilter.value === ALL_ACTORS
    ? true
    : actor.key === actorFilter.value || actor.id === actorFilter.value
}

/** 该演员是否正好是当前筛中的那一位（用于给 chip 上高亮色） */
function isActorActive(actor: ActorGroup): boolean {
  return actorFilter.value === actor.key || actorFilter.value === actor.id
}

/**
 * 是否属于「模糊匹配」：豆瓣上没有与配置名同名的演员，插件退回了最接近的搜索结果。
 * 此时 chip 会显示「配置名 → 豆瓣名」，避免用户找不到自己填的那位演员。
 */
function isFuzzyActor(actor: ActorGroup): boolean {
  return Boolean(actor.fuzzy) && Boolean(actor.name) && actor.name !== actor.key
}

/** 演员 chip 的悬停提示：说清这一位是谁，模糊匹配时给出候选并提示改用人物 ID */
function actorTitle(actor: ActorGroup): string {
  const suffix = '（点右侧 × 可从订阅演员中移除）'
  // 新加入的演员把「加入时间」写进提示：chip 上的「新」只说明是最近加的，
  // 具体哪天加的看着这个日期才没有歧义
  const prefix =
    actor.is_new && actor.joined_at ? `最近加入（${actor.joined_at}）｜` : ''
  if (actor.error) return `${prefix}${actor.error}${suffix}`
  if (isFuzzyActor(actor)) {
    const candidates = (actor.candidates || []).filter(Boolean)
    return (
      `${prefix}配置的「${actor.key}」在豆瓣没有同名演员，已按最接近的结果「${actor.name}」解析` +
      (candidates.length ? `（候选：${candidates.join(' / ')}）` : '') +
      `。请核对，或把配置项改成人物 ID 精确指定。${suffix}`
    )
  }
  return `${prefix}${actor.name}${suffix}`
}

/** 统一作品列表；关键词同时匹配作品名与出演演员名 */
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
const pendingTargets = computed<ActorWork[]>(() =>
  visibleWorks.value.filter((work) => !isSubscribed(work))
)

/** 作品墙分页：每页最多 PAGE_SIZE 个 */
const PAGE_SIZE = 20
const page = ref(1)
const pageCount = computed(() => Math.max(1, Math.ceil(visibleWorks.value.length / PAGE_SIZE)))
const pagedWorks = computed<ActorWork[]>(() => {
  const start = (page.value - 1) * PAGE_SIZE
  return visibleWorks.value.slice(start, start + PAGE_SIZE)
})

/** 筛选条件变化时回到第一页，避免停留在越界页 */
function resetPage(): void {
  page.value = 1
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

/** 用最新快照覆盖面板数据，并同步后端下发的开关与订阅偏好 */
function applyPayload(data: WorksPayload): void {
  payload.value = data
  enabled.value = Boolean(data.enabled)
  subscribeSavePath.value = data.subscribe_save_path || ''
  subscribeDownloader.value = data.subscribe_downloader || ''
  subscribeSites.value = data.subscribe_sites || []
}

/** 忽略一部作品：后端持久化后重新拉取快照，顶部会多出「已忽略 N 部」恢复入口 */
async function ignore(work: ActorWork): Promise<void> {
  const api = resolveApi(props)
  if (!api) return
  const res = await ignoreWork(api, work)
  notify(res.ok ? 'success' : 'error', res.message)
  if (res.ok) await load(false)
}

/**
 * 侧栏开关：直接 PUT /config 切换 enabled，只提交该字段，其余配置由后端合并保留。
 */
async function toggleEnabled(value: unknown): Promise<void> {
  const api = resolveApi(props)
  if (!api) {
    notify('error', '宿主 API 未就绪')
    return
  }
  const next = Boolean(value)
  toggling.value = true
  try {
    const raw = await api.put(`${API_BASE}/config`, { enabled: next })
    const res = normalizeResult<unknown>(raw)
    if (!res.ok) {
      enabled.value = !next
      notify('error', res.message || '切换状态失败')
      return
    }
    notify('success', next ? '插件已启用' : '插件已停用')
    await load(false)
    if (next) await refresh()
  } catch (err) {
    enabled.value = !next
    notify('error', '切换状态失败')
    console.warn(`[${PLUGIN_ID}] 切换启用状态失败`, err)
  } finally {
    toggling.value = false
  }
}

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

async function subscribe(work: ActorWork): Promise<void> {
  const api = resolveApi(props)
  if (!api) return
  const key = workKey(work)
  pendingKey.value = key
  try {
    const res = await submitSubscribe(api, work, {
      savePath: subscribeSavePath.value,
      downloader: subscribeDownloader.value,
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

/** 取消单个作品的订阅（卡片上已是「已订阅」时再点一次就是取消） */
async function unsubscribe(work: ActorWork): Promise<void> {
  const api = resolveApi(props)
  if (!api) return
  const key = workKey(work)
  pendingKey.value = key
  try {
    const res = await unsubscribeWork(api, work)
    if (res.ok) {
      // 先摘掉「已订阅」标记，卡片立刻回到可订阅态，不等下次整页刷新
      subscribedKeys.value = subscribedKeys.value.filter((item) => item !== key)
      notify('success', res.message)
    } else {
      notify('error', `${work.title} 取消订阅失败：${res.message}`)
    }
  } finally {
    pendingKey.value = ''
  }
}

/** 批量订阅确认弹窗开关 */
const confirmDialog = ref(false)

/** 待移除的演员；点 chip 上的 × 先弹确认，避免误删配置 */
const removeTarget = ref<ActorGroup | null>(null)
const removeDialog = ref(false)
const removing = ref(false)

/** 点演员 chip 上的删除按钮：先确认，再同步删除配置里的该条目 */
function askRemoveActor(actor: ActorGroup): void {
  removeTarget.value = actor
  removeDialog.value = true
}

/** 确认后真正移除（后端持久化配置 → 丢弃该演员快照 → 安排补刷新） */
async function doRemoveActor(): Promise<void> {
  const actor = removeTarget.value
  removeDialog.value = false
  if (!actor) return
  const api = resolveApi(props)
  if (!api) return
  removing.value = true
  try {
    const res = await removeActor(api, actor)
    notify(res.ok ? 'success' : 'error', res.message)
    if (res.ok) {
      // 移除的正好是当前筛中的演员时，回到「全部演员」，避免停在空结果上
      if (actorFilter.value === actor.key || actorFilter.value === actor.id) {
        actorFilter.value = ALL_ACTORS
      }
      await load(false)
    }
  } finally {
    removing.value = false
    removeTarget.value = null
  }
}

/** 点「订阅筛选结果」先弹确认，避免误触一次性订阅 N 部作品 */
function confirmSubscribeMany(): void {
  if (!pendingTargets.value.length) return
  confirmDialog.value = true
}

/** 确认后真正执行批量订阅 */
async function doSubscribeMany(): Promise<void> {
  confirmDialog.value = false
  await subscribeMany(pendingTargets.value)
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
      const res = await submitSubscribe(api, work, {
        savePath: subscribeSavePath.value,
        downloader: subscribeDownloader.value,
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

watch(
  () => payload.value?.enabled,
  (value) => {
    if (typeof value === 'boolean') enabled.value = value
  }
)

onMounted(() => load())
</script>

<style scoped>
/* 仅使用 scoped 样式 */
.das-root {
  max-width: 1600px;
}

.das-titlebar {
  gap: 12px;
  row-gap: 4px;
}

/* 演员 chip 区：flex 换行 + 纵向滚动。
   不能用 v-chip-group——它是横向滑动容器，会带左右箭头且展开看不出效果。 */
.das-chips {
  max-height: 96px;
  overflow-y: auto;
}

.das-actor-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

/* 演员 chip 上的「新」：作品墙不再逐张标新，最近加入的演员靠这里才一眼可辨 */
.das-chip-new {
  display: inline-flex;
  align-items: center;
  height: 14px;
  padding: 0 4px;
  margin-right: 3px;
  border-radius: 3px;
  background-color: rgb(var(--v-theme-error));
  color: #fff;
  font-size: 10px;
  font-weight: 600;
  line-height: 1;
}

/* 展开后放开限高：一次能看到更多演员（仍留上限，上百位时不至于拉爆页面） */
.das-chips-expanded {
  max-height: 60vh;
}

.das-toolbar {
  gap: 12px;
}

.das-dim {
  opacity: 0.75;
}

.das-search {
  max-width: 240px;
}

.das-checkbox {
  max-width: 130px;
}

.das-page-info {
  font-size: 0.82rem;
  opacity: 0.85;
  white-space: nowrap;
}
</style>
