<template>
  <!--
    A-Z 快速定位 —— **做成滚动条的样子**（2026-10-20 用户口径）。

    形态：钉在视口最右侧的一条窄条（8px，**不显示字母**）。
      · 鼠标压上去 → 展开成 40px，字母列淡入，鼠标所在位置的字母高亮，左侧浮出大圆气泡；
      · 按下拖动 → 连续跳转（滑过哪个字母就滚到哪个字母）；
      · 不悬停、不拖动时就是一条安静的自定义滚动条，不抢视觉。

    ⚠️ **必须 Teleport 到 body**：宿主面板容器同时带 `transform` 与 `overflow: hidden`，
    留在面板里的 `position: fixed` 会相对那个容器定位 —— 表现是索引跟着内容一起滚，
    还会被裁掉（与「回到顶部」「返回键」同一个坑，见 StickyBack.vue 的注释）。
    搬到 body 后才是真正相对视口；位置由 `sync()` 按锚点元素（卡片网格）的
    `getBoundingClientRect()` 现算，滚动 / 缩放时跟着走。
  -->
  <Teleport to="body">
    <div
      v-if="visible"
      class="sdas-scroll"
      :class="{ 'sdas-scroll--active': active }"
      :style="railStyle"
      role="scrollbar"
      aria-label="按首字母快速定位"
      aria-valuenow="0"
    >
      <!--
        字母列（2026-10-20 用户口径：滚动条加宽、内里显示 A-Z）。
        **默认是一条 8px 的窄条、不显示字母**；鼠标压在这条窄条上才展开成 40px 并把字母淡入。
        展开由 `.sdas-scroll-letters:hover` 自己触发 —— 展开后指针仍在它里面，所以不会抖。

        每个存在的首字母一排，纵向均分整条的高度：
          · `is-current` = 当前滚动位置落在这个字母上（主色字）；
          · `is-active`  = 鼠标/手指正停在这个字母上（主色实心块）。
      -->
      <div
        class="sdas-scroll-letters"
        @pointerdown="onPointerDown"
        @pointermove="onPointerMove"
      >
        <span
          v-for="stop in stops"
          :key="stop.letter"
          class="sdas-scroll-letter"
          :class="{
            'is-current': stop.letter === current,
            'is-active': stop.letter === hint,
          }"
          >{{ stop.letter }}</span
        >
      </div>

      <!-- 悬停 / 拖动时浮出的首字母（大圆气泡，眼睛不用盯细字母） -->
      <Transition name="sdas-alpha-fade">
        <span v-if="hint" class="sdas-scroll-hint" :style="hintStyle">{{ hint }}</span>
      </Transition>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

const props = withDefaults(
  defineProps<{
    /** 字母停靠点（按顺序）：`ratio` = 该字母第一条在列表里的相对位置（0..1） */
    stops: Array<{ letter: string; ratio: number }>
    /** 定位锚点：滚动条贴着它的右边缘、垂直覆盖它当前可见的那段 */
    anchor?: HTMLElement | null
  }>(),
  { anchor: null },
)

const emit = defineEmits<{ (e: 'jump', letter: string): void }>()

/** 轨道在视口里的位置与高度 */
const railStyle = ref<Record<string, string>>({ top: '0px', height: '0px', right: '0px' })
/** 字母提示相对轨道的纵向位置 */
const hintStyle = ref<Record<string, string>>({ top: '0px' })

/**
 * 轨道顶边在视口里的 y（px）。
 * 留一份数值（而不是每次去读 DOM）—— 指针事件比渲染更早到，`rail` 可能还没挂上。
 */
const trackTop = ref(0)

/**
 * 触发热区（2026-10-20 用户口径：「鼠标移到最右边没有触发」）。
 *
 * 折叠态的视觉条只有 8px、还贴在视口最右边缘 —— 要求指针**精确压在这 8px 上**
 * 才算「指着滚动条」，实际很难命中；更糟的是纯 CSS `:hover` 依赖命中测试，
 * 只要右边缘上方压了任何一层别的元素（宿主的全屏 overlay 容器之类），
 * 指针事件根本到不了这条 8px，永远不展开。
 *
 * 所以改成**自己算**：指针距视口右边缘 ≤ HOT_ZONE 且纵向落在轨道范围内就展开。
 * 这样不必压线、也不受上层元素影响（监听挂在 document 捕获阶段）。
 */
const HOT_ZONE = 18
/** 展开后指针外扩到这个距离仍保持展开（展开条 40px + 一点余量），移出去才收起 */
const KEEP_ZONE = 54
/** 纵向允许超出轨道上下的余量（指针在顶端/底端附近也算） */
const VERTICAL_SLACK = 28

