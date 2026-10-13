<template>
  <div class="sdas-root" :class="props.full ? 'pa-4' : 'pa-2'">
    <!-- 标题栏 -->
    <div class="d-flex align-center mb-3 flex-wrap" style="gap: 8px">
      <v-icon icon="mdi-movie-open-star-outline" class="mr-1" />
      <h2 class="text-h6 ma-0">{{ isMain ? '短剧' : '短剧 · 运行状态' }}</h2>
      <v-chip size="small" variant="tonal" :color="enabled ? 'primary' : 'warning'">
        {{ enabled ? '已启用' : '未启用' }}
      </v-chip>
      <v-chip
        v-if="payload?.running"
        size="small"
        variant="tonal"
        color="info"
        prepend-icon="mdi-progress-clock"
      >
        正在执行
      </v-chip>
      <v-chip
        v-else-if="cooldownCount"
        size="small"
        variant="tonal"
        color="warning"
        prepend-icon="mdi-timer-sand"
        :title="'搜过但站点暂无资源的剧，24 小时内不重复搜索'"
      >
        冷却 {{ cooldownCount }}
      </v-chip>
      <v-spacer />
      <v-switch
        v-if="isMain"
        v-model="enabled"
        color="primary"
        hide-details
        density="compact"
        :loading="toggling"
        :label="enabled ? '已启用' : '已停用'"
        class="sdas-switch"
        @update:model-value="toggleEnabled"
      />
      <v-btn
        size="small"
        variant="tonal"
        color="primary"
        icon="mdi-refresh"
        title="刷新本页数据"
        :loading="loading"
        @click="load(false)"
      />
      <v-btn
        v-if="isMain"
        size="small"
        variant="tonal"
        icon="mdi-folder-move-outline"
        title="立即整理一次（把已下载的搬进媒体库）"
        :loading="organizing"
        @click="doOrganize"
      />
      <v-btn
        v-if="isMain"
        size="small"
        color="primary"
        variant="tonal"
        prepend-icon="mdi-play"
        :loading="running"
        @click="doRun"
      >
        立即运行
      </v-btn>
    </div>

    <!-- 统计卡片 -->
    <v-row dense class="mb-3">
      <v-col v-for="item in statCards" :key="item.label" cols="6" sm="3">
        <v-card variant="tonal" class="pa-3" :title="item.title">
          <div class="text-caption sdas-dim">{{ item.label }}</div>
          <div class="text-h6">{{ item.value }}</div>
        </v-card>
      </v-col>
    </v-row>

    <v-alert
      v-if="!enabled"
      type="warning"
      variant="tonal"
      density="compact"
      class="mb-3"
    >
      插件未启用或尚未配置演员/搜索站点，请先到配置页填写后保存。
    </v-alert>

    <v-alert
      v-if="running"
      type="info"
      variant="tonal"
      density="compact"
      class="mb-3"
    >
      正在后台执行（演员多时一轮要跑较久），完成后此页会自动更新…
    </v-alert>

    <v-alert
      v-else-if="lastMessage"
      :type="payload?.last_result?.success === false ? 'warning' : 'success'"
      variant="tonal"
      density="compact"
      class="mb-3"
    >
      {{ lastMessage }}
    </v-alert>

    <!-- 运行配置摘要（侧栏「运行状态」入口的只读概览） -->
    <v-card v-if="!isMain" variant="outlined" class="mb-3">
      <div class="d-flex align-center pa-3 pb-1">
        <v-icon icon="mdi-cog-outline" size="18" class="mr-2" />
        <span class="text-subtitle-2">运行配置</span>
        <v-spacer />
        <span class="text-caption sdas-dim">在插件配置页修改后保存即可生效</span>
      </div>
      <div class="px-3 pb-3">
        <div v-for="item in configRows" :key="item.label" class="d-flex align-start py-1">
          <span class="text-caption sdas-dim sdas-label">{{ item.label }}</span>
          <span class="text-body-2">{{ item.value }}</span>
        </div>
      </div>
    </v-card>

    <!-- 演员快照 -->
    <v-card variant="outlined" class="mb-3">
      <div class="d-flex align-center pa-3 pb-1">
        <v-icon icon="mdi-account-multiple-outline" size="18" class="mr-2" />
        <span class="text-subtitle-2">演员（{{ actorRows.length }}）</span>
        <v-spacer />
        <span class="text-caption sdas-dim">
          上次运行：{{ formatTime(summary.last_run) }}
        </span>
      </div>
      <div class="px-3 pb-3">
        <div v-if="!actorRows.length" class="text-caption sdas-dim">尚未配置演员</div>
        <div class="d-flex flex-wrap" style="gap: 6px">
          <v-chip
            v-for="row in actorRows"
            :key="row.key"
            size="small"
            variant="tonal"
            :color="row.errors.length ? 'warning' : undefined"
            :title="actorTitle(row)"
          >
            {{ row.name }}
            <span v-if="row.works.length" class="sdas-dim ml-1">{{ row.works.length }}</span>
            <v-icon v-if="row.errors.length" icon="mdi-alert-circle-outline" size="14" class="ml-1" />
          </v-chip>
        </div>
        <div v-for="row in actorRows.filter((item) => item.errors.length)" :key="`err-${row.key}`" class="text-caption sdas-dim mt-1">
          · {{ row.name }}：{{ row.errors.join('；') }}
        </div>
      </div>
    </v-card>

    <!-- 演员作品墙 -->
    <v-card v-if="isMain" variant="outlined" class="mb-3">
      <div class="d-flex align-center pa-3 pb-1 flex-wrap" style="gap: 8px">
        <v-icon icon="mdi-movie-open-star-outline" size="18" class="mr-2" />
        <span class="text-subtitle-2">演员作品（{{ worksSummary.total }}）</span>
        <v-chip size="x-small" variant="tonal" color="primary">待订阅 {{ worksSummary.pending }}</v-chip>
        <v-chip v-if="worksSummary.cooling" size="x-small" variant="tonal" color="warning">
          冷却 {{ worksSummary.cooling }}
        </v-chip>
        <v-chip size="x-small" variant="tonal" color="success">已下载 {{ worksSummary.downloaded }}</v-chip>
        <v-spacer />
        <span class="text-caption sdas-dim">
          快照 {{ works.refreshed_at ? formatTime(works.refreshed_at) : '未刷新' }}
        </span>
        <v-btn
          size="small"
          variant="tonal"
          color="primary"
          prepend-icon="mdi-cloud-refresh-outline"
          :loading="refreshingWorks"
          title="只去 TMDB / 豆瓣 拉取演员作品，不触发下载"
          @click="doRefreshWorks"
        >
          刷新作品
        </v-btn>
      </div>

      <div class="d-flex align-center flex-wrap px-3 pb-2" style="gap: 8px">
        <v-text-field
          v-model="workKeyword"
          density="compact"
          variant="outlined"
          hide-details
          prepend-inner-icon="mdi-magnify"
          placeholder="筛选剧名 / 演员"
          class="sdas-filter"
        />
        <v-select
          v-model="workState"
          :items="stateFilters"
          density="compact"
          variant="outlined"
          hide-details
          class="sdas-state-filter"
        />
        <v-select
          v-model="workActor"
          :items="actorFilters"
          density="compact"
          variant="outlined"
          hide-details
          class="sdas-state-filter"
        />
      </div>

      <v-alert
        v-if="workMessage"
        type="info"
        variant="tonal"
        density="compact"
        class="mx-3 mb-2"
      >
        {{ workMessage }}
        <div class="text-caption sdas-dim">下载完成后由「整理入库」搬到媒体库，可在下方账本查看。</div>
      </v-alert>

      <v-table density="compact" hover class="sdas-table">
        <thead>
          <tr>
            <th class="text-start">剧名</th>
            <th class="text-start">年份</th>
            <th class="text-start">演员</th>
            <th class="text-start">发现</th>
            <th class="text-start">状态</th>
            <th class="text-end">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in visibleWorks" :key="row.key">
            <td>
              <div class="sdas-title" :title="row.alt_title || row.title">{{ row.title }}</div>
            </td>
            <td class="text-caption">{{ row.year || '—' }}</td>
            <td class="text-caption">{{ row.actor || '—' }}</td>
            <td class="text-caption text-no-wrap">
              <v-chip size="x-small" variant="tonal">{{ sourceLabel(row.source) }}</v-chip>
              <span v-if="row.type" class="sdas-dim ml-1">{{ row.type }}</span>
            </td>
            <td>
              <v-chip
                size="x-small"
                variant="tonal"
                :color="stateColor(row.state)"
                :title="row.torrent_title || ''"
              >
                {{ stateLabel(row) }}
              </v-chip>
            </td>
            <td class="text-end text-no-wrap">
              <v-btn
                v-if="row.state === 'pending' || row.state === 'cooling'"
                size="x-small"
                variant="tonal"
                color="primary"
                prepend-icon="mdi-plus"
                :loading="subscribingKey === row.key"
                @click="doSubscribe(row)"
              >
                订阅
              </v-btn>
              <v-btn
                size="x-small"
                variant="text"
                icon="mdi-magnify"
                title="到宿主的资源搜索页按剧名搜一遍（人工复核）"
                :href="workResourceUrl(row)"
                target="_blank"
              />
            </td>
          </tr>
          <tr v-if="!visibleWorks.length">
            <td colspan="6" class="text-center text-caption sdas-dim py-3">
              {{ worksEmptyHint }}
            </td>
          </tr>
        </tbody>
      </v-table>

      <div v-if="visibleWorks.length < filteredWorks.length" class="pa-2 text-center">
        <v-btn size="small" variant="text" @click="workLimit += 50">
          显示更多（还有 {{ filteredWorks.length - visibleWorks.length }} 部）
        </v-btn>
      </div>

      <div v-else-if="works.running" class="px-3 pb-2 text-caption sdas-dim">
        后台任务执行中，作品列表随后会自动更新…
      </div>
    </v-card>

    <!-- 账本 -->
    <v-card v-if="isMain" variant="outlined" class="mb-3">
      <div class="d-flex align-center pa-3 pb-1 flex-wrap" style="gap: 8px">
        <v-icon icon="mdi-book-check-outline" size="18" class="mr-2" />
        <span class="text-subtitle-2">已下载账本（{{ ledger.length }}）</span>
        <v-spacer />
        <v-text-field
          v-model="keyword"
          density="compact"
          variant="outlined"
          hide-details
          prepend-inner-icon="mdi-magnify"
          placeholder="筛选剧名 / 演员"
          class="sdas-filter"
        />
        <v-btn
          size="small"
          variant="text"
          color="error"
          :disabled="!ledger.length"
          @click="confirmClear = true"
        >
          清空账本
        </v-btn>
      </div>

      <v-table density="compact" hover class="sdas-table">
        <thead>
          <tr>
            <th class="text-start">剧名</th>
            <th class="text-start">年份</th>
            <th class="text-start">集数</th>
            <th class="text-start">站点</th>
            <th class="text-start">演员</th>
            <th class="text-start">状态</th>
            <th class="text-end">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in visibleLedger" :key="row.key">
            <td>
              <div class="sdas-title" :title="row.torrent_title || row.title">{{ row.title }}</div>
            </td>
            <td class="text-caption">{{ row.year || '—' }}</td>
            <td class="text-caption">{{ row.episodes ? `全${row.episodes}集` : '—' }}</td>
            <td class="text-caption">{{ row.site_name || '—' }}</td>
            <td class="text-caption">{{ row.actor || '—' }}</td>
            <td>
              <v-chip
                size="x-small"
                variant="tonal"
                :color="row.organized ? 'success' : 'info'"
                :title="row.organized_path || ''"
              >
                {{ row.organized ? '已整理' : '已下载' }}
              </v-chip>
              <span v-if="(row.alternatives || 0) > 1" class="text-caption sdas-dim ml-1" title="同剧命中多个资源，已择优">
                {{ row.alternatives }} 选 1
              </span>
            </td>
            <td class="text-end text-no-wrap">
              <v-btn
                size="x-small"
                variant="text"
                icon="mdi-magnify"
                title="到宿主的资源搜索页按剧名搜一遍（人工复核）"
                :href="resourceUrl(row)"
                target="_blank"
              />
              <v-btn
                size="x-small"
                variant="text"
                icon="mdi-delete-outline"
                color="error"
                title="从账本移除（下次轮询可重新下载）"
                :loading="pendingKey === row.key"
                @click="askRemove(row)"
              />
            </td>
          </tr>
          <tr v-if="!visibleLedger.length">
            <td colspan="7" class="text-center text-caption sdas-dim py-3">
              {{ ledger.length ? '没有匹配的记录' : '暂无记录，运行一轮后这里会出现已下载的剧' }}
            </td>
          </tr>
        </tbody>
      </v-table>
    </v-card>

    <!-- 冷却列表 -->
    <v-card v-if="isMain && cooldown.length" variant="outlined" class="mb-3">
      <div class="d-flex align-center pa-3 pb-1">
        <v-icon icon="mdi-timer-sand" size="18" class="mr-2" />
        <span class="text-subtitle-2">未命中冷却（{{ cooldown.length }}）</span>
        <v-spacer />
        <v-btn size="small" variant="text" @click="doClearCooldown">清空冷却</v-btn>
      </div>
      <div class="px-3 pb-3">
        <div class="d-flex flex-wrap" style="gap: 6px">
          <v-chip
            v-for="row in cooldown"
            :key="row.key"
            size="small"
            variant="tonal"
            color="warning"
            :title="`${row.title}${row.year ? '（' + row.year + '）' : ''}｜${formatCooldown(row.remaining_minutes)}`"
          >
            {{ row.title }}
            <span class="sdas-dim ml-1">{{ formatCooldown(row.remaining_minutes) }}</span>
          </v-chip>
        </div>
        <div class="text-caption sdas-dim mt-2">
          这些剧在站点上暂时搜不到资源，24 小时内不再重复搜索（成功下载或手动清空后恢复）。
        </div>
      </div>
    </v-card>

    <!-- 移除确认 -->
    <v-dialog v-model="removeDialog" max-width="420">
      <v-card class="pa-4">
        <div class="text-subtitle-2 mb-2">从账本移除「{{ removeTarget?.title }}」？</div>
        <div class="text-caption sdas-dim mb-3">
          移除后这部剧会在下一轮轮询时重新搜索并下载，已下载的文件不会被删除。
        </div>
        <div class="d-flex">
          <v-spacer />
          <v-btn variant="text" @click="removeDialog = false">取消</v-btn>
          <v-btn color="error" variant="tonal" :loading="removing" @click="doRemove">移除</v-btn>
        </div>
      </v-card>
    </v-dialog>

    <!-- 清空账本确认 -->
    <v-dialog v-model="confirmClear" max-width="420">
      <v-card class="pa-4">
        <div class="text-subtitle-2 mb-2">清空全部账本记录？</div>
        <div class="text-caption sdas-dim mb-3">
          账本用于去重：清空后所有剧都会被当作未下载，下一轮会重新搜索并下载（已下载文件不受影响）。
          同时会清空未命中冷却。
        </div>
        <div class="d-flex">
          <v-spacer />
          <v-btn variant="text" @click="confirmClear = false">取消</v-btn>
          <v-btn color="error" variant="tonal" :loading="clearing" @click="doClear">清空</v-btn>
        </div>
      </v-card>
    </v-dialog>
  </div>
