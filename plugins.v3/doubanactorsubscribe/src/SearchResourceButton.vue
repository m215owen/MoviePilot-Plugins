<template>
  <v-btn
    v-if="searchable"
    :size="size"
    :variant="variant"
    icon="mdi-magnify"
    :loading="loading"
    title="搜索这部作品的资源：先选站点，再在 MoviePilot 资源搜索页打开（新标签页）"
    @click="open"
  />

  <SitePickDialog
    v-model="visible"
    :sites="sites"
    :selected="selected"
    :loading="loading"
    title="选择搜索站点"
    @confirm="confirm"
  />
</template>

<script setup lang="ts">
/**
 * 「搜索资源」按钮 = 图标按钮 + 站点选择框。
 *
 * 宿主媒体详情页点击「搜索资源」时会先弹站点选择框（用户可以决定这次搜哪些站），
 * 插件这里做出同样的两步式交互，数据和默认值都取自宿主：
 *   - 站点清单：`site/media/{movie|tv|music}`（宿主按媒体类型裁剪出的启用站点）
 *   - 默认勾选：`system/setting/public/IndexerSites`（系统设置里的「搜索站点」）
 * 宿主的弹窗是主程序内部件，联邦插件 import 不到（联邦只共享 vue/vuetify），
 * 所以弹窗界面由 `SitePickDialog` 自行绘制，但**清单与默认值同源**，
 * 用户看到的站点和默认选中项与宿主完全一致。
 *
 * 站点清单为空（例如实例没配站点）时直接跳转，不弹空框 —— 这与宿主行为一致。
 * 清单按媒体类型缓存，同一部作品重复点开不会重复请求。
 */
import { computed, ref } from 'vue'
import SitePickDialog from './SitePickDialog.vue'
import {
  fetchDefaultSearchSites,
  fetchSearchSites,
  resolveApi,
  resourceSearchUrl,
  searchSiteKind,
} from './api'
import type { ActorWork, PluginApi, SiteOption } from './types'

const props = withDefaults(
  defineProps<{
    /** 目标作品 */
    work: ActorWork
    /** 宿主注入的 axios 实例 */
    api?: PluginApi
    /** 按钮尺寸（与所在列表保持一致） */
    size?: string
    /** 按钮样式（与所在列表保持一致） */
    variant?: string
  }>(),
  { size: 'small', variant: 'text' }
)

const emit = defineEmits<{ (e: 'error', message: string): void }>()

/** 按媒体类型缓存的站点清单与默认勾选（同一类型不必重复拉取） */
const cache = new Map<string, { sites: SiteOption[]; defaults: number[] }>()

const visible = ref(false)
const loading = ref(false)
const sites = ref<SiteOption[]>([])
const selected = ref<number[]>([])

/** 有豆瓣 ID 或片名才能搜；两者皆无时按钮不显示 */
const searchable = computed(() => Boolean(resourceSearchUrl(props.work)))

/** 点击按钮：先确保清单就绪，有站点就弹选择框，没有就直接跳 */
async function open(): Promise<void> {
  const api = resolveApi({ api: props.api })
  if (!api) return
  const kind = searchSiteKind(props.work.type)
  const cached = cache.get(kind)
  if (cached) {
    sites.value = cached.sites
    selected.value = cached.defaults
    if (!cached.sites.length) {
      launch([])
      return
    }
    visible.value = true
    return
  }
  loading.value = true
  try {
    const [options, defaults] = await Promise.all([
      fetchSearchSites(api, props.work.type),
      fetchDefaultSearchSites(api),
    ])
    const available = new Set(options.map((site) => site.id))
    // 默认勾选沿用宿主的「搜索站点」设置；实例没配过时退回全选，避免一打开就是空
    let pick = defaults.filter((id) => available.has(id))
    if (options.length && !pick.length) pick = options.map((site) => site.id)
    cache.set(kind, { sites: options, defaults: pick })
    sites.value = options
    selected.value = pick
    if (!options.length) {
      launch([])
      return
    }
    visible.value = true
  } finally {
    loading.value = false
  }
}

/** 用户在弹窗里确认：带着所选站点打开宿主的资源搜索页 */
function confirm(ids: number[]): void {
  visible.value = false
  launch(ids)
}

/** 打开宿主资源搜索页（hash 路由，见 `resourceSearchUrl`） */
function launch(ids: number[]): void {
  const url = resourceSearchUrl(props.work, ids)
  if (!url) {
    emit('error', '这部作品没有可用的检索条件')
    return
  }
  window.open(url, '_blank', 'noopener')
}
</script>
