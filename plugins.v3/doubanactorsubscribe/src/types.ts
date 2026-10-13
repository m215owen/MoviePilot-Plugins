/**
 * 豆瓣演员订阅 —— 前后端共享的数据结构定义。
 *
 * 字段与后端 `DoubanActorSubscribe._default_config()` / `get_works_payload()` 保持一致。
 */

/** 插件配置（对应后端 get_form 的默认模型） */
export interface PluginConfig {
  /** 是否启用插件 */
  enabled: boolean
  /**
   * 是否在 MoviePilot 主界面侧栏展示插件入口。
   *
   * 关闭后插件本身照常运行（定时刷新、自动订阅都继续），只是不再占用侧栏位置。
   */
  sidebar_nav: boolean
  /** 定时刷新 cron 表达式 */
  cron: string
  /** 演员列表：每行一个「演员名」或「豆瓣人物 ID」 */
  actors: string
  /** 每位演员展示/保留的作品数上限 */
  max_works: number
  /** 作品排序：time（按时间）/ vote（按评分）/ collection（豆瓣默认） */
  sort_by: string
  /** 请求豆瓣时是否走宿主配置的代理 */
  proxy: boolean
  /** 刷新完成后是否发送系统通知 */
  notify: boolean
  /** 是否自动订阅新作品 */
  auto_subscribe: boolean
  /** 自动订阅是否只针对“新出现”的作品（首次抓取只建基线） */
  auto_only_new: boolean
  /** 自动订阅的最低豆瓣评分，0 表示不限制 */
  auto_min_vote: number
  /** 自动订阅的媒体类型白名单，逗号分隔，如「电影,电视剧」 */
  auto_types: string
  /** 单次自动订阅的数量上限 */
  auto_max_per_run: number
  /** 订阅偏好：默认下载保存路径，空串表示跟随宿主默认配置 */
  subscribe_save_path: string
  /** 订阅偏好：默认下载器名称，空串表示跟随宿主默认配置 */
  subscribe_downloader: string
  /** 订阅偏好：默认订阅站点 ID 列表，空数组表示跟随宿主默认配置 */
  subscribe_sites: number[]
  /**
   * 手工粘贴的豆瓣 Cookie（留空 = 自动复用宿主 CookieCloud 里的豆瓣登录态）。
   *
   * 豆瓣对匿名请求返回 `403 need_login` 做限流，按名称搜索演员时额度只有个位数；
   * 带上登录态后实测可用次数显著提升，且不受出口 IP 被拉黑影响。
   */
  douban_cookie: string
  /** 运行时回显：当前 Cookie 来源 manual / cookiecloud / none（只读） */
  douban_cookie_source?: string
  /** 运行时回显：CookieCloud 取不到时的原因（只读） */
  douban_cookie_hint?: string
  /** 保存后立即刷新一次 */
  onlyonce?: boolean
  /** 运行期统计：累计刷新次数（只读） */
  run_count?: number
  /** 运行期标记：配置已变更、后台补刷新尚未完成（只读） */
  pending_refresh?: boolean
}

/** 单个影视作品（豆瓣条目） */
export interface ActorWork {
  /** 媒体来源，固定为 douban */
  media_source: string
  /** 豆瓣条目 ID */
  media_id: string
  /** 标题 */
  title: string
  /** 年份 */
  year: string
  /** MoviePilot 媒体类型：电影 / 电视剧；无法归类时为空串 */
  type: string
  /** 豆瓣原始类型：movie / tv 等 */
  raw_type?: string
  /** 是否可参与自动订阅 */
  subscribable: boolean
  /** 豆瓣评分 */
  vote: number
  /** 海报地址 */
  poster: string
  /** 豆瓣卡片副标题（年份 / 地区 / 类型 / 主演） */
  subtitle?: string
  /** 豆瓣条目页地址 */
  url?: string
  /** 该演员在此作品中的职务 */
  roles?: string[]
  /** 出演该作品的演员名（作品墙合并去重后聚合而来） */
  actorNames?: string[]
  /** 首次出现的时间（同一轮刷新写入基线的作品，其 first_seen == 演员 baseline_at） */
  first_seen?: string
  /**
   * 是否是「后来才出现的新作品」。
   *
   * 口径 = 首次出现在**该演员加入之后**，且在 `new_window_days` 天以内。
   * 所以刚把演员加进来时，他的历史作品一张都不会标「新」（那些是基线），
   * 只有之后某轮刷新才冒出来的作品才会带这个标记。
   */
  is_new?: boolean
}

