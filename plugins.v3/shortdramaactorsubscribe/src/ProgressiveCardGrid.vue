<script setup lang="ts">
/**
 * 虚拟滚动卡片网格 —— 复刻宿主 `src/components/misc/ProgressiveCardGrid.vue` 的核心机制。
 *
 * 为什么必须有它（探索页「滑到哪加载到哪」的真正答案）：
 * - 整份列表的高度**立即**由上下占位符（spacer）撑出来 —— 行高用「列宽 × 比率」估算，
 *   挂载后由 ResizeObserver 实测校正。⇒ 第一页数据一到滚动条就是「全长」的，
 *   「满没满一屏」的判定天然为真，加载链不会再把全集串行拉完；
 * - DOM 里**只挂载「视口 ± overscan 行」**的卡片，其余行都是 spacer ——
 *   拉了 40 页也只会有几十张卡真的在 DOM 里，不会再把页面压死；
 * - 渐进挂载只在**可见窗口内**按帧补批（与宿主同节奏：首批 initialCount，之后每帧一批）。
 *
 * 与宿主的差异（都有意为之）：
 * - 类名换 `sdas-pcg-*`（联邦 CSS 门禁：含 `.v-` 的选择器整条被丢，这里根本不用）；
 * - 不做 scrollToIndex / overlay 内虚拟化（插件用不到），overlay 滚动锁保留
 *   （弹宿主对话框时 body 会加 `v-overlay-scroll-blocked`，此时冻结窗口防坐标跳变）。
 */
import {
  computed,
  onActivated,
  onDeactivated,
  onMounted,
  onUnmounted,
  ref,
  watch,
} from 'vue'
import type { ComponentPublicInstance } from 'vue'

type ItemKey = string | number

const props = withDefaults(
  defineProps<{
    /** 完整业务列表；slot 按调用方数据结构渲染，可见窗口不修改原数组 */
    items: any[]
    /** 自动分列时允许的最小条目宽度（CSS px） */
    minItemWidth?: number
    /** 未实测条目的高度估算比率（高度 = 列宽 × 比率） */
    itemAspectRatio?: number
    /** 行列共用的间距（CSS px） */
    gap?: number
    /** 首批最少条目数，实际提交时补齐整行并覆盖当前视口 */
    initialCount?: number
    /** 后续每帧补充的条目数（实际按整行取整） */
    batchSize?: number
    /** 可见窗口上下额外保留的行数 */
    overscanRows?: number
    /** 稳定业务键；缺省用索引 */
    getItemKey?: (item: any, index: number) => string | number
  }>(),
  {
    minItemWidth: 144,
    itemAspectRatio: 1.5,
    gap: 16,
    initialCount: 6,
    batchSize: 6,
    overscanRows: 4,
    getItemKey: undefined,
  },
)

interface VirtualCell {
  item: any
  /** 完整列表中的零基索引 */
  index: number
  key: ItemKey
}

interface VirtualRange {
  startIndex: number
  endIndex: number
  startRow: number
  endRow: number
}

const containerRef = ref<HTMLElement | null>(null)
const trackRef = ref<HTMLElement | null>(null)

const layoutWidth = ref(0)
const viewportTop = ref(0)
const viewportBottom = ref(0)
const heightVersion = ref(0)
const frozenVisibleRange = ref<VirtualRange | null>(null)
const progressiveStartIndex = ref(0)
const progressiveEndIndex = ref(0)

const itemHeights = new Map<ItemKey, number>()
const observedElements = new Map<HTMLElement, ItemKey>()
const keyElements = new Map<ItemKey, HTMLElement>()
const itemRefCallbacks = new Map<ItemKey, (element: Element | ComponentPublicInstance | null) => void>()

let resizeObserver: ResizeObserver | null = null
let itemResizeObserver: ResizeObserver | null = null
let overlayLockObserver: MutationObserver | null = null
let scrollTarget: Window | HTMLElement | null = null
let layoutFrameId: number | null = null
let scrollFrameId: number | null = null
let progressiveFrameId: number | null = null
let mounted = false
let lastMeasuredColumnCount = 0
let lastMeasuredColumnWidth = 0
let documentOverlayLocked = false

