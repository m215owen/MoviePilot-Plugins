<template>
  <div class="sdas-root sdas-dash">
    <v-card variant="flat" class="sdas-dash-card">
      <div class="d-flex align-center pa-3 pb-1">
        <v-icon icon="mdi-movie-open-star-outline" size="20" class="mr-2" />
        <span class="text-body-1">短剧演员</span>
        <v-spacer />
        <v-btn
          icon="mdi-refresh"
          variant="text"
          size="x-small"
          :loading="loading"
          title="刷新"
          @click="load"
        />
      </div>

      <div class="px-3 pb-3">
        <div v-if="error" class="text-medium-emphasis text-body-2">{{ error }}</div>
        <template v-else>
          <div class="d-flex align-center flex-wrap mb-2" style="gap: 12px">
            <span class="text-caption">演员 <b>{{ status.actors || 0 }}</b></span>
            <span class="text-caption">作品 <b>{{ status.works || 0 }}</b></span>
            <span class="text-caption">新作品 <b>{{ status.new_works || 0 }}</b></span>
          </div>
          <div v-if="status.last_refresh" class="text-caption sdas-dim">
            上次刷新：{{ status.last_refresh }}
          </div>
          <div v-else class="text-caption sdas-dim">还没刷新过，去作品墙点「刷新」</div>
        </template>
      </div>
    </v-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { fetchStatus } from './api'
import type { PluginApi, StatusPayload } from './types'

const props = defineProps<{
  /** 宿主注入的 axios 实例 */
  api?: PluginApi
}>()

const status = ref<Partial<StatusPayload>>({})
const loading = ref(false)
const error = ref('')

async function load(): Promise<void> {
  loading.value = true
  error.value = ''
  try {
    status.value = await fetchStatus(props)
  } catch (err) {
    error.value = `加载失败：${err instanceof Error ? err.message : err}`
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.sdas-dash-card {
  background: transparent;
}

.sdas-dim {
  opacity: 0.7;
}
</style>
