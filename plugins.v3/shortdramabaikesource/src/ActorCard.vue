<template>
  <!--
    演员卡片 —— 档案 + 全部作品墙，搜索结果与展开区共用同一份。
    作品可能几十部，底部「完整信息」「原始数据」按需展开（见脚本里的注释）。
  -->
  <div>
    <v-card variant="outlined" class="pa-3">
      <div class="d-flex" style="gap: 12px">
        <v-avatar size="64" rounded class="flex-shrink-0">
          <v-img :src="proxyImage(actor.profile)" cover />
        </v-avatar>
        <div class="flex-grow-1" style="min-width: 0">
          <div class="text-subtitle-2">
            {{ actor.name || '（无姓名）' }}
            <span v-if="actor.actor_id" class="text-caption sdbs-dim ml-2">actor:{{ actor.actor_id }}</span>
          </div>
          <div class="text-caption sdbs-dim mt-1">{{ meta }}</div>
          <div v-if="actor.bio" class="text-caption mt-2 sdbs-clamp">{{ actor.bio }}</div>
        </div>
      </div>
      <div v-if="actor.coactors?.length" class="mt-2">
        <span class="text-caption sdbs-dim mr-1">常合作演员：</span>
        <v-chip
          v-for="co in actor.coactors.slice(0, 12)"
          :key="co.id || co.name"
          size="x-small"
          variant="tonal"
          class="mr-1 mb-1"
        >
          {{ co.name }}
        </v-chip>
      </div>
      <div class="d-flex align-center mt-2 flex-wrap" style="gap: 8px">
        <v-btn
          v-if="actor.url"
          size="x-small"
          variant="tonal"
          :href="actor.url"
          target="_blank"
          rel="noopener"
          prepend-icon="mdi-open-in-new"
        >
          演员页
        </v-btn>
        <v-btn size="x-small" variant="text" @click="rawOpen = !rawOpen">
          {{ rawOpen ? '收起原始数据' : '原始数据' }}
        </v-btn>
        <v-spacer />
        <span v-if="extra" class="text-caption sdbs-dim">{{ extra }}</span>
      </div>
      <pre v-if="rawOpen" class="sdbs-pre mt-2">{{ pretty(actor) }}</pre>
    </v-card>

    <!-- 作品墙 -->
    <div class="text-subtitle-2 mt-3 mb-2">
      <v-icon icon="mdi-movie-open-outline" size="18" class="mr-1" />
      全部作品
      <span class="text-caption sdbs-dim ml-1">共 {{ works.length }} 部</span>
    </div>
    <div v-if="!works.length" class="text-caption sdbs-dim">这位演员在这条记录里没有作品（多半是抓到的页面只有资料）。</div>
    <v-row dense>
      <v-col
        v-for="(work, index) in works"
        :key="work.media_id || index"
        cols="12"
        :sm="compact ? 12 : 6"
      >
        <v-card variant="outlined" class="pa-2 h-100 d-flex flex-column">
          <div class="d-flex" style="gap: 8px">
            <v-img
              :src="proxyImage(work.poster)"
              width="60"
              height="80"
              aspect-ratio="2/3"
              cover
              class="rounded flex-shrink-0 sdbs-poster"
            />
            <div class="flex-grow-1" style="min-width: 0">
              <div class="text-body-2 sdbs-work-title">{{ work.title || '（无标题）' }}</div>
              <div class="text-caption sdbs-dim mt-1">{{ recordMeta(workView(index)) || '—' }}</div>
              <div v-if="workTags(index, work).length" class="mt-1">
                <v-chip
                  v-for="tag in workTags(index, work)"
                  :key="tag"
                  size="x-small"
                  variant="tonal"
                  class="mr-1 mb-1"
                >
                  {{ tag }}
                </v-chip>
              </div>
            </div>
          </div>
          <v-spacer />
          <div class="d-flex align-center mt-1">
            <v-btn
              v-if="work.url"
              size="x-small"
              variant="text"
              :href="work.url"
              target="_blank"
              rel="noopener"
            >
              站点
            </v-btn>
            <v-btn
              size="x-small"
              variant="text"
              :loading="workLoadingIndex === index"
              :disabled="workComplete(index, work)"
              :title="workComplete(index, work)
                ? '已是作品页那份数据（完整标签 / 首播 / 版权方 / 时长 / 简介 / 剧照）'
                : '演员页卡片是摘要（标签只印 1~3 个、没有版权方），抓一次详情页补全'"
              @click="loadWorkDetail(index)"
            >
              {{ workComplete(index, work) ? '已补全' : '完整信息' }}
            </v-btn>
            <v-spacer />
            <v-btn size="x-small" variant="text" @click="toggleWorkRaw(index)">
              {{ openWorks.has(index) ? '收起' : '原始数据' }}
            </v-btn>
          </div>
          <pre v-if="openWorks.has(index)" class="sdbs-pre mt-1">{{ pretty(workView(index)) }}</pre>
        </v-card>
      </v-col>
    </v-row>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { proxyImage, recognizeTitle, resolveApi } from './api'
