<template>
  <div>
    <div v-if="!works.length" class="text-medium-emphasis text-body-2 py-4 text-center">
      {{ emptyText || '暂无作品数据' }}
    </div>

    <div v-else class="das-grid">
      <v-card
        v-for="work in works"
        :key="workKey(work)"
        variant="outlined"
        class="das-card"
      >
        <div class="das-poster">
          <v-img :src="proxyImage(work.poster)" :aspect-ratio="2 / 3" cover class="das-poster-img">
            <template #placeholder>
              <div class="das-poster-ph">
                <v-icon icon="mdi-image-outline" size="22" />
              </div>
            </template>
            <template #error>
              <div class="das-poster-ph">
                <v-icon icon="mdi-movie-open-off-outline" size="22" />
              </div>
            </template>
          </v-img>
          <!-- 「新」只给**演员加入之后**才出现的作品；刚加入演员的历史作品属于基线，不标新 -->
          <v-chip
            v-if="work.is_new"
            size="x-small"
            color="error"
            variant="flat"
            class="das-badge das-badge-left"
            title="该演员加入订阅之后才出现的新作品"
          >
            新
          </v-chip>
          <v-chip
            v-if="isSubscribed(work)"
            size="x-small"
            color="success"
            variant="flat"
            class="das-badge das-badge-right"
          >
            已订阅
          </v-chip>
        </div>

        <v-card-text class="pa-2 pb-1 das-body">
          <div class="das-title" :title="work.title">{{ work.title }}</div>
          <div class="das-meta">
            <v-chip size="x-small" variant="tonal" label>{{ work.type || '未分类' }}</v-chip>
            <span v-if="work.year" class="das-dim">{{ work.year }}</span>
            <span v-if="work.vote" class="das-dim das-vote">
              <v-icon icon="mdi-star" size="11" color="amber" />{{ work.vote.toFixed(1) }}
            </span>
          </div>
          <div v-if="showActors && work.actorNames && work.actorNames.length" class="das-actors" :title="work.actorNames.join(' / ')">
            <v-icon icon="mdi-account-outline" size="11" />
            <span class="das-actors-text">{{ work.actorNames.join(' / ') }}</span>
          </div>
          <div v-if="work.roles && work.roles.length" class="das-dim das-roles">
            {{ work.roles.join(' / ') }}
          </div>
        </v-card-text>

        <v-card-actions class="pa-2 pt-0 das-actions">
          <v-btn
            size="small"
            class="das-sub-btn"
            :color="isSubscribed(work) ? 'error' : 'primary'"
            :variant="isSubscribed(work) ? 'tonal' : 'flat'"
            :prepend-icon="isSubscribed(work) ? 'mdi-close' : 'mdi-plus'"
            :loading="pendingKey === workKey(work)"
            :disabled="busy"
            @click="isSubscribed(work) ? emit('unsubscribe', work) : emit('subscribe', work)"
          >
            {{ isSubscribed(work) ? '取消订阅' : '订阅' }}
          </v-btn>
          <v-btn
            v-if="detailHref(work)"
            size="small"
            variant="text"
            icon="mdi-open-in-new"
            :title="detailTitle(work)"
            :href="detailHref(work)"
            target="_blank"
            rel="noopener"
          />
          <v-btn
            size="small"
            variant="text"
            icon="mdi-eye-off-outline"
            title="忽略这部作品：不再展示，也不会被自动订阅"
            :disabled="busy"
            @click="emit('ignore', work)"
          />
        </v-card-actions>
      </v-card>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * 作品卡片墙（内部复用组件，不作为联邦暴露入口）。
 *
 * 只负责渲染与事件抛出，订阅的后端交互由父组件完成，
 * 这样详情页 / 侧栏全页 / 仪表板可以复用同一套视觉与交互。
 * 海报统一经宿主图片代理加载，绕开豆瓣 CDN 的 Referer 防盗链。
 * 卡片上的「详情」按钮跳宿主自带的媒体详情页（见 `mediaPageUrl`），不再外链豆瓣。
 */
import { mediaPageUrl, proxyImage, workKey } from './api'
import type { ActorWork } from './types'

const props = withDefaults(
  defineProps<{
    /** 待渲染的作品列表 */
    works: ActorWork[]
    /** 已订阅作品的身份键集合 */
    subscribedKeys: string[]
    /** 正在提交订阅的作品键（用于显示按钮 loading） */
    pendingKey?: string
    /** 批量提交进行中，禁用全部按钮 */
    busy?: boolean
    /** 空列表时的提示文案 */
    emptyText?: string
    /** 是否在卡片上显示「出演演员」，合并视图下用它替代按演员分组 */
    showActors?: boolean
  }>(),
  { subscribedKeys: () => [], showActors: true }
)

const emit = defineEmits<{
  (e: 'subscribe', work: ActorWork): void
  (e: 'unsubscribe', work: ActorWork): void
  (e: 'ignore', work: ActorWork): void
}>()

/** 该作品是否已在订阅系统中 */
function isSubscribed(work: ActorWork): boolean {
  return props.subscribedKeys.includes(workKey(work))
}

/**
 * 「详情」按钮的去向：优先走 MoviePilot 自带的媒体详情页
 * （与探索页点进媒体是同一个页面），一眼就能看到识别结果、订阅状态与资源。
 *
 * 宿主详情页强依赖媒体类型，遇到插件没能归类出类型的作品时，
 * 退回豆瓣条目页 —— 有得看总比点开一个空页面强。
 */
function detailHref(work: ActorWork): string {
  if (String(work.type || '').trim()) return mediaPageUrl(work)
  return String(work.url || '').trim() || mediaPageUrl(work)
}

/** 详情按钮的悬停提示：说清点出去会落在哪儿，别让人以为还在插件面板里 */
function detailTitle(work: ActorWork): string {
  return String(work.type || '').trim()
    ? '在 MoviePilot 中打开媒体详情（新标签页）'
    : '宿主未识别出媒体类型，改为打开豆瓣条目（新标签页）'
}
</script>

<style scoped>
/* 仅使用 scoped 样式；不要编写会全局生效的选择器（组件库类名、html、body、:root） */
.das-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(134px, 1fr));
  gap: 12px;
}

.das-card {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.das-poster {
  position: relative;
  background-color: rgba(128, 128, 128, 0.08);
}

.das-poster-img {
  width: 100%;
}

.das-poster-ph {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;
  opacity: 0.45;
}

.das-badge {
  position: absolute;
  top: 6px;
}

.das-badge-left {
  left: 6px;
}

.das-badge-right {
  right: 6px;
}

.das-body {
  flex: 1 1 auto;
}

.das-title {
  font-size: 0.85rem;
  font-weight: 600;
  line-height: 1.25;
  min-height: 2.5em;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  word-break: break-word;
}

.das-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 6px;
  flex-wrap: wrap;
}

.das-dim {
  font-size: 0.72rem;
  opacity: 0.75;
}

.das-vote {
  display: inline-flex;
  align-items: center;
  gap: 2px;
}

.das-roles {
  margin-top: 2px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 出演演员：合并视图下替代按演员分组，因此需要能一眼看到 */
.das-actors {
  display: flex;
  align-items: center;
  gap: 3px;
  margin-top: 4px;
  font-size: 0.7rem;
  opacity: 0.85;
  min-width: 0;
}

.das-actors-text {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.das-actions {
  display: flex;
  align-items: center;
  gap: 4px;
}

.das-sub-btn {
  flex: 1 1 auto;
}
</style>
