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
      <v-btn
        v-if="isMain"
        size="small"
        variant="tonal"
        color="primary"
        prepend-icon="mdi-cog-outline"
        :loading="settingsLoading"
        title="打开插件设置：演员 / 搜索站点 / 下载器与目录 / 整理方式"
        @click="openSettings"
      >
        设置
      </v-btn>
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
        v-if="isMain && organizeEnabled"
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

    <v-alert
      v-if="!enabled"
      type="warning"
      variant="tonal"
      density="compact"
      class="mb-3"
    >
      插件未启用或尚未配置演员/搜索站点，点右上角「设置」即可就地填写并保存。
    </v-alert>

    <v-alert
      v-if="settingsNotice"
      closable
      type="success"
      variant="tonal"
      density="compact"
      class="mb-3"
      @click:close="settingsNotice = ''"
    >
      {{ settingsNotice }}
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
            :title="actorTitle(row)"
          >
            {{ row.name }}
            <span v-if="row.works.length" class="sdas-dim ml-1">{{ row.works.length }}</span>
            <!-- 等待重试只留一个很轻的沙漏标记（完整原因在 tooltip 里），不再用警示色 -->
            <v-icon
              v-else-if="row.state === 'waiting'"
              icon="mdi-timer-sand"
              size="13"
              class="ml-1 sdas-retry-icon"
            />
          </v-chip>
        </div>
        <!-- 失败不再逐条铺开：临时性失败（豆瓣登录态失效 / 限流）插件每轮都会自动重试，
             这里只给一句汇总；「豆瓣没有影视作品集」是稳定结果、不是故障，另算一类。 -->
        <div v-if="actorsHint" class="text-caption sdas-dim mt-2">{{ actorsHint }}</div>
      </div>
    </v-card>

    <!-- 演员作品墙（与「豆瓣演员订阅」同形：筛选工具条 + 海报卡片墙 + 分页） -->
    <v-card v-if="isMain" variant="outlined" class="mb-3">
      <v-card-title class="d-flex align-center flex-wrap sdas-titlebar">
        <v-icon icon="mdi-movie-open-star-outline" class="mr-1" />
        <span>演员作品</span>
        <v-chip size="small" variant="tonal">{{ worksSummary.total }} 部</v-chip>
        <v-chip v-if="worksSummary.pending" size="small" variant="tonal" color="primary">
          待订阅 {{ worksSummary.pending }}
        </v-chip>
        <v-chip v-if="worksSummary.cooling" size="small" variant="tonal" color="warning">
          冷却 {{ worksSummary.cooling }}
        </v-chip>
        <v-chip v-if="worksSummary.downloaded" size="small" variant="tonal" color="info">
          已下载 {{ worksSummary.downloaded }}
        </v-chip>
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
      </v-card-title>

      <v-card-text class="pt-0">
        <!-- 演员筛选：与豆瓣插件一致，用可换行的 chip 行。
             刻意**不用 v-chip-group**：它是横向滑动容器（自带左右箭头，
             多出来的演员只能靠点箭头翻，展开也看不出效果）。 -->
        <div class="sdas-chips" :class="{ 'sdas-chips-expanded': actorsExpanded }">
          <div class="sdas-actor-chips">
            <v-chip
              size="small"
              variant="tonal"
              :color="workActor === ALL_ACTORS ? 'primary' : undefined"
              @click="workActor = ALL_ACTORS"
            >
              全部演员
            </v-chip>
            <v-chip
              v-for="item in visibleActorFilters"
              :key="item.value"
              size="small"
              variant="tonal"
              :color="workActor === item.value ? 'primary' : undefined"
              :title="`只看「${item.value}」的作品`"
              @click="workActor = item.value"
            >
              {{ item.value }}
              <span class="ml-1 sdas-dim">{{ item.count }}</span>
            </v-chip>
          </div>
        </div>
        <div v-if="actorFilters.length > ACTOR_COLLAPSE_LIMIT" class="mt-1">
          <v-btn
            size="x-small"
            variant="text"
            color="primary"
            :append-icon="actorsExpanded ? 'mdi-chevron-up' : 'mdi-chevron-down'"
            @click="actorsExpanded = !actorsExpanded"
          >
            {{ actorsExpanded ? '收起' : `展开全部（共 ${actorFilters.length} 位）` }}
          </v-btn>
        </div>

        <div class="d-flex align-center flex-wrap mt-2 sdas-toolbar">
          <v-btn-toggle v-model="workState" density="compact" variant="outlined" divided>
            <v-btn size="small" value="all">全部</v-btn>
            <v-btn size="small" value="pending">待订阅</v-btn>
            <v-btn size="small" value="cooling">冷却中</v-btn>
            <v-btn size="small" value="downloaded">已下载</v-btn>
          </v-btn-toggle>
          <v-text-field
            v-model="workKeyword"
            density="compact"
            variant="outlined"
            hide-details
            clearable
            prepend-inner-icon="mdi-magnify"
            placeholder="搜索剧名 / 演员"
            class="sdas-filter"
          />
          <v-spacer />
          <span class="text-caption sdas-dim sdas-count">
            筛出 {{ filteredWorks.length }} 部
          </span>
        </div>
      </v-card-text>

      <v-alert
        v-if="workMessage"
        type="info"
        variant="tonal"
        density="compact"
        class="mx-3 mb-2"
      >
        {{ workMessage }}
        <div v-if="organizeEnabled" class="text-caption sdas-dim">
          下载完成后由「整理入库」搬到媒体库，可在下方账本查看。
        </div>
        <div v-else class="text-caption sdas-dim">
          下载完成后由外部整理器入库（本插件不参与整理），可在下方账本查看。
        </div>
      </v-alert>

      <div class="px-3 pb-3">
        <v-progress-linear
          v-if="works.running || refreshingWorks"
          indeterminate
          color="primary"
          class="mb-3"
        />

        <!-- 作品卡片墙：海报 + 状态徽标 + 一键订阅，与「豆瓣演员订阅」同形 -->
        <WorkGrid
          :works="pagedWorks"
          :pending-key="subscribingKey"
          :sites="searchSites"
          :empty-text="worksEmptyHint"
          @subscribe="doSubscribe"
        />

        <!-- 分页：作品多时每页只渲染 20 张，避免长列表拖垮渲染。
             用 v-btn 手写而非 v-pagination：卡片墙在联邦组件里，
             手写按钮不依赖任何外部组件的注册情况。 -->
        <div v-if="workPageCount > 1" class="d-flex align-center justify-center mt-3 ga-2">
          <v-btn
            size="small"
            variant="tonal"
            icon="mdi-chevron-left"
            :disabled="workPage <= 1"
            @click="workPage = Math.max(1, workPage - 1)"
          />
          <span class="sdas-page-info">第 {{ workPage }} / {{ workPageCount }} 页</span>
          <v-btn
            size="small"
            variant="tonal"
            icon="mdi-chevron-right"
            :disabled="workPage >= workPageCount"
            @click="workPage = Math.min(workPageCount, workPage + 1)"
          />
        </div>
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

    <!-- 设置弹窗：面板内直达配置。
         宿主侧栏全页壳（plugin-app）只注入 api / nav-key / plugin-id，**不提供任何设置入口**，
         面板必须自己画一个；否则用户只能绕「设置 → 插件 → 找到本插件 → 配置」。
         这里直接复用联邦暴露的 ./Config 同一份组件（自行 PUT /config 落盘），
         与插件详情页的配置弹窗内容完全一致，不存在两套配置口径。 -->
    <v-dialog v-model="settingsDialog" max-width="1000">
      <div class="sdas-settings">
        <ConfigPanel
          v-if="settingsDialog"
          :initial-config="settingsConfig"
          :api="props.api"
          @close="settingsDialog = false"
          @save="onConfigSaved"
          @switch="settingsDialog = false"
        />
      </div>
    </v-dialog>
  </div>
