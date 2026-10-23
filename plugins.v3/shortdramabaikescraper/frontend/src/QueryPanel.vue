<template>
  <!--
    分区 ④：查询（`/lookup`）。

    一个输入框，两种语义，由**后端**判断，面板只负责把用户的意图分派过去：

      · 形如 `duanju:7696405989787978814` / `douban:36902559` / 裸豆瓣数字 id
        → 按 `media_id` 直查单条详情（先缓存后抓页）；
      · 其它一律当名字 → 走 `name` 分支出候选列表（作品 + 演员），
        `remote=1` 才出网补全（站内搜索 → 豆瓣）。

    「原始响应」区块给的是**未拆信封**的那份 JSON：面板上渲染的是投影字段，
    而 `success` / `message` / 候选的原始键只有原文里看得到 —— 排障看这个。
  -->
  <div class="sdbs-page">
    <v-alert v-if="error" type="error" variant="tonal" density="compact" class="mb-2">
      {{ error }}
    </v-alert>

    <div class="sdbs-searchbox">
      <v-text-field
        v-model="keyword"
        class="sdbs-search"
        variant="outlined"
        density="compact"
        hide-details
        clearable
        prepend-inner-icon="mdi-magnify"
        placeholder="media_id（duanju:769…）或剧名 / 演员名，例如：以爱为家"
        @keydown.enter="submitSearch()"
      />
      <v-btn
        class="sdbs-search-btn"
        size="small"
        color="primary"
        variant="tonal"
        :loading="loading"
        :disabled="!canSubmit"
        @click="submitSearch()"
      >
        查询
      </v-btn>
    </div>

    <!-- 选项行：是否联网、只看作品 / 只看人物 -->
    <div class="sdbs-actions mt-2">
      <v-switch
        v-model="remote"
        class="sdbs-switch"
        color="primary"
        density="compact"
        hide-details
        label="联网补全"
        :disabled="byId"
        :title="byId ? '按 media_id 直查本来就会按需抓页，这个开关只影响按名搜索' : '勾上才走站内搜索 / 豆瓣（会出网）'"
      />
      <v-btn-toggle
        v-model="type"
        class="sdbs-toggle"
        density="compact"
        variant="text"
        divided
        mandatory
        :disabled="byId"
        @update:model-value="hasResult && run()"
      >
        <v-btn size="x-small" value="">全部</v-btn>
        <v-btn size="x-small" value="work">作品</v-btn>
        <v-btn size="x-small" value="person">人物</v-btn>
      </v-btn-toggle>
      <v-spacer />
      <span class="text-caption sdbs-dim">
        {{ byId ? '按 id 直查（命中缓存则零请求）' : '按名字搜索候选' }}
      </span>
    </div>

    <!-- 点进来的回路：导航栈支持多层跳转（详情→原著→改编作品→…），每层都能返回 -->
    <div v-if="navStack.length" class="sdbs-actions mb-2 mt-2">
      <v-btn
        size="small"
        variant="tonal"
        color="primary"
        prepend-icon="mdi-arrow-left"
        @click="goBack()"
      >
        返回「{{ navStack[navStack.length - 1].name || navStack[navStack.length - 1].id }}」
      </v-btn>
      <span class="text-caption sdbs-dim">
        {{ person ? '正在看人物档案' : novel ? '正在看原著档案' : '正在看作品详情' }}
        <template v-if="navStack.length > 1">· 还有 {{ navStack.length - 1 }} 层可返回</template>
      </span>
    </div>

    <!-- 结果：人物档案（人物不是 MediaInfo，走 /person） -->
    <template v-if="person">
      <div class="sdbs-section">
        <v-icon icon="mdi-account-star-outline" size="16" />
        <span>人物档案</span>
        <v-spacer />
        <v-btn
          size="x-small"
          variant="text"
          prepend-icon="mdi-content-duplicate"
          @click="copy(JSON.stringify(person, null, 2))"
        >
          复制 JSON
        </v-btn>
        <v-btn
          size="x-small"
          variant="text"
          color="primary"
          prepend-icon="mdi-open-in-new"
          :href="person.detail_url || undefined"
          target="_blank"
          rel="noreferrer noopener"
          :disabled="!person.detail_url"
        >
          站点页面
        </v-btn>
      </div>

      <v-card variant="outlined" class="pa-3">
        <div class="d-flex" style="gap: 12px">
          <div
            class="sdbs-avatar-box"
            :style="person.avatar ? { backgroundImage: `url(${proxyImage(person.avatar)})` } : undefined"
          />
          <div style="flex: 1 1 auto; min-width: 0">
            <div class="text-subtitle-1 d-flex align-center flex-wrap" style="gap: 8px">
              <span>{{ person.name }}</span>
              <span class="sdbs-tag">{{ person.role }}</span>
              <span class="text-caption sdbs-dim">作品 {{ person.work_count }} 部</span>
            </div>
            <div class="sdbs-row-sub mt-1" style="padding-inline-start: 0" :title="person.media_id">
              <span class="sdbs-key">{{ person.media_id }}</span>
              <span v-if="person.douban_id" class="sdbs-key">· {{ person.douban_id }}</span>
            </div>
            <div v-if="person.douban_info?.length" class="text-caption sdbs-dim mt-1" style="padding-inline-start: 0">
              {{ person.douban_info.join('　') }}
            </div>
            <div v-if="person.intro" class="text-body-2 sdbs-clamp mt-2 sdbs-pre">
              {{ person.intro }}
            </div>
          </div>
        </div>
      </v-card>

      <template v-if="person.works?.length">
        <div class="sdbs-section mt-3">
          <v-icon icon="mdi-movie-multiple-outline" size="16" />
          <span>作品</span>
          <span class="sdbs-count">{{ person.works.length }}</span>
          <v-spacer />
          <span class="text-caption sdbs-dim">点海报查这部片的详情 · 含豆瓣合并来源（角标「豆瓣」）</span>
        </div>
        <!-- 海报网格（不用列表）：与探索页/候选卡同一套视觉 -->
        <div class="sdbs-grid">
          <div
            v-for="work in person.works"
            :key="work.media_id"
            class="sdbs-item sdbs-card"
            :title="`${work.name || work.media_id}${work.date ? ' · ' + work.date : work.year ? ' · ' + work.year : ''}${work.episodes ? ' · ' + work.episodes + ' 集' : ''}`"
            @click="openWork(work)"
          >
            <div
              class="sdbs-poster"
              :style="work.poster ? { backgroundImage: `url(${proxyImage(work.poster)})` } : undefined"
            >
              <span v-if="work.episodes" class="sdbs-mark">{{ work.episodes }} 集</span>
              <span v-else-if="work.rating" class="sdbs-mark">{{ Number(work.rating).toFixed(1) }}</span>
            </div>
            <div class="sdbs-card-title">{{ work.name || work.media_id }}</div>
            <div class="sdbs-card-sub">
              <span v-if="work.origin === 'douban'" class="sdbs-badge-douban">豆瓣</span>
              {{ work.date || work.year || work.kind || '—' }}
            </div>
            <div class="sdbs-card-meta">{{ (work.tags || []).slice(0, 2).join(' / ') || ' ' }}</div>
          </div>
        </div>
      </template>
    </template>

    <!-- 结果：原著档案（改编档案）。原著是"一本书"，与人物一样不是 MediaInfo -->
    <template v-else-if="novel">
      <div class="sdbs-section">
        <v-icon icon="mdi-book-open-variant" size="16" />
        <span>原著档案</span>
        <v-spacer />
        <v-btn
          size="x-small"
          variant="text"
          prepend-icon="mdi-content-duplicate"
          @click="copy(JSON.stringify(novel, null, 2))"
        >
          复制 JSON
        </v-btn>
        <v-btn
          size="x-small"
          variant="text"
          color="primary"
          prepend-icon="mdi-open-in-new"
          :href="novel.detail_url || undefined"
          target="_blank"
          rel="noreferrer noopener"
          :disabled="!novel.detail_url"
        >
          站点页面
        </v-btn>
      </div>

      <v-card variant="outlined" class="pa-3">
        <div class="d-flex" style="gap: 12px">
          <div
            class="sdbs-avatar-box"
            :style="novel.poster ? { backgroundImage: `url(${proxyImage(novel.poster)})` } : undefined"
          />
          <div style="flex: 1 1 auto; min-width: 0">
            <div class="text-subtitle-1 d-flex align-center flex-wrap" style="gap: 8px">
              <span>《{{ novel.name }}》</span>
              <span class="sdbs-tag">{{ novel.kind }}</span>
            </div>
            <div class="sdbs-row-sub mt-1" style="padding-inline-start: 0" :title="novel.media_id">
              <span class="sdbs-key">{{ novel.media_id }}</span>
              <span v-if="novel.author"> · 作者：{{ novel.author }}</span>
              <span v-if="novel.words"> · {{ novel.words }}</span>
            </div>
            <div v-if="novel.aka" class="text-caption sdbs-dim mt-1" style="padding-inline-start: 0">
              又名：《{{ novel.aka }}》
            </div>
            <div v-if="novel.overview" class="text-body-2 sdbs-clamp mt-2 sdbs-pre">
              {{ novel.overview }}
            </div>
          </div>
        </div>
      </v-card>

      <template v-if="novel.adaptations?.length">
        <div class="sdbs-section mt-3">
          <v-icon icon="mdi-movie-multiple-outline" size="16" />
          <span>改编作品</span>
          <span class="sdbs-count">{{ novel.adaptation_count || novel.adaptations.length }}</span>
          <v-spacer />
          <span class="text-caption sdbs-dim">改编自本原著的剧，点海报看详情</span>
        </div>
        <div class="sdbs-grid">
          <div
            v-for="work in novel.adaptations"
            :key="work.media_id"
            class="sdbs-item sdbs-card"
            :title="`${work.name || work.media_id}${work.date ? ' · ' + work.date : ''}${work.episodes ? ' · ' + work.episodes + ' 集' : ''}`"
            @click="openAdaptation(work)"
          >
            <div
              class="sdbs-poster"
              :style="work.poster ? { backgroundImage: `url(${proxyImage(work.poster)})` } : undefined"
            >
              <span v-if="work.episodes" class="sdbs-mark">{{ work.episodes }} 集</span>
            </div>
            <div class="sdbs-card-title">{{ work.name || work.media_id }}</div>
            <div class="sdbs-card-sub">{{ work.date || work.kind || '—' }}</div>
            <div class="sdbs-card-meta">{{ work.kind || ' ' }}</div>
          </div>
        </div>
      </template>
    </template>

    <!-- 结果：单条详情 -->
    <template v-else-if="single">
      <div class="sdbs-section">
        <v-icon icon="mdi-movie-open-outline" size="16" />
        <span>详情</span>
        <v-spacer />
        <v-btn
          size="x-small"
          variant="text"
          prepend-icon="mdi-content-duplicate"
          @click="copy(JSON.stringify(single, null, 2))"
        >
          复制 JSON
        </v-btn>
        <v-btn
          size="x-small"
          variant="text"
          color="primary"
          prepend-icon="mdi-open-in-new"
          :disabled="!detailHref"
          title="在宿主的媒体详情页打开（新标签）"
          :href="detailHref || undefined"
          target="_blank"
          rel="noreferrer noopener"
        >
          宿主详情页
        </v-btn>
        <!-- 改编档案：站点页面标注了原著才显示（novelOfSingle 由详情加载后探测） -->
        <v-btn
          v-if="novelOfSingle"
          size="x-small"
          variant="tonal"
          color="primary"
          prepend-icon="mdi-book-open-variant"
          :loading="novelLoading"
          @click="openNovelOfSingle()"
        >
          改编档案
        </v-btn>
      </div>

      <v-card variant="outlined" class="pa-3">
        <div class="d-flex" style="gap: 12px">
          <div
            class="sdbs-poster"
            style="flex: 0 0 auto; width: 104px"
            :style="single.poster_path ? { backgroundImage: `url(${proxyImage(single.poster_path)})` } : undefined"
          >
            <span v-if="single.vote_average" class="sdbs-mark">{{ Number(single.vote_average).toFixed(1) }}</span>
          </div>
          <div style="flex: 1 1 auto; min-width: 0">
            <div class="text-subtitle-1">{{ single.title || '（无标题）' }}</div>
            <div class="sdbs-meta" style="margin: 4px 0 6px">
              <span v-if="single.year" class="sdbs-meta-item">
                <v-icon size="14" icon="mdi-calendar" />{{ single.year }}
              </span>
              <span v-if="single.number_of_episodes" class="sdbs-meta-item">
                <v-icon size="14" icon="mdi-playlist-play" />{{ single.number_of_episodes }} 集
              </span>
              <span v-if="single.type" class="sdbs-meta-item">
                <v-icon size="14" icon="mdi-tag-outline" />{{ single.type }}
              </span>
            </div>
            <div class="sdbs-row-sub" style="padding-inline-start: 0" :title="single.media_id || ''">
              <span class="sdbs-key">{{ single.media_id || '—' }}</span>
              <span v-if="single.douban_id"> · 豆瓣 {{ single.douban_id }}</span>
              <span v-if="single.tmdb_id"> · TMDB {{ single.tmdb_id }}</span>
            </div>
            <!--
              站内指标：宿主 MediaInfo 没有「热度 / 播放 / 收藏」列，
              后端把它们挂在 classification_facts 上带出来，值是站点原串（989万）。
            -->
            <div v-if="metricList.length" class="sdbs-chips mt-1">
              <span
                v-for="metric in metricList"
                :key="metric.key"
                class="sdbs-metric"
                :title="metric.key"
              >
                <v-icon size="12" :icon="metric.icon" />{{ metric.label }} {{ metric.value }}
              </span>
            </div>
            <div v-if="genreList.length" class="sdbs-chips mt-2">
              <span v-for="genre in genreList" :key="genre" class="sdbs-tag">{{ genre }}</span>
            </div>
            <div v-if="single.overview" class="text-body-2 sdbs-clamp mt-2 sdbs-pre">
              {{ single.overview }}
            </div>
            <!-- 演职人员：带 media_id 的可直接点进人物档案（人物不是 MediaInfo，走 /person） -->
            <div v-if="directorLinks.length" class="sdbs-credit-row">
              <span class="sdbs-credit-label">导演</span>
              <span
                v-for="(credit, index) in directorLinks"
                :key="`director-${index}-${credit.label}`"
                class="sdbs-credit"
                :class="{ 'sdbs-credit-click': credit.mediaId }"
                :title="credit.mediaId || '站点未给出人物页链接'"
                @click="openPerson(credit.mediaId)"
              >{{ credit.label }}</span>
            </div>
            <div v-if="actorLinks.length" class="sdbs-credit-row">
              <span class="sdbs-credit-label">演员</span>
              <span
                v-for="(credit, index) in actorLinks"
                :key="`actor-${index}-${credit.label}`"
                class="sdbs-credit"
                :class="{ 'sdbs-credit-click': credit.mediaId }"
                :title="credit.mediaId || '站点未给出人物页链接'"
                @click="openPerson(credit.mediaId)"
              >{{ credit.label }}</span>
            </div>
          </div>
        </div>
      </v-card>
    </template>

    <!-- 结果：候选列表 -->
    <template v-else-if="list.length">
      <div class="sdbs-section">
        <v-icon icon="mdi-format-list-bulleted" size="16" />
        <span>候选</span>
        <span class="sdbs-count">{{ list.length }}</span>
        <v-spacer />
        <span class="text-caption sdbs-dim">同名多条原样列出，识别时才按规则收敛</span>
      </div>
      <div class="sdbs-grid">
        <div
          v-for="item in list"
          :key="item.media_id || item.title"
          class="sdbs-item"
          style="cursor: pointer"
          :title="item.media_id || ''"
          @click="pick(item)"
        >
          <div
            class="sdbs-poster"
            :style="item.poster_path ? { backgroundImage: `url(${proxyImage(item.poster_path)})` } : undefined"
          >
            <span v-if="item.vote_average" class="sdbs-mark">{{ Number(item.vote_average).toFixed(1) }}</span>
          </div>
          <div class="sdbs-card-title">{{ item.title || '（无标题）' }}</div>
          <div class="sdbs-card-sub">
            {{ [item.year, item.number_of_episodes ? `${item.number_of_episodes} 集` : ''].filter(Boolean).join(' · ') || '—' }}
          </div>
          <div class="sdbs-card-meta">{{ item.media_id || '' }}</div>
        </div>
      </div>
    </template>

    <div v-else-if="hasResult && !loading" class="sdbs-empty">
      <v-icon size="26" icon="mdi-magnify-close" />
      <span>
        没有结果。按名搜索时：{{ remote ? '本地 → 站内搜索 → 豆瓣都没命中' : '只查了本地库，把「联网补全」打开可再试站内搜索' }}
      </span>
      <!-- 把接口实际回来的形态摊在这里：万一宿主换了响应封装，一眼能看出来，
           不用打开开发者工具猜是「接口没数据」还是「前端没解析对」 -->
      <span class="text-caption sdbs-dim">接口返回：{{ rawSummary }}</span>
    </div>

    <div v-else-if="!hasResult" class="sdbs-empty">
      <v-icon size="26" icon="mdi-magnify" />
      <span>输入 media_id 查单条详情，或输入剧名 / 演员名出候选</span>
    </div>

    <!-- 原始响应：未拆信封的全文 -->
    <v-expansion-panels v-if="rawPayload" variant="accordion" class="mt-3">
      <v-expansion-panel>
        <v-expansion-panel-title class="text-caption">
          原始响应（含 success / message 信封）
        </v-expansion-panel-title>
        <v-expansion-panel-text>
          <div class="sdbs-actions">
            <v-btn
              size="x-small"
              variant="text"
              prepend-icon="mdi-content-duplicate"
              @click="copy(rawText)"
            >
              复制全文
            </v-btn>
            <v-btn size="x-small" variant="text" prepend-icon="mdi-code-json" @click="copy(rawText)">
              {{ rawSize }}
            </v-btn>
          </div>
          <pre class="sdbs-raw">{{ rawText }}</pre>
        </v-expansion-panel-text>
      </v-expansion-panel>
    </v-expansion-panels>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { envelopeOf, fetchNovel, fetchPerson, lookupByMediaId, lookupByName, lookupRaw, proxyImage } from './api'