const safeGap = computed(() => Math.max(0, props.gap))
const safeInitialCount = computed(() => Math.max(1, Math.floor(props.initialCount)))
const safeBatchSize = computed(() => Math.max(1, Math.floor(props.batchSize)))
const safeMinItemWidth = computed(() => Math.max(1, props.minItemWidth))
const safeOverscanRows = computed(() => Math.max(1, props.overscanRows))

const columnCount = computed(() => {
  if (!layoutWidth.value) return 1
  return Math.max(1, Math.floor((layoutWidth.value + safeGap.value) / (safeMinItemWidth.value + safeGap.value)))
})

const columnWidth = computed(() => {
  const columns = columnCount.value
  const width = layoutWidth.value || safeMinItemWidth.value
  return Math.max(1, (width - safeGap.value * (columns - 1)) / columns)
})

const estimatedHeight = computed(() => Math.max(1, columnWidth.value * props.itemAspectRatio))

const itemKeys = computed(() => props.items.map((item, index) => getComparableKey(item, index)))

const keyIndexMap = computed(() => {
  const map = new Map<ItemKey, number>()
  itemKeys.value.forEach((key, index) => map.set(key, index))
  return map
})

/** 每行高度：行内实测值取最大；有未实测条目时退化用估算值占位 */
const rowMetrics = computed(() => {
  void heightVersion.value

  const rows = Math.ceil(props.items.length / columnCount.value)
  const heights: number[] = []
  const measuredRows: boolean[] = []
  const offsets: number[] = [0]

  for (let row = 0; row < rows; row += 1) {
    const startIndex = row * columnCount.value
    const endIndex = Math.min(startIndex + columnCount.value, props.items.length)
    let rowHeight = 0
    let hasUnmeasuredItem = false

    for (let index = startIndex; index < endIndex; index += 1) {
      const height = itemHeights.get(itemKeys.value[index])
      if (height && height > 0) {
        rowHeight = Math.max(rowHeight, height)
      } else {
        hasUnmeasuredItem = true
      }
    }

    if (hasUnmeasuredItem) rowHeight = Math.max(rowHeight, estimatedHeight.value)
    else rowHeight = Math.max(rowHeight, 1)

    heights.push(rowHeight)
    measuredRows.push(!hasUnmeasuredItem)
    offsets.push(offsets[row] + rowHeight + (row < rows - 1 ? safeGap.value : 0))
  }

  return { heights, measuredRows, offsets, rowCount: rows, totalHeight: offsets[rows] ?? 0 }
})

const totalHeight = computed(() => rowMetrics.value.totalHeight)

const calculatedViewportRange = computed<VirtualRange>(previous => {
  const { offsets, rowCount } = rowMetrics.value

  if (!props.items.length || rowCount === 0) {
    return { endIndex: 0, endRow: 0, startIndex: 0, startRow: 0 }
  }

  const top = Math.max(0, Math.min(viewportTop.value, totalHeight.value))
  const bottom = Math.max(top, Math.min(viewportBottom.value, totalHeight.value))
  const firstVisibleRow = findFirstRowAtOrAfterOffset(offsets, top)
  const lastVisibleRow = findLastRowAtOrBeforeOffset(offsets, rowCount, bottom)

  const nextRange = {
    endIndex: Math.min(props.items.length, (lastVisibleRow + 1) * columnCount.value),
    endRow: lastVisibleRow,
    startIndex: firstVisibleRow * columnCount.value,
    startRow: firstVisibleRow,
  }

  // 行内滚动不改变挂载窗口：复用旧范围，避免整批 slot 更新与渐进任务重排
  if (
    previous &&
    previous.startIndex === nextRange.startIndex &&
    previous.endIndex === nextRange.endIndex &&
    previous.startRow === nextRange.startRow &&
    previous.endRow === nextRange.endRow
  ) {
    return previous
  }

  return nextRange
})

