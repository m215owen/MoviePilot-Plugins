<template>
  <!--
    作品卡 —— **照宿主 `src/components/cards/MediaCard.vue` 复刻**。
    作品墙 / 搜索结果 / 演员作品页共用这一张。

    宿主那一张的结构（逐条对过模板与 scoped 样式）：
      `VHover` → `div.media-card-hover-area`（hover 的 props 绑在**静止的**外壳上，
      免得卡片上浮后底边反复触发 mouseleave）→ `VCard{ripple:false, app-hover-lift-card,
      outline-none ring-gray-500 media-card}`，悬停加 `app-hover-lift-card--hovering`
      （宿主全局类：上浮 0.25rem）+ `ring-1`；
        海报 `VImg{aspect-ratio: 2/3, cover}`，`#placeholder` 是 `VSkeletonLoader`；
        悬停浮层 `absolute bottom-0` 铺满，`linear-gradient(rgba(45,55,72,40%) → 90%)`，
        依次是年份 / 标题 / 简介 / 左「搜索」右「订阅」两个图标钮；
        左上类型角标（颜色按媒体类型），右上已入库勾**或**评分角标（互斥），右下来源图标。
      点卡片进详情；触摸端两段式（先展开浮层，再点进详情）。

    本插件的差异：
      - 角标文字是「短剧」（宿主印 type 的中文名），底色取宿主**电视剧**那一档
        （`bg-indigo-500 border-indigo-600`）—— 短剧在系统里就是电视剧类型；
      - 右下的来源图标短剧恒为短剧百科，用 MDI 图标代替 logo 外链；
      - 右上没有评分时退成**首播日期**（短剧百科给新剧打分的滞后，整屏空角标更难看）；
        新作品（`is_new`）时这一格**改印「NEW」**（无底、细体、宽字距的半透明白，见 `.sdas-new`），
        顶掉本该显示的日期，不再额外挂一枚 chip —— 用户口径：另加一枚太突兀；
        调过三版（红底白字 / 主色底红字 / 红字无底）都被判「太显眼」，最终定位为
        「日期那一格换了个词」：层级与日期同级或更低，只负责提示状态。
  -->
  <v-hover v-slot="{ isHovering, props: hoverProps }">
    <div ref="cardRef" v-bind="hoverProps" class="sdas-hover-area">
      <v-card
        :ripple="false"
        :data-glass-optical-mode="posterCovered ? 'excluded' : undefined"
        class="app-hover-lift-card outline-none ring-gray-500 media-card sdas-card"
        :class="{
          'app-hover-lift-card--hovering': activeState(isHovering),
          'ring-1': loaded && !imgFailed,
        }"
        @click.stop="handleClick(isHovering)"
      >
        <!-- 海报：恒 2:3；骨架用宿主同款 VSkeletonLoader；加载失败退回图标占位 -->
        <v-img
          v-if="work.poster && !imgFailed"
          :key="imgRequest.key"
          :src="displaySrc"
          :aspect-ratio="2 / 3"
          :eager="imgRequest.eager"
          :transition="imgRequest.transition"
          cover
          class="object-cover aspect-w-2 aspect-h-3"
          @load="handleImageLoad"
          @error="handleImageError"
        >
          <template #placeholder>
            <div class="sdas-poster-skeleton-wrap">
              <v-skeleton-loader class="sdas-poster-skeleton" />
            </div>
          </template>
        </v-img>
        <div v-else class="sdas-poster-empty d-flex align-center justify-center">
          <v-icon icon="mdi-television-classic" size="64" color="medium-emphasis" />
        </div>

        <!--
          品类角标（左上）：VChip 样式与宿主 MediaCard 同款。
          文字按**复合 ID 的分类前缀**判「短剧 / 漫剧」（站点 /manju/ 与 /huolong/ 是漫剧频道，
          /duanju/ 与 /hema/ 是短剧频道）；配色沿用宿主那两档 —— 短剧取电视剧的靛蓝、
          漫剧取宿主默认的紫，扫一眼就能分开。
        -->
        <v-chip
          v-show="loaded"
          variant="elevated"
          size="small"
          :class="kindChipClass"
          class="absolute left-2 top-2 bg-opacity-80 text-white font-bold"
        >
          {{ kindLabel }}
        </v-chip>

        <!-- 右上：已入库 = 绿色圆形勾（探索页 ExistIcon 同款，DOM 与显隐条件照抄：
             勾只在**未悬停**时显示，悬停浮层展开时换评分角标显示）；
             与评分角标互斥；「已入库」判定与宿主媒体详情页同源，未知（缺字段）时不显示 -->
        <div v-show="loaded" class="absolute top-0 right-0 p-2 d-flex align-center ga-1">
          <div
            v-if="work.in_library === true && !activeState(isHovering)"
            class="pointer-events-none z-40 flex items-center"
            title="这部作品已在 MoviePilot 媒体库中（与媒体详情页的判定一致）"
          >
            <div
              class="relative inline-flex whitespace-nowrap rounded-full border-gray-700 font-semibold leading-5 ring-gray-700"
            >
              <div class="rounded-full bg-opacity-80 w-5 border p-0 bg-green-500 border-green-400 ring-green-400 text-green-100">
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
                  <path
                    fill-rule="evenodd"
                    d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.857-9.809a.75.75 0 00-1.214-.882l-3.483 4.79-1.88-1.88a.75.75 0 10-1.06 1.061l2.5 2.5a.75.75 0 001.137-.089l4-5.5z"
                    clip-rule="evenodd"
                  />
                </svg>
              </div>
            </div>
          </div>
          <!--
            新作品：**替代日期占这一格**，但只做「日期那一格换了个词」——
            小字号、常规字重、宽字距、半透明白、无底无边，靠一层极轻投影立住。
            视觉重量压到与日期 chip 同级或更低：扫视时它是状态的注脚，不是告示牌。
          -->
          <span
            v-else-if="badgeIsNew"
            class="sdas-new"
            title="新作品（最近上映 / 首次发现）"
          >NEW</span>
          <v-chip
            v-else-if="badge"
            variant="elevated"
            size="small"
            class="bg-opacity-80 text-white font-bold border-purple-600 bg-purple-600"
            :title="badgeTitle"
          >
            {{ badge }}
          </v-chip>
        </div>

        <!-- 右下来源图标：探索页 MediaCard 同款（VAvatar + 来源 logo，悬停时隐藏）；
             短剧作品来源恒为 duanju（短剧百科），用 MDI 图标代替 logo 外链 -->
        <v-avatar
          v-if="!activeState(isHovering)"
          v-show="loaded && !imgFailed"
          size="24"
          variant="plain"
          density="compact"
          tile
          class="absolute bottom-1 right-1"
        >
          <v-icon size="20" color="white">mdi-book-open-page-variant-outline</v-icon>
        </v-avatar>

        <!-- 左下：自建订阅搜索状态（引擎 = self 时后端附带；悬停时隐藏给按钮让位）。
             说清这部会不会被自动下载 / 为什么没下：已提交下载（绿）/ 下载历史已有 /
             已在媒体库（青）/ 暂无资源（灰，冷却重试）/ 搜索失败（红，冷却重试）；
             说清这部会不会被自动下载 / 为什么没下。 -->
        <v-chip
          v-else-if="subChip && !activeState(isHovering)"
          variant="elevated"
          size="x-small"
          class="absolute bottom-1 left-1 bg-opacity-80 text-white"
          :class="subChip.cls"
          :title="work.sub_detail || subChip.label"
        >
          <v-icon size="12" class="mr-1">{{ subChip.icon }}</v-icon>
          {{ subChip.label }}
        </v-chip>

        <!-- 悬停浮层：年份 / 标题 / 简介 / 按钮排（与宿主 MediaCard 同构：左搜索右订阅） -->
        <div
          v-if="detailVisible(isHovering)"
          class="w-full h-full flex flex-col flex-wrap justify-end align-left text-white absolute bottom-0 cursor-pointer pa-2"
          :style="OVERLAY_STYLE"
        >
          <span class="font-semibold text-sm">{{ work.year || '—' }}</span>
          <h1 class="sdas-card-title font-bold mb-2 text-white line-clamp-2 overflow-hidden text-ellipsis">
            {{ work.title }}
          </h1>
          <p class="sdas-card-overview line-clamp-3 overflow-hidden text-ellipsis">
            {{ cardSummary(work) }}
          </p>
          <!-- 底部按钮排：左搜索 / 右订阅（探索页 MediaCard 同款 IconBtn）。
               联邦模块拿不到宿主的全局组件别名，用 v-btn 复刻同款 props -->
          <div class="flex align-center justify-between">
            <v-btn
              icon
              variant="text"
              size="small"
              title="搜索资源（电影 + 电视剧全分类）"
              @click.stop="emit('search', work)"
            >
              <v-icon size="24" color="white">mdi-magnify</v-icon>
            </v-btn>
            <v-spacer />
            <!--
              立即搜索（2026-10-24 用户口径）：动作与订阅设置里的「立即搜索一次」
              完全一样（后端 /subscribe/search_now，清冷却后立刻跑一轮后台搜索）；
              未订阅时父级会先订阅再搜。放在「搜索」与「订阅」两枚按钮之间。
            -->
            <v-btn
              icon
              variant="text"
              size="small"
              :loading="props.searching === work.media_id"
              :disabled="Boolean(props.searching)"
              title="立即搜索一次（与订阅设置里的「立即搜索」同一动作）"
              @click.stop="emit('search-now', work)"
            >
              <v-icon size="24" color="white">mdi-download-outline</v-icon>
            </v-btn>
            <v-spacer />
            <!--
              订阅爱心：请求在飞时转圈并禁用（此前点下去毫无动静，像没反应）。
              只有这一部在处理时才转 —— 父级传的是「正在处理的 media_id」，
              不是全局忙态，否则点一张会满墙爱心一起转。
            -->
            <v-btn
              icon
              variant="text"
              size="small"
              :loading="props.subscribing === work.media_id"
              :disabled="Boolean(props.subscribing)"
              :color="subscribed ? 'error' : 'white'"
              :title="subscribed ? '已订阅（点击取消）' : '加入订阅'"
              @click.stop="emit('subscribe', work)"
            >
              <v-icon v-if="props.subscribing !== work.media_id" size="24" :color="subscribed ? 'error' : 'white'">
                {{ subscribed ? 'mdi-heart' : 'mdi-heart-outline' }}
              </v-icon>
            </v-btn>
          </div>
        </div>
      </v-card>
    </div>
  </v-hover>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { proxyImage, retryProxyImage } from './api'
