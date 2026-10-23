<template>
  <!--
    演员卡（2026-10-18 改版：**整张卡就是演员照片**，唯一按钮是右上角爱心）。

    与旧版的区别：
      · 卡面不再「100px 圆形头像 + 下方文字」，而是 2:3 的**完整图片**铺满卡面
        （没有图时退回人形占位）；
      · 姓名与身份压在底部渐变上（与作品卡同一套阅读顺序：先认人、再看数据）；
      · 按钮只剩一枚**右上角爱心**（实心红 = 已关注，空心 = 未关注），
        百科页入口与悬停浮层一并去掉 —— 点卡片本身就是进详情。
  -->
  <v-hover v-slot="{ isHovering, props: hoverProps }">
    <div v-bind="hoverProps" class="sdas-hover-area">
      <v-card
        :ripple="false"
        class="app-hover-lift-card outline-none sdas-person-card"
        :class="{ 'app-hover-lift-card--hovering': isHovering }"
        @click="emit('open')"
      >
        <div class="sdas-person-body">
          <!-- 整张卡 = 一张 2:3 的图 -->
          <v-img
            v-if="item.profile && !imgFailed"
            class="sdas-person-photo"
            :src="displaySrc"
            cover
            @load="onAvatarLoad"
            @error="onAvatarError"
          />
          <div v-else class="sdas-person-photo sdas-person-photo--empty">
            <v-icon size="56" color="medium-emphasis">mdi-account-outline</v-icon>
          </div>

          <!--
            底部渐变 + 两栏（2026-10-18 用户口径）：
              左 = 姓名 + 「N 部作品」，**常显**；
              右 = 粉丝 / 获赞，**各占一行**、右对齐，悬停才淡入。
            「女演员 / 男演员」这类职业性别标签不再显示（没有信息量）。
          -->
          <div class="sdas-person-caption">
            <div class="sdas-person-left">
              <div class="sdas-person-name">{{ item.name }}</div>
              <!-- 角色 / 职务（只有作品详情的演员阵容传）：常显，压在最上面一行副信息 -->
              <div v-if="role" class="sdas-person-role">{{ role }}</div>
              <div v-if="worksLine" class="sdas-person-meta">{{ worksLine }}</div>
            </div>
            <div v-if="statLines.length" class="sdas-person-more sdas-person-stats">
              <div v-for="line in statLines" :key="line">{{ line }}</div>
            </div>
          </div>

          <!--
            订阅全部作品（2026-10-19 用户口径）：只对**演员**开放（导演 / 编剧的作品
            不是短剧订阅的语义），所以由父组件显式传 `subscribe-all` 才渲染。
            位置在左上角，与右上角爱心同一条「悬停才显」的规则 —— 静止态卡面仍然只有照片。
          -->
          <v-btn
            v-if="subscribeAll"
            class="sdas-person-suball"
            variant="flat"
            size="small"
            density="compact"
            :loading="subscribeAllBusy"
            :disabled="subscribeAllBusy"
            title="把这名演员的全部作品提交给订阅系统"
            @click.stop="emit('subscribe-all')"
          >
            <v-icon size="18" start>mdi-playlist-plus</v-icon>
            <span class="sdas-person-suball-text">订阅全部</span>
          </v-btn>

          <!-- 唯一的按钮：右上角爱心 -->
          <v-btn
            class="sdas-person-like"
            icon
            variant="text"
            size="small"
            :loading="busy"
            :title="added ? '取消关注（移出关注列表）' : '关注（加入关注列表）'"
            @click.stop="emit('toggle')"
          >
            <v-icon size="22" :color="added ? 'error' : 'white'">
              {{ added ? 'mdi-heart' : 'mdi-heart-outline' }}
            </v-icon>
          </v-btn>
        </div>
      </v-card>
    </div>
  </v-hover>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'
import { proxyImage, retryProxyImage } from './api'
import type { ActorCandidate } from './types'

const props = defineProps<{
  item: ActorCandidate
  /** 是否已在关注列表（决定右上角爱心是实心还是空心） */
  added?: boolean
  /**
   * 角色名 / 职务（只有**作品详情的演员阵容**传）：演员是「饰演 陈天极」，
   * 导演 / 编剧这一格是他们自己的身份。演员墙不传，卡片与原来完全一致。
   */
  role?: string
  /** 关注 / 取消关注请求进行中（按钮转圈） */
  busy?: boolean
  /** 头像已加载完成（父组件的海报加载登记表用） */
  loaded?: boolean
  /**
   * 解析状态，只有「已关注的演员」列表会传：
   * '' 正常 / 'waiting' 暂时没取到作品（会自动重试）/ 'empty' 百科未收录。
   */
  state?: string
  /** 是否显示「订阅全部」按钮（只有演员卡需要；演员阵容里的导演 / 编剧不传） */
  subscribeAll?: boolean
  /** 「订阅全部」请求进行中（按钮转圈并禁用） */
  subscribeAllBusy?: boolean
}>()

