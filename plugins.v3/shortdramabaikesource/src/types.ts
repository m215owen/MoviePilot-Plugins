/**
 * 短剧百科数据源 —— 联邦前端用到的数据形状。
 *
 * 全部对齐后端真实返回值（``build_public_record`` / ``build_public_actor`` /
 * ``api_search`` / ``api_actor_search`` / ``api_status``），字段名逐字一致 ——
 * 后端那边改字段名，这边必须同步，否则界面上只是「某块是空的」，不会报错。
 */

/** 宿主注入的 axios 实例（baseURL 已是 `api/v1/`） */
export interface PluginApi {
  get: (url: string, config?: Record<string, unknown>) => Promise<unknown>
  put: (url: string, data?: unknown, config?: Record<string, unknown>) => Promise<unknown>
}

/** 一个作品记录（`/recognize` 的 `record`） */
export interface MediaRecord {
  media_source?: string
  /** `detail`（详情页，字段全）/ `search`（仅检索结果，字段少） */
  origin?: string
  media_id?: string
  native_id?: string
  title?: string
  year?: string
  overview?: string
  poster?: string
  backdrop?: string
  episode_count?: number
  duration_minutes?: number
  release_date?: string
  rating?: number
  play_count?: number
  tags?: string[]
  kind?: string
  studio?: string
  url?: string
  actors?: CastMember[]
}

/** 作品记录里的演员（字段名是 character / profile_path，不是 role / poster） */
export interface CastMember {
  id?: string
  name?: string
  character?: string
  profile_path?: string
  kind?: string
}

/** 演员页里的一张作品卡片 */
export interface WorkItem {
  media_id?: string
  native_id?: string
  title?: string
  poster?: string
  url?: string
  kind?: string
  episode_count?: number
  rating?: number
  tags?: string[]
  heat?: number
  play_count?: number
  badge?: string
}

/** 演员档案（`/actor` 的 `actor`） */
export interface ActorProfile {
  actor_id?: string
  media_id?: string
  name?: string
  job_title?: string
  gender?: string
  nationality?: string
  /** 头像 */
  profile?: string
  /** 简介 */
  bio?: string
  url?: string
  works?: WorkItem[]
  works_count?: number
  /** 合作演员（来自演员页「合作演员」区，字段是 id / name / profile_path） */
  coactors?: Array<{ id?: string; name?: string; profile_path?: string }>
}

/** 片名搜索的候选（`/search`） */
export interface TitleCandidate {
  media_id?: string
  title?: string
  score?: number
  poster?: string
  episode_count?: number
}

/** 演员搜索的候选（`/actor_search`） */
export interface ActorCandidate {
  actor_id?: string
  media_id?: string
  name?: string
  score?: number
}

/** `/status` */
export interface StatusPayload {
  enabled?: boolean
  top_lists?: string[]
  top_snapshot?: string
  cache?: { detail?: number; actor?: number }
  web_index?: { available?: boolean; enabled?: boolean; backend?: string }
  actor?: { enabled?: boolean; max_candidates?: number }
}

/** 配置模型（键与后端 `_default_config` 一致） */
export interface PluginConfig {
  enabled: boolean
  domain: string
  search_in_global: boolean
  interval_minutes: number
  timeout: number
  cache_ttl: number
  web_index_search: boolean
  web_index_backend: string
  proxy: boolean
  top_keys: string[]
  explore_detail_fetch: number
  detail_facts: boolean
}

/** `/config` GET 的可选项 */
export interface ConfigOptions {
  top_keys?: Array<{ value: string; label: string }>
  web_index_backends?: string[]
}