import { activeTouchCardId, nextCardId, revealedPosters } from './cardState'
import type { WorkItem } from './types'

/** 作品墙卡片（与宿主探索页 MediaCard 同款）：主墙 / 搜索结果 / 演员作品页共用 */
const props = defineProps<{
  work: WorkItem
  /** 海报是否已加载完（加载完才亮 ring 和角标，与探索页一致） */
  loaded: boolean
  /** 是否已在系统订阅里（订阅爱心状态） */
  subscribed: boolean
  /** 正在提交 / 取消订阅的那部剧 `media_id`（空串 = 空闲）；只有它那颗爱心转圈 */
  subscribing?: string
  /** 正在「立即搜索」的那部剧 `media_id`（空串 = 空闲）；只有它那颗按钮转圈 */
  searching?: string
  /**
   * 该订阅在宿主订阅页被暂停（只有「已订阅」页的行会传）：
   * 左下角显示灰色「已暂停」chip（自动搜索会跳过它），其余页面不传不显示。
   */
}>()

const emit = defineEmits<{
  (e: 'poster', key: string): void
  (e: 'open', work: WorkItem): void
  (e: 'search', work: WorkItem): void
  (e: 'subscribe', work: WorkItem): void
  (e: 'search-now', work: WorkItem): void
}>()