</template>

<script setup lang="ts">
/**
 * 插件详情页 / 侧栏全页面板（联邦暴露名 ./Page，侧栏全页经 AppPage 薄壳复用）。
 *
 * 数据全部来自插件自己的 `GET /status`：账本、冷却、演员快照与运行摘要。
 * 本插件不走宿主订阅系统，因此这里没有任何订阅按钮 —— 面板的核心动作是
 * 「立即运行」「整理入库」「移出账本」与「人工到站点复核」。
 */
import { computed, onMounted, ref } from 'vue'
import {
  API_BASE,
  clearCooldown,
  clearLedger,
  fetchConfig,
  fetchStatus,
  fetchWorks,
  formatCooldown,
  formatTime,
  organizeNow,
  PLUGIN_ID,
  refreshWorks,
  removeLedgerEntry,
  resolveApi,
  resourceSearchUrl,
  runOnce,
  saveConfig,
  subscribeWork,
} from './api'
import type {
  ActorRecord,
  LedgerEntry,
  PluginApi,
  PluginConfig,
  SiteOption,
  StatusPayload,
  WorkItem,
  WorksPayload,
} from './types'

const props = defineProps<{
  /** 宿主注入的 axios 实例 */
  api?: PluginApi
  /** 插件配置（宿主在详情页会传入） */
  config?: Partial<PluginConfig>
  /** 当前插件实例 ID */
  pluginId?: string
  /** 侧栏全页上下文（nav_key） */
  navKey?: string
  /** 是否使用整页留白（侧栏全页为 true） */
  full?: boolean
  /**
   * 展示模式：
   * - `main`（默认）：完整面板（操作按钮 + 账本 + 冷却）
   * - `status`：只读概览（运行摘要 + 演员解析状态 + 配置摘要），侧栏「运行状态」入口用
   */
  mode?: string
}>()

