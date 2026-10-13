<template>
  <div class="das-root pa-2">
    <v-card variant="outlined" class="pa-4">
      <div class="d-flex align-center mb-3">
        <v-icon icon="mdi-cog-outline" class="mr-2" />
        <h3 class="ma-0">豆瓣演员订阅 · 设置</h3>
        <v-spacer />
        <v-btn icon="mdi-close" variant="text" size="small" title="关闭" @click="emit('close')" />
      </div>

      <!-- 运行异常：自动弹出 5 秒后收起为小标签；手动点开「N 项异常」后常驻展开，不再自动缩起 -->
      <ErrorAlerts :errors="runtimeErrors" class="mb-3" />

      <v-row dense>
        <v-col cols="12" sm="6" md="3">
          <v-switch v-model="local.enabled" label="启用插件" color="primary" hide-details />
        </v-col>
        <v-col cols="12" sm="6" md="3">
          <v-switch
            v-model="local.sidebar_nav"
            label="在 MP 侧栏显示入口"
            color="primary"
            hide-details
          />
        </v-col>
        <v-col cols="12" sm="6" md="3">
          <v-switch v-model="local.proxy" label="使用代理服务器" color="primary" hide-details />
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

      <!-- 演员配置：文本形式，逗号分隔。演员多时固定高度、内部滚动，不会把页面撑长 -->
      <div class="text-subtitle-2 mb-2">
        <v-icon icon="mdi-account-multiple-outline" size="18" class="mr-1" />
        订阅的演员
        <span class="text-caption das-dim ml-2">共 {{ actorItems.length }} 位</span>
      </div>

      <!-- 快捷添加：与行式列表时同一套输入框，回车 / 点「添加」并入下方文本列表 -->
      <div class="d-flex align-center flex-wrap mb-2" style="gap: 8px">
        <v-text-field
          v-model="actorDraft"
          density="compact"
          variant="outlined"
          hide-details
          prepend-inner-icon="mdi-account-plus-outline"
          placeholder="输入演员名 / 人物 ID / 主页链接后回车添加（可一次粘贴多个）"
          class="das-actor-input"
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
        v-model="actorsText"
        density="comfortable"
        variant="outlined"
        hide-details
        rows="5"
        no-resize
        placeholder="多位演员用逗号分隔，例如：刘德华，吴京，张译"
        class="das-actor-textarea mb-2"
      />
      <div class="text-caption das-dim mb-3">
        用逗号分隔（也支持换行 / 顿号）；填「人物 ID」或人物主页链接可跳过搜索——豆瓣搜索限流很紧，演员多时优先填 ID。
      </div>

      <v-text-field
        v-model="searchName"
        label="搜索豆瓣演员（辅助填写人物 ID）"
        density="comfortable"
        hide-details
        prepend-inner-icon="mdi-magnify"
        class="mb-2"
        @keyup.enter="searchActor"
      >
        <template #append>
          <v-btn size="small" variant="tonal" :loading="searching" @click="searchActor">
            搜索
          </v-btn>
        </template>
      </v-text-field>

      <v-card v-if="candidates.length || searched" variant="tonal" class="pa-2 mb-3">
        <div v-if="!candidates.length" class="d-flex align-center text-caption das-dim" style="gap: 8px">
          <span>{{ searchMessage || '未搜索到匹配的演员，换一个名字或直接填写人物 ID。' }}</span>
          <v-spacer />
          <v-btn size="x-small" variant="text" icon="mdi-close" title="关闭提示" @click="searched = false" />
        </div>
        <!-- 添加按钮紧跟「ID xxxx」之后：不再用 v-spacer 推到行尾，避免鼠标要跨半个屏幕 -->
        <div
          v-for="item in candidates"
          :key="item.id"
          class="d-flex align-center py-1"
        >
          <v-avatar size="28" class="mr-2">
            <v-img v-if="item.avatar" :src="item.avatar" />
            <v-icon v-else icon="mdi-account-outline" size="16" />
          </v-avatar>
          <span class="text-body-2">{{ item.name }}</span>
          <span class="text-caption das-dim ml-2">ID {{ item.id }}</span>
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

      <!-- 豆瓣登录态：匿名搜索额度只有个位数，配上 Cookie 才能稳定按名称解析演员 -->
      <div class="text-subtitle-2 mb-2">
        <v-icon icon="mdi-cookie-outline" size="18" class="mr-1" />
        豆瓣 Cookie（提高搜索额度）
      </div>
      <v-alert type="info" variant="tonal" density="compact" class="mb-2">
        默认<b>自动</b>从宿主「系统设置 → CookieCloud」读取豆瓣登录态，这里无需填写。
        仅当 CookieCloud 没同步豆瓣、或想临时换一个账号时，才在下面手工粘贴覆盖。
      </v-alert>
      <v-textarea
        v-model="local.douban_cookie"
        label="豆瓣 Cookie（留空 = 自动用宿主 CookieCloud）"
        placeholder="bid=xxx; dbcl2=xxx; ck=xxx"
        hint="浏览器登录豆瓣后按 F12 → 网络 → 任意 douban.com 请求 → 请求头 Cookie 整段复制（务必含 dbcl2）。"
        persistent-hint
        rows="2"
        density="comfortable"
        auto-grow
        class="mb-2"
      />
      <div class="text-caption das-dim mb-3" :title="cookieHint">
        当前生效来源：{{ cookieStatus }}
        <v-icon v-if="cookieHint" icon="mdi-information-outline" size="13" class="ml-1" />
      </div>

      <v-divider class="my-3" />

      <!-- 抓取与展示 -->
      <div class="text-subtitle-2 mb-2">
        <v-icon icon="mdi-tune-variant" size="18" class="mr-1" />
        抓取与展示
      </div>
      <v-row dense>
        <v-col cols="12" sm="6">
          <v-select
            v-model="cronPreset"
            :items="cronPresets"
            item-title="label"
            item-value="value"
            label="刷新周期预设"
            density="comfortable"
          />
        </v-col>
        <v-col cols="12" sm="6">
          <v-text-field
            v-model="local.cron"
            label="cron 表达式"
            hint="5 段式，例如 0 8 * * * 表示每天 08:00"
            persistent-hint
            density="comfortable"
          />
        </v-col>
        <v-col cols="12" sm="4">
          <v-text-field
            v-model.number="local.max_works"
            type="number"
            min="5"
            max="10"
            label="每位演员展示作品数"
            hint="豆瓣作品集接口不支持翻页，最多只能取到 10 部"
            persistent-hint
            density="comfortable"
          />
        </v-col>
        <v-col cols="12" sm="4">
          <v-select
            v-model="local.sort_by"
            :items="sortOptions"
            item-title="label"
            item-value="value"
            label="作品排序"
            density="comfortable"
          />
        </v-col>
        <v-col cols="12" sm="4">
          <v-switch
            v-model="local.notify"
            label="刷新后发送系统通知"
            color="primary"
            hide-details
            class="mt-1"
          />
        </v-col>
      </v-row>

      <v-divider class="my-3" />

      <!-- 自动订阅 -->
      <div class="text-subtitle-2 mb-2">
        <v-icon icon="mdi-auto-fix" size="18" class="mr-1" />
        自动订阅
      </div>
      <v-switch
        v-model="local.auto_subscribe"
        label="开启自动订阅：把新发现的、满足条件的作品直接提交订阅"
        color="primary"
        hide-details
        class="mb-2"
      />
      <template v-if="local.auto_subscribe">
        <v-switch
          v-model="local.auto_only_new"
          label="仅订阅新出现的作品（首次抓取只建立基线，避免一次性订阅全部历史作品）"
          color="primary"
          hide-details
          density="compact"
          class="mb-3"
        />
        <v-row dense>
          <v-col cols="12" sm="4">
            <v-text-field
              v-model.number="local.auto_min_vote"
              type="number"
              step="0.5"
              min="0"
              max="10"
              label="最低豆瓣评分"
              hint="0 表示不限制"
              persistent-hint
              density="comfortable"
            />
          </v-col>
          <v-col cols="12" sm="4">
            <v-text-field
              v-model.number="local.auto_max_per_run"
              type="number"
              min="1"
              max="100"
              label="单次订阅上限"
              hint="防止首次开启时批量误订阅"
              persistent-hint
              density="comfortable"
            />
          </v-col>
          <v-col cols="12" sm="4">
            <div class="text-caption mb-1">参与自动订阅的类型</div>
            <v-btn-toggle v-model="autoTypes" multiple density="compact" variant="outlined" divided>
              <v-btn size="small" value="电影">电影</v-btn>
              <v-btn size="small" value="电视剧">电视剧</v-btn>
            </v-btn-toggle>
          </v-col>
        </v-row>
      </template>

      <v-divider class="my-3" />

      <!-- 订阅选项：下载保存路径 + 下载器 + 订阅站点，随本页「保存配置」一起持久化 -->
      <div class="text-subtitle-2 mb-2">
        <v-icon icon="mdi-tune-variant" size="18" class="mr-1" />
        订阅选项
      </div>
      <SubscribePrefs
        v-model:save-path="local.subscribe_save_path"
        v-model:downloader="local.subscribe_downloader"
        v-model:sites="local.subscribe_sites"
        :api="props.api"
        :show-save="false"
      />

      <v-alert type="info" variant="tonal" density="compact" class="my-3">
        保存由宿主完成：本组件只向宿主抛出 <code>save</code> 事件，
        宿主会调用 <code>api.put('plugin/{id}', cfg)</code> 持久化并重新初始化插件。
      </v-alert>

      <div class="d-flex">
        <v-btn color="primary" :loading="saving" @click="saveConfig">保存配置</v-btn>
        <v-btn variant="text" class="ml-2" @click="emit('switch')">查看详情</v-btn>
      </div>
    </v-card>
  </div>