const calculatedVisibleRange = computed<VirtualRange>(() => {
  if (!props.items.length) return calculatedViewportRange.value

  const viewportRange = calculatedViewportRange.value
  const rowCount = rowMetrics.value.rowCount
  const startRow = clamp(viewportRange.startRow - safeOverscanRows.value, 0, rowCount - 1)
  const endRow = clamp(viewportRange.endRow + safeOverscanRows.value, startRow, rowCount - 1)

  return {
    endIndex: Math.min(props.items.length, (endRow + 1) * columnCount.value),
    endRow,
    startIndex: startRow * columnCount.value,
    startRow,
  }
})

const visibleRange = computed(() => frozenVisibleRange.value ?? calculatedVisibleRange.value)

/** 视口首批内容同步提交，额外 overscan 分帧挂载；整份列表高度仍由 spacer 立即占位 */
const renderedVisibleRange = computed<VirtualRange>(previous => {
  const range = visibleRange.value

  if (frozenVisibleRange.value || range.endIndex <= range.startIndex) {
    return range
  }

  const viewportRange = calculatedViewportRange.value
  const initialEndIndex = Math.min(
    range.endIndex,
    Math.max(
      viewportRange.endIndex,
      Math.ceil((viewportRange.startIndex + safeInitialCount.value) / columnCount.value) * columnCount.value,
    ),
  )
  const stagedStartIndex = clamp(progressiveStartIndex.value, range.startIndex, viewportRange.startIndex)
  const stagedEndIndex = clamp(
    Math.max(progressiveEndIndex.value, initialEndIndex),
    viewportRange.endIndex,
    range.endIndex,
  )
  const startRow = Math.max(range.startRow, Math.floor(stagedStartIndex / columnCount.value))
  const endRow = Math.min(range.endRow, Math.max(range.startRow, Math.ceil(stagedEndIndex / columnCount.value) - 1))

  const nextRange = {
    ...range,
    endIndex: Math.min(range.endIndex, (endRow + 1) * columnCount.value),
    endRow,
    startIndex: startRow * columnCount.value,
    startRow,
  }

  if (
    previous &&
    previous.startIndex === nextRange.startIndex &&
    previous.endIndex === nextRange.endIndex &&
    previous.startRow === nextRange.startRow &&
    previous.endRow === nextRange.endRow
  ) {
    return previous
  }

  return nextRange
})

const visibleCells = computed<VirtualCell[]>(() => {
  const cells: VirtualCell[] = []
  const range = renderedVisibleRange.value
  for (let index = range.startIndex; index < range.endIndex; index += 1) {
    cells.push({ item: props.items[index], index, key: itemKeys.value[index] })
  }
  return cells
})

const topSpacerHeight = computed(() => rowMetrics.value.offsets[renderedVisibleRange.value.startRow] ?? 0)

const visibleBlockHeight = computed(() => {
  const range = renderedVisibleRange.value
  if (!props.items.length || range.endIndex <= range.startIndex) return 0
  return Math.max(
    (rowMetrics.value.offsets[range.endRow] ?? 0) +
      (rowMetrics.value.heights[range.endRow] ?? 0) -
      (rowMetrics.value.offsets[range.startRow] ?? 0),
    0,
  )
})

const bottomSpacerHeight = computed(() =>
  Math.max(totalHeight.value - topSpacerHeight.value - visibleBlockHeight.value, 0),
)

const gridStyle = computed(() => ({
  columnGap: `${safeGap.value}px`,
  gridTemplateColumns: `repeat(${columnCount.value}, minmax(0, 1fr))`,
  rowGap: `${safeGap.value}px`,
}))

function clamp(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max)
}

function getComparableKey(item: any, index: number): ItemKey {
  if (props.getItemKey) return props.getItemKey(item, index)
  return index
}