</template>

<script setup lang="ts">
/**
 * 插件详情页 / 侧栏全页面板（联邦暴露名 ./Page，侧栏全页经 AppPage 薄壳复用）。
 *
 * 数据全部来自插件自己的 `GET /status`：账本、冷却、演员快照与运行摘要。
 * 本插件不走宿主订阅系统，因此这里没有任何订阅按钮 —— 面板的核心动作是
 * 「设置」（就地打开完整配置弹窗）、「立即运行」「整理入库」「移出账本」与
 * 「人工到站点复核」。
 */
import { computed, onMounted, ref, watch } from 'vue'
import ConfigPanel from './Config.vue'
import WorkGrid from './WorkGrid.vue'
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
/** 状态筛选（v-btn-toggle 的取值，与卡片墙的状态徽标同口径） */
const workState = ref('all')
const workActor = ref('all')
/** 一次最多渲染多少张卡片（作品可能上百条，用分页而非无限拉长页面） */
const WORK_PAGE_SIZE = 20
const workPage = ref(1)
const refreshingWorks = ref(false)
const subscribingKey = ref('')
const workMessage = ref('')

/** 设置弹窗状态（面板标题栏「设置」按钮 → 就地打开完整配置页） */
const settingsDialog = ref(false)
const settingsLoading = ref(false)
/** 打开设置时快照下来的完整配置（Config 组件只在挂载时读一次 initialConfig） */
const settingsConfig = ref<Partial<PluginConfig>>({})
const settingsNotice = ref('')

