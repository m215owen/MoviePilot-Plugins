<template>
  <!--
    分区 ②：ID 库（`baike` 表）+ 外部 id（`baike_ext` 表）。

    两张表、三类 chip（2026-11-04 用户口径）：
    * 「站点 id」分类（各前缀）显示的是 `baike` 里**站点行自己的原始值** —— media_id / name，
      不掺豆瓣、TMDB；
    * 「豆瓣 id」「TMDB id」两个分类显示的是 `baike_ext` 的原始值 —— 名字 + 该列 id，
      后端按列非空过滤（`/baike/extlist?source=douban|tmdb`）。

    口径（计划 §6.5「看原始数据的语义」）：显示的都是表里的原样值，
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
        :placeholder="extMode
          ? `按名字 / ${extLabel} 模糊过滤（例如：马倩倩 / ${extSource === 'douban' ? '38500395' : '298016'}）`
          : `按 media_id 或 name 模糊过滤（例如：以爱为家 / ${siteInfo.sampleId}）`"
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
        <v-btn
          v-for="key in chips"
          :key="key"
          size="x-small"
          :value="key"
          :title="`${entityLabel(key)} · 库里 ${countOf(key)} 条`"
        >
          {{ entityLabel(key) }}
          <span v-if="countOf(key)" class="sdbs-dim"> {{ countOf(key) }}</span>
        </v-btn>
        <v-btn
          size="x-small"
          :value="EXT_DOUBAN"
          :title="`外部 id 表（baike_ext）里有豆瓣 id 的记录：名字 + 豆瓣 id，共 ${extDouban} 条；与站点行无关，清空站点库也不受影响`"
        >
          豆瓣 id
          <span v-if="extDouban" class="sdbs-dim"> {{ extDouban }}</span>
        </v-btn>
        <v-btn
          size="x-small"
          :value="EXT_TMDB"
          :title="`外部 id 表（baike_ext）里有 TMDB id 的记录：名字 + TMDB id，共 ${extTmdb} 条；与站点行无关，清空站点库也不受影响`"
        >
          TMDB id
          <span v-if="extTmdb" class="sdbs-dim"> {{ extTmdb }}</span>
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
        prepend-icon="mdi-link-variant-plus"
        :title="PERSON_ENTITIES.includes(entity)
          ? '按豆瓣演职员表给人物补影人 id（同片同名即同一人；一批 20 部作品，可反复点）'
          : '给库里 douban / tmdb 两列全空的行按名补一次外部 id（豆瓣精确匹配；一批 20 条，可反复点；豆瓣限流时会自动停）'"
        :loading="backfilling"
        :disabled="extMode || !loaded || !total || backfilling"
        @click="backfill()"
      >
        补 id
      </v-btn>
      <v-btn
        size="x-small"
        variant="text"
        color="error"
        prepend-icon="mdi-delete-sweep-outline"
        title="清空站点 ID 库（外部 id 与缓存都不动）"
        :disabled="extMode || !loaded || !total"
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

    <!-- 批量补外部 id 的结果（一次性提示，不占列表位置） -->
    <v-alert v-if="backfillTip" type="info" variant="tonal" density="compact" class="mb-2">
      {{ backfillTip }}
    </v-alert>

    <!-- 站点 id（`baike`）：只显示站点行自己的原始值 —— media_id / name -->
    <div v-if="!extMode && items.length" class="sdbs-list">
      <div v-for="row in items" :key="row.media_id" class="sdbs-row">
        <div class="sdbs-row-top">
          <button type="button" class="sdbs-row-head" @click="toggle(row.media_id)">
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
          <span v-if="!row.name"> · 无名字（不可按名检索）</span>
        </div>

        <!-- 展开区：这就是站点表的原样两列，连空串都如实显示 -->
        <div v-if="opened === row.media_id" class="sdbs-expand">
          <v-table density="compact" class="mb-1">
            <tbody>
              <tr v-for="col in SITE_COLUMNS" :key="col.key">
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

    <!-- 外部 id（`baike_ext`）：按 source 分成「豆瓣 id」「TMDB id」两个分类 -->
    <div v-else-if="extMode && extItems.length" class="sdbs-list">
      <div v-for="row in extItems" :key="row.name" class="sdbs-row">
        <div class="sdbs-row-top">
          <button type="button" class="sdbs-row-head" @click="toggle(row.name)">
            <v-icon size="14" :icon="opened === row.name ? 'mdi-chevron-down' : 'mdi-chevron-right'" />
            <span class="sdbs-row-main">
              <span class="sdbs-row-title">{{ row.name }}</span>
              <span class="sdbs-tag">{{ extLabel }}</span>
            </span>
          </button>
        </div>

        <div class="sdbs-row-sub" :title="extSubTitle(row)">
          <span>{{ extLabel }} <span class="sdbs-key">{{ extValueOf(row) || '（空）' }}</span></span>
          <span v-if="otherExtOf(row)" class="sdbs-gap sdbs-dim">· 另有 {{ otherExtOf(row) }}</span>
        </div>

        <div v-if="opened === row.name" class="sdbs-expand">
          <v-table density="compact" class="mb-1">
            <tbody>
              <tr v-for="col in EXT_COLUMNS" :key="col.key">
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
          </div>
          <pre class="sdbs-raw">{{ JSON.stringify(row, null, 2) }}</pre>
        </div>
      </div>
    </div>

    <div v-else class="sdbs-empty">
      <v-icon size="26" :icon="emptyIcon" />
      <span>
        {{ loading
          ? '读取中…'
          : extMode
            ? (submitted
                ? `外部 id 表里没有匹配「${submitted}」的 ${extLabel}`
                : `${extLabel}还是空的：补过一次 id 就会有记录`)
            : filtered
              ? '站点库里没有匹配的记录'
              : '站点库里还没有记录：识别 / 检索过一次就会有' }}
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
import {
  backfillExtIds,
  clearBaike,
  deleteBaike,
  fetchBaikeExtList,
  fetchBaikeList,
  fetchStatus,
} from './api'
import {
  MANJU_ENTITIES,
  PERSON_ENTITIES,
  entityFiltersFor,
  entityLabel,
  entityOf,
  isKnownEntity,
} from './constants'
import { ensureSite, setSite, siteInfo, siteKey } from './site'
import type { BaikeExtRow, BaikeRow, PluginApi } from './types'

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

