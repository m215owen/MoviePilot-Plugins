<template>
  <div class="sdas-root pa-2">
    <v-card variant="outlined" class="pa-4">
      <div class="d-flex align-center mb-3">
        <v-icon icon="mdi-movie-open-star-outline" class="mr-2" />
        <h3 class="ma-0">短剧演员 · 设置</h3>
        <v-spacer />
        <v-btn icon="mdi-close" variant="text" size="small" title="关闭" @click="emit('close')" />
      </div>

      <v-alert type="info" variant="tonal" density="compact" class="mb-3">
        作品全部来自<b>短剧百科</b>（duanjubaike.org，已作为媒体数据源接入系统）。
        在作品墙点「订阅」，走的就是<b>MoviePilot 自己的订阅系统</b> ——
        搜索、下载、整理全部由系统接管。
      </v-alert>

      <v-row dense>
        <v-col cols="12" sm="6" md="3">
          <v-switch v-model="local.enabled" label="启用插件" color="primary" hide-details />
        </v-col>
        <v-col cols="12" sm="6" md="3">
          <v-switch
            v-model="local.sidebar_nav"
            label="侧栏显示「短剧演员」入口"
            color="primary"
            hide-details
          />
        </v-col>
        <v-col cols="12" sm="6" md="3">
          <v-switch v-model="local.notify" label="新作品发系统通知" color="primary" hide-details />
        </v-col>
        <v-col cols="12" sm="6" md="3">
          <v-switch
            v-model="local.onlyonce"
            label="保存后立即刷新一次"
            color="primary"
            hide-details
          />
        </v-col>
      </v-row>

      <v-divider class="my-3" />

      <!-- 演员名单 -->
      <div class="text-subtitle-2 mb-2">
        <v-icon icon="mdi-account-multiple-outline" size="18" class="mr-1" />
        关注的演员
        <span class="text-caption sdas-dim ml-2">共 {{ actorItems.length }} 位</span>
      </div>
      <v-textarea
        v-model="local.actors"
        variant="outlined"
        density="compact"
        rows="4"
        auto-grow
        hide-details
        placeholder="一行一位，或用逗号分隔。例：&#10;徐艺真&#10;孙樾"
      />
      <div class="text-caption sdas-dim mt-1">
        单个添加也可以在作品墙右上角「添加演员」里填名字（会先在短剧百科里核对）。
      </div>

      <v-divider class="my-3" />

      <!-- 刷新节奏 -->
      <div class="text-subtitle-2 mb-2">
        <v-icon icon="mdi-timer-outline" size="18" class="mr-1" />
        刷新节奏
      </div>
      <v-row dense>
        <v-col cols="12" sm="6">
          <v-text-field
            v-model.number="local.interval_hours"
            type="number"
            min="1"
            label="发现间隔（小时）"
            variant="outlined"
            density="compact"
            hide-details
          />
        </v-col>
        <v-col cols="12" sm="6">
          <v-text-field
            v-model.number="local.retry_minutes"
            type="number"
            min="1"
            label="解析失败重试（分钟）"
            variant="outlined"
            density="compact"
            hide-details
          />
        </v-col>
      </v-row>
      <div class="text-caption sdas-dim mt-1">
        每隔「发现间隔」跑一轮发现任务，重抓距上次已超过一个间隔的演员（演员页要真抓网络，不会每轮全量重扫）；
        解析失败属于临时故障，按分钟级重试。
      </div>

      <v-divider class="my-3" />

      <!-- 搜索站点 -->
      <div class="text-subtitle-2 mb-2">
        <v-icon icon="mdi-web-check" size="18" class="mr-1" />
        资源搜索站点
        <span class="text-caption sdas-dim ml-2">
          作品墙上点「搜索」时，只在勾选的站点里搜；不勾 = 走系统默认
        </span>
      </div>
      <template v-if="siteOptions.length">
        <v-select
          v-model="selectedSiteModels"
          :items="sortedSiteOptions"
          item-title="name"
          item-value="id"
          label="资源搜索站点"
          multiple
          chips
          closable-chips
          variant="outlined"
          density="compact"
          hide-details
          placeholder="不选 = 走系统默认"
        >
          <template #prepend-item>
            <div class="d-flex align-center px-4 pb-2" style="gap: 8px">
              <v-btn size="x-small" variant="tonal" color="primary" @click="selectAllSites">全选</v-btn>
              <v-btn size="x-small" variant="tonal" @click="selectedSiteModels = []">清空</v-btn>
              <span class="text-caption sdas-dim">
                已选 {{ selectedSiteIds.length }} / {{ siteOptions.length }}
              </span>
            </div>
          </template>
        </v-select>
      </template>
      <v-alert v-else-if="siteLoadFailed" type="warning" variant="tonal" density="compact">
        站点列表加载失败，可稍后重新打开本页重试。
      </v-alert>
      <div v-else-if="siteLoading" class="text-caption sdas-dim">正在加载站点列表…</div>
      <div v-else class="text-caption sdas-dim">
        当前没有启用中的搜索站点 —— 作品墙的「搜索」会直接走系统默认行为。
      </div>

      <v-divider class="my-3" />

      <!-- 订阅下载器 -->
      <div class="text-subtitle-2 mb-2">
        <v-icon icon="mdi-download-network-outline" size="18" class="mr-1" />
        订阅下载器
        <span class="text-caption sdas-dim ml-2">作品墙提交订阅时使用的下载客户端</span>
      </div>
      <v-row dense>
        <v-col cols="12" sm="6">
          <v-combobox
            v-model="local.subscribe_downloader"
            :items="downloaderNames"
            :loading="downloaderLoading"
            label="下载器"
            variant="outlined"
            density="compact"
            clearable
            hide-details
            placeholder="留空 = 跟随系统默认"
          />
          <div
            v-if="local.subscribe_downloader && !downloaderNames.includes(local.subscribe_downloader)"
            class="text-caption text-warning mt-1"
          >
            宿主没有名为「{{ local.subscribe_downloader }}」的下载器，提交时会被忽略
          </div>
        </v-col>
      </v-row>
      <div class="text-caption sdas-dim mt-1">
        指定下载器后，作品墙点「订阅」会按此下载器<b>直接提交</b>（系统订阅弹窗没有下载器选项，带不上偏好）；
        留空则保持原样，弹出系统订阅对话框。下载客户端在宿主「设定 → 下载器」里维护。
      </div>

      <v-divider class="my-3" />

      <div class="d-flex align-center" style="gap: 8px">
        <v-spacer />
        <v-btn variant="text" @click="emit('close')">取消</v-btn>
        <v-btn color="primary" :loading="saving" @click="onSave">保存</v-btn>
      </div>
    </v-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { fetchDownloaderOptions, fetchSearchSites, saveConfig } from './api'
