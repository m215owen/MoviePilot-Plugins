<template>
  <!--
    主界面侧栏全页（联邦暴露名 ./AppPage，nav_key = main）。

    宿主会在侧栏「订阅」分组里挂一个「短剧演员」入口，点开即加载本组件。
    界面本体与插件详情页共用 ActorWall，这里只负责把宿主注入的
    `native-subscribe`（系统订阅入口）透传下去，并开启整页留白。
  -->
  <ActorWall
    :api="props.api"
    :config="props.config"
    :plugin-id="props.pluginId"
    :native-subscribe="props.nativeSubscribe"
    full
  />
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
  /** 宿主注入的原生订阅入口（kebab: native-subscribe） */
  nativeSubscribe?: NativeSubscribe
}>()
</script>
