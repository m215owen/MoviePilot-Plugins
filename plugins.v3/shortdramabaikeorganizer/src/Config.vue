<template>
  <v-card class="sdbo-config" variant="flat">
    <v-alert
      v-if="errorText"
      type="error"
      variant="tonal"
      density="compact"
      class="ma-3 mb-0"
    >{{ errorText }}</v-alert>

    <v-card-title class="text-body-1 pb-1">
      短剧百科整理 · 配置
      <span class="text-caption text-medium-emphasis">（前端 build a9）</span>
    </v-card-title>

    <v-card-text>
      <v-row dense>
        <v-col cols="12" md="3">
          <v-switch v-model="conf.enabled" label="启用插件" color="primary" density="compact" hide-details></v-switch>
        </v-col>
        <v-col cols="12" md="3">
          <v-switch v-model="conf.notify" label="发送通知" color="primary" density="compact" hide-details></v-switch>
        </v-col>
        <v-col cols="12" md="3">
          <v-switch v-model="conf.scrape_enabled" label="自动刮削" color="primary" density="compact" hide-details></v-switch>
        </v-col>
        <v-col cols="12" md="3">
          <v-switch v-model="conf.force_transfer" label="强制整理历史" color="primary" density="compact" hide-details></v-switch>
        </v-col>
        <v-col cols="12" md="3">
          <v-switch v-model="conf.monitor_enabled" label="目录监控" color="primary" density="compact" hide-details></v-switch>
        </v-col>
      </v-row>

      <!-- 扫描目录 -->
      <div class="text-caption text-medium-emphasis mt-3">扫描目录（待整理短剧的上一层根目录，可多选）</div>
      <div class="sdbo-dir-line">
        <v-select
          v-model="conf.source_dirs"
          :items="sourceItems"
          multiple
          chips
          density="compact"
          hide-details
          class="sdbo-grow"
        ></v-select>
        <v-btn variant="tonal" color="primary" prepend-icon="mdi-folder-search" @click="openBrowse('source')">浏览目录</v-btn>
      </div>

      <!-- 手动补一个路径（系统配置里没有的目录）：紧跟扫描目录行下方 -->
      <div class="sdbo-dir-line mt-2">
        <v-text-field
          v-model="manualPath"
          density="compact"
          variant="outlined"
          hide-details
          placeholder="系统配置里没有的目录？粘贴绝对路径后点右侧按钮加入"
          class="sdbo-grow"
          @keyup.enter="addManual"
        ></v-text-field>
        <v-btn variant="text" @click="addManual">加入扫描目录</v-btn>
      </div>

      <!-- 目标库目录 -->
      <div class="text-caption text-medium-emphasis mt-3">目标库目录（短剧媒体库根）</div>
      <div class="sdbo-dir-line">
        <v-select
          v-model="conf.library_dir"
          :items="libraryItems"
          density="compact"
          hide-details
          clearable
          class="sdbo-grow"
        ></v-select>
        <v-btn variant="tonal" color="primary" prepend-icon="mdi-folder-search" @click="openBrowse('library')">浏览目录</v-btn>
      </div>

      <v-row dense class="mt-3">
        <v-col cols="12" md="4">
          <v-text-field v-model.number="conf.scan_depth" type="number" min="1" label="扫描深度" density="compact" hide-details></v-text-field>
        </v-col>
        <v-col cols="12" md="4">
          <v-select v-model="conf.transfer_type" :items="transferItems" label="搬运方式" density="compact" hide-details></v-select>
        </v-col>
        <v-col cols="12" md="4">
          <v-text-field v-model.number="conf.episode_width" type="number" min="1" max="4" label="集号补零位数" density="compact" hide-details></v-text-field>
        </v-col>
        <v-col cols="12" md="4">
          <v-select v-model="conf.monitor_mode" :items="monitorModeItems" label="监控模式" density="compact" hide-details></v-select>
        </v-col>
        <v-col cols="12" md="4">
          <v-text-field v-model.number="conf.monitor_interval" type="number" min="10" label="轮询间隔(秒)（仅轮询模式）" density="compact" hide-details></v-text-field>
        </v-col>
        <v-col cols="12" md="4">
          <v-switch v-model="conf.auto_rename_episode" label="集号缺失自动补齐" color="primary" density="compact" hide-details></v-switch>
        </v-col>
        <v-col cols="12" md="4">
          <v-switch v-model="conf.force_reorganize" label="强制重整理" color="warning" density="compact" hide-details></v-switch>
        </v-col>
      </v-row>
    </v-card-text>

    <v-card-actions>
      <span class="text-caption text-medium-emphasis">识别源 djbaike ｜ 插件自包含搬运 ｜ 历史写系统整理历史</span>
      <v-spacer></v-spacer>
      <v-btn variant="text" @click="closeDialog">取消</v-btn>
      <v-btn color="primary" variant="flat" prepend-icon="mdi-content-save" :loading="saving" @click="saveConfig">保存</v-btn>
    </v-card-actions>

    <!-- 浏览目录弹窗 -->
    <v-dialog v-model="browseOpen" max-width="680" scrollable>
      <v-card>
        <v-card-title class="text-body-2">
          浏览目录 · {{ browseTarget === 'library' ? '目标库目录' : '扫描目录' }}
        </v-card-title>
        <v-card-text style="min-height: 300px">
          <div class="sdbo-dir-line">
            <v-btn variant="text" size="small" prepend-icon="mdi-arrow-up" :disabled="!parentPath || browseLoading" @click="goPath(parentPath)">上级</v-btn>
            <v-text-field
              v-model="pathInput"
              density="compact"
              variant="outlined"
              hide-details
              placeholder="输入绝对路径后回车"
              class="sdbo-grow"
              @keyup.enter="goPath(pathInput)"
            ></v-text-field>
            <v-btn variant="text" size="small" :disabled="browseLoading" @click="goPath(pathInput)">前往</v-btn>
          </div>

          <v-progress-linear v-if="browseLoading" indeterminate color="primary" class="mt-2"></v-progress-linear>
          <v-alert v-if="browseMessage" type="info" variant="tonal" density="compact" class="mt-2">{{ browseMessage }}</v-alert>

          <v-list v-if="browseEntries.length" density="compact" class="mt-2 sdbo-browse-list">
            <v-list-item
              v-for="entry in browseEntries"
              :key="entry.value"
              @click="goPath(entry.value)"
            >
              <template #prepend>
                <v-icon icon="mdi-folder" size="18" class="mr-2"></v-icon>
              </template>
              <v-list-item-title class="text-body-2">{{ entry.title }}</v-list-item-title>
            </v-list-item>
          </v-list>
          <div v-else-if="!browseLoading && !browseMessage" class="text-caption text-medium-emphasis mt-3">
            该目录下没有子目录，可直接选它，或输入更深的路径。
          </div>

          <div class="text-caption text-medium-emphasis mt-3">当前：{{ currentPath || '（未进入）' }}</div>
        </v-card-text>
        <v-card-actions>
          <v-btn variant="text" @click="browseOpen = false">取消</v-btn>
          <v-spacer></v-spacer>
          <v-btn color="primary" variant="flat" :disabled="!currentPath || browseLoading" @click="confirmBrowse">选定此目录</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-card>