/**
 * 外部 id 的两个分类（2026-11-04 用户口径「外部 id 拆为 tmdb 和豆瓣分类」）。
 *
 * 它们不是 `media_id` 前缀（外部 id 表按名字存、与站点无关），所以用不可能
 * 与真实前缀撞车的值当 chip 的 value，后端走 `/baike/extlist?source=` 而不是
 * `/baike/list?entity=`。
 */
const EXT_DOUBAN = '__ext_douban__'
const EXT_TMDB = '__ext_tmdb__'

/** 伪实体 → `/baike/extlist` 的 `source` 参数（后端按这一列非空过滤）。 */
const EXT_SOURCES: Record<string, 'douban' | 'tmdb'> = {
  [EXT_DOUBAN]: 'douban',
  [EXT_TMDB]: 'tmdb',
}

/** 站点表展开区的列（顺序即表里的真实列序：只有两列） */
const SITE_COLUMNS = [
  { key: 'media_id', label: 'media_id' },
  { key: 'name', label: 'name' },
] as const

/** 外部 id 表展开区的列 */
const EXT_COLUMNS = [
  { key: 'name', label: 'name' },
  { key: 'douban', label: 'douban' },
  { key: 'tmdb', label: 'tmdb' },
] as const

const loading = ref(false)
/** 是否已经拿到过一页（区分「还没读」与「读了确实是空」） */
const loaded = ref(false)
const items = ref<BaikeRow[]>([])
/** 外部 id 表的一页（与站点行分开放，避免两套字段混在一个数组里） */
const extItems = ref<BaikeExtRow[]>([])
const total = ref(0)
const offset = ref(0)
const limit = ref(50)
const error = ref('')

/** 关键词（服务端模糊）；回车或点「查询」才发请求 */
const keyword = ref('')
/** 已提交的关键词：与输入框解耦，避免边敲边打后端 */
const submitted = ref('')
/** 实体过滤（空串 = 全部；`EXT_DOUBAN` / `EXT_TMDB` = 外部 id 表的那一列） */
const entity = ref('')
/** 当前展开的那一条（同一时刻只开一条；站点行开 media_id、外部行开 name） */
const opened = ref('')