/** 当前滚动位置落在哪个字母上（字母列里高亮它） */
const current = ref('')

const visible = ref(false)
/** 悬停或拖动中（拇指高亮 + 展开） */
const active = ref(false)
/** 当前突出的字母（`''` = 不显示） */
const hint = ref('')

/** 轨道高度（像素，供比例换算用） */
const trackHeight = ref(0)
let hovering = false
let dragging = false
/** 拖动中最后一次发出去的字母（同一字母不重复滚） */
let lastJumped = ''

const hasStops = computed(() => props.stops.length > 1)

function clamp(value: number, min: number, max: number): number {
  if (!Number.isFinite(value)) return min
  return Math.min(max, Math.max(min, value))
}

/** 鼠标纵向位置 → 0..1 */
function ratioAt(clientY: number): number {
  if (trackHeight.value <= 0) return 0
  return clamp((clientY - trackTop.value) / trackHeight.value, 0, 1)
}

/** 比例 → 该位置对应的字母（取 ratio 不大于它的最后一个）—— 给「滚动位置」用 */
function letterAtRatio(ratio: number): string {
  const list = props.stops
  if (!list.length) return ''
  let hit = list[0].letter
  for (const stop of list) {
    if (stop.ratio <= ratio + 1e-6) hit = stop.letter
    else break
  }
  return hit
}

/**
 * 鼠标纵向位置 → 字母列里那一格。
 *
 * ⚠️ 跟 `letterAtRatio` 不是一回事：字母列是**等距排布**的（每个字母占一格），
 * 而 `stop.ratio` 是数据分布（某字母可能一整段都挤在 90% 处）。拿数据比例去换算
 * 鼠标位置，点到「M」可能返回「P」。所以这里按**序号**等距换算。
 */
function letterAtPointer(clientY: number): { letter: string; ratio: number } {
  const list = props.stops
  if (!list.length) return { letter: '', ratio: 0 }
  const ratio = ratioAt(clientY)
  const index = clamp(Math.floor(ratio * list.length), 0, list.length - 1)
  return { letter: list[index].letter, ratio: (index + 0.5) / list.length }
}

/** 把字母提示摆到某个纵向位置（相对轨道） */
function placeHint(ratio: number): void {
  const y = clamp(ratio * trackHeight.value, 0, trackHeight.value)
  hintStyle.value = { top: `${Math.round(y)}px` }
}

/** 藏起来时把展开态一起复位，免得下次出现就是展开的 */
function hide(): void {
  visible.value = false
  active.value = false
  hovering = false
  hint.value = ''
}

function sync(): void {
  const el = props.anchor
  if (!el || typeof window === 'undefined') {
    hide()
    return
  }

  const rect = el.getBoundingClientRect()
  const viewportHeight = window.innerHeight || 0

  // 锚点完全在视口外就藏起来（滚出面板 / 切到别的标签）
  if (!hasStops.value || rect.bottom < 160 || rect.top > viewportHeight - 80 || rect.width < 200) {
    hide()
    return
  }

  // 轨道覆盖锚点当前可见的那一段，两端各让出 8px，且不侵入宿主顶栏
  const top = Math.max(rect.top + 8, 76)
  const bottom = Math.min(rect.bottom - 8, viewportHeight - 16)
  const height = Math.max(96, bottom - top)

  // 滚动进度：内容顶部已经被滚到可视区上方多少
  const contentHeight = Math.max(rect.height, el.offsetHeight, 1)
  const viewportSpan = Math.max(160, viewportHeight - 76 - 16)

  // 内容装得下一屏 ⇒ 没得滚，滚动条没有意义（只留拇指也没处拖）
  if (contentHeight <= viewportSpan + 80) {
    hide()
    return
  }

  trackHeight.value = height
  trackTop.value = top
  /*
    折叠态**贴视口最右边缘**（2026-10-20 用户口径：「滚动条贴边」）。
    原生滚动条隐藏后它占的宽度已经补成容器内侧留白（见 ActorWall 的
    `muteNativeScrollBar`），所以贴边不会压住卡片。
  */
  railStyle.value = {
    top: `${Math.round(top)}px`,
    height: `${Math.round(height)}px`,
    right: '0px',
  }

  const scrolled = Math.max(0, 76 - rect.top)
  const progressValue = clamp(scrolled / Math.max(1, contentHeight - viewportSpan), 0, 1)

  // 字母列不需要拇指：当前字母本身就是滚动位置的读数
  current.value = letterAtRatio(progressValue)

  visible.value = true
}

let raf = 0
function queueSync(): void {
  if (raf) return
  raf = requestAnimationFrame(() => {
    raf = 0
    sync()
  })
}