const emit = defineEmits<{
  (e: 'open'): void
  /** 百科页入口（旧版浮层里的按钮已去掉，事件保留给父组件的既有监听） */
  (e: 'page'): void
  (e: 'toggle'): void
  (e: 'poster'): void
  /** 订阅全部作品（父组件负责调用后端批量接口与提示） */
  (e: 'subscribe-all'): void
}>()

/** 头像加载失败 → 退回占位（失败不留空框） */
const imgFailed = ref(false)

/** 头像代理地址 + 失败重试次数（宿主图片代理 DNS 偶发失败，见 `retryProxyImage`） */
const avatarSrc = computed(() =>
  props.item.profile ? proxyImage(props.item.profile) : '',
)
const retryCount = ref(0)
const retryTimer = ref<ReturnType<typeof setTimeout> | null>(null)
const displaySrc = computed(() => retryProxyImage(avatarSrc.value, retryCount.value))

function onAvatarLoad(): void {
  imgFailed.value = false
  emit('poster')
}

function onAvatarError(): void {
  // 整墙同时加载时宿主的 DNS 校验可能瞬时失败：隔 700ms 换地址再试两次
  if (retryCount.value < 2 && avatarSrc.value) {
    if (retryTimer.value) clearTimeout(retryTimer.value)
    retryTimer.value = setTimeout(() => {
      retryCount.value += 1
    }, 700)
    return
  }
  imgFailed.value = true
  emit('poster')
}

onBeforeUnmount(() => {
  if (retryTimer.value) clearTimeout(retryTimer.value)
})

/**
 * 左下那行（**常显**）：作品数 +（非演员的）职业 + 解析状态。
 *
 * 2026-10-18 用户口径：
 *   · ``N 部作品`` 常显 —— 它是判断这位演员"料多不多"的唯一依据；
 *   · ``女演员 / 男演员 / 演员`` **不显示** —— 头像＋姓名已经说明是演员，性别无信息量；
 *   · 导演 / 编剧这类**非演员**的职业仍保留（是有效信息）；
 *   · 国籍一律不显示。
 */
const worksLine = computed(() => {
  const parts: string[] = []
  if (props.item.works_count) parts.push(`${props.item.works_count} 部作品`)
  const job = String(props.item.job_title || '').trim()
  if (job && !['演员', '女演员', '男演员', '男', '女'].includes(job)) parts.push(job)
  if (props.state === 'waiting') parts.push('暂未取到作品，会自动重试')
  else if (props.state === 'empty') parts.push('短剧百科未收录')
  return parts.join(' · ')
})

/**
 * 右下那几行：粉丝 / 获赞**各占一行**（用户口径「换行显示」）。
 *
 * 拆成数组而不是拼一串：半栏窄卡里 ``粉丝 14.6万 · 获赞 3845.9万`` 一行放不下，
 * 之前用单行省略会被截掉后半截。返回空数组时整块不渲染。
 */
const statLines = computed(() => {
  const lines: string[] = []
  const followers = formatCount(props.item.followers)
  if (followers) lines.push(`粉丝 ${followers}`)
  const likes = formatCount(props.item.likes)
  if (likes) lines.push(`获赞 ${likes}`)
  return lines
})

/**
 * 数字缩写：站点给的是纯数字（``123456``），卡面位置有限，按「万 / 亿」压缩。
 * 0 / 空值返回空串 —— 卡片上不写「粉丝 0」。
 */
function formatCount(value?: number): string {
  const num = Number(value || 0)
  if (!num) return ''
  if (num >= 100000000) return `${(num / 100000000).toFixed(1)}亿`
  if (num >= 10000) return `${(num / 10000).toFixed(1)}万`
  return String(num)
}
</script>

<style scoped>
.sdas-hover-area {
  inline-size: 100%;
}

.sdas-person-card {
  cursor: pointer;
  overflow: hidden;
}

/* 卡面：2:3（padding-block-end 150%），整块交给图片 */
.sdas-person-body {
  position: relative;
  padding-block-end: 150%;
  overflow: hidden;
  background-image: linear-gradient(
    45deg,
    rgba(var(--v-theme-background), 0.3),
    rgba(var(--v-theme-surface), 0.3) 60%
  );
}

.sdas-person-photo {
  position: absolute;
  inset: 0;
  inline-size: 100%;
  block-size: 100%;
}

.sdas-person-photo--empty {
  display: flex;
  align-items: center;
  justify-content: center;
}

/*
 * 底部文字：**姓名常显**（2026-10-18 用户口径），身份行与粉丝/获赞**悬停才显**。
 *
 * 静止态只垫一层很淡的渐变 + 文字阴影 —— 名字在任何照片上都读得清，
 * 又不会把整张卡压暗；悬停时渐变加深、更多信息淡入。
 */
.sdas-person-caption {
  position: absolute;
  inset-inline: 0;
  inset-block-end: 0;
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 8px;
  padding: 22px 10px 9px;
  color: #fff;
  background: linear-gradient(
    to top,
    rgba(15, 20, 28, 0.62) 0%,
    rgba(15, 20, 28, 0.18) 55%,
    transparent 100%
  );
  transition: background-color 0.15s ease;
}

