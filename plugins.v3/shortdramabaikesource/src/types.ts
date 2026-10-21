/**
 * 短剧百科数据源 —— 联邦前端用到的数据形状。
 *
 * 全部对齐后端真实返回值（``build_public_record`` / ``build_public_actor`` /
 * ``api_lookup`` / ``api_status``），字段名逐字一致 —— 后端那边改字段名，
 * 这边必须同步，否则界面上只是「某块是空的」，不会报错。
 */

/** 宿主注入的 axios 实例（baseURL 已是 `api/v1/`） */
export interface PluginApi {
  get: (url: string, config?: Record<string, unknown>) => Promise<unknown>
  put: (url: string, data?: unknown, config?: Record<string, unknown>) => Promise<unknown>
  post: (url: string, data?: unknown, config?: Record<string, unknown>) => Promise<unknown>
  delete: (url: string, config?: Record<string, unknown>) => Promise<unknown>
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
  /** ⚠️ **全集总时长**（站点给的「时长」就是全集，不是单集） */
  duration_minutes?: number
  /** 单集时长 = 全集时长 ÷ 集数（短剧每集 1~3 分钟，折算值够用） */
  episode_minutes?: number
  release_date?: string
  rating?: number
  /** 站点自己的热度指标（「354万 热度」已还原成 3540000） */
  heat?: number
  play_count?: number
  favorite_count?: number
  tags?: string[]
  kind?: string
  /** 真人短剧 / AI短剧 —— 站点在 h1 左侧给的角标 */
  badge?: string
  series?: string
  season?: number
  studio?: string
  url?: string
  /** 页面语言（`zh-Hans` / `zh-Hant`） */
  in_language?: string
  /**
   * TMDB 真实身份（严格匹配到同名 + 同年的作品才有）。
   * 宿主详情页的评分面板 / 演职员 / 推荐 / 分季全都挂在这个 ID 上。
   */
  tmdb_id?: number
  actors?: CastMember[]
  /** 同页「推荐短剧」区块（字段口径与本记录一致） */
  related?: MediaRecord[]
}

/** 作品记录里的演员（字段名是 character / profile_path，不是 role / poster） */
export interface CastMember {
  id?: string
  name?: string
  character?: string
  profile_path?: string
  kind?: string
}