function getFallbackLayoutWidth() {
  if (typeof window === 'undefined') return safeMinItemWidth.value
  // keep-alive 激活首帧可能拿不到网格宽度，先用视口宽度兜底，避免只渲染一小列
  return Math.max(document.documentElement.clientWidth || window.innerWidth || 0, safeMinItemWidth.value)
}

function findFirstRowAtOrAfterOffset(offsets: number[], offset: number) {
  const heights = rowMetrics.value.heights
  let low = 0
  let high = heights.length - 1
  let answer = 0
  while (low <= high) {
    const mid = Math.floor((low + high) / 2)
    if (offsets[mid] + heights[mid] >= offset) {
      answer = mid
      high = mid - 1
    } else {
      low = mid + 1
    }
  }
  return answer
}

function findLastRowAtOrBeforeOffset(offsets: number[], rowCount: number, offset: number) {
  let low = 0
  let high = rowCount - 1
  let answer = 0
  while (low <= high) {
    const mid = Math.floor((low + high) / 2)
    if (offsets[mid] <= offset) {
      answer = mid
      low = mid + 1
    } else {
      high = mid - 1
    }
  }
  return answer
}

// ── overlay 滚动锁：宿主弹对话框时 body 加 `v-overlay-scroll-blocked` ──

function isDocumentOverlayLocked() {
  return typeof document !== 'undefined' && document.documentElement.classList.contains('v-overlay-scroll-blocked')
}

function shouldPauseVirtualSync() {
  return isDocumentOverlayLocked()
}

function freezeVisibleRange() {
  if (frozenVisibleRange.value) return
  cancelProgressiveRender()
  frozenVisibleRange.value = { ...renderedVisibleRange.value }
}

function releaseVisibleRange() {
  frozenVisibleRange.value = null
  syncProgressiveWindow()
  queueProgressiveRender()
}

function handleOverlayLockChange() {
  const nextOverlayLocked = isDocumentOverlayLocked()
  if (nextOverlayLocked === documentOverlayLocked) return

  documentOverlayLocked = nextOverlayLocked

  if (shouldPauseVirtualSync()) {
    freezeVisibleRange()
    return
  }

  invalidateScrollTargetCache()
  releaseVisibleRange()
  queueLayoutSync()
}

// ── 条目测高（ResizeObserver 按实测行高校正 spacer，滚动才不会越滚越漂） ──

function getElementFromRef(element: Element | ComponentPublicInstance | null): HTMLElement | null {
  if (!element || typeof HTMLElement === 'undefined') return null
  if (element instanceof HTMLElement) return element
  if (!('$el' in element)) return null
  const componentElement = element.$el
  return componentElement instanceof HTMLElement ? componentElement : null
}

function getRowHeight(row: number) {
  const startIndex = row * columnCount.value
  const endIndex = Math.min(startIndex + columnCount.value, props.items.length)
  let rowHeight = 0
  let hasUnmeasuredItem = false

  for (let index = startIndex; index < endIndex; index += 1) {
    const height = itemHeights.get(itemKeys.value[index])
    if (height && height > 0) rowHeight = Math.max(rowHeight, height)
    else hasUnmeasuredItem = true
  }

  if (hasUnmeasuredItem) return Math.max(rowHeight, estimatedHeight.value)
  return Math.max(rowHeight, 1)
}

