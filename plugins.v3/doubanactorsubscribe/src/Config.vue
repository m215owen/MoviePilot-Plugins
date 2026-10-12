<template>
  <div class="das-root pa-2">
    <v-card variant="outlined" class="pa-4">
      <div class="d-flex align-center mb-3">
        <v-icon icon="mdi-cog-outline" class="mr-2" />
        <h3 class="ma-0">豆瓣演员订阅 · 设置</h3>
        <v-spacer />
        <v-btn icon="mdi-close" variant="text" size="small" title="关闭" @click="emit('close')" />
      </div>

      <v-row dense>
        <v-col cols="12" sm="4">
          <v-switch v-model="local.enabled" label="启用插件" color="primary" hide-details />
        </v-col>
        <v-col cols="12" sm="4">
          <v-switch v-model="local.proxy" label="使用代理服务器" color="primary" hide-details />
        </v-col>
        <v-col cols="12" sm="4">
          <v-switch
            v-model="local.onlyonce"
            label="保存后立即刷新一次"
            color="primary"
            hide-details
          />
        </v-col>
      </v-row>

      <v-divider class="my-3" />

      <!-- 演员配置 -->
      <div class="text-subtitle-2 mb-2">
        <v-icon icon="mdi-account-multiple-outline" size="18" class="mr-1" />
        订阅的演员
      </div>
      <v-textarea
        v-model="local.actors"
        label="演员列表"
        placeholder="每行一个：演员名 或 豆瓣人物 ID&#10;例如：&#10;刘德华&#10;1054421"
        hint="按名称填写的会在刷新时自动搜索解析为豆瓣人物；直接填人物 ID 更精确"
        persistent-hint
        rows="4"
        density="comfortable"
        auto-grow
        class="mb-3"
      />

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
        <div v-if="!candidates.length" class="text-caption das-dim">
          未搜索到匹配的演员，换一个名字或直接填写人物 ID。
        </div>
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
          <v-spacer />
          <v-btn size="x-small" variant="text" color="primary" @click="appendActor(item.id)">
            添加 ID
          </v-btn>
        </div>
      </v-card>

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
import { API_BASE, PLUGIN_ID, resolveApi, unwrap } from './api'
import type { ActorCandidate, ApiResult, PluginApi, PluginConfig } from './types'

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
}

const local = reactive<PluginConfig>({ ...defaults })

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

// ─── 演员搜索辅助 ─────────────────────────────────────────────

const searchName = ref('')
const searching = ref(false)
const searched = ref(false)
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
  } catch (err) {
    candidates.value = []
    searched.value = true
    console.warn(`[${PLUGIN_ID}] 搜索演员失败`, err)
  } finally {
    searching.value = false
  }
}

/** 把搜索结果的人物 ID 追加到演员列表 */
function appendActor(id: string): void {
  const lines = String(local.actors || '')
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter(Boolean)
  if (!lines.includes(id)) lines.push(id)
  local.actors = lines.join('\n')
}

/** 提交保存：交给宿主持久化 */
function saveConfig(): void {
  saving.value = true
  emit('save', JSON.parse(JSON.stringify(local)))
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
})
</script>

<style scoped>
/* 仅使用 scoped 样式；不要编写会全局生效的选择器（组件库类名、html、body、:root） */
.das-dim {
  opacity: 0.75;
}
</style>
