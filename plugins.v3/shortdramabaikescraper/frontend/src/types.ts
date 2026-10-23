/**
 * 面板用到的类型：宿主注入的 HTTP 客户端 + 本插件后端的响应形状。
 *
 * 字段与 `api_models.py` **一一对应**（后端是 snake_case，这里不改名、不套壳），
 * 这样「面板上看到的」与「`/api/v1/plugin/.../…` 原文」永远同一套口径 ——
 * 面板本身就是排障工具，多一层字段映射就多一层对不上的可能。
 */

/** 宿主注入的 axios 实例（只用到这几个方法）。 */
export interface PluginApi {
  get?: (url: string, config?: unknown) => Promise<any>
  post?: (url: string, data?: unknown, config?: unknown) => Promise<any>
  put?: (url: string, data?: unknown, config?: unknown) => Promise<any>
  delete?: (url: string, config?: unknown) => Promise<any>
  defaults?: { baseURL?: string }
}

/** `GET /status` 的 `data`（= `api_models.StatusData`）。 */
export interface StatusPayload {
  enabled: boolean
  version: string
  media_source: string
  /** ID 库总条数 */
  total: number
  /** 可检索条数（`name` 非空） */
  searchable: number
  /** 按实体前缀计数：duanju / manju / hema / huolong / xiaoshuo / 人物三类 / douban / doubanp */
  by_entity: Record<string, number>
  /** 缓存 region 清单（`constants.ALL_REGIONS`） */
  regions: string[]
  /** 各缓存 region 的当前条数（概览页「缓存分布」饼图；随 TTL 过期而变） */
  by_region: Record<string, number>
}

/** `GET /baike/list` 的一行：**原始 4 列**，不作任何翻译或清洗。 */
export interface BaikeRow {
  media_id: string
  name: string
  douban: string
  tmdb: string
}

/** `GET /baike/list` 的 `data`（= `api_models.BaikePageData`）。 */
export interface BaikePage {
  total: number
  offset: number
  limit: number
  items: BaikeRow[]
}

/** 缓存枚举的一行：键 + **缓存里存的原始值**（就是写进 region 的那份 JSON）。 */
export interface CacheItem {
  key: string
  value: unknown
  /** 非空 = 这行是从数组值里展开的子条目，真正的缓存键是它（删除用） */
  parent?: string
  /** 面板显示名（榜单数组给「推荐（30 部）」这种，空则按值推断） */
  label?: string
}

/** `GET /cache/items` 的 `data`（= `api_models.CacheItemsData`）。 */
export interface CacheItems {
  region: string
  total: number
  items: CacheItem[]
}

/** 管理类操作的 `data`（= `api_models.OpResult`）。 */
export interface OpResult {
  ok: boolean
  detail: string
  affected: number
}

/**
 * 分类（宿主 `schemas.MediaGenre` 的形状：`{id, name}`）。
 *
 * ⚠️ `/lookup` 返回的 `genres` 是**对象数组**，不是字符串数组 —— 直接 `{{ genre }}`
 * 会渲染成 `{ "id": 0, "name": "爱情" }`。渲染前必须取 `name`（见 `genreNames()`）。
 */
export interface MediaGenre {
  id?: number
  name?: string
}

/**
 * 演职条目（宿主 `schemas.MediaCredit` 的形状）。
 *
 * 同样是对象：演员带 `character`（角色名），导演/编剧带 `job`。直接拼字符串会得到
 * `[object Object]` —— 必须取 `name`（见 `namesOf()`）。
 */
export interface MediaCredit {
  name?: string
  character?: string
  job?: string
  url?: string
}

/**
 * 宿主 `MediaInfo` 的子集（`/lookup`、`/search` 返回的就是它）。
 *
 * 只声明面板真正会渲染的字段：宿主 `MediaInfo` 有几十个键，全抄一遍既没用
 * 又会在宿主升级后变成维护负担；面板对缺字段一律容错。
 *
 * `genres` / `actors` / `directors` 写成「对象或字符串」的联合：宿主 v3.1.8 给的是对象，
 * 但换实现时可能退回字符串，渲染层两种都要吃得下。
 */