function ensureItemResizeObserver() {
  if (itemResizeObserver || typeof ResizeObserver === 'undefined') return

  itemResizeObserver = new ResizeObserver(entries => {
    if (shouldPauseVirtualSync()) {
      freezeVisibleRange()
      return
    }

    let shouldUpdate = false
    let scrollAdjustment = 0
    const currentViewportTop = viewportTop.value
    const currentOffsets = rowMetrics.value.offsets

    entries.forEach(entry => {
      const element = entry.target
      if (!(element instanceof HTMLElement)) return

      const key = observedElements.get(element)
      const index = key === undefined ? undefined : keyIndexMap.value.get(key)
      if (key === undefined || index === undefined) return

      const borderSize = Array.isArray(entry.borderBoxSize) ? entry.borderBoxSize[0] : entry.borderBoxSize
      const nextHeight = borderSize?.blockSize || entry.contentRect.height
      const previousHeight = itemHeights.get(key)
      if (!nextHeight || Math.abs((previousHeight ?? 0) - nextHeight) < 0.5) return

      const row = Math.floor(index / columnCount.value)
      const rowWasFullyMeasured = rowMetrics.value.measuredRows[row]
      const previousRowHeight = getRowHeight(row)
      const previousRowBottom = (currentOffsets[row] ?? 0) + previousRowHeight

      // 收缩抖动过滤：实测值比估算矮一点点时不再回写，避免 spacer 上下弹跳
      if (
        rowWasFullyMeasured &&
        previousHeight !== undefined &&
        previousHeight < previousRowHeight - 0.5 &&
        nextHeight <= previousRowHeight + 0.5
      ) {
        return
      }

      itemHeights.set(key, nextHeight)

      const nextRowHeight = getRowHeight(row)
      const delta = nextRowHeight - previousRowHeight
      // 视口上方行高变化时补偿 scrollTop，视觉位置不跳
      if (Math.abs(delta) >= 0.5 && previousRowBottom < currentViewportTop) {
        scrollAdjustment += delta
      }

      shouldUpdate = true
    })

    if (!shouldUpdate) return

    heightVersion.value += 1

    if (Math.abs(scrollAdjustment) >= 0.5) adjustScrollTop(scrollAdjustment)

    queueViewportSync()
  })
}

function setItemRef(element: Element | ComponentPublicInstance | null, key: ItemKey) {
  const htmlElement = getElementFromRef(element)
  const previousElement = keyElements.get(key)

  if (!htmlElement) {
    if (previousElement) {
      itemResizeObserver?.unobserve(previousElement)
      observedElements.delete(previousElement)
      keyElements.delete(key)
    }
    return
  }

  if (previousElement === htmlElement) return

  ensureItemResizeObserver()

  if (previousElement) {
    itemResizeObserver?.unobserve(previousElement)
    observedElements.delete(previousElement)
  }

  observedElements.set(htmlElement, key)
  keyElements.set(key, htmlElement)
  itemResizeObserver?.observe(htmlElement)
}

function getItemRef(key: ItemKey) {
  const existingCallback = itemRefCallbacks.get(key)
  if (existingCallback) return existingCallback

  const callback = (element: Element | ComponentPublicInstance | null) => setItemRef(element, key)
  itemRefCallbacks.set(key, callback)
  return callback
}

// ── 滚动容器探测（插件面板里会滚的不是 window/body —— 与宿主 scrollTarget.ts 同一套） ──

let targetCache = new WeakMap<HTMLElement, Window | HTMLElement>()

function invalidateScrollTargetCache() {
  targetCache = new WeakMap<HTMLElement, Window | HTMLElement>()
}

function isScrollableOverflow(overflowY: string) {
  return overflowY === 'auto' || overflowY === 'scroll' || overflowY === 'overlay'
}

function findNearestScrollTarget(element: HTMLElement | null): Window | HTMLElement {
  if (!element) return window

  let parent = element.parentElement
  const visited: HTMLElement[] = []
  let target: Window | HTMLElement = window

  while (parent && parent !== document.body && parent !== document.documentElement) {
    const cachedTarget = targetCache.get(parent)
    if (cachedTarget) {
      target = cachedTarget
      break
    }

    visited.push(parent)

    if (isScrollableOverflow(window.getComputedStyle(parent).overflowY)) {
      target = parent
      break
    }

    parent = parent.parentElement
  }

  visited.forEach(ancestor => targetCache.set(ancestor, target))
  return target
}

function findScrollTarget(): Window | HTMLElement {
  return findNearestScrollTarget(containerRef.value)
}

function addScrollListener(target: Window | HTMLElement) {
  target.addEventListener('scroll', queueViewportSync, { passive: true })
}

function removeScrollListener(target: Window | HTMLElement | null) {
  target?.removeEventListener('scroll', queueViewportSync)
}

