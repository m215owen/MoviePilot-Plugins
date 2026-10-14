<template>
  <div class="sdas-root pa-2">
    <v-card variant="outlined" class="pa-4">
      <div class="d-flex align-center mb-3">
        <v-icon icon="mdi-movie-star-outline" class="mr-2" />
        <h3 class="ma-0">短剧演员订阅 · 设置</h3>
        <v-spacer />
        <v-btn icon="mdi-close" variant="text" size="small" title="关闭" @click="emit('close')" />
      </div>

      <v-alert type="info" variant="tonal" density="compact" class="mb-3">
        本插件<b>不走宿主订阅系统</b>：短剧在 TMDB / 豆瓣 大量没有条目，宿主识别器建不起媒体身份。
        这里改为「剧名 → 站点搜索」直达资源：发现源合并 TMDB 与豆瓣，同名以年份消歧
        （年份缺失放行），同剧多资源按 做种数 → 体积 → 分辨率 择优下一条。
      </v-alert>

      <v-row dense>
        <v-col cols="12" sm="6" md="3">
          <v-switch v-model="local.enabled" label="启用插件" color="primary" hide-details />
        </v-col>
        <v-col cols="12" sm="6" md="3">
          <v-switch
            v-model="local.sidebar_nav"
            label="侧栏「订阅」组里显示「短剧」入口"
            color="primary"
            hide-details
          />
        </v-col>
        <v-col cols="12" sm="6" md="3">
          <v-switch v-model="local.notify" label="发送系统通知" color="primary" hide-details />
        </v-col>
        <v-col cols="12" sm="6" md="3">
          <v-switch v-model="local.proxy" label="使用宿主代理" color="primary" hide-details />
        </v-col>
      </v-row>

      <v-divider class="my-3" />

      <!-- 演员 -->
      <div class="text-subtitle-2 mb-2">
        <v-icon icon="mdi-account-multiple-outline" size="18" class="mr-1" />
        订阅的演员
        <span class="text-caption sdas-dim ml-2">共 {{ actorItems.length }} 位</span>
      </div>

      <div class="d-flex align-center flex-wrap mb-2" style="gap: 8px">
        <v-text-field
          v-model="actorDraft"
          density="compact"
          variant="outlined"
          hide-details
          prepend-inner-icon="mdi-account-plus-outline"
          placeholder="输入演员名 / 豆瓣ID / TMDB ID / 主页链接后回车添加（可一次粘贴多个）"
          class="sdas-actor-input"
          @keyup.enter="addActorDraft"
        />
        <v-btn
          size="small"
          variant="tonal"
          color="primary"
          :disabled="!actorDraft.trim()"
          @click="addActorDraft"
        >
          添加
        </v-btn>
      </div>

      <v-textarea
        v-model="local.actors"
        density="comfortable"
        variant="outlined"
        hide-details
        rows="4"
        no-resize
        placeholder="多位演员用逗号分隔，例如：马秋元，王格格，申浩男"
        class="sdas-actor-textarea mb-2"
      />
      <div class="text-caption sdas-dim mb-3">
        填「人物 ID」可跳过按名称搜索（豆瓣搜索额度很紧，演员多时优先填 ID）。
        发现源同时查 TMDB 与豆瓣，两边结果按剧名 + 年份并集。
      </div>

      <v-text-field
        v-model="searchName"
        label="搜索演员（辅助填写人物 ID）"
        density="comfortable"
        hide-details
        prepend-inner-icon="mdi-magnify"
        class="mb-2"
        @keyup.enter="doSearchActor"
      >
        <template #append>
          <v-btn size="small" variant="tonal" :loading="searching" @click="doSearchActor">
            搜索
          </v-btn>
        </template>
      </v-text-field>

      <v-card v-if="candidates.length || searchMessage" variant="tonal" class="pa-2 mb-3">
        <div
          v-if="!candidates.length"
          class="d-flex align-center text-caption sdas-dim"
          style="gap: 8px"
        >
          <span>{{ searchMessage }}</span>
          <v-spacer />
          <v-btn size="x-small" variant="text" icon="mdi-close" title="关闭" @click="clearSearch" />
        </div>
        <div v-for="item in candidates" :key="`${item.source}:${item.id}`" class="d-flex align-center py-1">
          <v-chip size="x-small" variant="tonal" class="mr-2" :color="chipColor(item.source)">
            {{ item.source === 'tmdb' ? 'TMDB' : '豆瓣' }}
          </v-chip>
          <span class="text-body-2">{{ item.name }}</span>
          <span v-if="item.original_name && item.original_name !== item.name" class="text-caption sdas-dim ml-2">
            {{ item.original_name }}
          </span>
          <span class="text-caption sdas-dim ml-2">ID {{ item.id }}</span>
          <v-btn
            size="x-small"
            variant="tonal"
            color="primary"
            density="compact"
            class="ml-2"
            @click="appendActor(item.id)"
          >
            添加 ID
          </v-btn>
        </div>
      </v-card>

      <v-divider class="my-3" />

      <!-- 搜索与下载 -->
      <div class="text-subtitle-2 mb-2">
        <v-icon icon="mdi-magnify-scan" size="18" class="mr-1" />
        搜索范围与下载
      </div>
      <v-row dense>
        <v-col cols="12" md="6">
          <v-select
            v-model="local.sites"
            :items="options.sites"
            label="搜索站点"
            multiple
            chips
            closable-chips
            density="comfortable"
            hint="不选则无法搜索；建议只选确有短剧资源的站点"
            persistent-hint
          />
        </v-col>
        <v-col cols="12" md="6">
          <v-select
            v-model="local.downloader"
            :items="downloaderItems"
            label="下载器"
            clearable
            density="comfortable"
            :hint="downloaderHint"
            persistent-hint
          />
        </v-col>
        <v-col cols="12">
          <div class="text-caption sdas-dim">
            下载器与下载路径的候选来自宿主「系统设置 → 下载器 / 目录管理」，
            默认值已按系统配置预填，无需手抄路径。
          </div>
        </v-col>
        <v-col cols="12">
          <v-switch
            v-model="local.use_baike"
            label="使用「短剧百科」发现演员作品（推荐）"
            color="primary"
            hide-details
            density="compact"
          />
          <div class="text-caption sdas-dim">
            默认<b>开启</b>：经跨插件通道调用 ShortDramaBaikeSource，按演员名在
            duanjubaike.org 取全部参演作品（短剧覆盖比 TMDB/豆瓣全得多）。
            每位演员首次解析要多花约 10 秒（站外索引检索一次），之后按缓存的百科 ID 直连演员页。
            关闭即回到「TMDB + 豆瓣」并集。
          </div>
        </v-col>
        <v-col cols="12">
          <v-switch
            v-model="local.prefer_short_drama_category"
            label="优先在站点「短剧」分类内搜索（可显著降低同名误命中；站点没有该分类时自动退化为全站搜索）"
            color="primary"
            hide-details
            density="compact"
          />
        </v-col>
      </v-row>

      <v-divider class="my-3" />

      <!-- 下载与入库 -->
      <div class="d-flex align-center mb-2 flex-wrap" style="gap: 8px">
        <span class="text-subtitle-2">
          <v-icon icon="mdi-download-outline" size="18" class="mr-1" />
          下载与入库
        </span>
        <v-chip v-if="shortDramaDirectory" size="x-small" variant="tonal" color="primary">
          检测到系统「短剧」目录
        </v-chip>
        <v-spacer />
        <v-btn
          size="small"
          variant="text"
          color="primary"
          :disabled="!options.defaults.directory"
          @click="applySystemDefaults"
        >
          采用系统推荐路径
        </v-btn>
      </div>
      <v-switch
        v-model="local.auto_download"
        label="自动下载（不推荐）"
        color="primary"
        hide-details
        density="compact"
      />
      <div class="text-caption sdas-dim mb-3">
        默认<b>关闭</b>：定时轮询只负责发现 —— 把新作品摆到作品墙，<b>你在作品墙点「订阅」才会下载</b>。
        打开后，轮询会把快照里<b>所有没下过的作品</b>挨个搜索下载（演员一多就是上千个种子），
        会把下载器灌爆，而且这类批量提交不可逆，请谨慎打开。
      </div>
      <v-switch
        v-model="local.organize_enabled"
        label="由本插件整理入库"
        color="primary"
        hide-details
        density="compact"
      />
      <div class="text-caption sdas-dim mb-3">
        默认<b>关闭</b>：本插件只负责「发现 → 下载」，入库交给外部整理器
        （如 shortdramaorganizer）。同一台机器上跑两个整理器会重复入库；确实没有外部整理器时再打开。
      </div>
      <v-row dense>
        <v-col cols="12" :md="local.organize_enabled ? 6 : 8">
          <v-combobox
            v-model="local.download_path"
            :items="directoryItems"
            item-title="title"
            item-value="value"
            label="下载目录（下载器保存路径）"
            density="comfortable"
            :hint="directoryHint"
            persistent-hint
            @update:model-value="onPickDirectory"
          />
        </v-col>
        <v-col v-if="local.organize_enabled" cols="12" md="6">
          <v-combobox
            v-model="local.library_path"
            :items="libraryItems"
            label="媒体库根目录"
            density="comfortable"
            hint="与下载目录成对，来自宿主「目录管理」；整理后放到 <该目录>/剧名 (年份)/"
            persistent-hint
            @update:model-value="onPickLibrary"
          />
        </v-col>
        <v-col cols="6" md="4">
          <v-text-field
            v-model.number="local.interval_hours"
            type="number"
            min="1"
            max="168"
            label="订阅轮询间隔（小时）"
            density="comfortable"
          />
        </v-col>
        <v-col cols="6" md="4">
          <v-text-field
            v-model.number="local.snapshot_hours"
            type="number"
            min="1"
            max="720"
            label="快照刷新间隔（小时）"
            density="comfortable"
            hint="演员作品清单多久重新拉一次；期间轮询直接用缓存，避免频繁请求豆瓣"
            persistent-hint
          />
        </v-col>
        <v-col cols="6" md="4">
          <v-text-field
            v-model.number="local.retry_minutes"
            type="number"
            min="1"
            max="1440"
            label="失败重试间隔（分钟）"
            density="comfortable"
            hint="解析失败的演员多久后单独重试一次（豆瓣登录态恢复后能很快自愈）"
            persistent-hint
          />
        </v-col>
        <v-col v-if="local.organize_enabled" cols="6" md="4">
          <v-select
            v-model="local.transfer_type"
            :items="options.transfer_types"
            label="整理方式"
            density="comfortable"
          />
        </v-col>
        <v-col v-if="local.organize_enabled" cols="6" md="4">
          <v-text-field
            v-model.number="local.organize_interval_minutes"
            type="number"
            min="5"
            max="1440"
            label="整理扫描间隔（分钟）"
            density="comfortable"
          />
        </v-col>
      </v-row>

      <v-divider class="my-3" />

      <!-- 豆瓣 Cookie -->
      <div class="text-subtitle-2 mb-2">
        <v-icon icon="mdi-cookie-outline" size="18" class="mr-1" />
        豆瓣 Cookie（提高搜索额度）
      </div>
      <v-alert type="info" variant="tonal" density="compact" class="mb-2">
        默认<b>自动</b>从宿主「系统设置 → CookieCloud」读取豆瓣登录态，这里无需填写。
        仅当 CookieCloud 没同步豆瓣、或想临时换账号时才手工粘贴覆盖。
      </v-alert>
      <v-textarea
        v-model="local.douban_cookie"
        label="豆瓣 Cookie（留空 = 自动用宿主 CookieCloud）"
        placeholder="bid=xxx; dbcl2=xxx; ck=xxx"
        rows="2"
        density="comfortable"
        auto-grow
        class="mb-2"
      />
      <div class="text-caption sdas-dim mb-1">
        当前生效来源：{{ cookieStatus }}
      </div>

      <v-divider class="my-3" />

      <div class="d-flex align-center flex-wrap" style="gap: 8px">
        <v-btn color="primary" :loading="saving" @click="saveConfig">保存配置</v-btn>
        <v-btn variant="text" @click="emit('switch')">查看详情</v-btn>
        <v-spacer />
        <span class="text-caption sdas-dim">保存后立即生效（后台会重新初始化插件）</span>
      </div>
    </v-card>
  </div>
