<template>
  <v-card variant="outlined" class="pa-4">
    <div class="d-flex align-center mb-3">
      <v-icon icon="mdi-television-classic" class="mr-2" />
      <h3 class="ma-0">短剧百科数据源 · 设置</h3>
      <v-spacer />
      <v-btn icon="mdi-close" variant="text" size="small" title="关闭" @click="emit('close')" />
    </div>

    <v-alert type="info" variant="tonal" density="compact" class="mb-3">
      本插件把 <b>duanjubaike.org</b> 注册成 MoviePilot 的一等媒体数据源（与 TMDB / 豆瓣同级），
      补齐 TMDB、豆瓣上没有条目的短剧。站内检索被 Cloudflare 挡住、目录页已弃用，
      片名与演员名 → ID 都走<b>站外索引</b>（搜索引擎的 <code>site:</code> 限定检索），
      因此这里没有「抓取配额」类配置 —— 正常使用不会触发站点风控。
    </v-alert>

    <v-progress-linear v-if="loading" indeterminate color="primary" class="mb-3" />

    <v-row dense>
      <v-col cols="12" sm="6" md="3">
        <v-switch v-model="local.enabled" label="启用插件" color="primary" hide-details />
      </v-col>
      <v-col cols="12" sm="6" md="3">
        <v-switch
          v-model="local.search_in_global"
          label="参与宿主全局检索"
          color="primary"
          hide-details
        />
      </v-col>
      <v-col cols="12" sm="6" md="3">
        <v-switch v-model="local.web_index_search" label="站外索引检索" color="primary" hide-details />
      </v-col>
      <v-col cols="12" sm="6" md="3">
        <v-switch v-model="local.detail_facts" label="详情页摘要行" color="primary" hide-details />
      </v-col>
    </v-row>

    <v-divider class="my-3" />

    <!-- ── 站点与节奏 ── -->
    <div class="text-subtitle-2 mb-2">
      <v-icon icon="mdi-earth" size="18" class="mr-1" />
      站点与节奏
    </div>
    <v-row dense>
      <v-col cols="12" md="6">
        <v-text-field
          v-model="local.domain"
          label="站点域名"
          density="compact"
          variant="outlined"
          hide-details
          placeholder="https://duanjubaike.org"
        />
      </v-col>
      <v-col cols="12" sm="4" md="2">
        <v-text-field
          v-model.number="local.interval_minutes"
          label="榜单刷新间隔"
          suffix="分钟"
          type="number"
          density="compact"
          variant="outlined"
          hide-details
        />
      </v-col>
      <v-col cols="12" sm="4" md="2">
        <v-text-field
          v-model.number="local.timeout"
          label="请求超时"
          suffix="秒"
          type="number"
          density="compact"
          variant="outlined"
          hide-details
        />
      </v-col>
      <v-col cols="12" sm="4" md="2">
        <v-text-field
          v-model.number="local.cache_ttl"
          label="详情缓存"
          suffix="秒"
          type="number"
          density="compact"
          variant="outlined"
          hide-details
        />
      </v-col>
    </v-row>
    <div class="text-caption sdbs-dim mt-1">
      详情页内容基本不变，缓存默认 7 天；榜单快照 6 小时过期，后台每 {{ local.interval_minutes }} 分钟检查一次。
    </div>

    <v-divider class="my-3" />

    <!-- ── 站外索引 ── -->
    <div class="text-subtitle-2 mb-2">
      <v-icon icon="mdi-web-search" size="18" class="mr-1" />
      站外索引（片名 / 演员名 → 站点 ID 的唯一通道）
    </div>
    <v-row dense>
      <v-col cols="12" sm="6" md="3">
        <v-select
          v-model="local.web_index_backend"
          :items="backendOptions"
          label="检索后端"
          density="compact"
          variant="outlined"
          hide-details
        />
      </v-col>
      <v-col cols="12" sm="6" md="3">
        <v-switch v-model="local.proxy" label="使用系统代理" color="primary" hide-details />
      </v-col>
    </v-row>
    <div class="text-caption sdbs-dim mt-1">
      实测 <code>auto</code> 与 <code>yandex</code> 有结果；单次检索约 10 秒，相邻两次至少隔 3 秒。
      关掉它之后按姓名找演员会直接不可用（没有第二条发现通道）。
    </div>

    <v-divider class="my-3" />

    <!-- ── 探索页 ── -->
    <div class="text-subtitle-2 mb-2">
      <v-icon icon="mdi-compass-outline" size="18" class="mr-1" />
      宿主「探索」页
    </div>
    <v-select
      v-model="local.top_keys"
      :items="topKeyOptions"
      item-title="label"
      item-value="value"
      label="榜单快照范围（= 探索页里的来源）"
      multiple
      chips
      closable-chips
      density="compact"
      variant="outlined"
      hide-details
      class="mb-2"
    />
    <v-row dense>
      <v-col cols="12" sm="6" md="3">
        <v-text-field
          v-model.number="local.explore_detail_fetch"
          label="探索页详情回填"
          suffix="部/次"
          type="number"
          density="compact"
          variant="outlined"
          hide-details
        />
      </v-col>
    </v-row>
    <!-- 快照实况：勾了但没刷到的榜单在探索页里是空列表，这里点名，省得去探索页猜 -->
    <div v-if="snapshotText" class="text-caption sdbs-dim mt-1">
      当前快照：{{ snapshotText }}
    </div>
    <div v-if="missingKeys.length" class="text-caption sdbs-dim">
      <v-icon icon="mdi-alert-outline" size="14" class="mr-1" />
      已勾选但快照里还没有：{{ missingKeys.join('、') }}（等下次刷新，或把
      <code>interval_minutes</code> 调小）
    </div>
    <div class="text-caption sdbs-dim mt-1">
      榜单页只有「标题 + 海报 + 集数」，回填会把当前页少量作品的
      「简介 / 年份 / 类型 / 主演」也带上；填 <code>0</code> 表示完全不额外请求。
      榜单页不受站点限流，多勾几个不吃亏。
    </div>

    <v-divider class="my-3" />

    <div class="d-flex align-center flex-wrap" style="gap: 8px">
      <v-btn
        color="primary"
        variant="tonal"
        :loading="saving"
        prepend-icon="mdi-content-save-outline"
        @click="doSave"
      >
        保存
      </v-btn>
      <v-btn variant="text" :disabled="saving" @click="resetToLoaded">还原</v-btn>
      <v-spacer />
      <span class="text-caption sdbs-dim">{{ hint }}</span>
    </div>
  </v-card>
