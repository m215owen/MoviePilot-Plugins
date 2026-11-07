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
      - 封面角标**与网页（duanjubaike.org 作品卡）同款**：实色胶囊、12px 字、字重 500、
        无边框无阴影（`.sdas-chip`，量值照搬站点的 Tailwind 类）。原来那枚自造的「短剧」
        靛蓝 chip 已撤 —— 站点短剧卡上本来没有这枚标；只有漫剧（.net 的 manju / huolong）
        才印一枚紫标，用来区分品类；
      - 右下的来源图标短剧恒为短剧百科，用 MDI 图标代替 logo 外链；
      - 右上没有评分时退成**首播日期**（短剧百科给新剧打分的滞后，整屏空角标更难看）；
      - 左上印数据源卡片上的**状态角标**（爆火 / 新剧 / 完结 / 预约），配色照搬站点。
        2026-11-02 起「新」的判定也改成看这枚「新剧」角标（原先是「本轮比上轮多出来的」，
        那份逐轮对比口径整体下线），所以右上不再单独印 NEW —— 同一个意思不出现两次。
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
        <!--
          2026-10-27：**从 `v-img` 换成原生 `<img>`**。

          现象：接口与图片代理全 200（浏览器实测 101 次请求无一次非 200），
          缓存也落盘了，但整墙海报一张都不显示；同一时刻演员卡（ActorCard）
          正常 —— 两者唯一的差别在图片组件。

          `v-img` 依赖 `:aspect-ratio` 属性撑高容器，样式里没有显式高度：
          这个属性一旦不生效，容器高度就是 0，图片「在、但看不见」。
          原生 `<img>` + CSS `aspect-ratio` 不依赖任何组件内部实现，
          也不再有 `v-img__img--preload`（opacity: 0）这类中间态。
        -->
        <!--
          `referrerpolicy="no-referrer"`：兜底分支会**绕过代理直连图床**，
          带上本站 Referer 反而会撞图床的防盗链；实测不带 Referer 直取 200。
          代理地址那一支不受影响（同源请求）。
        -->
        <img
          v-if="work.poster && !imgFailed"
          :key="displaySrc"
          :src="displaySrc"
          class="sdas-poster-img"
          :class="{ 'sdas-poster-img--ready': posterReady }"
          alt=""
          loading="lazy"
          decoding="async"
          referrerpolicy="no-referrer"
          @load="handleImageLoad"
          @error="handleImageError"
        />
        <div v-else class="sdas-poster-empty d-flex align-center justify-center">
          <v-icon icon="mdi-television-classic" size="64" color="medium-emphasis" />
        </div>

        <!--
          封面角标（左上）：**与 duanjubaike.org 作品卡上的 chip 完全同款**。
          站点封面角标只有两种色胶囊 —— 爆火 `bg-red-500` / 新剧 `bg-green-500`，
          几何统一 `text-xs px-2 py-1 rounded-full font-medium`（纯色、无边框、无阴影）。
          这里不再用 Vuetify 的 elevated chip（有边框有阴影、字重偏重、圆角偏方，
          和网页不是一套东西），照站点量值画 `.sdas-chip`。

          品类「短剧」**不再单独印**：站点短剧卡上本来就没有这枚标，那枚靛蓝 chip
          是插件自造的装饰，扫一眼就和网页对不上。只有漫剧（.net 的 manju / huolong）
          才印一枚紫标区分品类 —— 短剧就是默认情况，不需要额外声明。
        -->
        <div
          v-show="loaded"
          class="absolute left-2 top-2 d-flex flex-column align-start ga-1"
        >
          <span
            v-if="kindLabel !== '短剧'"
            class="sdas-chip sdas-chip-purple"
          >
            {{ kindLabel }}
          </span>
          <span
            v-for="item in stateBadges"
            :key="item.label"
            class="sdas-chip"
            :class="item.cls"
            :title="item.title"
          >
            {{ item.label }}
          </span>
        </div>

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
            右上是「已入库勾 / 评分 / 首播日期」三选一。
            2026-11-02 起这里**不再印 NEW**：新作判定改成「站点的『新剧』角标」
            （用户口径），而「新剧」已经由左上那列状态角标如实呈现（站点原样绿标），
            同一个意思不用在卡上出现两次。
          -->
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

      <!--
        卡下方常显剧名（2026-10-27 用户要求）。
        此前片名只在悬停浮层里出现，未悬停时整墙只有图、认不出是哪部；
        现在固定占两行高度，扫一眼就能读片名。点它等同于点卡片（进详情）。
      -->
      <div
        v-if="work.title"
        class="sdas-card-caption"
        :title="work.title"
        @click.stop="emit('open', work)"
      >
        {{ work.title }}
      </div>
    </div>
  </v-hover>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { proxiedImage, proxyImage, retryProxyImage } from './api'
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