</template>

<script setup lang="ts">
/**
 * 插件配置页（联邦暴露名 ./Config）。
 *
 * 保存方式遵循官方约定：`emit('save', cfg)`，由宿主持久化并重新初始化插件；
 * 组件自己也调一次插件接口（PUT /config）是为了让「侧栏全页里改配置」也能落盘，
 * 两者语义等价、不会互相冲突（宿主用的是同一份配置字典）。
 */
import { computed, onMounted, reactive, ref } from 'vue'
import { fetchOptions, resolveApi, saveConfig as putConfig, searchActor } from './api'
import type {
  ActorCandidate,
  DirectoryOption,
  DownloaderOption,
  OptionsDefaults,
  OptionsPayload,
  PluginApi,
  PluginConfig,
  SiteOption,
  TransferTypeOption,
} from './types'

const props = defineProps<{
  /** 宿主传入的初始配置 */
  initialConfig?: Partial<PluginConfig>
  /** 宿主注入的 axios 实例 */
  api?: PluginApi
}>()

const emit = defineEmits(['save', 'close', 'switch'])

const saving = ref(false)

const defaults: PluginConfig = {
  enabled: false,
  onlyonce: false,
  actors: '',
  sites: [],
  prefer_short_drama_category: true,
  downloader: '',
  download_path: '',
  library_path: '',
  transfer_type: 'link',
  interval_hours: 6,
  snapshot_hours: 24,
  retry_minutes: 20,
  organize_enabled: false,
  organize_interval_minutes: 30,
  auto_download: false,
  use_baike: true,
  notify: true,
  douban_cookie: '',
  proxy: false,
  max_works: 10,
  sidebar_nav: true,
}

