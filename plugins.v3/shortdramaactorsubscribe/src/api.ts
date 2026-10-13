/**
 * 短剧演员订阅 —— 前端调用宿主与插件后端的公共工具。
 *
 * 重要约定：
 * 1. 优先使用宿主传入的 `api` prop（实例作用域，适配插件虚拟分身）；
 *    仅在 prop 缺失时才回退全局 `window.MoviePilotAPI`。
 * 2. 宿主 axios 的 baseURL 已是 `api/v1/`，因此插件内路径写
 *    `plugin/<PluginID>/<path>`，绝不能写成 `api/v1/plugin/...`（会变成双前缀 404）。
 * 3. 主框架 axios 拦截器通常已解包响应，但个别版本仍会套一层 axios response，
 *    统一用 `unwrap()` / `unwrapList()` 归一化。
 * 4. 本插件不走宿主订阅系统：资源由插件自己按剧名到站点搜索并择优下载，
 *    因此这里不需要 `subscribe/` 相关接口。
 */
import type {
  ActorCandidate,
  ApiResult,
  OptionsPayload,
  PluginApi,
  PluginConfig,
  StatusPayload,
  WorkItem,
  WorksPayload,
} from './types'

/** 插件 ID，必须与后端插件类名一致 */
export const PLUGIN_ID = 'ShortDramaActorSubscribe'

/** 插件接口路径前缀（相对 baseURL `api/v1/`） */
export const API_BASE = `plugin/${PLUGIN_ID}`

/**
 * MoviePilot 自带的「资源搜索」页路由。
 *
 * 就是左侧导航里那一项（`mdi-magnify`），页面组件 `ResourceSearchView`，权限 `search`。
 * 它支持通过 query 直接发起一次搜索，是「拿这部剧去站点里找同名资源」最省事的入口，
 * 也是本插件「按剧名搜索」逻辑的人工复核通道。
 */
export const HOST_RESOURCE_PAGE = '/resource'

/**
 * MoviePilot 自带的「媒体详情」页路由（探索页点进某部作品打开的那个页面）。
 * 与 `HOST_RESOURCE_PAGE` 同理，必须走 hash 路由：`<应用基址>#/media?…`。
 */
export const HOST_MEDIA_PAGE = '/media'

/** 最近一次可用的宿主 axios 实例，供图片代理等非 props 场景推导接口前缀 */
let lastApi: PluginApi | null = null

/** 解析可用的 HTTP 客户端：优先 api prop，其次全局注入 */
export function resolveApi(props: { api?: PluginApi }): PluginApi | null {
  if (props && props.api) {
    rememberApi(props.api)
    return props.api
  }
  const globalApi =
    typeof window !== 'undefined'
      ? (window as unknown as { MoviePilotAPI?: PluginApi }).MoviePilotAPI
      : null
  if (globalApi) rememberApi(globalApi)
  return globalApi ?? lastApi
}

/** 记录 axios 实例与其 baseURL，供图片代理拼装绝对地址 */
function rememberApi(api: PluginApi): void {
  lastApi = api
  const base = (api as { defaults?: { baseURL?: string } }).defaults?.baseURL
  if (typeof base === 'string' && base) apiBase = normalizeApiBase(base)
}

/**
 * 把 baseURL 收敛到 `api/v1/` 根，避免宿主的 baseURL 携带插件前缀时
 * 拼出 `api/v1/plugin/<id>/system/img/...` 这种错误地址。
 */
function normalizeApiBase(base: string): string {
  const marker = 'api/v1/'
  const index = base.indexOf(marker)
  return index >= 0 ? base.slice(0, index + marker.length) : base
}

/** 宿主 axios 的 baseURL（默认 `api/v1/`） */
let apiBase = 'api/v1/'

/** 把 baseURL 解析成绝对前缀，兼容部署在子路径下的实例 */
function apiPrefix(): string {
  const fallback = apiBase.endsWith('/') ? apiBase : `${apiBase}/`
  try {
    const href = typeof window !== 'undefined' ? window.location.href : 'http://127.0.0.1/'
    const resolved = new URL(apiBase, href).toString()
    return resolved.endsWith('/') ? resolved : `${resolved}/`
  } catch {
    return fallback
  }
}

/** 当前应用地址去掉 hash 的部分；非浏览器环境下退化为空串（相对地址） */
function appBaseUrl(): string {
  if (typeof window === 'undefined') return ''
  return window.location.href.split('#')[0]
}

/**
 * 把图片地址转换为宿主图片代理地址。
 *
 * 豆瓣图片 CDN（`*.doubanio.com`）有防盗链：无 Referer 返回 418、Referer 不是豆瓣域名
 * 返回 403，浏览器无法伪造 Referer，因此必须经宿主 `system/img` 代理取图。
 *
 * 契约与宿主前端 `getDisplayImageUrl()` 一致：`system/img/0?imgurl=<urlencoded>&cache=true`
 * （`{proxy}` 取 0，即不强制走用户配置的代理；鉴权走浏览器资源 Token Cookie）。
 */