</template>

<script setup lang="ts">
/**
 * 插件配置页（联邦暴露名 ./Config）。
 *
 * 保存方式遵循官方约定：`emit('save', cfg)`，由宿主统一持久化，
 * 不要在组件内自行拼接 `api/v1/plugin/...` 路径。
 */
import { computed, onMounted, reactive, ref } from 'vue'
import ErrorAlerts from './ErrorAlerts.vue'
import SubscribePrefs from './SubscribePrefs.vue'
import { API_BASE, PLUGIN_ID, resolveApi, unwrap } from './api'
import type {
  ActorCandidate,
  ApiResult,
  PluginApi,
  PluginConfig,
  WorksPayload,
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
  sidebar_nav: true,
  cron: '0 8 * * *',
  actors: '',
  max_works: 10,
  sort_by: 'time',
  proxy: false,
  notify: false,
  auto_subscribe: false,
  auto_only_new: true,
  auto_min_vote: 0,
  auto_types: '电影,电视剧',
  auto_max_per_run: 5,
  onlyonce: false,
  subscribe_save_path: '',
  subscribe_downloader: '',
  subscribe_sites: [],
  douban_cookie: '',
}

const local = reactive<PluginConfig>({ ...defaults })

/**
 * 当前生效的 Cookie 来源。
 *
 * 来源由后端快照给出（`douban_cookie_source`），这里只做展示——
 * 用户最需要知道的是「到底有没有用上登录态」，而不是自己去猜。
 */