/** 演员筛选的「全部」哨兵值（与豆瓣插件同一套写法） */
const ALL_ACTORS = 'all'
/** 演员筛选区超过这个数量就默认折叠，避免筛选区占掉大半屏 */
const ACTOR_COLLAPSE_LIMIT = 12
const actorsExpanded = ref(false)

const worksSummary = computed(() => works.value.summary)

/** 演员筛选项：由作品数据自身推导，避免与配置里的写法不一致 */
const actorFilters = computed(() =>
  Array.from(new Set(works.value.items.map((item) => String(item.actor || '')).filter(Boolean))).map(
    (name) => ({
      value: name,
      count: works.value.items.filter((item) => String(item.actor || '') === name).length,
    })
  )
)

/** 折叠时只列前若干位；当前选中的演员强制保留，否则会看不到自己选中了什么 */
const visibleActorFilters = computed(() => {
  const all = actorFilters.value
  if (actorsExpanded.value || all.length <= ACTOR_COLLAPSE_LIMIT) return all
  const head = all.slice(0, ACTOR_COLLAPSE_LIMIT)
  const current = all.find((item) => item.value === workActor.value)
  if (current && !head.includes(current)) return [current, ...head]
  return head
})

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
    if (actor !== ALL_ACTORS && String(row.actor || '') !== actor) return false
    if (text) {
      const haystack = `${row.title || ''} ${row.actor || ''} ${row.year || ''} ${row.alt_title || ''}`
      if (!haystack.toLowerCase().includes(text)) return false
    }
    return true
  })
})

/** 作品墙分页 */
const workPageCount = computed(() =>
  Math.max(1, Math.ceil(filteredWorks.value.length / WORK_PAGE_SIZE))
)
const pagedWorks = computed<WorkItem[]>(() => {
  const start = (workPage.value - 1) * WORK_PAGE_SIZE
  return filteredWorks.value.slice(start, start + WORK_PAGE_SIZE)
})

/** 任何筛选条件变化都回到第一页，避免停留在越界 / 过时页 */
watch([workKeyword, workState, workActor], () => {
  workPage.value = 1
})

const worksEmptyHint = computed(() => {
  if (!works.value.configured) {
    return '还没配置演员与搜索站点：点右上角「设置」填写并保存'
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
      /** 后端归一的状态：''（正常）/ 'waiting'（等自动重试）/ 'empty'（豆瓣确无影视条目） */
      state: record?.state || '',
      ids: [record?.douban_id ? `豆瓣 ${record.douban_id}` : '', record?.tmdb_id ? `TMDB ${record.tmdb_id}` : '']
        .filter(Boolean)
        .join('｜'),
    }
  })
})

/**
 * 是否为「豆瓣登录态失效」类原因（与后端 `classify_error` 的口径一致）。
 * 只用来决定汇总文案是「等登录态恢复」还是「等下一轮重试」。
 */
function isAuthError(message: string): boolean {
  const text = String(message || '')
  return ['Cookie 已失效', '要求登录', 'need_login'].some((marker) => text.includes(marker))
}

/** 等待自动重试的演员（临时性失败：登录态失效 / 限流 / 网络） */
const waitingActors = computed(() => actorRows.value.filter((row) => row.state === 'waiting'))
/** 豆瓣确无影视条目的演员（稳定结果，重试也不会变，不是故障） */
const emptyActors = computed(() => actorRows.value.filter((row) => row.state === 'empty'))

/** 演员区的一句汇总：只在真有需要说明的情况出现，避免逐条刷错误打扰用户 */
const actorsHint = computed(() => {
  const parts: string[] = []
  if (waitingActors.value.length) {
    const expired = waitingActors.value.some((row) => row.errors.some(isAuthError))
    parts.push(
      expired
        ? `${waitingActors.value.length} 位演员等待豆瓣登录态恢复，将自动重试（重新登录豆瓣并同步 CookieCloud 后恢复）`
        : `${waitingActors.value.length} 位演员本轮未取到作品，将在下一轮自动重试`
    )
  }
  if (emptyActors.value.length) {
    parts.push(`${emptyActors.value.length} 位演员在豆瓣没有影视作品集`)
  }
  return parts.join('；')
})

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