export function proxyImage(url?: string | null): string {
  const raw = String(url || '').trim()
  if (!raw) return ''
  if (!/^https?:\/\//i.test(raw)) return raw
  if (raw.includes('/system/img/')) return raw
  return `${apiPrefix()}system/img/0?imgurl=${encodeURIComponent(raw)}&cache=true`
}

/**
 * 组装 MoviePilot「资源搜索」页地址，打开即按剧名搜一遍站点资源。
 *
 * ⚠️ 宿主前端用的是 **hash 路由**，绝不能直接拼 `/resource?…`：那样只会落到站点根路径、
 * 由 SPA 兜底渲染成首页，看起来就是「点了没反应」。正确形态是 `<应用基址>#/resource?…`。
 *
 * @param keyword 搜索关键词（本插件用剧名）
 * @param sites 限定搜索的站点 ID（可传数组或 `1,2,3` 字符串）；留空则用宿主自己的默认站点
 */
export function resourceSearchUrl(keyword: string, sites?: number[] | string): string {
  const text = String(keyword || '').trim()
  if (!text) return ''
  const params = new URLSearchParams()
  params.set('keyword', text)
  params.set('title', text)
  const siteText = normalizeSiteIds(sites)
  if (siteText) params.set('sites', siteText)
  return `${appBaseUrl()}#${HOST_RESOURCE_PAGE}?${params.toString()}`
}

/**
 * 组装 MoviePilot「媒体详情」页地址（与探索页点进媒体是同一个页面）。
 *
 * 两个易错点：① 必须走 hash 路由（`<应用基址>#/media?…`），直接拼 `/media?…`
 * 只会落到站点根路径并被 SPA 兜底成首页；② 宿主详情页**强依赖 `type`**（取中文的
 * 电影 / 电视剧），缺它会渲染成空壳 —— 所以调用方在拿不到类型时应当不显示这个入口。
 *
 * `media_source` 用发现来源（douban / tmdb），宿主据此解析媒体身份。
 *
 * @returns 可直接放进 `<a href>` 的地址；缺少 `media_id` 时返回空串
 */
export function mediaPageUrl(work: {
  source?: string
  media_id?: string
  title?: string
  year?: string
  type?: string
}): string {
  const mediaId = String(work?.media_id ?? '').trim()
  if (!mediaId) return ''
  const params = new URLSearchParams()
  params.set('media_source', String(work?.source ?? '').trim() || 'douban')
  params.set('media_id', mediaId)
  for (const key of ['title', 'year', 'type'] as const) {
    const value = String(work?.[key] ?? '').trim()
    if (value) params.set(key, value)
  }
  return `${appBaseUrl()}#${HOST_MEDIA_PAGE}?${params.toString()}`
}

/** 把站点 ID 归一化成宿主认识的 `1,2,3` 形态；无效输入返回空串 */
export function normalizeSiteIds(sites?: number[] | string): string {
  if (sites == null) return ''
  const list = Array.isArray(sites) ? sites : String(sites).split(',')
  const ids: string[] = []
  for (const item of list) {
    const text = String(item ?? '').trim()
    if (!text) continue
    const value = Number(text)
    if (!Number.isFinite(value)) continue
    ids.push(String(value))
  }
  return ids.join(',')
}

/** 归一化宿主响应：拦截器已解包的直接返回，否则取 .data */
export function unwrap<T = unknown>(raw: unknown): T {
  if (raw && typeof raw === 'object' && 'success' in (raw as Record<string, unknown>)) {
    return raw as T
  }
  const nested = (raw as { data?: unknown } | null)?.data
  return (nested ?? raw) as T
}

/**
 * 从宿主响应中取出**列表**。
 *
 * 宿主列表接口统一返回 `{success, data: [...]}` 信封，而 `unwrap()` 遇到带 `success`
 * 的对象会原样返回信封（对读 `success`/`message` 的场景是必须的），
 * 于是 `Array.isArray(信封)` 恒为假。这里对三种形状一并兜底。
 */
export function unwrapList<T = unknown>(raw: unknown): T[] {
  const value = raw as unknown
  if (Array.isArray(value)) return value as T[]
  if (value && typeof value === 'object') {
    const inner = (value as { data?: unknown }).data
    if (Array.isArray(inner)) return inner as T[]
    const deeper = (inner as { data?: unknown } | null)?.data
    if (Array.isArray(deeper)) return deeper as T[]
  }
  return []
}

/** 归一化后的插件接口结果 */
export interface NormalizedResult<T> {
  ok: boolean
  data?: T
  message: string
}

/**
 * 归一并容错插件接口的返回体。
 *
 * 宿主不会为插件的动态路由套统一响应体，因此插件接口的形状由插件自己决定；
 * 这里把「带 success 的信封」与「裸对象」统一成 `{ok, data, message}`，
 * 避免把成功误判成失败。
 */
export function normalizeResult<T = unknown>(raw: unknown): NormalizedResult<T> {
  const value = unwrap<Record<string, unknown>>(raw)
  if (value && typeof value === 'object' && 'success' in value) {
    return {
      ok: Boolean(value.success),
      data: value.data as T | undefined,
      message: String(value.message || ''),
    }
  }
  return { ok: true, data: (value ?? undefined) as T | undefined, message: '' }
}

/** 从捕获的异常里提取可读的错误信息（兼容 axios 与宿主统一响应体） */
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

/** 格式化时间为「刚刚 / N 分钟前 / 绝对时间」 */
export function formatTime(value?: string): string {
  if (!value) return '尚未运行'
  const timestamp = Date.parse(String(value).replace(' ', 'T'))
  if (Number.isNaN(timestamp)) return String(value)
  const diff = Date.now() - timestamp
  if (diff < 60_000) return '刚刚'
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)} 分钟前`
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)} 小时前`
  return String(value)
}

