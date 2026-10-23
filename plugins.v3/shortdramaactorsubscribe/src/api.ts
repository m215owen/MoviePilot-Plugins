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

/**
 * 直接向宿主提交订阅（携带订阅偏好）。
 *
 * 系统订阅弹窗没有下载器选项 —— 配置页指定了下载器时走这里，把偏好一并带上。
 * 返回 ``ok`` = 宿主已受理；``message`` 为宿主返回的说明（成功或失败原因）。
 */
export async function submitSubscribe(
  props: { api?: PluginApi },
  work: Pick<
    WorkItem,
    'title' | 'year' | 'media_source' | 'media_id' | 'type' | 'episode_count'
  >,
  downloader: string,
  prefs?: { sites?: number[]; savePath?: string; mode?: string },
): Promise<{ ok: boolean; message: string }> {
  const api = resolveApi(props)
  if (!api?.post) return { ok: false, message: '缺少可用的 api 实例' }
  const isMovie = String(work.type || '') === '电影'
  const episodes = Math.max(0, Number(work.episode_count || 0))
  const payload: Record<string, unknown> = {
    name: work.title,
    year: work.year || '',
    media_source: work.media_source,
    media_id: work.media_id,
    type: work.type || '电视剧',
  }
  // 电视剧必须带季集信息（宿主 `subscribe/create.py`：`total_episode` 为空会重新识别
  // 媒体，而插件来源识别结果没有 seasons ⇒ 直接失败「媒体信息中没有季集信息」）。
  if (!isMovie) {
    payload.season = 1
    payload.start_episode = 1
    payload.total_episode = episodes || 1
  }
  if (downloader) payload.downloader = downloader
  // 订阅站点（只在勾选的站搜；宿主订阅接口的 `sites` 是 int 列表）
  if (prefs?.sites?.length) payload.sites = prefs.sites
  // 订阅下载目录（宿主 `/download/paths` 的 save_path）
  const savePath = String(prefs?.savePath || '').trim()
  if (savePath) payload.save_path = savePath
  // 订阅类型：宿主 `best_version`，只在显式配置时下发（follow = 交给宿主订阅设置）
  if (prefs?.mode === 'normal') payload.best_version = 0
  else if (prefs?.mode === 'best') payload.best_version = 1
  try {
    const res = unwrap<{ success?: boolean; message?: string }>(
      await api.post(HOST_SUBSCRIBE, payload, { ...SILENT }),
    )
    if (res && res.success === false) {
      return { ok: false, message: String(res.message || '订阅失败') }
    }
    return { ok: true, message: String(res?.message || `已提交订阅：${work.title}`) }
  } catch (err) {
    return { ok: false, message: extractErrorMessage(err) }
  }
}

/**
 * 取消一部剧的订阅（**按身份删**，与系统详情页 `removeSubscribe` 同一个接口）。
 *
 * `DELETE subscribe/media/{media_id}?media_source=&season=` —— 不需要先查订阅 id，
 * 身份就是我们手里的 `media_source` + 复合 `media_id`。系统的取消流程走的也是它
 * （`useMediaSubscribe.ts: removeSubscribe` → `api.delete('subscribe/media/…')`），
 * 所以从插件里取消掉的订阅，与在系统详情页取消是同一件事。
 *
 * 不存在（已取消 / 从没订阅过）时宿主同样返回成功（幂等），调用方按成功处理。
 */
export async function cancelSubscribe(
  props: { api?: PluginApi },
  info: { mediaSource: string; mediaId: string; season?: number },
): Promise<void> {
  const api = resolveApi(props)
  const mediaId = String(info.mediaId || '').trim()
  const mediaSource = String(info.mediaSource || '').trim()
  if (!mediaId || !mediaSource) throw new Error('缺少媒体身份，无法取消订阅')
  if (!api?.delete) throw new Error('当前宿主未提供删除接口，请到系统订阅页取消')
  const params: Record<string, unknown> = { media_source: mediaSource }
  if (Number(info.season || 0) > 0) params.season = Number(info.season)
  await api.delete(`subscribe/media/${encodeURIComponent(mediaId)}`, {
    ...SILENT,
    params,
  })
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
}

