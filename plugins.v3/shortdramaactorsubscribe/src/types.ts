/**
 * 短剧演员订阅 —— 前后端共享的数据结构定义。
 *
 * 字段与后端 `ShortDramaActorSubscribe._default_config()` / `api_status()` /
 * `api_options()` 的返回体保持一致；改后端字段时这里要同步。
 */

/** 插件配置（对应后端 `_default_config()` / `_live_config()`） */
export interface PluginConfig {
  /** 是否启用插件 */
  enabled: boolean
  /** 保存后立即执行一轮（一次性语义，落盘时会自动清掉） */
  onlyonce: boolean
  /** 订阅演员：逗号 / 换行 / 分号分隔，可填姓名、豆瓣ID、TMDB ID 或豆瓣人物主页链接 */
  actors: string
  /** 搜索站点 ID 列表（不选则无法搜索） */
  sites: number[]
  /** 优先在站点的「短剧」分类内搜索（站点没有该分类时自动退化为全站搜索） */
  prefer_short_drama_category: boolean
  /** 下载器名称，空串表示跟随宿主默认 */
  downloader: string
  /** 下载目录（既用于提交下载，也作为整理时的扫描目录） */
  download_path: string
  /** 媒体库根目录（整理后放到 <该目录>/短剧/剧名 (年份)/） */
  library_path: string
  /** 整理方式：link（硬链接）/ copy / move */
  transfer_type: string
  /** 订阅轮询间隔（小时） */
  interval_hours: number
  /**
   * 定时轮询是否顺带自动下载。**默认 false（订阅制）**：
   * 轮询只做发现，下载由用户在作品墙点「订阅」触发。
   * 打开后会把快照里所有没下过的作品批量提交下载，慎用。
   */
  auto_download: boolean
  /**
   * 是否用「短剧百科」作为作品展示源（跨插件调用 ShortDramaBaikeSource），默认 true。
   * 开启后作品墙只展示百科里有的作品（TMDB/豆瓣整条跳过）；关闭回到双源并集。
   */
  use_baike: boolean
  /** 演员作品快照的整体刷新间隔（小时，默认 24）：期间轮询直接用缓存，省豆瓣额度 */
  snapshot_hours: number
  /** 解析失败后的重试间隔（分钟，默认 20）：登录态恢复后能很快自愈 */
  retry_minutes: number
  /** 是否启用整理入库 */
  organize_enabled: boolean
  /** 整理扫描间隔（分钟） */
  organize_interval_minutes: number
  /** 是否发送系统通知 */
  notify: boolean
  /** 手工粘贴的豆瓣 Cookie（留空 = 自动复用宿主 CookieCloud 的豆瓣登录态） */
  douban_cookie: string
  /** 请求豆瓣 / TMDB 时是否走宿主配置的代理 */
  proxy: boolean
  /** 每位演员保留的作品数上限（1-10，豆瓣作品集接口不支持翻页） */
  max_works: number
  /** 是否在 MoviePilot 主界面侧栏展示入口 */
  sidebar_nav: boolean
  /** 运行时回显：当前 Cookie 来源 manual / cookiecloud / none（只读） */
  douban_cookie_source?: string
}

/** 账本条目（已提交下载的一部剧） */
export interface LedgerEntry {
  /** 去重键：`归一化剧名|年份` */
  key: string
  /** 中文剧名 */
  title: string
  /** 年份，可能为空（短剧站点普遍缺年份） */
  year: string
  /** 集数（仅信息展示，不参与匹配与去重） */
  episodes?: number
  /** 命中站点名 */
  site_name?: string
  /** 种子原名（站点上多为拼音），整理时用于定位下载目录 */
  torrent_title?: string
  /** 下载器返回的哈希 */
  torrent_hash?: string
  /** 发现来源：douban / tmdb */
  media_source?: string
  /** 发现来源里的作品 ID */
  media_id?: string
  /** 该作品挂在哪位演员名下 */
  actor?: string
  /** 同剧命中的资源条数（择优前的候选规模） */
  alternatives?: number
  /** 是否已整理入库 */
  organized?: boolean
  /** 整理后的路径 */
  organized_path?: string
  /** 下载提交时间 */
  time?: string
}