/** 演员基本信息 */
export interface ActorBrief {
  /** 配置项原文（演员名或人物 ID） */
  key: string
  /** 豆瓣人物 ID */
  id: string
  /** 演员名 */
  name: string
  /** 头像 */
  avatar?: string | null
  /** 简介 */
  biography?: string
  /** 来源：id（直接给 ID）/ search（按名称搜索得到） */
  resolved_from?: string
  /**
   * 是否「按最接近的搜索结果」解析出来的。
   *
   * 豆瓣人物搜索是模糊匹配：配置「宋星颐」会返回「宋星翰 / 宋星成 / 宋星辰…」，
   * 插件拿不到同名条目时会退回第一个候选。此时 `key`（用户填的）与 `name`（豆瓣上的）
   * 不一致，面板必须提示，否则用户会以为「加的演员没生效」。
   */
  fuzzy?: boolean
  /** fuzzy 为真时的前几个候选名，供用户判断该改成哪个名字或改填人物 ID */
  candidates?: string[]
  /**
   * 演员的「加入时间」：**只有真正新加入的演员才有值**（本次刷新之前解析缓存里查无此人）。
   *
   * 升级前就在订阅列表里的老演员查不到加入时间，字段留空、chip 不标「新」——
   * 一次性给上百位演员补一个「现在」当加入时间，会让他们全被标成新演员。
   */
  joined_at?: string
  /** 是否是「最近加入」的演员（joined_at 在 new_window_days 天以内），chip 上标「新」 */
  is_new?: boolean
  /** 解析或抓取错误 */
  error?: string | null
  /** 该错误是否为可重试（豆瓣限流/网络失败），前端据此显示「稍后重试」而非「改配置」 */
  retryable?: boolean
}

/** 演员 + 其作品列表 */
export interface ActorGroup extends ActorBrief {
  works: ActorWork[]
}

/** 自动订阅历史记录 */
export interface AutoSubscribeRecord {
  time: string
  actor: string
  title: string
  year: string
  type: string
  vote?: number
  media_id: string
  success: boolean
  detail: string
}

/** 后端 GET /works 的返回体 */
export interface WorksPayload {
  enabled: boolean
  /** 上次刷新时间 */
  updated_at: string
  run_count: number
  actor_count: number
  work_count: number
  /** 「后来才出现的新作品」数量：首次出现在演员加入之后、且在窗口内的作品 */
  new_count: number
  /** 窗口内加入的演员数（作品不再逐张标新，新演员的规模由这个数体现） */
  new_actor_count?: number
  /** 「新」的口径：演员自加入、作品自在演员加入之后出现起，不超过这个天数 */
  new_window_days?: number
  auto_subscribe: boolean
  auto_only_new: boolean
  auto_min_vote: number
  auto_types: string[]
  auto_subscribed: AutoSubscribeRecord[]
  errors: string[]
  actors: ActorGroup[]
  /** 订阅偏好：当前默认保存路径 */
  subscribe_save_path: string
  /** 订阅偏好：当前默认下载器，空串表示跟随宿主默认配置 */
  subscribe_downloader?: string
  /** 订阅偏好：当前默认订阅站点 */
  subscribe_sites: number[]
  /** 当前豆瓣 Cookie 来源：manual（插件内手填）/ cookiecloud（宿主自动取）/ none */
  douban_cookie_source?: string
  /** 未取到豆瓣 Cookie 时的原因，直接展示给用户 */
  douban_cookie_hint?: string
  /**
   * 还没解析出人物 ID 的演员数。
   *
   * 0 表示全部解析完毕，之后刷新只走详情/作品集接口，不再消耗搜索额度。
   */
  unresolved_count?: number
  /**
   * 「待解析」演员中仍处于 24 小时搜索冷却内的数量。
   *
   * 只统计**尚未解析出人物 ID**的演员：某位演员成功搜到 ID 后本轮就不会再搜，
   * 把它的历史搜索记录也算成冷却会让数字只涨不降（搜索记录满 24 小时才过期）。
   */
  search_cooldown_count?: number
  /** 被用户忽略的作品数量；面板据此显示「已忽略 N 部」入口 */
  ignored_count?: number
  /** 被忽略的作品明细，用于在面板上恢复 */
  ignored?: IgnoredWork[]
  /** 是否正在等待后台补刷新 */
  pending_refresh: boolean
  /** 后台刷新是否正在进行（演员多时一次刷新会持续较久） */
  refreshing: boolean
}

/** 被用户忽略的作品（不再展示、也不参与自动订阅） */
export interface IgnoredWork {
  /** 唯一键，格式 `media_source:media_id` */
  key: string
  media_source?: string
  media_id?: string
  title?: string
  year?: string
  type?: string
  /** 忽略时间，用于按时间倒序展示 */
  time?: string
}

/** 可选的订阅站点（只保留展示所需字段，凭据不进前端状态） */
export interface SiteOption {
  id: number
  name: string
}

/** 可选的下载保存路径 */
export interface DownloadPathOption {
  name: string
  path: string
}

/**
 * 可选的下载器（宿主已配置的下载客户端）。
 *
 * `name` 是提交订阅时要写进 `downloader` 字段的值（宿主内部按名字找客户端），
 * `type` 只用于展示，如 qbittorrent / transmission。
 */
export interface DownloadClientOption {
  name: string
  type: string
}

/** 豆瓣演员搜索候选 */
export interface ActorCandidate {
  id: string
  name: string
  avatar?: string | null
  url?: string
}

/** 宿主统一响应体 */
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
