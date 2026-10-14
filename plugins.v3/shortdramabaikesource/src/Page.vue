<template>
  <div class="sdbs-root" :class="props.full ? 'pa-4' : 'pa-2'">
    <!-- ── 标题栏 ─────────────────────────────────────────────── -->
    <div class="d-flex align-center mb-3 flex-wrap" style="gap: 8px">
      <v-icon icon="mdi-television-classic" class="mr-1" />
      <h2 class="text-h6 ma-0">短剧百科数据源</h2>
      <v-chip size="small" variant="tonal" :color="enabled ? 'primary' : 'warning'">
        {{ enabled ? '已启用' : '未启用' }}
      </v-chip>
      <v-chip v-if="snapshotChip" size="small" variant="tonal" color="info" :title="snapshotChip">
        榜单快照 {{ snapshotChip }}
      </v-chip>
      <v-chip
        v-if="cacheChip"
        size="small"
        variant="tonal"
        color="secondary"
        title="内存里已缓存的作品详情与演员档案数量（插件重启后重新累积）"
      >
        缓存 {{ cacheChip }}
      </v-chip>
      <v-spacer />
      <v-btn
        v-if="props.full"
        size="small"
        variant="text"
        icon="mdi-close"
        title="关闭"
        @click="emit('close')"
      />
      <v-btn
        size="small"
        variant="tonal"
        color="primary"
        prepend-icon="mdi-cog-outline"
        :loading="configLoading"
        title="打开配置：站点域名 / 榜单范围 / 站外索引 / 探索页回填"
        @click="openSettings"
      >
        设置
      </v-btn>
      <v-switch
        v-model="enabled"
        color="primary"
        hide-details
        density="compact"
        :loading="toggling"
        :label="enabled ? '已启用' : '已停用'"
        class="sdbs-switch"
        @update:model-value="toggleEnabled"
      />
      <v-btn
        size="small"
        variant="tonal"
        color="primary"
        icon="mdi-refresh"
        title="刷新本页状态"
        :loading="loading"
        @click="load()"
      />
    </div>

    <v-alert type="info" variant="tonal" density="compact" class="mb-3">
      短剧在 TMDB / 豆瓣上大量没有条目，宿主识别器建不起媒体身份 —— 本插件补的就是这一段。
      两个搜索框各管一路：<b>左边按片名</b>找作品（先查榜单快照，没有再走站外索引），
      <b>右边按演员名</b>找演员及其全部作品。卡片右下角的「原始数据」可以直接看到插件处理后的完整字段。
    </v-alert>

    <v-row dense>
      <!-- ── 片名搜索 ─────────────────────────────────────────── -->
      <v-col cols="12" md="6">
        <v-card variant="outlined" class="pa-3 sdbs-panel">
          <div class="d-flex align-center mb-2">
            <v-icon icon="mdi-movie-search-outline" size="18" class="mr-1" />
            <span class="text-subtitle-2">按片名搜作品</span>
            <v-spacer />
            <v-progress-circular v-if="titleSearching" size="16" width="2" indeterminate />
          </div>

          <v-text-field
            v-model="titleKeyword"
            density="compact"
            variant="outlined"
            hide-details
            clearable
            prepend-inner-icon="mdi-magnify"
            placeholder="输入短剧片名，例如：女足替补的滚烫夏天"
            @keyup.enter="doSearchTitle"
          />
          <div class="d-flex align-center mt-2 flex-wrap" style="gap: 8px">
            <v-btn
              size="small"
              color="primary"
              variant="tonal"
              :loading="titleSearching"
              :disabled="!titleKeyword.trim()"
              @click="doSearchTitle"
            >
              搜索
            </v-btn>
            <v-btn size="small" variant="text" :disabled="!hasTitleResult" @click="clearTitle">
              清空
            </v-btn>
            <v-spacer />
            <span v-if="titleHint" class="text-caption sdbs-dim">{{ titleHint }}</span>
          </div>

          <!-- 候选列表 -->
          <v-card v-if="titleCandidates.length" variant="tonal" class="pa-2 mt-3">
            <div class="text-caption sdbs-dim mb-1">
              命中 {{ titleCandidates.length }} 条候选，点「识别」看完整详情（按匹配分排序）：
            </div>
            <div
              v-for="candidate in titleCandidates"
              :key="candidate.media_id || candidate.title"
              class="d-flex align-center py-1"
            >
              <v-chip size="x-small" variant="tonal" class="mr-2" :title="`匹配分 ${candidate.score}`">
                {{ candidate.score }}
              </v-chip>
              <span class="text-body-2 flex-grow-1">{{ candidate.title }}</span>
              <span v-if="candidate.episode_count" class="text-caption sdbs-dim mr-2">
                {{ candidate.episode_count }} 集
              </span>
              <v-btn
                size="x-small"
                variant="tonal"
                color="primary"
                :loading="titleLoadingId === candidate.media_id"
                @click="pickTitle(candidate)"
              >
                识别
              </v-btn>
            </div>
          </v-card>

          <!-- 作品卡片 -->
          <v-card v-if="titleRecord" variant="outlined" class="pa-3 mt-3">
            <div class="d-flex" style="gap: 12px">
              <v-img
                :src="proxyImage(titleRecord.poster)"
                width="92"
                height="123"
                aspect-ratio="2/3"
                cover
                class="rounded flex-shrink-0 sdbs-poster"
              />
              <div class="flex-grow-1" style="min-width: 0">
                <div class="text-subtitle-2">{{ titleRecord.title || '（无标题）' }}</div>
                <div class="text-caption sdbs-dim mt-1">{{ titleMeta }}</div>
                <div v-if="titleRecord.tags?.length" class="mt-1">
                  <v-chip
                    v-for="tag in titleRecord.tags"
                    :key="tag"
                    size="x-small"
                    variant="tonal"
                    class="mr-1 mb-1"
                  >
                    {{ tag }}
                  </v-chip>
                </div>
                <div v-if="titleRecord.overview" class="text-caption mt-2 sdbs-clamp">
                  {{ titleRecord.overview }}
                </div>
                <div v-if="titleCast" class="text-caption sdbs-dim mt-2">主演：{{ titleCast }}</div>
              </div>
            </div>
            <div class="d-flex align-center mt-2 flex-wrap" style="gap: 8px">
              <v-btn
                v-if="titleRecord.url"
                size="x-small"
                variant="tonal"
                :href="titleRecord.url"
                target="_blank"
                rel="noopener"
                prepend-icon="mdi-open-in-new"
              >
                站点页面
              </v-btn>
              <v-btn size="x-small" variant="text" @click="titleRawOpen = !titleRawOpen">
                {{ titleRawOpen ? '收起原始数据' : '原始数据' }}
              </v-btn>
            </div>
            <pre v-if="titleRawOpen" class="sdbs-pre mt-2">{{ pretty(titleRecord) }}</pre>
          </v-card>

          <v-alert
            v-else-if="titleMessage"
            type="warning"
            variant="tonal"
            density="compact"
            class="mt-3"
          >
            {{ titleMessage }}
          </v-alert>
        </v-card>
      </v-col>

      <!-- ── 演员搜索 ─────────────────────────────────────────── -->
      <v-col cols="12" md="6">
        <v-card variant="outlined" class="pa-3 sdbs-panel">
          <div class="d-flex align-center mb-2">
            <v-icon icon="mdi-account-search-outline" size="18" class="mr-1" />
            <span class="text-subtitle-2">按演员名搜作品</span>
            <v-spacer />
            <v-progress-circular v-if="actorSearching" size="16" width="2" indeterminate />
          </div>

          <v-text-field
            v-model="actorKeyword"
            density="compact"
            variant="outlined"
            hide-details
            clearable
            prepend-inner-icon="mdi-magnify"
            placeholder="输入演员姓名，例如：魏依珂"
            @keyup.enter="doSearchActor"
          />
          <div class="d-flex align-center mt-2 flex-wrap" style="gap: 8px">
            <v-btn
              size="small"
              color="primary"
              variant="tonal"
              :loading="actorSearching"
              :disabled="!actorKeyword.trim()"
              @click="doSearchActor"
            >
              搜索
            </v-btn>
            <v-btn size="small" variant="text" :disabled="!hasActorResult" @click="clearActor">
              清空
            </v-btn>
            <v-spacer />
            <span v-if="actorHint" class="text-caption sdbs-dim">{{ actorHint }}</span>
          </div>

          <!-- 候选演员 -->
          <v-card v-if="actorCandidates.length" variant="tonal" class="pa-2 mt-3">
            <div class="text-caption sdbs-dim mb-1">
              命中 {{ actorCandidates.length }} 位，点「看作品」拉取档案与全部作品：
            </div>
            <div
              v-for="candidate in actorCandidates"
              :key="candidate.actor_id || candidate.name"
              class="d-flex align-center py-1"
            >
              <v-chip size="x-small" variant="tonal" class="mr-2" :title="`匹配分 ${candidate.score}`">
                {{ candidate.score }}
              </v-chip>
              <span class="text-body-2 flex-grow-1">{{ candidate.name }}</span>
              <span class="text-caption sdbs-dim mr-2">actor:{{ candidate.actor_id }}</span>
              <v-btn
                size="x-small"
                variant="tonal"
                color="primary"
                :loading="actorLoadingId === candidate.actor_id"
                @click="pickActor(candidate)"
              >
                看作品
              </v-btn>
            </div>
          </v-card>

          <!-- 演员档案 + 作品墙 -->
          <div v-if="actorProfile" class="mt-3">
            <v-card variant="outlined" class="pa-3">
              <div class="d-flex" style="gap: 12px">
                <v-avatar size="64" rounded class="flex-shrink-0">
                  <v-img :src="proxyImage(actorProfile.profile)" cover />
                </v-avatar>
                <div class="flex-grow-1" style="min-width: 0">
                  <div class="text-subtitle-2">
                    {{ actorProfile.name || '（无姓名）' }}
                    <span class="text-caption sdbs-dim ml-2">actor:{{ actorProfile.actor_id }}</span>
                  </div>
                  <div class="text-caption sdbs-dim mt-1">{{ actorMeta }}</div>
                  <div v-if="actorProfile.bio" class="text-caption mt-2 sdbs-clamp">
                    {{ actorProfile.bio }}
                  </div>
                </div>
              </div>
              <div v-if="actorProfile.coactors?.length" class="mt-2">
                <span class="text-caption sdbs-dim mr-1">常合作演员：</span>
                <v-chip
                  v-for="co in actorProfile.coactors.slice(0, 12)"
                  :key="co.id || co.name"
                  size="x-small"
                  variant="tonal"
                  class="mr-1 mb-1"
                >
                  {{ co.name }}
                </v-chip>
              </div>
              <div class="d-flex align-center mt-2 flex-wrap" style="gap: 8px">
                <v-btn
                  v-if="actorProfile.url"
                  size="x-small"
                  variant="tonal"
                  :href="actorProfile.url"
                  target="_blank"
                  rel="noopener"
                  prepend-icon="mdi-open-in-new"
                >
                  演员页
                </v-btn>
                <v-btn size="x-small" variant="text" @click="actorRawOpen = !actorRawOpen">
                  {{ actorRawOpen ? '收起原始数据' : '原始数据' }}
                </v-btn>
              </div>
              <pre v-if="actorRawOpen" class="sdbs-pre mt-2">{{ pretty(actorProfile) }}</pre>
            </v-card>

            <!-- 作品墙 -->
            <div class="text-subtitle-2 mt-3 mb-2">
              <v-icon icon="mdi-movie-open-outline" size="18" class="mr-1" />
              全部作品
              <span class="text-caption sdbs-dim ml-1">共 {{ actorProfile.works?.length || 0 }} 部</span>
            </div>
            <v-row dense>
              <v-col
                v-for="(work, index) in actorProfile.works || []"
                :key="work.media_id || index"
                cols="12" sm="6"
              >
                <v-card variant="outlined" class="pa-2 h-100 d-flex flex-column">
                  <div class="d-flex" style="gap: 8px">
                    <v-img
                      :src="proxyImage(work.poster)"
                      width="60"
                      height="80"
                      aspect-ratio="2/3"
                      cover
                      class="rounded flex-shrink-0 sdbs-poster"
                    />
                    <div class="flex-grow-1" style="min-width: 0">
                      <div class="text-body-2 sdbs-work-title">{{ work.title || '（无标题）' }}</div>
                      <div class="text-caption sdbs-dim mt-1">{{ workMeta(work) }}</div>
                      <div v-if="work.tags?.length" class="mt-1">
                        <v-chip
                          v-for="tag in work.tags.slice(0, 3)"
                          :key="tag"
                          size="x-small"
                          variant="tonal"
                          class="mr-1 mb-1"
                        >
                          {{ tag }}
                        </v-chip>
                      </div>
                    </div>
                  </div>
                  <v-spacer />
                  <div class="d-flex align-center mt-1">
                    <v-btn
                      v-if="work.url"
                      size="x-small"
                      variant="text"
                      :href="work.url"
                      target="_blank"
                      rel="noopener"
                    >
                      站点
                    </v-btn>
                    <v-spacer />
                    <v-btn size="x-small" variant="text" @click="toggleWorkRaw(index)">
                      {{ openWorks.has(index) ? '收起' : '原始数据' }}
                    </v-btn>
                  </div>
                  <pre v-if="openWorks.has(index)" class="sdbs-pre mt-1">{{ pretty(work) }}</pre>
                </v-card>
              </v-col>
            </v-row>
          </div>

          <v-alert
            v-else-if="actorMessage"
            type="warning"
            variant="tonal"
            density="compact"
            class="mt-3"
          >
            {{ actorMessage }}
          </v-alert>
        </v-card>
      </v-col>
    </v-row>

    <!-- ── 设置弹窗 ───────────────────────────────────────────── -->
    <v-dialog v-model="settingsOpen" max-width="1080" scrollable>
      <Config
        v-if="settingsOpen"
        :api="props.api"
        :initial-config="remoteConfig"
        @close="settingsOpen = false"
        @save="onConfigSaved"
      />
    </v-dialog>
  </div>