/**
 * 拉当前订阅清单（作品墙左侧「订阅作品」面板的数据源）。
 *
 * 与后端 ``/subscriptions`` 同口径：插件订阅清单 ∪ 宿主 ``djbaike`` 未暂停订阅。
 * 失败返回空列表（面板不出就行，不打扰作品墙）；``engine`` 一并带回 —— 面板的
 * 显隐判断用它（比等配置页加载更快）。
 */
export async function fetchSubscriptions(
  props: { api?: PluginApi },
): Promise<{
  engine: string
  items: SubscriptionRow[]
  default_sites: string
  default_downloader: string
  default_save_path: string
}> {
  const api = resolveApi(props)
  if (!api?.get) {
    return { engine: '', items: [], default_sites: '', default_downloader: '', default_save_path: '' }
  }
  try {
    const data = readData<{
      engine?: string
      items?: SubscriptionRow[]
      default_sites?: string
      default_downloader?: string
      default_save_path?: string
    }>(await api.get(`${API_BASE}/subscriptions`, { ...SILENT }))
    return {
      engine: String(data?.engine || ''),
      items: Array.isArray(data?.items) ? data.items : [],
      default_sites: String(data?.default_sites || ''),
      default_downloader: String(data?.default_downloader || ''),
      default_save_path: String(data?.default_save_path || ''),
    }
  } catch {
    return { engine: '', items: [], default_sites: '', default_downloader: '', default_save_path: '' }
  }
}


/**
 * 订阅一部作品（**插件统一入口**）。
 *
 * 引擎 = ``self``：记进插件订阅清单（不进宿主订阅系统），等订阅搜索自动下载；
 * 引擎 = ``host``：后端转交宿主订阅链（与旧直连行为一致）。返回宿主风格
 * ``{ success, message }``，调用方照实提示。
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

/** 取消一部作品的订阅（插件订阅清单 + 宿主 ``djbaike`` 订阅一起清，后端幂等）。 */
export async function pluginUnsubscribe(
  props: { api?: PluginApi },
  mediaId: string,
): Promise<{ success?: boolean; message?: string }> {
  const api = resolveApi(props)
  if (!api?.post) throw new Error('缺少可用的 api 实例')
  return unwrap<{ success?: boolean; message?: string }>(
    await api.post(`${API_BASE}/unsubscribe`, { media_id: String(mediaId || '') }, { ...SILENT }),
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
    new_window_days: payload?.new_window_days ?? 7,
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
    heat: 0,
    play_count: 0,
    studio: '',
    platform: '',
    kind: '',
    release_date: release,
    actor: '',
    actor_key: '',
    first_seen: '',
    is_new: false,
  })
}