/** 海报代理地址（宿主 `system/img` 代理，带磁盘缓存）。 */
const posterSrc = computed(() => (props.work.poster ? proxyImage(props.work.poster) : ''))

/**
 * 海报加载失败的**重试阶梯**（2026-11-03 重写：现在首选可能是「直连 CDN」）。
 *
 * `proxyImage` 对 `cdn.duanjubaike.org` 直接返回原图（Cloudflare + 一年强缓存，
 * 浏览器自己缓存，翻回去零往返）；其它域名才走宿主 `system/img` 代理。
 * 所以阶梯要按**两条链路互换**来排，而不是固定「代理 → 代理 → 直连」：
 *
 *   0 = 首选链路（直连或代理，见 `proxyImage`）
 *   1 = 换成另一条链路（直连失败走代理 / 代理失败走直连）
 *   2 = 仍走备选链路，但加一个**时间戳**参数绕开可能被缓存住的坏响应
 *   3 = 认输，退回占位图标（之后每 30 秒自己再走一轮，最多两轮）
 *
 * 为什么备选那一步还要时间戳：代理响应带 `Cache-Control: max-age=604800`（七天强
 * 缓存），一旦某次拿到坏响应，浏览器七天之内连请求都不发 —— 固定的 `retry=1` 也会
 * 被缓存住，重试等于重放坏结果。
 */
const MAX_PROXY_RETRY = 2
/** 整轮失败后最多再自己重来的轮数（不用用户刷新页面） */
const MAX_ROUNDS = 2

const retryCount = ref(0)
const retryStamp = ref(Date.now())
const retryTimer = ref<ReturnType<typeof setTimeout> | null>(null)
const roundTimer = ref<ReturnType<typeof setTimeout> | null>(null)
const retryRound = ref(0)

/** 首选地址是不是「直连图床」（`proxyImage` 已经把 CDN 域名放行） */
const preferDirect = computed(
  () => Boolean(posterSrc.value) && posterSrc.value === String(props.work.poster || '').trim(),
)

const displaySrc = computed(() => {
  const raw = String(props.work.poster || '').trim()
  const preferred = posterSrc.value
  if (!preferred) return ''
  const attempt = retryCount.value
  if (attempt <= 0) return preferred
  // 备选链路：首选直连 → 走宿主代理；首选代理 → 直连原图
  const fallback = preferDirect.value ? proxiedImage(raw) : raw
  if (attempt === 1) return fallback
  // 最后一次：在「会被强缓存住坏响应」的那条链路上换时间戳重发
  if (attempt === MAX_PROXY_RETRY) {
    return retryProxyImage(preferDirect.value ? fallback : preferred, retryStamp.value)
  }
  return fallback
})

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

/**
 * 海报是否已经**真正画出像素**（load 过才算）—— 没 load 之前不让它可见。
 *
 * 初值直接查 `revealedPosters`（模块级登记表，跨卡片实例共享）：这张图之前已经
 * 加载过（翻页回来、从详情返回、换视图重建卡片）就**立刻可见**，不必等新的 load
 * 事件 —— 否则每次重挂都会先透明一段，看起来就是「翻回去图片又空了」。
 */
const posterReady = ref(
  Boolean(displaySrc.value && revealedPosters.has(displaySrc.value)),
)

function handleImageLoad(): void {
  imgFailed.value = false
  posterReady.value = true
  if (displaySrc.value) revealedPosters.add(displaySrc.value)
  emit('poster', props.work.key)
}

/** 换一条地址再来一次（时间戳每次都不同，见 `displaySrc` 的说明） */
function scheduleRetry(delay: number): void {
  if (retryTimer.value) clearTimeout(retryTimer.value)
  retryTimer.value = setTimeout(() => {
    retryTimer.value = null
    retryStamp.value = Date.now()
    retryCount.value += 1
  }, delay)
}

