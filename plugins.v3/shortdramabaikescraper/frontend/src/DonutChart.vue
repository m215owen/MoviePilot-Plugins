<template>
  <!--
    环图（甜甜圈图）组件：概览页的「实体分布」与「缓存分布」共用。

    为什么不用图表库：一个 SVG + `stroke-dasharray` 就够，体积为零，
    颜色、字号全跟宿主主题变量走（不引第三方样式，符合联邦 CSS 约束）。
    数量为 0 的分片不进图 —— 否则会出现长度为 0 的弧和假图例。
  -->
  <div class="sdbs-donut-wrap">
    <svg class="sdbs-donut" viewBox="0 0 140 140" role="img" :aria-label="`${title}饼图`">
      <!-- 底环：全空时也让人看出这是个环，而不是"图坏了" -->
      <circle
        cx="70"
        cy="70"
        :r="RADIUS"
        fill="none"
        stroke="rgba(var(--v-theme-on-surface), 0.08)"
        :stroke-width="THICKNESS"
      />
      <circle
        v-for="slice in slices"
        :key="slice.key"
        cx="70"
        cy="70"
        :r="RADIUS"
        fill="none"
        :stroke="slice.color"
        :stroke-width="THICKNESS"
        :stroke-dasharray="slice.dash"
        :stroke-dashoffset="slice.offset"
        stroke-linecap="butt"
        transform="rotate(-90 70 70)"
      >
        <title>{{ name(slice.key) }} {{ slice.count }} {{ unit }}（{{ slice.ratio }}）</title>
      </circle>
      <text x="70" y="66" text-anchor="middle" class="sdbs-donut-total">{{ total }}</text>
      <text x="70" y="82" text-anchor="middle" class="sdbs-donut-caption">{{ unit }}</text>
    </svg>

    <div class="sdbs-legend">
      <div v-for="slice in slices" :key="slice.key" class="sdbs-legend-row">
        <span class="sdbs-swatch" :style="{ backgroundColor: slice.color }" />
        <span class="sdbs-legend-name">{{ name(slice.key) }}</span>
        <span class="sdbs-legend-value">{{ slice.count }}</span>
        <span class="sdbs-legend-ratio">{{ slice.ratio }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { percent } from './constants'

const props = withDefaults(
  defineProps<{
    /** 分片数据（key + 数量）；数量为 0 的会被忽略 */
    rows: { key: string; count: number }[]
    /** 中心数字的单位文案 */
    unit?: string
    /** 把 key 翻成人话（实体前缀 / region 名 → 中文） */
    name: (key: string) => string
    /** 无障碍标签 */
    title?: string
  }>(),
  { unit: '条', title: '分布' },
)

/** 环半径与环宽（viewBox 140×140，圆心 70,70） */
const RADIUS = 52
const THICKNESS = 18
/** 环周长：dasharray 的总长度基准 */
const CIRCUMFERENCE = 2 * Math.PI * RADIUS

/**
 * 分类配色（**按传入顺序**固定取色）。
 *
 * 同一分类每次刷新颜色一致 —— 不能按"当前数量排序"取色，否则数据一变颜色就换，
 * 看图的人会以为分类变了。
 */
const PALETTE = [
  '#5B8FF9',
  '#61DDAA',
  '#F6BD16',
  '#7262FD',
  '#78D3F8',
  '#F6903D',
  '#9661BC',
  '#008685',
  '#F08BB4',
  '#65789B',
]

/** 参与绘制的总数（0 条分片不算） */
const total = computed(() =>
  props.rows.reduce((sum, row) => sum + Math.max(0, Number(row.count) || 0), 0),
)

/**
 * 环图分段：每条是一个 circle，用 `dasharray` 截取弧长、`dashoffset` 平移起点。
 *
 * `offset` 取负值（`-(已累计比例 × 周长)`）是 SVG 的写法：负偏移等于把起点顺时针推后，
 * 这样各段首尾相接而不用计算每段的起始角。
 */
const slices = computed(() => {
  const rows = props.rows
    .map((row) => ({ key: row.key, count: Math.max(0, Number(row.count) || 0) }))
    .filter((row) => row.count > 0)
  const sum = rows.reduce((acc, row) => acc + row.count, 0)
  if (!sum) return []
  let accumulated = 0
  return rows.map((row, index) => {
    const length = (row.count / sum) * CIRCUMFERENCE
    const offset = -(accumulated / sum) * CIRCUMFERENCE
    accumulated += row.count
    return {
      ...row,
      color: PALETTE[index % PALETTE.length],
      dash: `${length} ${CIRCUMFERENCE}`,
      offset,
      ratio: percent(row.count, sum),
    }
  })
})
</script>