function refreshScrollTarget() {
  if (!mounted) return
  const nextTarget = findScrollTarget()
  if (scrollTarget === nextTarget) return
  removeScrollListener(scrollTarget)
  scrollTarget = nextTarget
  addScrollListener(scrollTarget)
}

function handleWindowResize() {
  invalidateScrollTargetCache()
  queueLayoutSync()
}

function syncLayoutWidth() {
  const element = trackRef.value
  if (!element) {
    if (layoutWidth.value <= 0) layoutWidth.value = getFallbackLayoutWidth()
    return
  }

  const nextWidth = element.clientWidth
  if (nextWidth > 0) {
    layoutWidth.value = nextWidth
    return
  }

  if (layoutWidth.value <= 0) layoutWidth.value = getFallbackLayoutWidth()
}

function syncViewport() {
  const element = trackRef.value

  if (!element) {
    if (viewportBottom.value <= viewportTop.value) {
      viewportTop.value = 0
      viewportBottom.value = typeof window === 'undefined' ? 0 : window.innerHeight
    }
    return
  }

  const trackRect = element.getBoundingClientRect()
  const viewportRect =
    scrollTarget && scrollTarget !== window
      ? (scrollTarget as HTMLElement).getBoundingClientRect()
      : { bottom: window.innerHeight, top: 0 }

  const nextViewportTop = viewportRect.top - trackRect.top
  const nextViewportBottom = viewportRect.bottom - trackRect.top

  if (nextViewportBottom > nextViewportTop) {
    viewportTop.value = nextViewportTop
    viewportBottom.value = nextViewportBottom
  }
}

// ── 帧调度（rAF 节流；后台标签页冻结时各自停摆，回来由 keep-alive/事件兜底） ──

function queueLayoutSync() {
  if (typeof window === 'undefined' || layoutFrameId !== null) return

  layoutFrameId = window.requestAnimationFrame(() => {
    layoutFrameId = null

    if (shouldPauseVirtualSync()) {
      freezeVisibleRange()
      return
    }

    releaseVisibleRange()
    syncLayoutWidth()
    refreshScrollTarget()
    syncViewport()
  })
}

function queueViewportSync() {
  if (typeof window === 'undefined' || scrollFrameId !== null) return

  scrollFrameId = window.requestAnimationFrame(() => {
    scrollFrameId = null

    if (shouldPauseVirtualSync()) {
      freezeVisibleRange()
      return
    }

    releaseVisibleRange()
    syncViewport()
  })
}

function cancelProgressiveRender() {
  if (progressiveFrameId === null) return
  window.cancelAnimationFrame(progressiveFrameId)
  progressiveFrameId = null
}

function syncProgressiveWindow() {
  if (frozenVisibleRange.value) return

  // 列表缩短后先裁剪历史渐进窗口；追加数据时仍按批次继续渲染
  progressiveStartIndex.value = clamp(progressiveStartIndex.value, 0, props.items.length)
  progressiveEndIndex.value = clamp(progressiveEndIndex.value, 0, props.items.length)

  const range = calculatedVisibleRange.value
  const viewportRange = calculatedViewportRange.value
  const overlapsViewport =
    progressiveEndIndex.value > viewportRange.startIndex && progressiveStartIndex.value < viewportRange.endIndex

  if (!overlapsViewport) {
    progressiveStartIndex.value = viewportRange.startIndex
    progressiveEndIndex.value = viewportRange.endIndex
  } else {
    progressiveStartIndex.value = clamp(progressiveStartIndex.value, range.startIndex, viewportRange.startIndex)
    progressiveEndIndex.value = clamp(progressiveEndIndex.value, viewportRange.endIndex, range.endIndex)
  }

  const initialEndIndex = Math.min(
    range.endIndex,
    Math.max(
      viewportRange.endIndex,
      Math.ceil((viewportRange.startIndex + safeInitialCount.value) / columnCount.value) * columnCount.value,
    ),
  )
  progressiveEndIndex.value = Math.max(progressiveEndIndex.value, initialEndIndex)
}