function handleImageError(): void {
  // 先把这张图藏起来（`posterReady=false`）：浏览器在「响应到了但不是图片 / 0 字节」
  // 时会画出自己的**裂图**图标，重试那 800ms 里它会一直挂在卡面上 —— 用户看到的
  // 就是「先裂图、再加载出来」。藏起来换重试，覆盖层一直是骨架，不会有裂图。
  posterReady.value = false
  // 这张图这次坏了：把「已展示过」的登记撤掉，重挂时不要凭登记直接亮出来
  if (displaySrc.value) revealedPosters.delete(displaySrc.value)
  // 还有下一条链路可试（阶梯见 `displaySrc` 上方）就隔 800ms 再来
  if (retryCount.value < MAX_PROXY_RETRY && posterSrc.value) {
    scheduleRetry(800)
    return
  }
  imgFailed.value = true
  emit('poster', props.work.key)
  // 整条阶梯都失败：多半是代理那一时的故障（或浏览器缓存了坏响应），
  // 隔半分钟自己再走一轮，不必等用户刷新页面；最多两轮，之后停在占位图标。
  if (retryRound.value < MAX_ROUNDS && !roundTimer.value) {
    roundTimer.value = setTimeout(() => {
      roundTimer.value = null
      retryRound.value += 1
      retryStamp.value = Date.now()
      // 从带新时间戳的那一步起步，不复用可能被缓存住的原始地址
      retryCount.value = 1
      imgFailed.value = false
    }, 30_000)
  }
}

onMounted(() => {
  if (isTouchLikePointer.value) document.addEventListener('pointerdown', handleDocumentPointerDown)
})

onBeforeUnmount(() => {
  resetTouchState()
  if (retryTimer.value) clearTimeout(retryTimer.value)
  if (roundTimer.value) clearTimeout(roundTimer.value)
  document.removeEventListener('pointerdown', handleDocumentPointerDown)
})

/** 类型角标配色（宿主 `getChipColor` 逐字照搬；本插件恒走「电视剧」那一档） */
/**
 * 卡片左上角的品类：**漫剧 / 短剧**（2026-10-18 用户口径）。
 *
 * 判据是作品身份的**分类前缀**，不是剧情字段 —— .org 新站的作品前缀只有
 * `drama:`（站点卡片上另有「短剧 / 漫剧」badge 角标）；.net 老站把漫剧单列频道
 * （`/manju/`、`/huolong/` 火龙漫剧），短剧是 `/duanju/`、`/hema/` 河马短剧。
 * 认得前缀就按表给，认不出（裸数字 / 老数据）按「短剧」兜底。
 */