/** 未命中冷却条目（搜过但站点没有资源的剧） */
export interface CooldownEntry {
  key: string
  title: string
  year: string
  actor: string
  /** 距冷却结束还有多少分钟 */
  remaining_minutes: number
}

/** 演员参演作品（发现层产出的候选身份） */
export interface ActorWork {
  title: string
  year?: string
  alt_title?: string
  /** 发现来源：douban / tmdb */
  source?: string
  media_id?: string
  /** 媒体类型：电影 / 电视剧 */
  type?: string
  /** 归属演员名（由快照聚合而来） */
  actor?: string
  /** 海报地址（豆瓣为 cover.large.url，TMDB 为 image.tmdb.org 的 w300 地址） */
  poster?: string
  /** 评分（豆瓣 0-10 / TMDB 0-10），0 表示无评分 */
  vote?: number
}

/** 演员快照 */
export interface ActorRecord {
  /** 配置项原文（姓名或 ID） */
  key: string
  /** 解析出的演员名 */
  name: string
  /** 豆瓣人物 ID */
  douban_id?: string
  /** TMDB 人物 ID */
  tmdb_id?: string
  /** 作品列表 */
  works?: ActorWork[]
  /** 解析错误（豆瓣限流 / TMDB 未配置等）。后端仍会给全量原因，
   *  面板只在 tooltip 里展示，不再逐条铺开 —— 临时性失败等下一轮自动重试。 */
  errors?: string[]
  /**
   * 后端归一出来的展示状态：
   * - 缺省 / 空串：正常（拿到了作品）
   * - `waiting`：本轮没拿到作品且原因是临时的 → 等下一轮自动重试
   * - `empty`：豆瓣确实没有影视条目（稳定结果，非故障）
   */
  state?: string
  /** 上次解析时间 */
  time?: string
}

/** 运行概览统计 */
export interface StatusSummary {
  actor_count: number
  candidate_count: number
  downloaded_count: number
  organized_count: number
  cooldown_count: number
  /** 上次运行时间，形如 `2026-10-13 20:15:00` */
  last_run: string
  /** 上轮耗时（秒） */
  elapsed: number
}

/** 最近一轮的执行结果 */
export interface RunResult {
  success?: boolean
  message?: string
}

/** 后端 GET /status 的返回体 */
export interface StatusPayload {
  enabled: boolean
  /** 是否有一轮正在执行（手动触发后用它轮询） */
  running: boolean
  sidebar_nav: boolean
  actors: Record<string, ActorRecord>
  stats: Record<string, unknown>
  ledger: LedgerEntry[]
  cooldown: CooldownEntry[]
  summary: StatusSummary
  last_result: RunResult
}

/** 下拉候选：站点 */
export interface SiteOption {
  title: string
  value: number
}

/** 下拉候选：下载器（`value` 即提交下载时要写的名字） */
export interface DownloaderOption {
  title: string
  value: string
  /** 是否是宿主下载器配置里被标为「默认」的那个 */
  default?: boolean
}

/** 下拉候选：整理方式 */
export interface TransferTypeOption {
  title: string
  value: string
}

/**
 * 宿主「目录管理」里的一项（下载目录与媒体库目录成对）。
 *
 * 来源与宿主前端一致（`DirectoryHelper`），因此插件里选的路径就是宿主自己
 * 下载/整理时用的那一份，不需要用户再手抄。
 */
