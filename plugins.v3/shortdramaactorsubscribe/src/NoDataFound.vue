<template>
  <!--
    空态 —— **照宿主 `src/components/states/NoDataFound.vue` 复刻**
    （探索页 `MediaCardListView` / `PersonCardListView` 的「没有数据」用的就是它：
    超大号错误码 + 数字里的 `0` 换成旋转的胶卷盘 + 三片漂浮的胶片帧 +
    标题下的渐变小横线）。

    宿主那一份的样式在 `<style scoped>` 里（选择器带 `data-v`），联邦元素匹配不上 ⇒
    版式 / 动画 / SVG 全部照搬，类名换成自有 `sdas-*`。SVG 的 path 与圆孔坐标是逐字抄的
    （胶卷盘 6 个镂孔绕中心均匀分布，半径 18、中心距 48）。

    颜色一律用宿主主题变量：`--v-theme-primary`（主色）/ `--v-theme-on-surface`（正文色），
    所以明暗主题下都和探索页同色。
  -->
  <div class="sdas-nodata">
    <!-- 错误码：逐字符渲染，「0」换成胶卷盘 -->
    <div class="sdas-code" role="img" :aria-label="errorCode || '404'">
      <span class="sdas-code-glow" aria-hidden="true" />

      <template v-for="(char, index) in codeChars" :key="index">
        <span v-if="char === '0'" class="sdas-reel-holder" aria-hidden="true">
          <svg class="sdas-reel" viewBox="0 0 200 200" fill="none">
            <circle cx="100" cy="100" r="88" class="sdas-reel-rim" />
            <g class="sdas-reel-holes">
              <circle cx="148" cy="100" r="18" />
              <circle cx="124" cy="141.6" r="18" />
              <circle cx="76" cy="141.6" r="18" />
              <circle cx="52" cy="100" r="18" />
              <circle cx="76" cy="58.4" r="18" />
              <circle cx="124" cy="58.4" r="18" />
            </g>
            <circle cx="100" cy="100" r="11" class="sdas-reel-hub" />
          </svg>
        </span>
        <span v-else class="sdas-code-digit" aria-hidden="true">{{ char }}</span>
      </template>

      <!-- 漂浮的胶片帧装饰 -->
      <span class="sdas-film-chip is-a" aria-hidden="true" />
      <span class="sdas-film-chip is-b" aria-hidden="true" />
      <span class="sdas-film-chip is-c" aria-hidden="true" />
    </div>

    <div class="sdas-nodata-title">{{ errorTitle || '没有数据' }}</div>
    <div v-if="errorDescription" class="sdas-nodata-desc">{{ errorDescription }}</div>

    <!-- 按钮槽位（探索页的「重试」就放这里） -->
    <div v-if="$slots.button" class="sdas-nodata-actions">
      <slot name="button" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  /** 大号错误码；其中的 `0` 会被渲染成旋转的胶卷盘（默认 404） */
  errorCode?: string
  /** 标题（默认「没有数据」，与宿主 i18n 的 common.noData 一致） */
  errorTitle?: string
  /** 副标题说明（留空则不渲染） */
  errorDescription?: string
}>()

/** 逐字符渲染错误码（`0` → 胶卷盘） */
const codeChars = computed(() => (props.errorCode || '404').split(''))
</script>

<style scoped>
.sdas-nodata {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  inline-size: 100%;
  min-block-size: 300px;
  padding-block-start: 3rem;
  text-align: center;
  animation: sdas-rise-in 0.6s ease both;
}

/* ---------- 错误码 ---------- */
.sdas-code {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.06em;
  margin-block: 0 1.5rem;
  font-size: clamp(5rem, 16vw, 9rem);
  font-weight: 800;
  line-height: 1;
  letter-spacing: 0.02em;
}

.sdas-code-digit {
  background: linear-gradient(175deg, rgba(var(--v-theme-primary), 1) 12%, rgba(var(--v-theme-primary), 0.45) 100%);
  background-clip: text;
  -webkit-background-clip: text;
  color: transparent;
  text-shadow: none;
}

