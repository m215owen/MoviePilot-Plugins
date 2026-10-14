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
        <!-- 解析进度徽标：只统计「还没解析出人物 ID」的演员，
             解析完就归零消失。曾经的版本把「有 24 小时搜索记录的演员」全算进来，
             已解析的演员也会被算成「冷却中」，数字只涨不降，看着像卡住了。 -->
        <v-chip
          v-if="unresolvedCount"
          size="small"
          variant="tonal"
          color="warning"
          prepend-icon="mdi-timer-sand"
          :title="unresolvedHint"
        >
          待解析 {{ unresolvedCount }}
        </v-chip>
        <IgnoredManager
          :api="props.api"
          :ignored="payload?.ignored || []"
          :count="payload?.ignored_count || 0"
          @changed="load(false)"
        />
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
            <v-card variant="tonal" class="pa-3" :title="item.title">
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

      </v-card-text>
    </v-card>

    <!-- 订阅选项（下载保存路径 / 订阅站点）已收进插件配置页，面板不再重复展示；
         这里提交订阅时直接沿用后端下发的默认值，无需用户每次再选一遍 -->

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
          <!-- 只在真的查过库（library_known）时才给这个开关，避免旧快照下点了没反应 -->
          <v-checkbox
            v-if="libraryKnown"
            v-model="onlyNotInLibrary"
            label="只看未入库"
            density="compact"
            hide-details
            class="das-checkbox"
            title="只显示还没进媒体库的作品（判定与媒体详情页一致）。已在库的作品卡片角上会标「已入库」，自动订阅也会跳过它们"
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

    <div
      v-if="!visibleWorks.length && !loading"
      class="text-center text-medium-emphasis py-6"
    >
      暂无数据，点击顶部「刷新作品」抓取演员最新作品。
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
import { computed, inject, onMounted, ref, watch } from 'vue'
import IgnoredManager from './IgnoredManager.vue'
import WorkGrid from './WorkGrid.vue'
import {
  API_BASE,
  PLUGIN_ID,
  fetchSubscribedKeys,
  formatTime,
  ignoreWork,
  mergeWorks,
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
/** 订阅偏好：下载保存路径、下载器与订阅站点，提交订阅时一并带上 */
const subscribeSavePath = ref('')
const subscribeDownloader = ref('')
const subscribeSites = ref<number[]>([])

/** 演员筛选的「全部」哨兵值：chip-group 处于 mandatory 模式，需要一个真实值 */
const ALL_ACTORS = '__all__'

const actorFilter = ref(ALL_ACTORS)
const typeFilter = ref('')
const onlyNew = ref(false)
const onlyUnsubscribed = ref(false)
const onlyNotInLibrary = ref(false)
const sortMode = ref('year')
const keyword = ref('')

/** 任何筛选条件变化都回到第一页，避免停留在越界/过时页 */
watch(
  [actorFilter, typeFilter, onlyNew, onlyUnsubscribed, onlyNotInLibrary, sortMode, keyword],
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

/** 尚未解析出豆瓣人物 ID 的演员数（豆瓣搜索限流会让这个数逐步下降）。
 *  优先用后端给的统计（与解析缓存取交集），旧版后端没有该字段时回退到按快照自算。 */
const unresolvedCount = computed(
  () => payload.value?.unresolved_count ?? actors.value.filter((actor) => !actor.id).length
)

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

/**
 * 是否真的查过媒体库。
 *
 * 后端只有在刷新时才查库，且查库失败会保持「未知」。为假时面板既不显示
 * 「已在媒体库」统计，也不给「只看未入库」开关 —— 免得用户把「没查成」当成「都不在库」。
 */
const libraryKnown = computed(() => Boolean(payload.value?.library_known))

const statCards = computed(() => {
  const rows = [
    // 每张卡都带 title 字段（可为空串），保证数组元素类型一致、模板里可安全取 item.title
    { label: '演员', value: actors.value.length, title: '' },
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
  ]
  // 有未解析演员时优先暴露这个数：它才是「为什么作品这么少」的真正原因
  if (unresolvedCount.value) {
    rows.push({ label: '未解析演员', value: unresolvedCount.value, title: '' })
  } else {
    rows.push({ label: '累计刷新', value: payload.value?.run_count ?? 0, title: '' })
  }
  if (libraryKnown.value) {
    rows.push({
      label: '已在媒体库',
      value: payload.value?.library_count ?? 0,
      title:
        '已在媒体库中的作品数（判定与媒体详情页的「是否在媒体库」一致：先按豆瓣/TMDB 身份匹配，' +
        '未命中时按片名 + 类型 + 年份回退匹配）。卡片角上标「已入库」；自动订阅会跳过这些作品。',
    })
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
  // 「只看未入库」：只排除**明确已在库**的；未知（字段缺失）的保留，
  // 否则查库失败时一勾这个开关就会看到空白。
  if (onlyNotInLibrary.value) works = works.filter((work) => work.in_library !== true)
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

/** 用最新快照覆盖面板数据，并同步后端下发的订阅偏好 */
function applyPayload(data: WorksPayload): void {
  payload.value = data
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

/** 确认后真正执行批量订阅（顺序执行，避免给宿主识别链造成瞬时压力） */
async function doSubscribeMany(): Promise<void> {
  confirmDialog.value = false
  await subscribeMany(pendingTargets.value)
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
  max-width: 220px;
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
