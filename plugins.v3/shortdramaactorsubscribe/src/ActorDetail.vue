<template>
  <!--
    演员作品页（**自绘**）—— 版式照宿主「探索」页点演员进的那一页（`PersonDetailView.vue`）。

    宿主那一页的结构（逐条对过它的模板与 scoped 样式）：
      `max-w-8xl mx-auto px-4` 里
        → 头部一行：`VAvatar size=200`（图片加载完加 `ring-1 ring-gray-700`）+ 右侧
          `h1`（text-3xl → lg:text-4xl）+ 一行副信息（宿主是「生日 | 出生地」+ 别名）
        → 简介 `<p class="pt-2 text-sm lg:text-base">`（overflow-wrap: break-word）
        → `person-credits-section`（margin-block-start: 2rem）：`slider-header` 里一个
          `slider-title`（「参演作品」+ `mdi-arrow-right-circle-outline`）→ 作品卡网格。

    ⚠️ 数据面差异（宿主模型 vs 短剧百科，**字段对不上是正常的**）：宿主副信息行放的
    「生日 | 出生地 / 别名」是它那几个源（TMDB / 豆瓣 / Bangumi / AniList）才有的，
    短剧百科没有；百科有而宿主模型没有的是「职业 / 国籍 / 作品数」⇒ 副信息行用
    「职业 | 国籍」，第二行放作品数与在库数。位置与字号完全照宿主那一行搬。

    ⚠️ `slider-header` / `slider-title` 是宿主 `src/styles/common.scss` 里的**全局**类
    （不是 scoped），联邦元素直接能用 ⇒ 标题那一行照抄类名，不用复刻数值。
    宿主 scoped 的 `.person-*` 匹配不上，那些数值（头像 / 标题 / 副信息 / 段距）在下面
    样式里按原值复刻。
  -->
  <div ref="pageRoot" class="sdas-actor">
    <!-- 返回条：与作品详情页同一款（那一页由宿主路由返回，这里用同尺寸的图标钮） -->
    <div class="sdas-actor-bar">
      <span class="text-body-2 text-medium-emphasis">演员作品</span>
      <span v-if="!loaded" class="text-body-2 text-medium-emphasis ml-3">
        正在从短剧百科取档案与作品…
      </span>
      <span v-else-if="missing" class="text-body-2 text-medium-emphasis ml-3">
        百科里没有这位演员的档案
      </span>
      <v-spacer />
      <span v-if="hint" class="text-body-2 text-medium-emphasis">{{ hint }}</span>
    </div>

    <!--
      加载态 —— 对齐宿主 `PersonDetailView` 的 `v-if="!isRefreshed"`：没回来之前整页
      只有跳动圆点，不摆内容（宿主那一份也不带文字，所以这里不传 `text`）。
    -->
    <LoadingBanner v-if="!loaded" />

    <!--
      取数失败 —— 宿主演员页对应的是 `NoDataFound`（500 + `error.title` / `error.networkError`），
      且**没有**重试按钮（它靠浏览器 / 顶栏返回）；插件面板里没有那条退路 ⇒ 与作品详情
      页一样保留一个「重试」，否则失败后只能退出重进。
    -->
    <NoDataFound
      v-else-if="failed"
      error-code="500"
      error-title="出错啦！"
      error-description="无法获取到媒体信息，请检查网络连接。"
    >
      <template #button>
        <v-btn prepend-icon="mdi-refresh" variant="tonal" @click="load()">重试</v-btn>
      </template>
    </NoDataFound>

    <!-- 空态：百科里没这位演员，也没有作品可铺（探索页同款 404 + 胶卷盘） -->
    <NoDataFound
      v-else-if="!view"
      error-code="404"
      :error-title="`百科里没有「${actor.name}」的档案`"
      error-description="短剧百科只收录站上有的演员和作品"
    />

    <template v-else>
      <!-- 头部：圆形大头像 + 姓名 + 副信息（宿主那一行的排布照搬） -->
      <div class="sdas-actor-head">
        <v-avatar
          class="sdas-actor-avatar"
          size="200"
          :class="{ 'ring-1 ring-gray-700': avatarLoaded }"
        >
          <v-img
            v-if="view.profile"
            :src="proxyImage(view.profile)"
            cover
            @load="avatarLoaded = true"
          />
          <v-icon v-else size="72" color="medium-emphasis">mdi-account-outline</v-icon>
        </v-avatar>
        <div class="sdas-actor-meta">
          <h1 class="sdas-actor-name">{{ view.name }}</h1>
          <div class="sdas-actor-sub">
            <div v-if="subLine">{{ subLine }}</div>
            <div v-if="creditLine">{{ creditLine }}</div>
          </div>
        </div>
      </div>

      <!-- 简介（宿主是 pt-2 text-sm lg:text-base + overflow-wrap: break-word） -->
      <p v-if="view.bio" class="sdas-actor-bio">{{ view.bio }}</p>

      <!--
        档案要点（2026-10-18 补全「数据显示不全」）：数据源 actor_profile 的契约里
        一直有生日 / 籍贯 / 身高体重 / 星座 / 院校 / 粉丝 / 获赞，之前白名单没投影，
        页面上只剩「职业｜国籍 + 简介」。有哪项摆哪项，空的整格不出。
      -->
      <div v-if="facts.length" class="sdas-actor-facts">
        <div v-for="fact in facts" :key="fact.label" class="sdas-actor-fact">
          <span class="sdas-actor-fact-label">{{ fact.label }}</span>
          <span class="sdas-actor-fact-value">{{ fact.value }}</span>
        </div>
      </div>
      <p v-if="hobbiesLine" class="sdas-actor-line">
        <span class="sdas-actor-line-label">爱好</span>{{ hobbiesLine }}
      </p>
      <!--
        代表作：站点给的是一整串**没有分隔符**的剧名（语文上无法切），后端已按
        「最长标题匹配」把它对回作品行 ⇒ 这里一部一个可点条目，点开就是那部剧的详情。
        对不上的部分（多为本站没收录的长剧）不丢掉：整串做成一个**搜索入口**，
        点了带关键词去宿主资源搜索页 —— 站点没页面可开，至少能搜资源。
      -->
      <div v-if="repWorks.length || repLeftover" class="sdas-actor-line sdas-actor-rep">
        <span class="sdas-actor-line-label">代表作</span>
        <span class="sdas-rep-list">
          <button
            v-for="work in repWorks"
            :key="`rep:${work.key}`"
            type="button"
            class="sdas-rep-item"
            :title="`打开《${work.title}》的详情`"
            @click="emit('open-work', work)"
          >
            {{ work.title }}
          </button>
          <button
            v-if="repLeftover"
            type="button"
            class="sdas-rep-item sdas-rep-search"
            :title="`《${repLeftover}》在短剧百科里没有条目（百科把几部剧名连写在一起），点击去资源搜索`"
            @click="emit('search-rep', repLeftover)"
          >
            <v-icon class="sdas-rep-search-icon" size="13">mdi-magnify</v-icon>
            {{ repLeftover }}
          </button>
        </span>
      </div>
      <p v-else-if="view.rep_text" class="sdas-actor-line">
        <span class="sdas-actor-line-label">代表作</span>{{ view.rep_text }}
      </p>

      <!--
        本插件自己的动作（宿主演员页没有这一块）：关注 / 取消关注 + 订阅全部作品
        （百科演员页入口已按用户要求去掉）。「订阅全部」走插件后端批量接口 ——
        作品列表由后端现取，不受本页滚动加载的分页影响。
      -->
      <div class="sdas-actor-actions">
        <v-btn
          class="sdas-actor-action-btn"
          variant="tonal"
          :color="subscribed ? 'error' : 'primary'"
          :prepend-icon="subscribed ? 'mdi-account-remove' : 'mdi-account-plus'"
          :loading="busyFollow"
          @click="emit('toggle-actor')"
        >
          {{ subscribed ? '取消关注' : '关注该演员' }}
        </v-btn>
        <v-btn
          class="sdas-actor-action-btn"
          variant="tonal"
          color="primary"
          prepend-icon="mdi-playlist-plus"
          :loading="busySubscribeAll"
          :disabled="busySubscribeAll || !worksTotal"
          title="把这名演员的全部作品提交给订阅系统（跳过已订阅与已在库）"
          @click="emit('subscribe-all')"
        >
          订阅全部作品
        </v-btn>
      </div>

      <!-- 参演作品：标题行照抄宿主全局类 slider-header / slider-title -->
      <div class="sdas-actor-credits">
        <div class="slider-header sdas-credits-head">
          <span class="slider-title">
            <span>参演作品</span>
            <v-icon icon="mdi-arrow-right-circle-outline" size="18" class="ms-1" />
          </span>
          <v-spacer />
          <span class="text-body-2 text-medium-emphasis">{{ creditSummary }}</span>
        </div>

        <!--
          作品卡网格：与作品墙同一张卡（WorkCard），列宽下限 / 间距与探索页一致。
          外面包一层 GlassMediaBackdrop —— 宿主这一页的作品区用的就是
          `MediaCardListView`（带毛玻璃采样层），所以这边也跟上。
        -->
        <GlassMediaBackdrop v-if="works.length">
          <div class="sdas-credits-grid">
            <WorkCard
              v-for="work in works"
              :key="work.key"
              :work="work"
              :loaded="loadedKeys.has(work.key)"
              :subscribed="subscribedIds.has(work.media_id)"
              @poster="markPoster(work.key)"
              @open="emit('open-work', work)"
              @search="emit('search', work)"
              @subscribe="emit('subscribe', work)"
            />
          </div>
        </GlassMediaBackdrop>
        <!-- 有档案但一部作品都没有（加载中不会走到这里：那时整页是圆点） -->
        <NoDataFound v-else error-code="404" :error-title="`百科里没有「${view.name}」的作品记录`" />

        <!--
          滚动加载哨兵（2026-10-18 用户口径：作品改成滚动加载）。
          列表只铺第一页，滚到底再拉下一页 —— 首屏不必等几十部作品的投影与在库判定。
        -->
        <div ref="worksSentinel" class="sdas-credits-sentinel">
          <v-progress-circular v-if="worksLoading" indeterminate size="20" width="2" />
          <span v-else-if="works.length && !worksHasMore">
            已到末尾 · 共 {{ worksTotal }} 部
          </span>
        </div>
      </div>
    </template>
    <!-- 返回键：钉在视口（面板内 sticky / fixed 都会被宿主的 transform + overflow 吃掉） -->
    <StickyBack :anchor="pageRoot" title="返回" @back="emit('back')" />
  </div>