/** 悬停浮层背景（与探索页 MediaCard 逐字相同） */
const OVERLAY_STYLE = {
  background: 'linear-gradient(rgba(45, 55, 72, 40%) 0%, rgba(45, 55, 72, 90%) 100%)',
}

/** 本卡的触摸交互身份（模块内唯一） */
const cardId = nextCardId()

/** 粗指针设备：用点击展开浮层，避免 iOS 返回后沿用触摸态 */
const isTouchLikePointer = ref(
  typeof window !== 'undefined' && Boolean(window.matchMedia?.('(hover: none), (pointer: coarse)').matches),
)

/** 海报加载失败 → 退回图标占位（宿主 `imageLoadError` 同款语义） */
const imgFailed = ref(false)

/** 这张海报本次是否属于「重入」（见过就不再做淡入） */
const posterSrc = computed(() => (props.work.poster ? proxyImage(props.work.poster) : ''))
const revisit = ref(Boolean(posterSrc.value) && revealedPosters.has(posterSrc.value))

/**
 * 海报加载失败的重试次数（宿主图片代理 DNS 校验偶发失败，见 `retryProxyImage`）。
 * 0 = 原始地址；1 / 2 = 换一个带 `retry=N` 的地址重发。
 */
const retryCount = ref(0)
const retryTimer = ref<ReturnType<typeof setTimeout> | null>(null)
const displaySrc = computed(() => retryProxyImage(posterSrc.value, retryCount.value))

/** 传给 `v-img` 的请求参数（与宿主一致：重入不加 CSS 过渡，直接显示） */
const imgRequest = computed(() => ({
  key: posterSrc.value,
  eager: revisit.value,
  transition: revisit.value ? ({ css: false } as const) : 'fade-transition',
}))