import { factIcon, factLabel, isPersonId, METRIC_FACTS } from './constants'
import type { MediaInfo, NovelPayload, NovelWork, PersonPayload, PersonWork, PluginApi } from './types'

const props = defineProps<{
  /** 宿主注入的 axios 实例 */
  api?: PluginApi
}>()

const keyword = ref('')
/**
 * 「按 id 查询」的实际目标；非空时 `run()` 走 `/lookup?media_id=`。
 *
 * 为什么要和 `keyword` 分开：点候选卡 / 作品海报 / 演职人员时，用户想看到的是**名字**
 * （「移巢」「王格格」），但真正要查的是 `duanju:7670…`。以前直接把 id 写进输入框，
 * 搜完框里全是 id，看不出自己刚才搜的什么（用户 23:04 反馈）。
 */
const activeId = ref('')
const loading = ref(false)
const error = ref('')
/** 是否搜过一次（没搜过不占位、不显示空态） */
const hasResult = ref(false)
/** 联网开关（只影响按名搜索） */
const remote = ref(true)
/** 类型过滤：'' / work / person */
const type = ref('')

const single = ref<MediaInfo | null>(null)
const list = ref<MediaInfo[]>([])
/** 人物档案（人物不是 MediaInfo，只能走 `/person`） */
const person = ref<PersonPayload | null>(null)
/** 原著档案（改编档案；与人物一样不是 MediaInfo，走 `/novel`） */
const novel = ref<NovelPayload | null>(null)
/** 当前详情的原著档案：详情加载后探测，非空才显示「改编档案」按钮 */
const novelOfSingle = ref<NovelPayload | null>(null)
const novelLoading = ref(false)
/**
 * 导航栈：详情 ⇄ 原著 ⇄ 人物 ⇄ 作品 可以反复横跳，每一跳前把**当前视图**
 * 压栈，「返回」出栈一层还原 —— 所以多次点击都能层层退回。
 * 栈里存 id + 名字即可：作品 / 原著 / 人物都能按 id 重新取（命中缓存零请求），
 * 不必像旧版那样整份暂存组件状态。
 */
