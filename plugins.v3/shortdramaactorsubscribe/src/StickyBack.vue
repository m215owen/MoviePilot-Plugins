<template>
  <!--
    钉在视口的返回键（作品详情 / 演员详情 / 原著详情共用）。

    为什么不能用 `position: sticky`、也不能把 `position: fixed` 留在面板里：

    * 宿主面板容器同时带 **`transform`** 与 **`overflow: hidden`**。sticky 相对**最近的
      滚动祖先**吸附，而那个容器并不滚动（真正滚动的是 window / 更外层），所以 sticky
      完全不生效 —— 表现就是「返回键跟着页面一起滚」。
    * `fixed` 留在面板里则相对该容器定位，同样会跟着滚，还会被裁掉。

    稳妥做法只有一条：**Teleport 到 body**，让 fixed 真正相对视口。

    位置（2026-10-18 用户口径，三轮收敛）：**左上角**，但吸顶下限要压在宿主
    系统搜索栏**下方**（`TOP_FLOOR` ≈ 72px）—— 面板没滚时按钮贴面板自身左上；
    页面滚上去之后按钮钉在 72px 高度，不再盖住宿主顶栏的搜索框。
  -->
  <Teleport to="body">
    <v-btn
      v-if="anchor"
      class="sdas-sticky-back"
      :style="posStyle"
      icon
      variant="text"
      :title="title"
      @click="emit('back')"
    >
      <slot>
        <v-icon size="26">mdi-arrow-left</v-icon>
      </slot>
    </v-btn>
  </Teleport>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'

/**
 * 吸顶下限：宿主顶栏（含系统搜索栏）大致高度 + 余量。
 * 页面滚过头时按钮最多升到这里，不会把搜索栏盖住。
 */
const TOP_FLOOR = 72

const props = defineProps<{
  /** 面板根节点（锚点）：按钮贴着它的左上角摆放 */
  anchor?: HTMLElement | null
  /** 悬停提示 */
  title?: string
}>()

const emit = defineEmits<{ (e: 'back'): void }>()

/** 按钮的视口坐标（每次滚动按锚点位置重算） */
const posStyle = ref<Record<string, string>>({ top: `${TOP_FLOOR}px`, left: '12px' })

/** 滚动 / 布局变化里的重算节流：一帧最多一次 */
let raf = 0

function sync(): void {
  const el = props.anchor
  if (!el) return
  const rect = el.getBoundingClientRect()
  posStyle.value = {
    // 上限跟着面板走（没滚时贴面板左上），下限 TOP_FLOOR 保证不进宿主顶栏
    top: `${Math.max(TOP_FLOOR, Math.round(rect.top + 8))}px`,
    left: `${Math.max(8, Math.round(rect.left + 8))}px`,
  }
}

function onScroll(): void {
  if (raf) return
  raf = requestAnimationFrame(() => {
    raf = 0
    sync()
  })
}

// 捕获阶段挂在 document 上：scroll 不冒泡，这样任意祖先容器滚动都能收到
onMounted(() => {
  sync()
  document.addEventListener('scroll', onScroll, true)
  window.addEventListener('resize', onScroll)
})

onBeforeUnmount(() => {
  document.removeEventListener('scroll', onScroll, true)
  window.removeEventListener('resize', onScroll)
  if (raf) cancelAnimationFrame(raf)
})

watch(() => props.anchor, sync)
</script>

<style scoped>
/* 层级取 1500：高于面板内容，低于 Vuetify 弹窗（~2400）——
   取消订阅确认框开着时不该能隔着弹窗点到它。
   尺寸 48px / 图标 26：2026-10-18 用户口径「按钮太小」→ 放大一号。 */
.sdas-sticky-back {
  position: fixed;
  width: 48px !important;
  height: 48px !important;
  z-index: 1500;
}
</style>
