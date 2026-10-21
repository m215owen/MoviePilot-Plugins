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
    </v-row>

    <v-divider class="my-3" />

    <!-- ── 站点与请求 ── -->
    <div class="text-subtitle-2 mb-2">
      <v-icon icon="mdi-earth" size="18" class="mr-1" />
      站点与请求
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
      <v-col cols="12" sm="6" md="3">
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
      <v-col cols="12" sm="6" md="3">
        <v-text-field
          v-model.number="local.cache_ttl"
          label="缓存覆盖"
          suffix="秒"
          type="number"
          density="compact"
          variant="outlined"
          hide-details
        />
      </v-col>
      <v-col cols="12" sm="6" md="3">
        <v-text-field
          v-model.number="local.enrich_workers"
          label="补全并发"
          suffix="线程"
          type="number"
          :min="1"
          :max="32"
          density="compact"
          variant="outlined"
          hide-details
        />
      </v-col>
    </v-row>
    <div class="text-caption sdbs-dim mt-1">
      <b>0（默认）= 跟随宿主</b>：有效期取系统设置的「单条元数据识别缓存有效期」
      （设置 → 缓存 → <code>META_CACHE_EXPIRE</code>，单位小时，未填时宿主按 24 小时、
      大内存模式 72 小时计）；正数 = 显式覆盖；<b>负数 = 关闭插件缓存</b>（排障用）。
      缓存的后端也跟着宿主走（系统启用 Redis 时与宿主共用同一实例），
      但<b>不进宿主的缓存管理页</b> —— 要清缓存请用面板上的「缓存管理」。
      插件<b>没有后台任务</b>：缓存只在被查询时按需重建。
      <b>补全并发</b>是演员作品补全的抓取线程数（1~32，默认 8；站点对详情页不设风控，
      实测 12 并发全部 200）—— 调大更快，占更多并发连接；1 ≈ 串行。
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
      关掉它之后面板搜索框会直接不可用（没有第二条发现通道），按姓名找演员也一样。
    </div>

    <v-divider class="my-3" />

    <!-- ── URL 库（插件自有数据库） ── -->
    <div class="text-subtitle-2 mb-2">
      <v-icon icon="mdi-database-outline" size="18" class="mr-1" />
      URL 库（插件自有数据库）
    </div>
    <v-row dense>
      <v-col cols="12" sm="6" md="3">
        <v-switch
          v-model="local.follow_links"
          label="顺带沉淀页面里的链接"
          color="primary"
          hide-details
        />
      </v-col>
    </v-row>
    <div class="text-caption sdbs-dim mt-1">
      库里只存「关键词 → 页面 URL」，<b>不存解析结果</b>：站点内容随时在变，页面永远实时解析。
      取数优先查库（命中即零引擎请求），库里没有才检索一次并把作品与演员两类 URL 一起入库。
      开启本项后，解析作品页时顺带把演员链接写进库、解析演员页时顺带把作品链接写进库 ——
      所以搜过一部剧，之后再搜它里面的演员名也是零引擎请求。
      PostgreSQL 实例下这些表落在宿主库的独立 schema，SQLite 实例下落在插件数据目录的
      <code>plugin.db</code>，两种情况下都跟着宿主一起备份。
    </div>

    <v-divider class="my-3" />

    <div v-if="statusText" class="text-caption sdbs-dim mb-2">
      <v-icon icon="mdi-information-outline" size="14" class="mr-1" />{{ statusText }}
    </div>

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
import { onMounted, ref } from 'vue'
import { fetchConfig, fetchStatus, resolveApi, saveConfig } from './api'
import type { PluginApi, PluginConfig } from './types'

const props = defineProps<{
  /** 宿主传入的初始配置（兜底用） */
  initialConfig?: Partial<PluginConfig>
  /** 宿主注入的 axios 实例 */
  api?: PluginApi
}>()

const emit = defineEmits(['save', 'close', 'switch'])

/** 与后端 `_default_config()` 逐键一致（共 10 项） */
const DEFAULTS: PluginConfig = {
  enabled: false,
  domain: 'https://duanjubaike.org',
  search_in_global: true,
  timeout: 15,
  // 0 = 跟随宿主（系统设置里的「单条元数据识别缓存有效期」）
  cache_ttl: 0,
  web_index_search: true,
  web_index_backend: 'auto',
  proxy: false,
  follow_links: true,
  enrich_workers: 8,
}

const FALLBACK_BACKENDS = ['auto', 'duckduckgo', 'yandex', 'google', 'brave', 'mojeek']

const local = ref<PluginConfig>({ ...DEFAULTS, ...(props.initialConfig || {}) })
/** 服务端最近一次的真实配置，供「还原」使用 */
const loaded = ref<PluginConfig>({ ...local.value })
const backendOptions = ref(FALLBACK_BACKENDS)
const loading = ref(false)
const saving = ref(false)
const hint = ref('')
/** 运行实况文案（来自 /status） */
const statusText = ref('')

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
    if (options?.web_index_backends?.length) backendOptions.value = options.web_index_backends
    await loadStatus()
  } catch (error) {
    hint.value = '读取配置失败，当前显示的是默认值'
    console.warn('[ShortDramaBaikeSource] 读取配置失败', error)
  } finally {
    loading.value = false
  }
}

/** 拉一次 `/status`，把运行实况显示在保存栏上方 */
async function loadStatus(): Promise<void> {
  const api = resolveApi(props)
  if (!api) return
  try {
    const report = await fetchStatus(api)
    if (!report) {
      statusText.value = ''
      return
    }
    const index = report.web_index || {}
    const indexText = index.available
      ? index.enabled
        ? `站外索引 开（后端 ${index.backend || 'auto'}）`
        : '站外索引 关'
      : '站外索引 不可用（依赖缺失）'
    const store = report.store || {}
    const cache = report.cache || {}
    const ttlText = cache.ttl ? `有效期 ${cache.ttl}s` : '有效期 —'
    statusText.value = [
      `运行状态：${report.enabled ? '已启用' : '未启用'}`,
      indexText,
      `URL 库 ${store.total ?? 0} 条（作品 ${store.work ?? 0} / 演员 ${store.actor ?? 0}）`,
      `缓存 ${cache.count ?? 0} 条（后端 ${cache.backend ?? '—'}，${ttlText}）`,
    ].join('　｜　')
  } catch (error) {
    statusText.value = ''
    console.warn('[ShortDramaBaikeSource] 读取运行状态失败', error)
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
    }
    const report = await saveConfig(api, payload)
    if (report?.success) {
      if (report.config) {
        local.value = { ...DEFAULTS, ...report.config }
        loaded.value = { ...local.value }
      }
      hint.value = report.message || '配置已保存'
      await loadStatus()
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
