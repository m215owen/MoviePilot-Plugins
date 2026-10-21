<template>
  <!--
    作品卡片 —— 搜索结果里的那张，也是缓存 / URL 库点开展开区里的那张。
    抽成组件就是为了「点一下看到的和搜出来看到的完全一样」。
  -->
  <v-card variant="outlined" class="pa-3">
    <div class="d-flex" style="gap: 12px">
      <v-img
        :src="proxyImage(item.poster)"
        width="92"
        height="123"
        aspect-ratio="2/3"
        cover
        class="rounded flex-shrink-0 sdbs-poster"
      />
      <div class="flex-grow-1" style="min-width: 0">
        <div class="text-subtitle-2">{{ item.title || '（无标题）' }}</div>
        <div class="text-caption sdbs-dim mt-1">{{ meta }}</div>
        <div v-if="item.tags?.length" class="mt-1">
          <v-chip
            v-for="tag in item.tags"
            :key="tag"
            size="x-small"
            variant="tonal"
            class="mr-1 mb-1"
          >
            {{ tag }}
          </v-chip>
        </div>
        <div v-if="item.overview" class="text-caption mt-2 sdbs-clamp">{{ item.overview }}</div>
        <div v-if="cast" class="text-caption sdbs-dim mt-2">主演：{{ cast }}</div>
        <!-- 同页「推荐短剧」：站点自己给的关联作品，也一并解析出来了 -->
        <div v-if="item.related?.length" class="mt-2">
          <span class="text-caption sdbs-dim mr-1">同页推荐：</span>
          <v-chip
            v-for="rel in item.related.slice(0, 8)"
            :key="rel.media_id || rel.title"
            size="x-small"
            variant="tonal"
            class="mr-1 mb-1"
            :href="rel.url"
            target="_blank"
            rel="noopener"
          >
            {{ rel.title }}
          </v-chip>
        </div>
      </div>
    </div>
    <div class="d-flex align-center mt-2 flex-wrap" style="gap: 8px">
      <v-btn
        v-if="item.url"
        size="x-small"
        variant="tonal"
        :href="item.url"
        target="_blank"
        rel="noopener"
        prepend-icon="mdi-open-in-new"
      >
        站点页面
      </v-btn>
      <v-btn size="x-small" variant="text" @click="rawOpen = !rawOpen">
        {{ rawOpen ? '收起原始数据' : '原始数据' }}
      </v-btn>
      <v-spacer />
      <span v-if="extra" class="text-caption sdbs-dim">{{ extra }}</span>
    </div>
    <pre v-if="rawOpen" class="sdbs-pre mt-2">{{ pretty(item) }}</pre>
  </v-card>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { proxyImage } from './api'
import { castLine, pretty, recordMeta } from './format'
import type { MediaRecord } from './types'

const props = defineProps<{
  /** 作品记录（后端 `build_public_record` 的形状）；为空时卡片渲染成空态 */
  record?: MediaRecord | null
  /** 右下角的一句话补充（展开区用来标「缓存 detail:60017」这类来源） */
  extra?: string
}>()

/** 内部统一兜一层：调用方拿到数据前后都能安全渲染同一张卡 */
const item = computed<MediaRecord>(() => props.record || {})

/** 「原始数据」展开态：每张卡各管各的 */
const rawOpen = ref(false)

const meta = computed(() => recordMeta(item.value, true))
const cast = computed(() => castLine(item.value))

// 换了另一条记录（同一张卡被复用）时收起原始数据，免得看着像没加载出来
watch(() => props.record, () => {
  rawOpen.value = false
})
</script>

<style scoped>
.sdbs-dim {
  opacity: 0.7;
}
.sdbs-poster {
  background-color: rgba(128, 128, 128, 0.12);
}
/* 简介最多三行，避免一条简介把整列撑开 */
.sdbs-clamp {
  display: -webkit-box;
  -webkit-line-clamp: 3;
  line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
/* 原始数据块：等宽、可横向滚动、限高避免长 JSON 顶掉整页 */
.sdbs-pre {
  margin: 0;
  padding: 8px;
  max-height: 260px;
  overflow: auto;
  font-size: 12px;
  line-height: 1.5;
  white-space: pre;
  border-radius: 6px;
  background-color: rgba(128, 128, 128, 0.12);
}
</style>