/** 渐进挂载：每帧把窗口向目标推一批（整行取整），推完为止 */
function queueProgressiveRender() {
  if (
    typeof window === 'undefined' ||
    !mounted ||
    progressiveFrameId !== null ||
    frozenVisibleRange.value
  ) {
    return
  }

  const range = renderedVisibleRange.value
  const targetRange = visibleRange.value
  if (range.endIndex >= targetRange.endIndex && range.startIndex <= targetRange.startIndex) {
    return
  }

  progressiveFrameId = window.requestAnimationFrame(() => {
    progressiveFrameId = null
    const batchRows = Math.max(1, Math.floor(safeBatchSize.value / columnCount.value))
    const batchItems = batchRows * columnCount.value

    if (range.endIndex < targetRange.endIndex) {
      progressiveEndIndex.value = Math.min(targetRange.endIndex, range.endIndex + batchItems)
    } else {
      progressiveStartIndex.value = Math.max(targetRange.startIndex, range.startIndex - batchItems)
    }
    queueProgressiveRender()
  })
}

function adjustScrollTop(delta: number) {
  if (!scrollTarget || Math.abs(delta) < 0.5) return

  if (scrollTarget === window) {
    window.scrollBy({ behavior: 'auto', top: delta })
  } else {
    ;(scrollTarget as HTMLElement).scrollTop += delta
  }
}

// ── 测高缓存维护 ──

function pruneMeasurements() {
  const keys = new Set(itemKeys.value)
  let changed = false

  Array.from(itemHeights.keys()).forEach(key => {
    if (!keys.has(key)) {
      itemHeights.delete(key)
      changed = true
    }
  })

  Array.from(keyElements.entries()).forEach(([key, element]) => {
    if (!keys.has(key)) {
      itemResizeObserver?.unobserve(element)
      observedElements.delete(element)
      keyElements.delete(key)
    }
  })

  Array.from(itemRefCallbacks.keys()).forEach(key => {
    if (!keys.has(key)) itemRefCallbacks.delete(key)
  })

  if (changed) heightVersion.value += 1
}

function preservesLeadingKeys(nextKeys: ItemKey[], previousKeys: ItemKey[] = []) {
  if (!previousKeys.length || !nextKeys.length) return false

  const sharedLength = Math.min(nextKeys.length, previousKeys.length)
  for (let index = 0; index < sharedLength; index += 1) {
    if (nextKeys[index] !== previousKeys[index]) return false
  }
  return true
}

function hasSameKeySet(nextKeys: ItemKey[], previousKeys: ItemKey[] = []) {
  if (nextKeys.length !== previousKeys.length) return false
  const previousKeySet = new Set(previousKeys)
  return previousKeySet.size === nextKeys.length && nextKeys.every(key => previousKeySet.has(key))
}

function syncMeasurementsForItems(nextKeys: ItemKey[], previousKeys: ItemKey[] = []) {
  if (!preservesLeadingKeys(nextKeys, previousKeys) && !hasSameKeySet(nextKeys, previousKeys) && itemHeights.size) {
    itemHeights.clear()
    heightVersion.value += 1
  }
  pruneMeasurements()
}

function invalidateMeasurementsForLayoutChange() {
  const nextColumnCount = columnCount.value
  const nextColumnWidth = columnWidth.value

  if (lastMeasuredColumnCount === nextColumnCount && Math.abs(lastMeasuredColumnWidth - nextColumnWidth) < 1) {
    return
  }

  lastMeasuredColumnCount = nextColumnCount
  lastMeasuredColumnWidth = nextColumnWidth

  if (!itemHeights.size) return

  itemHeights.clear()
  heightVersion.value += 1
}

// ── 生命周期 ──

