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
        作品全部来自<b>短剧百科</b>（duanjubaike.net，已作为媒体数据源接入系统）。
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
      <!--
        名单以 **演员 ID** 保存（2026-10-20 起 ID 是唯一身份，同名演员可共存）；
        这里显示成名字（ID→名字来自 /actors），同名的两位会带 ID 后缀区分。
        手输名字保存时尽量还原成 ID，还原不了就原样传给后端解析归位。
      -->
      <v-textarea
        v-model="actorsDisplay"
        variant="outlined"
        density="compact"
        rows="2"
        auto-grow
        hide-details
        placeholder="人名用逗号分隔。例：徐艺真，孙樾，王小亿"
      />
      <div class="text-caption sdas-dim mt-1">
        单个添加也可以在作品墙右上角「添加演员」里填名字（会先在短剧百科里核对）。
      </div>

      <v-divider class="my-3" />

      <!--
        ── 订阅分区 ──
        顺序＝用户的实际决策链：**投递**（下载器 → 目录 → 站点）→ **方式**（普通 / 洗版）
        → **自动化**（自动订阅）。原先这五项被「刷新节奏 / 资源搜索站点」隔开、跨了两屏，
        用户找不到「订到哪」这一组，2026-10-20 收拢到一处。
      -->
      <div class="sdas-block-head">
        <v-icon icon="mdi-send-check-outline" size="20" class="mr-1" />
        <span class="sdas-block-title">订阅</span>
        <span class="text-caption sdas-dim ml-2">
          投递 → 方式 → 自动化；作品墙「订阅」、订阅全部作品、自动订阅三处共用
        </span>
      </div>

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

      <!-- 订阅下载目录 -->
      <div class="text-subtitle-2 mb-2">
        <v-icon icon="mdi-folder-download-outline" size="18" class="mr-1" />
        订阅下载目录
        <span class="text-caption sdas-dim ml-2">订阅的保存目录（含自动订阅 / 订阅全部作品）</span>
      </div>
      <v-row dense>
        <v-col cols="12" sm="8">
          <v-combobox
            v-model="savePathModel"
            :items="downloadPathItems"
            item-title="title"
            item-value="value"
            :return-object="false"
            :loading="downloadPathLoading"
            label="下载目录"
            variant="outlined"
            density="compact"
            clearable
            hide-details
            placeholder="留空 = 跟随宿主订阅默认"
          >
            <template #item="{ props: itemProps, item }">
              <v-list-item v-bind="itemProps" :subtitle="item.raw.path">
                <template #title>
                  <span>{{ item.raw.title }}</span>
                  <span v-if="item.raw.storage !== 'local'" class="text-caption sdas-dim ml-2">
                    {{ item.raw.storage }}
                  </span>
                </template>
              </v-list-item>
            </template>
          </v-combobox>
          <div
            v-if="savePathModel && !savePathInList"
            class="text-caption text-warning mt-1"
          >
            这个路径不是宿主登记的下载目录 —— 宿主保存时会退回默认目录。
            请从列表里选一个（或先去宿主「设定 → 目录」把该目录加进下载目录）
          </div>
          <div v-else-if="savePathInList" class="text-caption sdas-dim mt-1">
            实际提交的路径：<span class="sdas-mono">{{ effectiveSavePath }}</span>
            <span v-if="savePathAligned" class="ml-1">（已按宿主登记值对齐）</span>
            <span v-else class="ml-1">（与宿主登记值一致）</span>
          </div>
        </v-col>
      </v-row>
      <div class="text-caption sdas-dim mt-1">
        目录来自宿主「设定 → 目录」里的下载目录。宿主要求保存目录**精确匹配**某个下载目录根
        （子目录不算），所以这里只列根目录；留空则跟随宿主订阅默认。下载器是远端存储时，
        值可能是 `存储:路径` 形式的 URI，原样提交即可。
      </div>

      <v-divider class="my-3" />

      <!-- 订阅站点 -->
      <div class="text-subtitle-2 mb-2">
        <v-icon icon="mdi-web-plus" size="18" class="mr-1" />
        订阅站点
        <span class="text-caption sdas-dim ml-2">
          自动订阅 / 订阅全部作品只在勾选的站点里搜；不勾 = 走系统默认
        </span>
      </div>
      <template v-if="siteOptions.length">
        <v-select
          v-model="subscribeSiteModels"
          :items="sortedSubscribeSiteOptions"
          item-title="name"
          item-value="id"
          label="订阅站点"
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
              <v-btn size="x-small" variant="tonal" color="primary" @click="selectAllSubscribeSites">
                全选
              </v-btn>
              <v-btn size="x-small" variant="tonal" @click="subscribeSiteModels = []">清空</v-btn>
              <span class="text-caption sdas-dim">
                已选 {{ subscribeSiteIds.length }} / {{ siteOptions.length }}
              </span>
            </div>
          </template>
        </v-select>
      </template>
      <div v-else-if="siteLoading" class="text-caption sdas-dim">正在加载站点列表…</div>
      <div v-else class="text-caption sdas-dim">
        当前没有启用中的站点 —— 订阅会直接走系统默认站点。
      </div>
      <div class="text-caption sdas-dim mt-1">
        与上面的「资源搜索站点」是两件事：那一项只管作品墙点「搜索」跳转，这一项管<b>提交订阅</b>
        （自动订阅、订阅全部作品，以及作品墙点「订阅」时的直连提交）。
      </div>

      <v-divider class="my-3" />

      <!-- 订阅方式（宿主 Subscribe.best_version）：投递目标定好之后再决定普通 / 洗版 -->
      <div class="text-subtitle-2 mb-2">
        <v-icon icon="mdi-swap-horizontal-bold" size="18" class="mr-1" />
        订阅方式
        <span class="text-caption sdas-dim ml-2">投递到哪已经定了，这里只决定「有资源就下」还是「洗版」</span>
      </div>
      <v-btn-toggle
        v-model="local.subscribe_mode"
        mandatory
        divided
        density="compact"
        variant="outlined"
        color="primary"
      >
        <v-btn value="follow" size="small">跟随宿主设置</v-btn>
        <v-btn value="normal" size="small">普通订阅</v-btn>
        <v-btn value="best" size="small">洗版订阅</v-btn>
      </v-btn-toggle>
      <div class="text-caption sdas-dim mt-1">
        宿主订阅的「洗版」开关就是 `Subscribe.best_version`：普通订阅 = 有资源就下；
        洗版订阅 = 持续比对画质、遇到更好的版本再替换。
        <b>跟随宿主设置</b> = 不传值，按宿主「设定 → 订阅」里电视剧的洗版开关走（默认）；
        这里显式选普通 / 洗版会覆盖宿主的默认。作品墙点「订阅」、自动订阅、订阅全部作品三处共用。
      </div>

      <v-divider class="my-3" />

      <!-- 优选条件：同一部剧搜到多条时挑哪条下载（2026-10-23 用户口径） -->
      <div class="text-subtitle-2 mb-2">
        <v-icon icon="mdi-sort-descending" size="18" class="mr-1" />
        优选条件
        <span class="text-caption sdas-dim ml-2">同一部剧搜到多条资源时，挑哪条下载</span>
      </div>
      <v-btn-toggle
        v-model="local.subscribe_prefer"
        mandatory
        divided
        density="compact"
        variant="outlined"
        color="primary"
      >
        <v-btn value="seeders" size="small">按做种数</v-btn>
        <v-btn value="size_desc" size="small">体积最大</v-btn>
        <v-btn value="size_asc" size="small">体积最小</v-btn>
      </v-btn-toggle>
      <div class="text-caption sdas-dim mt-1">
        默认<b>按做种数</b>（越多越稳）；<b>体积最大</b> = 短剧通常是整季合集，更大一般更全；
        <b>体积最小</b> = 挑最省流量的那条。订阅搜索、订阅全部作品、自动订阅共用。
      </div>

      <v-divider class="my-3" />

      <!-- 自动订阅 -->
      <div class="text-subtitle-2 mb-2">
        <v-icon icon="mdi-bell-plus-outline" size="18" class="mr-1" />
        自动订阅演员作品
        <span class="text-caption sdas-dim ml-2">发现到符合条件的新作品，直接交给宿主订阅系统</span>
      </div>
      <v-switch
        v-model="local.auto_subscribe"
        color="primary"
        density="compact"
        hide-details
        inset
        label="打开自动订阅"
      />
      <v-row dense class="mt-1">
        <v-col cols="12" sm="6">
          <v-select
            v-model="local.auto_subscribe_scope"
            :items="scopeOptions"
            item-title="title"
            item-value="value"
            label="订阅范围"
            variant="outlined"
            density="compact"
            hide-details
          />
        </v-col>
        <v-col cols="12" sm="6">
          <v-text-field
            v-model.number="local.auto_subscribe_max_per_run"
            type="number"
            min="1"
            max="50"
            label="单轮最多订阅（部）"
            variant="outlined"
            density="compact"
            hide-details
          />
        </v-col>
      </v-row>
      <v-switch
        v-model="local.auto_subscribe_skip_library"
        color="primary"
        density="compact"
        hide-details
        inset
        class="mt-1"
        label="已在媒体库的作品跳过"
      />
      <div class="text-caption sdas-dim mt-1">
        订阅走宿主订阅系统（与作品墙点「订阅」同一条链路），搜索 / 下载 / 整理都由宿主接手；
        集数按作品卡上的集数提交，下载器沿用上面「订阅下载器」。
        <b>只订新作品</b>：只订最近 7 天内上映（按作品卡上的首播 / 上映日期）的作品，与作品墙的「新作品」同口径；
        <b>全部作品</b>：连历史作品一起补订，按「单轮最多订阅」逐轮推进。
      </div>

      <v-divider class="my-3" />

      <!-- 订阅引擎 -->
      <div class="text-subtitle-2 mb-2">
        <v-icon icon="mdi-engine-outline" size="18" class="mr-1" />
        订阅引擎
      </div>
      <v-select
        v-model="local.subscribe_engine"
        :items="engineOptions"
        item-title="title"
        item-value="value"
        label="搜索下载走哪条链路"
        variant="outlined"
        density="compact"
        hide-details
      />
      <div class="text-caption sdas-dim mt-1">
        <b>宿主订阅系统</b>：订阅交给宿主，搜索按媒体类型带站点分类参数 —— 个别站点把短剧挂在电影分类时会永远搜不到；
        <b>自建订阅搜索</b>：插件自己就是订阅系统 —— 「订阅」记在插件自己的清单里（作品墙左侧面板可见），
        **不提交宿主订阅系统**；搜索时全分类一起搜（电影 + 电视剧 + 短剧），按演员名 / 集数 / 年份消歧后直接提交下载，
        下载 / 整理 / 通知仍归宿主。两种引擎自动互斥，只跑选中的那条。
      </div>
      <template v-if="local.subscribe_engine === 'self'">
        <v-row dense class="mt-1">
          <v-col cols="12" sm="4">
            <v-text-field
              v-model.number="local.self_interval_hours"
              type="number"
              min="1"
              label="搜索间隔（小时）"
              variant="outlined"
              density="compact"
              hide-details
            />
          </v-col>
          <v-col cols="12" sm="4">
            <v-text-field
              v-model.number="local.self_max_per_run"
              type="number"
              min="1"
              max="30"
              label="单轮最多搜索（部）"
              variant="outlined"
              density="compact"
              hide-details
            />
          </v-col>
          <v-col cols="12" sm="4">
            <v-text-field
              v-model.number="local.self_max_pages"
              type="number"
              min="1"
              max="10"
              label="每部最多翻页"
              variant="outlined"
              density="compact"
              hide-details
            />
          </v-col>
        </v-row>
        <div class="text-caption sdas-dim mt-1">
          只搜**已订阅**的作品（卡片订阅 / 订阅全部 / 自动订阅都记进订阅清单）；搜索站点 / 下载器 / 下载目录
          沿用上面「订阅」分区的设置；无结果 72 小时、失败 24 小时后自动重试，单轮预算用完的下一轮接着跑（断点在台账里）。
          另外，插件每 30 分钟自动拉一次**订阅站点的站点 RSS**（不打搜索接口，避开站点流控），新种子与当前订阅
          按剧名消歧后直接下载；RSS 没有的仍由主动搜索兜底。
        </div>
      </template>

      <v-divider class="my-3" />

      <!--
        ── 运行分区 ──
        与订阅无关的两项：发现任务多久跑一轮、作品墙点「搜索」去哪些站点。
        放在「订阅」之后，避免把「订到哪」和「多久扫一次」混在一起。
      -->
      <div class="sdas-block-head">
        <v-icon icon="mdi-cog-outline" size="20" class="mr-1" />
        <span class="sdas-block-title">运行</span>
        <span class="text-caption sdas-dim ml-2">发现频率，以及作品墙「搜索」用的站点</span>
      </div>

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

      <v-alert v-if="saveError" type="error" variant="tonal" density="compact" class="mb-2">
        {{ saveError }}
      </v-alert>

      <div class="d-flex align-center" style="gap: 8px">
        <v-spacer />
        <v-btn variant="text" @click="emit('close')">取消</v-btn>
        <v-btn color="primary" :loading="saving" @click="onSave">保存</v-btn>
      </div>
    </v-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import {
  fetchActorList,
  fetchDownloaderOptions,
  fetchDownloadPaths,
  fetchSearchSites,
  saveConfig,
} from './api'
import type { HostSite } from './api'
import type {
  DownloadClientOption,
  DownloadPathOption,
  PluginApi,
  PluginConfig,
  SubscribeMode,
  SubscribePrefer,
} from './types'

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
    subscribe_sites: '',
    subscribe_save_path: '',
    subscribe_mode: 'follow',
    subscribe_prefer: 'seeders',
    auto_subscribe: false,
    auto_subscribe_scope: 'new',
    auto_subscribe_max_per_run: 5,
    auto_subscribe_skip_library: true,
    subscribe_engine: 'host',
    self_interval_hours: 6,
    self_max_per_run: 5,
    self_max_pages: 3,
  }
}