const emit = defineEmits(['action', 'close'])

/** 是否主面板模式（侧栏第二个入口是只读概览） */
const isMain = computed(() => props.mode !== 'status')

const loading = ref(false)
const running = ref(false)
const organizing = ref(false)
const clearing = ref(false)
const removing = ref(false)
const toggling = ref(false)
const pendingKey = ref('')
const keyword = ref('')
const confirmClear = ref(false)
const removeDialog = ref(false)
const removeTarget = ref<LedgerEntry | null>(null)

const payload = ref<StatusPayload | null>(null)
/** 插件配置的搜索站点，用于「人工到站点复核」时带上同一批站点 */
const searchSites = ref<number[]>([])
/** 从后端取回的配置（只读概览模式展示用；宿主传入的 props.config 优先级更高时以它为准） */
const remoteConfig = ref<Partial<PluginConfig>>({})
/** 站点候选，用于把配置里的站点 ID 翻译成名字 */
const siteOptions = ref<SiteOption[]>([])

// ─── 作品墙状态 ─────────────────────────────────────────────────

/** 作品墙数据（发现层快照 + 每条状态），来自 GET /works */
const works = ref<WorksPayload>({
  items: [],
  summary: { total: 0, pending: 0, cooling: 0, downloaded: 0 },
  refreshed_at: '',
  running: false,
  configured: false,
  actors: [],
  actor_count: 0,
})
const workKeyword = ref('')
const workState = ref('all')
const workActor = ref('all')
/** 一次最多渲染多少行（作品可能上百条，用「显示更多」分批） */
const workLimit = ref(40)
const refreshingWorks = ref(false)
const subscribingKey = ref('')
const workMessage = ref('')

