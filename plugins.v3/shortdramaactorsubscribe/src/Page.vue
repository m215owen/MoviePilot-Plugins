<template>
  <!--
    插件详情页（联邦暴露名 ./Page）：在插件管理里点开卡片时渲染。

    与侧栏全页共用 ActorWall —— 同一面作品墙、同一套订阅入口，只是不留整页边距。
    插件详情页拿不到宿主注入的 native-subscribe，那种场景下的「订阅」会提示用户
    改从「详情」页（系统媒体详情页）订阅。
  -->
  <div :class="props.full ? 'pa-4' : 'pa-2'">
    <ActorWall
      :api="props.api"
      :config="props.config"
      :plugin-id="props.pluginId"
      :native-subscribe="props.nativeSubscribe"
    />
  </div>
</template>

<script setup lang="ts">
import ActorWall from './ActorWall.vue'
import type { NativeSubscribe, PluginApi, PluginConfig } from './types'

const props = defineProps<{
  /** 宿主注入的 axios 实例 */
  api?: PluginApi
  /** 插件配置 */
  config?: Partial<PluginConfig>
  /** 当前插件实例 ID */
  pluginId?: string
  /** 宿主注入的原生订阅入口（全页场景才有） */
  nativeSubscribe?: NativeSubscribe
  /** 整页留白 */
  full?: boolean
}>()
</script>