const local = reactive<PluginConfig>({ ...defaults })

/** 下拉候选：先给空壳 + 兜底项，接口回来后覆盖 */
const options = reactive<OptionsPayload>({
  sites: [] as SiteOption[],
  downloaders: [] as DownloaderOption[],
  transfer_types: [
    { title: '硬链接（推荐，省空间，需同盘）', value: 'link' },
    { title: '软链接（跨盘可用，指向下载文件）', value: 'softlink' },
    { title: '复制', value: 'copy' },
    { title: '移动', value: 'move' },
  ] as TransferTypeOption[],
  directories: [] as DirectoryOption[],
  defaults: {
    downloader: '',
    directory: '',
    library_path: '',
    directory_name: '',
  } as OptionsDefaults,
})

// ─── 系统配置派生项（下载器 / 目录） ─────────────────────────────

/** 下载器候选：把系统默认那个标出来，用户一眼能看到留空等于用哪个 */
const downloaderItems = computed(() =>
  options.downloaders.map((item) => ({
    title: item.default ? `${item.title}（系统默认）` : item.title,
    value: item.value,
  }))
)

const downloaderHint = computed(() => {
  const prefer = options.defaults.downloader
  return prefer ? `留空则跟随宿主默认（${prefer}）` : '留空则跟随宿主默认下载器'
})

