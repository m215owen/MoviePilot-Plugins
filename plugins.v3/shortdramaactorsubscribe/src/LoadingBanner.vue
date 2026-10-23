<template>
  <!--
    首屏加载态 —— **照宿主 `src/@core/components/LoadingBanner.vue` 复刻**
    （探索页 `MediaCardListView` / `PersonCardListView` 首屏用的就是它：
    4 个主色圆点依次上下跳动）。

    宿主那一份的样式在 `<style scoped>` 里（选择器带 `data-v` 属性），联邦插件
    的元素匹配不上 ⇒ 版式与动画数值在这里逐条照搬，但类名一律换成自有 `sdas-*`
    （联邦 CSS 门禁会把含 `.v-` / `.mdi-` 的选择器整条丢掉，自有前缀才留得住）。

    宿主原本的外层还有 `w-full text-center text-gray-500 text-sm flex flex-col
    items-center my-5` —— 那些是宿主全局的 Tailwind 工具类，这里用自有类名等价写出，
    免得依赖联邦能否吃到 Tailwind。
  -->
  <div class="sdas-loading">
    <div class="sdas-loading-box">
      <div class="sdas-loading-inner">
        <div class="sdas-wave">
          <div class="sdas-wave-dot" />
          <div class="sdas-wave-dot" />
          <div class="sdas-wave-dot" />
          <div class="sdas-wave-dot" />
        </div>
        <div v-if="text" class="sdas-loading-text">{{ text }}</div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * 首屏加载横幅（探索页同款）。
 *
 * 用在「还一张卡片都没铺出来」的那一拍：作品墙首屏、演员页首屏、
 * 搜索两个链路都还没回来、作品详情 / 演员作品页取数中。
 * 已有数据时的翻页加载**不用**它（宿主那边也是空的 `#loading` 插槽）。
 */
defineProps<{
  /** 圆点下面的一行小字（宿主只有传了才渲染） */
  text?: string
}>()
</script>

<style scoped>
.sdas-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  inline-size: 100%;
  margin-block: 1.25rem;
  color: rgb(var(--v-theme-on-surface-variant, 158 158 158));
  font-size: 0.875rem;
  line-height: 1.25rem;
  text-align: center;
}

.sdas-loading-box {
  display: flex;
  align-items: center;
  justify-content: center;
  min-block-size: 20vh;
}

.sdas-loading-inner {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 20px;
}

.sdas-wave {
  display: flex;
  align-items: center;
  block-size: 40px;
  gap: 6px;
}

.sdas-wave-dot {
  border-radius: 50%;
  animation: sdas-wave 1.5s ease-in-out infinite;
  background-color: rgb(var(--v-theme-primary));
  block-size: 8px;
  inline-size: 8px;
}

.sdas-wave-dot:nth-child(1) {
  animation-delay: 0s;
}

.sdas-wave-dot:nth-child(2) {
  animation-delay: 0.2s;
}

.sdas-wave-dot:nth-child(3) {
  animation-delay: 0.4s;
}

.sdas-wave-dot:nth-child(4) {
  animation-delay: 0.6s;
}

@keyframes sdas-wave {
  0%,
  100% {
    transform: translateY(0);
  }

  50% {
    transform: translateY(-15px);
  }
}

.sdas-loading-text {
  color: rgb(var(--v-theme-primary));
  font-size: 0.9rem;
  font-weight: 500;
  letter-spacing: 1px;
}
</style>