.sdas-person-body:hover .sdas-person-caption {
  background: linear-gradient(
    to top,
    rgba(15, 20, 28, 0.88) 0%,
    rgba(15, 20, 28, 0.55) 55%,
    transparent 100%
  );
}

/*
 * 数据行（粉丝 / 获赞）：**悬停才显**（2026-10-18 用户口径「不常显」）。
 *
 * ⚠️ 透明度只由这一个类管 —— 之前 `.sdas-person-stats` 里又写了一次 `opacity: .82`，
 * 它在本文件里排在后面、优先级相同，直接把这里的 `0` 覆盖掉，于是数据行永远可见。
 * 以后要给右栏调淡，改这里（`.85` 就是悬停时的观感），别再往 stats 里写 opacity。
 */
.sdas-person-more {
  opacity: 0;
  transition: opacity 0.15s ease;
}

.sdas-person-body:hover .sdas-person-more {
  opacity: 0.85;
}

/* 触摸端没有 hover：常显，否则永远看不到这些信息 */
@media (hover: none) {
  .sdas-person-more {
    opacity: 0.85;
  }
}

/* 角色 / 职务（作品详情的演员阵容）：与作品数同字号、更淡，一行省略 */
.sdas-person-role {
  overflow: hidden;
  margin-top: 1px;
  font-size: 0.75rem;
  line-height: 1.125rem;
  opacity: 0.82;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sdas-person-name {
  overflow: hidden;
  font-size: 0.9375rem;
  font-weight: 700;
  line-height: 1.25;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.45);
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 左栏：姓名 + 「N 部作品」——可收缩，名字过长走省略，不挤走右栏 */
.sdas-person-left {
  flex: 1 1 auto;
  min-width: 0;
}

/*
 * 右栏：粉丝 / 获赞**各占一行**、右对齐（2026-10-18 用户口径「换行显示」）。
 *
 * 宽度由内容决定（`flex: 0 0 auto` + 每行 nowrap）：两行永远完整，不会像
 * 单行时那样被省略号截掉后半截；左栏不够就自己省略。
 */
.sdas-person-stats {
  flex: 0 0 auto;
  text-align: end;
  font-size: 0.6875rem;
  line-height: 1.0625rem;
  white-space: nowrap;
}

.sdas-person-meta {
  display: -webkit-box;
  overflow: hidden;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  margin-top: 2px;
  font-size: 0.75rem;
  line-height: 1.125rem;
  opacity: 0.88;
}

/*
 * 右上角爱心：压在图上，加一层暗色底衬 —— 浅色照片上白色空心心形也看得见。
 *
 * **悬停才显**（2026-10-18 用户口径）：静止态只留照片，卡片墙更干净。
 * 隐藏时同时 `pointer-events: none`，否则会点到看不见的按钮。
 */
.sdas-person-like {
  position: absolute;
  inset-block-start: 4px;
  inset-inline-end: 4px;
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.15s ease;
  background-color: rgba(0, 0, 0, 0.28) !important;
  backdrop-filter: blur(2px);
}

.sdas-person-body:hover .sdas-person-like,
.sdas-person-like:focus-visible {
  opacity: 1;
  pointer-events: auto;
}

/* 触摸端没有 hover：常显，不然这个按钮永远点不到 */
@media (hover: none) {
  .sdas-person-like {
    opacity: 1;
    pointer-events: auto;
  }
}

.sdas-person-like:hover {
  background-color: rgba(0, 0, 0, 0.42) !important;
}

/*
 * 左上角「订阅全部」：与爱心同一条显隐规则（悬停淡入 / 触摸端常显）。
 * 深色半透明底衬 + 白字，浅色照片上也读得清；字号压到 0.75rem，
 * 半栏窄卡里也放得下（爱心在右上，两者不打架）。
 */
.sdas-person-suball {
  position: absolute;
  inset-block-start: 4px;
  inset-inline-start: 4px;
  min-inline-size: 0;
  block-size: 26px;
  padding-inline: 8px;
  font-size: 0.75rem;
  letter-spacing: 0;
  text-transform: none;
  color: #fff !important;
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.15s ease;
  background-color: rgba(0, 0, 0, 0.34) !important;
  backdrop-filter: blur(2px);
}

.sdas-person-body:hover .sdas-person-suball,
.sdas-person-suball:focus-visible {
  opacity: 1;
  pointer-events: auto;
}

/* 触摸端没有 hover：常显，不然这个按钮永远点不到 */
@media (hover: none) {
  .sdas-person-suball {
    opacity: 1;
    pointer-events: auto;
  }
}

.sdas-person-suball:hover {
  background-color: rgba(0, 0, 0, 0.48) !important;
}

.sdas-person-suball-text {
  margin-inline-start: 2px;
  white-space: nowrap;
}
</style>