const worksSummary = computed(() => works.value.summary)

const stateFilters = [
  { title: '全部状态', value: 'all' },
  { title: '待订阅', value: 'pending' },
  { title: '冷却中', value: 'cooling' },
  { title: '已下载', value: 'downloaded' },
]

/** 演员筛选项：由作品数据自身推导，避免与配置里的写法不一致 */
const actorFilters = computed(() => [
  { title: '全部演员', value: 'all' },
  ...Array.from(new Set(works.value.items.map((item) => String(item.actor || '')).filter(Boolean))).map(
    (name) => ({ title: name, value: name })
  ),
])

const filteredWorks = computed<WorkItem[]>(() => {
  const text = workKeyword.value.trim().toLowerCase()
  const state = workState.value
  const actor = workActor.value
  return works.value.items.filter((row) => {
    if (state === 'downloaded') {
      if (row.state !== 'downloaded' && row.state !== 'organized') return false
    } else if (state !== 'all' && row.state !== state) {
      return false
    }
    if (actor !== 'all' && String(row.actor || '') !== actor) return false
    if (text) {
      const haystack = `${row.title || ''} ${row.actor || ''} ${row.year || ''} ${row.alt_title || ''}`
      if (!haystack.toLowerCase().includes(text)) return false
    }
    return true
  })
})

