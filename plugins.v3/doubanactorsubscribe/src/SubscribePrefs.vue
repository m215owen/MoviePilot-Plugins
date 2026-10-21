<template>
  <v-card variant="outlined" class="mb-3">
    <v-card-text class="pb-2">
      <div class="d-flex align-center flex-wrap mb-2" style="gap: 8px">
        <v-icon icon="mdi-tune-variant" size="18" />
        <span class="text-subtitle-2">订阅选项</span>
        <span class="text-caption das-dim">
          提交订阅时一并带上；留空则沿用 MoviePilot 的默认订阅配置
        </span>
        <v-spacer />
        <span
          v-if="loaded && !pathItems.length && !downloaderItems.length && !siteItems.length"
          class="text-caption text-warning"
        >
          未能读取宿主选项
        </span>
        <v-btn
          size="small"
          variant="text"
          icon="mdi-refresh"
          :loading="loadingOptions"
          title="重新读取宿主的下载路径、下载器与站点"
          @click="loadOptions"
        />
        <v-btn
          v-if="showSave"
          size="small"
          variant="tonal"
          color="primary"
          prepend-icon="mdi-content-save-outline"
          :loading="saving"
          @click="saveAsDefault"
        >
          保存为默认
        </v-btn>
      </div>

      <v-row dense>
        <v-col cols="12" md="4">
          <v-combobox
            v-model="pathModel"
            :items="pathItems"
            item-title="label"
            item-value="path"
            :loading="loadingOptions"
            label="下载保存路径"
            hint="可从下拉选择，也可直接输入自定义路径；留空表示跟随默认"
            persistent-hint
            density="comfortable"
            clearable
            prepend-inner-icon="mdi-folder-outline"
          />
        </v-col>
        <v-col cols="12" md="4">
          <v-combobox
            v-model="downloaderModel"
            :items="downloaderItems"
            item-title="label"
            item-value="name"
            :loading="loadingOptions"
            label="下载器"
            hint="宿主里已配置的下载客户端；留空表示跟随默认"
            persistent-hint
            density="comfortable"
            clearable
            prepend-inner-icon="mdi-download-network-outline"
          />
          <div
            v-if="downloader && !downloaderAvailable"
            class="text-caption text-warning mt-n2"
          >
            宿主没有名为「{{ downloader }}」的下载器，提交时会被忽略
          </div>
        </v-col>
        <v-col cols="12" md="4">
          <v-select
            v-model="sitesModel"
            :items="siteItems"
            item-title="label"
            item-value="id"
            :loading="loadingOptions"
            label="订阅站点"
            hint="不选表示使用宿主默认订阅站点"
            persistent-hint
            density="comfortable"
            multiple
            chips
            clearable
            prepend-inner-icon="mdi-web"
          />
        </v-col>
      </v-row>
    </v-card-text>
  </v-card>
</template>

<script setup lang="ts">
/**
 * 订阅选项（内部复用组件，不作为联邦暴露入口）。
 *
 * 提供「下载保存路径」「下载器」「订阅站点」三个偏好，供面板提交订阅时使用，
 * 并支持一键写回插件配置（PUT /config）成为默认值。
 *
 * 站点列表来自宿主 `site/rss`，其响应含站点凭据，这里只取 `{id, name}`；
 * 目录列表来自宿主 `download/paths`，只取路径；下载器来自 `download/clients`，
 * 只取 `{name, type}`（提交订阅时写的是 `name`）。
 */
import { computed, onMounted, ref, watch } from 'vue'
import {
  API_BASE,
  resolveApi,
  normalizeResult,
  fetchDownloaderOptions,
  fetchPathOptions,
  fetchSiteOptions,
} from './api'
import type {
  DownloadClientOption,
  DownloadPathOption,
  PluginApi,
  PluginConfig,
  SiteOption,
} from './types'

const props = withDefaults(
  defineProps<{
    /** 宿主注入的 axios 实例 */
    api?: PluginApi
    /** 是否显示「保存为默认」按钮；配置页由宿主统一保存，可关掉避免双写 */
    showSave?: boolean
  }>(),
  { showSave: true }
)

const emit = defineEmits<{
  (e: 'saved', ok: boolean, message: string): void
}>()