export interface DirectoryOption {
  /** 展示文案，形如 `短剧（/vol00/…/短剧/）` */
  title: string
  /** 下载目录真实路径，选中即写入配置的 `download_path` */
  value: string
  name: string
  download_path: string
  /** 该目录对应的媒体库根目录（可能为空） */
  library_path: string
  /** 电视 / 电影 / 音乐 */
  media_type: string
  /** 分类，如 `短剧` */
  media_category: string
  /** 名字/分类/路径任一含「短剧」（前端用来高亮推荐项） */
  is_short_drama: boolean
}

/** 系统侧推荐初值（配置页「一键采用」用） */
export interface OptionsDefaults {
  /** 宿主系统设置里被标为默认的下载器名 */
  downloader: string
  /** 优先推荐的下载目录（通常就是「短剧」那个） */
  directory: string
  /** 上面对应目录的媒体库根目录 */
  library_path: string
  /** 上面对应目录的名字 */
  directory_name: string
}

/** 后端 GET /options 的返回体 */
export interface OptionsPayload {
  sites: SiteOption[]
  downloaders: DownloaderOption[]
  transfer_types: TransferTypeOption[]
  /** 宿主「目录管理」里的目录清单（下载 + 媒体库） */
  directories: DirectoryOption[]
  /** 系统侧推荐初值 */
  defaults: OptionsDefaults
}

/** 作品墙里的状态 */
export type WorkState = 'pending' | 'subscribed' | 'cooling' | 'downloaded' | 'organized'

/** 作品墙的一条：演员参演作品 + 它当前的处理状态 */
export interface WorkItem {
  /** 账本键 `归一化剧名|年份`，订阅按钮回传的就是它 */
  key: string
  title: string
  year?: string
  alt_title?: string
  /** 电影 / 电视剧 */
  type?: string
  /** 发现来源：douban / tmdb */
  source?: string
  media_id?: string
  /** 归属演员名 */
  actor?: string
  /** 海报地址；旧快照没有该字段，卡片显示占位图 */
  poster?: string
  /** 评分，0 表示无评分（卡片上不展示） */
  vote?: number
  state: WorkState
  /** 是否已订阅（订阅中：插件每轮都会重试，直到下到为止） */
  subscribed?: boolean
  /** 冷却剩余分钟（state = cooling 时有意义） */
  remaining_minutes?: number
  /** 已下载时有：命中站点 */
  site_name?: string
  /** 已下载时有：种子原名 */
  torrent_title?: string
  /** 已下载时有：提交时间 */
  time?: string
}

/** 作品墙顶部统计 */
export interface WorksSummary {
  total: number
  /** 还没订阅、也没下载（点「订阅」才下） */
  pending: number
  /** 已订阅但还没下到（插件每轮重试） */
  subscribed: number
  cooling: number
  downloaded: number
}

/** 后端 GET /works 的返回体 */
export interface WorksPayload {
  items: WorkItem[]
  summary: WorksSummary
  /** 作品快照的刷新时间 */
  refreshed_at: string
  /** 是否有后台任务在跑（刷新作品后用它轮询） */
  running: boolean
  /** 演员与站点是否都已配置（未配置时作品墙只会是空态） */
  configured: boolean
  actors: string[]
  actor_count: number
}

/** 演员搜索候选（配置页「搜索演员」用） */
export interface ActorCandidate {
  /** douban / tmdb */
  source: string
  /** 该来源下的人物 ID，可直接填进演员列表 */
  id: string
  name: string
  original_name?: string
  avatar?: string
}

/** 后端统一响应体 */
export interface ApiResult<T = unknown> {
  success: boolean
  message?: string
  data?: T
}

/** 宿主注入的 axios 实例（baseURL 已为 api/v1/） */
export interface PluginApi {
  get<T = any>(url: string, config?: Record<string, unknown>): Promise<T>
  post<T = any>(url: string, data?: unknown, config?: Record<string, unknown>): Promise<T>
  put<T = any>(url: string, data?: unknown, config?: Record<string, unknown>): Promise<T>
  delete<T = any>(url: string, config?: Record<string, unknown>): Promise<T>
}