const visibleWorks = computed<WorkItem[]>(() => filteredWorks.value.slice(0, workLimit.value))

const worksEmptyHint = computed(() => {
  if (!works.value.configured) {
    return '还没配置演员与搜索站点：先到配置页填写并保存'
  }
  if (!works.value.items.length) {
    if (works.value.running) return '正在拉取演员作品…'
    return '点右上角「刷新作品」，插件会去 TMDB / 豆瓣 拉取演员的作品清单'
  }
  return '没有匹配的作品，换个筛选条件试试'
})

const enabled = computed({
  get: () => payload.value?.enabled ?? props.config?.enabled ?? false,
  set: (value: boolean) => {
    if (payload.value) payload.value.enabled = value
  },
})

const summary = computed(() => payload.value?.summary || ({} as StatusPayload['summary']))
const ledger = computed<LedgerEntry[]>(() => payload.value?.ledger || [])
const cooldown = computed(() => payload.value?.cooldown || [])
const cooldownCount = computed(() => cooldown.value.length)
const lastMessage = computed(() => String(payload.value?.last_result?.message || ''))

const actorRows = computed(() => {
  const actors = payload.value?.actors || {}
  return Object.keys(actors).map((key) => {
    const record = actors[key] as ActorRecord
    return {
      key,
      name: record?.name || key,
      works: record?.works || [],
      errors: record?.errors || [],
      ids: [record?.douban_id ? `豆瓣 ${record.douban_id}` : '', record?.tmdb_id ? `TMDB ${record.tmdb_id}` : '']
        .filter(Boolean)
        .join('｜'),
    }
  })
})

