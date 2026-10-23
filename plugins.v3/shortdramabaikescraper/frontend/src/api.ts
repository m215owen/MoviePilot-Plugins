/**
 * 前端与插件后端通信的唯一出口。
 *
 * 约定（与 shortdramanetsource / shortdramaactorsubscribe 保持同一套）：
 *
 * 1. 优先用宿主注入的 `api` prop（实例作用域，天然适配插件的虚拟分身配置）；
 *    缺失时回退全局 `window.MoviePilotAPI`，再缺失就报错，绝不自己 `fetch`
 *    —— 自己 fetch 会丢掉宿主的 baseURL、鉴权头与错误处理。
 * 2. 宿主 axios 的 baseURL 已含 `api/v1/`，这里只写 `plugin/<PluginID>/<path>`，
 *    **绝不重复写 `/api/v1/`**（会双前缀 404）。
 * 3. 后端统一三段式信封 `{success, message, data}`，由 `unwrap()` 拆封；
 *    面板的「原始数据」区块要看的正是**未拆封**的那一份，所以 `*Raw` 单独导出。
 */

import type {
  BaikePage,
  CacheItems,
  MediaInfo,
  NovelPayload,
  OpResult,
  PersonPayload,
  PluginApi,
  PluginConfig,
  StatusPayload,
} from './types'

/** 插件 ID（= 后端插件类名 = 联邦 `name`），三者必须一致。 */
export const PLUGIN_ID = 'ShortDramaBaikeScraper'

/** 接口路径前缀（相对宿主 baseURL `api/v1/`）。 */
export const API_BASE = `plugin/${PLUGIN_ID}`

/** 最近一次可用的宿主 axios 实例（`Page` 弹窗先挂载、`AppPage` 后挂载时兜底）。 */
let lastApi: PluginApi | null = null

/** 解析可用的 HTTP 客户端。 */
function resolveApi(props: { api?: PluginApi }): PluginApi {
  if (props && props.api) {
    lastApi = props.api
    return props.api
  }
  const globalApi =
    typeof window !== 'undefined'
      ? (window as unknown as { MoviePilotAPI?: PluginApi }).MoviePilotAPI
      : null
  if (globalApi) lastApi = globalApi
  if (lastApi) return lastApi
  throw new Error('宿主未注入 API 实例：面板需在 MoviePilot 插件页面内打开')
}

/**
 * 拆信封：`{success, message, data}` 形态取 `data`，其它一律原样返回。
 *
 * 判据只认 `success` + `data` 两个键，不要求「恰好三个键」：后端 `Response`
 * 将来若多带一个字段（如 `code`），按长度判就会突然不拆了 —— 那会表现为
 * 「接口 200 但面板空白」，极难查。
 */
export function unwrap(payload: any): any {
  return envelopeOf(payload).data
}

/** 这个值是不是后端的 `{success, message, data}` 信封。 */
export function isEnvelope(value: any): boolean {
  return Boolean(
    value &&
      typeof value === 'object' &&
      !Array.isArray(value) &&
      'success' in value &&
      'data' in value,
  )
}

/**
 * 把「宿主给的响应」归一成信封形态。
 *
 * ⚠️ 宿主注入的 `api` 到底有没有替我们拆过信封，**不能假设**：
 * 有的版本 `api.get()` 返回 AxiosResponse（`response.data` 才是信封），
 * 有的封装直接返回信封或直接返回业务 `data`。所以统一走这里：
 *
 * * 是信封 → 用它的 `data` / `success` / `message`；
 * * 不是信封（说明调用方拿到的**已经是** `data`）→ 整个值就是 `data`。
 *
 * 少了这层兼容，就会出现「`/lookup` 明明 200、返回 14 条，面板却说没有结果」——
 * 因为 `body.data` 在「已解包」的宿主上取到的是 `undefined`。
 */
export function envelopeOf(body: any): { success?: boolean; message?: string; data: any } {
  if (isEnvelope(body)) {
    return body as { success?: boolean; message?: string; data: any }
  }
  return { success: undefined, message: undefined, data: body }
}

/** 取业务数据（等价于 `unwrap` 的实现体，保留具名导出便于阅读调用点）。 */
export function pickData(body: any): any {
  return envelopeOf(body).data
}