/**
 * 海报是否已经**真正盖住**卡片。
 *
 * 只有到这一步才允许把卡片自身的背景采样关掉（`data-glass-optical-mode="excluded"`）：
 * 占位图与失败态仍要保留完整的玻璃材质（宿主原话）。
 */
const posterCovered = computed(() => Boolean(posterSrc.value) && props.loaded && !imgFailed.value)

/** 当前卡片是否处于「可操作详情态」：桌面看悬停，触摸端看是否被点开 */
function activeState(isHovering: boolean | null | undefined): boolean {
  return activeTouchCardId.value === cardId || (!isTouchLikePointer.value && Boolean(isHovering))
}

/** 浮层是否显示（宿主在图片错误 / 站点弹窗时还有强显分支，本插件不需要） */
function detailVisible(isHovering: boolean | null | undefined): boolean {
  return activeState(isHovering)
}

/** 收起触摸展开态（路由返回 / 换页后不留残影） */
function resetTouchState(): void {
  if (activeTouchCardId.value === cardId) activeTouchCardId.value = null
}

/**
 * 点卡片：触摸端第一次点只展开浮层，展开后再点才进详情；
 * 桌面端悬停即等于展开，点一下直接进详情（宿主 `handleMediaCardClick` 同款）。
 */
function handleClick(isHovering: boolean | null | undefined): void {
  if (isTouchLikePointer.value && !detailVisible(isHovering)) {
    activeTouchCardId.value = cardId
    return
  }
  resetTouchState()
  emit('open', props.work)
}

/** 点到卡外面就把展开态收掉（触摸端专用） */
function handleDocumentPointerDown(event: PointerEvent): void {
  if (!isTouchLikePointer.value || activeTouchCardId.value !== cardId) return
  if (!(event.target instanceof Node)) return
  if (cardRef.value?.contains(event.target)) return
  resetTouchState()
}

const cardRef = ref<HTMLElement | null>(null)

function handleImageLoad(): void {
  imgFailed.value = false
  if (posterSrc.value) revealedPosters.add(posterSrc.value)
  emit('poster', props.work.key)
}

function handleImageError(): void {
  // 宿主图片代理的 SSRF 校验按张做 DNS 解析，整墙同时加载时偶发瞬时失败 ——
  // 隔 700ms 换一个带重试标记的地址再来，两次都失败才退回占位图标。
  if (retryCount.value < 2 && posterSrc.value) {
    if (retryTimer.value) clearTimeout(retryTimer.value)
    retryTimer.value = setTimeout(() => {
      retryCount.value += 1
    }, 700)
    return
  }
  imgFailed.value = true
  emit('poster', props.work.key)
}

onMounted(() => {
  if (isTouchLikePointer.value) document.addEventListener('pointerdown', handleDocumentPointerDown)
})

onBeforeUnmount(() => {
  resetTouchState()
  if (retryTimer.value) clearTimeout(retryTimer.value)
  document.removeEventListener('pointerdown', handleDocumentPointerDown)
})

/** 类型角标配色（宿主 `getChipColor` 逐字照搬；本插件恒走「电视剧」那一档） */
/**
 * 卡片左上角的品类：**漫剧 / 短剧**（2026-10-18 用户口径）。
 *
 * 判据是作品身份的**分类前缀**（`manju:…` / `duanju:…`），不是剧情字段 ——
 * 站点把漫剧单列频道（`/manju/`、`/huolong/` 火龙漫剧），短剧是 `/duanju/`、`/hema/` 河马短剧。
 * 认得前缀就按表给，认不出（裸数字 / 老数据）按「短剧」兜底。
 */
const KIND_LABELS: Record<string, string> = {
  manju: '漫剧',
  huolong: '漫剧',
  duanju: '短剧',
  hema: '短剧',
}

const kindLabel = computed(() => {
  const raw = String(props.work.media_id || '')
  const kind = raw.includes(':') ? raw.split(':')[0].toLowerCase() : ''
  if (kind && KIND_LABELS[kind]) return KIND_LABELS[kind]
  // 没有前缀时看 media_source（墙上老数据可能是裸号 + 来源）
  const source = String(props.work.media_source || '').toLowerCase()
  return KIND_LABELS[source] || '短剧'
})

/** 角标配色：短剧 = 宿主「电视剧」那一档（靛蓝）；漫剧 = 宿主默认紫 */
const kindChipClass = computed(() =>
  kindLabel.value === '漫剧'
    ? 'border-purple-600 bg-purple-600'
    : 'bg-indigo-500 border-indigo-600',
)

