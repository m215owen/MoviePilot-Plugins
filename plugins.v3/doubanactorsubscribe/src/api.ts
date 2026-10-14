/**
 * TMDB 演员订阅 —— 前端调用宿主与插件后端的公共工具。
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
 * 5. 宿主列表接口的分页参数有硬上限（`page` ≥ 1、`count` ≤ 200，二者越界都会
 *    返回 422「请求参数不正确」），因此读取订阅列表必须显式分页。
 */
import type {
  ActorGroup,
  ActorWork,
  ApiResult,
  PluginApi,
  SiteOption,
  DownloadClientOption,
  DownloadPathOption,
  WorksPayload,
} from './types'

/** 插件 ID，必须与后端插件类名一致 */
export const PLUGIN_ID = 'DoubanActorSubscribe'

/** 插件接口路径前缀（相对 baseURL `api/v1/`） */
export const API_BASE = `plugin/${PLUGIN_ID}`

/** 宿主原生订阅接口（相对 baseURL `api/v1/`） */
export const HOST_SUBSCRIBE = 'subscribe/'

/** 宿主站点列表接口（含各站点 cookie，前端只取 id/name，不做其他存储） */
export const HOST_SITES = 'site/rss'

/** 宿主下载目录接口 */
export const HOST_DOWNLOAD_PATHS = 'download/paths'

/**
 * 宿主已配置的下载器列表（形如 `[{name, type}]`）。
 *
 * 提交订阅时把 `name` 写进 `downloader` 字段，宿主就按它选择下载客户端；
 * 不填则由宿主按默认订阅配置补全。
 */
export const HOST_DOWNLOAD_CLIENTS = 'download/clients'

/**
 * MoviePilot 自带的「媒体详情」页路由。
 *
 * 就是「探索 / 推荐」里点进某部作品时打开的那个页面，宿主前端 `MediaDetailView`
 * 从 **query** 读取 `media_source` / `media_id` / `title` / `year` / `type`
 * （`type` 为中文的 电影 / 电视剧，缺它会直接显示空页面）。
 */
export const HOST_MEDIA_PAGE = '/media'

/** 宿主单次列表查询允许的最大条数（见后端 COLLECTION_MAX_PAGE_SIZE） */
const MAX_PAGE_SIZE = 200

/** 读取订阅列表时的每页条数；取上限的一半，留出余量避免宿主收紧上限 */
const SUBSCRIBE_PAGE_SIZE = 100

/** 订阅列表最多翻多少页，避免极端数据量下无限循环 */
const SUBSCRIBE_MAX_PAGES = 20

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

/**
 * 把图片地址转换为宿主图片代理地址。
 *
 * 海报地址由后端按宿主的 `TMDB_IMAGE_DOMAIN`（国内实例常为自建镜像）拼成完整 URL，
 * 这里再统一经宿主 `system/img` 代理取图：宿主侧带缓存、也能顺带处理镜像域名，
 * 比让浏览器直连上游图片域名更稳。
 *
 * 契约与宿主前端 `getDisplayImageUrl()` 完全一致（探索页走的就是这条路径）：
 * `/api/v1/system/img/0?imgurl=<urlencoded>&cache=true`
 * - `{proxy}` 取 **0**：不强制走用户配置的代理服务器（图片域名通常可直连），
 *   取 1 会把取图请求塞进用户的代理配置，代理异常时图片全挂。
 * - 接口鉴权走浏览器资源 Token Cookie，因此 `<img src>` 直接可访问；
 *   服务端用 apikey 调它一定 401，这是预期行为。
 */
