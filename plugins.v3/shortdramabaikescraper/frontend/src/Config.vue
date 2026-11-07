<template>
  <!--
    插件配置页（联邦暴露名 `./Config`）。

    Vue 渲染模式下**必须暴露这个组件**：宿主管理页点「配置」时找的就是它，
    没有就是「配置页打不开」（官方 `Plugin_Development.md` §8.2 的推荐 exposes
    里也明确列了 `./Page` 与 `./Config`）。

    读写的字段与后端 `get_form()` 完全同源（`enabled` / `site` /
    `use_baidu_image_proxy` / `exclude_manju`），保存走 `PUT /config`。
    ⚠️ `site` 必须一起回传：后端虽然已改成「缺失键沿用当前值」，但少了它这次
    保存就不再表达用户的站点选择（历史 bug：配置页没有站点选项时，每次保存
    都把主站打回 net）。

    排版只用 Vuetify 标准组件与 utility class（v-switch + label + messages），
    **不要**自绘 flex 两栏：v-switch 的根节点会按容器宽度撑开，放进 flex 行里
    会把左侧文字挤压/换行。
  -->
  <div class="pa-2">
    <v-card variant="outlined" class="pa-4">
      <!-- 头部 -->
      <div class="d-flex align-center mb-2">
        <v-icon icon="mdi-cog-outline" size="20" class="mr-2 text-medium-emphasis" />
        <h3 class="ma-0 text-subtitle-1">短剧百科刮削源 · 设置</h3>
        <v-spacer />
        <v-btn icon="mdi-close" variant="text" size="small" title="关闭" @click="emit('close')" />
      </div>

      <div class="text-caption text-medium-emphasis mb-4">
        把「短剧百科」注册为媒体来源
        <span class="sdbs-key">djbaike</span>：按片名检索 → 识别 → 订阅 / 刮削。
      </div>

      <v-alert v-if="error" type="error" variant="tonal" density="compact" class="mb-3">
        {{ error }}
      </v-alert>

      <!-- 运行 -->
      <div class="text-subtitle-2 font-weight-bold">运行</div>
      <v-divider class="mt-1 mb-2" />
      <v-switch
        v-model="local.enabled"
        label="启用插件"
        color="primary"
        density="compact"
        hide-details
        class="mb-3"
        :loading="loading"
      />

      <!-- 数据源 -->
      <div class="text-subtitle-2 font-weight-bold">数据源</div>
      <v-divider class="mt-1 mb-2" />
      <v-select
        v-model="local.site"
        :items="siteItems"
        item-title="title"
        item-value="value"
        label="主站"
        density="compact"
        :messages="[
          '只决定检索 / 人物目录 / 榜单走哪个站；详情与图片按身份前缀自动路由',
          'drama: / actor: 恒走新站，duanju: 等恒走老站 —— 换站不会废掉已入库的旧身份',
        ]"
        :loading="loading"
        class="mb-3"
      />

      <!-- 图片 -->
      <div class="text-subtitle-2 font-weight-bold">图片</div>
      <v-divider class="mt-1 mb-2" />
      <v-switch
        v-model="local.use_baidu_image_proxy"
        label="保留使用百度图床代理（仅老站生效）"
        color="primary"
        density="compact"
        :disabled="local.site === 'org'"
        :messages="imageMessages"
        :loading="loading"
      />

      <!-- 内容 -->
      <div class="text-subtitle-2 font-weight-bold mt-2">内容</div>
      <v-divider class="mt-1 mb-2" />
      <v-switch
        v-model="local.exclude_manju"
        :label="excludeLabel"
        color="primary"
        density="compact"
        :messages="excludeMessages"
        :loading="loading"
      />

      <v-divider class="my-3" />

      <!-- 底部操作 -->
      <div class="d-flex align-center">
        <span v-if="saved" class="text-caption text-medium-emphasis">已保存</span>
        <v-spacer />
        <v-btn variant="text" :disabled="saving" @click="emit('close')">取消</v-btn>
        <v-btn
          color="primary"
          variant="flat"
          class="ml-2"
          :loading="saving"
          :disabled="loading"
          @click="save()"
        >
          保存
        </v-btn>
      </div>
    </v-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { fetchConfig, saveConfig } from './api'
import { SITE_INFO, setSite } from './site'
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

const local = ref<PluginConfig>({
  enabled: false,
  site: 'net',
  use_baidu_image_proxy: true,
  exclude_manju: true,
})
const loading = ref(false)
const saving = ref(false)
const saved = ref(false)
const error = ref('')

/** 主站候选（与后端 `constants.SITE_NET` / `SITE_ORG` 同值，文案取同一份 `SITE_INFO`）。 */
const siteItems = [SITE_INFO.net, SITE_INFO.org].map((info) => ({
  title: info.label,
  value: info.key,
}))

/** 「排除」开关在两个站的语义不同，文案跟着主站走，别让人以为切站后判据还是一样。 */
const excludeLabel = computed(() =>
  local.value.site === 'org' ? '排除 AI 剧' : '排除漫剧',
)
const excludeMessages = computed(() =>
  local.value.site === 'org'
    ? [
        '新站没有漫剧角标，打开后按卡片标题的「AI短剧」标剔除 AI 剧',
        '识别候选 / 面板检索 / 榜单 / 演员作品都生效',
      ]
    : [
        '打开：识别候选 / 面板检索 / 榜单都不再出现漫剧',
        '判定只看 kind 这一项 —— kind 为「漫剧」即排除',
      ],
)

/** 百度图床代理只对老站有意义：新站海报是页面自带的 CDN 绝对地址。 */
const imageMessages = computed(() =>
  local.value.site === 'org'
    ? [
        '当前是新站：海报直接用页面自带的 cdn.duanjubaike.org 绝对地址',
        '本开关对新站不生效（切换回老站后才会用上）',
      ]
    : [
        '打开：海报 / 头像走站点原始的百度 gimg 中转（gimg0.baidu.com）',
        '关闭：直连站点自家图床 img.duanjubaike.net',
      ],
)

function normalize(config?: Partial<PluginConfig> | null): PluginConfig {
  return {
    enabled: Boolean(config?.enabled),
    // 站点只有 net / org 两个合法值，其它（含 undefined）一律回落 net
    site: config?.site === 'org' ? 'org' : 'net',
    // 后端默认 True；只有显式 false 才关掉（老配置里没有这个键时保持默认）
    use_baidu_image_proxy: config?.use_baidu_image_proxy !== false,
    exclude_manju: config?.exclude_manju !== false,
  }
}

async function load(): Promise<void> {
  loading.value = true
  error.value = ''
  try {
    local.value = normalize(await fetchConfig(props))
    // 打开配置页就把主站同步到全局：切换保存后，面板顶栏 / 概览 / 查询示例立即跟着变
    setSite(local.value.site)
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
    // 整体替换：后端缺失键会沿用当前值，这里仍发完整对象，表达用户的全部选择
    local.value = normalize(await saveConfig(props, normalize(local.value)))
    // 以后端返回的值为准（它才是真正生效的那份），并同步全局主站
    setSite(local.value.site)
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

<style scoped>
.sdbs-key {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
}
</style>