</template>

<script setup lang="ts">
/**
 * 短剧百科数据源 —— 插件详情面板（联邦暴露名 `./Page`）。
 *
 * 为什么这个插件要从 Vuetify（JSON）改成联邦组件：面板上要放**会回传输入的搜索框**，
 * 而宿主的 JSON 页面只支持静态组件树与「点击 → 调接口」这类无参交互，承载不了输入框。
 *
 * 两个搜索框各走一条后端链路（`/search` → `/recognize`；`/actor_search` → `/actor`），
 * 结果都以卡片呈现，并保留「原始数据」展开位 —— 卡片是给人看的，
 * 展开是给排障/核对用的，两者看的是同一份后端返回。
 */
import { computed, ref } from 'vue'
import Config from './Config.vue'
import {
  fetchActor,
  fetchConfig,
  fetchStatus,
  proxyImage,
  recognizeTitle,
  resolveApi,
  saveConfig,
  searchActors,
  searchTitles,
} from './api'
import type {
  ActorCandidate,
  ActorProfile,
  MediaRecord,
  PluginApi,
  PluginConfig,
  StatusPayload,
  TitleCandidate,
  WorkItem,
} from './types'

const props = defineProps<{
  /** 宿主注入的 axios 实例 */
  api?: PluginApi
  /** 插件配置（宿主在详情页会传入） */
  config?: Partial<PluginConfig>
  /** 当前插件实例 ID */
  pluginId?: string
  /** 侧栏全页上下文（本插件不用，保留以兼容宿主传参） */
  navKey?: string
  /** 是否整页留白 */
  full?: boolean
}>()