onMounted(() => {
  mounted = true
  documentOverlayLocked = isDocumentOverlayLocked()
  scrollTarget = findScrollTarget()
  addScrollListener(scrollTarget)

  if (trackRef.value?.clientWidth) syncLayoutWidth()

  resizeObserver = new ResizeObserver(queueLayoutSync)
  if (trackRef.value) resizeObserver.observe(trackRef.value)

  if (typeof MutationObserver !== 'undefined') {
    overlayLockObserver = new MutationObserver(handleOverlayLockChange)
    overlayLockObserver.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ['class'],
    })
  }

  window.addEventListener('resize', handleWindowResize, { passive: true })

  queueLayoutSync()
  queueProgressiveRender()
})

onActivated(() => {
  mounted = true
  refreshScrollTarget()
  queueLayoutSync()
  queueProgressiveRender()
  requestAnimationFrame(queueLayoutSync)
})

onDeactivated(() => {
  mounted = false
  cancelProgressiveRender()
  removeScrollListener(scrollTarget)
  scrollTarget = null
})

onUnmounted(() => {
  mounted = false
  removeScrollListener(scrollTarget)
  scrollTarget = null

  window.removeEventListener('resize', handleWindowResize)
  resizeObserver?.disconnect()
  resizeObserver = null
  itemResizeObserver?.disconnect()
  itemResizeObserver = null
  overlayLockObserver?.disconnect()
  overlayLockObserver = null

  if (layoutFrameId !== null) {
    window.cancelAnimationFrame(layoutFrameId)
    layoutFrameId = null
  }

  if (scrollFrameId !== null) {
    window.cancelAnimationFrame(scrollFrameId)
    scrollFrameId = null
  }

  cancelProgressiveRender()
})

watch(
  itemKeys,
  (nextKeys, previousKeys) => {
    if (!preservesLeadingKeys(nextKeys, previousKeys) && !hasSameKeySet(nextKeys, previousKeys)) {
      cancelProgressiveRender()
      progressiveStartIndex.value = 0
      progressiveEndIndex.value = 0
    }
    syncMeasurementsForItems(nextKeys, previousKeys)
    syncProgressiveWindow()
    queueLayoutSync()
    queueProgressiveRender()
  },
  { immediate: true },
)

watch([columnCount, columnWidth], () => {
  cancelProgressiveRender()
  invalidateMeasurementsForLayoutChange()
  syncProgressiveWindow()
  queueViewportSync()
  queueProgressiveRender()
})

watch([calculatedViewportRange, calculatedVisibleRange], () => {
  cancelProgressiveRender()
  syncProgressiveWindow()
  queueProgressiveRender()
})
</script>

<template>
  <div ref="containerRef" class="sdas-pcg">
    <div ref="trackRef" class="sdas-pcg-track">
      <div
        v-if="topSpacerHeight > 0"
        class="sdas-pcg-spacer"
        :style="{ blockSize: `${topSpacerHeight}px` }"
        aria-hidden="true"
      />
      <div v-if="visibleCells.length > 0" class="sdas-pcg-grid" :style="gridStyle">
        <div
          v-for="cell in visibleCells"
          :key="cell.key"
          :ref="getItemRef(cell.key)"
          class="sdas-pcg-item"
          :data-progressive-grid-index="cell.index"
        >
          <slot :item="cell.item" :index="cell.index" />
        </div>
      </div>
      <div
        v-if="bottomSpacerHeight > 0"
        class="sdas-pcg-spacer"
        :style="{ blockSize: `${bottomSpacerHeight}px` }"
        aria-hidden="true"
      />
    </div>
  </div>
</template>

<style scoped>
.sdas-pcg {
  inline-size: 100%;
}

.sdas-pcg-track {
  inline-size: 100%;
  min-block-size: 1px;
  /* 占位符高度变化时不许浏览器做滚动锚定 —— 高度是我们自己管的 */
  overflow-anchor: none;
}

.sdas-pcg-grid {
  display: grid;
}

.sdas-pcg-item {
  inline-size: 100%;
  min-inline-size: 0;
}

/* 卡片撑满格子（与宿主同款）：海报 2:3 决定行高，卡片内容不会矮于它 */
.sdas-pcg-item > :deep(*) {
  block-size: 100%;
  inline-size: 100%;
}
</style>