/** 选中的下载保存路径（'' 表示跟随默认） */
const savePath = defineModel<string>('savePath', { default: '' })
/** 选中的下载器名称（'' 表示跟随默认） */
const downloader = defineModel<string>('downloader', { default: '' })
/** 选中的订阅站点 ID 列表（空数组表示跟随默认） */
const sites = defineModel<number[]>('sites', { default: () => [] })

const pathOptions = ref<DownloadPathOption[]>([])
const downloaderOptions = ref<DownloadClientOption[]>([])
const siteOptions = ref<SiteOption[]>([])
const saving = ref(false)
const loadingOptions = ref(false)
/** 是否至少尝试加载过一次（用于区分「加载中」与「真的没有可选数据」） */
const loaded = ref(false)

/** 下载路径下拉项：有别名时展示「别名 (路径)」，值始终是可直接提交的路径 */
const pathItems = computed(() =>
  pathOptions.value.map((item) => ({
    label: item.name && item.name !== item.path ? `${item.name}（${item.path}）` : item.path,
    path: item.path,
  }))
)

/** 下载器下拉项：有类型时展示「名称 (类型)」，值始终是提交用的名称 */
const downloaderItems = computed(() =>
  downloaderOptions.value.map((item) => ({
    label: item.type ? `${item.name}（${item.type}）` : item.name,
    name: item.name,
  }))
)

const siteItems = computed(() =>
  siteOptions.value.map((item) => ({ label: item.name, id: item.id }))
)

/** 手填 / 历史配置的下载器在宿主里是否真的存在（不存在时给出提示） */
const downloaderAvailable = computed(() => {
  const current = String(downloader.value || '').trim()
  if (!current) return true
  if (!downloaderOptions.value.length) return true
  return downloaderOptions.value.some((item) => item.name === current)
})

/** combobox 允许自由输入：选中项回传整个对象，输入时回传字符串 */
const pathModel = computed<string | { path: string } | null>({
  get: () => savePath.value || '',
  set: (value) => {
    if (value && typeof value === 'object') savePath.value = String(value.path || '')
    else savePath.value = String(value ?? '').trim()
  },
})

/** 下载器同样允许自由输入（宿主里的名字可以手填，避免选项没加载出来时卡住） */
const downloaderModel = computed<string | { name: string } | null>({
  get: () => downloader.value || '',
  set: (value) => {
    if (value && typeof value === 'object') downloader.value = String(value.name || '')
    else downloader.value = String(value ?? '').trim()
  },
})

const sitesModel = computed<number[]>({
  get: () => sites.value || [],
  set: (value) => {
    sites.value = Array.isArray(value) ? value.map((item) => Number(item)) : []
  },
})

async function loadOptions(): Promise<void> {
  const api = resolveApi(props)
  if (!api) return
  loadingOptions.value = true
  try {
    const [paths, downloaders, siteList] = await Promise.all([
      fetchPathOptions(api),
      fetchDownloaderOptions(api),
      fetchSiteOptions(api),
    ])
    pathOptions.value = paths
    downloaderOptions.value = downloaders
    siteOptions.value = siteList
  } finally {
    loadingOptions.value = false
    loaded.value = true
  }
}

/** 把当前选择写回插件配置，成为面板与自动订阅的默认值 */
async function saveAsDefault(): Promise<void> {
  const api = resolveApi(props)
  if (!api) {
    emit('saved', false, '宿主 API 未就绪')
    return
  }
  saving.value = true
  try {
    const raw = await api.put(`${API_BASE}/config`, {
      subscribe_save_path: savePath.value || '',
      subscribe_downloader: downloader.value || '',
      subscribe_sites: sites.value || [],
    })
    const res = normalizeResult<PluginConfig>(raw)
    emit('saved', res.ok, res.message || (res.ok ? '订阅选项已保存' : '保存失败'))
  } catch (err) {
    console.warn('[DoubanActorSubscribe] 保存订阅选项失败', err)
    emit('saved', false, '保存订阅选项失败')
  } finally {
    saving.value = false
  }
}

onMounted(loadOptions)

// 宿主可能在挂载之后才把 axios 实例注入进来（插件虚拟分身 / 联邦远程组件的场景），
// 因此 api 一就绪就补一次加载，避免两个下拉一直空着。
watch(
  () => props.api,
  (next) => {
    if (next && !loaded.value) void loadOptions()
  }
)
</script>

<style scoped>
.das-dim {
  opacity: 0.75;
}
</style>