export function proxyImage(url?: string | null): string {
  const raw = String(url || '').trim()
  if (!raw) return ''
  // 非 http(s) 地址（data:、相对路径）原样返回
  if (!/^https?:\/\//i.test(raw)) return raw
  // 已经是宿主代理地址时不再二次包装
  if (raw.includes('/system/img/')) return raw
  return `${apiPrefix()}system/img/0?imgurl=${encodeURIComponent(raw)}&cache=true`
}

/**
 * 组装 MoviePilot「媒体详情」页地址 —— 就是探索页里点进某部作品打开的那个页面。
 *
 * ⚠️ 宿主前端用的是 **hash 路由**（`createWebHashHistory`，base 形如 `./#`），
 * 所以绝不能直接拼 `/media?…`：那样只会落到站点根路径、由 SPA 兜底渲染成
 * 首页或登录页，看起来就是「点了没反应」。正确形态是 `<应用基址>#/media?…`。
 *
 * 应用基址取「当前文档地址去掉 `#` 之后的部分」：面板本身就跑在
 * `#/plugin-app/…` 之上，这样拼出来的地址天然带上实例的部署前缀，
 * 即使被反向代理到子路径下也不会拼错。
 *
 * @param work 至少要有 `media_id`；`title` / `year` 只是帮详情页省一次匹配，
 *             `type` 则是宿主详情页的硬性依赖（取值为中文的 电影 / 电视剧，
 *             缺失时页面会渲染成空壳，因此调用方应据此决定是否回退到 TMDB 条目页）
 * @returns 可直接放进 `<a href>` 的地址；缺少 `media_id` 时返回空串
 */
export function mediaPageUrl(work: {
  media_source?: string
  media_id?: string
  title?: string
  year?: string
  type?: string
}): string {
  const mediaId = String(work?.media_id ?? '').trim()
  if (!mediaId) return ''
  const params = new URLSearchParams()
  params.set('media_source', String(work?.media_source || '').trim() || 'themoviedb')
  params.set('media_id', mediaId)
  for (const key of ['title', 'year', 'type'] as const) {
    const value = String(work?.[key] ?? '').trim()
    if (value) params.set(key, value)
  }
  return `${appBaseUrl()}#${HOST_MEDIA_PAGE}?${params.toString()}`
}

/** 当前应用地址去掉 hash 的部分；非浏览器环境下退化为空串（相对地址）。 */
function appBaseUrl(): string {
  if (typeof window === 'undefined') return ''
  return window.location.href.split('#')[0]
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
 * 的对象会原样返回信封（对 `submitSubscribe` 这类要读 `success`/`message` 的场景是必须的），
 * 于是 `Array.isArray(信封)` 恒为假——这正是「下载保存路径 / 订阅站点下拉是空的」的原因。
 *
 * 这里对三种形状一并兜底：裸数组、`{data: [...]}` 信封、以及拦截器已解包的裸数组。
 */
export function unwrapList<T = unknown>(raw: unknown): T[] {
  const value = raw as unknown
  if (Array.isArray(value)) return value as T[]
  if (value && typeof value === 'object') {
    const inner = (value as { data?: unknown }).data
    if (Array.isArray(inner)) return inner as T[]
    // 少数版本会再套一层 axios response
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
 * 宿主不会为插件的动态路由套 `Response[T]`，因此插件接口的返回形状由插件自己决定：
 * 多数接口返回 `{success, data}`，但也有接口（历史原因）直接返回裸对象。
 * 这里把两种形状统一成 `{ok, data, message}`，避免把「成功」误判成失败——
 * 例如 `GET /config` 曾返回裸配置对象，前端按外壳取值会拿到 undefined。
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
  // 裸对象 / 裸数组：视为成功，数据就是返回体本身
  return { ok: true, data: (value ?? undefined) as T | undefined, message: '' }
}

/** 作品的订阅身份键，与后端 media_source:media_id 保持一致 */
export function workKey(work: ActorWork): string {
  return `${work.media_source}:${work.media_id}`
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

/** 订阅提交附加偏好：下载保存路径与订阅站点 */
export interface SubscribeExtras {
  /** 下载保存路径，空串表示跟随宿主默认配置 */
  savePath?: string
  /** 下载器名称，空串表示跟随宿主默认配置 */
  downloader?: string
  /** 订阅站点 ID 列表，空数组表示跟随宿主默认配置 */
  sites?: number[]
}

/** 订阅提交结果 */
export interface SubscribeOutcome {
  ok: boolean
  message: string
}

/**
 * 宿主在「影视未播出 / 信息尚未收录」时给出的拒绝原因关键词。
 *
 * 这些原因缺的是**季集信息**而不是作品本身有问题，因此可以降级成「预订」（待定），
 * 交给后端建一条占位订阅；其余失败（分类无效、网络异常等）照旧如实上报。
 */
const MISSING_INFO_HINTS = [
  '季集信息',
  '季的信息',
  '总集数',
  '集数信息',
  '未识别到媒体信息',
  '媒体信息识别失败',
]

/**
 * 判断订阅失败是否属于「影视信息还没到」（未播出 / 尚未收录）。
 *
 * 已知文案：「媒体信息中没有季集信息」「未获取到第 N 季的总集数」「未识别到媒体信息」
 * 「媒体信息识别失败」。最后用「季」「集」同现兜底，宿主换文案时不至于漏判。
 * 与后端 `_looks_like_missing_info` 保持同一套判定。
 */
export function isMissingInfoMessage(message: string): boolean {
  const text = String(message || '')
  if (MISSING_INFO_HINTS.some((hint) => text.includes(hint))) return true
  return text.includes('季') && text.includes('集')
}

/**
 * 把单个作品提交到 MoviePilot 订阅系统。
 *
 * 使用 TMDB 媒体身份（media_source=themoviedb + media_id）提交 —— 与宿主默认的识别源
 * 完全一致，命中准确且速度快；宿主侧会自动处理季号拆分、去重与用户归属。
 * `save_path` / `sites` 只在有值时提交，留空则沿用宿主自己的默认订阅配置。
 */
export async function submitSubscribe(
  api: PluginApi,
  work: ActorWork,
  extras: SubscribeExtras = {}
): Promise<SubscribeOutcome> {
  const payload: Record<string, unknown> = {
    name: work.title,
    year: work.year || '',
    media_source: work.media_source,
    media_id: work.media_id,
  }
  if (work.type) payload.type = work.type
  const savePath = String(extras.savePath || '').trim()
  if (savePath) payload.save_path = savePath
  const downloader = String(extras.downloader || '').trim()
  if (downloader) payload.downloader = downloader
  if (extras.sites && extras.sites.length) payload.sites = extras.sites
  try {
    const raw = await api.post(HOST_SUBSCRIBE, payload)
    const res = unwrap<{ success?: boolean; message?: string }>(raw)
    if (res && res.success === false) {
      const failure = res.message || '订阅失败'
      // 未播出 / 尚未收录的作品会因缺季集信息被宿主拒绝：这类不是「作品有问题」，
      // 而是「信息还没到」，改走插件侧「预订」（待定）兜底。
      if (isMissingInfoMessage(failure)) {
        const reserved = await reserveWork(api, work, extras)
        if (reserved.ok) return reserved
        return { ok: false, message: `${failure}（转为预订也失败：${reserved.message}）` }
      }
      return { ok: false, message: failure }
    }
    return { ok: true, message: res?.message || `已提交订阅：${work.title}` }
  } catch (err) {
    const message = extractError(err)
    if (isMissingInfoMessage(message)) {
      const reserved = await reserveWork(api, work, extras)
      if (reserved.ok) return reserved
    }
    return { ok: false, message }
  }
}

/**
 * 把作品转为「预订」（订阅状态置为待定 P）。
 *
 * 宿主为什么不能直接建：订阅链必须先补齐季集信息才肯落库，未播出 / TMDB 尚未收录的
 * 作品会被直接拒掉；而宿主公开接口又把 `state` 排除在可写字段之外，
 * 所以只能由插件侧按 TMDB 身份建占位订阅（待定 = 允许搜索、不允许完成）。
 */
export async function reserveWork(
  api: PluginApi,
  work: ActorWork,
  extras: SubscribeExtras = {}
): Promise<SubscribeOutcome> {
  try {
    const raw = await api.post(`${API_BASE}/reserve`, {
      title: work.title,
      year: work.year || '',
      type: work.type || '',
      media_source: work.media_source,
      media_id: work.media_id,
      poster: work.poster || '',
      subtitle: work.subtitle || '',
      vote: work.vote || 0,
      save_path: String(extras.savePath || '').trim(),
      downloader: String(extras.downloader || '').trim(),
      sites: extras.sites || [],
    })
    const res = unwrap<{ success?: boolean; message?: string }>(raw)
    if (res && res.success === false) {
      return { ok: false, message: res.message || '转为预订失败' }
    }
    return { ok: true, message: res?.message || `已按「预订」提交：${work.title}` }
  } catch (err) {
    return { ok: false, message: extractError(err) }
  }
}

/**
 * 取消一部作品在 MoviePilot 里的订阅。
 *
 * 面板上的订阅按钮在作品已订阅时会变成「取消订阅」，点它走的就是这里。
 * 宿主公开接口只能按 media_id + season 逐条删，而面板的粒度是「这部作品」，
 * 所以由插件后端按媒体身份找出订阅记录再删除。
 */
export async function unsubscribeWork(
  api: PluginApi,
  work: ActorWork
): Promise<SubscribeOutcome> {
  try {
    const raw = await api.post(`${API_BASE}/unsubscribe`, {
      media_source: work.media_source,
      media_id: work.media_id,
      title: work.title,
    })
    const res = unwrap<{ success?: boolean; message?: string }>(raw)
    if (res && res.success === false) {
      return { ok: false, message: res.message || '取消订阅失败' }
    }
    return { ok: true, message: res?.message || `已取消订阅「${work.title}」` }
  } catch (err) {
    return { ok: false, message: extractError(err) }
  }
}

/**
 * 忽略一部作品：面板不再展示它，自动订阅也会跳过。
 *
 * 忽略状态由后端持久化（键为 `media_source:media_id`），因此刷新后依然生效；
 * 数据不会从快照里删除，随时可以通过 `unignoreWork` 恢复。
 */
export async function ignoreWork(
  api: PluginApi,
  work: ActorWork
): Promise<SubscribeOutcome> {
  try {
    const raw = await api.post(`${API_BASE}/ignore`, {
      media_source: work.media_source,
      media_id: work.media_id,
      title: work.title,
      year: work.year,
      type: work.type,
    })
    const res = unwrap<{ success?: boolean; message?: string }>(raw)
    if (res && res.success === false) {
      return { ok: false, message: res.message || '忽略失败' }
    }
    return { ok: true, message: res?.message || `已忽略「${work.title}」` }
  } catch (err) {
    return { ok: false, message: extractError(err) }
  }
}

/** 恢复被忽略的作品；`all` 为真时清空整份忽略列表 */
export async function unignoreWork(
  api: PluginApi,
  key = '',
  all = false
): Promise<SubscribeOutcome> {
  try {
    const raw = await api.post(`${API_BASE}/unignore`, all ? { all: true } : { key })
    const res = unwrap<{ success?: boolean; message?: string }>(raw)
    if (res && res.success === false) {
      return { ok: false, message: res.message || '恢复失败' }
    }
    return { ok: true, message: res?.message || '已恢复' }
  } catch (err) {
    return { ok: false, message: extractError(err) }
  }
}

/**
 * 从订阅演员里移除一位（同步删除配置面板里的同名条目）。
 *
 * 面板的演员筛选 chip 上带删除按钮，点一下就能把这位演员从**配置的演员列表**里去掉，
 * 不必再跑回配置页手动删一行；后端会同步丢弃它的作品快照并安排一次补刷新。
 * 传的是配置里写的原始条目（`actor.key`），后端据此精确匹配。
 */
export async function removeActor(
  api: PluginApi,
  actor: ActorGroup
): Promise<SubscribeOutcome> {
  try {
    const raw = await api.post(`${API_BASE}/actor/remove`, {
      actor: actor.key,
      actor_id: actor.id || '',
      name: actor.name || '',
    })
    const res = unwrap<{ success?: boolean; message?: string }>(raw)
    if (res && res.success === false) {
      return { ok: false, message: res.message || '移除失败' }
    }
    const display = actor.name || actor.key
    return { ok: true, message: res?.message || `已移除演员「${display}」` }
  } catch (err) {
    return { ok: false, message: extractError(err) }
  }
}

/**
 * 读取宿主现有订阅的媒体身份集合，用于在面板上标记「已订阅」。
 *
 * 必须分页：宿主对 `count` 做了 `le=200` 校验，历史上直接请求 `count=500`
 * 会得到 422「请求参数不正确」，表现为「一进插件页面就报错」。
 */
export async function fetchSubscribedKeys(api: PluginApi): Promise<string[]> {
  const keys: string[] = []
  try {
    for (let page = 1; page <= SUBSCRIBE_MAX_PAGES; page += 1) {
      const raw = await api.get(HOST_SUBSCRIBE, {
        params: { page, count: SUBSCRIBE_PAGE_SIZE },
      })
      const list = unwrapList<Record<string, unknown>>(raw)
      if (!list.length) break
      for (const item of list) {
        const row = item as { media_source?: unknown; media_id?: unknown }
        if (row?.media_source && row?.media_id) {
          keys.push(`${row.media_source}:${row.media_id}`)
        }
      }
      if (list.length < SUBSCRIBE_PAGE_SIZE) break
    }
    return keys
  } catch (err) {
    // 读取失败只影响「已订阅」标记，不阻塞面板渲染
    console.warn(`[${PLUGIN_ID}] 读取已有订阅失败，已按 ${keys.length} 条处理`, err)
    return keys
  }
}

/**
 * 读取宿主可选的订阅站点列表。
 *
 * 宿主返回体包含站点凭据（cookie/apikey），这里只保留 `{id, name}` 并丢弃其余字段，
 * 避免敏感信息进入插件前端状态。仅保留启用中的站点。
 */
export async function fetchSiteOptions(api: PluginApi): Promise<SiteOption[]> {
  try {
    const raw = await api.get(HOST_SITES)
    const list = unwrapList<Record<string, unknown>>(raw)
    if (!list.length) return []
    const options: SiteOption[] = []
    for (const row of list) {
      if (row?.id == null) continue
      if (row.is_active === false) continue
      options.push({ id: Number(row.id), name: String(row.name || `站点 ${row.id}`) })
    }
    return options
  } catch (err) {
    console.warn(`[${PLUGIN_ID}] 读取站点列表失败`, err)
    return []
  }
}

/** 读取宿主可选的下载保存路径 */
export async function fetchPathOptions(api: PluginApi): Promise<DownloadPathOption[]> {
  try {
    const raw = await api.get(HOST_DOWNLOAD_PATHS)
    const list = unwrapList<Record<string, unknown>>(raw)
    if (!list.length) return []
    const options: DownloadPathOption[] = []
    const seen = new Set<string>()
    for (const row of list) {
      const path = String(row.save_path || row.download_path || '').trim()
      if (!path || seen.has(path)) continue
      seen.add(path)
      const name = String(row.name || '').trim()
      options.push({ name, path })
    }
    return options
  } catch (err) {
    console.warn(`[${PLUGIN_ID}] 读取下载目录失败`, err)
    return []
  }
}

/** 读取宿主已配置的下载器列表（`name` 即提交订阅时要写的 `downloader` 值） */
export async function fetchDownloaderOptions(api: PluginApi): Promise<DownloadClientOption[]> {
  try {
    const raw = await api.get(HOST_DOWNLOAD_CLIENTS)
    const list = unwrapList<Record<string, unknown>>(raw)
    if (!list.length) return []
    const options: DownloadClientOption[] = []
    const seen = new Set<string>()
    for (const row of list) {
      const name = String(row.name || '').trim()
      if (!name || seen.has(name)) continue
      seen.add(name)
      options.push({ name, type: String(row.type || '').trim() })
    }
    return options
  } catch (err) {
    console.warn(`[${PLUGIN_ID}] 读取下载器列表失败`, err)
    return []
  }
}

/** 宿主列表接口的 count 上限，暴露给需要自行分页的调用方 */
export const MAX_LIST_PAGE_SIZE = MAX_PAGE_SIZE

/**
 * 把所有演员的作品合并成一份去重的作品列表。
 *
 * 作品墙不再按演员分卡片：演员那一列的筛选 chip 已经承担了「按演员分类」的职责，
 * 重复展示会让列表变得极长。同一部作品出现在多位演员名下时只保留一条，
 * 并把演员名聚合进 `actorNames`，这样信息不丢失、列表也不会重复膨胀。
 */
export function mergeWorks(actors: ActorGroup[]): ActorWork[] {
  const merged = new Map<string, ActorWork>()
  for (const actor of actors) {
    const names = actorDisplayNames(actor)
    for (const work of actor.works || []) {
      const key = workKey(work)
      const existing = merged.get(key)
      if (!existing) {
        merged.set(key, {
          ...work,
          roles: [...(work.roles || [])],
          actorNames: [...names],
        })
        continue
      }
      const missing = names.filter((name) => !(existing.actorNames || []).includes(name))
      if (missing.length) {
        existing.actorNames = [...(existing.actorNames || []), ...missing]
      }
      // 任一演员把它视为新作品，就按新作品呈现
      if (work.is_new) existing.is_new = true
      const extraRoles = (work.roles || []).filter(
        (item) => !(existing.roles || []).includes(item)
      )
      if (extraRoles.length) existing.roles = [...(existing.roles || []), ...extraRoles]
    }
  }
  return Array.from(merged.values())
}

/**
 * 演员在作品墙上可被搜到的名字。
 *
 * 模糊匹配（TMDB 没有同名演员，插件退回了最接近的结果）时，配置名与 TMDB 名不一致：
 * 只放出 TMDB 名的话，用户按自己填的名字搜作品会一条都搜不到。两个都带上。
 */
function actorDisplayNames(actor: ActorGroup): string[] {
  const name = String(actor.name || '').trim()
  const key = String(actor.key || '').trim()
  const names = name ? [name] : []
  if (key && key !== name) names.push(key)
  return names
}

/** 作品默认排序：新作品优先，其次按年份倒序 */
export function sortWorks(works: ActorWork[], mode = 'year'): ActorWork[] {
  return [...works].sort((a, b) => {
    if (mode === 'new') {
      const flag = Number(Boolean(b.is_new)) - Number(Boolean(a.is_new))
      if (flag) return flag
    }
    return (Number(b.year) || 0) - (Number(a.year) || 0)
  })
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

/**
 * 等待后端刷新结束。
 *
 * 两种情况都要等：保存配置时后端会安排一次延迟补刷新（`pending_refresh`），
 * 手动刷新则改成了后台任务（`refreshing`）——演员多时一次刷新要跑几百个请求，
 * 放在 HTTP 请求里同步执行必然超时。这里轮询到两个标记都消失为止。
 */
export function waitForRefresh(
  api: PluginApi,
  apply: (payload: WorksPayload) => void,
  tries = 72,
  intervalMs = 2500
): void {
  const tick = async (): Promise<void> => {
    for (let index = 0; index < tries; index += 1) {
      await new Promise((resolve) => window.setTimeout(resolve, intervalMs))
      try {
        const res = unwrap<ApiResult<WorksPayload>>(await api.get(`${API_BASE}/works`))
        if (res?.success && res.data) {
          apply(res.data)
          if (!res.data.pending_refresh && !res.data.refreshing) return
        }
      } catch (err) {
        // 单次失败不影响继续轮询
        console.debug(`[${PLUGIN_ID}] 等待刷新完成时读取失败`, err)
      }
    }
  }
  void tick()
}