const emit = defineEmits(['action', 'close'])

const enabled = ref(Boolean(props.config?.enabled))
const toggling = ref(false)
const loading = ref(false)
const configLoading = ref(false)
const settingsOpen = ref(false)
const remoteConfig = ref<Partial<PluginConfig>>({})
const status = ref<StatusPayload | null>(null)

// ── 片名搜索 ──
const titleKeyword = ref('')
const titleSearching = ref(false)
const titleCandidates = ref<TitleCandidate[]>([])
const titleRecord = ref<MediaRecord | null>(null)
const titleMessage = ref('')
const titleRawOpen = ref(false)
const titleLoadingId = ref('')

// ── 演员搜索 ──
const actorKeyword = ref('')
const actorSearching = ref(false)
const actorCandidates = ref<ActorCandidate[]>([])
const actorProfile = ref<ActorProfile | null>(null)
const actorMessage = ref('')
const actorRawOpen = ref(false)
const actorLoadingId = ref('')
/** 已展开原始数据的作品下标（作品可能几十部，逐个展开比一次全铺清爽） */
const openWorks = ref(new Set<number>())

const pretty = (value: unknown) => JSON.stringify(value ?? null, null, 2)

const snapshotChip = computed(() => {
  const lists = status.value?.top_lists || []
  if (!lists.length) return ''
  return `${lists.length} 个榜单`
})

