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
 * 4. **订阅走宿主系统**：卡片上的「订阅」调宿主注入的 `nativeSubscribe`，
 *    插件后端不参与订阅；这里只需要读一次 `subscribe/` 用来标「已订阅」。
 */
import type {
  ActorSearchPayload,
  ApiResult,
  DownloadClientOption,
  FacetItem,
  PluginApi,
  PluginConfig,
  StatusPayload,
  WorkItem,
  WorkSearchPayload,
  WorksFacets,
  WorksPayload,
  WorksQuery,
} from './types'

/** 插件 ID，必须与后端插件类名一致 */
export const PLUGIN_ID = 'ShortDramaActorSubscribe'

/** 插件接口路径前缀（相对 baseURL `api/v1/`） */
export const API_BASE = `plugin/${PLUGIN_ID}`

/** MoviePilot 自带的「媒体详情」页路由（探索页点卡片打开的那个页面） */
export const HOST_MEDIA_PAGE = '/media'

/** 宿主「下载客户端」列表接口（订阅下载器的选项来源） */
export const HOST_DOWNLOAD_CLIENTS = 'download/clients'

/** 宿主订阅接口：配置页指定了下载器时，作品墙直接提交（不弹系统订阅对话框） */
const HOST_SUBSCRIBE = 'subscribe/'

/** 最近一次可用的宿主 axios 实例 */
let lastApi: PluginApi | null = null

/** 宿主 axios 的 baseURL（默认 `api/v1/`） */
let apiBase = 'api/v1/'

