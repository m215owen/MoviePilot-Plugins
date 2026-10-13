<template>
  <div>
    <div v-if="!works.length" class="text-medium-emphasis text-body-2 py-4 text-center">
      {{ emptyText || '暂无作品数据' }}
    </div>

    <div v-else class="sdas-grid">
      <v-card v-for="work in works" :key="work.key" variant="outlined" class="sdas-card">
        <div class="sdas-poster">
          <v-img :src="proxyImage(work.poster)" :aspect-ratio="2 / 3" cover class="sdas-poster-img">
            <template #placeholder>
              <div class="sdas-poster-ph">
                <v-icon icon="mdi-image-outline" size="22" />
              </div>
            </template>
            <template #error>
              <div class="sdas-poster-ph">
                <v-icon icon="mdi-movie-open-off-outline" size="22" />
              </div>
            </template>
          </v-img>
          <!-- 状态徽标：本页是「演员全部作品 + 当前状态」的看板，所以每个状态都标出来 -->
          <v-chip
            size="x-small"
            :color="statusOf(work).color"
            variant="flat"
            class="sdas-badge sdas-badge-left"
            :title="statusOf(work).title"
          >
            {{ statusOf(work).text }}
          </v-chip>
          <!-- 来源徽标：豆瓣 / TMDB，两源并集是本插件的发现口径 -->
          <v-chip
            v-if="work.source"
            size="x-small"
            variant="flat"
            class="sdas-badge sdas-badge-right"
            :title="`作品信息来自 ${sourceLabel(work.source)}`"
          >
            {{ sourceLabel(work.source) }}
          </v-chip>
        </div>

        <v-card-text class="pa-2 pb-1 sdas-body">
          <div class="sdas-card-title" :title="work.alt_title || work.title">{{ work.title }}</div>
          <div class="sdas-meta">
            <v-chip size="x-small" variant="tonal" label>{{ work.type || '未分类' }}</v-chip>
            <span v-if="work.year" class="sdas-dim">{{ work.year }}</span>
            <span v-if="work.vote" class="sdas-dim sdas-vote">
              <v-icon icon="mdi-star" size="11" color="amber" />{{ Number(work.vote).toFixed(1) }}
            </span>
          </div>
          <div v-if="work.actor" class="sdas-actors" :title="work.actor">
            <v-icon icon="mdi-account-outline" size="11" />
            <span class="sdas-actors-text">{{ work.actor }}</span>
          </div>
          <div v-if="work.torrent_title" class="sdas-dim sdas-source" :title="work.torrent_title">
            {{ work.torrent_title }}
          </div>
        </v-card-text>

        <v-card-actions class="pa-2 pt-0 sdas-actions">
          <v-btn
            size="small"
            class="sdas-sub-btn"
            :color="statusOf(work).color"
            :variant="actable(work) ? 'flat' : 'tonal'"
            :prepend-icon="statusOf(work).icon"
            :loading="pendingKey === work.key"
            :disabled="!actable(work)"
            :title="statusOf(work).title"
            @click="emit('subscribe', work)"
          >
            {{ statusOf(work).action }}
          </v-btn>
          <v-btn
            v-if="detailHref(work)"
            size="small"
            variant="text"
            icon="mdi-open-in-new"
            title="在 MoviePilot 中打开媒体详情（新标签页）"
            :href="detailHref(work)"
            target="_blank"
            rel="noopener"
          />
          <v-btn
            v-if="resourceHref(work)"
            size="small"
            variant="text"
            icon="mdi-magnify"
            title="到 MoviePilot 的资源搜索页按剧名搜一遍（人工复核）"
            :href="resourceHref(work)"
            target="_blank"
            rel="noopener"
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
 * 与「豆瓣演员订阅」的作品墙同形：海报 + 标题 + 元信息 + 一行操作按钮，
 * 视觉与交互保持一致，这样两个插件之间切换时不用重新适应。
 * 只负责渲染与事件抛出，订阅的后端交互由父组件完成。
 *
 * 本插件比豆瓣多一层信息：每张卡片要表达**这部剧当前处理到哪一步**
 * （待订阅 / 冷却中 / 已下载 / 已整理），因此海报上常驻一个状态徽标。
 * 海报统一经宿主图片代理加载（豆瓣 CDN 有防盗链）。
 */
import { mediaPageUrl, proxyImage, resourceSearchUrl } from './api'
import type { WorkItem } from './types'

