/**
 * 短剧演员订阅 —— 前端数据类型。
 *
 * 2026-10-15 重写后的数据契约只有两类东西：
 *   1. 演员（配置里填的名字 + 百科解析出的身份与状态）；
 *   2. 作品（百科作品卡 + 演员归属 + 筛选排序用的字段）。
 * 下载 / 整理 / 账本相关的类型全部删除 —— 那些已经交回宿主订阅系统。
 */

/**
 * 宿主注入的 axios 实例（本插件只用到 get/post/put）
 *
 * 第三个参数是请求配置（宿主额外认识 ``feedback: 'silent'`` = 关掉它那一层错误 Toast、
 * ``timeout`` = 覆盖默认超时），见官方 API 专题 §5.2。
 */
export interface PluginApi {
  get?: (url: string, config?: Record<string, unknown>) => Promise<any>
  post?: (url: string, data?: unknown, config?: Record<string, unknown>) => Promise<any>
  put?: (url: string, data?: unknown, config?: Record<string, unknown>) => Promise<any>
  /** 删除（宿主注入的是 axios 实例，取消订阅用；旧宿主没有就跳过） */
  delete?: (url: string, config?: Record<string, unknown>) => Promise<any>
  defaults?: { baseURL?: string }
}

/** 宿主原生订阅注入的返回（宿主接口，不是本插件的信封） */
export interface ApiResult {
  success?: boolean
  message?: string
  code?: string
  [key: string]: unknown
}

/*
  插件端点的三段式信封（``schemas.Response[T]``）：顶层只有 ``success`` / ``message`` /
  ``data`` 三个键，业务对象一律在 ``data`` 里。`src/api.ts` 的 `readData()` 负责拆封，
  组件只消费拆封后的业务模型（下面的 ``*Payload`` 就是 data 的形状）。
  这里不再单独声明信封 interface —— 没有地方直接引用它的类型。
*/

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
  /**
   * 播放平台（「在哪播」，如 红果短剧 / 河马剧场）
   *
   * ⚠️ 数据源的**作品卡**（`actor_works`）目前不带这个字段 —— 平台只写在作品详情页的
   * meta 文案里。所以墙上恒为空串、筛选项恒为空数组（前端整行隐藏），只有**详情页**
   * 有真值。数据源一旦在卡片层补上，这里无需改动自动生效。
   */
  platform: string
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
  /**
   * 自建订阅搜索状态（订阅引擎 = self 时后端附带，来自台账；未处理的行没有这些字段）：
   * downloaded 已提交下载 / history 下载历史已有 / in_library 已在库 /
   * noresult 暂无资源（冷却重试）/ failed 失败（冷却重试）
   */
  sub_state?: string
  /** 状态的人话说明（如「已提交 PTS（标题匹配 + 演员「何田田」）」） */
  sub_detail?: string
  /** 状态写入时间 */
  sub_time?: string
  /** 台账记下的**种子页面**（下载成功才有）：详情页给一枚按钮直接跳过去 */
  sub_url?: string
  /** 台账记下的**种子标题**（按钮下面一行灰字） */
  sub_torrent?: string
  /** 百科简介（只有搜索结果里的作品有；墙上的卡没有这个字段） */
  overview?: string
  /**
   * 宿主侧订阅被暂停（只有「已订阅」页的行会带）：卡片左下角显示灰色「已暂停」chip。
   * 其余页面的作品永远没有这个字段。
   */
  paused?: boolean
}

/** 作品详情里的演员行（后端 ``WorkDetailActorRow``） */
export interface WorkDetailActor {
  actor_id: string
  name: string
  /** 饰演角色（站点没录入时为空） */
  character: string
  /** 头像（百科 CDN 绝对地址，走宿主 system/img 代理） */
  profile: string
  /**
   * 站点给的角标（主演 / 配角）。
   *
   * ⚠️ **本页不显示它** —— 宿主 `PersonCard` 那一行是固定的 `t('person.actor')`=「演员」，
   * 与系统一比一就别自作主张。字段留着（实测短剧站基本为空），将来要用不用再动后端。
   */
  kind: string
  /** 百科演员页地址（推不出来时为空） */
  url: string
  /** 是否已在本插件的关注列表里 */
  subscribed: boolean
}

/**
 * 作品详情（后端 ``WorkDetailData``，``GET /works/detail``）—— **自绘详情页**的数据源。
 *
 * 字段分两拨：百科详情页侧的（简介 / 题材 / 时长 / 演员表…）与**墙上快照侧**的
 * （``heat`` / ``play_count`` / ``kind`` / ``in_library``…）—— 后者是宿主 ``MediaInfo``
 * 里压根没有的字段，宿主自带的详情页因此永远显示不出来。
 */