const statCards = computed(() => [
  { label: '演员', value: String(summary.value.actor_count || 0), title: '配置并已解析的演员数' },
  {
    label: '候选作品',
    value: String(summary.value.candidate_count || 0),
    title: '上一轮发现层产出的候选剧数（TMDB + 豆瓣并集）',
  },
  { label: '已下载', value: String(summary.value.downloaded_count || 0), title: '账本里的记录数' },
  { label: '已整理', value: String(summary.value.organized_count || 0), title: '已搬进媒体库的剧数' },
])

/** 站点 ID → 站点名（配置摘要展示用） */
function siteName(id: number): string {
  const hit = siteOptions.value.find((item) => Number(item.value) === Number(id))
  return hit?.title || `站点 ${id}`
}

/** 整理方式 → 中文 */
function transferLabel(value?: string): string {
  if (value === 'copy') return '复制'
  if (value === 'move') return '移动'
  return '硬链接'
}

/** Cookie 来源 → 可读文案 */
function cookieLabel(source?: string): string {
  if (source === 'manual') return '插件内手填的 Cookie'
  if (source === 'cookiecloud') return '宿主 CookieCloud（自动读取）'
  return '未取到（豆瓣匿名搜索额度极低）'
}

/** 只读概览模式下的配置摘要行 */
const configRows = computed(() => {
  const config: Partial<PluginConfig> = { ...(props.config || {}), ...remoteConfig.value }
  const sites = (config.sites || []) as number[]
  return [
    {
      label: '搜索站点',
      value: sites.length
        ? sites.map((id) => siteName(Number(id))).join('，')
        : '未配置（无法搜索）',
    },
    {
      label: '搜索范围',
      value: config.prefer_short_drama_category === false ? '全站搜索' : '优先站点「短剧」分类',
    },
    { label: '下载器', value: String(config.downloader || '跟随宿主默认') },
    { label: '下载目录', value: String(config.download_path || '未配置') },
    { label: '媒体库目录', value: String(config.library_path || '未配置') },
    {
      label: '整理方式',
      value: `${transferLabel(config.transfer_type)}${
        config.organize_enabled === false ? '（整理已关闭）' : ''
      }`,
    },
    {
      label: '运行间隔',
      value: `${config.interval_hours || 6} 小时轮询 / ${
        config.organize_interval_minutes || 30
      } 分钟整理`,
    },
    { label: '豆瓣登录态', value: cookieLabel(config.douban_cookie_source) },
  ]
})