/** 演员页里的一张作品卡片（后端默认已补详情，字段与 `MediaRecord` 一致） */
export interface WorkItem {
  media_id?: string
  native_id?: string
  title?: string
  poster?: string
  backdrop?: string
  url?: string
  kind?: string
  /**
   * `detail` = 已按**作品页**补全（后端一贯如此，是默认也是唯一口径）；
   * `card` = 只有演员页卡片摘要（只可能出现在 `enrich=0` 的老缓存 / 显式跳过时）。
   */
  origin?: string
  episode_count?: number
  /** ⚠️ **全集总时长**（只有补全过详情页才有） */
  duration_minutes?: number
  episode_minutes?: number
  release_date?: string
  year?: string
  studio?: string
  overview?: string
  rating?: number
  /**
   * 卡片上印的题材标签是**摘要**（只印 1~3 个），完整标签要抓详情页才有。
   * 后端默认已全部补全（`origin === 'detail'`），所以正常不会看到截断的标签。
   */
  tags?: string[]
  heat?: number
  play_count?: number
  favorite_count?: number
  badge?: string
  /** 演员阵容（作品页有，演员页补全后同样有） */
  actors?: CastMember[]
  /** 同页「推荐短剧」区块 */
  related?: MediaRecord[]
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

/** 候选记录的来源：`store`（URL 库里已有，零引擎请求）/ `search`（这次刚搜到的） */
export type CandidateFrom = 'store' | 'search' | string

/** 作品候选（`/lookup` 的 `titles`，按片名打分） */
export interface TitleCandidate {
  media_id?: string
  native_id?: string
  title?: string
  url?: string
  from?: CandidateFrom
  score?: number
  poster?: string
  episode_count?: number
  /**
   * 同名条数（>1 时才有值）。
   *
   * 站点会给同一部剧建多条记录：实测 `/drama/40445`（真人短剧，字段齐全）与
   * `/drama/40354`（AI 短剧，没有演员 / 集数 / 时长 / 出品方）标题与简介**一字不差**。
   * 面板据此提示「这条还有别的版本」，否则用户无从判断该点哪一条。
   */
  same_title?: number
}

/** 演员候选（`/lookup` 的 `actors`，按姓名打分） */
export interface ActorCandidate {
  actor_id?: string
  media_id?: string
  name?: string
  url?: string
  from?: CandidateFrom
  score?: number
}

/** `/lookup` —— 面板唯一那个搜索框的后端返回值 */
export interface LookupPayload {
  success?: boolean
  message?: string
  keyword?: string
  year?: string
  titles?: TitleCandidate[]
  actors?: ActorCandidate[]
}

/** URL 库里的一条记录（`/urls` 的 `records`） */
export interface UrlRecord {
  kind?: 'work' | 'actor' | string
  /** 这条记录**自己的名字**（作品＝片名；演员＝演员名，归一化写法）—— 也是它的查询键 */
  keyword?: string
  /** 把它带出来的**那个搜索词**原文（可能是片名，也可能是当时搜的那部剧） */
  display?: string
  /** 页面标题（已剥站点后缀） */
  label?: string
  url?: string
  /** 站点 ID（作品 ID / 演员 ID），从 URL 路径取出 —— 一个页面只有一条记录 */
  native_id?: string
  /** `search`（搜索引擎发现）/ `page`（页面里的链接顺带发现） */
  origin?: string
  /** 引擎后端（origin=search 时有值） */
  backend?: string
  hits?: number
  first_seen_at?: number
  last_used_at?: number
}

/** `/urls` —— URL 库的统计与记录 */
export interface UrlsPayload {
  success?: boolean
  message?: string
  stats?: {
    total?: number
    work?: number
    actor?: number
    keywords?: number
    last_seen_at?: number
  }
  records?: UrlRecord[]
}

/**
 * `POST /urls/clear` —— 清空 URL 库。
 *
 * 不给 `kind` / `keyword` 就是**整库清空**（面板会二次确认）；只给 `kind` 清该类全部；
 * 两个都给就只清那个关键词的记录。清完后端会把「最近问过引擎」的时间戳一起清掉，
 * 所以马上再搜同一个词就能重新发现。
 */
export interface UrlsClearPayload {
  success?: boolean
  message?: string
  /** 实际删除的条数 */
  removed?: number
  /** 人类可读的范围描述（「整库」/「类型 actor」/「关键词「某剧」」） */
  scope?: string
  stats?: UrlsPayload['stats']
}

/**
 * 插件缓存现状（`/status` 与 `/cache` 的 `cache` 字段）。
 *
 * 后端缓存**跟着宿主走**（同一套 `app.sdk.cache`），但不进宿主的缓存管理页 ——
 * 所以这里把「跟着哪些系统开关」一并下发，面板要能解释清有效期为什么是这个值。
 */
export interface CacheStatus {
  /** 条目总数 */
  count?: number
  /** 按类型计数（detail / actor / tmdb） */
  kinds?: Record<string, number>
  kind_labels?: Record<string, string>
  detail?: number
  actor?: number
  tmdb?: number
  /** 缓存区名（宿主 Redis 上的键前缀 `region:<region>:key:`） */
  region?: string
  /** 是否生效（站点命中系统「不缓存站点」时为 false） */
  enabled?: boolean
  /** 实际有效期（秒） */
  ttl?: number
  /** 有效期来源：plugin（插件配置覆盖）/ system / system-auto / off（插件配置关闭） */
  ttl_source?: string
  /** 插件配置的覆盖值（0 = 未覆盖，负数 = 关闭） */
  override_ttl?: number
  /** 插件配置显式关掉了缓存（`cache_ttl < 0`） */
  disabled?: boolean
  /** 实际落点：redis / cachetools（宿主内存后端）/ local（宿主无缓存 SDK 时的降级） */
  backend?: string
  sdk?: boolean
  domain?: string
  blocked?: boolean
  /** 宿主的缓存相关开关（原样展示） */
  system?: {
    backend?: string
    meta_expire_hours?: number
    auto_ttl?: number
    image_cache?: boolean
    image_cache_days?: number
    no_cache_site_key?: string
  }
}

/** 缓存里的一条记录（`/cache` 的 `data`） */
export interface CacheEntry {
  /** 完整键，如 `detail:60017` / `actor:371` / `tmdb|片名|2026` */
  key?: string
  /** detail / actor / tmdb */
  kind?: string
  kind_label?: string
  /** 展示名（作品片名 / 演员名 / TMDB 检索的片名） */
  label?: string
  /** 站点 ID 或年份（第二展示列） */
  ref?: string
  /** 写入时间（秒级时间戳） */
  cached_at?: number
  /**
   * 附属于这条记录、与它同属一部作品的其它缓存。
   *
   * TMDB 身份是按「片名 + 年份」单独建键的，所以同一部剧在列表里会占两行 ——
   * 后端按片名把它们挂到作品详情这条下面，面板跟着缩进渲染一行，看着不再重复。
   */
  attached?: CacheEntry[]
}

/** `/cache` —— 缓存管理界面的数据 */
export interface CachePayload {
  success?: boolean
  message?: string
  count?: number
  returned?: number
  kind?: string
  keyword?: string
  kinds?: string[]
  kind_labels?: Record<string, string>
  cache?: CacheStatus
  data?: CacheEntry[]
}

/**
 * `GET /cache/{key}` —— **单条**缓存的完整内容（面板点开某条时用）。
 *
 * 后端一次给三样东西：`data`（缓存里原始的解析结果，排障看它）、
 * `record` / `actor`（同一份数据的对外投影，与 `/recognize`、`/actor` 同形状 ——
 * 面板直接用搜索结果那两张卡片渲染）、`summary`（TMDB 身份这类没卡片可渲染的条目靠它说话）。
 */
export interface CacheDetailPayload {
  success?: boolean
  message?: string
  key?: string
  kind?: string
  kind_label?: string
  label?: string
  ref?: string
  cached_at?: number
  /** 实际有效期（秒） */
  ttl?: number
  /** 缓存里那份未投影的解析结果 */
  data?: unknown
  /** 一句话摘要 */
  summary?: string
  /** `kind=detail` 时的作品投影 */
  record?: MediaRecord | null
  /** `kind=actor` 时的演员投影 */
  actor?: ActorProfile | null
}

/** `DELETE /cache` 的返回值 */
export interface CacheClearPayload {
  success?: boolean
  message?: string
  removed?: number
  scope?: string
  stats?: CacheStatus
}

/** `/status` */
export interface StatusPayload {
  enabled?: boolean
  domain?: string
  version?: string
  cache?: CacheStatus
  /** URL 库容量（库里只存 URL，页面数据永远实时解析） */
  store?: { total?: number; work?: number; actor?: number; keywords?: number; last_seen_at?: number }
  web_index?: { available?: boolean; enabled?: boolean; backend?: string }
  follow_links?: boolean
  actor?: { enabled?: boolean; max_candidates?: number }
}

/** 配置模型（键与后端 `_default_config` 一致，共 10 项） */
export interface PluginConfig {
  enabled: boolean
  domain: string
  search_in_global: boolean
  timeout: number
  /**
   * 缓存有效期**覆盖值**（秒）。
   *
   * * `0`（默认）= **跟随宿主**：取系统设置「单条元数据识别缓存有效期」
   *   （`META_CACHE_EXPIRE`，小时，0/未填时宿主按 24 小时、大内存模式 72 小时计）；
   * * `> 0` = 显式覆盖；
   * * `< 0` = **关闭插件缓存**（排障用；系统没有「关掉识别缓存」的开关，所以这一档在插件侧）。
   */
  cache_ttl: number
  web_index_search: boolean
  web_index_backend: string
  proxy: boolean
  /** 解析页面时顺带把页面里的演员 / 作品链接写进 URL 库 */
  follow_links: boolean
  /** 演员作品补全的并发抓取线程数（1~32，默认 8） */
  enrich_workers: number
}

/** `/config` GET 的可选项 */
export interface ConfigOptions {
  web_index_backends?: string[]
}