/**
 * 新作品标记：`is_new` 由后端**现算**（首播在最近 7 天内，见 `is_fresh_work`），
 * 过了窗口自动撤，不需要任何清理逻辑。
 * 展示位**借用右上角那个角标**（用户 2026-10-19 口径：不要额外再加一枚红 chip，
 * 太突兀；新作品直接顶掉本该显示的「首播日期」）。评分仍在时以评分为准。
 */
const badgeIsNew = computed(() => Number(props.work.vote) <= 0 && Boolean(props.work.is_new))

const badge = computed(() => {
  const vote = Number(props.work.vote)
  if (vote > 0) return vote.toFixed(1)
  const date = String(props.work.release_date || '').trim()
  if (!date) return ''
  const matched = /^(\d{4})-(\d{2})-(\d{2})$/.exec(date)
  return matched ? `${matched[2]}-${matched[3]}` : date
})

/** 角标含义（悬停提示）：评分 / 首播日期（新作品那枚有固定 title，不走这里） */
const badgeTitle = computed(() =>
  Number(props.work.vote) > 0 ? '评分' : '首播日期（百科还没有这部剧的评分）',
)

/**
 * 自建订阅搜索状态（订阅引擎 = self 时后端随行附带）：卡左下角一枚小 chip，
 * 说清「这部会不会被自动下载、为什么没下」。未处理的行没有 sub_state ⇒ 不显示
 * （= 还在队列里，不用逐一标注）。
 */
const SUB_STATES: Record<string, { label: string; cls: string; icon: string }> = {
  downloaded: { label: '已提交下载', cls: 'bg-green-600 border-green-400', icon: 'mdi-check-circle-outline' },
  history: { label: '下载历史已有', cls: 'bg-teal-600 border-teal-400', icon: 'mdi-content-duplicate' },
  in_library: { label: '已在媒体库', cls: 'bg-teal-600 border-teal-400', icon: 'mdi-library-outline' },
  noresult: { label: '暂无资源', cls: 'bg-grey-darken-1 border-grey', icon: 'mdi-magnify-close' },
  failed: { label: '搜索失败', cls: 'bg-red-600 border-red-400', icon: 'mdi-alert-circle-outline' },
}
const subChip = computed(() => SUB_STATES[String(props.work.sub_state || '')] || null)

/** 浮层里的简介行：演员 / 集数 / 题材；墙外来的卡（如搜索结果）退回百科简介 */
function cardSummary(work: WorkItem): string {
  const parts: string[] = []
  if (work.actor) parts.push(work.actor)
  if (work.episode_count) parts.push(`${work.episode_count} 集`)
  const genres = (work.genres || []).slice(0, 3)
  if (genres.length) parts.push(genres.join(' / '))
  if (!parts.length && work.release_date) parts.push(work.release_date)
  return parts.join(' · ') || props.work.overview || '—'
}
</script>

<style scoped>
.sdas-hover-area {
  inline-size: 100%;
}

.sdas-card {
  cursor: pointer;
}

/*
 * 「NEW」标记：不是角标，是**日期位置的替身**。
 * 小字号 + 常规字重 + 宽字距 + 半透明白，无底无边，只借一层极轻的暗色投影
 * 保证它落在浅色海报上不消失。目的是与日期 chip 同级或更轻 —— 一眼看得到，
 * 但不会比片名、海报更抢镜（此前红字/主色底两版都太像告示牌）。
 */
.sdas-new {
  font-size: 0.6875rem;
  font-weight: 600;
  letter-spacing: 0.16em;
  line-height: 1;
  color: rgba(248, 250, 252, 0.9);
  text-shadow: 0 1px 3px rgba(0, 0, 0, 0.7);
  padding-inline: 2px;
  user-select: none;
}

/* 海报骨架（宿主 `#placeholder` 里那层 VSkeletonLoader 的铺法） */
.sdas-poster-skeleton-wrap {
  position: relative;
  block-size: 100%;
  inline-size: 100%;
}

.sdas-poster-skeleton {
  position: absolute;
  inset: 0;
  block-size: 100%;
  inline-size: 100%;
}

/* 海报占位：与宿主 .media-card-placeholder 同一口径 */
.sdas-poster-empty {
  aspect-ratio: 2 / 3;
  inline-size: 100%;
  background: rgba(var(--v-theme-on-surface), 0.08);
}

/*
  悬停浮层里的文字（对应宿主 .media-card-title / .media-card-overview）。
  宿主那两个类在它自己的 scoped 样式里，联邦元素匹配不上 ⇒ 数值在这里复刻。
*/
.sdas-card-title {
  font-size: 1.125rem;
  line-height: 1.25rem;
}

.sdas-card-overview {
  font-size: 0.875rem;
  line-height: 1.125rem;
  opacity: 0.92;
}
</style>