/** 账本筛选：剧名 / 演员 / 站点 任一命中 */
const visibleLedger = computed<LedgerEntry[]>(() => {
  const text = keyword.value.trim().toLowerCase()
  if (!text) return ledger.value
  return ledger.value.filter((row) =>
    `${row.title || ''} ${row.actor || ''} ${row.site_name || ''}`.toLowerCase().includes(text)
  )
})

function actorTitle(row: {
  name: string
  ids: string
  works: { length: number }
  errors: string[]
}): string {
  const parts = [row.name]
  if (row.ids) parts.push(row.ids)
  parts.push(`${row.works.length} 部作品`)
  if (row.errors.length) parts.push(row.errors.join('；'))
  return parts.join('｜')
}

/** 构造「到宿主资源搜索页按剧名搜一遍」的深链（host 前端是 hash 路由） */
function resourceUrl(row: LedgerEntry): string {
  return resourceSearchUrl(row.title, searchSites.value)
}

// ─── 作品墙 ─────────────────────────────────────────────────────

/** 状态 → 颜色（红涨绿跌不适用，这里用语义色：成功/信息/警告/主色） */
function stateColor(state: string): string {
  if (state === 'organized') return 'success'
  if (state === 'downloaded') return 'info'
  if (state === 'cooling') return 'warning'
  return 'primary'
}

function stateLabel(row: WorkItem): string {
  if (row.state === 'organized') return '已整理'
  if (row.state === 'downloaded') return '已下载'
  if (row.state === 'cooling') return `冷却 ${row.remaining_minutes || 0} 分`
  return '待订阅'
}

/** 发现来源 → 展示名 */
function sourceLabel(source?: string): string {
  if (source === 'tmdb') return 'TMDB'
  if (source === 'douban') return '豆瓣'
  return '未知'
}

/** 作品行的人工复核深链（带插件配置的站点） */
function workResourceUrl(row: WorkItem): string {
  return resourceSearchUrl(row.title, searchSites.value)
}

function applyWorks(data: WorksPayload): void {
  works.value = data
}

async function loadWorks(): Promise<void> {
  const api = resolveApi(props)
  if (!api) return
  try {
    const data = await fetchWorks(api)
    if (data) applyWorks(data)
  } catch (err) {
    console.warn(`[${PLUGIN_ID}] 读取作品墙失败`, err)
  }
}

/** 刷新作品：只跑发现层，不下载（后端是一次性后台任务，这里轮询 running） */
async function doRefreshWorks(): Promise<void> {
  const api = resolveApi(props)
  if (!api) return
  refreshingWorks.value = true
  workMessage.value = ''
  try {
    const res = await refreshWorks(api, applyWorks)
    workMessage.value = res.message
    await load(false)
  } finally {
    refreshingWorks.value = false
  }
}

/**
 * 订阅一部作品：后端走与轮询完全相同的链路（搜索 → 匹配 → 择优 → 下载），
 * 成功后写账本，因此不会与下一轮自动下载重复。
 */
async function doSubscribe(row: WorkItem): Promise<void> {
  const api = resolveApi(props)
  if (!api) return
  subscribingKey.value = row.key
  workMessage.value = ''
  try {
    const res = await subscribeWork(api, { key: row.key, title: row.title, year: row.year })
    workMessage.value = res.message
    await loadWorks()
    await load(false)
  } finally {
    subscribingKey.value = ''
  }
}

