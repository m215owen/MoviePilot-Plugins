<template>
  <div class="das-root pa-4">
    <div class="d-flex align-center mb-3 flex-wrap" style="gap: 12px">
      <v-icon icon="mdi-chart-timeline-variant" class="mr-1" />
      <h2 class="text-h6 ma-0">豆瓣演员订阅 · 运行状态</h2>
      <v-chip size="small" variant="tonal">{{ pluginId || 'DoubanActorSubscribe' }} / {{ navKey || 'settings' }}</v-chip>
      <v-spacer />
      <v-btn size="small" variant="tonal" color="primary" icon="mdi-refresh" :loading="loading" @click="load" />
    </div>

    <!-- 统计 -->
    <v-row dense class="mb-3">
      <v-col v-for="item in statCards" :key="item.label" cols="6" md="3">
        <v-card variant="tonal" class="pa-3">
          <div class="text-caption">{{ item.label }}</div>
          <div class="text-h6">{{ item.value }}</div>
        </v-card>
      </v-col>
    </v-row>

    <v-alert
      v-for="(err, index) in payload?.errors || []"
      :key="index"
      type="error"
      variant="tonal"
      density="compact"
      class="mb-2"
    >
      {{ err }}
    </v-alert>

    <!-- 订阅选项：下载保存路径 + 订阅站点（组件内自行 PUT /config 持久化） -->
    <SubscribePrefs class="mb-3" :api="props.api" @saved="onPrefsSaved" />

    <v-row>
      <!-- 快速配置 -->
      <v-col cols="12" lg="5">
        <v-card variant="outlined" class="pa-4">
          <div class="text-subtitle-2 mb-3">
            <v-icon icon="mdi-flash-outline" size="18" class="mr-1" />
            快速配置
          </div>
          <v-alert type="info" variant="tonal" density="compact" class="mb-3">
            本页通过 <code>PUT {{ API_BASE }}/config</code> 只提交下面三个字段，
            其余配置（自动订阅、评分阈值等）保持原样，完整设置请在插件配置弹窗中调整。
          </v-alert>

          <v-switch v-model="local.enabled" label="启用插件" color="primary" hide-details class="mb-2" />
          <v-textarea
            v-model="local.actors"
            label="订阅的演员"
            placeholder="支持逗号/顿号/分号分隔，也可每行一个：&#10;刘德华, 吴京, 张译&#10;或直接粘贴人物主页链接：&#10;https://www.douban.com/personage/37871253/"
            hint="演员名或豆瓣人物 ID/主页链接均可。填 ID 或链接可跳过搜索——豆瓣匿名搜索有严格限流，演员多时按名称搜索会失败。"
            persistent-hint
            rows="4"
            auto-grow
            density="comfortable"
            class="mb-2"
          />
          <v-text-field
            v-model="local.cron"
            label="刷新周期（cron）"
            hint="5 段式，例如 0 8 * * *"
            persistent-hint
            density="comfortable"
            class="mb-3"
          />

          <div class="d-flex flex-wrap" style="gap: 8px">
            <v-btn color="primary" :loading="saving" @click="save">保存并刷新</v-btn>
            <v-btn variant="tonal" :loading="refreshing" @click="runNow">立即刷新作品</v-btn>
            <v-btn variant="text" @click="load">放弃修改</v-btn>
            <v-spacer />
            <v-btn variant="text" color="error" prepend-icon="mdi-delete-outline" @click="confirmClear = true">
              清空记录
            </v-btn>
          </div>
        </v-card>
      </v-col>

      <!-- 自动订阅历史 -->
      <v-col cols="12" lg="7">
        <v-card variant="outlined">
          <v-card-title class="d-flex align-center">
            自动订阅历史
            <v-spacer />
            <span class="text-caption das-dim">
              共 {{ (payload?.auto_subscribed || []).length }} 条
            </span>
          </v-card-title>
          <v-card-text>
            <div v-if="!payload?.auto_subscribed?.length" class="text-medium-emphasis text-body-2">
              暂无自动订阅记录。开启自动订阅后，插件会把新发现且满足条件的作品提交到订阅系统。
            </div>
            <v-table v-else density="compact">
              <thead>
                <tr>
                  <th>时间</th>
                  <th>演员</th>
                  <th>作品</th>
                  <th>结果</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(row, index) in payload.auto_subscribed" :key="index">
                  <td class="text-caption">{{ row.time }}</td>
                  <td class="text-caption">{{ row.actor || '—' }}</td>
                  <td>
                    <a :href="`https://movie.douban.com/subject/${row.media_id}/`" target="_blank">
                      {{ row.title }}
                    </a>
                    <span class="text-caption das-dim ml-1">{{ row.year || '' }}</span>
                  </td>
                  <td>
                    <v-icon
                      :icon="row.success ? 'mdi-check-circle' : 'mdi-alert-circle'"
                      :color="row.success ? 'success' : 'error'"
                      size="16"
                    />
                    <span class="text-caption ml-1">{{ row.detail }}</span>
                  </td>
                </tr>
              </tbody>
            </v-table>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- 清空确认 -->
    <v-dialog v-model="confirmClear" max-width="420">
      <v-card>
        <v-card-title>确认清空？</v-card-title>
        <v-card-text>
          将清空已抓取的作品快照与自动订阅记录。已提交到订阅系统的订阅不会被删除。
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="confirmClear = false">取消</v-btn>
          <v-btn color="error" :loading="clearing" @click="clearRecords">确认清空</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </div>
</template>

