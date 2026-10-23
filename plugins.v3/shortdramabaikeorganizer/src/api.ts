/**
 * 短剧百科整理 —— 前端与后端之间的唯一通道（2026-10-22 重写版）。
 *
 * 三条约定：
 *  1. 宿主注入的 `api` 是 axios 实例，baseURL 已经是 `api/v1/`，所以这里只写
 *     `plugin/<插件类名>/<路径>`，多写一层 `api/v1` 会 404。
 *  2. 宿主的 axios 有的版本已解出 `response.data`，有的没解 —— 统一交给 `unwrap`
 *     按 axios 特征判断，不看业务字段名（业务载荷顶层也叫 data）。
 *  3. 后端统一返回 `{success, message, data}` 信封，这里只把 `data` 交出去；
 *     失败直接抛 Error，由组件显示。
 */

/** 插件类名（必须与后端 plugin_name 对应的类名一致） */
export const PLUGIN_ID = 'ShortDramaBaikeOrganizer'

/** 接口根（相对 baseURL） */
const API_ROOT = `plugin/${PLUGIN_ID}`

/** 宿主注入的 axios 最小面 */
export interface HostApi {
  get: (url: string, config?: Record<string, unknown>) => Promise<unknown>
  post: (url: string, data?: unknown, config?: Record<string, unknown>) => Promise<unknown>
}

/** 插件配置（与后端 DEFAULT_CONFIG 的键一一对应） */
export interface OrganizerConfig {
  enabled: boolean
  source_dirs: string[]
  library_dir: string
  scan_depth: number
  transfer_type: string
  episode_width: number
  auto_rename_episode: boolean
  scrape_enabled: boolean
  force_transfer: boolean
  notify: boolean
  monitor_enabled: boolean
  monitor_mode: string
  monitor_interval: number
  force_reorganize: boolean
}

/** `/status` 载荷 */
export interface OrganizerStatus {
  enabled: boolean
  source: string
  source_provider: string
  source_ready: boolean
  library_dir: string
  source_dirs: string[]
  transfer_type: string
  /** 集号补零位数（整理详情/预演里显示 E018 还是 E18 由它决定，默认 2） */
  episode_width: number
  scrape_enabled: boolean
  /** 强制整理：开 = 无视系统整理历史，命中过的文件也重新整理 */
  force_transfer: boolean
  monitor_enabled: boolean
  history_backend: string
  store_available: boolean
  note: string
}

/** 单条扫描结果 */
export interface ScanItem {
  drama: string
  path: string
  state: 'pending' | 'unrecognized'
  title: string
  year: number | null
  media_id: string
  reason: string
  /** 目标剧目录（库目录/剧名 (年)），识别成功才有 */
  dest_dir?: string
  /** 目标目录当前是否存在 */
  dest_exists?: boolean
  /** 目标是否已刮削（有 nfo/海报） */
  scraped?: boolean
  /** 目标下是否已有整理历史记录（不论谁写的） */
  transferred?: boolean
}

/** 扫描进度快照 */
export interface ScanSnapshot {
  state: 'idle' | 'running' | 'stopping' | 'stopped' | 'done' | 'error'
  total: number
  done: number
  current: string
  message: string
  counts: { pending: number; unrecognized: number }
  items: ScanItem[]
}

/** 记录库一条剧记录（面板「记录」列表与四类统计的数据源） */
export interface StoreRecord {
  id: number
  drama: string
  path: string
  state: 'recognized' | 'unrecognized'
  media_id: string
  title: string
  year: number | null
  dest_dir: string
  dest_exists: boolean
  scraped: boolean
  transferred: boolean
  done_count: number
  /** 剧的总集数（百科词条带出来的；旧行/未重扫为 0） */
  episode_count?: number
  /** 已整理的不同集数（按 SxxEyy 去重；旧行面板会自动补算） */
  organized_episodes?: number
  /** 手动标记整理完成（扫描会跳过这类目录） */
  completed?: boolean
  /** 整理完成 = 手动标记过，或已整理集数与数据源集数对齐（后端推导） */
  done?: boolean
  reason: string
  updated_at: number
}

/** 记录库统计（面板六张卡：已识别 = 待整理 + 整理中 + 整理完成，另有未识别 / 未刮削） */
export interface StoreStats {
  recognized: number
  /** 待整理 = 已识别但还没整理过（目标目录尚不存在） */
  pending: number
  /** 整理中 = 搬过但集数还没对齐（原「已整理」口径） */
  transferred: number
  completed: number
  unrecognized: number
  unscraped: number
}

/** `/store` 载荷 */
export interface StoreSnapshot {
  available: boolean
  stats: StoreStats
  items: StoreRecord[]
}

/** 目录选项（下拉用） */
export interface DirOption {
  title: string
  value: string
}

/** 目录浏览结果 */
export interface BrowseResult {
  path: string
  parent: string
  entries: DirOption[]
}

/** 整理结果（单剧同步整理的返回） */
export interface OrganizeResult {
  done?: number
  skipped?: number
  failed?: number
  error?: string
  note?: string
  drama?: string
  dest_dir?: string
}