const cacheChip = computed(() => {
  const cache = status.value?.cache
  if (!cache) return ''
  return `详情 ${cache.detail ?? 0} ｜ 演员 ${cache.actor ?? 0}`
})

const titleMeta = computed(() => {
  const record = titleRecord.value
  if (!record) return ''
  const parts: string[] = []
  if (record.year) parts.push(record.year)
  if (record.episode_count) parts.push(`共 ${record.episode_count} 集`)
  if (record.duration_minutes) parts.push(`单集 ${record.duration_minutes} 分钟`)
  if (record.kind) parts.push(record.kind)
  if (record.rating) parts.push(`评分 ${record.rating}`)
  parts.push(`来源 ${record.origin === 'detail' ? '详情页' : '检索结果'}`)
  return parts.join(' ｜ ')
})

const titleCast = computed(() => {
  const actors = titleRecord.value?.actors || []
  if (!actors.length) return ''
  return actors
    .slice(0, 10)
    .map((actor) => (actor.character ? `${actor.name}（饰 ${actor.character}）` : actor.name))
    .join('、')
})

const titleHint = computed(() => {
  if (titleSearching.value) return '检索中，需要 10 秒左右'
  if (titleCandidates.value.length) return `${titleCandidates.value.length} 条候选`
  if (titleRecord.value) return '已取到详情'
  return ''
})

