<template>
  <!-- ⚠️ VHover 的鼠标事件在插槽的 props 里，必须 v-bind 到包裹元素上，否则不会悬停 -->
  <v-hover v-slot="{ isHovering, props: hoverProps }">
    <div v-bind="hoverProps" class="sdas-hover-area">
      <v-card
        :ripple="false"
        class="app-hover-lift-card outline-none ring-gray-500 media-card sdas-card"
        :class="{
          'app-hover-lift-card--hovering': isHovering,
          'ring-1': loaded,
        }"
        @click="emit('open', work)"
      >
        <!-- 海报：恒 2:3 -->
        <v-img
          v-if="work.poster"
          :src="proxyImage(work.poster)"
          :aspect-ratio="2 / 3"
          cover
          class="object-cover aspect-w-2 aspect-h-3"
          @load="emit('poster', work.key)"
          @error="emit('poster', work.key)"
        >
          <template #placeholder>
            <div class="sdas-poster-skeleton" />
          </template>
        </v-img>
        <div v-else class="sdas-poster-empty d-flex align-center justify-center">
          <v-icon icon="mdi-movie-open-outline" size="56" color="medium-emphasis" />
        </div>

        <!-- 短剧徽标（左上）：VChip 样式与宿主 MediaCard 同款 -->
        <v-chip
          v-show="loaded"
          variant="elevated"
          size="small"
          class="absolute left-2 top-2 bg-opacity-80 text-white font-bold border-purple-600 bg-purple-600"
        >
          短剧
        </v-chip>
        <!-- 右上：已入库 = 绿色圆形勾（探索页作品卡 MediaCard 的 ExistIcon 同款，
             DOM 与显隐条件照抄：勾只在**未悬停**时显示，悬停浮层展开时换评分角标显示）；
             与评分角标互斥（已入库且未悬停 → 只显示勾）；
             「已入库」判定与宿主媒体详情页同源，未知（缺字段）时不显示 -->
        <div v-show="loaded" class="absolute top-0 right-0 p-2">
          <div
            v-if="work.in_library === true && !isHovering"
            class="pointer-events-none z-40 flex items-center"
            title="这部作品已在 MoviePilot 媒体库中（与媒体详情页的判定一致）"
          >
            <div
              class="relative inline-flex whitespace-nowrap rounded-full border-gray-700 font-semibold leading-5 ring-gray-700"
            >
              <div
                class="rounded-full bg-opacity-80 w-5 border p-0 bg-green-500 border-green-400 ring-green-400 text-green-100"
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  viewBox="0 0 20 20"
                  fill="currentColor"
                  aria-hidden="true"
                >
                  <path
                    fill-rule="evenodd"
                    d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.857-9.809a.75.75 0 00-1.214-.882l-3.483 4.79-1.88-1.88a.75.75 0 10-1.06 1.061l2.5 2.5a.75.75 0 001.137-.089l4-5.5z"
                    clip-rule="evenodd"
                  />
                </svg>
              </div>
            </div>
          </div>
          <v-chip
            v-else-if="Number(work.vote) > 0"
            variant="elevated"
            size="small"
            class="bg-opacity-80 text-white font-bold border-purple-600 bg-purple-600"
          >
            {{ Number(work.vote).toFixed(1) }}
          </v-chip>
        </div>

        <!-- 右下来源图标：探索页 MediaCard 同款（VAvatar + 来源 logo，悬停时隐藏）；
             短剧作品来源恒为 duanju（短剧百科），用百科插件图标作 logo -->
        <v-avatar
          v-if="!isHovering"
          v-show="loaded"
          size="24"
          variant="plain"
          density="compact"
          tile
          class="absolute bottom-1 right-1"
        >
          <v-img
            cover
            src="https://raw.githubusercontent.com/m215owen/MoviePilot-Plugins/main/icons/ShortDramaBaikeSource.png"
            class="shadow-lg"
          />
        </v-avatar>

        <!-- 悬停浮层：年份 / 标题 / 简介 / 按钮排（与宿主 MediaCard 同构：左搜索右订阅） -->
        <div
          v-if="isHovering"
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
               IconBtn 是宿主的 Vuetify 全局别名（icon + variant:text + VIcon size 24），
               联邦模块拿不到别名，用 v-btn 复刻同款 props：icon + text + 图标 24px -->
          <div class="flex align-center justify-between">
            <v-btn icon variant="text" size="small" title="搜索资源" @click.stop="emit('search', work)">
              <v-icon size="24" color="white">mdi-magnify</v-icon>
            </v-btn>
            <v-spacer />
            <v-btn
              icon
              variant="text"
              size="small"
              :color="subscribed ? 'error' : 'white'"
              :title="subscribed ? '已订阅' : '加入订阅'"
              @click.stop="emit('subscribe', work)"
            >
              <v-icon size="24" :color="subscribed ? 'error' : 'white'">
                {{ subscribed ? 'mdi-heart' : 'mdi-heart-outline' }}
              </v-icon>
            </v-btn>
          </div>
        </div>
      </v-card>
    </div>
  </v-hover>
</template>

<script setup lang="ts">
import { proxyImage } from './api'
import type { WorkItem } from './types'

/** 作品墙卡片（与宿主探索页 MediaCard 同款）：主墙与搜索结果共用 */
const props = defineProps<{
  work: WorkItem
  /** 海报是否已加载完（加载完才亮 ring 和角标，与探索页一致） */
  loaded: boolean
  /** 是否已在系统订阅里（订阅爱心状态） */
  subscribed: boolean
}>()

const emit = defineEmits<{
  (e: 'poster', key: string): void
  (e: 'open', work: WorkItem): void
  (e: 'search', work: WorkItem): void
  (e: 'subscribe', work: WorkItem): void
}>()

/** 悬停浮层背景（与探索页 MediaCard 逐字相同） */
const OVERLAY_STYLE = {
  background: 'linear-gradient(rgba(45, 55, 72, 40%) 0%, rgba(45, 55, 72, 90%) 100%)',
}

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

/* 海报骨架：与宿主 .media-card-placeholder 同一口径 */
.sdas-poster-skeleton {
  inline-size: 100%;
  block-size: 100%;
  background: rgba(var(--v-theme-on-surface), 0.08);
}

.sdas-poster-empty {
  aspect-ratio: 2 / 3;
  inline-size: 100%;
  background: rgba(var(--v-theme-on-surface), 0.08);
}

/* 悬停浮层里的文字（对应宿主 .media-card-title / .media-card-overview） */
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