<script setup lang="ts">
/**
 * 侧栏全页 · 运行状态入口（联邦暴露名 ./AppPageSettings，对应 nav_key = settings）。
 *
 * 主程序按 nav_key 的 PascalCase 优先解析暴露名，因此 `settings` → `./AppPageSettings`。
 * 与 Config.vue 不同，这里在组件内直接调用插件 API（PUT /config、POST /run、POST /clear），
 * 并通过宿主注入的 Toast 反馈结果。
 */
import { computed, inject, onMounted, reactive, ref } from 'vue'
import SubscribePrefs from './SubscribePrefs.vue'
import { API_BASE, PLUGIN_ID, formatTime, normalizeResult, resolveApi, waitForRefresh } from './api'
import type { PluginApi, PluginConfig, WorksPayload } from './types'

interface HostToast {
  success(message: string): unknown
  info(message: string): unknown
  warning(message: string): unknown
  error(message: string): unknown
}

const props = defineProps<{
  api?: PluginApi
  nativeSubscribe?: (mediaInfo: Record<string, unknown>) => Promise<unknown>
  navKey?: string
  pluginId?: string
}>()

const toast = inject<HostToast | null>('moviepilot:toast', null)

const loading = ref(false)
const saving = ref(false)
const refreshing = ref(false)
const clearing = ref(false)
const confirmClear = ref(false)
const payload = ref<WorksPayload | null>(null)

/** 本页只编辑这三个字段，其余配置保持不变 */
const local = reactive({ enabled: false, actors: '', cron: '' })

const statCards = computed(() => [
  { label: '演员', value: payload.value?.actor_count ?? 0 },
  { label: '作品', value: payload.value?.work_count ?? 0 },
  { label: '新作品', value: payload.value?.new_count ?? 0 },
  { label: '上次刷新', value: formatTime(payload.value?.updated_at) },
])

function notify(type: 'success' | 'error', message: string): void {
  const handler = toast && (toast as unknown as Record<string, unknown>)[type]
  if (typeof handler === 'function') {
    ;(handler as (msg: string) => unknown).call(toast, message)
    return
  }
  console.warn(`[${PLUGIN_ID}] ${message}`)
}

/** 订阅选项「保存为默认」的回调 */
function onPrefsSaved(ok: boolean, message: string): void {
  notify(ok ? 'success' : 'error', message)
}

async function load(): Promise<void> {
  const api = resolveApi(props)
  if (!api) {
    notify('error', '宿主 API 未就绪')
    return
  }
  loading.value = true
  try {
    const [cfgRaw, worksRaw] = await Promise.all([
      api.get(`${API_BASE}/config`),
      api.get(`${API_BASE}/works`),
    ])
    const cfg = normalizeResult<PluginConfig>(cfgRaw)
    if (cfg.ok && cfg.data) {
      local.enabled = Boolean(cfg.data.enabled)
      local.actors = String(cfg.data.actors || '')
      local.cron = String(cfg.data.cron || '')
    }
    const works = normalizeResult<WorksPayload>(worksRaw)
    if (works.ok && works.data) payload.value = works.data
  } catch (err) {
    notify('error', '读取状态失败')
    console.warn(`[${PLUGIN_ID}] 读取状态失败`, err)
  } finally {
    loading.value = false
  }
}

/** 提交这三个字段，其余配置由后端合并保留 */
async function save(): Promise<void> {
  const api = resolveApi(props)
  if (!api) {
    notify('error', '宿主 API 未就绪')
    return
  }
  saving.value = true
  try {
    const raw = await api.put(`${API_BASE}/config`, {
      enabled: local.enabled,
      actors: local.actors,
      cron: local.cron,
    })
    const res = normalizeResult<PluginConfig>(raw)
    if (res.ok) {
      notify('success', '配置已保存')
      await runNow()
    } else {
      notify('error', res.message || '保存失败')
    }
  } catch (err) {
    notify('error', '保存失败')
    console.warn(`[${PLUGIN_ID}] 保存配置失败`, err)
  } finally {
    saving.value = false
  }
}

/** 立即刷新一次作品（后台执行，轮询等待结果） */
async function runNow(): Promise<void> {
  const api = resolveApi(props)
  if (!api) return
  refreshing.value = true
  try {
    const raw = await api.post(`${API_BASE}/run`)
    const res = normalizeResult<WorksPayload>(raw)
    if (res.data) payload.value = res.data
    if (res.ok) notify('success', res.message || '已开始刷新演员最新作品')
    else notify('error', res.message || '刷新失败')
    if (payload.value?.refreshing || payload.value?.pending_refresh) {
      waitForRefresh(api, (data) => {
        payload.value = data
      })
    }
  } catch (err) {
    notify('error', '刷新失败')
    console.warn(`[${PLUGIN_ID}] 刷新失败`, err)
  } finally {
    refreshing.value = false
  }
}

/** 清空作品快照与自动订阅记录 */
async function clearRecords(): Promise<void> {
  const api = resolveApi(props)
  if (!api) return
  clearing.value = true
  try {
    const raw = await api.post(`${API_BASE}/clear`)
    const res = normalizeResult<unknown>(raw)
    if (res.ok) {
      notify('success', res.message || '已清空记录')
      confirmClear.value = false
      await load()
    } else {
      notify('error', res.message || '清空失败')
    }
  } catch (err) {
    notify('error', '清空失败')
    console.warn(`[${PLUGIN_ID}] 清空失败`, err)
  } finally {
    clearing.value = false
  }
}

onMounted(load)
</script>

<style scoped>
/* 仅使用 scoped 样式 */
.das-root {
  max-width: 1600px;
}

.das-dim {
  opacity: 0.75;
}
</style>