const props = withDefaults(
  defineProps<{
    /** 待渲染的作品列表 */
    works: WorkItem[]
    /** 正在提交下载的作品键（用于显示按钮 loading） */
    pendingKey?: string
    /** 空列表时的提示文案 */
    emptyText?: string
    /** 插件配置里的搜索站点，用于「搜索资源」深链（留空则用宿主自己的默认站点） */
    sites?: number[]
  }>(),
  { sites: () => [] }
)

const emit = defineEmits<{
  (e: 'subscribe', work: WorkItem): void
}>()

/** 发现来源 → 展示名 */
function sourceLabel(source?: string): string {
  if (source === 'tmdb') return 'TMDB'
  if (source === 'douban') return '豆瓣'
  return '未知'
}

/** 只有还没处理过的作品才允许点「订阅」 */
function actable(work: WorkItem): boolean {
  return work.state === 'pending' || work.state === 'cooling'
}

/** 状态 → 徽标与按钮的文案 / 配色 / 说明（口径与后端 `_work_rows` 一致） */
function statusOf(work: WorkItem): {
  text: string
  action: string
  color: string
  icon: string
  title: string
} {
  if (work.state === 'organized') {
    return {
      text: '已整理',
      action: '已入库',
      color: 'success',
      icon: 'mdi-folder-check-outline',
      title: work.time ? `已下载并整理入库（${work.time}）` : '已下载并整理入库',
    }
  }
  if (work.state === 'downloaded') {
    return {
      text: '已下载',
      action: '已下载',
      color: 'info',
      icon: 'mdi-download-outline',
      title: work.torrent_title
        ? `已提交下载：${work.torrent_title}${work.site_name ? ` @ ${work.site_name}` : ''}（等待整理）`
        : '已提交下载，等待整理入库',
    }
  }
  if (work.state === 'cooling') {
    return {
      text: '冷却',
      action: '重试',
      color: 'warning',
      icon: 'mdi-refresh',
      title: `站点暂时没搜到资源，${work.remaining_minutes || 0} 分钟后可再试（也可现在手动重搜一次）`,
    }
  }
  return {
    text: '待订阅',
    action: '订阅',
    color: 'primary',
    icon: 'mdi-plus',
    title: '立即按剧名到站点搜索并择优下载一条',
  }
}

/**
 * 「详情」按钮的去向：MoviePilot 自带的媒体详情页。
 *
 * 宿主详情页**强依赖媒体类型**（中文的 电影 / 电视剧），拿到类型才给入口，
 * 否则点开是个空壳，不如不显示。
 */
function detailHref(work: WorkItem): string {
  if (!String(work.type || '').trim()) return ''
  return mediaPageUrl(work)
}

/** 「搜索资源」按钮：跳宿主资源搜索页，带上插件配置的站点 */
function resourceHref(work: WorkItem): string {
  return resourceSearchUrl(work.title, props.sites)
}
</script>

<style scoped>
/* 仅使用 scoped 样式；不要编写会全局生效的选择器（组件库类名、html、body、:root） */
.sdas-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(134px, 1fr));
  gap: 12px;
}

.sdas-card {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.sdas-poster {
  position: relative;
  background-color: rgba(128, 128, 128, 0.08);
}

.sdas-poster-img {
  width: 100%;
}

.sdas-poster-ph {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;
  opacity: 0.45;
}

.sdas-badge {
  position: absolute;
  top: 6px;
}

.sdas-badge-left {
  left: 6px;
}

.sdas-badge-right {
  right: 6px;
}

.sdas-body {
  flex: 1 1 auto;
}

.sdas-card-title {
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

.sdas-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 6px;
  flex-wrap: wrap;
}

.sdas-dim {
  font-size: 0.72rem;
  opacity: 0.75;
}

.sdas-vote {
  display: inline-flex;
  align-items: center;
  gap: 2px;
}

/* 出演演员：合并视图下代替按演员分组，因此需要能一眼看到 */
.sdas-actors {
  display: flex;
  align-items: center;
  gap: 3px;
  margin-top: 4px;
  font-size: 0.7rem;
  opacity: 0.85;
  min-width: 0;
}

.sdas-actors-text {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 已下载的剧显示种子原名（多为拼音），方便回下载器里找 */
.sdas-source {
  margin-top: 2px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sdas-actions {
  display: flex;
  align-items: center;
  gap: 4px;
}

.sdas-sub-btn {
  flex: 1 1 auto;
}
</style>