/** 一部剧的整理结果（整理快照 details 的元素，也是「整理详情」窗口的行） */
export interface OrganizeDetail {
  drama: string
  path: string
  title: string
  dest_dir: string
  done: number
  skipped: number
  failed: number
  unrecognized: boolean
  organized: boolean
  error: string
  note: string
}

/** 整理任务快照（GET /organize） */
export interface OrganizeSnapshot {
  state: 'idle' | 'running' | 'stopping' | 'stopped' | 'done' | 'error'
  /** scan = 还在识别阶段；organize = 已在搬运阶段 */
  phase: '' | 'scan' | 'organize'
  total: number
  done: number
  current: string
  message: string
  counts: { dramas: number; done: number; skipped: number; failed: number; unrecognized: number }
  details: OrganizeDetail[]
}

/** 启动/停止整理的返回（后端包了一层） */
export interface OrganizeAction {
  started?: boolean
  stopped?: boolean
  message?: string
  organize?: OrganizeSnapshot
}

/** 系统整理历史里的一条文件级记录（「整理详情」窗口的数据源） */
export interface HistoryRecord {
  id: number | null
  title: string
  year: string
  src: string
  src_name: string
  dest: string
  dest_name: string
  mode: string
  seasons: string
  episodes: string
  media_source: string
  media_id: string
  status: boolean
  date: string
}

/** 整理详情 · 单剧（文件级整理记录） */
export interface DramaDetails {
  scope: 'drama'
  dest_dir: string
  count: number
  items: HistoryRecord[]
}

/** 整理详情 · 本次整理运行（逐部剧结果） */
export interface RunDetails {
  scope: 'run'
  state: string
  message: string
  counts: { dramas: number; done: number; skipped: number; failed: number; unrecognized: number }
  details: OrganizeDetail[]
}

/** 整理详情（/details 的两种形态） */
export type OrganizeDetails = DramaDetails | RunDetails

/** 整理预演里的一条计划 */
export interface PreviewPlan {
  src: string
  src_name: string
  target: string
  target_name: string
  episode: number
}

/** 整理预演（重新整理前先看清楚会搬哪些文件） */
export interface OrganizePreview {
  exists: boolean
  library_dir: string
  title: string
  year: number | null
  count: number
  items: PreviewPlan[]
}

/** POST /organize 的参数（全部可选：不传 path = 后台整理全部） */
export interface OrganizeParams {
  path?: string
  force?: string
  media_id?: string
  title?: string
  year?: string
  /** 人工指定身份时带上搜索候选的集数（缺失会导致记录「共 X 集」空） */
  episode_count?: string
  library_dir?: string
  transfer_type?: string
}

/** 扫描动作的返回（后端包了一层：`{started/stopped, message, scan: <快照>}`） */
export interface ScanAction {
  started?: boolean
  stopped?: boolean
  message?: string
  scan?: ScanSnapshot
}

/** 百科搜索候选（未识别目录人工处理用） */
export interface SearchCandidate {
  media_id: string
  title: string
  year: number | null
  episode_count: number | null
}

/** 取宿主注入的 api 实例：优先 props，其次全局，最后 null */
export function hostApi(props?: { api?: HostApi }): HostApi | null {
  const injected = props?.api
  if (injected && typeof injected.get === 'function') return injected
  const globalApi =
    typeof window !== 'undefined'
      ? ((window as unknown as { MoviePilotAPI?: HostApi }).MoviePilotAPI ?? null)
      : null
  return globalApi && typeof globalApi.get === 'function' ? globalApi : null
}

/** 是否 axios 响应包装（只认 status/statusText/headers 三个特征） */
function isAxiosResponse(value: unknown): boolean {
  if (!value || typeof value !== 'object') return false
  const record = value as Record<string, unknown>
  return (
    typeof record.status === 'number' &&
    typeof record.statusText === 'string' &&
    !!record.headers &&
    typeof record.headers === 'object'
  )
}

/** 剥掉 axios 外壳与 `{success,message,data}` 信封 */
function extract(value: unknown): unknown {
  const body = isAxiosResponse(value) ? (value as Record<string, unknown>).data : value
  if (body && typeof body === 'object' && 'success' in body) {
    const envelope = body as { success?: boolean; message?: string; data?: unknown }
    if (envelope.success === false) {
      throw new Error(envelope.message || '后端返回失败')
    }
    return envelope.data
  }
  return body
}

async function getJson<T>(api: HostApi, path: string, params?: Record<string, unknown>): Promise<T> {
  const response = await api.get(`${API_ROOT}${path}`, params ? { params } : undefined)
  return extract(response) as T
}

async function postJson<T>(
  api: HostApi,
  path: string,
  params?: Record<string, unknown>,
): Promise<T> {
  // 后端 handler 的形参是普通 str/int（FastAPI 只从 query 取），所以参数走 params
  const response = await api.post(`${API_ROOT}${path}`, undefined, params ? { params } : undefined)
  return extract(response) as T
}