/** 待删的那一条；`null` = 这次是「清空」而不是删单条 */
const pending = ref<BaikeRow | null>(null)
const confirmOpen = ref(false)
const purging = ref(false)

/** 各实体的库内条数（`/status.by_entity`；拿不到就退化成「不显示条数」） */
const counts = ref<Record<string, number>>({})

/** 外部 id 表的两类条数（`/status.ext_douban` / `ext_tmdb`）：chip 上的计数 */
const extDouban = ref(0)
const extTmdb = ref(0)

/** 当前看的是不是外部 id 表（豆瓣 / TMDB 两类都算） */
const extMode = computed(() => Boolean(EXT_SOURCES[entity.value]))

/** 当前外部分类的 `source` 参数（`douban` / `tmdb`；站点分类为空串） */
const extSource = computed(() => EXT_SOURCES[entity.value] || '')

/** 当前外部分类的显示名（站点分类给空串） */
const extLabel = computed(() =>
  extSource.value === 'douban' ? '豆瓣 id' : extSource.value === 'tmdb' ? 'TMDB id' : '',
)

/** 排除漫剧 / AI 剧开关（`/status.exclude_manju`）：打开时漫剧类分类整类不列 */
const excludeManju = ref(true)

/** 批量补外部 id：进行中标记 + 上一轮结果提示 + 批次游标 */
const backfilling = ref(false)
const backfillTip = ref('')
const cursor = ref('')

/**
 * 实体 chips 的清单：**当前主站的实体** + 库里确实存在的其他前缀。
 *
 * 为什么不是一份写死的列表：新老站的编号空间完全不同（老站 `duanju`/`yanyuan`，
 * 新站 `drama`/`actor`）。写死一套就会在换站后显示一排 0 条的分类，
 * 而真正有数据的那两类只能靠行内标签露个英文前缀。
 *
 * 为什么还要并上「其他前缀」：库是共用的，切站不清库 —— 老站抓过的行仍在库里，
 * 必须给它们留一个能筛的入口，不能因为当前主站是新站就让它们凭空消失。
 *
 * 排除开关打开时漫剧类（`MANJU_ENTITIES`）整类不列：后端已把这些行从统计和
 * 列表里滤掉，面板留着它们只会显示一排 0 条的「漫剧」。
 */
const chips = computed(() => {
  const own = entityFiltersFor(siteKey.value, excludeManju.value)
  const extra = Object.keys(counts.value)
    .filter(
      (key) =>
        isKnownEntity(key) &&
        !own.includes(key) &&
        countOf(key) > 0 &&
        !(excludeManju.value && MANJU_ENTITIES.includes(key))
    )
    .sort()
  return [...own, ...extra]
})

/** 某前缀在库里的条数（未知返回 0）。 */
function countOf(entity: string): number {
  return Number(counts.value[String(entity || '')] || 0)
}

/**
 * 读一次 `/status`：同时拿到「各分类条数」和「当前主站」。
 *
 * 只发一个请求 —— 分类清单、条数、站点三者是同一份运行时事实，
 * 分三次读只会出现「chip 已经是新站、条数还是老站」的错位。
 */
async function loadStatus(): Promise<void> {
  try {
    const status = await fetchStatus(props)
    counts.value = status?.by_entity || {}
    extDouban.value = Number(status?.ext_douban || 0)
    extTmdb.value = Number(status?.ext_tmdb || 0)
    excludeManju.value = status?.exclude_manju !== false
    setSite(status?.site)
  } catch {
    // 读不到状态：分类照常按主站给，只是不显示条数
    await ensureSite(props.api)
  }
  syncEntity()
}

/**
 * 当前筛选的实体不在清单里了（换站 / 该分类被清空）→ 退回「全部」并重查。
 *
 * `EXT_DOUBAN` / `EXT_TMDB` 不是真实前缀，永远算合法 —— 外部 id 表可以是 0 条，
 * 但不能因此把人从外部 id 分类里踢回「全部」。
 */
function syncEntity(): void {
  if (!entity.value || extMode.value) return
  if (chips.value.includes(entity.value)) return
  entity.value = ''
  search()
}