/** 订阅范围选项：`new` 只订演员加入之后的新作品，`all` 连历史作品一起补订 */
const scopeOptions = [
  { title: '只订新作品（推荐）', value: 'new' },
  { title: '全部作品（含历史）', value: 'all' },
]

/** 订阅引擎选项：宿主订阅链 vs 插件自建订阅搜索 */
const engineOptions = [
  { title: '宿主订阅系统（默认）', value: 'host' },
  { title: '自建订阅搜索（全分类补搜）', value: 'self' },
]

const local = ref<PluginConfig>(defaults())
const saving = ref(false)
const saveError = ref('')

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

// ── 订阅站点（与搜索站点同一批选项，落到 subscribe_sites） ──

/** 把「逗号分隔的站点 ID 串」解析成数字数组（容错中文逗号 / 空白） */
function parseSiteIds(value: string): number[] {
  return String(value || '')
    .split(/[,，;；\s]+/)
    .map((item) => Number(item))
    .filter((id) => Number.isFinite(id) && id > 0)
}

const subscribeSiteIds = computed(() => parseSiteIds(local.value.subscribe_sites))

/** v-select 多选直接吃数组；写回时归一成逗号分隔字符串存配置 */
const subscribeSiteModels = computed<number[]>({
  get: () => subscribeSiteIds.value,
  set: (ids) => {
    const unique = Array.from(new Set(ids.filter((id) => Number.isFinite(id) && id > 0)))
    local.value.subscribe_sites = unique.join(',')
  },
})