</template>

<script setup lang="ts">
/**
 * 短剧百科数据源 —— 配置页（联邦暴露名 `./Config`）。
 *
 * ⚠️ 只在 `onMounted` 读一次 `initialConfig`，所以宿主/面板必须**先把配置取回来再挂载**
 * 本组件；否则表单会是一片默认值，用户一保存就把已有配置覆盖掉。
 * 为了少踩这个坑，这里挂载后自己再拉一次 `GET /config`（真实生效值），
 * `initialConfig` 只作为拉取失败时的兜底。
 */
import { computed, onMounted, ref } from 'vue'
import { fetchConfig, fetchStatus, resolveApi, saveConfig } from './api'
import type { PluginApi, PluginConfig } from './types'

const props = defineProps<{
  /** 宿主传入的初始配置（兜底用） */
  initialConfig?: Partial<PluginConfig>
  /** 宿主注入的 axios 实例 */
  api?: PluginApi
}>()

const emit = defineEmits(['save', 'close', 'switch'])

/** 与后端 `_default_config()` 逐键一致 */
const DEFAULTS: PluginConfig = {
  enabled: false,
  domain: 'https://duanjubaike.org',
  search_in_global: true,
  interval_minutes: 5,
  timeout: 15,
  cache_ttl: 604800,
  web_index_search: true,
  web_index_backend: 'auto',
  proxy: false,
  top_keys: ['hot', 'new'],
  explore_detail_fetch: 8,
  detail_facts: true,
}

/** 后端没有可选项时的兜底（榜单键取自插件的 TOP_LISTS） */
const FALLBACK_TOP_KEYS = [
  { value: 'hot', label: '热播榜' },
  { value: 'new', label: '新剧榜' },
  { value: 'celebrity', label: '明星榜' },
  { value: 'comic-hot', label: '漫剧热榜' },
  { value: 'search', label: '搜索榜' },
  { value: 'hot-urban', label: '都市榜' },
  { value: 'hot-rebirth', label: '重生榜' },
  { value: 'hot-through', label: '穿越榜' },
  { value: 'hot-system', label: '系统榜' },
  { value: 'hot-male', label: '男频榜' },
  { value: 'hot-female', label: '女频榜' },
  { value: 'hot-female-grouth', label: '女性成长榜' },
  { value: 'hot-strong-female', label: '大女主榜' },
  { value: 'hot-vest', label: '战神马甲榜' },
  { value: 'hot-face-slapping', label: '打脸榜' },
  { value: 'hot-counter-attack', label: '逆袭榜' },
  { value: 'hot-country', label: '乡村榜' },
]