/** 检索返回的演员行 → 演员卡（换源后 MediaInfo 只带身份 + 海报，其余字段留空） */
function normalizeLookupActor(raw: any): ActorCandidate {
  const mediaId = String(raw?.media_id || raw?.actor_id || '')
  return {
    name: String(raw?.title || raw?.name || '').trim(),
    actor_id: mediaId,
    media_id: mediaId,
    // 站内搜索的结果未必与输入完全同名（可能是同名不同人），交给卡片让用户判断
    exact: false,
    profile: String(raw?.poster_path || raw?.poster || '').trim() || undefined,
    works_count: 0,
    job_title: undefined,
    gender: undefined,
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
 * 2026-10-22 换源：新 `/lookup` 回的是**混排的 MediaInfo 列表**（作品 / 演员 /
 * 原著 / 豆瓣条目在一起），这里按 media_id 前缀分流 —— 只收**百科剧集**（duanju /
 * manju / hema / huolong）与**百科人物**（yanyuan / daoyan / bianju）；原著与豆瓣
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
  const payload = unwrap<any>(
    await api.get(
      `plugin/ShortDramaBaikeScraper/lookup?name=${encodeURIComponent(text)}&remote=1`,
      { ...SILENT, timeout: 60_000 },
    ),
  )
  const data = payload?.data
  const rows = Array.isArray(data) ? data : []
  const works: WorkItem[] = []
  const actors: ActorCandidate[] = []
  for (const raw of rows) {
    const mediaId = String(raw?.media_id || '')
    const entity = mediaId.split(':')[0] || ''
    if (['duanju', 'manju', 'hema', 'huolong'].includes(entity)) {
      works.push(normalizeLookupWork(raw, works.length))
    } else if (['yanyuan', 'daoyan', 'bianju'].includes(entity)) {
      actors.push(normalizeLookupActor(raw))
    }
  }
  return { works, actors, source: 'djbaike' }
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
export async function fetchRanks(props: { api?: PluginApi }): Promise<RanksPayload> {
  const api = resolveApi(props)
  if (!api?.get) throw new Error('缺少可用的 api 实例')
  return (
    readData<RanksPayload>(await api.get(`${API_BASE}/ranks`, { ...SILENT })) || {
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
 */
export async function fetchPeople(
  props: { api?: PluginApi },
  kind: string,
  page: number,
): Promise<PeopleListPayload> {
  const api = resolveApi(props)
  if (!api?.get) throw new Error('缺少可用的 api 实例')
  const query = new URLSearchParams()
  query.set('kind', kind)
  query.set('page', String(page))
  return (
    readData<PeopleListPayload>(
      await api.get(`${API_BASE}/people?${query.toString()}`, {
        ...SILENT,
        timeout: 60_000,
      }),
    ) || { kind, page, has_more: false, message: '', people: [] }
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
 * 2026-10-22 换源后来自 ShortDramaBaikeScraper `/lookup` 的 MediaCredit
 * （`url` 是站点人物页地址，人物复合 ID 从地址里抠出来），所以能直接渲染成
 * 演员卡、点了进人物档案页。
 */
export interface WorkSourcePerson {
  name: string
  /** 复合身份（`yanyuan:` / `daoyan:` / `bianju:` + 页面 ID）；抠不出来时为空 */
  media_id: string
  /** 演员是角色名，导演 / 编剧是职务 */
  role: string
  /** 站点分类：`yanyuan` / `daoyan` / `bianju` */
  kind: string
  /** 头像（站点图床绝对地址） */
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
 * 原著信息（ShortDramaBaikeScraper `/novel` 的投影）—— 「原著详情页」的数据源。
 *
 * 2026-10-22 换源：站点不再在剧集记录里带 `adapted_from`，改由数据源的
 * `/novel` 端点单给（传剧 id 或原著 id 均可；页面没标原著时 `data=null`）。
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
 * 2026-10-22 换源后走 ShortDramaBaikeScraper 的两个公开端点：
 * - `/lookup?media_id=` → MediaInfo：导演（含职务）/ 演员（含角色）/ **豆瓣身份** /
 *   站点详情页地址 —— 其中豆瓣身份是关键：后端 `/works/detail` 经模块方法
 *   `recognize_media` 拿到的是宿主 domain 版 MediaInfo（转换时丢 `douban_id`），
 *   这一份把豆瓣补回来；
 * - `/novel?media_id=` → 原著档案 + 全部改编作品（「改编自」块与原著详情页）。
 *
 * 老源 NetSource `/catalog/detail` 里那些站点独有字段（热度 / 播放量 / 收藏 /
 * 状态 / 全片时长 / 出品方 / 平台 / 编剧）scraper 不再提供，一律留空 / 0，
 * 详情页按空值隐藏对应行。任一端点读不到就静默返回空壳，详情页退回第一块数据。
 */
export interface WorkSourceRecord {
  director: WorkSourcePerson[]
  writer: WorkSourcePerson[]
  cast: WorkSourcePerson[]
  /**
   * 热度 / 播放量 / 收藏 —— 只留**站点原文**（「380.14万」/「1016万」/「8.86万」）。
   *
   * 数据源把三项作为分类事实原样提交；展示就照抄原文，不折算、不做数值兜底
   * （2026-10-23 用户口径：数值那份用不上）。空串 = 站点没写这一项。
   */
  heat_text: string
  play_count_text: string
  favorites_text: string
  /** 连载状态（`已完结` / `连载中`…；换源后不再提供） */
  status: string
  /** 全片总时长（分钟）+ 站点原文（换源后不再提供） */
  duration_minutes: number
  duration_text: string
  /** 出品方 / 版权方、播出平台（换源后不再提供） */
  studio: string
  platform: string
  /** 豆瓣条目 ID + 地址（`/lookup` 带回；补后端 domain 转换丢掉的那份） */
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
 * 从数据源 detail_link（`…/yanyuan/info-123.html`）里抠出**人物复合 ID**。
 * `/lookup` 的 MediaCredit 不带 media_id，只带人物页地址 —— 地址形态固定，反推即可。
 */
function personIdFromUrl(url: unknown): string {
  const hit = String(url || '').match(/\/(yanyuan|daoyan|bianju)\/info-(\d+)\.html/)
  return hit ? `${hit[1]}:${hit[2]}` : ''
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

/** ShortDramaBaikeScraper `/novel` 的 NovelData → 「原著详情页」的 AdaptedInfo */
function novelToAdaptedInfo(novel: any): AdaptedInfo | null {
  const title = String(novel?.name || '').trim()
  if (!title) return null
  return {
    title,
    author: String(novel?.author || '').trim(),
    url: String(novel?.detail_url || '').trim(),
    poster: String(novel?.poster || '').trim(),
    media_id: String(novel?.media_id || '').trim(),
    words: parseWordCount(novel?.words),
    genres: [],
    summary: String(novel?.overview || '').trim(),
    works: (Array.isArray(novel?.adaptations) ? novel.adaptations : [])
      .filter((item: any) => String(item?.name || '').trim())
      .map((item: any) => {
        const mediaId = String(item.media_id || '').trim()
        const split = mediaId.split(':')
        return {
          media_id: mediaId,
          title: String(item.name).trim(),
          url:
            split[0] && split[1]
              ? `https://www.duanjubaike.net/${split[0]}/info-${split[1]}.html`
              : '',
          poster: String(item.poster || '').trim(),
          release_date: String(item.date || '').trim(),
          episodes: toNumber(item.episodes),
          genres: [],
        }
      }),
  }
}

/**
 * 读数据源侧的**第二块数据面**（导演 / 演员表 + 豆瓣身份 + 改编自）。
 *
 * 2026-10-22 换源：走 ShortDramaBaikeScraper 的 `/lookup`（MediaInfo：
 * 导演含职务 / 演员含角色 / 豆瓣身份 / 站点详情页地址）+ `/novel`（原著档案 +
 * 全部改编作品）。人物复合 ID 从 detail_link 里反推；scraper 不再提供的
 * 站点字段（热度 / 播放量 / 收藏 / 状态 / 时长 / 出品方 / 平台 / 编剧）留空，
 * 详情页按空值隐藏对应行。任一端点失败静默返回空壳，不影响详情页本身。
 */
export async function fetchWorkSource(
  props: { api?: PluginApi },
  mediaId: string,
): Promise<WorkSourceRecord> {
  const api = resolveApi(props)
  if (!api?.get || !mediaId) return { ...EMPTY_SOURCE }
  try {
    const payload = unwrap<any>(
      await api.get(
        `plugin/ShortDramaBaikeScraper/lookup?media_id=${encodeURIComponent(mediaId)}`,
        { ...SILENT, timeout: 20_000 },
      ),
    )
    const info = payload?.data
    if (!info || typeof info !== 'object') return { ...EMPTY_SOURCE }
    const creditRows = (
      rows: unknown,
      kind: string,
      fallbackRole: string,
    ): WorkSourcePerson[] =>
      (Array.isArray(rows) ? rows : [])
        .filter((item: any) => String(item?.name || '').trim())
        .map((item: any) => ({
          name: String(item.name).trim(),
          media_id: personIdFromUrl(item.url),
          role: String(item.character || item.job || '').trim() || fallbackRole,
          kind,
          // 头像：数据源（MediaCredit）给的是宿主形体 ``profile_path``，同样收
          // ``profile`` / ``poster`` 两种别名 —— 过去这里写死空串，导演/编剧卡
          // 因此永远只能出人形占位（演员走详情端点那一份，同源缺陷在 2026-10-22 一并修）。
          profile: String(
            item.profile_path || item.profile || item.poster || '',
          ).trim(),
        }))
    const director = creditRows(info.directors, 'daoyan', '导演')
    // scraper 的详情没有编剧字段（站点详情页不印）—— 留空，页面退回 MediaInfo 那份
    const writer: WorkSourcePerson[] = []
    const cast = creditRows(info.actors, 'yanyuan', '')
    // 改编自：页面没标原著时 /novel 的 data=null（静默，改编块不渲染）
    let adapted: AdaptedInfo | null = null
    let adaptedTitle = ''
    let adaptedAuthor = ''
    let adaptedUrl = ''
    try {
      const novelPayload = unwrap<any>(
        await api.get(
          `plugin/ShortDramaBaikeScraper/novel?media_id=${encodeURIComponent(mediaId)}`,
          { ...SILENT, timeout: 20_000 },
        ),
      )
      adapted = novelToAdaptedInfo(novelPayload?.data)
      if (adapted) {
        adaptedTitle = adapted.title
        adaptedAuthor = adapted.author
        adaptedUrl = adapted.url
      }
    } catch {
      // 原著端点不可用 / 没标原著：改编块不渲染，不影响详情页
    }
    const doubanId = String(info.douban_id || '').trim()
    // ── 站内统计（2026-10-23 数据源补齐后接上）──
    // 热度走宿主 ``MediaInfo.popularity``（站点「红果平台热度」）；播放 / 收藏宿主
    // 没有专用列，数据源放在分类事实 ``extensions.djbaike.*`` 里（值是已折算的数字）。
    const facts = (info.classification_facts || {}) as Record<string, unknown>
    /**
     * 站点统计的**原文**（「380.14万」/「1016万」/「8.86万」）：数据源把热度 /
     * 播放 / 收藏作为分类事实原样提交（宿主 MediaInfo 没有这三列）。
     * 展示照抄原文，不做折算（数值那份用不上）。
     */
    const factText = (key: string): string => String(facts[key] || '').trim()
    const runtimeMinutes = Number(info.runtime)
    const platformName = String((info.networks || [])[0]?.name || '').trim()
    return {
      director,
      writer,
      cast,
      heat_text: factText('extensions.djbaike.heat'),
      play_count_text: factText('extensions.djbaike.play_count'),
      favorites_text: factText('extensions.djbaike.favorite_count'),
      status: String(info.status || '').trim(),
      duration_minutes: Number.isFinite(runtimeMinutes) && runtimeMinutes > 0 ? runtimeMinutes : 0,
      duration_text: '',
      studio: '',
      platform: platformName,
      douban_id: doubanId,
      douban_url: doubanId ? `https://movie.douban.com/subject/${doubanId}/` : '',
      adapted_title: adaptedTitle,
      adapted_author: adaptedAuthor,
      adapted_url: adaptedUrl,
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
 * 2026-10-22 换源后与剧集侧同一出口：数据源 `/novel` 端点传原著 id 也能取全
 * （含改编作品清单）；取不到就按已有字段照常显示。
 */
export async function fetchAdaptedDetail(
  props: { api?: PluginApi },
  mediaId: string,
): Promise<AdaptedInfo | null> {
  const id = String(mediaId || '').trim()
  const api = resolveApi(props)
  if (!id || !api?.get) return null
  try {
    // 2026-10-22 换源：/novel 传剧 id 或原著 id 均可；页面没标原著时 data=null
    const payload = unwrap<any>(
      await api.get(
        `plugin/ShortDramaBaikeScraper/novel?media_id=${encodeURIComponent(id)}`,
        { ...SILENT, timeout: 20_000 },
      ),
    )
    return novelToAdaptedInfo(payload?.data)
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
 * 宿主 djbaike 订阅），见 ActorWall.loadSubscribed —— 这里不再单独读宿主订阅表：
 * 两条来源各算一套的结果就是「订阅了红心不亮 / 取消点了没反应」（2026-10-22）。
 */