export interface WorkDetailPayload {
  /** 百科里是否有这部剧（false = 只有墙上那点信息，详情页给空态提示） */
  found: boolean
  media_source: string
  media_id: string
  title: string
  year: string
  type: string
  overview: string
  poster: string
  /** 剧照首图，详情页顶栏大图用（没有则退回海报） */
  backdrop: string
  vote: number
  release_date: string
  episode_count: number
  /** 单集时长（分钟，站点只印全集总时长，按集数折算） */
  episode_minutes: number
  /** 全集时长（分钟，折算值 = 单集 × 集数） */
  duration_minutes: number
  genres: string[]
  /** 出品方 / 版权方 */
  studio: string
  /** 播放平台（「在哪播」，站点 meta 文案里抠出来的，如 红果短剧） */
  platform: string
  status: string
  language: string
  /** 百科作品页地址 */
  url: string
  /** 百科严格匹配到的 TMDB 条目 ID（0 = 没有 TMDB 身份） */
  tmdb_id: number
  /** TMDB 条目地址（有 tmdb_id 才有；来源区 TheMovieDb chip 用它） */
  tmdb_url: string
  /** 豆瓣条目 ID（数据源匹配到的；有它才能取豆瓣短评 / 影评） */
  douban_id?: string
  /** 豆瓣条目地址（来源区「豆瓣」chip 用它） */
  douban_url?: string
  actors: WorkDetailActor[]
  /** 真人短剧 / AI 短剧（站点角标） */
  kind: string
  first_seen: string
  is_new: boolean
  /** 三态：true 在库 / false 不在库 / null 未知（查库失败） */
  in_library?: boolean | null
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

/** 一个筛选项（类型 / 年份 / 版权方 / 播放平台） */
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
  /** 播放平台：与版权方同理，数据源没给就是空数组（当前作品卡不带平台 ⇒ 恒空） */
  platforms: FacetItem[]
}

/** 作品墙查询参数 */
export interface WorksQuery {
  actor?: string
  genre?: string
  year?: string
  studio?: string
  /** 播放平台（「在哪播」） */
  platform?: string
  /** 'date' 首播日期（默认）/ 'heat' 热度 / 'play' 播放 / 'rating' 评分 */
  sort?: string
  /** 只看未入库（后端只排除明确已在库的；未知作品保留） */
  only_not_in_library?: boolean
  /** 只看未订阅（后端按订阅清单排除，与卡片红心同一份） */
  only_not_subscribed?: boolean
  keyword?: string
  page?: number
  page_size?: number
}

/** 作品墙返回（一页）—— 后端 ``WorksData``（信封里的 ``data``） */
export interface WorksPayload {
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
    /** 在库状态查成了的作品数（页模式下只含缓存里已有的结论，可能小于全集） */
    library_known: number
    /** 其中明确已在库的作品数 */
    in_library: number
    /** 判定通道可用 —— 「只看未入库」开关的展示依据（页模式下不依赖 library_known） */
    probe_available?: boolean
    /** 本次请求是否做过全量判定（「只看未入库」开启时为 true） */
    probe_full?: boolean
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
  /** 站点人物页的粉丝数 / 获赞数（卡片上展示，0 = 没有） */
  followers?: number
  likes?: number
  /** 百科演员页地址 */
  url?: string
  media_id?: string
}

/** 查演员返回—— 后端 ``ActorSearchData``（信封里的 ``data``） */
export interface ActorSearchPayload {
  name: string
  candidates: ActorCandidate[]
}

/**
 * 人物目录的一行（后端 ``PeopleRow``）。
 *
 * 与演员候选同构（同一个卡片组件渲染），多一个 ``kind`` 说明这行来自哪个目录：
 * ``yanyuan`` 演员 / ``daoyan`` 导演 / ``bianju`` 编剧 —— 三者同属「人物」。
 */
export interface PeopleRow extends ActorCandidate {
  kind?: string
}

/** 人物目录的一页（后端 ``PeopleListData``）。``message`` 只在数据源缺能力时非空 */
export interface PeopleListPayload {
  kind: string
  page: number
  has_more: boolean
  message: string
  people: PeopleRow[]
}

/** 榜单目录的一行（后端 ``RankRow``） */
export interface RankItem {
  key: string
  name: string
  has_detail?: boolean
}

/** 榜单目录（后端 ``RanksData``） */
export interface RanksPayload {
  ranks: RankItem[]
  message: string
}

/**
 * 榜单卡行（后端 ``RankMediaRow``）—— 数据源按**实际页面**取必要字段：
 * ``media_id / title / badge / episodes / date / actors_text``；
 * ``poster`` / ``url`` 由数据源按 ``media_id`` 现推后附带。
 */