/** 请求序号：快速改条件时只认最后发出的那个 */
let token = 0

const filtered = computed(() => Boolean(submitted.value || entity.value))

/** 当前页的行数（站点 / 外部两个来源合一，分页条只关心条数） */
const rowCount = computed(() =>
  extMode.value ? extItems.value.length : items.value.length,
)

/** 「显示 x–y」：空库时给 0–0，而不是负区间 */
const rangeText = computed(() => {
  if (!rowCount.value) return '0'
  return `${offset.value + 1}–${offset.value + rowCount.value}`
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
  return `清空站点 ID 库的 ${total.value} 条记录？\n\n只删「baike」表里的站点行，**外部 id（baike_ext 里的豆瓣 / TMDB）保留**；**缓存也不动**（缓存请到「缓存」分区单独清）。站点行清空后要靠后续识别 / 检索重新生长。`
})

/** 站点行的悬停全文（窄屏放不下） */
function subTitle(row: BaikeRow): string {
  const parts = [row.media_id]
  parts.push(entityLabel(entityOf(row.media_id)))
  return parts.join(' · ')
}

/** 这一行在**当前分类**下的 id（`extSource` 决定看哪一列；站点分类返回空串）。 */
function extValueOf(row: BaikeExtRow): string {
  if (extSource.value === 'douban') return row.douban
  if (extSource.value === 'tmdb') return row.tmdb
  return ''
}

/** 另一列也有值时给一句提示（它不属于当前分类，但确实是同一条记录里的）。 */
function otherExtOf(row: BaikeExtRow): string {
  if (extSource.value === 'douban' && row.tmdb) return `TMDB ${row.tmdb}`
  if (extSource.value === 'tmdb' && row.douban) return `豆瓣 ${row.douban}`
  return ''
}

/** 外部 id 行的悬停全文（名字 + 两列原始值） */
function extSubTitle(row: BaikeExtRow): string {
  const parts = [row.name, `${extLabel.value || '外部 id'} ${extValueOf(row) || '（空）'}`]
  if (row.douban && extSource.value !== 'douban') parts.push(`豆瓣 ${row.douban}`)
  if (row.tmdb && extSource.value !== 'tmdb') parts.push(`TMDB ${row.tmdb}`)
  return parts.join(' · ')
}

/** 能不能查详情：只认「已知前缀:非空 id」—— 裸豆瓣数字 id 后端也接受，这里一并放行 */
function canLookup(row: BaikeRow): boolean {
  const id = String(row.media_id || '')
  return id.includes(':') && id.split(':')[1].length > 0
}

/** 展开 / 收起（纯前端，不再请求：这一页的数据就是库里的原样） */
function toggle(key: string): void {
  opened.value = opened.value === key ? '' : key
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
  cursor.value = '' // 换了实体 / 关键词，批次游标就失效了，从头扫
  backfillTip.value = ''
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
  const wantExt = extMode.value
  loading.value = true
  error.value = ''
  try {
    // 两个分类走两个端点：站点库（media_id / name）与外部 id 表（name / douban / tmdb）
    let got = 0
    if (wantExt) {
      const data = await fetchBaikeExtList(props, {
        q: submitted.value,
        offset: offset.value,
        limit: limit.value,
        source: extSource.value,
      })
      if (seq !== token) return // 已有更新的请求在路上，丢弃这次结果
      extItems.value = data?.items || []
      items.value = []
      got = extItems.value.length
      total.value = Number(data?.total ?? got)
    } else {
      const data = await fetchBaikeList(props, {
        q: submitted.value,
        entity: entity.value,
        offset: offset.value,
        limit: limit.value,
      })
      if (seq !== token) return
      items.value = data?.items || []
      extItems.value = []
      got = items.value.length
      total.value = Number(data?.total ?? got)
    }
    // 条件变严可能导致 offset 越界：退回最后一页的起点，而不是显示「空但共 N 条」
    if (!got && total.value > 0 && offset.value > 0) {
      offset.value = Math.max(0, Math.floor((total.value - 1) / limit.value) * limit.value)
    }
  } catch (err) {
    if (seq !== token) return
    error.value = `读取 ${wantExt ? `外部 id 表（${extLabel.value}）` : '站点 ID 库'}失败：${err instanceof Error ? err.message : String(err)}`
    items.value = []
    extItems.value = []
    total.value = 0
  } finally {
    if (seq === token) {
      loading.value = false
      loaded.value = true
    }
  }
}

