<template>
  <!--
    分区 ②：ID 库（`baike` 表）。

    口径（计划 §6.5「看原始数据的语义」）：列表里显示的、展开后显示的，
    **都是表里的原样 4 列**（media_id / name / douban / tmdb），
    不做清洗、不做翻译、不拼 URL。想看「库里到底存了什么」时，
    这一页就是那份答案；拼出来的地址之类派生信息一概不混进来。

    检索走**服务端**：库只增不减，一次拿全不现实，`q` 与实体前缀都进 SQL 条件，
    所以搜到的永远是全库范围，不会被分页截断。
  -->
  <div class="sdbs-page">
    <v-alert v-if="error" type="error" variant="tonal" density="compact" class="mb-2">
      {{ error }}
    </v-alert>

    <!-- 过滤行：关键词（服务端模糊 media_id / name） -->
    <div class="sdbs-filter-row">
      <v-text-field
        v-model="keyword"
        class="sdbs-filter"
        variant="outlined"
        density="compact"
        hide-details
        clearable
        prepend-inner-icon="mdi-magnify"
        placeholder="按 media_id 或 name 模糊过滤（例如：以爱为家 / duanju:7696）"
        @keydown.enter="search()"
      />
      <v-btn size="small" variant="tonal" color="primary" :loading="loading" @click="search()">
        查询
      </v-btn>
    </div>

    <!-- 实体 chips：值就是 media_id 前缀（服务端按 `entity:%` 过滤） -->
    <div class="sdbs-actions">
      <v-btn-toggle
        v-model="entity"
        class="sdbs-toggle"
        density="compact"
        variant="text"
        divided
        mandatory
        @update:model-value="search()"
      >
        <v-btn size="x-small" value="">全部</v-btn>
        <v-btn v-for="key in ENTITY_FILTERS" :key="key" size="x-small" :value="key">
          {{ entityLabel(key) }}
        </v-btn>
      </v-btn-toggle>
      <v-spacer />
      <v-btn
        size="x-small"
        variant="text"
        prepend-icon="mdi-refresh"
        title="按当前条件重查（数据库查询本来就实时，这里只是重发条件）"
        :loading="loading"
        @click="load()"
      >
        刷新
      </v-btn>
      <v-btn
        size="x-small"
        variant="text"
        color="error"
        prepend-icon="mdi-delete-sweep-outline"
        title="清空整个 ID 库（缓存不动）"
        :disabled="!loaded || !total"
        @click="askClear()"
      >
        清空
      </v-btn>
    </div>

    <!-- 分页条：offset / limit 分页（后端只支持 offset 语义，不假装成页码） -->
    <div class="sdbs-meta">
      <span class="sdbs-meta-item">
        <v-icon size="14" icon="mdi-format-list-numbered" />
        共 <span class="sdbs-meta-value">{{ loaded ? total : '—' }}</span> 条
      </span>
      <span class="sdbs-meta-item">
        显示
        <span class="sdbs-meta-value sdbs-num">{{ rangeText }}</span>
      </span>
      <v-spacer />
      <v-btn
        size="x-small"
        variant="text"
        icon="mdi-chevron-left"
        title="上一页"
        :disabled="offset <= 0 || loading"
        @click="step(-1)"
      />
      <v-btn
        size="x-small"
        variant="text"
        icon="mdi-chevron-right"
        title="下一页"
        :disabled="offset + limit >= total || loading"
        @click="step(1)"
      />
      <v-select
        v-model="limit"
        density="compact"
        variant="outlined"
        hide-details
        :items="LIMITS"
        style="max-width: 96px"
        @update:model-value="search()"
      />
    </div>

    <!-- 列表 -->
    <div v-if="items.length" class="sdbs-list">
      <div v-for="row in items" :key="row.media_id" class="sdbs-row">
        <div class="sdbs-row-top">
          <button type="button" class="sdbs-row-head" @click="toggle(row)">
            <v-icon size="14" :icon="opened === row.media_id ? 'mdi-chevron-down' : 'mdi-chevron-right'" />
            <span class="sdbs-row-main">
              <!-- 名字为空是**合法**状态：顺带登记时只拿到了 id（列表页卡片没名字） -->
              <span class="sdbs-row-title">{{ row.name || '（未记录名字）' }}</span>
              <span class="sdbs-tag">{{ entityLabel(entityOf(row.media_id)) }}</span>
            </span>
          </button>
          <v-btn
            class="sdbs-row-del"
            size="x-small"
            variant="text"
            color="error"
            icon="mdi-delete-outline"
            :title="`从库里删掉 ${row.media_id}（会联动删它的详情 / 人物缓存）`"
            @click.stop="askDelete(row)"
          />
        </div>

        <div class="sdbs-row-sub" :title="subTitle(row)">
          <span class="sdbs-key">{{ row.media_id }}</span>
          <span v-if="row.douban"> · 豆瓣 <span class="sdbs-key">{{ row.douban }}</span></span>
          <span v-if="row.tmdb"> · TMDB <span class="sdbs-key">{{ row.tmdb }}</span></span>
          <span v-if="!row.name"> · 无名字（不可按名检索）</span>
        </div>

        <!-- 展开区：这就是「原始 4 列」，连空串都如实显示 -->
        <div v-if="opened === row.media_id" class="sdbs-expand">
          <v-table density="compact" class="mb-1">
            <tbody>
              <tr v-for="col in COLUMNS" :key="col.key">
                <td class="sdbs-key" style="width: 120px">{{ col.key }}</td>
                <td>
                  <span v-if="row[col.key]" class="sdbs-key">{{ row[col.key] }}</span>
                  <span v-else class="sdbs-dim">（空）</span>
                </td>
              </tr>
            </tbody>
          </v-table>
          <div class="sdbs-actions">
            <v-btn
              size="x-small"
              variant="text"
              prepend-icon="mdi-content-duplicate"
              @click="copy(JSON.stringify(row, null, 2))"
            >
              复制这一行 JSON
            </v-btn>
            <v-btn
              size="x-small"
              variant="text"
              color="primary"
              prepend-icon="mdi-open-in-new"
              :disabled="!canLookup(row)"
              title="按 media_id 查这条的详情（会出网，命中缓存则零请求）"
              @click="emit('lookup', row.media_id)"
            >
              查详情
            </v-btn>
          </div>
          <pre class="sdbs-raw">{{ JSON.stringify(row, null, 2) }}</pre>
        </div>
      </div>
    </div>

    <div v-else class="sdbs-empty">
      <v-icon size="26" :icon="emptyIcon" />
      <span>
        {{ loading ? '读取中…' : filtered ? '库里没有匹配的记录' : '库里还没有记录：识别 / 检索过一次就会有' }}
      </span>
    </div>

    <!-- 删除确认：删单条代价可控（下次检索会重新入库），但会联动清详情缓存，仍拦一道 -->
    <v-dialog v-model="confirmOpen" max-width="460">
      <v-card>
        <v-card-title class="text-body-1">
          {{ pending ? '删除这一条 ID' : '清空整个 ID 库' }}
        </v-card-title>
        <v-card-text class="text-body-2" style="white-space: pre-line">{{ confirmText }}</v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" :disabled="purging" @click="closeConfirm()">取消</v-btn>
          <v-btn
            color="error"
            variant="flat"
            :loading="purging"
            @click="confirmPurge()"
          >
            {{ pending ? '删除' : '清空' }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { clearBaike, deleteBaike, fetchBaikeList } from './api'
import { ENTITY_FILTERS, entityLabel, entityOf } from './constants'
import type { BaikeRow, PluginApi } from './types'

const props = defineProps<{
  /** 宿主注入的 axios 实例 */
  api?: PluginApi
}>()

const emit = defineEmits<{
  /** 点「查详情」：把 media_id 交给外壳，切到查询分区并直接查（跨分区联动） */
  (e: 'lookup', mediaId: string): void
}>()

/** 每页条数的可选值（后端上限 200，见 `api_baike_list`） */
const LIMITS = [25, 50, 100, 200]

/** 展开区表格的列（顺序即表里的真实列序） */
const COLUMNS = [
  { key: 'media_id', label: 'media_id' },
  { key: 'name', label: 'name' },
  { key: 'douban', label: 'douban' },
  { key: 'tmdb', label: 'tmdb' },
] as const

const loading = ref(false)
/** 是否已经拿到过一页（区分「还没读」与「读了确实是空」） */
const loaded = ref(false)
const items = ref<BaikeRow[]>([])
const total = ref(0)
const offset = ref(0)
const limit = ref(50)
const error = ref('')

/** 关键词（服务端模糊）；回车或点「查询」才发请求 */
const keyword = ref('')
/** 已提交的关键词：与输入框解耦，避免边敲边打后端 */
const submitted = ref('')
/** 实体过滤（空串 = 全部） */
const entity = ref('')
/** 当前展开的那一条（同一时刻只开一条） */
const opened = ref('')

/** 待删的那一条；`null` = 这次是「清空」而不是删单条 */
const pending = ref<BaikeRow | null>(null)
const confirmOpen = ref(false)
const purging = ref(false)

/** 请求序号：快速改条件时只认最后发出的那个 */
let token = 0

const filtered = computed(() => Boolean(submitted.value || entity.value))

/** 「显示 x–y」：空库时给 0–0，而不是负区间 */
const rangeText = computed(() => {
  if (!items.value.length) return '0'
  return `${offset.value + 1}–${offset.value + items.value.length}`
})

const emptyIcon = computed(() => {
  if (loading.value) return 'mdi-progress-clock'
  return filtered.value ? 'mdi-magnify-close' : 'mdi-database-off-outline'
})

/** 确认框正文：把「库只是索引、缓存另算」写清楚，避免误以为详情也没了 */
const confirmText = computed(() => {
  if (pending.value) {
    return `从 ID 库删掉这一行？\n\nmedia_id：${pending.value.media_id}\nname：${pending.value.name || '（空）'}\n\n会联动删除它的详情缓存与人物缓存；下次识别到它会重新入库。`
  }
  return `清空整个 ID 库的 ${total.value} 条记录？\n\n只删索引，**缓存不动**（缓存请到「缓存」分区单独清）。清空后 ID 库要靠后续识别 / 检索重新生长。`
})

/** 行内副标题（窄屏放不下，悬停看全） */
function subTitle(row: BaikeRow): string {
  const parts = [row.media_id]
  if (row.douban) parts.push(`豆瓣 ${row.douban}`)
  if (row.tmdb) parts.push(`TMDB ${row.tmdb}`)
  parts.push(entityLabel(entityOf(row.media_id)))
  return parts.join(' · ')
}

/** 能不能查详情：只认「已知前缀:非空 id」—— 裸豆瓣数字 id 后端也接受，这里一并放行 */
function canLookup(row: BaikeRow): boolean {
  const id = String(row.media_id || '')
  return id.includes(':') && id.split(':')[1].length > 0
}

/** 展开 / 收起（纯前端，不再请求：这一页的数据就是库里的原样） */
function toggle(row: BaikeRow): void {
  opened.value = opened.value === row.media_id ? '' : row.media_id
}

/** 复制到剪贴板（失败只提示，不抛 —— 复制是便利功能，不该打断操作） */
async function copy(text: string): Promise<void> {
  try {
    await navigator.clipboard.writeText(text)
  } catch {
    error.value = '复制失败：浏览器拒绝了剪贴板权限'
  }
}

/** 改条件重查：条件一变就回第一页（否则会停在越界的 offset 上看空列表） */
function search(): void {
  submitted.value = String(keyword.value || '').trim()
  offset.value = 0
  opened.value = ''
  void load()
}

/** 翻页 */
function step(direction: number): void {
  const next = offset.value + direction * limit.value
  if (next < 0) return
  offset.value = next
  opened.value = ''
  void load()
}

async function load(): Promise<void> {
  const seq = ++token
  loading.value = true
  error.value = ''
  try {
    const data = await fetchBaikeList(props, {
      q: submitted.value,
      entity: entity.value,
      offset: offset.value,
      limit: limit.value,
    })
    if (seq !== token) return // 已有更新的请求在路上，丢弃这次结果
    items.value = data?.items || []
    total.value = Number(data?.total ?? items.value.length)
    // 条件变严可能导致 offset 越界：退回最后一页的起点，而不是显示「空但共 N 条」
    if (!items.value.length && total.value > 0 && offset.value > 0) {
      offset.value = Math.max(0, Math.floor((total.value - 1) / limit.value) * limit.value)
    }
  } catch (err) {
    if (seq !== token) return
    error.value = `读取 ID 库失败：${err instanceof Error ? err.message : String(err)}`
    items.value = []
    total.value = 0
  } finally {
    if (seq === token) {
      loading.value = false
      loaded.value = true
    }
  }
}

/** 点行上的垃圾桶 */
function askDelete(row: BaikeRow): void {
  pending.value = row
  confirmOpen.value = true
}

/** 点顶部「清空」 */
function askClear(): void {
  pending.value = null
  confirmOpen.value = true
}

function closeConfirm(): void {
  if (purging.value) return
  confirmOpen.value = false
  pending.value = null
}

/**
 * 执行删除 / 清空。
 *
 * 删完**重读当前页**（而不是本地 splice）：总数、下一页边界都要跟着变，
 * 而这些是服务端算的。
 */
async function confirmPurge(): Promise<void> {
  const target = pending.value
  purging.value = true
  error.value = ''
  try {
    if (target) {
      const result = await deleteBaike(props, target.media_id)
      if (!result?.ok) error.value = `删除未生效：${result?.detail || '该 media_id 不存在'}`
    } else {
      const result = await clearBaike(props)
      if (!result?.ok) error.value = '清空未生效：后端未确认'
      offset.value = 0
    }
    confirmOpen.value = false
    pending.value = null
    opened.value = ''
    await load()
  } catch (err) {
    error.value = `操作失败：${err instanceof Error ? err.message : String(err)}`
  } finally {
    purging.value = false
  }
}

/** 给外壳的出口：外部切到本分区时可直接刷新 */
defineExpose({ reload: load })

/**
 * 输入防抖：敲字时不打后端，停 350ms 再查一次。
 *
 * 只 watch 关键词（实体 chips 是「点了就查」，不需要防抖）。
 * `clearable` 的叉会把值置成 null，所以统一 `String(... || '')`。
 */
let timer: number | undefined
watch(
  () => keyword.value,
  (value) => {
    window.clearTimeout(timer)
    const text = String(value || '').trim()
    // 清空输入框 = 回到「无条件」，立刻重查；否则等停手
    if (!text) {
      search()
      return
    }
    timer = window.setTimeout(() => {
      submitted.value = text
      offset.value = 0
      opened.value = ''
      void load()
    }, 350)
  },
)

onMounted(() => {
  void load()
})

onBeforeUnmount(() => {
  window.clearTimeout(timer)
})
</script>