/** 冷却剩余分钟数 → 可读文案 */
export function formatCooldown(minutes: number): string {
  const value = Number(minutes) || 0
  if (value <= 0) return '随时重试'
  if (value < 60) return `冷却 ${value} 分钟`
  const hours = Math.floor(value / 60)
  const rest = value % 60
  return rest ? `冷却 ${hours} 小时 ${rest} 分` : `冷却 ${hours} 小时`
}

// ─── 插件接口 ────────────────────────────────────────────────────

/** 读取运行概览（含账本与冷却列表） */
export async function fetchStatus(api: PluginApi): Promise<StatusPayload | null> {
  const res = normalizeResult<StatusPayload>(await api.get(`${API_BASE}/status`))
  return res.ok && res.data ? res.data : null
}

/** 读取配置与下拉候选 */
export async function fetchConfig(
  api: PluginApi
): Promise<{ config: PluginConfig; options: OptionsPayload } | null> {
  const res = normalizeResult<{ config: PluginConfig; options: OptionsPayload }>(
    await api.get(`${API_BASE}/config`)
  )
  return res.ok && res.data ? res.data : null
}

/** 保存配置（等价于宿主配置页的保存：落盘 + 重新初始化插件） */
export async function saveConfig(
  api: PluginApi,
  config: Partial<PluginConfig>
): Promise<{ ok: boolean; message: string }> {
  try {
    const res = normalizeResult<PluginConfig>(await api.put(`${API_BASE}/config`, config))
    return { ok: res.ok, message: res.message || (res.ok ? '配置已保存' : '保存失败') }
  } catch (err) {
    return { ok: false, message: extractError(err) }
  }
}

/** 读取站点 / 下载器 / 整理方式候选 */
export async function fetchOptions(api: PluginApi): Promise<OptionsPayload | null> {
  const res = normalizeResult<OptionsPayload>(await api.get(`${API_BASE}/options`))
  return res.ok && res.data ? res.data : null
}

/**
 * 立即执行一轮订阅轮询。
 *
 * 后端把执行登记成**一次性后台任务**（避免演员多时 HTTP 超时），
 * 因此这里提交后要轮询 `/status`：`running` 从 true 回到 false，
 * 且 `summary.last_run` 发生变化，才算真正跑完。
 */
export async function runOnce(
  api: PluginApi,
  apply: (payload: StatusPayload) => void,
  beforeRun = ''
): Promise<{ ok: boolean; message: string }> {
  try {
    const res = normalizeResult(await api.post(`${API_BASE}/run`))
    if (!res.ok) return { ok: false, message: res.message || '提交执行失败' }
    // 后端延迟 1 秒入队，先等一小会再开始轮询
    await new Promise((resolve) => window.setTimeout(resolve, 1500))
    for (let index = 0; index < 90; index += 1) {
      const payload = await fetchStatus(api)
      if (payload) {
        apply(payload)
        const lastRun = String(payload.summary?.last_run || '')
        if (!payload.running && lastRun && lastRun !== beforeRun) {
          return { ok: true, message: payload.last_result?.message || '执行完成' }
        }
      }
      await new Promise((resolve) => window.setTimeout(resolve, 2000))
    }
    return { ok: true, message: '已提交执行，正在后台运行，可稍后刷新查看' }
  } catch (err) {
    return { ok: false, message: extractError(err) }
  }
}