/** 已勾选的排前面，组内保持原有顺序 */
const sortedSubscribeSiteOptions = computed<HostSite[]>(() => {
  const picked = new Set(subscribeSiteIds.value)
  const selected = siteOptions.value.filter((site) => picked.has(site.id))
  const rest = siteOptions.value.filter((site) => !picked.has(site.id))
  return [...selected, ...rest]
})

function selectAllSubscribeSites(): void {
  local.value.subscribe_sites = siteOptions.value.map((site) => site.id).join(',')
}

// ── 订阅下载目录 ──

const downloadPaths = ref<DownloadPathOption[]>([])
const downloadPathLoading = ref(true)

/** combobox 的候选：`title` 给人看（目录名），`value` 是真正提交给宿主的 save_path */
const downloadPathItems = computed(() =>
  downloadPaths.value.map((item) => ({
    title: item.name || item.download_path || item.save_path,
    subtitle: item.download_path || item.save_path,
    value: item.save_path,
    path: item.download_path || item.save_path,
    storage: item.storage,
  })),
)

/**
 * 路径比较用的归一：去空白、统一分隔符、折叠重复斜杠、**去掉尾部斜杠**。
 *
 * 宿主登记的目录名**可能带尾斜杠**（实测「短剧」= `/vol00/…/download/短剧/`），
 * 用户从系统目录里复制出来的是不带的那一版 —— 直接 `includes` 会因为一个 `/`
 * 判成「不在列表」，纯属误报。命中与否按归一后比，提交时再用宿主那份原值。
 */