import { pretty, recordMeta } from './format'
import type { ActorProfile, MediaRecord, PluginApi, WorkItem } from './types'

const props = defineProps<{
  /** 演员档案（后端 `build_public_actor` 的形状）；为空时渲染成空态 */
  profile?: ActorProfile | null
  /** 宿主注入的 axios 实例（「完整信息」按需补全要用） */
  api?: PluginApi
  /** 窄容器（展开区）里作品墙强制单列 —— v-col 的断点看视口，不看容器 */
  compact?: boolean
  /** 右下角的一句话补充（展开区用来标来源） */
  extra?: string
}>()

/** 内部统一兜一层：调用方拿到数据前后都能安全渲染同一张卡 */
const actor = computed<ActorProfile>(() => props.profile || {})
const works = computed<WorkItem[]>(() => actor.value.works || [])

const rawOpen = ref(false)
/** 已展开原始数据的作品下标（作品可能几十部，逐个展开比一次全铺清爽） */
const openWorks = ref(new Set<number>())
/**
 * 作品墙里**已补全**的作品（下标 → 完整记录）。
 *
 * ⚠️ 演员页的卡片是**摘要视图**：站点在卡片上只印 1~3 个题材标签（实测《失控交易》
 * 卡片上只有「爱情」，而它详情页有 5 个），完整标签只有详情页的 JSON-LD 里才有。
 * 一个演员动辄几十部作品，一次性全抓既不现实也容易撞风控 —— 所以这里按需补：
 * 点卡片上的「完整信息」才抓这一部的详情页，抓到就整条替换进卡片。
 */
const workFull = ref<Record<number, MediaRecord>>({})
/** 正在补全的作品下标（按钮 loading 态） */
const workLoadingIndex = ref<number | null>(null)

const meta = computed(() => {
  const item = actor.value
  const parts: string[] = []
  if (item.job_title) parts.push(item.job_title)
  if (item.gender) parts.push(`性别 ${item.gender}`)
  if (item.nationality) parts.push(item.nationality)
  parts.push(`作品 ${item.works_count ?? (item.works || []).length} 部`)
  return parts.join(' ｜ ')
})

// 换成另一位演员时把本地展开态清干净，否则会串到下一位的名字上
watch(() => props.profile, () => {
  rawOpen.value = false
  openWorks.value = new Set<number>()
  workFull.value = {}
  workLoadingIndex.value = null
})

/**
 * 卡片上真正用来渲染的那条记录：补全过就用完整记录，否则用演员页卡片的摘要。
 */
function workView(index: number): WorkItem {
  return (workFull.value[index] as WorkItem | undefined) ?? works.value[index] ?? {}
}

/**
 * 这部作品是否已是「作品页那份数据」。
 *
 * 后端**一贯**把全部作品补过详情（`origin === 'detail'`），这时面板不必再点
 * 「完整信息」—— 载荷里就是完整记录；只有 `enrich=0` 的老缓存 / 手动跳过时才需要
 * 按需补（点哪部补哪部）。
 */
function workComplete(index: number, work?: WorkItem): boolean {
  return Boolean(workFull.value[index]) || work?.origin === 'detail'
}

/**
 * 卡片上的标签：已是完整记录就全给，摘要则**照旧只给卡片上那 1~3 个**。
 * 卡片印多少就是多少，不补齐也不假装。
 */
function workTags(index: number, work: WorkItem): string[] {
  const tags = (workFull.value[index]?.tags ?? work.tags) || []
  return workComplete(index, work) ? tags : tags.slice(0, 3)
}

/** 抓一部作品的详情页，把卡片补成完整记录（按需，一部一次请求） */
async function loadWorkDetail(index: number): Promise<void> {
  const client = resolveApi({ api: props.api })
  const work = works.value[index]
  if (!client || !work?.media_id || workComplete(index, work)) return
  workLoadingIndex.value = index
  try {
    const report = await recognizeTitle(client, { media_id: work.media_id })
    if (report?.success && report.record) {
      workFull.value = { ...workFull.value, [index]: report.record }
    }
  } finally {
    workLoadingIndex.value = null
  }
}

function toggleWorkRaw(index: number): void {
  const next = new Set(openWorks.value)
  if (next.has(index)) next.delete(index)
  else next.add(index)
  openWorks.value = next
}
</script>

<style scoped>
.sdbs-dim {
  opacity: 0.7;
}
.sdbs-poster {
  background-color: rgba(128, 128, 128, 0.12);
}
.sdbs-clamp {
  display: -webkit-box;
  -webkit-line-clamp: 3;
  line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.sdbs-work-title {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
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
