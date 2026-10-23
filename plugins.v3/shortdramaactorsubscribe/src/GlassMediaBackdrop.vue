<template>
  <!--
    卡片区毛玻璃底 —— **照宿主 `src/components/theme/GlassMediaBackdrop.vue` 移植**。

    它干的事：把这一片卡片区里所有**静止**的 `.media-card` 的圆角矩形取并集，
    拼成一条 `clip-path: path(...)`，交给**一个**绝对定位层去做 `backdrop-filter`，
    然后把参与合并的卡片自身的采样关掉。

    为什么要有它（而不是每张卡各自模糊）：每张卡各做一次背景采样，浏览器就得为每张卡
    单独栅格化一遍背景；卡片一多就是几十次采样。合并成一个层只采样一次，视觉一致、
    开销低一个量级。悬停上浮的卡**不参与**合并（宿主同款：上浮与回落动画期间由卡片
    自己采样，动画结束 `transitionend` 再收编）。

    与宿主的差异（照实说明）：
      - 主题判定用 `document.documentElement[data-theme] === 'glass'` —— 宿主读 Vuetify
        的 `theme.global.name`，联邦拿不到那个实例；而宿主主题变量本来就挂在
        `html[data-theme='glass']` 上（`src/styles/themes/glass.scss`），所以读属性等价。
      - 不做宿主那个 `isChromiumFixedShellBackplateBrowser()` 判定（那是宿主固定壳的
        专属优化）；只保留 `clip-path: path()` 与 `backdrop-filter` 的能力检测。
      - 采样层自带 `data-glass-optical-mode="excluded"`（与宿主一致），它自己不会被
        再采一次。

    非 glass 主题下 `enabled` 恒 false ⇒ 组件退化成透明的普通包裹层，零副作用。
  -->
  <div
    ref="root"
    class="sdas-glass-backdrop"
    :class="{ 'is-active': enabled }"
    @transitionend="schedule"
  >
    <div
      v-if="backdrop"
      class="sdas-glass-sampling"
      :style="backdrop"
      aria-hidden="true"
      data-glass-optical-mode="excluded"
    />
    <slot />
  </div>
</template>

<script setup lang="ts">
import { computed, onActivated, onDeactivated, onMounted, onUnmounted, ref, shallowRef, watch, type CSSProperties } from 'vue'

interface SharedBackdrop extends CSSProperties {
  /** 所有待显示海报的圆角并集，使用承载层局部坐标。 */
  clipPath: string
  /** 只分配尚未被海报覆盖的行区间，不随累计分页高度增长。 */
  height: string
  /** 相对列表容器的起点，随虚拟占位更新而非逐帧追随 scrollY。 */
  top: string
}

const root = ref<HTMLElement | null>(null)
const backdrop = shallowRef<SharedBackdrop | null>(null)

// 主题 / 透明度偏好 / 浏览器能力 —— 三者都满足才有意义
const themeName = ref('')
const reducedTransparency = ref(false)
const supported =
  typeof CSS !== 'undefined' &&
  typeof CSS.supports === 'function' &&
  CSS.supports('clip-path', 'path("M0 0H1V1Z")') &&
  CSS.supports('backdrop-filter', 'blur(1px)')
const enabled = computed(() => supported && themeName.value === 'glass' && !reducedTransparency.value)

const ownedCards = new Set<HTMLElement>()
let active = false
let frame = 0
let mutationObserver: MutationObserver | null = null
let resizeObserver: ResizeObserver | null = null
let themeObserver: MutationObserver | null = null
let transparencyMedia: MediaQueryList | null = null

function releaseCards() {
  for (const card of ownedCards) delete card.dataset.glassSharedBackdrop
  ownedCards.clear()
  backdrop.value = null
}

/** 共享层只处理无位移表面；悬停及其退出动画由原生卡片独立采样。 */
function isStationary(card: HTMLElement, css: CSSStyleDeclaration) {
  if (card.classList.contains('app-hover-lift-card--hovering')) return false
  if (css.transform === 'none' || !css.transform) return true

  return new DOMMatrixReadOnly(css.transform).isIdentity
}

function cornerRadius(value: string, width: number, height: number) {
  const parts = value.split(' ')
  const parse = (part: string, size: number) =>
    part.endsWith('%') ? (parseFloat(part) * size) / 100 : parseFloat(part)
  return [
    Math.min(width / 2, Math.max(0, parse(parts[0], width) || 0)),
    Math.min(height / 2, Math.max(0, parse(parts[1] ?? parts[0], height) || 0)),
  ]
}

