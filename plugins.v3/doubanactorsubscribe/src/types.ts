/**
 * 豆瓣演员订阅 —— 前后端共享的数据结构定义。
 *
 * 字段与后端 `DoubanActorSubscribe._default_config()` / `get_works_payload()` 保持一致。
 */

/** 插件配置（对应后端 get_form 的默认模型） */
export interface PluginConfig {
  /** 是否启用插件 */
  enabled: boolean
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
  /** 保存后立即刷新一次 */
  onlyonce?: boolean
  /** 运行期统计：累计刷新次数（只读） */
  run_count?: number
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
  /** 首次被发现的时间 */
  first_seen?: string
  /** 是否为本次刷新新发现的作品 */
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
  /** 解析或抓取错误 */
  error?: string | null
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
  new_count: number
  auto_subscribe: boolean
  auto_only_new: boolean
  auto_min_vote: number
  auto_types: string[]
  auto_subscribed: AutoSubscribeRecord[]
  errors: string[]
  actors: ActorGroup[]
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
