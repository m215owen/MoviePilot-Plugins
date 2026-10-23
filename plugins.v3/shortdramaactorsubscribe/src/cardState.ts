import { ref } from 'vue'

/**
 * 卡片之间共享的交互状态。
 *
 * 宿主 `MediaCard.vue` 把这两样放在 SFC 的模块作用域里（`<script>` 块 + 自动导入）；
 * 联邦工程没有自动导入，两块 `<script>` 都显式 import `vue` 会撞成重复标识符，
 * 所以单独放一个模块 —— 语义与宿主完全一致，都在组件实例之外共享。
 *
 * ── 1. 触摸端的「点开详情层」归属 ──
 * 桌面端靠悬停展开浮层，点一下即进详情；触摸端没有 hover，所以第一次点只展开浮层、
 * 第二次点才进详情（否则一碰就跳走，看不到简介与两个按钮）。一次只允许一张卡处于
 * 展开态，所以这个 id 必须跨组件实例共享。
 */
export const activeTouchCardId = ref<number | null>(null)

let cardIdSeed = 0

/** 给每张卡片分配一个模块内唯一的交互身份 */
export function nextCardId(): number {
  cardIdSeed += 1
  return cardIdSeed
}

/**
 * ── 2. 海报「已经展示过」的登记表 ──
 * 分页追加 / 换筛选重建卡片时，同一张海报会再走一遍 `v-img`；若还淡入一次就会闪一下
 * （浏览器缓存里图像是瞬到的）。首次看到才淡入，之后直接显示 —— 宿主
 * `mediaPosterPresentationCache` 的等价物。
 */
export const revealedPosters = new Set<string>()