interface NavEntry {
  kind: 'person' | 'novel' | 'work'
  id: string
  name: string
  /** 进入该视图时已加载好的快照；返回时直接还原，避免重新拉取偶发失败（如原著页抓取超时）。 */
  payload?: NovelPayload | PersonPayload | MediaInfo
}
const navStack = ref<NavEntry[]>([])
const rawPayload = ref<any>(null)

/**
 * 输入的是不是 media_id。
 *
 * 判据（与后端 `api_lookup` 一致）：含冒号（`{entity}:{id}`）或是**纯数字**
 * （裸豆瓣 subject id，后端也接受）。不在这里校验实体前缀是否合法 ——
 * 那属于后端的 `is_known()`，面板越权判断反而会把「新实体」拦在门外。
 */
const byId = computed(() => {
  // 点卡片进来的：目标已确定是 id（输入框里显示的是名字）
  if (activeId.value) return true
  const text = keyword.value.trim()
  if (!text) return false
  return text.includes(':') || /^\d+$/.test(text)
})

const canSubmit = computed(() => Boolean(keyword.value.trim()) && !loading.value)


/**
 * 演职 / 分类条目的最小形状（宿主 `MediaCredit` / `MediaGenre`）。
 *
 * 宿主 `/lookup` 给的是对象数组，但渲染层同时兼容字符串形态（换实现时不至于炸）。
 */