const cookieSource = computed<string>(() => {
  const initial = props.initialConfig as Record<string, unknown> | undefined
  return String(initial?.douban_cookie_source || 'none')
})

/**
 * Cookie 状态只保留一句短文案，完整失败原因收进 hover 提示。
 *
 * 之前把整段错误原文直接挂在页面上，只要没配好就一直在，既占位置又容易被
 * 误读成「插件坏了」。
 */
const cookieStatus = computed<string>(() => {
  if (cookieSource.value === 'manual') return '插件内手填的 Cookie'
  if (cookieSource.value === 'cookiecloud') return '宿主 CookieCloud（自动读取，已生效）'
  return '未取到登录态（悬停查看原因）'
})

/** 未取到 Cookie 时的原因，仅在悬停时展示 */
const cookieHint = computed<string>(() => {
  if (cookieSource.value === 'manual' || cookieSource.value === 'cookiecloud') return ''
  const initial = props.initialConfig as Record<string, unknown> | undefined
  const hint = initial?.douban_cookie_hint
  return hint ? String(hint) : '尚未取到：刷新一次后会显示原因'
})

/** 常用 cron 预设 */
const cronPresets = [
  { label: '每 6 小时', value: '0 */6 * * *' },
  { label: '每 12 小时', value: '0 */12 * * *' },
  { label: '每天 08:00', value: '0 8 * * *' },
  { label: '每天 20:00', value: '0 20 * * *' },
  { label: '每周一 08:00', value: '0 8 * * 1' },
]

const sortOptions = [
  { label: '按时间（最新作品优先）', value: 'time' },
  { label: '豆瓣默认（最受关注优先）', value: 'collection' },
]

/** 预设与自定义 cron 的双向绑定 */
const cronPreset = computed({
  get: () => (cronPresets.some((item) => item.value === local.cron) ? local.cron : ''),
  set: (value: string) => {
    if (value) local.cron = value
  },
})

/** 「电影,电视剧」字符串 与 多选按钮组 的双向绑定 */
const autoTypes = computed<string[]>({
  get: () =>
    String(local.auto_types || '')
      .split(/[,，;；]/)
      .map((item) => item.trim())
      .filter((item) => item === '电影' || item === '电视剧'),
  set: (value: string[]) => {
    local.auto_types = (value && value.length ? value : ['电影', '电视剧']).join(',')
  },
})