function normalizePath(value: unknown): string {
  const text = String(value || '').trim().replace(/\\/g, '/')
  if (!text) return ''
  return text.replace(/\/{2,}/g, '/').replace(/\/+$/, '')
}

/**
 * 把 model 里可能出现的「非字符串」收敛成路径串。
 *
 * `v-combobox` 在 Vuetify 3 里 `return-object` **默认为 true**，选中候选时 v-model
 * 拿到的是整条 item 对象（`{title, subtitle, value, path, storage}`）而不是 `value`，
 * 于是 `String(obj)` 落库成字面量 `"[object Object]"` —— 界面输入框里显示的是目录名
 * （「短剧」），存进去的却是一个完全无效的值，宿主匹配不到就退回默认目录。
 * 这里显式兜底：对象取 `value` / 裸值；`"[object Object]"` 与 `[object Array]`
 * 这类残值一律当空处理（无从还原，交给用户重选）。
 */
function unwrapPathValue(value: unknown): string {
  if (value && typeof value === 'object') {
    const raw = value as { value?: unknown; save_path?: unknown }
    return String(raw.value ?? raw.save_path ?? '').trim()
  }
  const text = String(value ?? '').trim()
  return /^\[object [A-Za-z]+\]$/.test(text) ? '' : text
}

/** combobox 的 model：读写都过一遍 `unwrapPathValue`，防对象 / 残值回流配置 */
const savePathModel = computed<string>({
  get: () => unwrapPathValue(local.value.subscribe_save_path),
  set: (value) => {
    local.value.subscribe_save_path = unwrapPathValue(value)
  },
})

