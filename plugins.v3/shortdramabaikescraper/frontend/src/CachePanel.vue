<template>
  <!--
    分区 ③：缓存（5 个 region：详情 / 人物 / 豆瓣 / 站内搜索 / 榜单）。

    搜索（2026-10-23 用户口径）：顶部输入框按「缓存键或值内容」筛，榜单区那种
    「一份缓存 = 一整份卡行列表」的值整体参与匹配，搜剧名能定位到它在哪本榜里；
    行标题显示榜单名（后端给的 `label`，如「推荐（30 部）」）。

    口径（计划 §6.5）：枚举的是**缓存里存的那份 JSON 原文** —— 详情 region 就是
    写进 `djbaike.detail` 的 MediaInfo 投影、搜索 region 就是搜索结果键列表，
    原样展示、原样删除。面板不替人「解读」缓存，只让人核对它。

    ⚠️ 缓存的键只在**分区内**唯一（同一个 id 在不同 region 各有一份），
    所以删单条必须同时带 `region` + `key`，二者缺一后端直接拒绝。
  -->
  <div class="sdbs-page">
    <v-alert v-if="error" type="error" variant="tonal" density="compact" class="mb-2">
      {{ error }}
    </v-alert>

    <!-- 分区选择：region 名是后端的硬标识，中文只是标签 -->
    <div class="sdbs-actions">
      <v-btn-toggle
        v-model="region"
        class="sdbs-toggle"
        density="compact"
        variant="text"
        divided
        mandatory
        @update:model-value="search()"
      >
        <v-btn v-for="key in regions" :key="key" size="x-small" :value="key">
          {{ regionLabel(key) }}
        </v-btn>
      </v-btn-toggle>
    </div>

    <div class="sdbs-meta">
      <span class="sdbs-meta-item">
        <v-icon size="14" icon="mdi-database-outline" />
        <span class="sdbs-key">{{ region || '—' }}</span>
      </span>
      <span class="sdbs-meta-item">
        枚举 <span class="sdbs-meta-value">{{ loaded ? items.length : '—' }}</span> 条
      </span>
      <v-spacer />
      <v-text-field
        v-model="q"
        density="compact"
        variant="outlined"
        hide-details
        clearable
        prepend-inner-icon="mdi-magnify"
        placeholder="搜键 / 内容"
        style="max-width: 180px"
        class="mr-2"
        @update:model-value="scheduleSearch()"
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
      <v-btn
        size="x-small"
        variant="text"
        prepend-icon="mdi-refresh"
        title="重新枚举（缓存会自己过 TTL，这里只是重读一遍）"
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
        title="清空本插件全部缓存分区（ID 库不动）"
        @click="askClear()"
      >
        清空全部
      </v-btn>
    </div>

    <div v-if="items.length" class="sdbs-list">
      <div v-for="item in items" :key="item.key" class="sdbs-row">
        <div class="sdbs-row-top">
          <button type="button" class="sdbs-row-head" @click="toggle(item)">
            <v-icon size="14" :icon="opened === item.key ? 'mdi-chevron-down' : 'mdi-chevron-right'" />
            <span class="sdbs-row-main">
              <span class="sdbs-row-title">{{ summary(item) }}</span>
              <span v-if="kindTag(item)" class="sdbs-tag">{{ kindTag(item) }}</span>
            </span>
          </button>
          <v-btn
            class="sdbs-row-del"
            size="x-small"
            variant="text"
            color="error"
            icon="mdi-delete-outline"
            :title="`删掉 ${region} 里的这一条`"
            @click.stop="askDelete(item)"
          />
        </div>

        <div class="sdbs-row-sub" :title="`${region} · ${item.parent || item.key}`">
          <span class="sdbs-key">{{ item.key }}</span>
          <span v-if="item.parent" class="sdbs-tag">{{ item.parent }}</span>
        </div>

        <!-- 展开区：该缓存对象的**原始 JSON** -->
        <div v-if="opened === item.key" class="sdbs-expand">
          <div class="sdbs-actions">
            <v-btn
              size="x-small"
              variant="text"
              prepend-icon="mdi-content-duplicate"
              @click="copy(rawJson(item))"
            >
              复制原始 JSON
            </v-btn>
            <v-btn
              size="x-small"
              variant="text"
              prepend-icon="mdi-identifier"
              @click="copy(item.key)"
            >
              复制键
            </v-btn>
          </div>
          <pre class="sdbs-raw">{{ rawJson(item) }}</pre>
        </div>
      </div>
    </div>

    <div v-else class="sdbs-empty">
      <v-icon size="26" :icon="loading ? 'mdi-progress-clock' : 'mdi-database-off-outline'" />
      <span>{{ loading ? '读取中…' : emptyHint }}</span>
    </div>

    <v-dialog v-model="confirmOpen" max-width="460">
      <v-card>
        <v-card-title class="text-body-1">
          {{ pending ? '删除这条缓存' : '清空全部缓存' }}
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
import { computed, onMounted, ref } from 'vue'
import { clearCache, deleteCacheItem, fetchCacheItems, fetchStatus } from './api'
import { REGION_LABELS, regionLabel } from './constants'
import type { CacheItem, PluginApi } from './types'

