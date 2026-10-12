/**
 * 插件开发模板 —— 前端调用宿主的公共工具。
 *
 * 重要约定：
 * 1. 优先使用宿主传入的 `api` prop（实例作用域，适配插件虚拟分身）；
 *    仅在 prop 缺失时才回退全局 `window.MoviePilotAPI`。
 * 2. 宿主 axios 的 baseURL 已是 `api/v1/`，因此插件内路径写
 *    `plugin/<PluginID>/<path>`，绝不能写成 `api/v1/plugin/...`（会变成双前缀 404）。
 * 3. 主框架 axios 拦截器通常已解包响应，但个别版本仍会套一层 axios response，
 *    统一用 `unwrap()` 归一化。
 */
import type { PluginApi } from './types'

/** 插件 ID，必须与后端插件类名一致 */
export const PLUGIN_ID = 'PluginTemplate'

/** 插件接口路径前缀（相对 baseURL `api/v1/`） */
export const API_BASE = `plugin/${PLUGIN_ID}`

/** 解析可用的 HTTP 客户端：优先 api prop，其次全局注入 */
export function resolveApi(props: { api?: PluginApi }): PluginApi | null {
  if (props && props.api) return props.api
  const globalApi =
    typeof window !== 'undefined' ? (window as unknown as { MoviePilotAPI?: PluginApi }).MoviePilotAPI : null
  return globalApi ?? null
}

/** 归一化宿主响应：拦截器已解包的直接返回，否则取 .data */
export function unwrap<T = unknown>(raw: unknown): T {
  if (raw && typeof raw === 'object' && 'success' in (raw as Record<string, unknown>)) {
    return raw as T
  }
  const nested = (raw as { data?: unknown } | null)?.data
  return (nested ?? raw) as T
}

/** 格式化时间为“刚刚 / N 分钟前 / 绝对时间” */
export function formatTime(value?: string): string {
  if (!value) return '—'
  return value
}