/** 下载目录候选（来自宿主「目录管理」，「短剧」目录加星标） */
const directoryItems = computed(() =>
  options.directories
    .filter((item) => item.download_path)
    .map((item) => ({
      title: item.is_short_drama ? `★ ${item.title}` : item.title,
      value: item.download_path,
    }))
)

/** 媒体库目录候选（同一份目录配置里的 library_path） */
const libraryItems = computed(() =>
  Array.from(
    new Set(options.directories.map((item) => item.library_path).filter((item) => !!item))
  )
)

const directoryHint = computed(() => {
  const count = options.directories.length
  if (!count) return '未从系统读到目录配置，可直接手工填写路径'
  return `共 ${count} 个系统目录，可下拉选择或直接输入；既用于提交下载，也作为整理扫描目录`
})

/** 系统里那个「短剧」目录（有的话配置页给出显式提示） */
const shortDramaDirectory = computed(
  () => options.directories.find((item) => item.is_short_drama) || null
)

/**
 * 把 v-combobox 回写的值取成纯字符串。
 *
 * ⚠️ 这版 Vuetify 的 `v-combobox` **不认 `item-value`**：`:items` 是
 * `{title, value}` 对象数组时，选中一项会把**整个 item 对象**写回 `v-model`
 * （`v-select` 才只回写 value）。于是配置里会存成
 * `{"title": "★ 短剧（/vol00/…）", "value": "/vol00/…"}` 这种脏值，
 * 后端拿到就不是路径了。这里统一取 value，保证落库的是路径字符串。
 */
