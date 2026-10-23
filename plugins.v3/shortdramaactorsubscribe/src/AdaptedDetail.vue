<template>
  <!--
    原著详情页（2026-10-18 新增）：作品详情页里点「改编自」进来的**整页**。

    数据全部来自剧集记录里的 `adapted_from`（书名 / 作者 / 字数 / 题材 / 简介 /
    封面 / 原著页地址 / 全部改编作品），所以这一页**零额外请求** —— 父组件把整份
    `AdaptedInfo` 传进来即可。版式与作品详情页同一套：返回条 → 封面 + 标题 +
    副信息 → 简介 →「改编作品」网格（点开进那部剧的详情页）。
  -->
  <div ref="pageRoot" class="sdas-adapted">
    <div class="sdas-adapted-bar">
      <span class="text-body-2 text-medium-emphasis">原著</span>
      <v-spacer />
    </div>

    <!-- 兜底：既没拿到详情数据、兜底请求也没回来时，给一句明确的话，不留白页 -->
    <div v-if="!view.title && loading" class="sdas-adapted-loading">
      <v-progress-circular indeterminate size="22" width="2" />
      <span class="text-body-2 text-medium-emphasis ml-2">正在取原著信息…</span>
    </div>
    <p v-else-if="!view.title" class="sdas-adapted-empty-tip">
      站点没有登记这部剧的原著信息。
    </p>

    <div v-if="view.title" class="sdas-adapted-head">
      <div class="sdas-adapted-cover">
        <v-img
          v-if="view.poster"
          class="sdas-adapted-cover-img"
          :src="proxyImage(view.poster)"
          cover
        />
        <div v-else class="sdas-adapted-cover-empty">
          <v-icon size="48" color="medium-emphasis">mdi-book-open-page-variant-outline</v-icon>
        </div>
      </div>

      <div class="sdas-adapted-meta">
        <h1 class="sdas-adapted-name">{{ view.title }}</h1>
        <div class="sdas-adapted-sub">
          <span v-if="view.author">{{ view.author }}</span>
          <span v-if="view.author && wordsText" class="mx-1">|</span>
          <span v-if="wordsText">{{ wordsText }}</span>
        </div>
        <!-- 题材：站点给的是短标签，做成静态 chip（这一页没有筛选，不需要交互） -->
        <div v-if="view.genres.length" class="sdas-adapted-genres">
          <span v-for="genre in view.genres" :key="genre" class="sdas-adapted-genre">
            {{ genre }}
          </span>
        </div>
      </div>
    </div>

    <template v-if="view.summary">
      <h2 class="sdas-adapted-h2">简介</h2>
      <p class="sdas-adapted-text">{{ view.summary }}</p>
    </template>

    <div class="sdas-adapted-credits">
      <div class="slider-header sdas-adapted-credits-head">
        <span class="slider-title">
          <span>改编作品</span>
          <v-icon icon="mdi-arrow-right-circle-outline" size="18" class="ms-1" />
        </span>
        <v-spacer />
        <span class="text-body-2 text-medium-emphasis">共 {{ works.length }} 部</span>
      </div>

      <GlassMediaBackdrop v-if="works.length">
        <div class="sdas-adapted-grid">
          <WorkCard
            v-for="work in works"
            :key="work.key"
            :work="work"
            :loaded="loadedKeys.has(work.key)"
            :subscribed="subscribedIds.has(work.media_id)"
            @poster="markPoster(work.key)"
            @open="emit('open-work', work)"
            @search="emit('search', work)"
            @subscribe="emit('subscribe', work)"
          />
        </div>
      </GlassMediaBackdrop>
      <p v-else class="sdas-adapted-empty">站点没有登记这本书的改编作品。</p>
    </div>
    <!-- 返回键：钉在视口（面板内 sticky / fixed 都会被宿主的 transform + overflow 吃掉） -->
    <StickyBack :anchor="pageRoot" title="返回" @back="emit('back')" />
  </div>
</template>

<script setup lang="ts">
import StickyBack from './StickyBack.vue'

/** 页面根节点：返回键（`StickyBack`）按它的左上角定位到视口 */
const pageRoot = ref<HTMLElement | null>(null)

import { computed, onMounted, reactive, ref } from 'vue'
import GlassMediaBackdrop from './GlassMediaBackdrop.vue'
import WorkCard from './WorkCard.vue'
import { fetchAdaptedDetail, fetchAdaptedInfo, proxyImage } from './api'
import type { AdaptedInfo } from './api'
import type { PluginApi, WorkItem } from './types'

