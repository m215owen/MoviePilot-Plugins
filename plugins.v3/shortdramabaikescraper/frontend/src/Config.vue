<template>
  <!--
    插件配置页（联邦暴露名 `./Config`）。

    Vue 渲染模式下**必须暴露这个组件**：宿主管理页点「配置」时找的就是它，
    没有就是「配置页打不开」（官方 `Plugin_Development.md` §8.2 的推荐 exposes
    里也明确列了 `./Page` 与 `./Config`）。

    读写的字段与后端 `get_form()` 完全同源（`enabled`），
    保存走 `PUT /config`（整体替换语义）。
  -->
  <div class="sdbs-root pa-2">
    <v-card variant="outlined" class="pa-4">
      <div class="d-flex align-center mb-2">
        <v-icon icon="mdi-cog-outline" class="mr-2" />
        <h3 class="ma-0 text-subtitle-1">短剧百科刮削源 · 设置</h3>
        <v-spacer />
        <v-btn icon="mdi-close" variant="text" size="small" title="关闭" @click="emit('close')" />
      </div>

      <div class="text-caption text-medium-emphasis mb-4">
        把「短剧百科」(www.duanjubaike.net) 注册为媒体来源
        <span class="sdbs-key">djbaike</span>：按片名检索 → 识别 → 订阅 / 刮削。
      </div>

      <v-alert v-if="error" type="error" variant="tonal" density="compact" class="mb-3">
        {{ error }}
      </v-alert>

      <div class="text-subtitle-2 font-weight-bold">运行</div>
      <v-divider class="mt-1 mb-3" />
      <v-switch
        v-model="local.enabled"
        label="启用插件"
        color="primary"
        density="compact"
        hide-details
        :loading="loading"
      />

      <div class="d-flex align-center mt-5" style="gap: 8px">
        <span v-if="saved" class="text-caption sdbs-dim">已保存</span>
        <v-spacer />
        <v-btn variant="text" :disabled="saving" @click="emit('close')">取消</v-btn>
        <v-btn color="primary" variant="flat" :loading="saving" :disabled="loading" @click="save()">
          保存
        </v-btn>
      </div>
    </v-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { fetchConfig, saveConfig } from './api'
import type { PluginApi, PluginConfig } from './types'

const props = defineProps<{
  /** 宿主注入的 axios 实例（实例作用域，适配虚拟分身） */
  api?: PluginApi
}>()

const emit = defineEmits<{
  /** 关闭配置弹窗（宿主监听后自己收面板） */
  (e: 'close'): void
  /** 保存成功（宿主可据此刷新状态） */
  (e: 'saved'): void
}>()

const local = ref<PluginConfig>({ enabled: false })
const loading = ref(false)
const saving = ref(false)
const saved = ref(false)
const error = ref('')

async function load(): Promise<void> {
  loading.value = true
  error.value = ''
  try {
    const config = await fetchConfig(props)
    local.value = {
      enabled: Boolean(config?.enabled),
    }
  } catch (err) {
    error.value = `读取配置失败：${err instanceof Error ? err.message : String(err)}`
  } finally {
    loading.value = false
  }
}

async function save(): Promise<void> {
  saving.value = true
  error.value = ''
  saved.value = false
  try {
    // 整体替换：后端缺失键会取默认值，所以这里发完整对象
    const result = await saveConfig(props, {
      enabled: Boolean(local.value.enabled),
    })
    local.value = {
      enabled: Boolean(result?.enabled),
    }
    saved.value = true
    emit('saved')
  } catch (err) {
    error.value = `保存失败：${err instanceof Error ? err.message : String(err)}`
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  void load()
})
</script>
