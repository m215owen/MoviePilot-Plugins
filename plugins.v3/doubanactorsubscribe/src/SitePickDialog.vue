<template>
  <v-dialog
    :model-value="modelValue"
    max-width="520"
    scrollable
    @update:model-value="emit('update:modelValue', $event)"
  >
    <v-card>
      <v-card-title class="d-flex align-center">
        <v-icon icon="mdi-server-network" size="20" class="mr-2" />
        <span class="text-body-1">{{ title || '选择站点' }}</span>
        <v-spacer />
        <span class="text-caption text-medium-emphasis">
          已选择 {{ picked.length }}/{{ sites.length }} 个站点
        </span>
      </v-card-title>
      <v-divider />

      <v-card-text class="pb-2">
        <v-text-field
          v-model="filter"
          density="compact"
          variant="outlined"
          hide-details
          clearable
          prepend-inner-icon="mdi-magnify"
          placeholder="站点搜索"
          class="mb-2"
        />

        <div v-if="loading" class="text-caption text-medium-emphasis py-3 text-center">
          正在读取站点清单…
        </div>
        <div v-else-if="!sites.length" class="text-caption text-medium-emphasis py-3">
          宿主没有可用的站点，将按宿主默认搜索站点搜索。
        </div>
        <div v-else-if="!shown.length" class="text-caption text-medium-emphasis py-3">
          没有匹配「{{ filter }}」的站点。
        </div>
        <div v-else class="das-site-list">
          <v-checkbox
            v-for="site in shown"
            :key="site.id"
            :model-value="picked.includes(site.id)"
            :label="site.name"
            :title="site.domain || site.name"
            density="compact"
            hide-details
            class="das-site-item"
            @update:model-value="toggle(site.id, $event)"
          />
        </div>
        <div
          v-if="!loading && sites.length && !picked.length"
          class="text-caption text-medium-emphasis mt-2"
        >
          未选择任何站点时，按宿主的默认站点搜索全部。
        </div>
      </v-card-text>

      <v-divider />
      <v-card-actions>
        <v-btn size="small" variant="text" :disabled="!sites.length" @click="selectAll">
          选择全部
        </v-btn>
        <v-btn size="small" variant="text" :disabled="!picked.length" @click="picked = []">
          取消全选
        </v-btn>
        <v-spacer />
        <v-btn size="small" variant="text" @click="emit('update:modelValue', false)">取消</v-btn>
        <v-btn
          size="small"
          color="primary"
          variant="flat"
          :disabled="loading"
          @click="emit('confirm', [...picked])"
        >
          确认
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
/**
 * 「搜索资源」用的站点选择框。
 *
 * 宿主媒体详情页点「搜索资源」时会先弹出它自己的站点选择框，让用户挑这次要搜哪些站；
 * 宿主的弹窗组件是主程序内部件、联邦插件拿不到（只共享 vue/vuetify），
 * 因此这里**按同样的做法自己画一个**：站点清单与默认勾选值都取自宿主
 * （`site/media/{type}` + `system/setting/public/IndexerSites`），文案也保持一致，
 * 这样用户在插件里看到的站点、默认选中项与宿主那边完全一样。
 *
 * 只在打开时把外部传入的默认选中项拷进内部状态，之后由用户自己改；
 * 关闭不提交则丢弃，不污染下次的默认值。
 */
import { computed, ref, watch } from 'vue'
import type { SiteOption } from './types'

const props = withDefaults(
  defineProps<{
    /** 是否显示 */
    modelValue: boolean
    /** 可选站点（宿主按媒体类型裁剪后的启用站点） */
    sites: SiteOption[]
    /** 默认选中项（宿主的默认搜索站点设置） */
    selected?: number[]
    /** 站点清单是否仍在加载 */
    loading?: boolean
    /** 弹窗标题 */
    title?: string
  }>(),
  { selected: () => [], loading: false, title: '选择站点' }
)

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'confirm', ids: number[]): void
}>()

/** 用户当前的勾选结果 */
const picked = ref<number[]>([])
/** 站点名过滤词 */
const filter = ref('')

/** 过滤后的站点列表 */
const shown = computed(() => {
  const keyword = filter.value.trim().toLowerCase()
  if (!keyword) return props.sites
  return props.sites.filter((site) => {
    const name = String(site.name || '').toLowerCase()
    const domain = String(site.domain || '').toLowerCase()
    return name.includes(keyword) || domain.includes(keyword)
  })
})

// 每次打开都以外部传入的默认值为准，避免上次的临时改动残留
watch(
  () => props.modelValue,
  (visible) => {
    if (!visible) return
    filter.value = ''
    const available = new Set(props.sites.map((site) => site.id))
    picked.value = props.selected.filter((id) => available.has(id))
    // 站点清单加载完成后再回填一次默认值：打开弹窗时清单往往还没回来
    if (!props.sites.length) picked.value = [...props.selected]
  }
)

// 清单是异步回来的，回来后重新对齐默认勾选（仅保留仍然可用的站点）
watch(
  () => props.sites,
  (sites) => {
    if (!props.modelValue || !sites.length) return
    const available = new Set(sites.map((site) => site.id))
    picked.value = picked.value.filter((id) => available.has(id))
  }
)

/** 勾选 / 取消勾选一个站点 */
function toggle(id: number, value: boolean | null): void {
  const next = new Set(picked.value)
  if (value) next.add(id)
  else next.delete(id)
  picked.value = Array.from(next)
}

/** 全选（只针对清单里的站点，过滤词不影响全选语义） */
function selectAll(): void {
  picked.value = props.sites.map((site) => site.id)
}
</script>

<style scoped>
/* 站点多时弹窗内部滚动；不要编写全局生效的选择器 */
.das-site-list {
  max-height: 46vh;
  overflow-y: auto;
  padding-right: 4px;
}

.das-site-item {
  margin-bottom: -4px;
}
</style>