</template>

<script setup lang="ts">
/**
 * 短剧百科整理 · 配置页（2026-10-22 重写，单文件自包含）。
 *
 * 只用最基础的 Vuetify 组件（v-card / v-row / v-col / v-select / v-text-field /
 * v-switch / v-btn / v-dialog / v-list / v-alert / v-progress-linear），不依赖任何
 * 自定义 CSS 或第三方组件；渲染期异常通过 onErrorCaptured 直接显示在页面上，
 * 避免「白屏且无线索」。
 */
import { onErrorCaptured, onMounted, reactive, ref, type Ref } from 'vue'

import {
  backend,
  hostApi,
  type DirOption,
  type OrganizerConfig,
  type HostApi,
} from './api'

const props = defineProps<{
  initialConfig?: Partial<OrganizerConfig>
  api?: HostApi
}>()

const emit = defineEmits(['save', 'close', 'switch'])

const DEFAULTS: OrganizerConfig = {
  enabled: false,
  source_dirs: [],
  library_dir: '',
  scan_depth: 1,
  transfer_type: 'softlink',
  episode_width: 2,
  auto_rename_episode: true,
  scrape_enabled: true,
  force_transfer: false,
  notify: true,
  monitor_enabled: false,
  monitor_mode: 'watch',
  monitor_interval: 60,
  force_reorganize: false,
}

const transferItems: DirOption[] = [
  { title: '移动（move）', value: 'move' },
  { title: '复制（copy）', value: 'copy' },
  { title: '硬链接（link）', value: 'link' },
  { title: '软链接（softlink）', value: 'softlink' },
]

const monitorModeItems: DirOption[] = [
  { title: '事件监听（推荐）', value: 'watch' },
  { title: '轮询（回退）', value: 'poll' },
]

/** 把任意历史形态（换行串 / 数组 / {title,value} 对象）归一成字符串数组 */
function toList(value: unknown): string[] {
  const raw: unknown[] =
    typeof value === 'string' ? value.split(/\r?\n/) : Array.isArray(value) ? value : []
  const result: string[] = []
  for (const item of raw) {
    const text =
      typeof item === 'string'
        ? item
        : item && typeof item === 'object'
          ? String((item as Record<string, unknown>).value ?? (item as Record<string, unknown>).title ?? '')
          : ''
    const trimmed = text.trim()
    if (trimmed && result.indexOf(trimmed) < 0) result.push(trimmed)
  }
  return result
}