/**
 * 从任意嵌套形态里捞出扫描快照。
 *
 * 宿主 axios 的拦截器不同版本解包深度不一样（原始 response / `response.data` /
 * `response.data.data` 都见过），POST 与 GET 还可能不一致。与其猜一层，不如按
 * **形状**递归找：只要对象里有 `state` + `total` + `items` 就当快照。
 */
export function pickScan(value: unknown, depth = 0): ScanSnapshot | null {
  if (!value || typeof value !== 'object' || depth > 4) return null
  const record = value as Record<string, unknown>
  if (
    typeof record.state === 'string' &&
    'total' in record &&
    Array.isArray(record.items)
  ) {
    return record as unknown as ScanSnapshot
  }
  for (const key of ['scan', 'data', 'result', 'payload']) {
    const found = pickScan(record[key], depth + 1)
    if (found) return found
  }
  return null
}

/**
 * 从任意嵌套形态里捞出整理快照。
 *
 * 与 `pickScan` 同理（宿主 axios 拦截器解包深度各版本不一），按**形状**递归找：
 * 有 `state` + `total` + `details` 就是整理快照（扫描快照是 `items`，靠这个区分）。
 */
export function pickOrganize(value: unknown, depth = 0): OrganizeSnapshot | null {
  if (!value || typeof value !== 'object' || depth > 4) return null
  const record = value as Record<string, unknown>
  if (
    typeof record.state === 'string' &&
    'total' in record &&
    Array.isArray(record.details)
  ) {
    return record as unknown as OrganizeSnapshot
  }
  for (const key of ['organize', 'data', 'result', 'payload']) {
    const found = pickOrganize(record[key], depth + 1)
    if (found) return found
  }
  return null
}

export const backend = {
  status: (api: HostApi) => getJson<OrganizerStatus>(api, '/status'),
  scan: (api: HostApi) => getJson<ScanSnapshot>(api, '/scan'),
  scanStart: (api: HostApi) => postJson<ScanAction>(api, '/scan/start'),
  scanStop: (api: HostApi) => postJson<ScanAction>(api, '/scan/stop'),
  /**
   * 整理入口。
   *
   * ⚠️ 不传 `path` 时后端是**后台任务**（立刻返回），真正结果要轮询
   * `organizeProgress`。曾经是同步跑完全部 → 反代超时 → 前端只看到 502。
   */
  organize: (api: HostApi, params: OrganizeParams = {}) =>
    postJson<OrganizeResult & OrganizeAction>(api, '/organize', params as Record<string, unknown>),
  /** 整理进度快照（后台整理时轮询） */
  organizeProgress: (api: HostApi) => getJson<OrganizeSnapshot>(api, '/organize'),
  /** 启动后台整理全部 */
  organizeStart: (api: HostApi, force = false) =>
    postJson<OrganizeAction>(api, '/organize/start', { force: force ? '1' : '0' }),
  /** 停止后台整理 */
  organizeStop: (api: HostApi) => postJson<OrganizeAction>(api, '/organize/stop'),
  /** 整理预演：按指定身份/目标库列出将整理哪些文件（media_id 用于从源数据取季号） */
  preview: (api: HostApi, params: { path: string; title?: string; year?: string; library_dir?: string; media_id?: string }) =>
    getJson<OrganizePreview>(api, '/preview', params as Record<string, unknown>),
  /**
   * 整理详情：传 `path`/`dest` 拿单剧文件级记录；都不传拿本次整理运行详情。
   */
  details: (api: HostApi, params: { path?: string; dest?: string } = {}) =>
    getJson<OrganizeDetails>(api, '/details', params as Record<string, unknown>),
  /** 按关键词搜百科候选（人工指定身份用） */
  search: (api: HostApi, keyword: string, limit = 10) =>
    getJson<{ count: number; items: SearchCandidate[] }>(api, '/search', { keyword, limit }),
  /** 记录库：统计 + 全部剧记录（整理中 / 整理完成分开数） */
  store: (api: HostApi) => getJson<StoreSnapshot>(api, '/store'),
  /** 手动标记 / 取消「整理完成」（value=0 取消） */
  storeComplete: (api: HostApi, path: string, value = '1') =>
    postJson<{ success: boolean; message?: string }>(api, '/store/complete', { path, value }),
  /** 立即刮削（传源目录 path，或直接传目标目录 dest） */
  scrape: (api: HostApi, params: { path?: string; dest?: string }) =>
    postJson<{ success: boolean; scraped?: boolean; skipped?: boolean; message?: string; error?: string; dest_dir?: string }>(
      api,
      '/scrape',
      params,
    ),
  /** 删除一条记录库记录 */
  storeDelete: (api: HostApi, path: string) =>
    postJson<{ success: boolean; message?: string }>(api, '/store/delete', { path }),
  /** 清空记录库 */
  storeClear: (api: HostApi) =>
    postJson<{ success: boolean; message?: string; data?: { count: number } }>(api, '/store/clear'),
  browse: (api: HostApi, path = '') => getJson<BrowseResult>(api, '/dirs/browse', { path }),
  dirOptions: (api: HostApi) =>
    getJson<{ sources: DirOption[]; libraries: DirOption[] }>(api, '/dirs/options'),
}