/**
 * 批量补豆瓣 / TMDB id：一次点按连推 5 批（每批 30 条），用游标往前挪。
 *
 * 为什么带游标：库里几千行，后端按 `media_id` 排序取「还缺 id 的行」；
 * 不带游标每次都从最小的那批开始，反复点只会补同一批（实测第二轮起豆瓣恒 +0）。
 *
 * 为什么分批：豆瓣搜索有熔断（code=103 指数退避），一口气搜几千条必然被限；
 * 后端遇限流会立刻收工回 `throttled=true`，这里如实提示「过几分钟再点」。
 */
async function backfill(): Promise<void> {
  if (backfilling.value) return
  backfilling.value = true
  backfillTip.value = ''
  error.value = ''
  // 人物**两段式**：`/baike/extids` 先按名做「唯一精确同名」直绑（不抓人物页，
  // 一条约 2 秒），只有同名多于一个时才抓人物页按作品交集消歧。
  //
  // 为什么不再用 `/baike/person_extids`：那个端点按**演职员表**批量扫，一部剧能
  // 覆盖几十人、判据也硬（同片同名），但它只覆盖「已绑豆瓣 sid 的作品」——
  // 库里演员绝大多数落在覆盖之外（实测 1560 个新站演员只绑上 88 个），而且它的
  // 游标单位是「作品」，点演员分类时提示会变成「扫了 n 部剧」，与「这一类补了
  // 多少条」对不上。演职员表批扫仍在 API 上保留，用于全库扫。
  const personScope = PERSON_ENTITIES.includes(entity.value)
  const BATCH = personScope ? 15 : 30
  const ROUNDS = personScope ? 2 : 5
  let scanned = 0
  let douban = 0
  let tmdb = 0
  let remaining = 0
  let throttled = false
  try {
    for (let round = 0; round < ROUNDS; round += 1) {
      const result = await backfillExtIds(props, {
        entity: entity.value,
        limit: BATCH,
        after: cursor.value,
      })
      scanned += result?.scanned || 0
      douban += result?.douban || 0
      tmdb += result?.tmdb || 0
      remaining = result?.remaining || 0
      const next = result?.cursor || ''
      const moved = next !== cursor.value
      cursor.value = next
      if (result?.throttled) {
        throttled = true
        break
      }
      if (!moved) break // 已经扫到库尾，下一轮会从同一处开始，没意义
    }
    const parts = personScope
      ? [`扫了 ${scanned} 个演员/人物`, `补豆瓣 ${douban}`, `补 TMDB ${tmdb}`, `剩余待补 ${remaining}`]
      : [`扫了 ${scanned} 条`, `补豆瓣 ${douban}`, `补 TMDB ${tmdb}`, `剩余待补 ${remaining}`]
    backfillTip.value =
      parts.join(' · ') +
      (throttled ? '（豆瓣风控，等 10 分钟以上再点）' : remaining > 0 ? '（再点一次继续往后扫）' : '')
    await load()
    await loadStatus()
  } catch (err) {
    error.value = `批量补 id 失败：${err instanceof Error ? err.message : String(err)}`
  } finally {
    backfilling.value = false
  }
}

/** 点行上的垃圾桶 */
function askDelete(row: BaikeRow): void {  pending.value = row
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
    // 条数变了，chips 的计数与「分类清单」都要跟着走，再重读当前页
    await loadStatus()
    await load()
  } catch (err) {
    error.value = `操作失败：${err instanceof Error ? err.message : String(err)}`
  } finally {
    purging.value = false
  }
}

/** 面板整页刷新：分类条数 + 列表一起重读（外壳切到本分区时调） */
async function refresh(): Promise<void> {
  await loadStatus()
  await load()
}

/** 给外壳的出口：外部切到本分区时可直接刷新 */
defineExpose({ reload: refresh })

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
  void loadStatus()
  void load()
})

onBeforeUnmount(() => {
  window.clearTimeout(timer)
})
</script>