/** 是否由本插件负责整理入库。
 *
 * 默认**关闭**：本插件只做「发现 → 下载」，入库交给外部整理器
 * （宿主上另有 shortdramaorganizer 监听同一个下载目录）。
 * 关闭时页面不再显示「立即整理」入口，概览里的媒体库/整理项也一并让位。
 */
const organizeEnabled = computed<boolean>(() => {
  const cfg = { ...(props.config || {}), ...remoteConfig.value } as Partial<PluginConfig>
  return cfg.organize_enabled === true
})

/** 只读概览模式下的配置摘要行 */
const configRows = computed(() => {
  const config: Partial<PluginConfig> = { ...(props.config || {}), ...remoteConfig.value }
  const sites = (config.sites || []) as number[]
  const rows = [
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
  ]
  if (organizeEnabled.value) {
    rows.push(
      { label: '媒体库目录', value: String(config.library_path || '未配置') },
      { label: '整理方式', value: transferLabel(config.transfer_type) },
      {
        label: '运行间隔',
        value: `${config.interval_hours || 6} 小时轮询 / ${
          config.organize_interval_minutes || 30
        } 分钟整理`,
      }
    )
  } else {
    rows.push(
      { label: '整理', value: '由外部整理器负责（本插件不参与）' },
      { label: '运行间隔', value: `${config.interval_hours || 6} 小时轮询` }
    )
  }
  rows.push({ label: '豆瓣登录态', value: cookieLabel(config.douban_cookie_source) })
  return rows
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
//
// 卡片本身的渲染（海报、状态徽标、订阅按钮、「详情」与「搜索资源」入口）
// 全部收在 WorkGrid.vue 里，与「豆瓣演员订阅」的作品墙同形；
// 这里只负责取数、筛选与把订阅动作转给后端。

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

/**
 * 打开设置弹窗：先把最新配置取回来再渲染。
 *
 * 必须先取配置再挂载 —— Config 组件只在 `onMounted` 里读一次 `initialConfig`，
 * 若先挂载（快照为空）再回填，表单会全空，用户一保存就把已有配置清掉。
 */
async function openSettings(): Promise<void> {
  const api = resolveApi(props)
  settingsNotice.value = ''
  settingsLoading.value = true
  let merged: Partial<PluginConfig> = { ...(props.config || {}), ...remoteConfig.value }
  if (api) {
    try {
      const data = await fetchConfig(api)
      if (data?.config) {
        remoteConfig.value = data.config
        searchSites.value = data.config.sites || []
        merged = { ...(props.config || {}), ...data.config }
      }
    } catch (err) {
      console.debug(`[${PLUGIN_ID}] 打开设置前读取配置失败`, err)
    }
  }
  settingsConfig.value = merged
  settingsLoading.value = false
  settingsDialog.value = true
}

/** 设置弹窗保存回调：Config 组件已自行 PUT /config，这里只需刷新面板口径 */
async function onConfigSaved(cfg?: Partial<PluginConfig>): Promise<void> {
  if (cfg) remoteConfig.value = { ...remoteConfig.value, ...cfg }
  settingsDialog.value = false
  settingsNotice.value = '设置已保存并生效'
  await loadConfig()
  await load(false)
  await loadWorks()
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

/* 演员 chip 上的「等待重试」标记：刻意做得比正文更淡，
   失败原因收进 tooltip —— 临时性失败每轮都会重试，不需要靠颜色报警。 */
.sdas-retry-icon {
  opacity: 0.55;
}

.sdas-filter {
  max-width: 220px;
  flex: 1 1 180px;
}

/* 设置弹窗：配置项不少（演员 / 站点 / 下载器 / 目录 / 整理），
   限高 + 内部滚动，避免小屏上按钮被挤出可视区。 */
.sdas-settings {
  max-height: 88vh;
  overflow-y: auto;
  border-radius: 8px;
}

/* 作品墙标题栏与工具条（与豆瓣插件同一套间距，视觉保持一致） */
.sdas-titlebar {
  flex-wrap: wrap;
  gap: 8px;
  row-gap: 4px;
}

.sdas-toolbar {
  gap: 12px;
}

/* 演员 chip 区：flex 换行 + 纵向滚动（不能用 v-chip-group——那是横向滑动容器） */
.sdas-chips {
  max-height: 96px;
  overflow-y: auto;
}

.sdas-actor-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

/* 展开后放开限高：一次能看到更多演员（仍留上限，上百位时不至于拉爆页面） */
.sdas-chips-expanded {
  max-height: 60vh;
}

.sdas-page-info {
  font-size: 0.82rem;
  opacity: 0.85;
  white-space: nowrap;
}

.sdas-count {
  white-space: nowrap;
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