/** GET：返回**原样响应体**（不拆信封）。 */
async function getRaw(
  props: { api?: PluginApi },
  path: string,
  params?: Record<string, any>,
): Promise<any> {
  const api = resolveApi(props)
  if (!api.get) throw new Error('宿主 API 缺少 get 方法')
  // feedback:'silent'：面板的失败一律自己用 error 区展示（v-alert），绝不让宿主
  // 对 success=false 的信封弹全局 toast —— 2026-10-22 实锤：/novel 对无原著的剧
  // 返回「页面未标注原著」，probeNovel 每次打开作品都会调它，宿主就在右下角弹，
  // 表现成「打开作品就报错」。
  const response = await api.get(`${API_BASE}${path}`, { params, feedback: 'silent' })
  // 宿主若把 body 本身当返回值（而不是 AxiosResponse），`response.data` 已是业务数据 ——
  // 这里再剥一层就永久丢掉信封，「原始响应」区块就再也看不到 success / message。
  if (isEnvelope(response)) return response
  return response?.data ?? response
}

/** GET（拆信封）。 */
async function get(
  props: { api?: PluginApi },
  path: string,
  params?: Record<string, any>,
): Promise<any> {
  return unwrap(await getRaw(props, path, params))
}

/** POST（查询串走 `params`，如 `deleteBaike` 没有查询串时也可省略）。 */
async function post(
  props: { api?: PluginApi },
  path: string,
  params?: Record<string, any>,
): Promise<any> {
  const api = resolveApi(props)
  if (!api.post) throw new Error('宿主 API 缺少 post 方法')
  const response = await api.post(`${API_BASE}${path}`, undefined, { params, feedback: 'silent' })
  return unwrap(response?.data ?? response)
}

/** DELETE（axios 的第二参数是 config，查询串要放进 `params`）。 */
async function del(
  props: { api?: PluginApi },
  path: string,
  params?: Record<string, any>,
): Promise<any> {
  const api = resolveApi(props)
  if (!api.delete) throw new Error('宿主 API 缺少 delete 方法')
  const response = await api.delete(`${API_BASE}${path}`, { params, feedback: 'silent' })
  return unwrap(response?.data ?? response)
}

/** PUT（body 是 JSON）。宿主若直接给信封，先原地取，别再剥一层。 */
async function put(
  props: { api?: PluginApi },
  path: string,
  payload: unknown,
): Promise<any> {
  const api = resolveApi(props)
  if (!api.put) throw new Error('宿主 API 缺少 put 方法')
  const response = await api.put(`${API_BASE}${path}`, payload)
  if (isEnvelope(response)) return unwrap(response)
  return unwrap(response?.data ?? response)
}

// ── 状态 ───────────────────────────────────────────────────────────────
/** `GET /status`：启用状态 + ID 库计数 + 缓存 region 清单。 */
export async function fetchStatus(props: { api?: PluginApi }): Promise<StatusPayload> {
  return (await get(props, '/status')) as StatusPayload
}

// ── ID 库 ──────────────────────────────────────────────────────────────
/**
 * `GET /baike/list`：ID 库分页（返回原始 4 列）。
 *
 * 搜索是**服务端**做的：库只增不减，一次拿全不现实；`q` 与 `entity` 都进 SQL
 * 条件，所以搜到的永远是全库范围，不会被分页截断。
 */
export async function fetchBaikeList(
  props: { api?: PluginApi },
  params: { q?: string; entity?: string; offset?: number; limit?: number } = {},
): Promise<BaikePage> {
  return (await get(props, '/baike/list', params)) as BaikePage
}

/** `DELETE /baike/del`：删单条 ID（后端会联动删它的详情 / 人物缓存）。 */
export async function deleteBaike(props: { api?: PluginApi }, mediaId: string): Promise<OpResult> {
  return (await del(props, '/baike/del', { media_id: mediaId })) as OpResult
}

/** `POST /baike/clear`：清空整个 ID 库（危险）。 */
export async function clearBaike(props: { api?: PluginApi }): Promise<OpResult> {
  return (await post(props, '/baike/clear')) as OpResult
}

// ── 缓存 ───────────────────────────────────────────────────────────────
/** `GET /cache/items`：枚举某 region 的原始键值（面板「看原始数据」）。 */
export async function fetchCacheItems(
  props: { api?: PluginApi },
  region: string,
  limit = 100,
  search = '',
): Promise<CacheItems> {
  return (await get(props, '/cache/items', { region, limit, search })) as CacheItems
}

/** `DELETE /cache/del`：删单条缓存（`region` + `key` 两个都要，key 只在区内唯一）。 */
export async function deleteCacheItem(
  props: { api?: PluginApi },
  region: string,
  key: string,
): Promise<OpResult> {
  return (await del(props, '/cache/del', { region, key })) as OpResult
}

/** `POST /cache/clear`：清空本插件全部 region（**不动 ID 库**）。 */
export async function clearCache(props: { api?: PluginApi }): Promise<OpResult> {
  return (await post(props, '/cache/clear')) as OpResult
}

