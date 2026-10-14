/**
 * 短剧百科数据源 —— 面板调用后端的公共工具。
 *
 * 约定：
 * 1. 优先用宿主经 props 传进来的 `api` 实例（带正确鉴权），缺失时回退全局
 *    `window.MoviePilotAPI`。本插件的接口在后端声明为 `auth: "bear"`，
 *    面板用登录态调用正好命中。
 * 2. 宿主 axios 的 baseURL 已是 `api/v1/`，所以插件内路径写
 *    `plugin/<PluginID>/<path>` —— 绝不能写成 `api/v1/plugin/...`（双前缀 404）。
 * 3. 主框架的 axios 拦截器通常会解包响应，个别版本仍套一层 axios response，
 *    因此统一用 `unwrap()` 归一化。
 */
import type {
  ActorProfile,
  ConfigOptions,
  LookupPayload,
  MediaRecord,
  PluginApi,
  PluginConfig,
  StatusPayload,
  UrlsClearPayload,
  UrlsPayload,
} from './types'

/** 插件 ID，必须与后端插件类名一致 */
export const PLUGIN_ID = 'ShortDramaBaikeSource'

/** 接口前缀（相对 baseURL `api/v1/`） */
export const API_BASE = `plugin/${PLUGIN_ID}`

/** 最近一次可用的宿主 axios 实例，供图片代理推导接口前缀 */
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

function rememberApi(api: PluginApi): void {
  lastApi = api
  const base = (api as { defaults?: { baseURL?: string } }).defaults?.baseURL
  if (typeof base === 'string' && base) apiBase = normalizeApiBase(base)
}

/**
 * 把 baseURL 收敛到 `api/v1/` 根。
 *
 * 宿主的 baseURL 有时会带上插件前缀，直接拼会得到
 * `api/v1/plugin/<id>/plugin/<id>/...` 这种地址，所以先截断到 `api/v1/`。
 */
function normalizeApiBase(base: string): string {
  const marker = 'api/v1/'
  const index = base.indexOf(marker)
  return index >= 0 ? base.slice(0, index + marker.length) : base
}

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

/**
 * 把图片地址转成宿主图片代理地址。
 *
 * 站点 CDN（`cdn.duanjubaike.org`）本身允许直连，但走宿主代理能顺带复用
 * 「安全图片域名白名单」（本插件在 `init_plugin` 里已经把该 CDN 登记进去），
 * 也避免浏览器的混合内容拦截。
 *
 * 契约与宿主前端 `getDisplayImageUrl()` 一致：`system/img/0?imgurl=<urlencoded>&cache=true`。
 */
export function proxyImage(url?: string | null): string {
  const raw = String(url || '').trim()
  if (!raw) return ''
  if (!/^https?:\/\//i.test(raw)) return raw
  if (raw.includes('/system/img/')) return raw
  return `${apiPrefix()}system/img/0?imgurl=${encodeURIComponent(raw)}&cache=true`
}

/** 打开站点的作品详情页（新标签） */
export function siteMediaUrl(url?: string | null): string {
  return String(url || '').trim()
}

/**
 * 把 axios 响应归一化成后端返回的原始对象。
 *
 * 宿主拦截器可能已经把 `data` 解出来了，也可能没有 —— 两种都兜住。
 */
function unwrap<T>(response: unknown): T {
  const value = response as { data?: unknown } | null
  if (value && typeof value === 'object' && 'data' in value) {
    const inner = (value as { data?: unknown }).data
    // 只在看起来像「被包了一层 axios response」时解包
    if (inner && typeof inner === 'object') return inner as T
  }
  return response as T
}

/** 调一个 GET 接口，失败时返回 null（面板不弹错误堆栈，只提示一句） */
async function getJson<T>(api: PluginApi, path: string, params?: Record<string, unknown>): Promise<T | null> {
  try {
    const response = await api.get(`${API_BASE}${path}`, { params })
    return unwrap<T>(response)
  } catch (error) {
    console.warn(`[${PLUGIN_ID}] ${path} 调用失败`, error)
    return null
  }
}

/** 拉运行状态（域名 / 缓存条数 / 站外索引可用性） */
export function fetchStatus(api: PluginApi): Promise<StatusPayload | null> {
  return getJson<StatusPayload>(api, '/status')
}

/**
 * 关键词检索 —— 面板**唯一那个搜索框**的后端。
 *
 * 一个词片名与演员名都收：后端只打一次站外索引，再把同一批原始结果分别喂给
 * 「作品解析」与「演员解析」，返回 `{ titles, actors }` 两块。
 * 前端哪边有结果就展示哪边，不预判用户输入的是片名还是人名。
 */
export function lookupKeyword(api: PluginApi, keyword: string, year?: string) {
  return getJson<LookupPayload>(api, '/lookup', { keyword, year: year || undefined })
}

/** 按 media_id 或片名取一条完整作品记录 */
export function recognizeTitle(api: PluginApi, options: { media_id?: string; keyword?: string; year?: string }) {
  return getJson<{ success?: boolean; message?: string; record?: MediaRecord | null }>(
    api,
    '/recognize',
    options,
  )
}

/** 取演员档案（含全部作品与合作演员） */
export function fetchActor(api: PluginApi, options: { actor_id?: string; name?: string }) {
  return getJson<{ success?: boolean; message?: string; actor?: ActorProfile | null }>(api, '/actor', options)
}

/**
 * 查 URL 库。
 *
 * 库里**只存 URL**（关键词 → 页面地址），不存解析结果 —— 站点内容随时在变，页面永远
 * 实时解析。不给 `keyword` 时回最近入库的记录，给了就按关键词精确查询。
 */
export function fetchUrls(api: PluginApi, options: { keyword?: string; kind?: string; limit?: number } = {}) {
  return getJson<UrlsPayload>(api, '/urls', {
    keyword: options.keyword || undefined,
    kind: options.kind || undefined,
    limit: options.limit ?? 50,
  })
}

/**
 * 清空 URL 库（面板上的「清空库」按钮）。
 *
 * 不给 `kind` / `keyword` 就是**整库清空**；只给 `kind` 清该类全部；两个都给只清那个
 * 关键词的记录。破坏性操作 —— 调用方必须先让用户确认一次。
 */
export async function clearUrls(
  api: PluginApi,
  options: { keyword?: string; kind?: string } = {},
): Promise<UrlsClearPayload | null> {
  try {
    const response = await api.post(`${API_BASE}/urls/clear`, {
      keyword: options.keyword || '',
      kind: options.kind || '',
    })
    return unwrap<UrlsClearPayload>(response)
  } catch (error) {
    console.warn(`[${PLUGIN_ID}] 清空 URL 库失败`, error)
    return null
  }
}

/** 读配置（面板配置页回显） */
export function fetchConfig(api: PluginApi) {
  return getJson<{ success?: boolean; config?: Partial<PluginConfig>; options?: ConfigOptions }>(api, '/config')
}

/** 存配置 */
export async function saveConfig(
  api: PluginApi,
  config: Partial<PluginConfig>,
): Promise<{ success?: boolean; message?: string; config?: Partial<PluginConfig> } | null> {
  try {
    const response = await api.put(`${API_BASE}/config`, config)
    return unwrap(response)
  } catch (error) {
    console.warn(`[${PLUGIN_ID}] 保存配置失败`, error)
    return null
  }
}