function pickValue(value: unknown): string {
  if (value && typeof value === 'object') {
    const item = value as Record<string, unknown>
    return String(item.value ?? item.title ?? '').trim()
  }
  return String(value ?? '').trim()
}

/** 选中系统目录后，若媒体库目录还是空的或仍是自动填的，就跟着一起更新 */
function onPickDirectory(value: unknown): void {
  const path = pickValue(value)
  local.download_path = path // 把可能写进来的 item 对象换回字符串
  if (!path) return
  const hit = options.directories.find((item) => item.download_path === path)
  if (!hit) return
  const current = String(local.library_path || '').trim()
  const autoFilled = options.directories.some(
    (item) => item.library_path && item.library_path === current
  )
  if (!current || autoFilled) {
    local.library_path = hit.library_path || ''
  }
}

/** 媒体库目录同样归一化（items 是字符串数组，但历史脏值可能是对象） */
function onPickLibrary(value: unknown): void {
  local.library_path = pickValue(value)
}

/** 一键采用系统推荐（优先「短剧」目录 + 系统默认下载器） */
function applySystemDefaults(): void {
  const defaults = options.defaults
  if (!defaults) return
  if (defaults.directory) local.download_path = defaults.directory
  if (defaults.library_path) local.library_path = defaults.library_path
  if (defaults.downloader && !String(local.downloader || '').trim()) {
    local.downloader = defaults.downloader
  }
}

/** Cookie 来源回显（manual / cookiecloud / none） */
const cookieStatus = computed<string>(() => {
  const source = String(
    (props.initialConfig as Record<string, unknown> | undefined)?.douban_cookie_source || ''
  )
  if (source === 'manual') return '插件内手填的 Cookie'
  if (source === 'cookiecloud') return '宿主 CookieCloud（自动读取，已生效）'
  if (source) return '未取到登录态（豆瓣匿名搜索额度极低）'
  return '读取中…'
})

function chipColor(source: string): string {
  return source === 'tmdb' ? 'teal' : 'green'
}

// ─── 演员列表（文本，逗号分隔，与后端 _parse_actors 口径一致） ────

const actorItems = computed<string[]>(() =>
  String(local.actors || '')
    .split(/[\r\n,，、;；]+/)
    .map((item) => item.trim())
    .filter(Boolean)
)

const actorDraft = ref('')

/** 统一写回演员列表：去重保序，用中文逗号连接 */
function commitActorItems(items: string[]): void {
  const seen = new Set<string>()
  const next: string[] = []
  for (const item of items) {
    const value = String(item || '').trim()
    if (!value || seen.has(value)) continue
    seen.add(value)
    next.push(value)
  }
  local.actors = next.join('，')
}

function addActorDraft(): void {
  const parts = String(actorDraft.value || '')
    .split(/[\r\n,，、;；]+/)
    .map((item) => item.trim())
    .filter(Boolean)
  if (!parts.length) return
  commitActorItems([...actorItems.value, ...parts])
  actorDraft.value = ''
}

