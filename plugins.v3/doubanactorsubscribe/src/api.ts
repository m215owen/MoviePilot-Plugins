/**
 * 豆瓣演员订阅 —— 前端调用宿主与插件后端的公共工具。
 *
 * 重要约定：
 * 1. 优先使用宿主传入的 `api` prop（实例作用域，适配插件虚拟分身）；
 *    仅在 prop 缺失时才回退全局 `window.MoviePilotAPI`。
 * 2. 宿主 axios 的 baseURL 已是 `api/v1/`，因此插件内路径写
 *    `plugin/<PluginID>/<path>`，绝不能写成 `api/v1/plugin/...`（会变成双前缀 404）。
 * 3. 订阅提交直接调用宿主原生订阅接口 `subscribe/`，这样订阅会归属到当前登录用户，
 *    并复用宿主的识别、去重与校验逻辑。
 * 4. 主框架 axios 拦截器通常已解包响应，但个别版本仍会套一层 axios response，
 *    统一用 `unwrap()` 归一化。
 */
import type { ActorWork, PluginApi } from './types'

/** 插件 ID，必须与后端插件类名一致 */
export const PLUGIN_ID = 'DoubanActorSubscribe'

/** 插件接口路径前缀（相对 baseURL `api/v1/`） */
export const API_BASE = `plugin/${PLUGIN_ID}`

/** 宿主原生订阅接口（相对 baseURL `api/v1/`） */
export const HOST_SUBSCRIBE = 'subscribe/'

/** 解析可用的 HTTP 客户端：优先 api prop，其次全局注入 */
export function resolveApi(props: { api?: PluginApi }): PluginApi | null {
  if (props && props.api) return props.api
  const globalApi =
    typeof window !== 'undefined'
      ? (window as unknown as { MoviePilotAPI?: PluginApi }).MoviePilotAPI
      : null
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

/** 作品的订阅身份键，与后端 media_source:media_id 保持一致 */
export function workKey(work: ActorWork): string {
  return `${work.media_source}:${work.media_id}`
}

/** 从捕获的异常里提取可读的错误信息（兼容 axios 与宿主响应体） */
export function extractError(err: unknown): string {
  const anyErr = err as {
    response?: { data?: { detail?: unknown; message?: unknown } }
    message?: string
  }
  const data = anyErr?.response?.data
  if (data) {
    if (typeof data.detail === 'string' && data.detail) return data.detail
    if (Array.isArray(data.detail) && data.detail.length) {
      const first = data.detail[0] as { msg?: string }
      if (first?.msg) return String(first.msg)
    }
    if (typeof data.message === 'string' && data.message) return data.message
  }
  return anyErr?.message || '请求失败'
}

/** 订阅提交结果 */
export interface SubscribeOutcome {
  ok: boolean
  message: string
}

/**
 * 把单个作品提交到 MoviePilot 订阅系统。
 *
 * 使用豆瓣媒体身份（media_source=douban + media_id）提交，因此不依赖宿主的识别源设置，
 * 命中准确且速度快；宿主侧会自动处理季号拆分、去重与用户归属。
 */
export async function submitSubscribe(
  api: PluginApi,
  work: ActorWork
): Promise<SubscribeOutcome> {
  const payload: Record<string, unknown> = {
    name: work.title,
    year: work.year || '',
    media_source: work.media_source,
    media_id: work.media_id,
  }
  if (work.type) payload.type = work.type
  try {
    const raw = await api.post(HOST_SUBSCRIBE, payload)
    const res = unwrap<{ success?: boolean; message?: string }>(raw)
    if (res && res.success === false) {
      return { ok: false, message: res.message || '订阅失败' }
    }
    return { ok: true, message: res?.message || `已提交订阅：${work.title}` }
  } catch (err) {
    return { ok: false, message: extractError(err) }
  }
}

/** 读取宿主现有订阅的媒体身份集合，用于在面板上标记「已订阅」 */
export async function fetchSubscribedKeys(api: PluginApi): Promise<string[]> {
  try {
    const raw = await api.get(HOST_SUBSCRIBE, { params: { page: 1, count: 500 } })
    const list = unwrap<unknown>(raw)
    const keys: string[] = []
    if (Array.isArray(list)) {
      for (const item of list) {
        const row = item as { media_source?: unknown; media_id?: unknown }
        if (row?.media_source && row?.media_id) {
          keys.push(`${row.media_source}:${row.media_id}`)
        }
      }
    }
    return keys
  } catch (err) {
    // 读取失败只影响「已订阅」标记，不阻塞面板渲染
    console.warn(`[${PLUGIN_ID}] 读取已有订阅失败`, err)
    return []
  }
}

/** 格式化时间为「刚刚 / N 分钟前 / 绝对时间」 */
export function formatTime(value?: string): string {
  if (!value) return '尚未刷新'
  const timestamp = Date.parse(value.replace(' ', 'T'))
  if (Number.isNaN(timestamp)) return value
  const diff = Date.now() - timestamp
  if (diff < 60_000) return '刚刚'
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)} 分钟前`
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)} 小时前`
  return value
}