type CreditLike = { name?: string; character?: string; job?: string; url?: string } | string

/** 分类名数组（只取 `name`，去重保序） */
function genreNames(items: CreditLike[] | undefined): string[] {
  const seen = new Set<string>()
  const out: string[] = []
  for (const item of items || []) {
    const name = typeof item === 'string' ? item.trim() : String(item?.name || '').trim()
    if (!name || seen.has(name)) continue
    seen.add(name)
    out.push(name)
  }
  return out
}

const genreList = computed(() => genreNames(single.value?.genres))

/**
 * 站内指标（热度 / 播放 / 收藏）。
 *
 * 这三项宿主 `MediaInfo` 没有对应列，后端挂在 `classification_facts` 上；
 * **值是站点原串**（`989万`） —— 面板原样显示，不折算、不排序、不参与比较。
 * 「面板只做展示」的纪律在这里就是：不把 `989万` 再加工成 9890000。
 */
interface MetricChip {
  key: string
  label: string
  value: string
  icon: string
}

const metricList = computed<MetricChip[]>(() => {
  const facts = single.value?.classification_facts || {}
  const out: MetricChip[] = []
  for (const key of METRIC_FACTS) {
    const raw = facts[key]
    const text = typeof raw === 'string' ? raw.trim() : raw === null || raw === undefined ? '' : String(raw)
    if (!text) continue
    out.push({ key, label: factLabel(key), value: text, icon: factIcon(key) })
  }
  return out
})