const props = defineProps<{
  /** 宿主注入的 axios 实例 */
  api?: PluginApi
}>()

/** 枚举上限（后端封顶 500，见 `api_cache_items`） */
const LIMITS = [50, 100, 200, 500]

/**
 * 兜底的分区清单：`/status.regions` 拿不到时（插件未启用、库未就绪）
 * 仍能枚举 —— 分区名是编译期常量，不依赖运行时状态。
 */
const FALLBACK_REGIONS = Object.keys(REGION_LABELS)

const regions = ref<string[]>(FALLBACK_REGIONS)
const region = ref('djbaike.detail')
const limit = ref(100)

const loading = ref(false)
const loaded = ref(false)
const items = ref<CacheItem[]>([])
/** 搜索词（按缓存键或值内容筛，后端过滤） */
const q = ref('')
let searchTimer: ReturnType<typeof setTimeout> | null = null
const error = ref('')
/** 当前展开的那一条（键在区内唯一，够用作标识） */
const opened = ref('')

const pending = ref<CacheItem | null>(null)
const confirmOpen = ref(false)
const purging = ref(false)

let token = 0

/** 确认框正文：把「缓存可重建」写清楚 —— 它与 ID 库是两回事 */
const confirmText = computed(() => {
  if (pending.value) {
    const realKey = pending.value.parent || pending.value.key
    return `删掉 ${region.value} 里的这一条？\n\n键：${realKey}${pending.value.parent ? '（整份数组缓存，一次删掉整条）' : ''}\n\n只删这一份缓存，ID 库不动；下次用到它会重新抓页。`
  }
  return `清空本插件的**全部缓存分区**（detail / person / douban / search / rank）？\n\nID 库不动。清空后首次识别会重新出网抓页，换来的是「全部按当下页面重刮」。`
})

/** 值是不是对象（`Object.prototype.toString` 比 typeof 稳，数组/日期都算） */
function isPlainObject(value: unknown): value is Record<string, any> {
  return Object.prototype.toString.call(value) === '[object Object]'
}

/**
 * 一行显示什么：优先用值里自带的标题（详情 / 人物缓存都是这种），
 * 退化成 JSON 前一段 —— 绝不为了「好看」去猜字段含义。
 */
function summary(item: CacheItem): string {
  if (item.label) return item.label
  const value = item.value
  if (typeof value === 'string') return value.slice(0, 80) || '（空字符串）'
  if (Array.isArray(value)) return `数组 · ${value.length} 项`
  if (isPlainObject(value)) {
    const title = value.title || value.name || value.media_id
    if (title) return String(title)
    const keys = Object.keys(value)
    return keys.length ? `{ ${keys.slice(0, 4).join(', ')}${keys.length > 4 ? ' …' : ''} }` : '（空对象）'
  }
  if (value === null || value === undefined) return '（null）'
  return String(value)
}