/** 单值归一 */
function toOne(value: unknown): string {
  if (typeof value === 'string') return value.trim()
  if (value && typeof value === 'object') {
    const record = value as Record<string, unknown>
    return String(record.value ?? record.title ?? '').trim()
  }
  return ''
}

const incoming = props.initialConfig || {}
const conf = reactive<OrganizerConfig>({
  ...DEFAULTS,
  ...incoming,
  source_dirs: toList(incoming.source_dirs),
  library_dir: toOne(incoming.library_dir),
} as OrganizerConfig)

const errorText = ref('')
const saving = ref(false)
const manualPath = ref('')

const sourceItems = ref<DirOption[]>([])
const libraryItems = ref<DirOption[]>([])

const browseOpen = ref(false)
const browseTarget = ref<'source' | 'library'>('source')
const browseLoading = ref(false)
const browseMessage = ref('')
const browseEntries = ref<DirOption[]>([])
const currentPath = ref('')
const parentPath = ref('')
const pathInput = ref('')

onErrorCaptured((err) => {
  errorText.value = `渲染异常：${(err as Error)?.message || String(err)}`
  return false
})

function apiOrNull(): HostApi | null {
  return hostApi({ api: props.api })
}

async function loadDirOptions(): Promise<void> {
  const api = apiOrNull()
  if (!api) return
  try {
    const data = await backend.dirOptions(api)
    sourceItems.value = data?.sources || []
    libraryItems.value = data?.libraries || []
  } catch (err) {
    errorText.value = `读取系统目录失败：${(err as Error)?.message || String(err)}`
  }
}

function openBrowse(target: 'source' | 'library'): void {
  browseTarget.value = target
  browseOpen.value = true
  browseMessage.value = ''
  const start =
    target === 'library'
      ? toOne(conf.library_dir)
      : toList(conf.source_dirs)[0] || ''
  const fallback = (target === 'library' ? libraryItems.value[0] : sourceItems.value[0])?.value || '/'
  void goPath(start || fallback)
}

async function goPath(path: string): Promise<void> {
  const api = apiOrNull()
  if (!api) {
    browseMessage.value = '宿主 api 实例不可用，请刷新页面重试'
    return
  }
  browseLoading.value = true
  browseMessage.value = ''
  try {
    const data = await backend.browse(api, path || '')
    currentPath.value = data?.path || ''
    parentPath.value = data?.parent || ''
    pathInput.value = data?.path || ''
    browseEntries.value = data?.entries || []
  } catch (err) {
    browseMessage.value = `读取目录失败：${(err as Error)?.message || String(err)}`
  } finally {
    browseLoading.value = false
  }
}

function confirmBrowse(): void {
  if (!currentPath.value) return
  if (browseTarget.value === 'library') {
    conf.library_dir = currentPath.value
    ensureOption(libraryItems, currentPath.value)
  } else {
    const list = toList(conf.source_dirs)
    if (list.indexOf(currentPath.value) < 0) list.push(currentPath.value)
    conf.source_dirs = list
    ensureOption(sourceItems, currentPath.value)
  }
  browseOpen.value = false
}

function addManual(): void {
  const path = manualPath.value.trim()
  if (!path) return
  const list = toList(conf.source_dirs)
  if (list.indexOf(path) < 0) list.push(path)
  conf.source_dirs = list
  ensureOption(sourceItems, path)
  manualPath.value = ''
}

/** 浏览/手动加入的目录也要进下拉候选，否则选完下拉框里看不到它 */
function ensureOption(items: Ref<DirOption[]>, path: string): void {
  if (!path) return
  if (items.value.some((item) => item.value === path)) return
  items.value = [...items.value, { title: path, value: path }]
}

function saveConfig(): void {
  saving.value = true
  errorText.value = ''
  emit('save', {
    ...conf,
    source_dirs: toList(conf.source_dirs),
    library_dir: toOne(conf.library_dir),
  })
  window.setTimeout(() => {
    saving.value = false
  }, 400)
}

function closeDialog(): void {
  emit('close')
}

onMounted(() => {
  void loadDirOptions()
})
</script>

<style scoped>
.sdbo-dir-line {
  display: flex;
  align-items: flex-start;
  gap: 8px;
}

.sdbo-grow {
  flex: 1 1 auto;
  min-width: 0;
}

.sdbo-browse-list {
  max-height: 300px;
  overflow-y: auto;
  border: 1px solid rgba(0, 0, 0, 0.12);
  border-radius: 6px;
}
</style>