/** 解析可用的 HTTP 客户端：优先 api prop，其次全局注入 */
function resolveApi(props: { api?: PluginApi }): PluginApi | null {
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

/** 把 baseURL 收敛到 `api/v1/` 根，避免拼出 `api/v1/plugin/<id>/system/img/...` */
function normalizeApiBase(base: string): string {
  const marker = 'api/v1/'
  const index = base.indexOf(marker)
  return index >= 0 ? base.slice(0, index + marker.length) : base
}

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

/** 当前应用地址去掉 hash 的部分；非浏览器环境下退化为空串 */
function appBaseUrl(): string {
  if (typeof window === 'undefined') return ''
  return window.location.href.split('#')[0]
}

/**
 * 把图片地址转换为宿主图片代理地址。
 *
 * 短剧百科的图片 CDN 有防盗链与 Referer 校验，浏览器无法伪造，必须经宿主
 * `system/img` 代理取图。契约与宿主前端一致：`system/img/0?imgurl=<urlencoded>&cache=true`。
 */
export function proxyImage(url?: string | null): string {
  const raw = String(url || '').trim()
  if (!raw) return ''
  if (!/^https?:\/\//i.test(raw)) return raw
  if (raw.includes('/system/img/')) return raw
  return `${apiPrefix()}system/img/0?imgurl=${encodeURIComponent(raw)}&cache=true`
}

/**
 * 组装宿主的「媒体详情」页地址（hash 路由）。
 *
 * 短剧百科已作为宿主媒体数据源接入，因此详情页由系统自己渲染：
 * 带上 `media_source` + `media_id`，系统会拿这个身份去百科取详情。
 */
export function mediaPageUrl(work: WorkItem): string {
  const query = new URLSearchParams()
  query.set('media_source', work.media_source)
  query.set('media_id', work.media_id)
  query.set('title', work.title)
  if (work.year) query.set('year', work.year)
  query.set('type', work.type || '电视剧')
  return `${appBaseUrl()}#${HOST_MEDIA_PAGE}?${query.toString()}`
}

/**
 * 组装宿主的「资源搜索」页地址（hash 路由），卡片上的搜索按钮用。
 *
 * 参数口径与宿主 MediaCard 的 `handleSearch` 一致：按标题搜资源（`area=title`），
 * 带上媒体身份让站点搜索结果能对回这部短剧；用户在站点弹窗里选了站点时，
 * 额外带 `sites=<id,..>`（宿主资源页会只搜这些站点）。
 */
export function resourceSearchUrl(work: WorkItem, sites?: number[]): string {
  const query = new URLSearchParams()
  query.set('media_source', work.media_source)
  query.set('media_id', work.media_id)
  query.set('type', work.type || '电视剧')
  query.set('area', 'title')
  query.set('title', work.title)
  if (work.year) query.set('year', work.year)
  if (sites && sites.length) query.set('sites', sites.join(','))
  return `${appBaseUrl()}#/resource?${query.toString()}`
}

/** 宿主「站点」的展示字段（`site/media/{t}` 返回项的子集） */
export interface HostSite {
  id: number
  name: string
  is_active?: boolean
}

/** 宿主对「电视剧」资源的站点查询结果缓存（作品墙全是电视剧，一份即可） */
let cachedSites: HostSite[] | null = null

/**
 * 查询当前可用站点（口径与宿主 MediaCard 的 `querySites` 一致），配置页选站点用。
 *
 * 端点是 `site/media/tv`，需要登录态鉴权——走宿主注入的 axios 实例即可。
 * **请求失败时抛错**（与「成功但一台站点都没有」区分开，配置页要分别提示）。
 */
export async function fetchSearchSites(props: { api?: PluginApi }): Promise<HostSite[]> {
  if (cachedSites) return cachedSites
  const api = resolveApi(props)
  if (!api?.get) throw new Error('缺少可用的 api 实例')
  // ⚠️ 宿主返回的是信封 `{success, message, data: [...]}`（真机实测），必须 unwrapList
  // 取 `.data`；直接 Array.isArray(payload) 会永远判空 → 配置页一块站点都不显示。
  const payload = unwrap<HostSite[]>(await api.get('site/media/tv'))
  const rows = unwrapList<HostSite>(payload)
  const sites = rows.filter((site) => site && site.is_active)
  cachedSites = sites
  return sites
}

/** 读取宿主已配置的下载客户端（去重，只取 name/type；读不到返回空列表）。 */
export async function fetchDownloaderOptions(
  props: { api?: PluginApi },
): Promise<DownloadClientOption[]> {
  const api = resolveApi(props)
  if (!api?.get) return []
  try {
    const rows = unwrapList<Record<string, unknown>>(await api.get(HOST_DOWNLOAD_CLIENTS))
    const options: DownloadClientOption[] = []
    const seen = new Set<string>()
    for (const row of Array.isArray(rows) ? rows : []) {
      const name = String(row?.name || '').trim()
      if (!name || seen.has(name)) continue
      seen.add(name)
      options.push({ name, type: String(row?.type || '').trim() })
    }
    return options
  } catch (err) {
    console.warn(`[${PLUGIN_ID}] 读取下载器列表失败`, err)
    return []
  }
}

/** 从请求异常里抠出可读的失败原因（宿主 4xx 会把原因放在 detail / message）。 */
function extractErrorMessage(err: unknown): string {
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

/**
 * 直接向宿主提交订阅（携带订阅偏好）。
 *
 * 系统订阅弹窗没有下载器选项 —— 配置页指定了下载器时走这里，把偏好一并带上。
 * 返回 ``ok`` = 宿主已受理；``message`` 为宿主返回的说明（成功或失败原因）。
 */
export async function submitSubscribe(
  props: { api?: PluginApi },
  work: Pick<WorkItem, 'title' | 'year' | 'media_source' | 'media_id' | 'type'>,
  downloader: string,
): Promise<{ ok: boolean; message: string }> {
  const api = resolveApi(props)
  if (!api?.post) return { ok: false, message: '缺少可用的 api 实例' }
  const payload: Record<string, unknown> = {
    name: work.title,
    year: work.year || '',
    media_source: work.media_source,
    media_id: work.media_id,
    type: work.type || '电视剧',
  }
  if (downloader) payload.downloader = downloader
  try {
    const res = unwrap<{ success?: boolean; message?: string }>(
      await api.post(HOST_SUBSCRIBE, payload),
    )
    if (res && res.success === false) {
      return { ok: false, message: String(res.message || '订阅失败') }
    }
    return { ok: true, message: String(res?.message || `已提交订阅：${work.title}`) }
  } catch (err) {
    return { ok: false, message: extractErrorMessage(err) }
  }
}

/** 归一化响应体：兼容「已解包」与「套一层 axios response」两种形态 */
function unwrap<T = any>(response: any): T {
  if (!response) return response
  if (response.data !== undefined && response.status !== undefined) return response.data
  return response
}

/** 归一化列表响应：列表接口返回 `{success, data:[...]}` */
function unwrapList<T = any>(response: any): T[] {
  const payload = unwrap<any>(response)
  if (!payload) return []
  if (Array.isArray(payload)) return payload
  if (Array.isArray(payload.data)) return payload.data
  return []
}

/** 归一化筛选项列表：后端可能是 undefined / 非数组 */
function normalizeFacetList(raw: unknown): FacetItem[] {
  if (!Array.isArray(raw)) return []
  return raw
    .filter((item) => item && typeof item === 'object')
    .map((item) => ({
      value: String((item as FacetItem).value ?? ''),
      count: Number((item as FacetItem).count ?? 0),
    }))
    .filter((item) => item.value)
}

/** 归一化筛选项集合 */
function normalizeFacets(raw: any): WorksFacets {
  return {
    genres: normalizeFacetList(raw?.genres),
    years: normalizeFacetList(raw?.years),
    studios: normalizeFacetList(raw?.studios),
  }
}

/**
 * 归一化一条作品。
 *
 * 后端快照里可能还是**旧结构**（没有 `genres` / `heat` 这些后来加的字段），
 * 直接渲染 `work.genres.join()` 会抛错把整面墙打崩 —— 这里统一补齐默认值。
 */
function normalizeWork(raw: any): WorkItem {
  return {
    ...(raw || {}),
    genres: Array.isArray(raw?.genres) ? raw.genres.filter((item: unknown) => !!item) : [],
    heat: Number(raw?.heat || 0),
    play_count: Number(raw?.play_count || 0),
    studio: String(raw?.studio || ''),
    kind: String(raw?.kind || ''),
    year: String(raw?.year || ''),
    release_date: String(raw?.release_date || ''),
  }
}

/**
 * 抓取作品墙的**一页**。
 *
 * 筛选、排序、分页全在后端做（真机 95 位演员 = 2256 部，全量拉到前端既慢又浪费），
 * 前端只管「拿一页 → 滚到底再拿下一页」。
 */
export async function fetchWorks(
  props: { api?: PluginApi },
  params: WorksQuery = {},
): Promise<WorksPayload> {
  const api = resolveApi(props)
  if (!api?.get) throw new Error('缺少可用的 api 实例')

  const query = new URLSearchParams()
  query.set('page', String(params.page && params.page > 0 ? params.page : 1))
  query.set('page_size', String(params.page_size && params.page_size > 0 ? params.page_size : 60))
  if (params.actor) query.set('actor', params.actor)
  if (params.genre) query.set('genre', params.genre)
  if (params.year) query.set('year', params.year)
  if (params.studio) query.set('studio', params.studio)
  if (params.sort) query.set('sort', params.sort)
  if (params.only_not_in_library) query.set('only_not_in_library', '1')
  if (params.keyword) query.set('keyword', params.keyword)

  const payload = unwrap<WorksPayload>(await api.get(`${API_BASE}/works?${query.toString()}`))
  const rows = Array.isArray(payload?.works) ? payload.works : []
  return {
    ...(payload || {}),
    works: rows.map(normalizeWork),
    actor_filters: Array.isArray(payload?.actor_filters) ? payload.actor_filters : [],
    facets: normalizeFacets(payload?.facets),
    total: Number(payload?.total || 0),
    page: Number(payload?.page || params.page || 1),
    page_size: Number(payload?.page_size || params.page_size || 60),
    has_more: Boolean(payload?.has_more),
    sort: String(payload?.sort || params.sort || 'heat'),
    new_window_days: payload?.new_window_days ?? 3,
    summary: payload?.summary ?? {
      total: 0,
      new: 0,
      library_known: 0,
      in_library: 0,
    },
  }
}

/** 插件状态（演员数 / 作品数 / 新作品数 / 最近刷新） */
export async function fetchStatus(props: { api?: PluginApi }): Promise<StatusPayload> {
  const api = resolveApi(props)
  if (!api?.get) throw new Error('缺少可用的 api 实例')
  return unwrap<StatusPayload>(await api.get(`${API_BASE}/status`))
}

/**
 * 在短剧百科里查演员。
 *
 * `enrich` 为真时后端会给前几位候选补演员档案（头像 / 作品数 / 简介）——
 * 「搜索演员」的卡片要头像，所以开；添加演员的候选列表只要名字，不用开。
 *
 * ⚠️ 百科的站外索引检索不便宜（真机见过 40 秒级），这里显式放宽超时，
 * 不吃宿主 axios 的默认超时（否则慢一点就被掐成「没找到」）。
 */
export async function searchActor(
  props: { api?: PluginApi },
  name: string,
  enrich = false,
): Promise<ActorSearchPayload> {
  const api = resolveApi(props)
  if (!api?.post) throw new Error('缺少可用的 api 实例')
  const payload = unwrap<ActorSearchPayload>(
    await api.post(`${API_BASE}/actors/search`, { name, enrich }, { timeout: 90_000 }),
  )
  return { ...payload, candidates: Array.isArray(payload?.candidates) ? payload.candidates : [] }
}

/**
 * 把作品搜索的返回行归一成作品卡的 WorkItem：身份与海报照搬，
 * 墙上才有的字段（演员 / 题材 / 热度…）给空值，key 加 `sw:` 前缀与墙上的行区分。
 */
function normalizeSearchWork(raw: any, index: number): WorkItem {
  return normalizeWork({
    key: `sw:${raw?.media_source || 'duanju'}:${raw?.media_id || index}`,
    title: String(raw?.title || ''),
    year: String(raw?.year || ''),
    type: '电视剧',
    media_source: String(raw?.media_source || 'duanju'),
    media_id: String(raw?.media_id || ''),
    poster: String(raw?.poster || ''),
    vote: Number(raw?.vote || 0),
    episode_count: 0,
    url: '',
    genres: [],
    heat: 0,
    play_count: 0,
    studio: '',
    kind: '',
    release_date: '',
    actor: '',
    actor_key: '',
    first_seen: '',
    is_new: false,
    overview: String(raw?.overview || ''),
  })
}

/**
 * 在短剧百科里按片名查作品（走宿主搜索同一条链路：run_module("search_medias")）。
 * 与 searchActor 同样放宽超时 —— 站内索引没召回时要现问搜索引擎。
 */
export async function searchWorks(
  props: { api?: PluginApi },
  name: string,
): Promise<WorkSearchPayload> {
  const api = resolveApi(props)
  if (!api?.post) throw new Error('缺少可用的 api 实例')
  const payload = unwrap<WorkSearchPayload>(
    await api.post(`${API_BASE}/works/search`, { name }, { timeout: 90_000 }),
  )
  const rows = Array.isArray(payload?.works) ? payload.works : []
  return { ...payload, works: rows.map(normalizeSearchWork) }
}

/** 添加演员（actor_id 有值时直接采用，否则后端按同名精确匹配） */
export async function addActor(
  props: { api?: PluginApi },
  name: string,
  actor_id = '',
): Promise<ApiResult> {
  const api = resolveApi(props)
  if (!api?.post) throw new Error('缺少可用的 api 实例')
  // 添加时会当场抓一轮该演员的全部作品（作品详情逐页补），几分钟都可能 —— 放宽超时
  return unwrap<ApiResult>(
    await api.post(`${API_BASE}/actors/add`, { name, actor_id }, { timeout: 180_000 }),
  )
}

/** 移除演员 */
export async function removeActor(props: { api?: PluginApi }, name: string): Promise<ApiResult> {
  const api = resolveApi(props)
  if (!api?.post) throw new Error('缺少可用的 api 实例')
  return unwrap<ApiResult>(await api.post(`${API_BASE}/actors/remove`, { name }))
}

/**
 * 某位演员的**全部**作品（百科实时，关注与否均可）—— 点演员卡片展开作品墙用。
 *
 * 后端现查短剧百科（每条作品都已补成作品页记录），比墙上的快照数据慢一截，
 * 放宽超时；失败由调用方降级成提示。
 */
export async function fetchActorWorks(
  props: { api?: PluginApi },
  actorId: string,
  name = '',
): Promise<WorksPayload> {
  const api = resolveApi(props)
  if (!api?.get) throw new Error('缺少可用的 api 实例')
  const query = new URLSearchParams()
  if (actorId) query.set('actor_id', actorId)
  if (name) query.set('name', name)
  return unwrap<WorksPayload>(
    await api.get(`${API_BASE}/actors/works?${query.toString()}`, { timeout: 120_000 }),
  )
}

/** 读取插件配置 */
export async function fetchConfig(props: { api?: PluginApi }): Promise<Partial<PluginConfig>> {
  const api = resolveApi(props)
  if (!api?.get) throw new Error('缺少可用的 api 实例')
  const payload = unwrap<any>(await api.get(`${API_BASE}/config`))
  return payload?.config || payload || {}
}

/** 保存插件配置 */
export async function saveConfig(
  props: { api?: PluginApi },
  config: Partial<PluginConfig>,
): Promise<ApiResult> {
  const api = resolveApi(props)
  if (!api?.put) throw new Error('缺少可用的 api 实例')
  return unwrap<ApiResult>(await api.put(`${API_BASE}/config`, config))
}

/**
 * 读取宿主订阅列表里「短剧百科来源」的条目，用于给卡片标「已订阅」。
 *
 * 宿主订阅接口返回的是列表信封 `{success, data:[...]}`（可能带分页），
 * 这里只取来源属于短剧百科的 `media_id`。取不到就返回空集合 ——
 * 标记只是锦上添花，不能因为读不到就让整面墙出不来。
 *
 * ⚠️ 来源要认两个值：``duanju`` 是百科插件身份定稿后的**规范标识**（现在新建的
 * 订阅都是它），``duanjubaike`` 是早期标识（**存量订阅**里还留着，百科插件的别名表
 * 也仍然认）。只认其中一个，都会漏掉一批订阅 —— 卡片上的「已订阅」会静默消失。
 */
const BAIKE_MEDIA_SOURCES = new Set(['duanju', 'duanjubaike'])

export async function fetchSubscribedIds(props: { api?: PluginApi }): Promise<Set<string>> {
  const ids = new Set<string>()
  const api = resolveApi(props)
  if (!api?.get) return ids
  try {
    const rows = unwrapList<any>(await api.get('subscribe/?page=1&count=200'))
    for (const row of rows) {
      if (!row) continue
      if (!BAIKE_MEDIA_SOURCES.has(String(row.media_source || ''))) continue
      if (row.media_id) ids.add(String(row.media_id))
    }
  } catch {
    // 忽略：订阅标记失败不影响作品墙
  }
  return ids
}
