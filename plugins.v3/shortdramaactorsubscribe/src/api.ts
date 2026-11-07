/**
 * 短剧演员订阅 —— 前端调用宿主与插件后端的公共工具。
 *
 * 重要约定：
 * 1. 优先使用宿主传入的 `api` prop（实例作用域，适配插件虚拟分身）；
 *    仅在 prop 缺失时才回退全局 `window.MoviePilotAPI`。
 * 2. 宿主 axios 的 baseURL 已是 `api/v1/`，因此插件内路径写
 *    `plugin/<PluginID>/<path>`，绝不能写成 `api/v1/plugin/...`（会变成双前缀 404）。
 * 3. **插件后端统一三段式信封**（`{success, message, data}`，见 `api_models`）：业务对象一律
 *    在 `data` 里，统一由 `readData()` 拆封；组件只消费拆封后的业务模型。
 * 4. **订阅走宿主系统**：卡片上的「订阅」调宿主注入的 `nativeSubscribe`，
 *    插件后端不参与订阅；这里只需要读一次 `subscribe/` 用来标「已订阅」。
 */
import type {
  ActorCandidate,
  ActorCardItem,
  ActorDetailPayload,
  ActorMutationPayload,
  ActorSearchPayload,
  ActorSubscribeAllPayload,
  ActorItem,
  DownloadClientOption,
  DownloadPathOption,
  FacetItem,
  LogsPayload,
  PeopleListPayload,
  PluginApi,
  PluginConfig,
  RankWorksPayload,
  RanksPayload,
  StatusPayload,
  WorkDetailPayload,
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

/** 宿主「下载客户端」列表接口（订阅下载器的选项来源） */
export const HOST_DOWNLOAD_CLIENTS = 'download/clients'

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
 * 给图片代理地址追加一个「第几次重试」标记（不改原始图片地址）。
 *
 * 宿主 `system/img` 代理带 SSRF 防护，**逐张**做 DNS 校验；作品墙一屏几十张同时到达时，
 * 解析偶发瞬时失败（宿主日志 `Blocked unsafe image URL ... reason=dns_resolution_failed`），
 * 表现就是个别海报空白。这类失败隔一会儿重试通常就好了 —— 加一个不同的查询参数
 * 让浏览器 / 代理重新发起请求（成功一次后代理会按 `cache=true` 落盘，不再解析 DNS）。
 */
export function retryProxyImage(url: string, attempt: number): string {
  if (!url || attempt <= 0) return url
  return `${url}${url.includes('?') ? '&' : '?'}retry=${attempt}`
}

/**
 * 走宿主 `system/img` 代理的地址（不管域名，强制走代理）。
 *
 * 契约与宿主前端一致：`system/img/0?imgurl=<urlencoded>&cache=true`
 * （`cache=true` 时宿主会落磁盘，第二次起不再回源）。
 */
export function proxiedImage(url?: string | null): string {
  const raw = String(url || '').trim()
  if (!raw) return ''
  if (!/^https?:\/\//i.test(raw)) return raw
  if (raw.includes('/system/img/')) return raw
  return `${apiPrefix()}system/img/0?imgurl=${encodeURIComponent(raw)}&cache=true`
}

/**
 * 可以直接连的图床。
 *
 * 2026-11-04 曾把 `cdn.duanjubaike.org` 放进来做「直连优先」（Cloudflare 一年强缓存，
 * 直连省一遍代理往返），**次日实测翻车**：用户浏览器直连该 CDN 失败（NAS 侧 curl 正常，
 * 浏览器侧过不去 —— 大概率是上网分流规则没放行），org 来源的作品海报与演员头像整墙
 * 空白，且卡片重试阶梯退回代理 URL 时可能撞上浏览器 7 天强缓存的旧坏响应，雪上加霜。
 * 现在清空：**所有外域图统一走宿主 `system/img` 代理**（服务端直连 CDN 是通的，
 * 代理链路今早日志全 200），直连只保留为卡片重试阶梯里的备选链路。
 */
const DIRECT_IMAGE_HOSTS: string[] = []

/**
 * 图片地址 → 实际用的 `src`（一律走宿主代理；`DIRECT_IMAGE_HOSTS` 为空保留机制）。
 *
 * 其它域名按老口径经宿主代理（跨域防盗链在那边是真实存在的；服务端直连
 * 图床没问题，用户浏览器直连不一定通 —— 2026-11-04 的教训）。
 */
export function proxyImage(url?: string | null): string {
  const raw = String(url || '').trim()
  if (!raw) return ''
  if (!/^https?:\/\//i.test(raw)) return raw
  if (raw.includes('/system/img/')) return raw
  if (DIRECT_IMAGE_HOSTS.some((host) => raw.includes(`//${host}/`))) return raw
  return proxiedImage(raw)
}

/**
 * 组装宿主的「资源搜索」页地址（hash 路由），卡片上的搜索按钮用。
 *
 * **为什么改成「不带媒体身份、不带 type」的标题搜索（2026-10-22）**
 *
 * 原来照宿主 MediaCard 的口径带 `media_source` + `media_id` + `type=电视剧`，
 * 宿主资源页拿到身份就走**精确搜索**，而精确搜索会按媒体类型拼站点分类参数：
 * 电视剧 → `cat402/403/404/405`（站点侧分类过滤），一个分类都不多带。
 *
 * 短剧在各站分类极不统一 —— 实测 PTS（拾刻）把《为所欲为（80集）何田田&王轩等 - SKIT》
 * 放在 **Movies/电影（cat401）**，于是「电视剧」视角下站点根本不返回这条：
 * 同一关键词 `mtype=电视剧` 0 条，不带 mtype（= 全部分类）4 条且第一条就是它。
 * 宿主在 type 为空时，前端请求**不传 mtype**（`...e.type?{mtype:e.type}:{}`），
 * 站点就把电影 / 电视剧 / 短剧 / 动漫一起搜 —— 也就是「电视剧 + 电影」。
 *
 * 代价：不再带媒体身份，下载历史里不会有 `media_source/media_id`（靠片名识别整理）。
 * 副作用是搜索结果**更全**：分类放错的短剧也能被搜到。
 *
 * 用户在站点弹窗里选了站点时，额外带 `sites=<id,..>`（宿主资源页只搜这些站点）。
 */
export function resourceSearchUrl(work: WorkItem, sites?: number[]): string {
  const query = new URLSearchParams()
  // 关键词搜索：宿主只在没有媒体身份时才走 `search/title`（全分类）
  query.set('keyword', work.title)
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
  const rows = unwrapList<HostSite>(await api.get('site/media/tv', { ...SILENT }))
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
    const rows = unwrapList<Record<string, unknown>>(
      await api.get(HOST_DOWNLOAD_CLIENTS, { ...SILENT }),
    )
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

/**
 * 读取宿主的「下载目录」列表（订阅下载目录的选项来源）。
 *
 * 端点 `download/paths` 返回 `{name, storage, download_path, save_path}`。
 * 宿主的 save_path 校验要求**精确匹配**某个下载目录根（`DirectoryHelper.
 * get_download_dir_by_save_path`），所以配置里存它比手输路径可靠 —— 手输的子目录
 * 不会当成目录根，分类规则也就落不上。读不到返回空列表（配置页退化成手输）。
 */
export async function fetchDownloadPaths(
  props: { api?: PluginApi },
): Promise<DownloadPathOption[]> {
  const api = resolveApi(props)
  if (!api?.get) return []
  try {
    const rows = unwrapList<Record<string, unknown>>(
      await api.get('download/paths', { ...SILENT }),
    )
    const options: DownloadPathOption[] = []
    const seen = new Set<string>()
    for (const row of Array.isArray(rows) ? rows : []) {
      const savePath = String(row?.save_path || row?.download_path || '').trim()
      if (!savePath || seen.has(savePath)) continue
      seen.add(savePath)
      options.push({
        name: String(row?.name || '').trim() || savePath,
        storage: String(row?.storage || 'local').trim(),
        download_path: String(row?.download_path || '').trim(),
        save_path: savePath,
      })
    }
    return options
  } catch (err) {
    console.warn(`[${PLUGIN_ID}] 读取下载目录失败`, err)
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

/** 一条订阅（作品墙左侧「订阅作品」面板的行）。 */
export interface SubscriptionRow {
  media_id: string
  title: string
  year: string
  actor: string
  /** 海报（面板用作品墙同款海报卡展示） */
  poster?: string
  /** 在库三态（探针现查）：true 已入库 / false 未入库 / null 未知（探针不可用） */
  in_library?: boolean | null
  /** 订阅搜索状态（downloaded / noresult / failed / in_library / history；空 = 未处理） */
  sub_state: string
  sub_detail: string
  sub_time: string
  /** 台账记下的种子页面（下载成功才有）：详情页给一枚「种子页面」按钮 */
  torrent_url?: string
  /** 台账记下的种子标题 */
  torrent_title?: string
  /** 订阅级落点覆写：空串 = 用配置页默认 */
  sites?: string
  downloader?: string
  save_path?: string
  /** 身份属于哪一站（org / net；空 = 融合身份或数据源没给站点画像） */
  site?: string
  /** 旧站点身份（数据源换过站、这条还没换过来）：前端拿标题做「同名桥」 */
  stale?: boolean
  /** 这一行是否已订阅（能出现在订阅清单里就是 true；与作品行同名字段对齐） */
  subscribed?: boolean
}

/**
 * 拉当前订阅清单（作品墙左侧「订阅作品」面板的数据源）。
 *
 * 与后端 ``/subscriptions`` 同口径：插件订阅清单 ∪ 宿主 未暂停订阅。
 * 失败返回空列表（面板不出就行，不打扰作品墙）。``site`` 是数据源当前站点，
 * ``stale_count`` 是「还挂在别的站点身份上」的条数（换过站还没换过来的）。
 */export async function fetchSubscriptions(
  props: { api?: PluginApi },
): Promise<{
  items: SubscriptionRow[]
  site: string
  stale_count: number
  default_sites: string
  default_downloader: string
  default_save_path: string
  /**
   * 这次请求**成功与否**（``false`` = 网络/宿主/解析失败，``items`` 只是空壳）。
   *
   * 必须与「真的 0 条订阅」区分开：调用方拿空壳去覆盖本地订阅集合，就会把整面墙
   * 已订阅的卡片刷成「未订阅」（2026-11-02 真机反馈）。
   */
  ok: boolean
}> {
  const empty = {
    items: [] as SubscriptionRow[],
    site: '',
    stale_count: 0,
    default_sites: '',
    default_downloader: '',
    default_save_path: '',
    ok: false,
  }
  const api = resolveApi(props)
  if (!api?.get) return empty
  try {
    const data = readData<{
      items?: SubscriptionRow[]
      site?: string
      stale_count?: number
      default_sites?: string
      default_downloader?: string
      default_save_path?: string
    }>(await api.get(`${API_BASE}/subscriptions`, { ...SILENT }))
    return {
      items: Array.isArray(data?.items) ? data.items : [],
      site: String(data?.site || ''),
      stale_count: Number(data?.stale_count || 0),
      default_sites: String(data?.default_sites || ''),
      default_downloader: String(data?.default_downloader || ''),
      default_save_path: String(data?.default_save_path || ''),
      ok: true,
    }
  } catch {
    return empty
  }
}

/** 订阅身份的轻量快照（``GET /subscribed_ids``） */
export interface SubscribedIdsPayload {
  /** 订阅清单里的全部身份（当前站 + 别的站旧身份） */
  ids: string[]
  /** 数据源当前站点（空 = 没有站点画像） */
  site: string
  /** 「身份属于别的站点」那些订阅的剧名（换过站：ID 对不上、名字对得上） */
  stale_titles: string[]
  count: number
  /** 已关注演员的身份（`actor:12` 这种），搜索结果里的演员卡据此点亮红心 */
  actor_ids: string[]
}

/**
 * 拉订阅身份的**轻量快照** —— 作品卡判「已订阅 / 未订阅」用。
 *
 * 为什么不复用 ``fetchSubscriptions``：那份是完整订阅清单（含台账、在库判定、
 * 上百条 → 上百 KB）。作品卡只需要一串 ID，为它拉全量，一旦那次请求失败或
 * 解析失败就会**静默**变成空集合，整屏「已订阅」全被画成「未订阅」（2026-11-02
 * 真机反馈）。这里只要 ID + 换站前的同名桥。
 *
 * 失败返回空快照（调用方退回列表行自带的 ``subscribed`` 字段）。
 */
export async function fetchSubscribedIds(
  props: { api?: PluginApi },
): Promise<SubscribedIdsPayload> {
  const empty: SubscribedIdsPayload = {
    ids: [],
    site: '',
    stale_titles: [],
    count: 0,
    actor_ids: [],
  }
  const api = resolveApi(props)
  if (!api?.get) return empty
  try {
    const data = readData<Partial<SubscribedIdsPayload>>(
      await api.get(`${API_BASE}/subscribed_ids`, { ...SILENT }),
    )
    return {
      ids: Array.isArray(data?.ids) ? data.ids.map((item) => String(item || '')) : [],
      site: String(data?.site || ''),
      stale_titles: Array.isArray(data?.stale_titles)
        ? data.stale_titles.map((item) => String(item || ''))
        : [],
      count: Number(data?.count || 0),
      actor_ids: Array.isArray(data?.actor_ids)
        ? data.actor_ids.map((item) => String(item || ''))
        : [],
    }
  } catch {
    return empty
  }
}


/**
 * 订阅一部作品（**插件统一入口**）。
 *
 * 只有一条链路：记进**插件订阅清单**，等订阅搜索自动下载（宿主订阅 2026-11-02
 * 起完全去除）。返回宿主风格 ``{ success, message }``，调用方照实提示。
 */
export async function pluginSubscribe(
  props: { api?: PluginApi },
  work: {
    title: string
    year?: string
    media_source?: string
    media_id: string
    actor?: string
    poster?: string
  },
): Promise<{ success?: boolean; message?: string }> {
  const api = resolveApi(props)
  if (!api?.post) throw new Error('缺少可用的 api 实例')
  return unwrap<{ success?: boolean; message?: string }>(
    await api.post(
      `${API_BASE}/subscribe`,
      {
        title: String(work.title || ''),
        year: String(work.year || ''),
        media_source: String(work.media_source || 'djbaike'),
        media_id: String(work.media_id || ''),
        actor: String(work.actor || ''),
        poster: String(work.poster || ''),
      },
      { ...SILENT },
    ),
  )
}

/** 取消一部作品的订阅（插件订阅清单 + 宿主 订阅一起清，后端幂等）。 */
export async function pluginUnsubscribe(
  props: { api?: PluginApi },
  mediaId: string,
  title = '',
): Promise<{ success?: boolean; message?: string }> {
  const api = resolveApi(props)
  if (!api?.post) throw new Error('缺少可用的 api 实例')
  const body: Record<string, string> = { media_id: String(mediaId || '') }
  // title 只在换过站时有意义：卡上是新身份、清单里是旧身份，后端按同名找那条旧记录
  if (title) body.title = String(title)
  return unwrap<{ success?: boolean; message?: string }>(
    await api.post(`${API_BASE}/unsubscribe`, body, { ...SILENT }),
  )
}

/**
 * 编辑一条订阅的配置（作品详情页「订阅设置」）：只有落点三项 ——
 * 站点 / 下载器 / 保存目录。订阅没有暂停位（2026-10-23 用户口径）。
 */
export async function pluginSubscribeUpdate(
  props: { api?: PluginApi },
  mediaId: string,
  targets: { sites?: string; downloader?: string; save_path?: string },
): Promise<{ success?: boolean; message?: string }> {
  const api = resolveApi(props)
  if (!api?.post) throw new Error('缺少可用的 api 实例')
  // 只带**要改**的字段：后端按「键在不在请求里」判断哪一项要动
  const payload: Record<string, unknown> = { media_id: String(mediaId || '') }
  if (targets) {
    if (targets.sites !== undefined) payload.sites = targets.sites
    if (targets.downloader !== undefined) payload.downloader = targets.downloader
    if (targets.save_path !== undefined) payload.save_path = targets.save_path
  }
  return unwrap<{ success?: boolean; message?: string }>(
    await api.post(`${API_BASE}/subscribe/update`, payload, { ...SILENT }),
  )
}

/**
 * 对一部订阅**立即搜索一次**（不等下一轮定时）：后端清掉冷却记录后开后台
 * 线程跑一轮，结果写回台账 ——「订阅设置」里刷新一下就能看到。
 */
export async function pluginSubscribeSearchNow(
  props: { api?: PluginApi },
  mediaId: string,
): Promise<{ success?: boolean; message?: string }> {
  const api = resolveApi(props)
  if (!api?.post) throw new Error('缺少可用的 api 实例')
  return unwrap<{ success?: boolean; message?: string }>(
    await api.post(
      `${API_BASE}/subscribe/search_now`,
      { media_id: String(mediaId || '') },
      { ...SILENT },
    ),
  )
}

/** 随机订阅命中的作品（`/subscribe/random` 的 data.items 元素） */
export interface RandomSubscribeWork {
  media_id: string
  title: string
  year: string
  actor: string
  poster: string
}

/**
 * 随机订阅（2026-10-23 用户口径）：从作品墙全集随机挑 `count` 部**未订阅且
 * 未入库**的作品订阅；候选不足时后端自动少订。返回命中的清单用于提示。
 */
export async function pluginSubscribeRandom(
  props: { api?: PluginApi },
  count: number,
): Promise<{ success?: boolean; message?: string; data?: { requested: number; items: RandomSubscribeWork[] } }> {
  const api = resolveApi(props)
  if (!api?.post) throw new Error('缺少可用的 api 实例')
  return unwrap<{
    success?: boolean
    message?: string
    data?: { requested: number; items: RandomSubscribeWork[] }
  }>(
    await api.post(
      `${API_BASE}/subscribe/random`,
      { count: Math.max(1, Math.min(10, Math.floor(count) || 1)) },
      { ...SILENT },
    ),
  )
}

/**
 * 立即对**全部订阅作品**跑一轮订阅搜索（不等下一轮定时）：后端顺手清掉
 * 「暂无资源 / 搜索失败」的冷却；已入库 / 已下载 / 历史已有照旧跳过。
 */
export async function pluginSubscribeSearchAll(
  props: { api?: PluginApi },
): Promise<{ success?: boolean; message?: string }> {
  const api = resolveApi(props)
  if (!api?.post) throw new Error('缺少可用的 api 实例')
  return unwrap<{ success?: boolean; message?: string }>(
    await api.post(`${API_BASE}/subscribe/search_all`, {}, { ...SILENT }),
  )
}

/**
 * 传给宿主注入客户端的附加配置：**错误提示由本插件自己负责**。
 *
 * 宿主客户端默认会对 HTTP 错误和 ``success=false`` 弹一次错误 Toast（API 专题 §5.2），
 * 而本插件每个调用点都有按语境给的提示（或空态），所以统一 ``feedback: 'silent'``
 * 关掉宿主那一层，避免同一次失败弹两条。
 */
const SILENT = { feedback: 'silent' } as const

/**
 * 是否为「套了一层 axios response」的形态。
 *
 * 判据**只认 axios response 特征**（``status`` 是数字 + ``statusText`` 是字符串 +
 * ``headers`` 是对象），绝不能只看有没有 ``data`` 字段 —— 后端载荷顶层也可能叫 ``data``
 * （本插件的信封就是 ``{success, message, data}``），那样会被误当响应体再解包一层，
 * 表现为界面永远空白。V3 宿主注入的客户端已经把最终 payload 交给调用方，这里只是为了
 * 兼容个别仍套一层的版本。
 */
function isAxiosResponse(value: any): boolean {
  if (!value || typeof value !== 'object') return false
  return (
    typeof value.status === 'number' &&
    typeof value.statusText === 'string' &&
    typeof value.headers === 'object' &&
    value.headers !== null &&
    'data' in value
  )
}

/** 归一化响应体：只解 axios 外壳，其它形态原样返回 */
function unwrap<T = any>(response: any): T {
  if (isAxiosResponse(response)) return response.data as T
  return response as T
}

/**
 * 读插件端点的**三段式信封**，返回其中的 ``data``。
 *
 * 插件所有普通 JSON 端点都返回宿主统一 envelope（顶层只有 success / message / data，
 * 业务对象一律在 ``data`` 里，见 ``api_models``）。这里统一处理两件事：
 *
 * - ``success === false``：调用完成但业务被拒（例如「已经在关注列表里」）⇒ 抛错给调用方提示；
 * - HTTP 4xx/5xx（参数错 / 上游故障）：宿主客户端已抛异常，这里原样向上冒泡。
 */
function readData<T>(response: any): T {
  const payload = unwrap<any>(response)
  if (payload && typeof payload === 'object' && payload.success === false) {
    throw new Error(String(payload.message || '操作失败'))
  }
  return (payload?.data ?? null) as T
}

/** 归一化列表响应：宿主普通 JSON 端点同样是三段式信封（列表在 ``data`` 里） */
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
    platforms: normalizeFacetList(raw?.platforms),
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
    // 播放平台：作品卡目前不带（平台只在详情页 meta 里），恒空 ⇒ 墙上的平台筛选行自动隐藏。
    // 数据源哪天在卡片层补上，这里不用改，直接就有值。
    platform: String(raw?.platform || ''),
    kind: String(raw?.kind || ''),
    year: String(raw?.year || ''),
    release_date: String(raw?.release_date || ''),
    // 状态角标（爆火 / 新剧 / 完结 / 预约…）：后端已经给了就直接透传，
    // 旧快照（这个字段还没有时）统一补空数组，卡片据此不渲染任何标签
    badges: Array.isArray(raw?.badges) ? raw.badges.filter((item: unknown) => !!item) : [],
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
  if (params.platform) query.set('platform', params.platform)
  if (params.sort) query.set('sort', params.sort)
  if (params.only_new) query.set('only_new', '1')
  if (params.only_not_in_library) query.set('only_not_in_library', '1')
  if (params.only_not_subscribed) query.set('only_not_subscribed', '1')
  if (params.keyword) query.set('keyword', params.keyword)

  const payload = readData<WorksPayload>(
    await api.get(`${API_BASE}/works?${query.toString()}`, { ...SILENT }),
  )
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
    sort: String(payload?.sort || params.sort || 'date'),
    summary: payload?.summary ?? {
      total: 0,
      new: 0,
      library_known: 0,
      in_library: 0,
    },
  }
}

/**
 * `POST /works/refresh_library`：清空后端在库判定缓存，并让宿主同步一次媒体库。
 *
 * 在库结论带 600 秒 TTL，刚入库的剧在缓存过期前一直显示「未入库」；而宿主的本地库表
 * 只有 6 小时一次的同步在灌，刚入库的剧表里压根没有 —— 光清缓存重判也是「未入库」。
 * 所以后端顺手踢一次宿主同步、几十秒后再清一遍缓存。把后端的提示原样返回给调用方，
 * 让按钮的 toast 说清楚「正在同步、稍等」。
 */
export async function refreshLibraryStatus(props: { api?: PluginApi }): Promise<string> {
  const api = resolveApi(props)
  if (!api?.post) throw new Error('缺少可用的 api 实例')
  const response = await api.post(`${API_BASE}/works/refresh_library`, {}, { ...SILENT })
  readData(response)
  const message = (unwrap<any>(response) as { message?: unknown } | null)?.message
  return typeof message === 'string' ? message : ''
}

/**
 * `POST /refresh`：立即刷新全部演员的作品快照。
 *
 * `clearCache` = 顺手把**数据源的缓存**先清掉：快照刷新走数据源的 get_person，
 * 那层带 24h 统一缓存 —— 不清的话 force 刷新命中的还是旧行（2026-11-04 实证：
 * 数据源作品卡加了角标字段后，只刷快照墙上死活不显示）。全量强刷 100+ 位演员
 * 要几分钟，timeout 给足 10 分钟。
 */
export async function refreshWorks(props: { api?: PluginApi }): Promise<string> {
  const api = resolveApi(props)
  if (!api?.post) throw new Error('缺少可用的 api 实例')
  const response = await api.post(
    `${API_BASE}/refresh?clear_cache=1`,
    {},
    { ...SILENT, timeout: 600_000 },
  )
  readData(response)
  const message = (unwrap<any>(response) as { message?: unknown } | null)?.message
  return typeof message === 'string' ? message : ''
}

/** 插件状态（演员数 / 作品数 / 新作品数 / 最近刷新） */
export async function fetchStatus(props: { api?: PluginApi }): Promise<StatusPayload> {
  const api = resolveApi(props)
  if (!api?.get) throw new Error('缺少可用的 api 实例')
  return readData<StatusPayload>(await api.get(`${API_BASE}/status`, { ...SILENT }))
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
  const payload = readData<ActorSearchPayload>(
    await api.post(`${API_BASE}/actors/search`, { name, enrich }, { ...SILENT, timeout: 90_000 }),
  )
  return { ...payload, candidates: Array.isArray(payload?.candidates) ? payload.candidates : [] }
}

/**
 * 把作品搜索的返回行归一成作品卡的 WorkItem：身份与海报照搬，
 * 墙上才有的字段（演员 / 题材 / 热度…）给空值，key 加 `sw:` 前缀与墙上的行区分。
 */
function normalizeSearchWork(raw: any, index: number): WorkItem {
  return normalizeWork({
    key: `sw:${raw?.media_source || 'djbaike'}:${raw?.media_id || index}`,
    title: String(raw?.title || ''),
    year: String(raw?.year || ''),
    type: '电视剧',
    media_source: String(raw?.media_source || 'djbaike'),
    media_id: String(raw?.media_id || ''),
    poster: String(raw?.poster || ''),
    vote: Number(raw?.vote || 0),
    episode_count: 0,
    url: '',
    genres: [],
    heat: 0,
    play_count: 0,
    studio: '',
    platform: '',
    kind: '',
    release_date: '',
    actor: '',
    actor_key: '',
    first_seen: '',
    is_new: false,
    overview: String(raw?.overview || ''),
    // 站点搜索结果卡同样带角标（爆火 / 新剧）：有就印，没有就不印
    badges: Array.isArray(raw?.badges) ? raw.badges.filter((item: unknown) => !!item) : [],
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
  const payload = readData<WorkSearchPayload>(
    await api.post(`${API_BASE}/works/search`, { name }, { ...SILENT, timeout: 90_000 }),
  )
  const rows = Array.isArray(payload?.works) ? payload.works : []
  return { ...payload, works: rows.map(normalizeSearchWork) }
}

/**
 * 数据源检索（`/lookup`）的结果：作品 + 演员，**站点优先、本地库兜底**。
 *
 * 这是短剧百科**自己那一套**搜索：打站内搜索，同名多季 / 同名不同副标题会全部列出来
 * （`search_medias` 那种「片名精确匹配」做不到），站点 0 条时才退回本地库。
 * 所以面板的搜索框直接用它 —— 与在数据源面板里检索得到的结果一致。
 */
export interface SiteLookupResult {
  works: WorkItem[]
  actors: ActorCandidate[]
  /** `site` = 站点命中 / `library` = 站点 0 条、退回本地库 / 空串 = 不知道 */
  source: string
  /**
   * 订阅身份的轻量快照（随检索一并取回）：命中的作品行已经就地带上
   * `subscribed = true`，调用方再把 `ids` / `stale_titles` 并进自己的集合，
   * 卡片后续刷新也不会退回「未订阅」。
   */
  subscribed_ids?: string[]
  stale_titles?: string[]
}

/**
 * 检索返回的作品行 → 作品卡。
 *
 * 2026-10-22 换源：数据源 `/lookup` 回的是 schemas MediaInfo
 * （`poster_path` / `vote_average` / `number_of_episodes` / `detail_link`）。
 */
function normalizeLookupWork(raw: any, index: number): WorkItem {
  const mediaId = String(raw?.media_id || '')
  const release = String(raw?.release_date || '')
  return normalizeWork({
    key: `sw:${mediaId || index}`,
    title: String(raw?.title || ''),
    year: release.slice(0, 4) || String(raw?.year || '').slice(0, 4),
    type: '电视剧',
    media_source: 'djbaike',
    media_id: mediaId,
    poster: String(raw?.poster_path || raw?.poster || ''),
    vote: Number(raw?.vote_average || raw?.rating || 0),
    episode_count: Number(raw?.number_of_episodes || raw?.episodes || 0),
    url: String(raw?.detail_link || raw?.url || ''),
    genres: (Array.isArray(raw?.genres) ? raw.genres : [])
      .map((item: any) => String(item?.name ?? item ?? '').trim())
      .filter(Boolean),
    heat: Number(raw?.heat || 0),
    play_count: Number(raw?.play_count || 0),
    studio: '',
    platform: String(raw?.platform || ''),
    kind: '',
    release_date: release,
    actor: '',
    actor_key: '',
    first_seen: '',
    is_new: false,
  })
}

/** 检索返回的演员行 → 演员卡（站内检索自带头像 / 作品数 / 职业 / 性别，直接透传） */
function normalizeLookupActor(raw: any): ActorCandidate {
  const mediaId = String(raw?.media_id || raw?.actor_id || '')
  return {
    name: String(raw?.title || raw?.name || '').trim(),
    actor_id: mediaId,
    media_id: mediaId,
    // 站内搜索的结果未必与输入完全同名（可能是同名不同人），交给卡片让用户判断
    exact: false,
    profile: String(raw?.poster_path || raw?.poster || '').trim() || undefined,
    works_count: Number(raw?.works_count || 0),
    job_title: String(raw?.job_title || '').trim() || undefined,
    gender: String(raw?.gender || '').trim() || undefined,
    nationality: undefined,
    bio: undefined,
    followers: 0,
    likes: 0,
    url: String(raw?.detail_link || raw?.url || '').trim() || undefined,
  }
}

/**
 * 走**数据源自己的检索**（`GET plugin/ShortDramaBaikeScraper/lookup?name=&remote=1`）。
 *
 * 为什么直连它的 HTTP 而不走本插件的 `/actors/search`、`/works/search`：
 * 那两条是本插件自己拼的（一条查人、一条查片名，各自一套口径），而数据源的 `/lookup`
 * 是它面板里「检索」用的那一条 —— 站点优先、库兜底，同名多季会列全。用户要的就是
 * 「和那边搜出来一样」，所以只用它；它不可用（没装 / 未启用 / 旧版本）时调用方退回老路。
 *
 * 2026-11-03 换源：ShortDramaNetSource **完全废弃**，改走 ShortDramaBaikeScraper。
 * 它的 `/lookup?name=` 回的是**一个 MediaInfo 扁平列表**（没有 works / actors 分块），
 * 所以按 `media_id` 前缀自己分拣 —— 只收**百科剧集**（drama / duanju / manju /
 * hema / huolong）与**百科人物**（actor / yanyuan / daoyan / bianju）；原著与豆瓣
 * 条目不是本插件的面板身份（号段 / 体系不同），丢弃。
 */
export async function lookupSite(
  props: { api?: PluginApi },
  keyword: string,
): Promise<SiteLookupResult> {
  const api = resolveApi(props)
  if (!api?.get) throw new Error('缺少可用的 api 实例')
  const text = String(keyword || '').trim()
  if (!text) return { works: [], actors: [], source: '' }
  // 检索与订阅快照**并行**：多一次往返不值得，订阅状态也等不起
  const [payload, subs] = await Promise.all([
    api
      .get(
        `plugin/ShortDramaBaikeScraper/lookup?name=${encodeURIComponent(text)}&remote=1`,
        {
          ...SILENT,
          timeout: 60_000,
        },
      )
      .then((response: any) => unwrap<any>(response)),
    fetchSubscribedIds(props),
  ])
  const rows = Array.isArray(payload?.data) ? payload.data : []
  const works: WorkItem[] = []
  const actors: ActorCandidate[] = []
  for (const raw of rows) {
    const mediaId = String(raw?.media_id || '')
    const entity = mediaId.split(':')[0].toLowerCase()
    if (['drama', 'duanju', 'manju', 'hema', 'huolong'].includes(entity)) {
      works.push(normalizeLookupWork(raw, works.length))
    } else if (['actor', 'yanyuan', 'daoyan', 'bianju'].includes(entity)) {
      actors.push(normalizeLookupActor(raw))
    }
  }
  // 订阅状态：搜索结果的作品行**不经本插件后端**（直连数据源 /lookup），
  // 所以列表行上不会有后端标的 `subscribed`。这里补一次轻量快照，
  // 命中就地打标 —— 不能只靠父组件的订阅清单（那份上百 KB，一旦失败/解析
  // 失败会静默变空集合，整屏已订阅被画成未订阅，2026-11-02 真机反馈）。
  if (subs.ids.length) {
    const idSet = new Set(subs.ids)
    for (const work of works) {
      if (idSet.has(String(work.media_id || ''))) work.subscribed = true
    }
  }
  // 演员卡同理：关注名单也是**本插件**的数据，检索结果不经过它，得就地打标，
  // 否则搜索回来的演员卡永远是空心（2026-11-02 真机反馈）。
  if (subs.actor_ids.length) {
    const actorSet = new Set(subs.actor_ids)
    for (const actor of actors) {
      if (actorSet.has(String(actor.actor_id || actor.media_id || ''))) {
        actor.subscribed = true
      }
    }
  }
  return {
    works,
    actors,
    // 数据源把站点命中与本地库合并返回（`remote=1`），分不出哪条来自哪边 ——
    // 空串 = 不知道，界面不会错贴「站点无结果」。
    source: '',
    subscribed_ids: subs.ids,
    stale_titles: subs.stale_titles,
  }
}

/** 演员增删的返回：``message`` 是给用户看的文案，其余是 data 里的内容 */
export interface ActorMutationResult extends ActorMutationPayload {
  message: string
}

/** 演员增删的公共实现（后端统一 ``Response[ActorMutationData]``） */
async function mutateActor(
  props: { api?: PluginApi },
  action: 'add' | 'remove',
  body: Record<string, unknown>,
  timeout?: number,
): Promise<ActorMutationResult> {
  const api = resolveApi(props)
  if (!api?.post) throw new Error('缺少可用的 api 实例')
  const envelope = unwrap<{ message?: string; data?: ActorMutationPayload }>(
    await api.post(`${API_BASE}/actors/${action}`, body, {
      ...SILENT,
      ...(timeout ? { timeout } : {}),
    }),
  )
  const data = envelope?.data || ({} as ActorMutationPayload)
  return {
    message: String(envelope?.message || ''),
    actors: Array.isArray(data.actors) ? data.actors : [],
    need_pick: Boolean(data.need_pick),
    candidates: Array.isArray(data.candidates) ? data.candidates : [],
  }
}

/**
 * 添加演员（``actor_id`` 有值时直接采用，否则后端按同名精确匹配）。
 *
 * 后端按标准信封返回：``data.need_pick`` 为真表示「百科里没有同名精确命中」，
 * 由前端拿候选让用户挑（不是接口失败）；重复添加 / 参数缺失等则是 HTTP 4xx 异常。
 */
export async function addActor(
  props: { api?: PluginApi },
  name: string,
  actor_id = '',
): Promise<ActorMutationResult> {
  // 添加时会当场抓一轮该演员的全部作品（作品详情逐页补），几分钟都可能 —— 放宽超时
  return mutateActor(props, 'add', { name, actor_id }, 180_000)
}

/**
 * 移除演员（2026-10-20 起按 ID：ID 是唯一身份，同名的另一位不受影响）。
 *
 * `name` 只是兜底 —— 关注名单正在从名字键向 ID 键收敛，过渡态里按名字也能删。
 */
export async function removeActor(
  props: { api?: PluginApi },
  identity: { actor_id?: string; name?: string },
): Promise<ActorMutationResult> {
  return mutateActor(props, 'remove', { ...identity })
}

/**
 * 关注名单（``GET /actors``，轻量：状态 + 作品数，不含档案）。
 *
 * 配置页用它把名单里的 ID 显示成名字（2026-10-20 起关注名单以 ID 存，
 * ID 是唯一身份，名字只作展示）。
 */
export async function fetchActorList(
  props: { api?: PluginApi },
): Promise<ActorItem[]> {
  const api = resolveApi(props)
  if (!api?.get) throw new Error('缺少可用的 api 实例')
  const data = readData<{ actors?: ActorItem[] }>(
    await api.get(`${API_BASE}/actors`, { ...SILENT }),
  )
  return Array.isArray(data?.actors) ? data.actors : []
}

/**
 * 已关注演员的**卡片数据**（面板「已关注的演员」卡片墙）。
 *
 * 字段与 `searchActor` 的候选行同构 —— 前端两处用**同一个卡片组件**渲染，
 * 样式与交互因此完全一致。档案（头像 / 简介）优先读后端快照：发现任务每轮顺带补一次，
 * 所以默认调用很快；`enrich=true` 时后端会给还没有档案的演员现抓一次演员页（最多 12 位），
 * 稍慢但能立刻补上头像（卡片墙标题行的刷新按钮走这条）。
 */
export async function fetchActorCards(
  props: { api?: PluginApi },
  enrich = false,
): Promise<ActorCardItem[]> {
  const api = resolveApi(props)
  if (!api?.get) throw new Error('缺少可用的 api 实例')
  const query = enrich ? '?enrich=1' : ''
  const data = readData<{ actors?: ActorCardItem[] }>(
    await api.get(`${API_BASE}/actors/cards${query}`, { ...SILENT, timeout: 120_000 }),
  )
  return Array.isArray(data?.actors) ? data.actors : []
}

/**
 * 一位演员的**详情**（``GET /actors/detail``）—— 自绘「演员作品页」的数据源。
 *
 * 档案（姓名 / 头像 / 简介 / 职业 / 国籍）走百科 ``actor_profile``，作品走
 * ``actor_works``（与 ``/actors/works`` 同一段投影）。两条都是现查 —— 要抓演员页、
 * 还要逐部补作品详情，所以超时放到 3 分钟。
 */
export async function fetchActorDetail(
  props: { api?: PluginApi },
  actorId: string,
  name = '',
  page = 1,
  pageSize = 24,
): Promise<ActorDetailPayload> {
  const api = resolveApi(props)
  if (!api?.get) throw new Error('缺少可用的 api 实例')
  const query = new URLSearchParams()
  if (actorId) query.set('actor_id', actorId)
  if (name) query.set('name', name)
  // 作品分页：详情页滚动加载，一次一页（后端把整份投影缓存在内存里，翻页是纯切片）
  query.set('works_page', String(page))
  query.set('works_page_size', String(pageSize))
  return readData<ActorDetailPayload>(
    await api.get(`${API_BASE}/actors/detail?${query.toString()}`, {
      ...SILENT,
      timeout: 180_000,
    }),
  )
}

/** 归一化「订阅全部作品」的返回（字段缺失时补默认值，别让模板炸掉） */
function normalizeActorSubscribeAll(raw: any): ActorSubscribeAllPayload {
  const details = Array.isArray(raw?.details)
    ? raw.details
        .filter((row: any) => row && typeof row === 'object')
        .map((row: any) => ({
          time: String(row.time || ''),
          title: String(row.title || ''),
          year: String(row.year || ''),
          media_id: String(row.media_id || ''),
          actor: String(row.actor || ''),
          ok: row.ok === true,
          detail: String(row.detail || ''),
        }))
    : []
  return {
    name: String(raw?.name || ''),
    total: Number(raw?.total || 0),
    submitted: Number(raw?.submitted || 0),
    skipped_library: Number(raw?.skipped_library || 0),
    skipped_subscribed: Number(raw?.skipped_subscribed || 0),
    failed: Number(raw?.failed || 0),
    capped: raw?.capped === true,
    media_ids: Array.isArray(raw?.media_ids)
      ? raw.media_ids.map((item: unknown) => String(item)).filter(Boolean)
      : [],
    details,
  }
}

/**
 * **订阅一位演员的全部作品**（演员卡 / 演员详情页的按钮）。
 *
 * 走后端 `/actors/subscribe_all` 而不是前端逐部提交：
 *
 * - 作品列表由后端**现取**，不受演员详情页分页影响（只加载了第一页也能全订）；
 * - 已在媒体库的由后端跳过（与自动订阅同一个开关），`excludeIds` 里的（前端已知
 *   已订阅）也直接跳过，不会被重复提交；
 * - 后端走 `SubscribeChain`，与系统订阅是同一套落库逻辑；下载器 / 站点 / 目录
 *   沿用配置页那三项；
 * - 一次点几十部要跑一会儿，超时放宽到 3 分钟。
 */
export async function subscribeAllActor(
  props: { api?: PluginApi },
  info: { actorId?: string; name?: string; excludeIds?: string[] },
): Promise<ActorSubscribeAllPayload> {
  const api = resolveApi(props)
  if (!api?.post) throw new Error('缺少可用的 api 实例')
  const res = readData<ActorSubscribeAllPayload>(
    await api.post(
      `${API_BASE}/actors/subscribe_all`,
      {
        actor_id: String(info.actorId || ''),
        name: String(info.name || ''),
        exclude_ids: (info.excludeIds || []).map(String).filter(Boolean),
      },
      { ...SILENT, timeout: 180_000 },
    ),
  )
  return normalizeActorSubscribeAll(res)
}

/**
 * 某位演员的**全部**作品（百科实时，关注与否均可）—— 点演员卡片展开作品墙用。
 *
 * 后端现查短剧百科（每条作品都已补成作品页记录），比墙上的快照数据慢一截，
 * 放宽超时；失败由调用方降级成提示。
 */
/**
 * 榜单目录（发现页「榜单」chips 用，``GET /ranks``）。
 * 纯静态目录、零网络，失败也返回空目录 + 说明，不当成请求错误。
 */
export async function fetchRanks(
  props: { api?: PluginApi },
  /**
   * `true` = 要**全集**（配置页的选项列表用）。
   *
   * 默认只返回配置里勾选的项（发现页只该看到勾过的）；配置页则相反 ——
   * 拿过滤后的目录做选项，被取消的项就再也勾不回来了。
   */
  includeAll = false,
): Promise<RanksPayload> {
  const api = resolveApi(props)
  if (!api?.get) throw new Error('缺少可用的 api 实例')
  const path = includeAll ? `${API_BASE}/ranks?all=1` : `${API_BASE}/ranks`
  return (
    readData<RanksPayload>(await api.get(path, { ...SILENT })) || {
      ranks: [],
      message: '',
    }
  )
}

/**
 * 一个榜单的作品卡（``GET /ranks/works?rank=rebo``）。
 * 行为数据源按实际页面解析的原样卡（``RankMediaItem``），这里不做归一 ——
 * 卡片样式由页面映射到与作品页同一张卡。站点榜单页不支持翻页，一页就是
 * 全部；抓不到时 ``medias`` 空 + ``message``。
 */
export async function fetchRankWorks(
  props: { api?: PluginApi },
  rank: string,
  page = 1,
): Promise<RankWorksPayload> {
  const api = resolveApi(props)
  if (!api?.get) throw new Error('缺少可用的 api 实例')
  const query = new URLSearchParams()
  query.set('rank', rank)
  query.set('page', String(Math.max(1, page)))
  const payload = readData<RankWorksPayload>(
    await api.get(`${API_BASE}/ranks/works?${query.toString()}`, {
      ...SILENT,
      timeout: 60_000,
    }),
  )
  const rows = Array.isArray(payload?.medias) ? payload.medias : []
  return {
    rank: payload?.rank || rank,
    name: payload?.name || '',
    page: Number(payload?.page) || page,
    has_more: Boolean(payload?.has_more),
    message: payload?.message || '',
    medias: rows,
  }
}

/**
 * 插件最近日志（面板右上「日志」区域用，``GET /logs?limit=80``）。
 * 旧行在前、新行在后；轮询调用，失败返回空列表不影响页面。
 */
export async function fetchLogs(
  props: { api?: PluginApi },
  limit = 80,
): Promise<LogsPayload> {
  const api = resolveApi(props)
  if (!api?.get) throw new Error('缺少可用的 api 实例')
  return (
    readData<LogsPayload>(
      await api.get(`${API_BASE}/logs?limit=${encodeURIComponent(String(limit))}`, {
        ...SILENT,
        timeout: 15_000,
      }),
    ) || { items: [] }
  )
}

/**
 * 取**一页人物目录**（后端 ``GET /people``）。
 *
 * 数据源侧对应站点的 ``/<kind>/list.html?page=N``（24 条/页）。降级口径：
 * 数据源还没提供 ``list_people`` 模块方法时后端**不报错**，返回空列表 + ``message``，
 * 这里把 ``message`` 原样交给页面显示，不当成请求失败。
 *
 * @param kind ``yanyuan`` 演员 / ``daoyan`` 导演 / ``bianju`` 编剧
 * @param page 从 1 开始的页码
 * @param gender ``男`` / ``女``；空串 = 全部（站点的男女榜，2026-11-02 用户口径）
 */
export async function fetchPeople(
  props: { api?: PluginApi },
  kind: string,
  page: number,
  gender = '',
): Promise<PeopleListPayload> {
  const api = resolveApi(props)
  if (!api?.get) throw new Error('缺少可用的 api 实例')
  const query = new URLSearchParams()
  query.set('kind', kind)
  query.set('page', String(page))
  // 空串不发这个参数 —— 站点「全部」就是不筛（后端也按空串处理）
  if (gender) query.set('gender', gender)
  return (
    readData<PeopleListPayload>(
      await api.get(`${API_BASE}/people?${query.toString()}`, {
        ...SILENT,
        timeout: 60_000,
      }),
    ) || { kind, page, gender, has_more: false, message: '', people: [] }
  )
}

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
  return readData<WorksPayload>(
    await api.get(`${API_BASE}/actors/works?${query.toString()}`, {
      ...SILENT,
      timeout: 120_000,
    }),
  )
}

/**
 * 一部作品的**详情**（面板自绘的详情页）—— 不走宿主自带的媒体详情页。
 *
 * 为什么要自己取：宿主详情页（`MoviePilot-Frontend` 的 `MediaDetailView.vue`）里
 * 右侧信息面板 / 演职员 / 推荐 / 分季**全部以 `tmdb_id` 为前提**，短剧大多不在 TMDB 上
 * ⇒ 那些区块整块不渲染；本端点把百科详情的标准字段与**宿主模型里没有**的墙上字段
 * （热度 / 播放量 / 真人·AI / 在库）一起给全。
 *
 * 百科现查（详情页要出网，虽然百科插件侧有 TTL 缓存）——放宽超时，慢一点也好过被掐断。
 */
export async function fetchWorkDetail(
  props: { api?: PluginApi },
  work: Pick<WorkItem, 'media_id' | 'title' | 'year'>,
): Promise<WorkDetailPayload> {
  const api = resolveApi(props)
  if (!api?.get) throw new Error('缺少可用的 api 实例')
  const query = new URLSearchParams()
  query.set('media_id', String(work?.media_id || ''))
  if (work?.title) query.set('title', work.title)
  if (work?.year) query.set('year', work.year)
  const data = readData<WorkDetailPayload>(
    await api.get(`${API_BASE}/works/detail?${query.toString()}`, {
      ...SILENT,
      timeout: 120_000,
    }),
  )
  return normalizeWorkDetail(data)
}

/** 归一化详情载荷：字段缺失 / 类型不稳（数值给字符串）时补齐默认值，别让模板炸掉 */
function normalizeWorkDetail(raw: any): WorkDetailPayload {
  return {
    ...(raw || {}),
    found: raw?.found === true,
    title: String(raw?.title || ''),
    year: String(raw?.year || ''),
    media_source: String(raw?.media_source || 'djbaike'),
    media_id: String(raw?.media_id || ''),
    type: String(raw?.type || '电视剧'),
    overview: String(raw?.overview || ''),
    poster: String(raw?.poster || ''),
    backdrop: String(raw?.backdrop || ''),
    vote: Number(raw?.vote || 0),
    release_date: String(raw?.release_date || ''),
    episode_count: Number(raw?.episode_count || 0),
    episode_minutes: Number(raw?.episode_minutes || 0),
    duration_minutes: Number(raw?.duration_minutes || 0),
    genres: Array.isArray(raw?.genres) ? raw.genres.filter((tag: unknown) => !!tag) : [],
    studio: String(raw?.studio || ''),
    // 播放平台（「在哪播」）：详情层后端从 MediaInfo 的 networks 收敛出来，
    // 拿不到再拿墙上那一行兜底（merge_detail_row），都取不到就是空串
    platform: String(raw?.platform || ''),
    status: String(raw?.status || ''),
    language: String(raw?.language || ''),
    url: String(raw?.url || ''),
    actors: Array.isArray(raw?.actors)
      ? raw.actors
          .filter((row: any) => row && row.name)
          .map((row: any) => ({
            actor_id: String(row.actor_id || ''),
            name: String(row.name),
            character: String(row.character || ''),
            profile: String(row.profile || ''),
            kind: String(row.kind || ''),
            url: String(row.url || ''),
            subscribed: row.subscribed === true,
          }))
      : [],
    heat: Number(raw?.heat || 0),
    play_count: Number(raw?.play_count || 0),
    kind: String(raw?.kind || ''),
    first_seen: String(raw?.first_seen || ''),
    is_new: raw?.is_new === true,
    in_library: typeof raw?.in_library === 'boolean' ? raw.in_library : null,
  }
}

/**
 * 站点原始记录里的一个**人物**（导演 / 编剧 / 演员通用）。
 *
 * 来自数据源 `/recognize` 的 `actors[]`（人物分类全表，`kind` 标分类、
 * `media_id` 直接给复合身份），所以能直接渲染成演员卡、点了进人物档案页。
 */
export interface WorkSourcePerson {
  name: string
  /** 复合身份（`actor:` / `yanyuan:` / `daoyan:` / `bianju:` + 页面 ID）；抠不出来时为空 */
  media_id: string
  /** 演员是角色名，导演 / 编剧是职务 */
  role: string
  /** 站点分类：`actor`（.org）或 `yanyuan` / `daoyan` / `bianju`（.net） */
  kind: string
  /** 头像（站点图床 / CDN 绝对地址） */
  profile: string
}

/** 原著（小说）改编出的一部作品（站点 `adapted_from.works[]` 的一项） */
export interface AdaptedWork {
  media_id: string
  title: string
  url: string
  poster: string
  release_date: string
  episodes: number
  genres: string[]
}

/**
 * 原著信息（数据源 `/recognize` 的 `adapted_from` 投影）—— 「原著详情页」的数据源。
 *
 * 2026-11-02 换源：剧集详情直接带 `adapted_from`（原著档案 + 改编作品清单）；
 * 原著**自己**的页面（`xiaoshuo:<id>`）走数据源 `/catalog/detail` 取档案
 * （改编作品清单数据源不反查，`works` 为空、该块隐藏）。
 */
export interface AdaptedInfo {
  title: string
  author: string
  url: string
  poster: string
  /**
   * 原著在数据源里的身份（`xiaoshuo:<id>`）。
   *
   * 剧集页的改编区只给「本剧的原著」这一层信息，**改编作品列表**要拿原著自己
   * 的记录才有（原著页那一区）。有它时原著详情页会补一次取全（见
   * `fetchAdaptedDetail`）；老记录可能为空，为空就按已有的显示。
   */
  media_id: string
  /** 总字数（0 = 站点没给） */
  words: number
  genres: string[]
  summary: string
  works: AdaptedWork[]
}

/**
 * 作品详情页补的「第二块数据面」：数据源侧的补充信息。
 *
 * 2026-11-03 换源后走 ShortDramaBaikeScraper（ShortDramaNetSource 已完全废弃）：
 * - `/lookup?media_id=` → 宿主 MediaInfo：`actors[]`（演员表，`character` 是角色；
 *   导演 / 编剧它不单列，两块恒空）、`douban_id`（后端 `/works/detail` 的 domain
 *   转换会丢，这里补回）、`classification_facts` 里的站点统计；
 * - `/novel?media_id=` → 原著档案 + 全部改编作品（「改编自」块）。
 *
 * 统计口径：`heat` / `play_count` / `favorite_count` 是已折算的数字，展示层转回
 * 「万 / 亿」文案；`status` / `duration` 数据源不给，恒空。
 *
 * 出品方 / 平台数据源也不提供，留空，详情页按空值隐藏对应行。
 * 端点读不到就静默返回空壳，详情页退回第一块数据。
 */
export interface WorkSourceRecord {
  director: WorkSourcePerson[]
  writer: WorkSourcePerson[]
  cast: WorkSourcePerson[]
  /**
   * 热度 / 播放量 / 收藏 —— 展示文案（「380.14万」/「1016万」/「8.86万」）。
   *
   * `/recognize` 给的是已折算的数字；这里转回站点口径的「万 / 亿」文案，
   * 空串 = 站点没写这一项。
   */
  heat_text: string
  play_count_text: string
  favorites_text: string
  /** 连载状态（`已完结` / `更新至第 N 集`…） */
  status: string
  /** 单集时长（分钟，换源后不再提供）+ 站点原文（如 `2分30秒`） */
  duration_minutes: number
  duration_text: string
  /** 出品方 / 版权方、播出平台（换源后不再提供） */
  studio: string
  platform: string
  /** 豆瓣条目 ID + 地址（`/recognize` 带回；补后端 domain 转换丢掉的那份） */
  douban_id: string
  douban_url: string
  /** 改编自（小说名 / 作者 / 原著页地址；不是改编作品时都为空） */
  adapted_title: string
  adapted_author: string
  /** 原著（小说）在百科的页面地址 */
  adapted_url: string
  /** 原著完整信息（「原著详情页」用；不是改编作品时 null） */
  adapted: AdaptedInfo | null
}

const EMPTY_SOURCE: WorkSourceRecord = {
  director: [],
  writer: [],
  cast: [],
  heat_text: '',
  play_count_text: '',
  favorites_text: '',
  status: '',
  duration_minutes: 0,
  duration_text: '',
  studio: '',
  platform: '',
  douban_id: '',
  douban_url: '',
  adapted_title: '',
  adapted_author: '',
  adapted_url: '',
  adapted: null,
}

function toNumber(value: unknown): number {
  const num = Number(String(value ?? '').replace(/[^\d.]/g, ''))
  return Number.isFinite(num) ? num : 0
}

/**
 * 从数据源 detail_link 里抠出**人物复合 ID**（三种页面形态都认）：
 * .net `…/yanyuan/info-123.html`、.net `…/yanyuan/123.html`、
 * .org `…/[zh-Hans/]actor/123`。`/lookup` 的 MediaCredit 不带 media_id，
 * 只带人物页地址 —— 地址形态固定，反推即可。
 */
function personIdFromUrl(url: unknown): string {
  const hit = String(url || '').match(
    /\/(?:zh-[A-Za-z]+\/)?(yanyuan|daoyan|bianju|actor)\/(?:info-)?([A-Za-z0-9][A-Za-z0-9_-]*?)(?:\.html)?(?=$|[/?#])/i,
  )
  return hit ? `${hit[1].toLowerCase()}:${hit[2]}` : ''
}

/** NovelData.words（`32.5 万字`）→ 总字数（解析不了给 0） */
function parseWordCount(text: unknown): number {
  const raw = String(text || '').trim()
  const hit = raw.match(/([\d.]+)/)
  if (!hit) return 0
  const value = Number(hit[1])
  if (!Number.isFinite(value)) return 0
  return raw.includes('万') ? Math.round(value * 10000) : Math.round(value)
}

/** 数值 → 人类可读文案（`3801400` → `380.14万`；与站点「万 / 亿」两档同口径） */
function compactNum(value: unknown): string {
  const num = Number(value || 0)
  if (!Number.isFinite(num) || num <= 0) return ''
  const trim = (text: string) => text.replace(/\.?0+$/, '')
  if (num >= 1e8) return `${trim((num / 1e8).toFixed(2))}亿`
  if (num >= 1e4) return `${trim((num / 1e4).toFixed(2))}万`
  return String(Math.round(num))
}

/**
 * 数据源原著档案（`/novel` 的 `data`）→ 详情页「改编自」块。
 *
 * ShortDramaBaikeScraper 的 `NovelData`：`name` / `author` / `words`（字符串
 * 「32.5 万字」）/ `overview` / `poster` / `detail_url` / `adaptations[]`
 * （`name` 是剧名，不是 `title`）。字段缺就留空，界面按空值隐藏。
 */
function novelDataToAdapted(data: any): AdaptedInfo | null {
  const title = String(data?.name || '').trim()
  if (!title) return null
  return {
    title,
    author: String(data?.author || '').trim(),
    url: String(data?.detail_url || '').trim(),
    poster: String(data?.poster || '').trim(),
    media_id: String(data?.media_id || '').trim(),
    words: parseWordCount(data?.words),
    genres: [],
    summary: String(data?.overview || '').trim(),
    works: (Array.isArray(data?.adaptations) ? data.adaptations : [])
      .filter((item: any) => String(item?.name || '').trim())
      .map((item: any) => ({
        media_id: String(item.media_id || '').trim(),
        title: String(item.name).trim(),
        url: String(item.detail_url || '').trim(),
        poster: String(item.poster || '').trim(),
        release_date: String(item.date || '').trim(),
        episodes: toNumber(item.episodes),
        genres: [],
      })),
  }
}

/**
 * 读数据源侧的**第二块数据面**（演员表 + 豆瓣身份 + 改编自 + 站点统计）。
 *
 * 2026-11-03 换源：ShortDramaNetSource **完全废弃**，改走 ShortDramaBaikeScraper
 * 的 `/lookup?media_id=`（回宿主 MediaInfo：`actors[]` 带角色、`douban_id`、
 * `classification_facts` 里的站点统计）＋ `/novel?media_id=`（原著档案 + 改编清单）。
 *
 * 与旧数据源的差别（拿不到就留空，界面按空值隐藏，不报错）：
 * * MediaInfo 的 `actors[]` 只有演员表（`character` 是角色），**没有**导演 / 编剧
 *   分类 —— 那两块恒空；旧数据源能按 `kind` 拆三份，这里拆不出来；
 * * 统计数字在 `classification_facts`（键 `extensions.djbaike.heat` /
 *   `.play_count` / `.favorite_count`），不是顶层 `heat` / `play_count`；
 * * `status` / `duration` 数据源不给，恒空。
 */
export async function fetchWorkSource(
  props: { api?: PluginApi },
  mediaId: string,
): Promise<WorkSourceRecord> {
  const api = resolveApi(props)
  if (!api?.get || !mediaId) return { ...EMPTY_SOURCE }
  try {
    const [payload, novel] = await Promise.all([
      api
        .get(
          `plugin/ShortDramaBaikeScraper/lookup?media_id=${encodeURIComponent(mediaId)}`,
          { ...SILENT, timeout: 30_000 },
        )
        .then((response: any) => unwrap<any>(response)),
      api
        .get(`plugin/ShortDramaBaikeScraper/novel?media_id=${encodeURIComponent(mediaId)}`, {
          ...SILENT,
          timeout: 30_000,
        })
        .then((response: any) => unwrap<any>(response))
        .catch(() => null),
    ])
    const info = payload?.data
    // `data=null` = 查不到（数据源对未收录 / 人物身份会给 null）
    if (
      !info ||
      typeof info !== 'object' ||
      !String(info.media_id || info.title || '').trim()
    ) {
      return { ...EMPTY_SOURCE }
    }
    const creditRows = (
      rows: unknown,
      kind: string,
      fallbackRole: string,
    ): WorkSourcePerson[] =>
      (Array.isArray(rows) ? rows : [])
        .filter((item: any) => String(item?.name || '').trim())
        .map((item: any) => ({
          name: String(item.name).trim(),
          media_id: String(item.media_id || '').trim() || personIdFromUrl(item.url),
          role:
            String(item.role || item.character || '').trim() ||
            String(item.job || '').trim() ||
            fallbackRole,
          kind,
          // 头像：数据源（MediaCredit / ActorRow）给的是 ``profile_path`` 或
          // ``poster``，两种别名都收 —— 写死空串会让导演/编剧卡永远人形占位。
          profile: String(
            item.profile_path || item.profile || item.poster || '',
          ).trim(),
        }))
    // MediaInfo 的 `actors[]` 只有演员（`character` = 角色）；导演 / 编剧数据源
    // 不在详情里给，两块恒空。
    const cast = creditRows(info.actors, 'yanyuan', '')
    const director: WorkSourcePerson[] = []
    const writer: WorkSourcePerson[] = []
    const adapted = novelDataToAdapted(novel?.data)
    const doubanId = String(info.douban_id || '').trim()
    // ── 站内统计：数据源把折算后的数字放在 `classification_facts` 扩展位
    // （`extensions.djbaike.*`），转回「万 / 亿」文案展示；缺键 = 站点没写。
    const facts = (info.classification_facts || {}) as Record<string, any>
    const factNum = (name: string): number =>
      Number(facts[`extensions.djbaike.${name}`] || 0) || 0
    return {
      director,
      writer,
      cast,
      heat_text: compactNum(factNum('heat')),
      play_count_text: compactNum(factNum('play_count')),
      favorites_text: compactNum(factNum('favorite_count')),
      status: '',
      duration_minutes: 0,
      duration_text: '',
      studio: '',
      platform: '',
      douban_id: doubanId,
      douban_url: doubanId ? `https://movie.douban.com/subject/${doubanId}/` : '',
      adapted_title: adapted?.title || '',
      adapted_author: adapted?.author || '',
      adapted_url: adapted?.url || '',
      adapted,
    }
  } catch {
    // 补充信息：拿不到就只显示 MediaInfo 那份，不影响详情页本身
    return { ...EMPTY_SOURCE }
  }
}

/** 豆瓣短评一条（宿主 `GET /api/v1/douban/interests/{id}/{type}` 的 items） */
export interface DoubanComment {
  id: string
  comment: string
  rating: number
  votes: number
  author: string
  author_url: string
  /** 头像（豆瓣图床；没有时为空） */
  avatar: string
  time: string
}

/** 豆瓣影评一条（宿主 `GET /api/v1/douban/reviews/{id}/{type}` 的 items） */
export interface DoubanReview {
  id: string
  title: string
  abstract: string
  rating: number
  useful: number
  author: string
  /** 头像（豆瓣图床；没有时为空） */
  avatar: string
  url: string
  time: string
}

/**
 * 豆瓣类型名：宿主那几个接口按 `movie` / `tv` 分表（**同一个 id 在两边结果不同** ——
 * 实测 38383286 走 `movie` 是 0 条、走 `tv` 才有短评与影评）。
 * 短剧在系统里就是电视剧，所以按 `view.type` 判。
 */
function doubanTypeName(typeName: string): string {
  return String(typeName || '') === '电影' ? 'movie' : 'tv'
}

/**
 * 取豆瓣**短评**一页（宿主自己的接口，与系统详情页「短评 / 影评」那一页同一份数据）。
 *
 * 系统那一页是 `start` 偏移 + `count` 条数分页（见 `MediaCommentView.vue`），
 * 这里照同一套协议走；`total` 用来在标签上显示条数、并判断还有没有下一页。
 *
 * 没有 `douban_id` 就没有这两块（系统侧同理）；失败静默返回空页 —— 豆瓣限流是常事。
 */
export async function fetchDoubanComments(
  props: { api?: PluginApi },
  doubanId: string,
  typeName = '电视剧',
  start = 0,
  count = 10,
): Promise<{ items: DoubanComment[]; total: number }> {
  const api = resolveApi(props)
  const id = String(doubanId || '').trim()
  if (!api?.get || !id) return { items: [], total: 0 }
  try {
    const payload = unwrap<any>(
      await api.get(
        `douban/interests/${encodeURIComponent(id)}/${doubanTypeName(typeName)}?start=${start}&count=${count}`,
        { ...SILENT, timeout: 30_000 },
      ),
    )
    const data = payload?.data || {}
    const rows = Array.isArray(data.items) ? data.items : []
    return {
      items: rows.map((row: any) => ({
        id: String(row?.id || ''),
        comment: String(row?.comment || '').trim(),
        rating: Number(row?.rating || 0),
        votes: Number(row?.vote_count || 0),
        author: String(row?.author?.name || '').trim(),
        author_url: String(row?.author?.url || '').trim(),
        avatar: String(row?.author?.avatar || '').trim(),
        time: String(row?.create_time || '').trim(),
      })),
      total: Number(data.total || rows.length) || 0,
    }
  } catch {
    return { items: [], total: 0 }
  }
}

/** 取豆瓣**影评**一页（长评；字段与短评不同：标题 / 摘要 / 有用数） */
export async function fetchDoubanReviews(
  props: { api?: PluginApi },
  doubanId: string,
  typeName = '电视剧',
  start = 0,
  count = 10,
): Promise<{ items: DoubanReview[]; total: number }> {
  const api = resolveApi(props)
  const id = String(doubanId || '').trim()
  if (!api?.get || !id) return { items: [], total: 0 }
  try {
    const payload = unwrap<any>(
      await api.get(
        `douban/reviews/${encodeURIComponent(id)}/${doubanTypeName(typeName)}?start=${start}&count=${count}`,
        { ...SILENT, timeout: 30_000 },
      ),
    )
    const data = payload?.data || {}
    const rows = Array.isArray(data.items) ? data.items : []
    return {
      items: rows.map((row: any) => ({
        id: String(row?.id || ''),
        title: String(row?.title || '').trim(),
        abstract: String(row?.abstract || '').trim(),
        rating: Number(row?.rating || 0),
        useful: Number(row?.useful_count || 0),
        author: String(row?.author?.name || '').trim(),
        avatar: String(row?.author?.avatar || '').trim(),
        url: String(row?.url || '').trim(),
        time: String(row?.create_time || '').trim(),
      })),
      total: Number(data.total || rows.length) || 0,
    }
  } catch {
    return { items: [], total: 0 }
  }
}

/**
 * 只取一部作品的**原著信息**（原著页自用兜底）。
 *
 * 正常路径是作品详情里顺手把 `adapted` 交给原著页；这一条只在那份数据为空
 * （详情那边没取到 / 组件被直接挂载）时补一次，数据源详情缓存命中时零站点请求。
 */
export async function fetchAdaptedInfo(
  props: { api?: PluginApi },
  mediaId: string,
): Promise<AdaptedInfo | null> {
  if (!String(mediaId || '').trim()) return null
  try {
    const source = await fetchWorkSource(props, mediaId)
    return source.adapted
  } catch {
    return null
  }
}

/**
 * 原著**自己**的记录（`xiaoshuo:<id>`）→ 原著详情页的完整信息。
 *
 * 2026-11-03 换源：ShortDramaNetSource **完全废弃**，改走 ShortDramaBaikeScraper 的
 * `/novel?media_id=`（`NovelData`：书名 / 作者 / 封面 / 页面地址 / 字数 / 简介 /
 * 改编作品清单）；取不到（`data=null`）就按已有字段照常显示。
 */
export async function fetchAdaptedDetail(
  props: { api?: PluginApi },
  mediaId: string,
): Promise<AdaptedInfo | null> {
  const id = String(mediaId || '').trim()
  const api = resolveApi(props)
  if (!id || !api?.get) return null
  try {
    const payload = unwrap<any>(
      await api.get(
        `plugin/ShortDramaBaikeScraper/novel?media_id=${encodeURIComponent(id)}`,
        { ...SILENT, timeout: 20_000 },
      ),
    )
    return novelDataToAdapted(payload?.data)
  } catch {
    return null
  }
}

/**
 * 作品在媒体服务器上的**播放地址**（系统的详情页「播放」按钮走的就是这一套）。
 *
 * 两步：
 * 1. `GET /api/v1/mediaserver/exists`（按 media_source + media_id 查库）；
 * 2. `GET /api/v1/mediaserver/play/{item_id}` 拿播放页地址。
 *
 * 返回空串表示没有可播放的条目（没入库 / 没配媒体服务器 / 服务器里找不到）。
 */
export async function fetchPlayUrl(
  props: { api?: PluginApi },
  info: { mediaSource: string; mediaId: string; title: string; year: string; type: string },
): Promise<string> {
  const api = resolveApi(props)
  if (!api?.get) return ''
  const source = String(info.mediaSource || '').trim()
  const mediaId = String(info.mediaId || '').trim()
  if (!source || !mediaId) return ''
  try {
    const query = new URLSearchParams({
      media_source: source,
      media_id: mediaId,
      title: String(info.title || ''),
      year: String(info.year || ''),
      mtype: String(info.type || ''),
    })
    const found = unwrap<any>(
      await api.get(`mediaserver/exists?${query.toString()}`, { ...SILENT, timeout: 30_000 }),
    )
    const itemId = String(found?.data?.item?.id || '').trim()
    if (!itemId) return ''
    const played = unwrap<any>(
      await api.get(`mediaserver/play/${encodeURIComponent(itemId)}`, {
        ...SILENT,
        timeout: 30_000,
      }),
    )
    return String(played?.data?.url || '').trim()
  } catch {
    return ''
  }
}

/** 读取插件配置 */
export async function fetchConfig(props: { api?: PluginApi }): Promise<Partial<PluginConfig>> {
  const api = resolveApi(props)
  if (!api?.get) throw new Error('缺少可用的 api 实例')
  return readData<PluginConfig>(await api.get(`${API_BASE}/config`, { ...SILENT })) || {}
}

/** 保存插件配置 */
export async function saveConfig(
  props: { api?: PluginApi },
  config: Partial<PluginConfig>,
): Promise<Partial<PluginConfig>> {
  const api = resolveApi(props)
  if (!api?.put) throw new Error('缺少可用的 api 实例')
  return readData<PluginConfig>(await api.put(`${API_BASE}/config`, config, { ...SILENT })) || {}
}

/**
 * 卡片「已订阅」状态的**唯一来源**是 `/subscriptions`（订阅清单：插件订阅清单 ∪
 * 宿主订阅），见 ActorWall.loadSubscribed —— 这里不再单独读宿主订阅表：
 * 两条来源各算一套的结果就是「订阅了红心不亮 / 取消点了没反应」（2026-10-22）。
 */