const actorMeta = computed(() => {
  const actor = actorProfile.value
  if (!actor) return ''
  const parts: string[] = []
  if (actor.job_title) parts.push(actor.job_title)
  if (actor.gender) parts.push(`性别 ${actor.gender}`)
  if (actor.nationality) parts.push(actor.nationality)
  parts.push(`作品 ${actor.works_count ?? (actor.works || []).length} 部`)
  return parts.join(' ｜ ')
})

const actorHint = computed(() => {
  if (actorSearching.value) return '检索中，需要 10 秒左右'
  if (actorCandidates.value.length) return `命中 ${actorCandidates.value.length} 位`
  if (actorProfile.value) return `作品 ${actorProfile.value.works_count ?? 0} 部`
  return ''
})

const hasTitleResult = computed(
  () => Boolean(titleCandidates.value.length || titleRecord.value || titleMessage.value),
)
const hasActorResult = computed(
  () => Boolean(actorCandidates.value.length || actorProfile.value || actorMessage.value),
)

function workMeta(work: WorkItem): string {
  const parts: string[] = []
  if (work.kind) parts.push(work.kind)
  if (work.episode_count) parts.push(`${work.episode_count} 集`)
  if (work.rating) parts.push(`评分 ${work.rating}`)
  if (work.heat) parts.push(`热度 ${Math.round(work.heat / 10000)} 万`)
  return parts.join(' ｜ ') || '—'
}

/** 拉运行状态；失败静默（面板不铺错误，只少一块信息） */
async function load(): Promise<void> {
  const api = resolveApi(props)
  if (!api) return
  loading.value = true
  try {
    const payload = await fetchStatus(api)
    if (payload) {
      status.value = payload
      enabled.value = Boolean(payload.enabled)
    }
  } finally {
    loading.value = false
  }
}

/** 启用/停用：读当前配置 → 改一个键 → 存回（避免只提交 enabled 把其它键冲掉） */
async function toggleEnabled(value: unknown): Promise<void> {
  const api = resolveApi(props)
  if (!api) return
  toggling.value = true
  try {
    const current = await fetchConfig(api)
    const merged: Partial<PluginConfig> = { ...(current?.config || remoteConfig.value) }
    merged.enabled = Boolean(value)
    const report = await saveConfig(api, merged)
    if (!report?.success) {
      enabled.value = !value
      titleMessage.value = report?.message || '切换启用状态失败'
      return
    }
    remoteConfig.value = report.config || merged
    await load()
  } finally {
    toggling.value = false
  }
}

async function doSearchTitle(): Promise<void> {
  const api = resolveApi(props)
  const keyword = titleKeyword.value.trim()
  if (!api || !keyword) return
  titleSearching.value = true
  titleMessage.value = ''
  titleRecord.value = null
  titleCandidates.value = []
  titleRawOpen.value = false
  try {
    const report = await searchTitles(api, keyword)
    const candidates = report?.candidates || []
    titleCandidates.value = candidates
    if (!candidates.length) {
      titleMessage.value =
        report?.message ||
        `没搜到「${keyword}」：榜单快照（最新/热门作品）里没有，站外索引也没收录。` +
          '注意片名这一路走的是「搜索引擎的 site: 收录」——站点自己的检索被 Cloudflare 挡着用不了，' +
          '而搜索引擎的召回不稳定、也基本只认完整片名。换成完整片名再搜一次通常就能命中，' +
          '例如用「女足替补的滚烫夏天」，而不是「女足替补」。'
      return
    }
    // 只有一条候选说明没什么可选，直接识别出来给用户看
    if (candidates.length === 1) await pickTitle(candidates[0])
  } finally {
    titleSearching.value = false
  }
}