export interface RankMediaItem {
  media_id: string
  title: string
  badge: string
  episodes: number
  date: string
  actors_text: string
  poster: string
  url: string
  /** 在库判定（true 在库 / false 不在库 / null 未知）—— 卡片「入库」图标 */
  in_library?: boolean | null
  [extra: string]: unknown
}

/** 一个榜单的作品卡列表（后端 ``RankWorksData``） */
export interface RankWorksPayload {
  rank: string
  name: string
  /** 当前页码（从 1 起） */
  page: number
  /** 是否还有下一页（推荐页按站点分页；其他榜由数据源按 30 部切片） */
  has_more: boolean
  medias: RankMediaItem[]
  message: string
}

/** 插件最近日志（后端 ``LogsData``：原始日志行，旧的在前） */
export interface LogsPayload {
  items: string[]
}

/** 按片名查作品返回 —— 后端 ``WorkSearchData``（信封里的 ``data``） */
export interface WorkSearchPayload {
  name: string
  works: WorkItem[]
}

/**
 * 演员增删的 data（后端 ``ActorMutationData``）。
 *
 * ``need_pick`` 为真 = 只给名字且百科里没有**同名精确命中**：不是接口失败，前端拿
 * ``candidates`` 让用户挑一位（官方 API 专题 §3.3「未命中不等于接口失败」）。
 */
export interface ActorMutationPayload {
  actors: string[]
  need_pick?: boolean
  candidates?: ActorCandidate[]
}

/** 「已关注演员」卡片项（``/actors/cards``）：字段与搜索候选**同构** + 本地解析状态 */
export interface ActorCardItem extends ActorCandidate {
  /** '' 正常 / 'waiting' 暂时没取到作品（会自动重试）/ 'empty' 百科未收录 */
  state?: string
}

/**
 * 演员详情（后端 ``ActorDetailData``，``GET /actors/detail``）—— **自绘演员作品页**的数据源。
 *
 * 版式照宿主的演员详情页（``PersonDetailView.vue``）：圆形大头像 + 姓名 + 一行副信息 +
 * 简介 + 「参演作品」网格。
 *
 * ⚠️ 字段与宿主模型对不上是**正常的**：宿主那一页的「生日 | 出生地 / 别名」是
 * TMDB / 豆瓣 / Bangumi / AniList 才有的东西，短剧百科没有；百科有而宿主模型没有的是
 * ``job_title`` / ``nationality`` / ``works_count`` ⇒ 副信息行用「职业 | 国籍」。
 */
export interface ActorDetailPayload {
  /** 百科里有没有这位演员（false = 前端出空态，不算接口失败） */
  found: boolean
  actor_id: string
  media_id: string
  name: string
  /** 头像（百科 CDN 绝对地址，走宿主 system/img 代理） */
  profile: string
  bio: string
  /** 职业（站点给「演员」之类的身份） */
  job_title: string
  gender: string
  nationality: string
  /** 百科演员页地址 */
  url: string
  /** 出生日期（``1996-05-20``；只到年份时看 ``birth_year``） */
  birth_date?: string
  birth_year?: string
  /** 出生地 / 籍贯 */
  birth_place?: string
  /** 身高（cm）/ 体重（kg）；0 = 站点没给 */
  height_cm?: number
  weight_kg?: number
  /** 星座 / 毕业院校 */
  constellation?: string
  education?: string
  /** 爱好（空数组 = 站点没给） */
  hobbies?: string[]
  /** 站点原文里的「代表作」那一句 */
  rep_text?: string
  /** 代表作对回的作品（可点，按原文顺序；切分在后端做） */
  rep_works?: WorkItem[]
  /** 粉丝数 / 获赞数（站点人物页给的纯数字） */
  followers?: number
  likes?: number
  /** 百科侧的作品总数 */
  works_count: number
  /** **本页**实际返回的作品条数 */
  total: number
  /** 作品总数（分页前） */
  works_total?: number
  works_page?: number
  works_page_size?: number
  /** 还有下一页（滚到底续拉） */
  has_more?: boolean
  /** 明确已在库的作品数 / 查成了在库状态的条数（``library_known === 0`` = 判定不可用） */
  in_library_count: number
  library_known: number
  /** 这位演员在不在本插件的关注列表里 */
  subscribed: boolean
  works: WorkItem[]
}

/**
 * 订阅类型（宿主 `Subscribe.best_version` 口径）：
 * `follow` = 不传参数、跟随宿主订阅设置；`normal` = 普通订阅；`best` = 洗版订阅。
 */