/** 当前配置值命中的候选（只差尾斜杠也算命中） */
const matchedPathOption = computed(() => {
  const key = normalizePath(savePathModel.value)
  if (!key) return null
  return downloadPathItems.value.find((item) => normalizePath(item.value) === key) || null
})

/** 命中了宿主的某个下载目录（不是「手输了一个宿主不认识的路径」） */
const savePathInList = computed(() => Boolean(matchedPathOption.value))

/** 命中但写法不同时，保存要用的**宿主原值**（提示 + onSave 都用它） */
const savePathAligned = computed(() => {
  const option = matchedPathOption.value
  if (!option) return ''
  const raw = savePathModel.value
  return option.value && option.value !== raw ? option.value : ''
})

/** 最终会提交给宿主的路径：命中候选用宿主原值，否则就是输入值本身 */
const effectiveSavePath = computed(
  () => matchedPathOption.value?.value || savePathModel.value,
)

/**
 * 目录列表到位后的一次性校准：配置里存的要是**目录名**（`短剧`）而不是 save_path，
 * 归一比较命中不了，但能和候选项的 `title` 对上 —— 这种就自动换成宿主的 save_path。
 * 真不是路径、也对不上名字的值（`[object Object]` 残值已被清空）保持原样，照常报警。
 */
function reconcileSavePath(): void {
  const raw = savePathModel.value
  if (!raw) return
  if (matchedPathOption.value) return
  const byName = downloadPathItems.value.find(
    (item) => item.title && normalizePath(item.title) === normalizePath(raw),
  )
  if (byName && byName.value) local.value.subscribe_save_path = byName.value
}