/** 立即整理一次 */
export async function organizeNow(api: PluginApi): Promise<{ ok: boolean; message: string }> {
  try {
    const res = normalizeResult(await api.post(`${API_BASE}/organize`))
    return { ok: res.ok, message: res.message || (res.ok ? '已执行整理扫描' : '整理未执行') }
  } catch (err) {
    return { ok: false, message: extractError(err) }
  }
}

/** 从账本移除一条记录（允许下次轮询重新下载） */
export async function removeLedgerEntry(
  api: PluginApi,
  key: string
): Promise<{ ok: boolean; message: string }> {
  try {
    const res = normalizeResult(await api.post(`${API_BASE}/unmatch`, { key }))
    return { ok: res.ok, message: res.message || (res.ok ? '已移除' : '移除失败') }
  } catch (err) {
    return { ok: false, message: extractError(err) }
  }
}

/** 清空账本（连带清空冷却表） */
export async function clearLedger(api: PluginApi): Promise<{ ok: boolean; message: string }> {
  try {
    const res = normalizeResult(await api.post(`${API_BASE}/clear`))
    return { ok: res.ok, message: res.message || (res.ok ? '账本已清空' : '清空失败') }
  } catch (err) {
    return { ok: false, message: extractError(err) }
  }
}

/** 清空未命中冷却 */
export async function clearCooldown(api: PluginApi): Promise<{ ok: boolean; message: string }> {
  try {
    const res = normalizeResult(await api.post(`${API_BASE}/miss/clear`))
    return { ok: res.ok, message: res.message || (res.ok ? '冷却已清空' : '清空失败') }
  } catch (err) {
    return { ok: false, message: extractError(err) }
  }
}

/** 按名称搜索演员（TMDB + 豆瓣并集），供配置页取 ID */
export async function searchActor(
  api: PluginApi,
  name: string
): Promise<{ ok: boolean; message: string; data: ActorCandidate[] }> {
  try {
    const res = normalizeResult<ActorCandidate[]>(
      await api.get(`${API_BASE}/search_actor`, { params: { name } })
    )
    return { ok: res.ok, message: res.message, data: res.data || [] }
  } catch (err) {
    return { ok: false, message: extractError(err), data: [] }
  }
}

// ─── 作品墙 ──────────────────────────────────────────────────────

/** 读取演员作品墙（发现层快照 + 每条状态） */
export async function fetchWorks(api: PluginApi): Promise<WorksPayload | null> {
  const res = normalizeResult<WorksPayload>(await api.get(`${API_BASE}/works`))
  return res.ok && res.data ? res.data : null
}

/**
 * 立即订阅一条作品：后端按同一条「搜索 → 匹配 → 择优 → 下载」链路处理，
 * 成功后写账本（因此不会与自动轮询重复下载）。
 */
export async function subscribeWork(
  api: PluginApi,
  payload: { key?: string; title?: string; year?: string }
): Promise<{ ok: boolean; message: string; data?: WorkItem }> {
  try {
    const res = normalizeResult<WorkItem>(await api.post(`${API_BASE}/works/subscribe`, payload))
    return { ok: res.ok, message: res.message || (res.ok ? '已提交下载' : '订阅失败'), data: res.data }
  } catch (err) {
    return { ok: false, message: extractError(err) }
  }
}

/**
 * 只刷新演员作品快照（不下载）。
 *
 * 与「立即运行」同样是后台一次性任务：提交后轮询 `/works` 的 `running` 直到结束，
 * 中途把每次拿到的数据喂给 `apply` 让页面持续更新。
 */
export async function refreshWorks(
  api: PluginApi,
  apply: (payload: WorksPayload) => void
): Promise<{ ok: boolean; message: string }> {
  try {
    const res = normalizeResult(await api.post(`${API_BASE}/works/refresh`))
    if (!res.ok) return { ok: false, message: res.message || '提交刷新失败' }
    await new Promise((resolve) => window.setTimeout(resolve, 1200))
    for (let index = 0; index < 90; index += 1) {
      const payload = await fetchWorks(api)
      if (payload) {
        apply(payload)
        if (!payload.running) return { ok: true, message: '作品已刷新' }
      }
      await new Promise((resolve) => window.setTimeout(resolve, 2000))
    }
    return { ok: true, message: '正在后台刷新，稍后刷新页面查看' }
  } catch (err) {
    return { ok: false, message: extractError(err) }
  }
}

/** 从路径里取文件名（账本展示「整理后路径」时用） */
export function baseName(path?: string): string {
  const text = String(path || '').trim()
  if (!text) return ''
  const parts = text.replace(/[\\/]+$/, '').split(/[\\/]/)
  return parts[parts.length - 1] || text
}

/** 供类型推断使用（避免 `ApiResult` 未使用告警） */
export type { ApiResult }