</template>

<script setup lang="ts">
import StickyBack from './StickyBack.vue'

/** 页面根节点：返回键（`StickyBack`）按它的左上角定位到视口 */
const pageRoot = ref<HTMLElement | null>(null)

import { computed, nextTick, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { fetchActorDetail, proxyImage } from './api'
import WorkCard from './WorkCard.vue'
import GlassMediaBackdrop from './GlassMediaBackdrop.vue'
import LoadingBanner from './LoadingBanner.vue'
import NoDataFound from './NoDataFound.vue'
import type { ActorCandidate, ActorDetailPayload, PluginApi, WorkItem } from './types'

/**
 * 演员作品页：点演员卡进来（**整页**，不是卡片区里的一块）。
 *
 * 数据全部由后端 ``GET /actors/detail`` 一次给全（档案 + 全部作品），所以本组件只管
 * 取数与呈现。加载 / 失败 / 空态**与宿主演员详情页同一套**：加载中整页只有跳动圆点
 * （`!loaded` ≡ 宿主的 `!isRefreshed`），失败整块换 NoDataFound（500 + 宿主那两句固定
 * 文案 + 重试），百科没有这位演员时改用**卡片上的字段**垫底（见 `fallback`）。
 */
const props = defineProps<{
  /** 宿主注入的 axios 实例 */
  api?: PluginApi
  /** 进来时点的那位演员（卡片数据，作为取数期间的兜底视图 + 取数用的 actor_id） */
  actor: ActorCandidate
  /** 是否已在本插件关注列表里 */
  subscribed: boolean
  /** 关注 / 取消关注请求进行中 */
  busyFollow?: boolean
  /** 已订阅（系统订阅）的作品 ID 集合，决定作品卡上的爱心状态 */
  subscribedIds?: Set<string>
  /** 「订阅全部作品」请求进行中（按钮转圈并禁用） */
  busySubscribeAll?: boolean
}>()

const emit = defineEmits<{
  (e: 'back'): void
  (e: 'search', work: WorkItem): void
  (e: 'subscribe', work: WorkItem): void
  (e: 'open-work', work: WorkItem): void
  /** 代表作里对不上作品的那一串，交给父组件带去资源搜索 */
  (e: 'search-rep', text: string): void
  (e: 'toggle-actor'): void
  /** 订阅全部作品（父组件负责调后端批量接口与提示） */
  (e: 'subscribe-all'): void
}>()

/** 详情载荷（后端一次给全）；null = 还没回来 */
const detail = ref<ActorDetailPayload | null>(null)
/**
 * 详情是否已请求完毕 / 是否失败 —— **对齐宿主演员详情页的 `isRefreshed`**。
 *
 * 宿主 `PersonDetailView` 是 `onBeforeMount` 里取数、`LoadingBanner v-if="!isRefreshed"`：
 * 没回来之前整页只有圆点，不摆任何内容。本页同样：加载中只出圆点，不再用卡片兜底顶着。
 */
const loaded = ref(false)
const failed = ref(false)
/** 行内提示（取数期间的口径说明之类），4 秒自动清 */
const hint = ref('')
let hintTimer: ReturnType<typeof setTimeout> | null = null

/** 头像是否加载完（加载完才画 ring，与宿主那一页一致） */
const avatarLoaded = ref(false)
/** 海报已加载完的作品键（WorkCard 据此亮环形描边与角标） */
const loadedKeys = reactive(new Set<string>())

/**
 * 兜底视图：用卡片上已有的字段（头像 / 姓名 / 作品数 / 职业）。
 *
 * ⚠️ 它不是「加载中的占位」—— 加载中整页只有圆点（见模板 `v-if="!loaded"`）。
 * 它只在**百科没有这位演员**（`found=false` 的空壳）时起作用：把卡片上现成的头像 /
 * 姓名 / 作品数 / 职业垫进去，页面不至于空掉。
 */
const fallback = computed<ActorDetailPayload>(() => ({
  found: true,
  actor_id: String(props.actor?.actor_id || ''),
  media_id: String(props.actor?.media_id || ''),
  name: String(props.actor?.name || ''),
  profile: String(props.actor?.profile || ''),
  bio: String(props.actor?.bio || ''),
  job_title: String(props.actor?.job_title || ''),
  gender: String(props.actor?.gender || ''),
  nationality: String(props.actor?.nationality || ''),
  url: String(props.actor?.url || ''),
  works_count: Number(props.actor?.works_count || 0),
  total: 0,
  in_library_count: 0,
  library_known: 0,
  subscribed: Boolean(props.subscribed),
  works: [],
}))

/** 页面呈现的数据：命中就用详情，没命中（百科没有这位演员）用卡片兜底 */
const view = computed<ActorDetailPayload | null>(() =>
  detail.value?.found ? detail.value : props.actor ? fallback.value : null,
)
const missing = computed(() => Boolean(detail.value) && !detail.value?.found)

/** 每页作品数（与作品墙 / 发现演员同量级：一屏多一点，滚到底正好续拉） */
const WORKS_PAGE_SIZE = 24

/**
 * 作品**按页累加**（2026-10-18 用户口径：详情页作品改滚动加载）。
 *
 * 以前是一次把几十部全取回来铺出去；现在只取第一页，滚到底由哨兵续拉 ——
 * 首屏不用等整份投影 + 在库判定，滚动体验与作品墙 / 发现演员一致。
 */
const works = ref<WorkItem[]>([])
/** 作品总数（分页前；后端 ``works_total``，老后端退回 ``total``） */
const worksTotal = ref(0)
/** 还有下一页 */
const worksHasMore = ref(false)
/** 正在取下一页（哨兵里转圈） */
const worksLoading = ref(false)
/** 已取到第几页 */
let worksPage = 0
/** 连续失败次数：同一页失败三次就停，别让哨兵无限重试 */
let worksFailures = 0

/** 滚动加载哨兵（作品网格之后） */
const worksSentinel = ref<HTMLElement | null>(null)
let worksObserver: IntersectionObserver | null = null

/**
 * 重挂哨兵。分支切换（加载中 / 空态 / 首屏刚铺完）会重建这个节点，
 * 观察器不会自己跟过去 —— 不重挂就是「滑到底也不再加载」。
 */
function observeWorksSentinel(): void {
  if (!worksObserver) return
  worksObserver.disconnect()
  if (worksSentinel.value) worksObserver.observe(worksSentinel.value)
}

/** 副信息行：宿主放「生日 | 出生地」，我们放「职业 | 国籍」（数据源有什么放什么） */
const subLine = computed(() => {
  const parts: string[] = []
  const job = String(view.value?.job_title || '').trim()
  const nationality = String(view.value?.nationality || '').trim()
  if (job) parts.push(job)
  if (nationality) parts.push(nationality)
  return parts.join(' | ')
})

/**
 * 档案要点（标签 + 值）：数据源给了哪项就摆哪项。
 *
 * 生日优先精确日期，只有年份时退回 ``birth_year``；身高 / 体重拼单位；
 * 粉丝 / 获赞按「万 / 亿」缩写。空的一律不进数组 —— 前端不会出现「身高 —」这种格子。
 */
const facts = computed<{ label: string; value: string }[]>(() => {
  const data = view.value
  if (!data) return []
  const rows: { label: string; value: string }[] = []
  const birth = String(data.birth_date || '').trim() || String(data.birth_year || '').trim()
  if (birth) rows.push({ label: '生日', value: birth })
  if (data.birth_place) rows.push({ label: '出生地', value: data.birth_place })
  if (data.height_cm) rows.push({ label: '身高', value: `${data.height_cm} cm` })
  if (data.weight_kg) rows.push({ label: '体重', value: `${data.weight_kg} kg` })
  if (data.constellation) rows.push({ label: '星座', value: data.constellation })
  if (data.education) rows.push({ label: '院校', value: data.education })
  const followers = formatCount(data.followers)
  if (followers) rows.push({ label: '粉丝', value: followers })
  const likes = formatCount(data.likes)
  if (likes) rows.push({ label: '获赞', value: likes })
  return rows
})

/** 代表作（已对回作品行，可点） */
const repWorks = computed<WorkItem[]>(() => view.value?.rep_works || [])

/**
 * 代表作里**没能对回作品行**的剩余文字（例：刘艺乔的「无忧渡薄冰田耕纪锦医风华」）。
 *
 * 站点把几部剧名连写、既无分隔也不给链接 ⇒ 没法逐部拆开（随便切一刀就是假链接，
 * 比不能点更糟）。这里把已经匹配上的标题从原文剔掉，剩下的整串做成**资源搜索入口**：
 * 点了带着关键词去宿主搜索页，用户改一下关键词就能搜 —— 比一行死文字有用。
 */
const repLeftover = computed(() => {
  const raw = String(view.value?.rep_text || '').trim()
  if (!raw) return ''
  let rest = raw
  for (const work of repWorks.value) {
    const title = String(work.title || '').trim()
    if (title) rest = rest.replace(title, '')
  }
  return rest.replace(/[\s、,，;；/|]+/g, ' ').trim()
})

/** 爱好：一行顿号分隔（列表长度不定，不做成格子） */
const hobbiesLine = computed(() => (view.value?.hobbies || []).join('、'))

/** 数字缩写（站点给的是纯数字，详情页也不摆一长串） */
function formatCount(value?: number): string {
  const num = Number(value || 0)
  if (!num) return ''
  if (num >= 100000000) return `${(num / 100000000).toFixed(1)} 亿`
  if (num >= 10000) return `${(num / 10000).toFixed(1)} 万`
  return String(num)
}

/** 第二行：作品数与在库数（宿主放的是别名，我们放这一页真正有信息量的两个数字） */
const creditLine = computed(() => {
  const data = view.value
  if (!data) return ''
  const total = Number(data.works_count || 0) || worksTotal.value
  if (!total) return ''
  const parts = [`参演 ${total} 部短剧`]
  if (data.library_known > 0) parts.push(`已入库 ${data.in_library_count} 部`)
  return parts.join(' · ')
})

/** 标题行右侧的统计（作品数 / 在库数，判定不可用时只说总数） */
const creditSummary = computed(() => {
  const data = view.value
  const total = worksTotal.value || Number(data?.works_count || 0)
  if (!loaded.value && !total) return '正在取作品…'
  const parts = [`共 ${total} 部`]
  if (data && data.library_known > 0) {
    parts.push(`入库 ${data.in_library_count} 部`)
    if (data.library_known < total) parts.push(`判定 ${data.library_known} 部`)
  }
  return parts.join(' · ')
})

function markPoster(key: string): void {
  loadedKeys.add(key)
}

function toast(text: string): void {
  hint.value = text
  if (hintTimer) clearTimeout(hintTimer)
  hintTimer = setTimeout(() => {
    hint.value = ''
  }, 4000)
}

/**
 * 拉这位演员的详情（档案 + 全部作品）。
 *
 * 与宿主 `PersonDetailView` 同一套时序：`loaded` ≡ `isRefreshed`，加载中整页只有圆点；
 * 失败时 `failed` ⇒ 整块换 NoDataFound（异常只进控制台，界面用那两句固定文案）。
 */
function actorIdOf(): string {
  return String(props.actor?.actor_id || '')
}

function actorNameOf(): string {
  return String(props.actor?.name || '')
}

/**
 * 把一页结果并进页面状态。
 *
 * ``append=false``（第一页）= 整份替换；``append=true``（续拉）= 追加去重 ——
 * 后端翻页期间缓存可能刚过期重取一遍，理论上同一部剧会重复出现，这里按
 * ``work.key`` 兜一层。
 */
function applyWorksPage(data: ActorDetailPayload, append: boolean): void {
  const pageWorks = data.works || []
  if (append) {
    const seen = new Set(works.value.map((item) => item.key))
    works.value = [...works.value, ...pageWorks.filter((item) => !seen.has(item.key))]
  } else {
    works.value = pageWorks
  }
  worksTotal.value = Number(data.works_total ?? data.total ?? works.value.length) || 0
  // 后端给了 has_more 就信它；老后端没有这个字段时退回「已加载 < 总数」
  worksHasMore.value =
    typeof data.has_more === 'boolean'
      ? data.has_more
      : works.value.length < worksTotal.value
  worksPage = Number(data.works_page || (append ? worksPage : 1)) || 1
}

/** 续拉下一页作品（滚动到底由哨兵触发） */
async function loadMoreWorks(): Promise<void> {
  if (worksLoading.value || !worksHasMore.value) return
  const actorId = actorIdOf()
  const name = actorNameOf()
  if (!actorId && !name) return
  worksLoading.value = true
  try {
    const data = await fetchActorDetail(props, actorId, name, worksPage + 1, WORKS_PAGE_SIZE)
    applyWorksPage(data, true)
    worksFailures = 0
  } catch (err) {
    // 续拉失败不整页报错（已经铺出来的作品不能丢），失败三次就停，改为显示末尾
    worksFailures += 1
    console.error('[ShortDramaActorSubscribe] 续拉作品失败', err)
    if (worksFailures >= 3) worksHasMore.value = false
  } finally {
    worksLoading.value = false
    // 哨兵随列表重排：重挂一次，若还在视口内会立刻续拉下一页
    await nextTick()
    observeWorksSentinel()
  }
}

/**
 * 拉这位演员的详情（档案 + 第一页作品）。
 *
 * 与宿主 `PersonDetailView` 同一套时序：`loaded` ≡ `isRefreshed`，加载中整页只有圆点；
 * 失败时 `failed` ⇒ 整块换 NoDataFound（异常只进控制台，界面用那两句固定文案）。
 */
async function load(): Promise<void> {
  const actorId = actorIdOf()
  const name = actorNameOf()
  loaded.value = false
  failed.value = false
  worksLoading.value = false
  worksFailures = 0
  worksPage = 0
  works.value = []
  worksTotal.value = 0
  worksHasMore.value = false
  if (!actorId && !name) {
    failed.value = true
    loaded.value = true
    return
  }
  try {
    const data = await fetchActorDetail(props, actorId, name, 1, WORKS_PAGE_SIZE)
    detail.value = data
    if (data.found) applyWorksPage(data, false)
  } catch (err) {
    // 与宿主一致：异常只进控制台，界面统一用 NoDataFound 那两句固定文案
    console.error('[ShortDramaActorSubscribe] 演员详情加载失败', err)
    detail.value = null
    failed.value = true
  } finally {
    loaded.value = true
    await nextTick()
    observeWorksSentinel()
  }
}

// 换一位演员就重拉（同一组件实例被复用时，不能留上一位的数据）
watch(
  () => String(props.actor?.actor_id || props.actor?.name || ''),
  () => {
    detail.value = null
    // 与宿主一致：换一位演员 = 全新一页（宿主是路由跳转 ⇒ 新实例 ⇒ 状态从零开始）
    loaded.value = false
    failed.value = false
    avatarLoaded.value = false
    loadedKeys.clear()
    works.value = []
    worksTotal.value = 0
    worksHasMore.value = false
    worksPage = 0
    load()
  },
  { immediate: true },
)

/**
 * 滚动哨兵：滚到网格底部（前后 800px）就续拉下一页。
 *
 * 不指定 `root` —— 交集由浏览器按**所有裁剪祖先**计算，所以面板把内容钉在
 * 自己的滚动容器里也照样准，不必去猜「到底谁在滚」。
 */
onMounted(() => {
  if (typeof IntersectionObserver === 'undefined') return
  worksObserver = new IntersectionObserver(
    (entries) => {
      if (!entries.some((entry) => entry.isIntersecting)) return
      void loadMoreWorks()
    },
    { rootMargin: '800px 0px' },
  )
  observeWorksSentinel()
})

onUnmounted(() => {
  worksObserver?.disconnect()
  worksObserver = null
  if (hintTimer) clearTimeout(hintTimer)
})

defineExpose({ toast })
</script>

<style scoped>
/*
  ⚠️ 联邦 CSS 门禁会把任何含 `.v-` 的选择器整条丢掉 ⇒ 样式一律自有 `sdas-*` 类名。
  宿主全局类（slider-header / slider-title / ring-1 / ring-gray-700 / text-body-2 /
  text-medium-emphasis / ms-1 / ml-1 / ml-3）只用 class 属性引用，不在这里定义。
*/
.sdas-actor {
  display: flex;
  flex-direction: column;
  padding: 0 0 24px;
  color: rgb(var(--v-theme-on-surface));
}

/* 返回条：压在页面顶部（作品详情页同一款） */
/*
 * 返回条：**吸顶**（sticky）。
 *
 * 插件面板没有宿主顶栏 / 浏览器返回，返回键是唯一的退路，不能随内容滚走。
 * 之前作品详情页把它做成左上角绝对定位的浮层（不占排版），滑两屏就够不着了；
 * 改成 sticky 后它占一行、滚到哪都停在顶部。背景给实色，否则下方内容会从它背后透出来。
 */
.sdas-actor-bar {
  display: flex;
  align-items: center;
  min-height: 32px;
  padding-inline: 12px;
  margin-bottom: 4px;
}

/* 头部：窄屏竖排居中，≥768px 横排（宿主 flex-md-row 同款断点） */
.sdas-actor-head {
  position: relative;
  z-index: 10;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.75rem;
  padding-inline: 16px;
  margin: 0.75rem 0 1.5rem;
}

@media (width >= 768px) {
  .sdas-actor-head {
    flex-direction: row;
    align-items: flex-start;
    gap: 1rem;
  }
}

.sdas-actor-avatar {
  flex: 0 0 auto;
  background: rgba(var(--v-theme-on-surface), 0.08);
}

.sdas-actor-meta {
  min-inline-size: 0;
}

/* h1：宿主 text-3xl → lg:text-4xl（1.875rem/2.25rem → 2.25rem/2.5rem），
   窄屏居中、≥768px 靠左（宿主 text-center text-lg-left） */
.sdas-actor-name {
  margin: 0;
  font-size: 1.875rem;
  font-weight: 400;
  line-height: 2.25rem;
  text-align: center;
}

@media (width >= 768px) {
  .sdas-actor-name {
    font-size: 2.25rem;
    line-height: 2.5rem;
    text-align: left;
  }
}

/* 副信息：宿主 mt-1 mb-2 space-y-1 text-xs sm:text-sm lg:text-base */
.sdas-actor-sub {
  margin: 0.25rem 0 0.5rem;
  font-size: 0.75rem;
  line-height: 1.25rem;
  text-align: center;
}

.sdas-actor-sub > div + div {
  margin-top: 0.25rem;
}

@media (width >= 640px) {
  .sdas-actor-sub {
    font-size: 0.875rem;
  }
}

@media (width >= 1024px) {
  .sdas-actor-sub {
    font-size: 1rem;
  }
}

@media (width >= 768px) {
  .sdas-actor-sub {
    text-align: left;
  }
}

/* 简介：宿主 pt-2 text-sm lg:text-base + overflow-wrap: break-word */
.sdas-actor-bio {
  padding: 16px 16px 0;
  margin: 0;
  font-size: 0.875rem;
  line-height: 1.5rem;
  overflow-wrap: break-word;
}

@media (width >= 1024px) {
  .sdas-actor-bio {
    font-size: 1rem;
  }
}

/*
 * 档案要点（生日 / 出生地 / 身高 / 体重 / 星座 / 院校 / 粉丝 / 获赞）
 * 自适应网格：宽屏一排放三四个，窄屏自动降成一列；值可能很长（院校）所以允许换行。
 */
.sdas-actor-facts {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  gap: 6px 18px;
  padding: 12px 16px 0;
  margin-top: 10px;
}

.sdas-actor-fact {
  display: flex;
  align-items: baseline;
  gap: 8px;
  min-inline-size: 0;
}

.sdas-actor-fact-label {
  flex: 0 0 auto;
  font-size: 0.75rem;
  line-height: 1.25rem;
  color: rgba(var(--v-theme-on-surface), 0.6);
}

.sdas-actor-fact-value {
  min-inline-size: 0;
  font-size: 0.875rem;
  line-height: 1.25rem;
  overflow-wrap: anywhere;
}

/* 爱好 / 代表作：整行文字（长度不定，不做成格子） */
.sdas-actor-line {
  display: flex;
  gap: 8px;
  padding: 6px 16px 0;
  margin: 0;
  font-size: 0.875rem;
  line-height: 1.5rem;
  overflow-wrap: anywhere;
}

.sdas-actor-line-label {
  flex: 0 0 auto;
  font-size: 0.75rem;
  line-height: 1.5rem;
  color: rgba(var(--v-theme-on-surface), 0.6);
}

/* 代表作：可点条目一行排开（像链接，不是按钮块） */
.sdas-actor-rep {
  align-items: baseline;
}

.sdas-rep-list {
  display: flex;
  flex-wrap: wrap;
  gap: 2px 12px;
  min-inline-size: 0;
}

/*
 * 代表作条目：**不用主色**（2026-10-18 用户口径）—— 与正文同色，
 * 靠悬停下划线 + 手型光标表达「可点」，不在一行文字里跳出一片蓝。
 */
.sdas-rep-item {
  padding: 0;
  border: 0;
  background: none;
  color: inherit;
  font: inherit;
  font-size: 0.875rem;
  line-height: 1.5rem;
  cursor: pointer;
  text-align: start;
}

.sdas-rep-item:hover {
  text-decoration: underline;
}

.sdas-rep-item:focus-visible {
  outline: 2px solid rgb(var(--v-theme-primary));
  outline-offset: 2px;
  border-radius: 3px;
}

/*
 * 「未收录」那一串：不是作品链接，而是一个搜索入口。
 * 用虚线底边 + 放大镜图标 + 略淡的字色，跟旁边实打实的作品条目区分开，
 * 免得用户以为点了会进详情。
 */
.sdas-rep-search {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  border-block-end: 1px dashed rgba(var(--v-theme-on-surface), 0.35);
  color: rgba(var(--v-theme-on-surface), 0.72);
}

.sdas-rep-search-icon {
  opacity: 0.7;
}

/* 作品滚动加载哨兵：与作品墙同款，居中的细转圈 / 末尾提示 */
.sdas-credits-sentinel {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  min-block-size: 44px;
  padding: 8px 0;
  font-size: 0.75rem;
  color: rgba(var(--v-theme-on-surface), 0.6);
}

/* 本插件自己的动作排（宿主演员页没有这一块）：与作品详情页的操作按钮同一款 tonal */
.sdas-actor-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  padding: 1rem 16px 0;
}

.sdas-actor-action-btn {
  flex: 0 0 auto;
}

/* 参演作品区：宿主 .person-credits-section 的 margin-block-start: 2rem */
.sdas-actor-credits {
  margin-block-start: 2rem;
  padding-inline: 16px;
}

/* 标题行：slider-header 是 display:flex（全局），这里只补两端对齐与下边距 */
.sdas-credits-head {
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.75rem;
}

/*
  作品卡网格：与作品墙同式（探索页 ProgressiveCardGrid 的 minItemWidth=144 /
  gap=16）。这里用 CSS `auto-fill` 直接算列数 —— 它用的就是 minmax 的下限
  `144px`，与 `floor((宽 + 16) / 160)` 的列数结果一致，省掉一次量宽。
*/
.sdas-credits-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(144px, 1fr));
  gap: 16px;
}

/* 空态（与面板其它处的空态同一款） */
/* 空态（探索页同款）见 NoDataFound.vue —— 旧的 sdas-actor-empty 三条样式已随替换删掉 */
</style>