/**
 * 原著详情页：只做呈现，数据由父组件从剧集记录里带进来（`AdaptedInfo`）。
 *
 * 为什么不做独立接口：站点在**剧集**记录的 `adapted_from` 里已经给了整份原著
 * （含全部改编作品），再为它开一个端点只会多一次站点请求；而这份数据本来就在
 * 打开作品详情时到手了。
 */
const props = defineProps<{
  /** 宿主注入的 axios 实例（兜底取数用） */
  api?: PluginApi
  /** 原著信息（书名 / 作者 / 字数 / 题材 / 简介 / 封面 / 原著页 / 改编作品） */
  novel: AdaptedInfo
  /**
   * 进来时那部**剧集**的 media_id（`duanju:…` / `manju:…`）。
   *
   * 传进来的 `novel` 为空时（详情那边没取到改编数据、或组件被直接挂载）用它
   * 自己向数据源补一次 —— 这一页因此不会出现「打开了但什么都没有」。
   */
  mediaId?: string
  /** 已订阅（系统订阅）的作品 ID 集合，决定作品卡上的爱心状态 */
  subscribedIds?: Set<string>
}>()

const emit = defineEmits<{
  (e: 'back'): void
  (e: 'open-work', work: WorkItem): void
  (e: 'search', work: WorkItem): void
  (e: 'subscribe', work: WorkItem): void
}>()

/** 空壳默认值：模板一律读 `view`，字段缺失也不会炸 */
const EMPTY_INFO: AdaptedInfo = {
  title: '',
  author: '',
  url: '',
  poster: '',
  media_id: '',
  words: 0,
  genres: [],
  summary: '',
  works: [],
}

/** 自取到的原著信息（兜底 / 补全路径用；正常路径直接读 props.novel） */
const local = ref<AdaptedInfo | null>(null)
const loading = ref(false)

/**
 * 页面呈现的数据：父组件传入的为主，`local` 只补**空的那几项**。
 *
 * 为什么要合并而不是整份替换：剧集页的改编区只写得出「本剧的原著」，
 * 作者 / 封面 / 改编作品都可能缺；补全请求回来时不能把父组件已经给的
 * 书名覆盖成空（旧记录甚至没有 `media_id`，那次请求根本不会发）。
 */
const view = computed<AdaptedInfo>(() => {
  const base = props.novel || EMPTY_INFO
  const extra = local.value
  if (!extra) return base
  return {
    title: base.title || extra.title,
    author: base.author || extra.author,
    url: base.url || extra.url,
    poster: base.poster || extra.poster,
    media_id: base.media_id || extra.media_id,
    words: base.words || extra.words,
    genres: base.genres?.length ? base.genres : extra.genres,
    summary: base.summary || extra.summary,
    works: base.works?.length ? base.works : extra.works,
  }
})

onMounted(async () => {
  const novelId = String(props.novel?.media_id || '').trim()
  const mediaId = String(props.mediaId || '').trim()
  // 有两种「不完整」需要补：
  // ① 连书名都没有（详情那边没取到改编数据）→ 按**剧集**身份补一次；
  // ② 有书名但缺改编作品 / 作者（剧集页改编区只给到书名那一版）→ 按**原著**身份补全。
  const needFill = !props.novel?.title || !props.novel?.works?.length
  if (!needFill) return
  if (!novelId && !mediaId) return
  loading.value = true
  try {
    if (novelId) {
      local.value = await fetchAdaptedDetail({ api: props.api }, novelId)
    } else if (!props.novel?.title) {
      local.value = await fetchAdaptedInfo({ api: props.api }, mediaId)
    }
  } finally {
    loading.value = false
  }
})

/** 封面已加载的作品键（WorkCard 据此亮描边与角标，与其它页同一套） */
const loadedKeys = reactive(new Set<string>())

function markPoster(key: string): void {
  loadedKeys.add(key)
}

/** 字数：4896551 → 「489.7 万字」（站点给的是纯数字） */
const wordsText = computed(() => {
  const words = Number(view.value.words || 0)
  if (!words) return ''
  if (words >= 10000) return `约 ${(words / 10000).toFixed(1)} 万字`
  return `${words} 字`
})

/**
 * 改编作品 → 作品卡需要的行。
 *
 * 站点的 `works[]` 只给身份 / 标题 / 海报 / 日期 / 集数 / 题材，卡片要的其余字段
 * 一律给安全默认值（它们只影响排序与角标，这一页不做排序）。
 */