export interface MediaInfo {
  type?: string
  title?: string
  original_title?: string
  media_source?: string
  media_id?: string
  year?: string
  overview?: string
  poster_path?: string
  vote_average?: number
  number_of_episodes?: number
  genres?: Array<MediaGenre | string>
  actors?: Array<MediaCredit | string>
  directors?: Array<MediaCredit | string>
  detail_link?: string
  douban_id?: string | number
  tmdb_id?: string | number
  /** 上线 / 首播时间（站点原串，如 `2026年10月14日`） */
  release_date?: string
  /** 流媒体平台（宿主 `MediaCompany`：只有 `name` 有值，站点不给 id） */
  networks?: Array<{ id?: number | string; name?: string }>
  /**
   * 来源专有事实（后端 `classify.py` 的 `FACT_*`）。
   *
   * 热度 / 播放 / 收藏在宿主 `MediaInfo` 上没有对应列，靠这里带出来；
   * **值是站点原串**（`989万`），面板原样显示，不折算、不排序。
   */
  classification_facts?: Record<string, string | number | boolean>
}

/** 面板页签 key（四分区，计划 §6.5）。 */
export type PanelTab = 'overview' | 'baike' | 'cache' | 'query'

/**
 * 插件配置（键与后端 `_default_config()` / `get_form()` 一一对应）。
 *
 * Vue 配置页（联邦 `./Config`）通过 `GET/PUT /config` 读写这份结构；
 * 宿主原生表单走 `get_form()` —— 两边必须同源。
 */
export interface PluginConfig {
  enabled: boolean
}

/** 人物页的一张作品卡（`/person` 的 `works[]`）。 */
export interface PersonWork {
  media_id: string
  name: string
  kind: string
  poster: string
  date: string
  episodes: number
  actors: string[]
  tags: string[]
  /** 来源：baike=短剧百科 / douban=豆瓣独有（合并进来的） */
  origin?: 'baike' | 'douban' | string
  /** 年份（豆瓣来源才有） */
  year?: string
  /** 豆瓣评分（豆瓣来源才有） */
  rating?: number
}

/**
 * `GET /person` 的 `data`（= `api_models.PersonData`）。
 *
 * 人物**不是** MediaInfo（那个结构描述"一部片"），所以单开一份类型；
 * 它只给面板与外部插件看，不参与识别链路。
 */
export interface PersonPayload {
  media_id: string
  name: string
  /** 身份文案：女演员 / 男演员 / 导演 / 编剧 */
  role: string
  kind: string
  avatar: string
  intro: string
  works: PersonWork[]
  work_count: number
  detail_url: string
  /** 豆瓣影人 id（doubanp:{pid}，绑定成功才有） */
  douban_id?: string
  /** 豆瓣补充信息（性别 / 生日 / 出生地等，绑定成功才有） */
  douban_info?: string[]
}

/** 原著档案里的一张改编作品卡（`/novel` 的 `adaptations[]`）。 */
export interface NovelWork {
  media_id: string
  name: string
  kind: string
  poster: string
  date: string
  episodes: number
}

/**
 * `GET /novel` 的 `data`（= `api_models.NovelData`）。
 *
 * 原著与人物一样不是 MediaInfo（原著是"一本书"），单开一份类型。
 */
export interface NovelPayload {
  media_id: string
  name: string
  kind: string
  author: string
  /** 又名（改编版剧名，站点标注才有） */
  aka: string
  /** 字数（如 32.5 万字） */
  words: string
  overview: string
  poster: string
  detail_url: string
  adaptations: NovelWork[]
  adaptation_count: number
  /** 请求时传的剧 media_id（直接传原著时为空） */
  novel_id_of?: string
}