import type { HostSite } from './api'
import type { DownloadClientOption, PluginApi, PluginConfig } from './types'

const props = defineProps<{
  /** 宿主注入的 axios 实例 */
  api?: PluginApi
  /** 初始配置（宿主从插件配置里读到的当前值） */
  initialConfig?: Partial<PluginConfig>
}>()

const emit = defineEmits<{
  (e: 'save', config: Partial<PluginConfig>): void
  (e: 'close'): void
  (e: 'switch', enabled: boolean): void
}>()

/** 默认值：与后端 `_default_config()` 保持一致 */
function defaults(): PluginConfig {
  return {
    enabled: false,
    onlyonce: false,
    actors: '',
    interval_hours: 12,
    retry_minutes: 20,
    notify: true,
    sidebar_nav: true,
    search_sites: '',
    subscribe_downloader: '',
  }
}

const local = ref<PluginConfig>(defaults())
const saving = ref(false)

// ── 搜索站点 ──

const siteOptions = ref<HostSite[]>([])
const siteLoadFailed = ref(false)
const siteLoading = ref(true)

onMounted(async () => {
  try {
    siteOptions.value = await fetchSearchSites(props)
  } catch {
    siteLoadFailed.value = true
  } finally {
    siteLoading.value = false
  }
})

const selectedSiteIds = computed(() =>
  String(local.value.search_sites || '')
    .split(/[,，;；\s]+/)
    .map((item) => Number(item))
    .filter((id) => Number.isFinite(id) && id > 0),
)

/** v-select 多选直接吃数组；写回时归一成逗号分隔字符串存配置 */
const selectedSiteModels = computed<number[]>({
  get: () => selectedSiteIds.value,
  set: (ids) => {
    const unique = Array.from(new Set(ids.filter((id) => Number.isFinite(id) && id > 0)))
    local.value.search_sites = unique.join(',')
  },
})

/**
 * 下拉列表排序：已勾选的排前面，组内保持原有顺序（稳定分区，不额外重排）。
 * 依赖 selectedSiteIds，勾选/取消后列表实时重排。
 */
const sortedSiteOptions = computed<HostSite[]>(() => {
  const picked = new Set(selectedSiteIds.value)
  const selected = siteOptions.value.filter((site) => picked.has(site.id))
  const rest = siteOptions.value.filter((site) => !picked.has(site.id))
  return [...selected, ...rest]
})

function selectAllSites(): void {
  local.value.search_sites = siteOptions.value.map((site) => site.id).join(',')
}

// ── 订阅下载器 ──

const downloaderOptions = ref<DownloadClientOption[]>([])
const downloaderLoading = ref(true)

/** 下拉候选：只给名字（combobox 允许手输，v-model 直接是名字字符串） */
const downloaderNames = computed(() => downloaderOptions.value.map((item) => item.name))

onMounted(async () => {
  try {
    downloaderOptions.value = await fetchDownloaderOptions(props)
  } finally {
    downloaderLoading.value = false
  }
})

// ⚠️ 只在挂载时读一次 initialConfig：调用方必须先取到配置再挂载本组件，
// 否则表单是空的，用户一保存就把已有配置清掉。
onMounted(() => {
  const incoming = props.initialConfig || {}
  local.value = { ...defaults(), ...incoming }
})

const actorItems = computed(() =>
  String(local.value.actors || '')
    .split(/[,，;；\n\r]+/)
    .map((item) => item.trim())
    .filter(Boolean),
)

async function onSave(): Promise<void> {
  saving.value = true
  try {
    // combobox clearable 清空时会把 model 置 null，落库前归一成空串
    const cleaned = String(local.value.subscribe_downloader || '').trim()
    await saveConfig(props, { ...local.value, subscribe_downloader: cleaned })
    emit('save', { ...local.value, subscribe_downloader: cleaned })
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.sdas-dim {
  opacity: 0.7;
}
</style>