function apply(data: StatusPayload): void {
  payload.value = data
}

async function load(showSpinner = true): Promise<void> {
  const api = resolveApi(props)
  if (!api) return
  if (showSpinner) loading.value = true
  try {
    const data = await fetchStatus(api)
    if (data) apply(data)
  } catch (err) {
    console.warn(`[${PLUGIN_ID}] 读取运行概览失败`, err)
  } finally {
    loading.value = false
  }
}

/** 读取一次配置（拿搜索站点拼「人工复核」深链，同时给只读概览提供配置摘要） */
async function loadConfig(): Promise<void> {
  const api = resolveApi(props)
  if (!api) return
  try {
    const data = await fetchConfig(api)
    remoteConfig.value = data?.config || {}
    searchSites.value = data?.config?.sites || []
    siteOptions.value = data?.options?.sites || []
  } catch (err) {
    console.debug(`[${PLUGIN_ID}] 读取插件配置失败`, err)
  }
}

/** 立即运行一轮：后端排队执行，这里轮询到结束 */
async function doRun(): Promise<void> {
  const api = resolveApi(props)
  if (!api) return
  running.value = true
  try {
    const before = String(summary.value.last_run || '')
    const res = await runOnce(api, apply, before)
    if (!res.ok) {
      await load(false)
    }
    await load(false)
    emit('action')
  } finally {
    running.value = false
  }
}

async function doOrganize(): Promise<void> {
  const api = resolveApi(props)
  if (!api) return
  organizing.value = true
  try {
    await organizeNow(api)
    await load(false)
  } finally {
    organizing.value = false
  }
}

/** 侧栏开关：直接改写配置并落盘，省得再进配置页 */
async function toggleEnabled(value: boolean): Promise<void> {
  const api = resolveApi(props)
  if (!api) return
  toggling.value = true
  try {
    await saveConfig(api, { enabled: value })
    await load(false)
  } catch (err) {
    console.warn(`[${PLUGIN_ID}] 切换启用状态失败`, err)
  } finally {
    toggling.value = false
  }
}

function askRemove(row: LedgerEntry): void {
  removeTarget.value = row
  removeDialog.value = true
}

async function doRemove(): Promise<void> {
  const api = resolveApi(props)
  const row = removeTarget.value
  removeDialog.value = false
  if (!api || !row) return
  removing.value = true
  pendingKey.value = row.key
  try {
    await removeLedgerEntry(api, row.key)
    await load(false)
  } finally {
    removing.value = false
    pendingKey.value = ''
    removeTarget.value = null
  }
}

async function doClear(): Promise<void> {
  const api = resolveApi(props)
  confirmClear.value = false
  if (!api) return
  clearing.value = true
  try {
    await clearLedger(api)
    await load(false)
  } finally {
    clearing.value = false
  }
}

async function doClearCooldown(): Promise<void> {
  const api = resolveApi(props)
  if (!api) return
  await clearCooldown(api)
  await load(false)
}

onMounted(() => {
  void load()
  void loadConfig()
  void loadWorks()
})

/** 让 API_BASE 参与类型检查（保留给将来直接拼接口的场景） */
void API_BASE
</script>

<style scoped>
/* 只使用 scoped 样式 */
.sdas-dim {
  opacity: 0.75;
}

.sdas-switch {
  flex: 0 0 auto;
  margin-right: 4px;
}

.sdas-filter {
  max-width: 220px;
  flex: 1 1 180px;
}

/* 作品墙的状态 / 演员筛选框（窄一点，别把工具条撑开） */
.sdas-state-filter {
  max-width: 150px;
  flex: 0 0 auto;
}

.sdas-label {
  min-width: 96px;
  flex: 0 0 auto;
}

.sdas-table {
  table-layout: auto;
}

.sdas-title {
  max-width: 260px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