/**
 * 演职条目 → 可点 chip。
 *
 * `/lookup` 返回的 `MediaCredit` **没有 media_id 字段**，只有站点链接
 * `url`（`https://www.duanjubaike.net/yanyuan/info-7411422549579420953.html`），
 * 所以人物的 `media_id` 得从 url 反推；反推不出来就退化成纯文本（不假装可点）。
 */
interface CreditChip {
  label: string
  mediaId: string
}

function personIdFromUrl(url: string): string {
  const matched = /[/](yanyuan|daoyan|bianju)\/info-(\d+)\.html/.exec(url || '')
  return matched ? `${matched[1]}:${matched[2]}` : ''
}

function creditChips(items: CreditLike[] | undefined, withRole = false, limit = 0): CreditChip[] {
  const list = items || []
  const picked = limit > 0 ? list.slice(0, limit) : list
  return picked
    .map((item) => {
      if (!item) return null
      if (typeof item === 'string') {
        const label = item.trim()
        return label ? { label, mediaId: '' } : null
      }
      const name = String(item.name || '').trim()
      if (!name) return null
      const role = String(item.character || '').trim()
      return {
        label: withRole && role ? `${name}（${role}）` : name,
        mediaId: personIdFromUrl(String(item.url || '')),
      }
    })
    .filter((chip): chip is CreditChip => Boolean(chip && chip.label))
}