export type SubscribeMode = 'follow' | 'normal' | 'best'
export type SubscribePrefer = 'seeders' | 'size_desc' | 'size_asc'
/** 订阅引擎：host = 宿主订阅链（默认）/ self = 插件自建订阅搜索（全分类补搜） */
export type SubscribeEngine = 'host' | 'self'

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
  /** 订阅站点：逗号分隔的站点 ID（空 = 跟随宿主订阅默认；只作用于提交订阅） */
  subscribe_sites: string
  /** 订阅下载目录：宿主 `/download/paths` 的 save_path（空 = 跟随宿主订阅默认） */
  subscribe_save_path: string
  /** 订阅类型：follow = 跟随宿主订阅设置 / normal = 普通订阅 / best = 洗版订阅 */
  subscribe_mode: SubscribeMode
  /** 优选条件：多条命中时挑哪条 —— seeders = 按做种数（默认）/ size_desc = 体积最大 / size_asc = 体积最小 */
  subscribe_prefer: 'seeders' | 'size_desc' | 'size_asc'
  /** 自动订阅：关注演员的作品直接交给宿主订阅链 */
  auto_subscribe: boolean
  /** `new` = 只订演员加入之后新出现的作品（默认）/ `all` = 连历史作品一起 */
  auto_subscribe_scope: 'new' | 'all'
  /** 单轮最多提交几部（1..50） */
  auto_subscribe_max_per_run: number
  /** 已在媒体库的作品是否跳过 */
  auto_subscribe_skip_library: boolean
  /** 订阅引擎：host = 宿主订阅链 / self = 自建订阅搜索（绕开站点分类错位） */
  subscribe_engine: SubscribeEngine
  /** 自建订阅搜索运行间隔（小时） */
  self_interval_hours: number
  /** 自建订阅搜索单轮最多搜索几部（1..30） */
  self_max_per_run: number
  /** 自建订阅搜索每部最多翻几页（1..10） */
  self_max_pages: number
}

/** 宿主「下载客户端」列表项（fetchDownloaderOptions 的产出） */
export interface DownloadClientOption {
  /** 下载客户端名字：提交订阅时写的就是它 */
  name: string
  /** 客户端类型（qbittorrent / transmission…），仅展示用 */
  type: string
}

/** 一条自动订阅记录（后端台账里的一次尝试） */
export interface AutoSubscribeRecord {
  time: string
  title: string
  year: string
  media_id: string
  actor: string
  /** false = 这次没订成（原因在 detail） */
  ok: boolean
  detail: string
}

/** 状态接口返回—— 后端 ``StatusData``（信封里的 ``data``） */
export interface StatusPayload {
  enabled: boolean
  configured: boolean
  actors: number
  works: number
  new_works: number
  last_refresh: string
  new_window_days: number
  states: ActorItem[]
  /** 自动订阅开关（关着时下面两个字段仍给，方便展示历史条数） */
  auto_subscribe?: boolean
  /** 累计自动订阅成功部数（不含「已在媒体库」跳过） */
  auto_subscribed?: number
  /** 最近几条自动订阅记录（新的在前，最多 5 条） */
  auto_subscribe_recent?: AutoSubscribeRecord[]
  /** 自建订阅搜索引擎（host / self；host 时下面计数恒为 0） */
  sub_engine?: 'host' | 'self'
  /** 自建订阅：已提交下载 */
  sub_downloaded?: number
  /** 自建订阅：无结果（冷却重试中） */
  sub_noresult?: number
  /** 自建订阅：失败（冷却重试中） */
  sub_failed?: number
  /** 自建订阅：在库 / 下载历史已有而跳过 */
  sub_skipped?: number
  /** 自建订阅：还没轮到 */
  sub_pending?: number
}

/** 宿主的原生订阅注入：传入媒体对象即弹出系统订阅对话框 */
export type NativeSubscribe = (media: Record<string, unknown>) => Promise<ApiResult>

/**
 * 宿主 `/download/paths` 的一项（订阅下载目录的选项来源）。
 *
 * `save_path` 可直接作为订阅的保存目录提交；`name` 是目录别名（宿主也认）。
 */
export interface DownloadPathOption {
  name: string
  storage: string
  download_path: string
  save_path: string
}

/** 「订阅全部作品」的单部结果（后端 `ActorSubscribeAllData.details[]`） */
export interface ActorSubscribeAllDetail {
  time: string
  title: string
  year: string
  media_id: string
  actor: string
  ok: boolean
  detail: string
}

/** 「订阅全部作品」的结果（后端 `ActorSubscribeAllData`） */
export interface ActorSubscribeAllPayload {
  name: string
  total: number
  submitted: number
  skipped_library: number
  skipped_subscribed: number
  failed: number
  capped: boolean
  /** 本次提交成功的作品 ID（前端据此点亮爱心） */
  media_ids: string[]
  details: ActorSubscribeAllDetail[]
}
