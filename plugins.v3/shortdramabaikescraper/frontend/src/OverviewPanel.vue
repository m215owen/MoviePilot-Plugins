<template>
  <!--
    分区 ①：状态概览（复用 `/status`）。

    这一屏只回答三个问题：插件开没开、库里有什么、探索页会显示哪几个榜。
    不做任何「猜」的统计 —— 所有数字都是后端 `WHERE media_id LIKE 'x:%'` 数出来的，
    面板只负责排版。
  -->
  <div class="sdbs-page">
    <v-alert
      v-if="error"
      type="error"
      variant="tonal"
      density="compact"
      class="mb-3"
    >
      {{ error }}
    </v-alert>

    <!--
      ⚠️ 判据必须是 `status?.enabled === false`，不能写 `!status?.enabled`：
      `status` 初值是 null，取反得到 true，刚打开面板会先闪一条「未启用」警告。
    -->
    <v-alert
      v-if="status?.enabled === false"
      type="warning"
      variant="tonal"
      density="compact"
      class="mb-3"
    >
      插件当前未启用：识别、检索与探索页都不会生效（面板的管理操作仍可用）。
    </v-alert>

    <div class="sdbs-stats">
      <div class="sdbs-stat">
        <div class="sdbs-stat-label">ID 库总条数</div>
        <div class="sdbs-stat-value">{{ loaded ? status?.total ?? 0 : '—' }}</div>
        <div class="sdbs-stat-hint">表内真实行数</div>
      </div>
      <div class="sdbs-stat">
        <div class="sdbs-stat-label">可检索条数</div>
        <div class="sdbs-stat-value">{{ loaded ? status?.searchable ?? 0 : '—' }}</div>
        <div class="sdbs-stat-hint">
          {{ status ? `占 ${percent(status.searchable, status.total)}（name 非空）` : 'name 非空的行' }}
        </div>
      </div>
      <div class="sdbs-stat">
        <div class="sdbs-stat-label">豆瓣兜底</div>
        <div class="sdbs-stat-value">{{ loaded ? doubanTotal : '—' }}</div>
        <div class="sdbs-stat-hint">百科未收录、走豆瓣出条</div>
      </div>
      <div class="sdbs-stat">
        <div class="sdbs-stat-label">缓存条数</div>
        <div class="sdbs-stat-value">{{ loaded ? cacheTotal : '—' }}</div>
        <div class="sdbs-stat-hint">
          {{ loaded ? `分布在 ${cachedRegions} / ${status?.regions?.length ?? 0} 个分区` : '各缓存 region 行数之和' }}
        </div>
      </div>
    </div>

    <!-- 实体分布：饼图（按 media_id 前缀统计，数量为 0 的实体不进图） -->
    <div class="sdbs-section">
      <v-icon icon="mdi-chart-donut" size="16" />
      <span>实体分布</span>
      <v-spacer />
      <span class="text-caption sdbs-dim">按 media_id 前缀统计</span>
    </div>
    <DonutChart
      v-if="entityTotal"
      :rows="entityRows"
      unit="条"
      :name="entityLabel"
      title="实体分布"
    />
    <div v-else class="sdbs-empty" style="padding: 12px">
      <v-icon size="24" icon="mdi-database-off-outline" />
      <span>还没有任何记录</span>
    </div>

    <!--
      缓存分布：饼图（2026-10-24 用户口径：缓存数据也要饼状图统计）。
      条数是后端扫各 region 的键数出来的（`/status.by_region`），随 TTL 自然过期，
      所以这里只做展示，不提供任何"清理"按钮（清理在缓存页）。
    -->
    <div class="sdbs-section">
      <v-icon icon="mdi-chart-pie" size="16" />
      <span>缓存分布</span>
      <v-spacer />
      <span class="text-caption sdbs-dim">按缓存 region 统计（会随 TTL 过期）</span>
    </div>
    <DonutChart
      v-if="cacheTotal"
      :rows="cacheRows"
      unit="条"
      :name="regionLabel"
      title="缓存分布"
    />
    <div v-else class="sdbs-empty" style="padding: 12px">
      <v-icon size="24" icon="mdi-cached" />
      <span>缓存现在是空的（没抓过页，或已过 TTL）</span>
    </div>

    <!-- 运行事实：来源标识 / 版本 / 站点，方便核对生效的是哪一份代码 -->
    <v-divider class="my-3" />
    <div class="sdbs-meta">
      <span class="sdbs-meta-item">
        <v-icon size="14" icon="mdi-tag-outline" />
        版本 <span class="sdbs-meta-value">{{ status?.version || '—' }}</span>
      </span>
      <span class="sdbs-meta-item">
        <v-icon size="14" icon="mdi-database-search-outline" />
        来源标识
        <span class="sdbs-meta-value sdbs-key">{{ status?.media_source || '—' }}</span>
      </span>
      <span class="sdbs-meta-item">
        <v-icon size="14" icon="mdi-web" />
        站点
        <!-- 跟随 `/status.site`：切到新站后这里必须跟着变，否则「切换没生效」 -->
        <a
          class="sdbs-key"
          :href="siteInfo.base"
          target="_blank"
          rel="noreferrer noopener"
        >{{ siteInfo.host }}</a>
        <span class="sdbs-dim">{{ siteKey === 'org' ? '新站' : '老站' }}</span>
      </span>
      <span class="sdbs-meta-item">
        <v-icon size="14" icon="mdi-filter-remove-outline" />
        排除
        <span class="sdbs-meta-value">
          {{ status?.exclude_manju === false ? '未开启' : siteInfo.excludeName }}
        </span>
      </span>
      <v-spacer />
      <v-btn
        size="x-small"
        variant="text"
        prepend-icon="mdi-refresh"
        :loading="loading"
        @click="load()"
      >
        刷新
      </v-btn>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { fetchStatus } from './api'