/** 按鼠标位置更新提示（气泡贴在那一格的中心），返回命中的字母 */
function showHintAt(clientY: number): string {
  const hit = letterAtPointer(clientY)
  hint.value = hit.letter
  placeHint(hit.ratio)
  return hit.letter
}

function jump(letter: string): void {
  if (!letter || letter === lastJumped) return
  lastJumped = letter
  emit('jump', letter)
}

function onPointerDown(event: PointerEvent): void {
  if (!hasStops.value) return
  dragging = true
  active.value = true
  lastJumped = ''
  event.preventDefault()
  ;(event.currentTarget as HTMLElement)?.setPointerCapture?.(event.pointerId)
  jump(showHintAt(event.clientY))
}

function onPointerMove(event: PointerEvent): void {
  // 只负责「拖动中的连续跳转」；悬停展开交给下面的全局热区判定
  if (!dragging) return
  jump(showHintAt(event.clientY))
}

/**
 * 指针距视口右边缘还有多少 px（负数 = 已经在窗口外）。
 *
 * 基准取 `documentElement.clientWidth`（不含窗口滚动条），与 `position: fixed; right: 0`
 * 的定位基准一致 —— 否则窗口本身带滚动条时，条会落在滚动条左侧，鼠标移到「最右边」
 * 其实压在那 15px 的滚动条上，永远碰不到条。
 */
function edgeGap(clientX: number): number {
  const width = document.documentElement?.clientWidth || window.innerWidth || 0
  return width - clientX
}

/**
 * 按指针位置决定「展开 / 保持 / 收起」，并同步气泡文字。
 *
 * 两段阈值：没展开时只在最右 HOT_ZONE 内触发；一旦展开，外扩到 KEEP_ZONE 都保持，
 * 指针在展开条里移动不会因为跨出 8px 又被判成离开而反复闪。
 */
function applyPointer(clientX: number, clientY: number): void {
  if (!visible.value || dragging || !hasStops.value) return
  const gap = edgeGap(clientX)
  const withinVertical =
    clientY >= trackTop.value - VERTICAL_SLACK &&
    clientY <= trackTop.value + trackHeight.value + VERTICAL_SLACK

  if (!active.value) {
    if (gap < -2 || gap > HOT_ZONE || !withinVertical) return
    hovering = true
    active.value = true
    lastJumped = ''
    showHintAt(clientY)
    return
  }

  if (gap < -2 || gap > KEEP_ZONE || !withinVertical) {
    hovering = false
    active.value = false
    hint.value = ''
    return
  }
  showHintAt(clientY)
}

let moveRaf = 0
function onGlobalPointerMove(event: PointerEvent): void {
  // 触摸没有「悬停」概念：手指按住时由本地 pointerdown 接管，这里只认鼠标
  if (event.pointerType !== 'mouse') return
  if (!visible.value || dragging) return
  const x = event.clientX
  const y = event.clientY
  if (moveRaf) return
  moveRaf = requestAnimationFrame(() => {
    moveRaf = 0
    applyPointer(x, y)
  })
}

function stopDrag(): void {
  if (!dragging) return
  dragging = false
  active.value = hovering
  if (!hovering) hint.value = ''
  lastJumped = ''
}

onMounted(() => {
  // scroll 不冒泡 ⇒ 捕获阶段挂在 document 上，任意祖先容器滚动都能收到
  document.addEventListener('scroll', queueSync, true)
  /*
    热区判定也走 document 捕获阶段：宿主页面右边缘若压了别的元素，指针事件不会
    落到这条 8px 上（纯 CSS `:hover` 就永不触发）；捕获阶段在 document 上能先拿到
    坐标，自己算「离右边缘多远」，不依赖命中测试。
  */
  document.addEventListener('pointermove', onGlobalPointerMove, true)
  window.addEventListener('resize', queueSync)
  window.addEventListener('pointerup', stopDrag)
  window.addEventListener('pointercancel', stopDrag)
  sync()
})

onBeforeUnmount(() => {
  document.removeEventListener('scroll', queueSync, true)
  document.removeEventListener('pointermove', onGlobalPointerMove, true)
  window.removeEventListener('resize', queueSync)
  window.removeEventListener('pointerup', stopDrag)
  window.removeEventListener('pointercancel', stopDrag)
  if (raf) cancelAnimationFrame(raf)
  if (moveRaf) cancelAnimationFrame(moveRaf)
})

// 锚点换人（切标签 / 重新挂载）或字母表变化时重算一次
watch(() => [props.anchor, props.stops.length], () => queueSync())
</script>

<style scoped>
/*
 * 定位容器：40px 宽、钉在视口最右侧（宿主原生滚动条原来的位置）。
 * **自己不接指针**（`pointer-events: none`）—— 指针只认里面那条 8px 窄条，
 * 这样折叠状态下只有 8px 会从卡片上"抢"事件，不会把右侧 40px 全占掉。
 */