// ── 查询 ───────────────────────────────────────────────────────────────
/** `GET /lookup?media_id=`：按 media_id 取单条详情（也接受裸豆瓣数字 id）。 */
export async function lookupByMediaId(
  props: { api?: PluginApi },
  mediaId: string,
): Promise<MediaInfo | null> {
  return (await get(props, '/lookup', { media_id: mediaId })) as MediaInfo | null
}

/** `GET /lookup?name=`：按名搜作品 / 演员候选（`remote=1` 才联网补全）。 */
export async function lookupByName(
  props: { api?: PluginApi },
  name: string,
  options: { remote?: boolean; type?: string } = {},
): Promise<MediaInfo[]> {
  const data = await get(props, '/lookup', {
    name,
    remote: options.remote ? 1 : 0,
    type: options.type || '',
  })
  return Array.isArray(data) ? (data as MediaInfo[]) : []
}

/** `GET /lookup` 的原始响应（含信封，供「原始数据」展开）。 */
export async function lookupRaw(
  props: { api?: PluginApi },
  params: { media_id?: string; name?: string; remote?: number; type?: string },
): Promise<any> {
  return getRaw(props, '/lookup', params)
}

/**
 * `GET /person?media_id=`：人物档案 + 作品清单（演员 / 导演 / 编剧）。
 *
 * 人物不是 MediaInfo，`/lookup?media_id=` 遇到人物会明确回
 * 「人物档案请用 /person 查询」，所以面板必须走这里。
 */
export async function fetchPerson(
  props: { api?: PluginApi },
  mediaId: string,
): Promise<{ person: PersonPayload | null; message: string }> {
  const body = await getRaw(props, '/person', { media_id: mediaId })
  const payload = envelopeOf(body)
  const data = payload.data as PersonPayload | null
  return {
    person: data && typeof data === 'object' ? data : null,
    message: String(payload.message || ''),
  }
}

/**
 * `GET /novel`：原著档案 + 改编作品清单。
 *
 * 传**剧** media_id（后端取详情里标注的原著）或**原著** media_id 均可；
 * 页面没标原著时 `novel` 为 null（面板据此隐藏「改编档案」按钮）。
 */
export async function fetchNovel(
  props: { api?: PluginApi },
  mediaId: string,
): Promise<{ novel: NovelPayload | null; message: string }> {
  const body = await getRaw(props, '/novel', { media_id: mediaId })
  const payload = envelopeOf(body)
  const data = payload.data as NovelPayload | null
  return {
    novel: data && typeof data === 'object' ? data : null,
    message: String(payload.message || ''),
  }
}

/**
 * 海报地址 → 浏览器可直接加载的 URL（**只给面板看**，不进 NFO / 刮削）。
 *
 * * 豆瓣图床只认 `Referer: https://movie.douban.com/`，浏览器 `<img>` 直连是
 *   403 / 418（空白），所以豆瓣地址统一改写成**宿主的图片代理**
 *   `/api/v1/system/img/0?imgurl=…&cache=1` —— 宿主取图时自带豆瓣 Referer
 *   与磁盘缓存。代理端点的鉴权是宿主的 `resource_token` cookie，面板同源天然带着。
 * * 站点图（`img.duanjubaike.net`）与 TMDB 图可直连，原样返回，不多绕一跳。
 * * 已是相对路径 / data URI 的不再套代理。
 */
export function proxyImage(url?: string | null): string {
  const text = String(url || '').trim()
  if (!text || text.startsWith('/') || text.startsWith('data:')) return text
  let host = ''
  try {
    host = new URL(text).hostname.toLowerCase()
  } catch {
    return text
  }
  if (host === 'doubanio.com' || host.endsWith('.doubanio.com')) {
    return `/api/v1/system/img/0?imgurl=${encodeURIComponent(text)}&cache=1`
  }
  return text
}

// ── 配置（Vue 配置页 `./Config`） ─────────────────────────────────────
/**
 * `GET /config`：读当前配置。
 *
 * 返回的是**归一后**的配置（后端 `_live_config()` 会用默认值兜底），
 * 所以表单里看到的永远是"实际生效的那份"。
 */
export async function fetchConfig(props: { api?: PluginApi }): Promise<PluginConfig> {
  return (await get(props, '/config')) as PluginConfig
}

/**
 * `PUT /config`：保存配置（**整体替换**语义）。
 *
 * ⚠️ 后端 `api_update_config` 是「缺失键取默认值」，所以这里必须把**完整**的
 * 配置对象发回去。
 */
export async function saveConfig(
  props: { api?: PluginApi },
  payload: PluginConfig,
): Promise<PluginConfig> {
  return (await put(props, '/config', payload)) as PluginConfig
}