/* 背景柔光 */
.sdas-code-glow {
  position: absolute;
  inset: -30% -10%;
  z-index: -1;
  background: radial-gradient(closest-side, rgba(var(--v-theme-primary), 0.16), transparent 70%);
  animation: sdas-breathe 5s ease-in-out infinite;
}

/* ---------- 胶卷盘 ---------- */
.sdas-reel-holder {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  block-size: 0.92em;
  inline-size: 0.92em;
  margin-inline: 0.06em;
}

.sdas-reel {
  block-size: 100%;
  inline-size: 100%;
  animation: sdas-reel-spin 24s linear infinite;
}

.sdas-reel-rim {
  fill: rgba(var(--v-theme-primary), 0.08);
  stroke: rgba(var(--v-theme-primary), 0.9);
  stroke-width: 9;
}

/* 盘面 6 个镂孔：仅用描边，孔内透出背景色 */
.sdas-reel-holes circle {
  stroke: rgba(var(--v-theme-on-surface), 0.5);
  stroke-width: 4;
}

.sdas-reel-hub {
  fill: rgba(var(--v-theme-primary), 0.95);
}

/* ---------- 漂浮胶片帧 ---------- */
.sdas-film-chip {
  position: absolute;
  border: 1.5px solid rgba(var(--v-theme-on-surface), 0.18);
  border-radius: 4px;
  /* 上下齿孔用重复渐变模拟 */
  background-image: repeating-linear-gradient(90deg, transparent 0 6px, rgba(var(--v-theme-on-surface), 0.22) 6px 10px);
  background-position: center top 3px;
  background-repeat: repeat-x;
  background-size: 100% 3px;
  block-size: 14px;
  inline-size: 34px;
  opacity: 0.7;
}

.sdas-film-chip.is-a {
  inset-block-start: -8%;
  inset-inline-start: 6%;
  rotate: -18deg;
  animation: sdas-drift 6s ease-in-out infinite;
}

.sdas-film-chip.is-b {
  inset-block-end: -6%;
  inset-inline-end: 4%;
  rotate: 14deg;
  animation: sdas-drift 7s ease-in-out 1.2s infinite;
}

.sdas-film-chip.is-c {
  inset-block-start: 12%;
  inset-inline-end: -6%;
  rotate: 26deg;
  animation: sdas-drift 8s ease-in-out 2.4s infinite;
}

/* ---------- 文字 ---------- */
.sdas-nodata-title {
  position: relative;
  color: rgba(var(--v-theme-on-surface), 0.95);
  font-size: 1.5rem;
  font-weight: 500;
  margin-block-end: 0.75rem;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 5%);
}

.sdas-nodata-title::after {
  display: block;
  border-radius: 3px;
  background: linear-gradient(90deg, rgba(var(--v-theme-primary), 0.8), rgba(var(--v-theme-primary), 0.2));
  block-size: 3px;
  content: '';
  inline-size: 60px;
  margin-block-start: 0.5rem;
  margin-inline: auto;
}

.sdas-nodata-desc {
  color: rgba(var(--v-theme-on-surface), 0.75);
  font-size: 1rem;
  margin-block-end: 1rem;
  margin-inline: auto;
  max-inline-size: 80%;
}

.sdas-nodata-actions {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
}

/* ---------- 动画 ---------- */
@keyframes sdas-rise-in {
  from {
    opacity: 0;
    transform: translateY(14px);
  }

  to {
    opacity: 1;
    transform: none;
  }
}

@keyframes sdas-breathe {
  0%,
  100% {
    opacity: 0.7;
    transform: scale(1);
  }

  50% {
    opacity: 1;
    transform: scale(1.08);
  }
}

@keyframes sdas-reel-spin {
  to {
    rotate: 360deg;
  }
}

@keyframes sdas-drift {
  0%,
  100% {
    transform: translateY(0);
  }

  50% {
    transform: translateY(-8px);
  }
}

@media (prefers-reduced-motion: reduce) {
  .sdas-nodata,
  .sdas-code-glow,
  .sdas-reel,
  .sdas-film-chip {
    animation: none;
  }
}
</style>