onMounted(async () => {
  try {
    downloadPaths.value = await fetchDownloadPaths(props)
  } finally {
    downloadPathLoading.value = false
  }
})

// 目录列表与配置谁先到不定，谁后到就校准一次（只校准首轮，之后用户改的值不再动）
let reconciled = false
watch(
  [() => downloadPathItems.value.length, () => savePathModel.value],
  () => {
    if (reconciled || !downloadPathItems.value.length) return
    reconciled = true
    reconcileSavePath()
  },
)

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
  // 老版本把对象序列化进了配置（`"[object Object]"`），装载时就清掉，
  // 否则输入框显示的是一串乱码值、还会顶着一条「不是宿主下载目录」的警告
  local.value.subscribe_save_path = unwrapPathValue(local.value.subscribe_save_path)
  // 名单里的 ID 要显示成名字：best-effort 拉一次关注列表（失败就原样显示 ID）
  fetchActorList(props)
    .then((rows) => {
      actorRows.value = rows
    })
    .catch(() => {
      /* 拉不到就算了：文本框退回显示 ID，不影响保存 */
    })
})

const actorItems = computed(() =>
  String(local.value.actors || '')
    .split(/[,，;；\n\r]+/)
    .map((item) => item.trim())
    .filter(Boolean),
)

// ── 关注名单的「ID ↔ 名字」显示 ──
// 名单以 ID 保存（ID 是唯一身份，2026-10-20），文本框里显示成名字才可读；
// 名字→ID 的映射来自 /actors（best-effort，拉不到就原样显示 ID）。

/** 关注名单的轻量行（key = 演员 ID，name = 展示名） */
const actorRows = ref<Array<{ key: string; name: string }>>([])

/** 演员 ID → 名字 */
const actorIdToName = computed<Record<string, string>>(() => {
  const map: Record<string, string> = {}
  for (const row of actorRows.value) {
    if (row.key && row.name) map[row.key] = row.name
  }
  return map
})

/** 名字 → 演员 ID（同名时存数组，文本框里用「名字｜ID」区分） */
const actorNameToIds = computed<Record<string, string[]>>(() => {
  const map: Record<string, string[]> = {}
  for (const row of actorRows.value) {
    if (!row.key || !row.name) continue
    ;(map[row.name] ||= []).push(row.key)
  }
  return map
})

/** 行内 ID 形态（复合 ID，与后端 `_actor_id_of` 同一口径） */
const ACTOR_ID_RE = /^(?:yanyuan|daoyan|bianju):\d+$/

