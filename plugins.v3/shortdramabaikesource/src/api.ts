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
  CacheClearPayload,
  CachePayload,
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
 * 图片是否使用宿主的磁盘缓存 —— 跟随系统的「全局图片缓存」开关。
 *
 * 面板拉 `/status` 时把该开关写进来：宿主关掉全局图片缓存时，插件请求图片也不再
 * 带 `cache=true`（宿主 `proxy_img` 的 `cache` 参数控制的是**读**，写由宿主自己决定）。
 * 拿不到状态前先按「开」处理，与宿主前端 `getDisplayImageUrl` 的默认一致。
 */
let imageCacheEnabled = true

/** 供 `/status` 回填系统图片缓存开关（内部使用） */
export function setImageCacheEnabled(value: boolean): void {
  imageCacheEnabled = value
}

/**
 * 把图片地址转成宿主图片代理地址。
 *
 * 站点 CDN（`cdn.duanjubaike.org`）本身允许直连，但走宿主代理能顺带复用
 * 「安全图片域名白名单」（本插件在 `init_plugin` 里已经把该 CDN 登记进去），
 * 也避免浏览器的混合内容拦截。
 *
 * 契约与宿主前端 `getDisplayImageUrl()` 一致：`system/img/0?imgurl=<urlencoded>&cache=true`，
 * 其中 `cache` 只在系统开启全局图片缓存时带上。
 */
export function proxyImage(url?: string | null): string {
  const raw = String(url || '').trim()
  if (!raw) return ''
  if (!/^https?:\/\//i.test(raw)) return raw
  if (raw.includes('/system/img/')) return raw
  const cache = imageCacheEnabled ? '&cache=true' : ''
  return `${apiPrefix()}system/img/0?imgurl=${encodeURIComponent(raw)}${cache}`
}

/** 打开站点的作品详情页（新标签） */
export function siteMediaUrl(url?: string | null): string {
  return String(url || '').trim()
}

/**
 * 把 axios 响应归一化成后端返回的原始对象。
 *
 * 宿主拦截器通常已经把响应体解了出来（`api.get()` 直接拿到后端 JSON），但个别版本
 * 仍会套一层 axios response —— 两种都要兜住。
 *
 * ⚠️ 判据必须看「像不像 axios response」，**绝不能只看有没有 `data` 字段**：
 * 后端自己的载荷里也有 `data`（`GET /cache` 的条目数组字段就叫 `data`），
 * 只看 `data` 会把载荷里的那个数组当成响应体返回出去，界面就变成空列表。
 * 真正的 axios response 一定同时带 `status`(number) / `statusText`(string) /
 * `headers`(object) —— 后端的业务载荷不会有这三样。
 */
function unwrap<T>(response: unknown): T {
  const value = response as Record<string, unknown> | null
  if (!value || typeof value !== 'object') return response as T
  const headers = value.headers
  const looksLikeAxiosResponse =
    typeof value.status === 'number'
    && typeof value.statusText === 'string'
    && Boolean(headers)
    && typeof headers === 'object'
  if (looksLikeAxiosResponse && 'data' in value) return value.data as T
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

/** 拉运行状态（域名 / 缓存条数 / 站外索引可用性），顺带同步系统的图片缓存开关 */
export async function fetchStatus(api: PluginApi): Promise<StatusPayload | null> {
  const report = await getJson<StatusPayload>(api, '/status')
  const imageCache = report?.cache?.system?.image_cache
  if (typeof imageCache === 'boolean') setImageCacheEnabled(imageCache)
  return report
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

/**
 * 查插件缓存（面板「缓存管理」）。
 *
 * 缓存后端与有效期都跟着宿主走（`app.sdk.cache`：Redis 或进程内内存），但**不接入**
 * 宿主的缓存管理页 —— 所以插件面板自己给一个同构的界面：统计 + 类型筛选 + 删除 + 清空。
 */
export function fetchCache(
  api: PluginApi,
  options: { kind?: string; keyword?: string; limit?: number } = {},
) {
  return getJson<CachePayload>(api, '/cache', {
    kind: options.kind || undefined,
    keyword: options.keyword || undefined,
    limit: options.limit ?? 200,
  })
}

/** 删一条缓存（键如 `detail:60017`） */
export async function deleteCacheEntry(api: PluginApi, key: string): Promise<CacheClearPayload | null> {
  try {
    const response = await api.delete(`${API_BASE}/cache/${encodeURIComponent(key)}`)
    return unwrap<CacheClearPayload>(response)
  } catch (error) {
    console.warn(`[${PLUGIN_ID}] 删除缓存失败`, error)
    return null
  }
}

/** 清空缓存；给了 `kind` 就只清这一类 */
export async function clearCache(api: PluginApi, kind = ''): Promise<CacheClearPayload | null> {
  try {
    const response = await api.delete(`${API_BASE}/cache`, {
      params: kind ? { kind } : undefined,
    })
    return unwrap<CacheClearPayload>(response)
  } catch (error) {
    console.warn(`[${PLUGIN_ID}] 清空缓存失败`, error)
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