function update() {
  frame = 0
  const container = root.value
  if (!active || !enabled.value || !container || container.closest('.v-overlay__content')) {
    releaseCards()
    return
  }
  const base = container.getBoundingClientRect()
  if (!base.width || !base.height) {
    releaseCards()
    return
  }

  const nextCards = new Set<HTMLElement>()
  const rects = []
  let top = Infinity
  let bottom = -Infinity
  for (const card of container.querySelectorAll<HTMLElement>('.media-card')) {
    if (card.dataset.glassOpticalMode === 'excluded') continue
    const css = getComputedStyle(card)
    if (!isStationary(card, css)) continue
    const box = card.getBoundingClientRect()
    if (!box.width || !box.height) continue
    const x = box.left - base.left
    const y = box.top - base.top
    rects.push({
      x,
      y,
      w: box.width,
      h: box.height,
      corners: [
        css.borderTopLeftRadius,
        css.borderTopRightRadius,
        css.borderBottomRightRadius,
        css.borderBottomLeftRadius,
      ].map(value => cornerRadius(value, box.width, box.height)),
    })
    top = Math.min(top, y)
    bottom = Math.max(bottom, y + box.height)
    nextCards.add(card)
  }

  const paths = rects.map(({ x, y: offsetY, w, h, corners: [tl, tr, br, bl] }) => {
    const y = offsetY - top
    return `M${x + tl[0]} ${y}H${x + w - tr[0]}A${tr[0]} ${tr[1]} 0 0 1 ${x + w} ${y + tr[1]}V${y + h - br[1]}A${br[0]} ${br[1]} 0 0 1 ${x + w - br[0]} ${y + h}H${x + bl[0]}A${bl[0]} ${bl[1]} 0 0 1 ${x} ${y + h - bl[1]}V${y + tl[1]}A${tl[0]} ${tl[1]} 0 0 1 ${x + tl[0]} ${y}Z`
  })
  // 先计算完整几何，再在同一帧交接采样所有权；不得提前移除尚未就绪的逐卡滤镜。
  const nextBackdrop = paths.length
    ? { clipPath: `path("${paths.join(' ')}")`, top: `${top}px`, height: `${bottom - top}px` }
    : null
  if (
    nextBackdrop?.clipPath !== backdrop.value?.clipPath ||
    nextBackdrop?.top !== backdrop.value?.top ||
    nextBackdrop?.height !== backdrop.value?.height
  )
    backdrop.value = nextBackdrop
  for (const card of ownedCards) {
    if (!nextCards.has(card)) delete card.dataset.glassSharedBackdrop
  }
  ownedCards.clear()
  for (const card of nextCards) {
    if (card.dataset.glassSharedBackdrop !== 'true') card.dataset.glassSharedBackdrop = 'true'
    ownedCards.add(card)
  }
}

function schedule() {
  if (active && enabled.value && !frame) frame = requestAnimationFrame(update)
}

function stop() {
  if (frame) cancelAnimationFrame(frame)
  frame = 0
  mutationObserver?.disconnect()
  resizeObserver?.disconnect()
  themeObserver?.disconnect()
  mutationObserver = null
  resizeObserver = null
  themeObserver = null
  releaseCards()
}

function readTheme() {
  if (typeof document === 'undefined') return
  themeName.value = document.documentElement.dataset.theme || ''
}

function start() {
  stop()
  if (!active || !enabled.value || !root.value) return
  mutationObserver = new MutationObserver(records => {
    if (
      records.some(record => {
        if (record.type === 'childList')
          return [...record.addedNodes, ...record.removedNodes].some(
            node =>
              node instanceof Element &&
              (node.matches('.media-card,[data-progressive-grid-index]') || node.querySelector('.media-card')),
          )
        return record.target instanceof Element && record.target.matches('.media-card,.progressive-card-grid__spacer')
      })
    )
      schedule()
  })
  mutationObserver.observe(root.value, {
    subtree: true,
    childList: true,
    attributes: true,
    attributeFilter: ['data-glass-optical-mode', 'class', 'style'],
  })
  resizeObserver = new ResizeObserver(schedule)
  resizeObserver.observe(root.value)
  schedule()
}

onMounted(() => {
  active = true
  readTheme()
  themeObserver = new MutationObserver(() => {
    readTheme()
    schedule()
  })
  themeObserver.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme', 'data-theme-radius'] })
  if (typeof window !== 'undefined' && typeof window.matchMedia === 'function') {
    transparencyMedia = window.matchMedia('(prefers-reduced-transparency: reduce)')
    reducedTransparency.value = transparencyMedia.matches
    transparencyMedia.addEventListener('change', event => {
      reducedTransparency.value = event.matches
    })
  }
  start()
})

onActivated(() => {
  active = true
  start()
})

onDeactivated(() => {
  active = false
  stop()
})

onUnmounted(() => {
  active = false
  stop()
})

watch(enabled, start, { flush: 'post' })
</script>

<style scoped>
.sdas-glass-backdrop.is-active {
  position: relative;
}

/*
  采样层（z-index 0）垫在内容下面；内容整体抬到 z-index 1。
  ⚠️ 必须排除采样层自己 —— 它也是本容器的直接子元素，一并抬到 z-index 1 就跑到内容
  上面去了（宿主那边只针对 `.progressive-card-grid` 所以没这个坑）。
*/
.sdas-glass-backdrop.is-active > :deep(:not(.sdas-glass-sampling)) {
  position: relative;
  z-index: 1;
}

.sdas-glass-sampling {
  position: absolute;
  z-index: 0;
  pointer-events: none;
  inset-inline-start: 0;
  inline-size: 100%;
  backdrop-filter: var(--glass-native-surface-backdrop-filter);
  -webkit-backdrop-filter: var(--glass-native-surface-backdrop-filter);
}

/* 只移交原生采样；卡片自身的颜色、轮廓和增强档光学资格保持不变。 */
:deep(.media-card[data-glass-shared-backdrop='true']) {
  --glass-native-surface-backdrop-filter: none;
  --glass-surface-backdrop-filter: none;
}
</style>