const actorsDisplay = computed<string>({
  get() {
    const idToName = actorIdToName.value
    const nameCounts: Record<string, number> = {}
    for (const row of actorRows.value) {
      if (row.name) nameCounts[row.name] = (nameCounts[row.name] || 0) + 1
    }
    return actorItems.value
      .map((item) => {
        const name = idToName[item]
        if (!name) return item
        // 同名有两位：光显示名字分不清是谁，带 ID 后缀
        return (nameCounts[name] || 0) > 1 ? `${name}｜${item}` : name
      })
      .join('，')
  },
  set(value: string) {
    local.value.actors = String(value || '')
      .split(/[,，;；\n\r]+/)
      .map((line) => {
        const text = line.trim()
        if (!text) return ''
        // 「名字｜ID」形态：取 ID（同名区分后缀）
        const mixed = text.match(/^(.*)｜((?:yanyuan|daoyan|bianju):\d+)$/)
        if (mixed) return mixed[2]
        if (ACTOR_ID_RE.test(text)) return text
        // 纯名字：映射回 ID（同名取不出唯一 ID 时原样传，后端解析归位）
        const ids = actorNameToIds.value[text]
        return ids && ids.length === 1 ? ids[0] : text
      })
      .filter(Boolean)
      .join(',')
  },
})

async function onSave(): Promise<void> {
  saving.value = true
  saveError.value = ''
  try {
    // combobox clearable 清空时会把 model 置 null，落库前归一成空串
    const cleaned = String(local.value.subscribe_downloader || '').trim()
    // 下载目录：命中宿主登记项时**用宿主那份原值**（可能带尾斜杠 / `存储:` 前缀），
    // 宿主的 save_path 匹配是按目录名精确比的，少一个 `/` 就会退回默认目录。
    const cleanedPath = matchedPathOption.value
      ? matchedPathOption.value.value
      : unwrapPathValue(local.value.subscribe_save_path)
    // 单轮上限夹在 1..50（与后端 _AUTO_SUB_MAX_LIMIT 一致），空值回落默认 5
    const rawMax = Number(local.value.auto_subscribe_max_per_run)
    const maxPerRun = Number.isFinite(rawMax) && rawMax > 0 ? Math.min(50, Math.floor(rawMax)) : 5
    // 订阅类型只有三态，非法值回落 follow（后端 _subscribe_mode 同一口径）
    const rawMode = String(local.value.subscribe_mode || '')
    const mode: SubscribeMode = rawMode === 'normal' || rawMode === 'best' ? rawMode : 'follow'
    // 优选条件三态，非法值回落 seeders（后端 _subscribe_prefer 同一口径）
    const rawPrefer = String(local.value.subscribe_prefer || '')
    const prefer: SubscribePrefer =
      rawPrefer === 'size_desc' || rawPrefer === 'size_asc' ? rawPrefer : 'seeders'
    const payload = {
      ...local.value,
      subscribe_downloader: cleaned,
      subscribe_save_path: cleanedPath,
      subscribe_mode: mode,
      subscribe_prefer: prefer,
      auto_subscribe_max_per_run: maxPerRun,
    }
    await saveConfig(props, payload)
    emit('save', payload)
  } catch (err) {
    // 配置页原先没有 catch：保存失败（400 / 网络）会变成一条没人看的未捕获拒绝
    saveError.value = `保存失败：${err instanceof Error ? err.message : err}`
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.sdas-dim {
  opacity: 0.7;
}

/*
 * 分区标题（订阅那一大块）：比小节标题重一档 —— 左侧一条主色竖线 + 稍大字号，
 * 让人一眼看出「从这里开始是订阅」，而不是又一个小节。
 * 类名一律自有 `sdas-*`：联邦 CSS 门禁会丢掉含 `.v-` 的选择器。
 */
.sdas-block-head {
  display: flex;
  align-items: center;
  gap: 4px;
  margin: 4px 0 12px;
  padding-inline-start: 10px;
  border-inline-start: 3px solid rgb(var(--v-theme-primary));
  line-height: 1.4;
}

.sdas-block-title {
  font-size: 1rem;
  font-weight: 700;
}

.sdas-mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 0.75rem;
}
</style>