// ─── 演员搜索 ───────────────────────────────────────────────────

const searchName = ref('')
const searching = ref(false)
const searchMessage = ref('')
const candidates = ref<ActorCandidate[]>([])

async function doSearchActor(): Promise<void> {
  const api = resolveApi(props)
  const name = searchName.value.trim()
  if (!api || !name) return
  searching.value = true
  try {
    const res = await searchActor(api, name)
    candidates.value = res.data
    searchMessage.value = candidates.value.length
      ? ''
      : res.message || '未找到匹配的演员，换一个名字或直接填写人物 ID。'
  } finally {
    searching.value = false
  }
}

function clearSearch(): void {
  candidates.value = []
  searchMessage.value = ''
}

/** 把搜索结果的 ID 追加进演员列表（后端能按纯数字 ID 直接解析，不走搜索） */
function appendActor(id: string): void {
  commitActorItems([...actorItems.value, id])
}

// ─── 候选与保存 ─────────────────────────────────────────────────

async function loadOptions(): Promise<void> {
  const api = resolveApi(props)
  if (!api) return
  try {
    const data = await fetchOptions(api)
    if (!data) return
    options.sites = data.sites || []
    options.downloaders = data.downloaders || []
    options.directories = data.directories || []
    if (data.defaults) options.defaults = data.defaults
    if (data.transfer_types?.length) options.transfer_types = data.transfer_types

    // 下载路径与下载器默认跟随宿主系统配置：只在用户还没填过时预填，
    // 已经填好的值（无论是手填还是上次保存的）一律不动。
    if (!String(local.download_path || '').trim() && options.defaults.directory) {
      local.download_path = options.defaults.directory
      if (!String(local.library_path || '').trim()) {
        local.library_path = options.defaults.library_path
      }
    }
    if (!String(local.downloader || '').trim() && options.defaults.downloader) {
      local.downloader = options.defaults.downloader
    }
  } catch (err) {
    console.warn('[ShortDramaActorSubscribe] 读取下拉候选失败', err)
  }
}

/**
 * 保存：先抛 `save` 事件让宿主统一持久化（官方约定），
 * 同时调一次插件自己的 PUT /config，保证侧栏全页与详情页两条途径都能落盘。
 */
async function saveConfig(): Promise<void> {
  saving.value = true
  const payload = JSON.parse(JSON.stringify(local)) as PluginConfig
  // 路径字段再兜一层：即便是历史脏值（item 对象）也在此刻收敛成字符串
  payload.download_path = pickValue(payload.download_path)
  payload.library_path = pickValue(payload.library_path)
  payload.transfer_type = pickValue(payload.transfer_type) || 'link'
  emit('save', payload)
  const api = resolveApi(props)
  if (api) {
    const res = await putConfig(api, payload)
    if (!res.ok) console.warn('[ShortDramaActorSubscribe] 保存配置失败：', res.message)
  }
  window.setTimeout(() => {
    saving.value = false
  }, 600)
}

onMounted(() => {
  const initial = props.initialConfig
  if (initial && typeof initial === 'object') {
    Object.keys(defaults).forEach((key) => {
      const value = (initial as Record<string, unknown>)[key]
      if (value !== undefined) {
        ;(local as Record<string, unknown>)[key] = value
      }
    })
  }
  // 历史脏值自愈：早期版本把 v-combobox 的 item 对象写进了路径字段，
  // 不修的话页面会显示 [object Object]、且整理必然失败
  local.download_path = pickValue(local.download_path)
  local.library_path = pickValue(local.library_path)
  void loadOptions()
})
</script>

<style scoped>
/* 只使用 scoped 样式；不要编写会全局生效的选择器（组件库类名、html、body、:root） */
.sdas-dim {
  opacity: 0.75;
}

/* 演员再多也不会把配置页撑长 */
.sdas-actor-textarea {
  max-height: 200px;
}

.sdas-actor-input {
  flex: 1 1 260px;
  min-width: 220px;
}
</style>