const works = computed<WorkItem[]>(() =>
  (view.value.works || [])
    .filter((item) => item.title)
    .map((item) => ({
      key: `${item.media_id || item.title}|${item.release_date.slice(0, 4)}`,
      title: item.title,
      year: item.release_date.slice(0, 4),
      type: '电视剧',
      media_source: 'djbaike',
      media_id: item.media_id,
      poster: item.poster,
      vote: 0,
      episode_count: item.episodes,
      url: item.url,
      genres: item.genres,
      heat: 0,
      play_count: 0,
      studio: '',
      platform: '',
      kind: '',
      release_date: item.release_date,
      actor: '',
      actor_key: '',
      first_seen: '',
      is_new: false,
    })),
)
</script>

<style scoped>
/*
  ⚠️ 联邦 CSS 门禁会丢掉任何含 `.v-` 的选择器 ⇒ 样式一律自有 `sdas-*` 类名；
  宿主全局类（slider-header / slider-title / text-body-2 / text-medium-emphasis）
  只用 class 属性引用。
*/
.sdas-adapted-loading,
.sdas-adapted-empty-tip {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px 16px;
  margin: 0;
  font-size: 0.875rem;
  opacity: 0.66;
}

.sdas-adapted {
  display: flex;
  flex-direction: column;
  padding: 0 0 24px;
  color: rgb(var(--v-theme-on-surface));
}

/*
 * 返回条：**吸顶**（sticky）。
 *
 * 插件面板没有宿主顶栏 / 浏览器返回，返回键是唯一的退路，不能随内容滚走。
 * 之前作品详情页把它做成左上角绝对定位的浮层（不占排版），滑两屏就够不着了；
 * 改成 sticky 后它占一行、滚到哪都停在顶部。背景给实色，否则下方内容会从它背后透出来。
 */
.sdas-adapted-bar {
  display: flex;
  align-items: center;
  min-height: 32px;
  padding-inline: 12px;
  margin-bottom: 4px;
}

/* 头部：封面 + 标题 / 作者 / 字数 / 题材（窄屏竖排，≥768px 横排） */
.sdas-adapted-head {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.875rem;
  padding-inline: 16px;
  margin: 0.5rem 0 1.25rem;
}

@media (width >= 768px) {
  .sdas-adapted-head {
    flex-direction: row;
    align-items: flex-start;
    gap: 1.25rem;
  }
}

.sdas-adapted-cover {
  flex: 0 0 auto;
  inline-size: 9rem;
  aspect-ratio: 2 / 3;
  overflow: hidden;
  border-radius: 10px;
  background: rgba(var(--v-theme-on-surface), 0.06);
}

.sdas-adapted-cover-img,
.sdas-adapted-cover-empty {
  inline-size: 100%;
  block-size: 100%;
}

.sdas-adapted-cover-empty {
  display: flex;
  align-items: center;
  justify-content: center;
}

.sdas-adapted-meta {
  min-inline-size: 0;
}

.sdas-adapted-name {
  margin: 0;
  font-size: 1.75rem;
  font-weight: 500;
  line-height: 2.25rem;
  text-align: center;
  overflow-wrap: anywhere;
}

@media (width >= 768px) {
  .sdas-adapted-name {
    text-align: left;
  }
}

.sdas-adapted-sub {
  margin-top: 0.25rem;
  font-size: 0.875rem;
  line-height: 1.5rem;
  text-align: center;
  color: rgba(var(--v-theme-on-surface), 0.72);
}

@media (width >= 768px) {
  .sdas-adapted-sub {
    text-align: left;
  }
}

.sdas-adapted-genres {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  justify-content: center;
  margin-top: 0.5rem;
}

@media (width >= 768px) {
  .sdas-adapted-genres {
    justify-content: flex-start;
  }
}

.sdas-adapted-genre {
  padding: 2px 8px;
  border-radius: 4px;
  background: rgba(var(--v-theme-on-surface), 0.08);
  font-size: 0.75rem;
  line-height: 1.25rem;
}

.sdas-adapted-h2 {
  padding-inline: 16px;
  margin: 0.5rem 0 0.25rem;
  font-size: 1.125rem;
  font-weight: 500;
}

.sdas-adapted-text {
  padding-inline: 16px;
  margin: 0;
  font-size: 0.9375rem;
  line-height: 1.65rem;
  overflow-wrap: break-word;
  white-space: pre-wrap;
}

.sdas-adapted-credits {
  margin-top: 1.5rem;
}

.sdas-adapted-credits-head {
  padding-inline: 16px;
}

/* 改编作品网格：与演员页的作品网格同口径（150px 起，自动铺满） */
.sdas-adapted-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  gap: 16px;
  padding: 8px 16px 0;
}

.sdas-adapted-empty {
  padding: 8px 16px 0;
  margin: 0;
  font-size: 0.875rem;
  color: rgba(var(--v-theme-on-surface), 0.6);
}
</style>