async function pickTitle(candidate: TitleCandidate): Promise<void> {
  const api = resolveApi(props)
  if (!api || !candidate.media_id) return
  titleLoadingId.value = candidate.media_id
  titleMessage.value = ''
  titleRawOpen.value = false
  try {
    const report = await recognizeTitle(api, { media_id: candidate.media_id })
    if (report?.success && report.record) {
      titleRecord.value = report.record
    } else {
      titleMessage.value = report?.message || '取详情失败（多半是站点风控，稍后再试）'
    }
  } finally {
    titleLoadingId.value = ''
  }
}

function clearTitle(): void {
  titleKeyword.value = ''
  titleCandidates.value = []
  titleRecord.value = null
  titleMessage.value = ''
  titleRawOpen.value = false
}

async function doSearchActor(): Promise<void> {
  const api = resolveApi(props)
  const keyword = actorKeyword.value.trim()
  if (!api || !keyword) return
  actorSearching.value = true
  actorMessage.value = ''
  actorProfile.value = null
  actorCandidates.value = []
  actorRawOpen.value = false
  openWorks.value = new Set<number>()
  try {
    const report = await searchActors(api, keyword)
    const candidates = report?.candidates || []
    actorCandidates.value = candidates
    if (!candidates.length) {
      actorMessage.value =
        report?.message || `没找到演员「${keyword}」：站外索引未收录，或姓名对不上。`
      return
    }
    if (candidates.length === 1) await pickActor(candidates[0])
  } finally {
    actorSearching.value = false
  }
}

async function pickActor(candidate: ActorCandidate): Promise<void> {
  const api = resolveApi(props)
  if (!api || !candidate.actor_id) return
  actorLoadingId.value = candidate.actor_id
  actorMessage.value = ''
  actorRawOpen.value = false
  openWorks.value = new Set<number>()
  try {
    const report = await fetchActor(api, { actor_id: candidate.actor_id })
    if (report?.success && report.actor) {
      actorProfile.value = report.actor
    } else {
      actorMessage.value = report?.message || '拉演员页失败（多半是站点风控，稍后再试）'
    }
  } finally {
    actorLoadingId.value = ''
  }
}

function clearActor(): void {
  actorKeyword.value = ''
  actorCandidates.value = []
  actorProfile.value = null
  actorMessage.value = ''
  actorRawOpen.value = false
  openWorks.value = new Set<number>()
}

function toggleWorkRaw(index: number): void {
  const next = new Set(openWorks.value)
  if (next.has(index)) next.delete(index)
  else next.add(index)
  openWorks.value = next
}

/** 先取配置再挂载弹窗：Config 只在 onMounted 读一次 initialConfig，先挂载会拿到空快照 */
async function openSettings(): Promise<void> {
  const api = resolveApi(props)
  configLoading.value = true
  try {
    if (api) {
      const report = await fetchConfig(api)
      if (report?.config) remoteConfig.value = report.config
    }
  } finally {
    configLoading.value = false
  }
  settingsOpen.value = true
}

async function onConfigSaved(config?: Partial<PluginConfig>): Promise<void> {
  if (config) remoteConfig.value = config
  settingsOpen.value = false
  await load()
}

load()
</script>

<style scoped>
.sdbs-root {
  min-width: 0;
}
/* 详情弹窗里的 switch 会带默认的外边距，压紧一点 */
.sdbs-switch {
  margin: 0;
  flex: 0 0 auto;
}
.sdbs-dim {
  opacity: 0.7;
}
.sdbs-panel {
  height: 100%;
}
.sdbs-poster {
  background-color: rgba(128, 128, 128, 0.12);
}
/* 简介最多三行，避免一条简介把整列撑开 */
.sdbs-clamp {
  display: -webkit-box;
  -webkit-line-clamp: 3;
  line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.sdbs-work-title {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
/* 原始数据块：等宽、可横向滚动、限高避免长 JSON 顶掉整页 */
.sdbs-pre {
  margin: 0;
  padding: 8px;
  max-height: 260px;
  overflow: auto;
  font-size: 12px;
  line-height: 1.5;
  white-space: pre;
  border-radius: 6px;
  background-color: rgba(128, 128, 128, 0.12);
}
</style>