import DonutChart from './DonutChart.vue'
import {
  MANJU_ENTITIES,
  entityFiltersFor,
  REGION_LABELS,
  entityLabel,
  percent,
  regionLabel,
} from './constants'
import { setSite, siteInfo, siteKey } from './site'
import type { PluginApi, StatusPayload } from './types'

const props = defineProps<{
  /** 宿主注入的 axios 实例 */
  api?: PluginApi
}>()

const loading = ref(false)
/** 是否已经拿到过一份状态（区分「还没读」与「读了确实是 0」） */
const loaded = ref(false)
const status = ref<StatusPayload | null>(null)
const error = ref('')

/** 豆瓣两类兜底条数之和（`douban:` 作品 + `doubanp:` 人物） */
const doubanTotal = computed(() => {
  const counts = status.value?.by_entity || {}
  return Number(counts.douban || 0) + Number(counts.doubanp || 0)
})

/**
 * 实体分布行：按**当前主站**的实体顺序（作品 → 原著 → 人物 → 豆瓣）**全部列出**。
 *
 * 不隐藏本主站 0 条的行：`drama` 为 0 与 `drama` 不存在是两件事，隐藏了就看不出
 * 「这个分区一次都没抓到过」。
 *
 * 别的主站的前缀（切站不清库，老站的行还在库里）只在**有条目时**才追加：
 * 它们是残留数据，0 条时列出来只会让人以为分类没切过来。
 *
 * 「排除漫剧 / AI 剧」打开时，漫剧类（`MANJU_ENTITIES`）整类不列：后端已把
 * 这些行从统计里滤掉，留着就是三行永远 0 条的「漫剧」。
 */
const entityRows = computed(() => {
  const counts = status.value?.by_entity || {}
  const excludeManju = status.value?.exclude_manju !== false
  const own = entityFiltersFor(siteKey.value, excludeManju)
  const known = own.map((key) => ({ key, count: Number(counts[key] || 0) }))
  // 后端将来加了新前缀 / 库里还有别站的数据：有条目就排在后面原样显示，不丢数据
  const extra = Object.keys(counts)
    .filter(
      (key) =>
        !own.includes(key) &&
        Number(counts[key] || 0) > 0 &&
        !(excludeManju && MANJU_ENTITIES.includes(key))
    )
    .sort()
    .map((key) => ({ key, count: Number(counts[key] || 0) }))
  return [...known, ...extra]
})

/**
 * 缓存分布行：按固定顺序（详情 → 人物 → 豆瓣 → 站内搜索 → 榜单）列出**全部**分区。
 *
 * 与实体分布同一个口径：0 条的分区也要列出来 —— 「这个分区一条都没缓存过」
 * 和「这个分区不存在」是两件事，隐藏了就看不出来。
 * 顺序以后端 `/status.regions` 为准，认不出的一律排在后面，不丢数据。
 */
const cacheRows = computed(() => {
  const counts = status.value?.by_region || {}
  const known = Object.keys(REGION_LABELS)
  const declared = status.value?.regions || []
  const extra = [...declared, ...Object.keys(counts)].filter((key) => !known.includes(key))
  return [...known, ...extra].map((key) => ({ key, count: Number(counts[key] || 0) }))
})

/** 缓存总条数（0 说明缓存全空或全过期） */
const cacheTotal = computed(() => cacheRows.value.reduce((sum, row) => sum + row.count, 0))

/** 有货的分区数（对比「分区总数」能看出有几个分区是空的） */
const cachedRegions = computed(() => cacheRows.value.filter((row) => row.count > 0).length)

/** 实体分布的总条数（0 条实体不进图，否则会出现长度为 0 的假图例） */
const entityTotal = computed(() => entityRows.value.reduce((sum, row) => sum + row.count, 0))

async function load(): Promise<void> {
  loading.value = true
  error.value = ''
  try {
    status.value = await fetchStatus(props)
    // 顺带把主站同步到全局状态：概览是打开面板的第一屏，
    // 这里拿到的 site 比各组件各发一次 /status 更省
    setSite(status.value?.site)
  } catch (err) {
    error.value = `读取状态失败：${err instanceof Error ? err.message : String(err)}`
    status.value = null
  } finally {
    loading.value = false
    loaded.value = true
  }
}

/** 外壳（`PanelTabs`）切到本页或点刷新时调用 */
defineExpose({ reload: load })

onMounted(() => {
  void load()
})
</script>