/** 值里的类型标记（详情缓存有 `kind`，人物缓存有职能），没有就不显示 */
function kindTag(item: CacheItem): string {
  const value = item.value
  if (!isPlainObject(value)) return ''
  return String(value.kind || value.type || value.media_source || '')
}

/** 原始 JSON 文本（`undefined` 也要能打印出来，不能抛） */
function rawJson(item: CacheItem): string {
  try {
    return JSON.stringify(item.value, null, 2) ?? String(item.value)
  } catch {
    return String(item.value)
  }
}

async function copy(text: string): Promise<void> {
  try {
    await navigator.clipboard.writeText(text)
  } catch {
    error.value = '复制失败：浏览器拒绝了剪贴板权限'
  }
}

function toggle(item: CacheItem): void {
  opened.value = opened.value === item.key ? '' : item.key
}

/**
 * 空态说明：每个分区为空的原因不一样，笼统一句"空的"会让人以为坏了。
 *
 * 榜单区：一条缓存 = 一整份卡行列表（这里已摊成一条一行）；为空说明还没抓过榜。
 */
const emptyHint = computed(() => {
  if (q.value.trim()) return `这个分区里没有匹配「${q.value.trim()}」的条目`
  if (region.value === 'djbaike.rank') {
    return '榜单区为空：打开面板里任一榜单后才会写入（一本榜一条缓存，值是该榜全部卡行）'
  }
  return '这个分区现在是空的（没抓过页，或已过 TTL）'
})

/** 切分区 / 改上限 / 改搜索词：清空展开态（旧键在新分区里未必存在） */
function search(): void {
  opened.value = ''
  void load()
}

/** 输入防抖：300ms 内连续输入只发一次请求 */
function scheduleSearch(): void {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => search(), 300)
}

async function load(): Promise<void> {
  const seq = ++token
  loading.value = true
  error.value = ''
  try {
    const data = await fetchCacheItems(props, region.value, limit.value, q.value.trim())
    if (seq !== token) return
    items.value = data?.items || []
  } catch (err) {
    if (seq !== token) return
    error.value = `读取缓存失败：${err instanceof Error ? err.message : String(err)}`
    items.value = []
  } finally {
    if (seq === token) {
      loading.value = false
      loaded.value = true
    }
  }
}

/** 分区清单以 `/status` 为准（将来后端加 region，面板不用改代码） */
async function loadRegions(): Promise<void> {
  try {
    const status = await fetchStatus(props)
    const list = status?.regions || []
    if (list.length) {
      regions.value = list
      if (!list.includes(region.value)) region.value = list[0]
    }
  } catch {
    // 状态读不到就用兜底清单：清单一事不该阻塞「看缓存」
  }
}

function askDelete(item: CacheItem): void {
  pending.value = item
  confirmOpen.value = true
}

function askClear(): void {
  pending.value = null
  confirmOpen.value = true
}

function closeConfirm(): void {
  if (purging.value) return
  confirmOpen.value = false
  pending.value = null
}

async function confirmPurge(): Promise<void> {
  const target = pending.value
  purging.value = true
  error.value = ''
  try {
    if (target) {
      // 数组展开行的真键是 parent；删它等于删整份数组缓存
      const result = await deleteCacheItem(props, region.value, target.parent || target.key)
      if (!result?.ok) error.value = `删除未生效：${result?.detail || '键不存在或已过期'}`
    } else {
      const result = await clearCache(props)
      if (!result?.ok) error.value = '清空未生效：后端未确认'
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

/** 给外壳的出口 */
defineExpose({ reload: load })

onMounted(async () => {
  await loadRegions()
  await load()
})
</script>
