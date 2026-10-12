<template>
  <div v-if="errors.length" class="das-errors">
    <template v-if="visible">
      <v-alert
        v-for="(item, index) in errors"
        :key="`${index}-${item}`"
        type="warning"
        variant="tonal"
        density="compact"
        class="mb-2"
      >
        {{ item }}
      </v-alert>
    </template>
    <v-chip
      v-else
      size="small"
      variant="tonal"
      color="warning"
      prepend-icon="mdi-alert-outline"
      @click="show"
    >
      {{ errors.length }} 项异常（点击查看）
    </v-chip>
  </div>
</template>

<script setup lang="ts">
/**
 * 异常提示条：出现后自动隐藏，避免长列表被提示刷屏。
 *
 * 不直接销毁信息——收起后留一个「N 项异常」的小标签，点一下可以再看一遍。
 * 每次内容变化都会重新计时，因此新一轮刷新产生的异常也一定会被看到。
 */
import { onBeforeUnmount, ref, watch } from 'vue'

const props = withDefaults(
  defineProps<{
    errors?: string[]
    /** 自动隐藏前的展示时长（毫秒），<=0 表示常驻 */
    duration?: number
  }>(),
  { errors: () => [], duration: 5000 }
)

const visible = ref(true)
let timer: number | undefined

function clearTimer(): void {
  if (timer !== undefined) {
    window.clearTimeout(timer)
    timer = undefined
  }
}

/** 展示提示并重新计时 */
function show(): void {
  clearTimer()
  visible.value = true
  if (props.duration > 0) {
    timer = window.setTimeout(() => {
      visible.value = false
    }, props.duration)
  }
}

watch(
  () => (props.errors || []).join('\n'),
  () => {
    if (!props.errors || !props.errors.length) {
      clearTimer()
      visible.value = true
      return
    }
    show()
  },
  { immediate: true }
)

onBeforeUnmount(clearTimer)
</script>

<style scoped>
.das-errors {
  margin-bottom: 8px;
}
</style>