const directorLinks = computed(() => creditChips(single.value?.directors))
const actorLinks = computed(() => creditChips(single.value?.actors, true, 12))

/** 当前视图对应的栈条目（候选列表 / 空态不可返回，返回 null） */
function currentEntry(): NavEntry | null {
  if (person.value)
    return { kind: 'person', id: person.value.media_id, name: person.value.name, payload: person.value }
  if (novel.value)
    return { kind: 'novel', id: novel.value.media_id, name: novel.value.name, payload: novel.value }
  if (single.value?.media_id) {
    return {
      kind: 'work',
      id: String(single.value.media_id),
      name: String(single.value.title || ''),
      payload: single.value,
    }
  }
  return null
}

/** 跳走之前把当前视图压栈（同一条目不重复压） */
function pushNav(): void {
  const entry = currentEntry()
  if (!entry?.id) return
  const top = navStack.value[navStack.value.length - 1]
  if (top && top.id === entry.id) return
  navStack.value.push(entry)
}

/** 返回上一层：出栈一条，优先用快照直接还原（零网络、不会失败）；
 *  快照缺失（理论上不会发生）再回退到重新拉取。 */
function goBack(): void {
  const entry = navStack.value.pop()
  if (!entry) return
  error.value = ''
  activeId.value = entry.id
  keyword.value = entry.name || entry.id
  if (entry.kind === 'person') {
    if (entry.payload) {
      person.value = entry.payload as PersonPayload
      single.value = null
      novel.value = null
      novelOfSingle.value = null
      list.value = []
      rawPayload.value = null
      hasResult.value = true
    } else {
      void loadPerson(entry.id)
    }
    return
  }
  if (entry.kind === 'novel') {
    if (entry.payload) {
      novel.value = entry.payload as NovelPayload
      person.value = null
      single.value = null
      novelOfSingle.value = null
      list.value = []
      rawPayload.value = null
      hasResult.value = true
    } else {
      void loadNovel(entry.id)
    }
    return
  }
  // 作品：有快照直接还原，并静默重探原著（点亮「改编档案」按钮）；无快照走 /lookup
  if (entry.payload) {
    single.value = entry.payload as MediaInfo
    person.value = null
    novel.value = null
    novelOfSingle.value = null
    list.value = []
    rawPayload.value = null
    hasResult.value = true
    if (single.value?.media_id) void probeNovel(single.value.media_id)
  } else {
    void run()
  }
}

/** 点演职人员 → 直接切到人物档案（不重新按名搜索，直接按 media_id 走 /person） */
function openPerson(mediaId: string): void {
  if (!mediaId) return
  pushNav()
  // 不往输入框写 id：等 /person 回来后由 loadPerson 回填人物名
  activeId.value = mediaId
  void loadPerson(mediaId)
}

const rawText = computed(() => {
  try {
    return JSON.stringify(rawPayload.value, null, 2)
  } catch {
    return String(rawPayload.value)
  }
})

const rawSize = computed(() => `${rawText.value.length} 字符`)

/**
 * 接口回来的东西长什么样（空态里显示）。
 *
 * 三种宿主封装都可能：数组（已解包到 data）、`{success,message,data}` 信封、
 * 或者别的对象。空结果时把形态写出来，排查「没数据」还是「没解析对」不用开控制台。
 */