.sdas-scroll {
  position: fixed;
  z-index: 1400;
  width: 40px;
  border-radius: 999px;
  pointer-events: none;
  user-select: none;
}

/*
 * 字母列：**折叠 = 8px 窄条、字母全透明**；悬停 / 拖动 = 展开成 40px、字母淡入。
 *
 * 展开靠 `:hover` 自己触发（而不是靠外层 40px 容器），所以：
 *   · 鼠标没来时不会因为"路过右边 40px"就展开；
 *   · 一旦展开，指针仍落在展开后的 40px 里，hover 不会中断 —— 不会来回抖。
 *
 * 每格 `flex: 1` + `space-evenly`：字母按轨道高度自动摊开，字母多、条矮时也塞得下。
 */
.sdas-scroll-letters {
  position: absolute;
  inset-block: 0;
  right: 0;
  width: 8px;
  display: flex;
  flex-direction: column;
  justify-content: space-evenly;
  padding-block: 4px;
  border-radius: 999px;
  background: rgba(var(--v-theme-surface), 0.5);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  box-shadow:
    0 2px 10px rgba(0, 0, 0, 0.08),
    inset 0 0 0 1px rgba(var(--v-theme-on-surface), 0.06);
  overflow: hidden;
  pointer-events: auto;
  touch-action: none;
  cursor: pointer;
  user-select: none;
  transition:
    width 0.18s ease,
    background-color 0.16s ease;
}

/*
 * 展开只看 `--active`（由「右侧热区」判定，见脚本里的 applyPointer），
 * 不再用 `:hover` —— 纯 CSS hover 依赖命中测试，右边缘上方只要压着任何一层
 * 别的元素就永远收不到指针，"鼠标移到最右边"会毫无反应。
 */
.sdas-scroll--active .sdas-scroll-letters {
  width: 40px;
  background: rgba(var(--v-theme-surface), 0.86);
}

/* 单个字母：折叠时全透明（只有条，没有字） */
.sdas-scroll-letter {
  flex: 1 1 0;
  min-block-size: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
  line-height: 1;
  letter-spacing: 0.02em;
  color: rgba(var(--v-theme-on-surface), 0.5);
  opacity: 0;
  transition:
    opacity 0.14s ease,
    color 0.12s ease,
    background-color 0.12s ease,
    transform 0.12s ease;
}

.sdas-scroll--active .sdas-scroll-letter {
  opacity: 1;
}

/* 当前滚动位置落在这个字母上 */
.sdas-scroll-letter.is-current {
  color: rgb(var(--v-theme-primary));
  font-weight: 800;
}

/* 鼠标/手指正压在这个字母上 */
.sdas-scroll-letter.is-active {
  color: rgb(var(--v-theme-on-primary));
  background: rgb(var(--v-theme-primary));
  font-weight: 800;
  transform: scale(1.06);
}

/*
 * 悬停 / 拖动时浮出的首字母 —— **iOS 通讯录那种圆形气泡**（2026-10-20 用户口径：
 * 「突出显示有个线性包裹」，不要方框）：正圆、无描边、主色实底，右侧一枚小尖角
 * 指向字母列，柔和投影托住。摆在字母列左侧 4px，别踩在指针下面。
 */
.sdas-scroll-hint {
  position: absolute;
  right: 46px;
  transform: translateY(-50%);
  display: flex;
  align-items: center;
  justify-content: center;
  inline-size: 46px;
  block-size: 46px;
  border-radius: 50%;
  font-size: 21px;
  font-weight: 700;
  line-height: 1;
  letter-spacing: 0.02em;
  color: rgb(var(--v-theme-on-primary));
  background: rgb(var(--v-theme-primary));
  box-shadow:
    0 8px 22px rgba(0, 0, 0, 0.22),
    0 2px 6px rgba(0, 0, 0, 0.14);
  pointer-events: none;
}

/* 指向细轨的小尖角（气泡右侧，垂直居中） */
.sdas-scroll-hint::after {
  content: '';
  position: absolute;
  inset-inline-start: 100%;
  inset-block-start: 50%;
  margin-block-start: -5px;
  inline-size: 0;
  block-size: 0;
  border-block: 5px solid transparent;
  border-inline-start: 7px solid rgb(var(--v-theme-primary));
}

.sdas-alpha-fade-enter-active,
.sdas-alpha-fade-leave-active {
  transition: opacity 0.14s ease;
}

.sdas-alpha-fade-enter-from,
.sdas-alpha-fade-leave-to {
  opacity: 0;
}
</style>