// ─── 演员列表（文本，逗号分隔） ────────────────────────────────

/**
 * 演员列表以「逗号分隔文本」配置与展示。
 *
 * 后端 `_parse_actors` 兼容逗号 / 换行 / 顿号 / 分号等分隔符；
 * 这里统一拆分成数组用于计数，展示时用中文逗号连接。
 */
const actorItems = computed<string[]>(() =>
  String(local.actors || '')
    .split(/[\r\n,，、;；]+/)
    .map((item) => item.trim())
    .filter(Boolean)
)

/** 文本域绑定：读时用「，」连接，写时原样存回（交给后端解析） */
const actorsText = computed<string>({
  get: () => actorItems.value.join('，'),
  set: (value: string) => {
    local.actors = String(value || '')
  },
})

/** 统一写回演员列表：去重且保持顺序，用「，」连接 */
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

/** 快捷添加输入框的草稿（回车 / 点「添加」后并入文本列表） */
const actorDraft = ref('')

/** 追加草稿内容（支持一次粘贴多个：逗号 / 顿号 / 分号 / 换行分隔） */
function addActorDraft(): void {
  const parts = String(actorDraft.value || '')
    .split(/[\r\n,，、;；]+/)
    .map((item) => item.trim())
    .filter(Boolean)
  if (!parts.length) return
  commitActorItems([...actorItems.value, ...parts])
  actorDraft.value = ''
}

// ─── 演员搜索辅助 ─────────────────────────────────────────────

const searchName = ref('')
const searching = ref(false)
const searched = ref(false)
/** 搜索失败原因（限流 / need_login / 查无此人），在结果区给出可读说明 */
const searchMessage = ref('')
const candidates = ref<ActorCandidate[]>([])

/** 搜索豆瓣演员，便于拿到准确的人物 ID */
async function searchActor(): Promise<void> {
  const api = resolveApi(props)
  const name = searchName.value.trim()
  if (!api || !name) return
  searching.value = true
  try {
    const raw = await api.get(`${API_BASE}/search_actor`, { params: { name } })
    const res = unwrap<ApiResult<ActorCandidate[]>>(raw)
    candidates.value = res?.success ? res.data || [] : []
    searched.value = true
    // 失败原因（限流 / need_login）必须说清楚，否则用户会以为是自己名字写错了
    searchMessage.value = res?.success
      ? candidates.value.length
        ? ''
        : '未搜索到匹配的演员，换一个名字或直接填写人物 ID。'
      : res?.message || '搜索失败，请稍后重试。'
  } catch (err) {
    candidates.value = []
    searched.value = true
    searchMessage.value = '搜索失败，请稍后重试。'
    console.warn(`[${PLUGIN_ID}] 搜索演员失败`, err)
  } finally {
    searching.value = false
  }
}

/** 把搜索结果的人物 ID 追加到演员列表 */
function appendActor(id: string): void {
  commitActorItems([...actorItems.value, id])
}

/** 提交保存：交给宿主持久化 */
function saveConfig(): void {
  saving.value = true
  emit('save', JSON.parse(JSON.stringify(local)))
  window.setTimeout(() => {
    saving.value = false
  }, 600)
}

// ─── 运行异常（与面板一致：先展示，5 秒后自动收起为小标签） ──

const runtimeErrors = ref<string[]>([])

/** 读取刷新快照里的演员解析异常；失败不影响配置页编辑 */
async function loadRuntimeErrors(): Promise<void> {
  const api = resolveApi(props)
  if (!api) return
  try {
    const raw = await api.get(`${API_BASE}/works`)
    const res = unwrap<ApiResult<WorksPayload>>(raw)
    runtimeErrors.value = res?.success ? res.data?.errors || [] : []
  } catch (err) {
    console.warn(`[${PLUGIN_ID}] 读取运行异常失败`, err)
  }
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
  void loadRuntimeErrors()
})
</script>

<style scoped>
/* 仅使用 scoped 样式；不要编写会全局生效的选择器（组件库类名、html、body、:root） */
.das-dim {
  opacity: 0.75;
}

/* 固定高度 + 内部滚动：演员再多也不会把配置页撑长 */
.das-actor-textarea {
  max-height: 220px;
}

/* 快捷添加栏：窄屏时输入框占满一行，按钮换行跟随 */
.das-actor-input {
  flex: 1 1 260px;
  min-width: 220px;
}
</style>