const rawSummary = computed(() => {
  const body = rawPayload.value
  if (body === null || body === undefined) return '无响应'
  if (Array.isArray(body)) return `数组 ${body.length} 条（已解包）`
  if (typeof body === 'object') {
    const record = body as Record<string, any>
    if ('success' in record && 'data' in record) {
      const data = record.data
      const size = Array.isArray(data) ? `${data.length} 条` : data === null ? 'null' : typeof data
      return `信封 success=${String(record.success)} data=${size}`
    }
    return `对象（键：${Object.keys(record).slice(0, 4).join(',') || '空'}）`
  }
  return `原始值 ${String(body)}`
})

/** 宿主媒体详情页地址（hash 路由）：短剧在宿主里归入电视剧 */
const detailHref = computed(() => {
  const item = single.value
  if (!item?.media_id) return ''
  const query = new URLSearchParams()
  query.set('media_source', 'djbaike')
  query.set('media_id', item.media_id)
  query.set('type', '电视剧')
  query.set('title', item.title || '')
  const base = typeof window === 'undefined' ? '' : window.location.href.split('#')[0]
  return `${base}#/media?${query.toString()}`
})

async function copy(text: string): Promise<void> {
  try {
    await navigator.clipboard.writeText(text)
  } catch {
    error.value = '复制失败：浏览器拒绝了剪贴板权限'
  }
}

/**
 * 回车 / 点「查询」：这是一次**新的检索**，此前的导航栈作废。
 * （作品卡点进来的那次走 `run()` 直连，不经过这里，所以不会误清。）
 */
function submitSearch(): void {
  // 手动检索（回车 / 点「查询」）＝以框里的文字为准，之前"点卡片定的 id"作废
  activeId.value = ''
  navStack.value = []
  void run()
}

/** 点候选卡：人物走档案端点，作品走 `/lookup?media_id=`（输入框显示名字，不显示 id） */
function pick(item: MediaInfo): void {
  const id = String(item.media_id || '')
  if (!id) return
  const name = String(item.title || '').trim()
  if (isPersonId(id)) {
    pushNav()
    activeId.value = id
    keyword.value = name || id
    void loadPerson(id)
    return
  }
  pushNav()
  activeId.value = id
  keyword.value = name || id
  void run()
}

/** 作品卡（人物 / 原著档案里点进来的）：记住来处 → 按 media_id 直查详情 */
function openWork(work: PersonWork): void {
  if (!work.media_id) return
  pushNav()
  person.value = null
  novel.value = null
  activeId.value = work.media_id
  keyword.value = String(work.name || '').trim() || work.media_id
  void run()
}

/** 原著档案的改编作品卡：同 openWork，只是入参形状不同 */
function openAdaptation(work: NovelWork): void {
  if (!work.media_id) return
  pushNav()
  person.value = null
  novel.value = null
  activeId.value = work.media_id
  keyword.value = String(work.name || '').trim() || work.media_id
  void run()
}

/**
 * 取原著档案（`/novel`）：传剧 id 时后端先取详情里的原著链接，再抓原著页。
 * 与 loadPerson 一样单独一条链路：原著不是 MediaInfo。
 */
async function loadNovel(mediaId: string): Promise<void> {
  loading.value = true
  error.value = ''
  novel.value = null
  person.value = null
  single.value = null
  novelOfSingle.value = null
  list.value = []
  rawPayload.value = null
  try {
    const result = await fetchNovel(props, mediaId)
    if (result.novel) {
      novel.value = result.novel
      // 输入框显示书名，真正的查询目标仍是 media_id（点改编作品 / 返回都靠它）
      keyword.value = String(result.novel.name || '').trim() || mediaId
      activeId.value = mediaId
    } else {
      // 兜底路径（返回原著档案时快照缺失才走到这）：给中性文案，**绝不透传后端
      // message**——「页面未标注原著」只对「剧→原著探测」语义成立，对「回到原著
      // 档案」是误导（原著档案之前明明显示过）。真无原著的剧走静默探测，不到这。
      error.value = `原著档案加载失败：${mediaId}`
    }
    hasResult.value = true
  } catch (err) {
    error.value = `查询失败：${err instanceof Error ? err.message : String(err)}`
    hasResult.value = true
  } finally {
    loading.value = false
  }
}

/** 点详情页的「改编档案」按钮：档案在详情加载时已探测好，这里直接展示 */
function openNovelOfSingle(): void {
  const target = novelOfSingle.value
  if (!target) return
  pushNav()
  novel.value = target
  person.value = null
  single.value = null
  rawPayload.value = null
  keyword.value = String(target.name || '').trim() || target.media_id
  activeId.value = target.media_id
  hasResult.value = true
}

