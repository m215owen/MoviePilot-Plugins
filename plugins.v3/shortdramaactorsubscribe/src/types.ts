/**
 * 短剧演员订阅 —— 前端数据类型。
 *
 * 2026-10-15 重写后的数据契约只有两类东西：
 *   1. 演员（配置里填的名字 + 百科解析出的身份与状态）；
 *   2. 作品（百科作品卡 + 演员归属 + 筛选排序用的字段）。
 * 下载 / 整理 / 账本相关的类型全部删除 —— 那些已经交回宿主订阅系统。
 */

/** 宿主注入的 axios 实例（本插件只用到 get/post/put） */
export interface PluginApi {
  get?: (url: string, config?: Record<string, unknown>) => Promise<any>
  post?: (url: string, data?: unknown, config?: Record<string, unknown>) => Promise<any>
  put?: (url: string, data?: unknown, config?: Record<string, unknown>) => Promise<any>
  defaults?: { baseURL?: string }
}

/** 通用接口返回 */
export interface ApiResult {
  success?: boolean
  message?: string
  code?: string
  [key: string]: unknown
}

/** 作品墙上的一部剧 */
export interface WorkItem {
  /** 去重键（归一化剧名|年份） */
  key: string
  title: string
  /** 首播年（数据源给不出时为空串） */
  year: string
  type: string
  /** 媒体来源：短剧百科（规范标识 `duanju`） */
  media_source: string
  /** 百科原生 ID（裸数字，形如 `34146`），与 media_source 一起构成系统订阅认的媒体身份 */
  media_id: string
  poster: string
  vote: number
  episode_count: number
  /** 百科作品页地址 */
  url: string
  /** 题材标签（类型筛选用；卡片上是摘要，详情页才是全量） */
  genres: string[]
  /** 热度（作品自带，排序用） */
  heat: number
  /** 播放量（作品自带，排序用） */
  play_count: number
  /** 版权方（数据源补齐后才有，空串表示没有） */
  studio: string
  /** 真人短剧 / AI 短剧 */
  kind: string
  /**
   * 在库状态（与宿主媒体详情页同一套判定）：
   * true 已入库 / false 不在库 / 缺省未知（查库失败或数据没查成，不显示标记）
   */
  in_library?: boolean
  release_date: string
  /** 参演演员（多位时形如「A / B」） */
  actor: string
  actor_key: string
  first_seen: string
  is_new: boolean
  /** 百科简介（只有搜索结果里的作品有；墙上的卡没有这个字段） */
  overview?: string
}

/** 演员筛选条目 */
export interface ActorFilter {
  key: string
  name: string
  works: number
  /** '' 正常 / 'waiting' 临时失败 / 'empty' 百科未收录 */
  state: string
}

/** 演员列表条目（/actors） */
export interface ActorItem extends ActorFilter {
  baike_id: string
  time: string
  errors: string[]
}

/** 一个筛选项（类型 / 年份 / 版权方） */
export interface FacetItem {
  value: string
  count: number
}

/** 筛选项集合（基于全集算，不随勾选跳动） */
export interface WorksFacets {
  genres: FacetItem[]
  years: FacetItem[]
  /** 版权方：数据源没给就是空数组，前端据此隐藏这一栏 */
  studios: FacetItem[]
}

/** 作品墙查询参数 */
export interface WorksQuery {
  actor?: string
  genre?: string
  year?: string
  studio?: string
  /** 'heat' 热度（默认）/ 'play' 播放 / 'rating' 评分 / 'date' 首播日期 */
  sort?: string
  /** 只看未入库（后端只排除明确已在库的；未知作品保留） */
  only_not_in_library?: boolean
  keyword?: string
  page?: number
  page_size?: number
}

/** 作品墙返回（一页） */
export interface WorksPayload extends ApiResult {
  /** 当前筛选条件下的作品总数 */
  total: number
  page: number
  page_size: number
  /** 还有下一页（前端滚动加载用） */
  has_more: boolean
  sort: string
  works: WorkItem[]
  actor_filters: ActorFilter[]
  facets: WorksFacets
  new_window_days: number
  summary: {
    /** 全集作品数（不受筛选影响） */
    total: number
    /** 全集里的新作品数 */
    new: number
    /** 在库状态查成了的作品数（0 = 整个媒体库判定不可用，前端隐藏在库 UI） */
    library_known: number
    /** 其中明确已在库的作品数 */
    in_library: number
  }
}

/** 百科查演员的候选（「搜索演员」的卡片数据源） */
export interface ActorCandidate {
  name: string
  actor_id: string
  /** 与输入的名字完全同名（可直接采纳） */
  exact: boolean
  /** 是否已在关注列表里 */
  subscribed?: boolean
  /** 演员头像（百科 CDN 绝对地址；补档案失败时为空） */
  profile?: string
  /** 参演作品数（补档案失败时为 0） */
  works_count?: number
  bio?: string
  gender?: string
  nationality?: string
  job_title?: string
  /** 百科演员页地址 */
  url?: string
  media_id?: string
}

/** 查演员返回 */
export interface ActorSearchPayload extends ApiResult {
  name: string
  candidates: ActorCandidate[]
}

/** 按片名查作品返回 */
export interface WorkSearchPayload extends ApiResult {
  name: string
  works: WorkItem[]
}

/** 插件配置 */
export interface PluginConfig {
  enabled: boolean
  onlyonce: boolean
  /** 演员名单：逗号或换行分隔 */
  actors: string
  interval_hours: number
  retry_minutes: number
  notify: boolean
  sidebar_nav: boolean
  /** 资源搜索站点：逗号分隔的站点 ID（空 = 不限定，走宿主默认） */
  search_sites: string
  /** 订阅下载器：宿主下载客户端的名字（空 = 跟随系统默认，订阅时弹系统对话框） */
  subscribe_downloader: string
}

/** 宿主「下载客户端」列表项（fetchDownloaderOptions 的产出） */
export interface DownloadClientOption {
  /** 下载客户端名字：提交订阅时写的就是它 */
  name: string
  /** 客户端类型（qbittorrent / transmission…），仅展示用 */
  type: string
}

/** 状态接口返回 */
export interface StatusPayload extends ApiResult {
  enabled: boolean
  configured: boolean
  actors: number
  works: number
  new_works: number
  last_refresh: string
  new_window_days: number
  states: ActorItem[]
}

/** 宿主的原生订阅注入：传入媒体对象即弹出系统订阅对话框 */
export type NativeSubscribe = (media: Record<string, unknown>) => Promise<ApiResult>