const KIND_LABELS: Record<string, string> = {
  drama: '短剧',
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

/**
 * 状态角标（爆火 / 新剧 / 完结 / 预约）：数据源作品卡封面左上角那列彩色 chip 的原文。
 *
 * 配色就是站点的 Tailwind 原值（red-500 / green-500 / blue-500 / amber-500），几何也一样
 * （见 `.sdas-chip`）—— 网页什么样，卡上就什么样。
 *
 * 白名单只放已知词：站点以后加新角标时宁可先不显示，也不让卡上飘出认不出的文本 ——
 * 要显示就到这里补一行（连同配色）。
 */
const STATE_BADGES: Record<string, { cls: string; title: string }> = {
  爆火: { cls: 'sdas-chip-red', title: '爆火（站点标记的热播）' },
  新剧: { cls: 'sdas-chip-green', title: '新剧（站点标记的新上线）' },
  完结: { cls: 'sdas-chip-blue', title: '完结' },
  预约: { cls: 'sdas-chip-amber', title: '预约' },
}

const stateBadges = computed(() =>
  (props.work.badges || [])
    .map((text) => {
      const style = STATE_BADGES[text]
      return style ? { label: text, cls: style.cls, title: style.title } : null
    })
    .filter((item): item is { label: string; cls: string; title: string } => Boolean(item)),
)

/**
 * 新剧标记：**不再由本组件判定** —— 2026-11-02 用户口径把「新作」判定改成
 * 「新剧标签」判定后，「新」就是数据源卡片上的「新剧」状态角标，已经由左上那列
 * 状态角标（`stateBadges`）如实呈现，这里不再重复印 NEW / 新作品。
 * 后端的 `is_new` 字段仍在（口径同为「带新剧角标」），供筛选与统计用。
 */

const badge = computed(() => {
  const vote = Number(props.work.vote)
  if (vote > 0) return vote.toFixed(1)
  const date = String(props.work.release_date || '').trim()
  if (!date) return ''
  const matched = /^(\d{4})-(\d{2})-(\d{2})$/.exec(date)
  return matched ? `${matched[2]}-${matched[3]}` : date
})

/** 角标含义（悬停提示）：评分 / 首播日期 */
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
 * 卡下方常显的剧名 —— 版式与 Emby 作品卡下方标题一致（2026-10-27 用户口径）：
 * **居中、单行、超出省略号**。
 *
 * Emby 的 `.cardText` 就是这一套（`text-align: center` + `white-space: nowrap`
 * + `text-overflow: ellipsis`），行高固定 ⇒ 同一行卡片高度天然齐平，
 * 不依赖 line-clamp 的多行截断。颜色取 `on-surface` 派生色，明暗主题自适应。
 */
/*
 * 卡下方常显的剧名 —— 居中、最多两行、超出省略（2026-10-27 用户口径）。
 *
 * 字号 / 字重**向卡内标题（`.sdas-card-title`：18px / bold）靠拢**：卡内是 18px 粗体、
 * 卡下方若只给 14px 常规，同一张卡上像两套排版，所以取两者之间的一档
 * （16px / 600）。位置仍按 Emby 那样居中。
 *
 * 两行截断用 `-webkit-line-clamp`；再用 `min-block-size: 2.7em`（= 2 × 1.35 行高）
 * 把单行标题也撑到两行高，保证同一行卡片高度齐平。
 */
.sdas-card-caption {
  margin-block-start: 8px;
  padding-inline: 4px;
  font-size: 1rem;
  line-height: 1.35;
  font-weight: 600;
  text-align: center;
  color: rgba(var(--v-theme-on-surface), 0.87);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  overflow-wrap: anywhere;
  min-block-size: 2.7em;
  cursor: pointer;
  user-select: none;
}

/**
 * 「NEW」标记的样式已随判定口径下线（2026-11-02：新作 = 站点的「新剧」角标，
 * 由左上的状态角标呈现）。这里保留一段说明，避免后来者把它当漏改的东西加回来。
 */

/*
 * 封面角标（.sdas-chip）：**逐值复刻 duanjubaike.org 作品卡上的 chip**。
 * 站点那几枚标就是 Tailwind 的 `text-xs px-2 py-1 rounded-full font-medium`：
 * 12px 字 / 16px 行高、上下 4px 左右 8px、全圆角、纯色底、无边框无阴影、字重 500。
 * 之前用的 Vuetify elevated chip 有边框、有阴影、字重 700、圆角也偏小 —— 和网页
 * 摆在一起一眼就是两套 UI，所以改成自绘（2026-11-02 用户口径：调得和网页的标一致）。
 * 颜色取站点 Tailwind 原值，不做半透明（站点是实色）。
 */
.sdas-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
  border-radius: 9999px;
  font-size: 12px;
  line-height: 16px;
  font-weight: 500;
  color: #fff;
  white-space: nowrap;
  user-select: none;
}

/* 站点实色：red-500 / green-500 / blue-500 / amber-500；紫是漫剧品类专用的补充色 */
.sdas-chip-red {
  background-color: #ef4444;
}

.sdas-chip-green {
  background-color: #22c55e;
}

.sdas-chip-blue {
  background-color: #3b82f6;
}

.sdas-chip-amber {
  background-color: #f59e0b;
}

.sdas-chip-purple {
  background-color: #a855f7;
}

/* 海报：原生 img，比例与裁切都在 CSS 里定死，不依赖组件的 aspect-ratio 属性 */
.sdas-poster-img {
  display: block;
  inline-size: 100%;
  block-size: auto;
  aspect-ratio: 2 / 3;
  object-fit: cover;
  object-position: center;
  background: rgba(var(--v-theme-on-surface), 0.08);
  /* 只有真正 load 过的图才显形：加载中 / 失败重试期间保持透明，
     浏览器自己那枚裂图图标就不会露出来（2026-11-03 用户反馈「先裂图再加载」）。 */
  opacity: 0;
  transition: opacity 0.18s ease;
}

.sdas-poster-img--ready {
  opacity: 1;
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