/**
 * 详情加载后探测原著档案（点亮「改编档案」按钮）。
 *
 * 后端 `/novel` 里剧详情与原著页都有缓存，多数情况零网络；失败静默落 null
 * —— 探测不出来等同于「页面没标原著」，按钮不亮即可，不该打扰详情展示。
 */
async function probeNovel(mediaId: string): Promise<void> {
  novelLoading.value = true
  try {
    const result = await fetchNovel(props, mediaId)
    // 竞态防护：详情已经切走了就丢弃这次结果
    if (single.value?.media_id === mediaId) {
      novelOfSingle.value = result.novel
    }
  } catch {
    // 静默
  } finally {
    novelLoading.value = false
  }
}

/**
 * 取人物档案。
 *
 * 为什么单独一条链路：人物不是「一部片」，宿主的 `MediaInfo` 装不下它；
 * 后端 `/lookup?media_id=yanyuan:…` 会明确回「人物档案请用 /person 查询」，
 * 所以面板必须先按前缀分派，别让用户看到一个空结果。
 */
async function loadPerson(mediaId: string): Promise<void> {
  loading.value = true
  error.value = ''
  person.value = null
  novel.value = null
  novelOfSingle.value = null
  single.value = null
  list.value = []
  rawPayload.value = null
  try {
    const result = await fetchPerson(props, mediaId)
    if (result.person) {
      person.value = result.person
      // 输入框显示人物名，真正的查询目标仍是 media_id（点作品/返回都靠它）
      keyword.value = String(result.person.name || '').trim() || mediaId
      activeId.value = mediaId
    } else {
      error.value = result.message || `取不到人物档案：${mediaId}`
    }
    hasResult.value = true
  } catch (err) {
    error.value = `人物档案读取失败：${err instanceof Error ? err.message : String(err)}`
    hasResult.value = true
  } finally {
    loading.value = false
  }
}

/** 执行查询：一次请求，同时留一份原始响应 */
async function run(): Promise<void> {
  // 点卡片进来的走 activeId（输入框里是名字）；手动输入的走输入框文字
  const text = (activeId.value || keyword.value).trim()
  if (!text) return
  // 人物 id（`yanyuan:…`）走档案端点
  if (isPersonId(text)) {
    await loadPerson(text)
    return
  }
  loading.value = true
  error.value = ''
  single.value = null
  list.value = []
  person.value = null
  novel.value = null
  novelOfSingle.value = null
  try {
    if (byId.value) {
      const body = await lookupRaw(props, { media_id: text })
      rawPayload.value = body
      // 不假设宿主替我们拆过信封：统一用 envelopeOf 归一（两种宿主形态都正确）
      const payload = envelopeOf(body)
      const data = payload.data
      if (Array.isArray(data)) {
        // 后端按 id 查返回单条；万一将来改成列表，也不至于「有数据却空白」
        single.value = (data[0] ?? null) as MediaInfo | null
      } else {
        single.value = data && typeof data === 'object' ? (data as MediaInfo) : null
      }
      if (!single.value && payload.success === false) {
        error.value = String(payload.message || '查询失败')
      }
      // 详情就绪后探测原著：站点页面标注了原著才亮「改编档案」按钮。
      // 失败/无原著都静默落 null，不打扰详情展示。
      if (single.value?.media_id) {
        void probeNovel(single.value.media_id)
      }
    } else {
      const body = await lookupRaw(props, {
        name: text,
        remote: remote.value ? 1 : 0,
        type: type.value,
      })
      rawPayload.value = body
      const payload = envelopeOf(body)
      const data = payload.data
      const rows = Array.isArray(data) ? (data as MediaInfo[]) : []
      // 按名查询时后端永远返回候选列表；只有一条也照列表展示（识别收敛是宿主的事）
      list.value = rows
      if (!rows.length && payload.success === false) {
        error.value = String(payload.message || '查询失败')
      }
      // 兜底：极少数情况下后端给出单条对象（未来换实现），也认
      if (!rows.length && data && !Array.isArray(data) && typeof data === 'object') {
        single.value = data as MediaInfo
      }
    }
    hasResult.value = true
  } catch (err) {
    error.value = `查询失败：${err instanceof Error ? err.message : String(err)}`
    hasResult.value = true
  } finally {
    loading.value = false
  }
}

/** 给外壳的出口：ID 库点「查详情」时由外壳调 `query(mediaId)` */
defineExpose({
  query(mediaId: string): void {
    keyword.value = mediaId
    activeId.value = ''
    navStack.value = []
    void run()
  },
})

// 保留两个未被模板直接使用的导出，避免 TS「声明未使用」误报：
// `lookupByMediaId` / `lookupByName` 是给外部（未来的自动化）留的便捷封装，
// 面板内部统一走 `lookupRaw` 以便同时留原文。
void lookupByMediaId
void lookupByName
</script>