const FALLBACK_BACKENDS = ['auto', 'duckduckgo', 'yandex', 'google', 'brave', 'mojeek']

const local = ref<PluginConfig>({ ...DEFAULTS, ...(props.initialConfig || {}) })
/** 服务端最近一次的真实配置，供「还原」使用 */
const loaded = ref<PluginConfig>({ ...local.value })
const topKeyOptions = ref(FALLBACK_TOP_KEYS)
const backendOptions = ref(FALLBACK_BACKENDS)
const loading = ref(false)
const saving = ref(false)
const hint = ref('')
/** 快照实况文案（来自 /status），让「勾了范围」与「探索页实际有什么」对得上 */
const snapshotText = ref('')
/** 已勾选但快照里还没有的榜单键 —— 这些在探索页里是空列表 */
const missingKeys = ref<string[]>([])

/** 按快照键中文名回显；键不在选项里时原样显示 */
function labelOfKey(key: string): string {
  return topKeyOptions.value.find((item) => item.value === key)?.label || key
}

const topKeyLabelOf = computed(() => {
  const map = new Map(topKeyOptions.value.map((item) => [item.value, item.label]))
  return (key: string) => map.get(key) || key
})

onMounted(() => {
  void loadConfig()
})

async function loadConfig(): Promise<void> {
  const api = resolveApi(props)
  if (!api) return
  loading.value = true
  try {
    const report = await fetchConfig(api)
    if (report?.config) {
      local.value = { ...DEFAULTS, ...report.config }
      loaded.value = { ...local.value }
    }
    const options = report?.options
    if (options?.top_keys?.length) topKeyOptions.value = options.top_keys
    if (options?.web_index_backends?.length) backendOptions.value = options.web_index_backends
    hint.value = local.value.top_keys.length
      ? `已勾选：${local.value.top_keys.map(topKeyLabelOf.value).join('、')}`
      : ''
    await loadSnapshot()
  } catch (error) {
    hint.value = '读取配置失败，当前显示的是默认值'
    console.warn('[ShortDramaBaikeSource] 读取配置失败', error)
  } finally {
    loading.value = false
  }
}

/** 拉一次 /status，把快照实况与「勾了但还没刷到」的榜单显示出来 */
async function loadSnapshot(): Promise<void> {
  const api = resolveApi(props)
  if (!api) return
  try {
    const report = await fetchStatus(api)
    const cached = report?.top_lists || []
    snapshotText.value = report?.top_snapshot || ''
    missingKeys.value = (local.value.top_keys || [])
      .filter((key) => !cached.includes(key))
      .map(labelOfKey)
  } catch (error) {
    snapshotText.value = ''
    missingKeys.value = []
    console.warn('[ShortDramaBaikeSource] 读取快照状态失败', error)
  }
}

function resetToLoaded(): void {
  local.value = { ...loaded.value }
  hint.value = '已还原为服务端当前配置'
}

async function doSave(): Promise<void> {
  const api = resolveApi(props)
  if (!api) {
    hint.value = '拿不到宿主接口实例，无法保存'
    return
  }
  saving.value = true
  hint.value = ''
  try {
    const payload: Partial<PluginConfig> = {
      ...local.value,
      domain: String(local.value.domain || '').trim(),
      // 清空多选时别把榜单范围弄成空的（后端也会兜底，这里先给个可读的默认）
      top_keys: local.value.top_keys?.length ? local.value.top_keys : DEFAULTS.top_keys,
    }
    const report = await saveConfig(api, payload)
    if (report?.success) {
      if (report.config) {
        local.value = { ...DEFAULTS, ...report.config }
        loaded.value = { ...local.value }
      }
      hint.value = report.message || '配置已保存'
      await loadSnapshot()
      emit('save', local.value)
    } else {
      hint.value = report?.message || '保存失败'
    }
  } catch (error) {
    hint.value = '保存失败（请看宿主日志）'
    console.warn('[ShortDramaBaikeSource] 保存配置失败', error)
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.sdbs-dim {
  opacity: 0.7;
}
</style>
