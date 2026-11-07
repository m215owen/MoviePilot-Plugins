/**
 * 面板用的展示词典（**只做翻译，不做判断**）。
 *
 * 这些映射与后端 `constants.py` 一一对应，但**判断一律以后端为准**：
 * 前端不根据 `media_id` 前缀决定「这是作品还是人物」，只把后端给的
 * key 翻成中文给人看。哪天站点加了新实体，后端先认，面板退化成显示原 key
 * （原 key 本身就是最准确的信息，比硬猜一个中文名强）。
 */

/**
 * 实体前缀 → 中文（`constants.ENTITY_ALL` + 豆瓣两类）。
 *
 * 新老站的**编号空间互不相通**：老站短剧是 `duanju:`、新站短剧是 `drama:`，
 * 演员同理（`yanyuan:` / `actor:`）。同一个概念两个前缀，中文名就必须点明站点，
 * 否则库里同时存着两站数据时，「短剧」到底指哪一批人看不出来。
 */
export const ENTITY_LABELS: Record<string, string> = {
  duanju: '短剧（老站）',
  manju: '漫剧',
  hema: '漫剧（河马）',
  huolong: '漫剧（火龙）',
  xiaoshuo: '原著',
  yanyuan: '演员（老站）',
  daoyan: '导演',
  bianju: '编剧',
  drama: '短剧（新站）',
  actor: '演员（新站）',
  douban: '豆瓣作品',
  doubanp: '豆瓣人物',
}

/**
 * 各主站自己的实体前缀（顺序即 chips / 图例顺序：作品 → 原著 → 人物 → 豆瓣）。
 *
 * 老站把作品按短剧 / 漫剧 / 原著分四个分区、人物按演员 / 导演 / 编剧分三类；
 * 新站只有 `drama` / `actor` 两个分区（导演、编剧站点压根不单列）。
 * 豆瓣兜底两站共用。
 */
const SITE_ENTITIES: Record<string, string[]> = {
  net: ['duanju', 'manju', 'hema', 'huolong', 'xiaoshuo', 'yanyuan', 'daoyan', 'bianju', 'douban', 'doubanp'],
  org: ['drama', 'actor', 'douban', 'doubanp'],
}

/** 全部已知实体前缀（老站在前、新站在后；`douban*` 是两站共用的兜底）。 */
export const ENTITY_FILTERS: string[] = [
  'duanju',
  'manju',
  'hema',
  'huolong',
  'xiaoshuo',
  'yanyuan',
  'daoyan',
  'bianju',
  'drama',
  'actor',
  'douban',
  'doubanp',
]

/**
 * 漫剧类前缀（老站把漫剧拆成三种来源）。
 *
 * 「排除漫剧」开关打开时，库里这些前缀的行既不计入总数也不返回
 * （后端 `store.page` / `store.counts` 已按开关过滤）；面板的分类清单
 * 必须同步隐藏，否则会留一排永远 0 条的「漫剧」chip。
 */
export const MANJU_ENTITIES: string[] = ['manju', 'hema', 'huolong']

/**
 * 当前主站该显示的实体清单（认不出的站点按老站处理）。
 *
 * 面板的实体 chips、概览的实体分布都从这里取 —— 分类必须跟着主站走，
 * 否则切到新站后 chips 还列着一排 0 条的老站分区，看着就像「切换没生效」。
 *
 * `excludeManju = true`（配置里排除了漫剧 / AI 剧）时，漫剧类前缀整类不列：
 * 后端已经把那些行过滤掉了，面板再留空分类只会让人以为筛选没生效。
 */
export function entityFiltersFor(site: string, excludeManju = false): string[] {
  const key = String(site || '').trim().toLowerCase()
  const list = SITE_ENTITIES[key] || SITE_ENTITIES.net
  return excludeManju ? list.filter((item) => !MANJU_ENTITIES.includes(item)) : [...list]
}

/** 这个前缀是不是某站点自己的实体（用来判断库里是否有「别的站」的数据）。 */
export function isKnownEntity(entity: string): boolean {
  return Object.prototype.hasOwnProperty.call(ENTITY_LABELS, String(entity || '').trim())
}

/** 缓存 region → 中文（`constants.ALL_REGIONS`）。 */
export const REGION_LABELS: Record<string, string> = {
  'djbaike.detail': '详情',
  'djbaike.person': '人物',
  'djbaike.douban': '豆瓣',
  'djbaike.search': '站内搜索',
  'djbaike.rank': '榜单',
}

/** 实体前缀的中文名；认不出就原样返回。 */
export function entityLabel(entity: string): string {
  const key = String(entity || '').trim()
  return ENTITY_LABELS[key] || key || '未知'
}

/** region 的中文名；认不出就原样返回。 */
export function regionLabel(region: string): string {
  const key = String(region || '').trim()
  return REGION_LABELS[key] || key || '未知'
}

/** `media_id` 的前缀（`{entity}:{id}` 的 entity 部分；无冒号时原串）。 */
export function entityOf(mediaId: string): string {
  const text = String(mediaId || '')
  const at = text.indexOf(':')
  return at > 0 ? text.slice(0, at) : text
}

/**
 * 人物实体前缀（与后端 `constants.ENTITY_PERSON` 同步）。
 *
 * 人类型条目不能走 `/lookup?media_id=`（那是"一部片"的结构），必须走 `/person`；
 * 面板据此在点击时分派，而不是等后端回一个 `data: null`。
 *
 * `actor` 是新站的人物分区（2026-11-03 接入）：漏了它，新站的演员会被当作品查。
 * `doubanp` 是豆瓣影人 id（外部 id 库里存着一批）：漏了它，点开只会调 `/lookup`
 * 拿回 `data: null`（2026-11-04 用户指出「外部 id 库明明有很多人物」）。
 */
export const PERSON_ENTITIES = ['yanyuan', 'daoyan', 'bianju', 'actor', 'doubanp']

/** 这个 media_id 是不是人物。 */
export function isPersonId(mediaId: string): boolean {
  return PERSON_ENTITIES.includes(entityOf(mediaId))
}

/**
 * 分类事实字段 id → 中文（后端 `classify.py` 的 `FACT_*`）。
 *
 * 热度 / 播放 / 收藏这三项宿主 `MediaInfo` 没有对应列，后端只能挂在
 * `classification_facts` 上带出来；面板在这里翻成中文显示。
 * 认不出的 key 显示原样（原 key 比硬猜的中文准）。
 */
export const FACT_LABELS: Record<string, string> = {
  'extensions.djbaike.heat': '热度',
  'extensions.djbaike.play_count': '播放',
  'extensions.djbaike.favorite_count': '收藏',
  'extensions.djbaike.is_short_drama': '百科收录',
  'extensions.djbaike.kind': '形态',
}

/** 作品详情要展示的站内指标（顺序即展示顺序；值一律是站点原串，如 `989万`）。 */
export const METRIC_FACTS: string[] = [
  'extensions.djbaike.heat',
  'extensions.djbaike.play_count',
  'extensions.djbaike.favorite_count',
]

/** 站内指标的图标（认不出给个通用图形）。 */
export const FACT_ICONS: Record<string, string> = {
  'extensions.djbaike.heat': 'mdi-fire',
  'extensions.djbaike.play_count': 'mdi-play-circle-outline',
  'extensions.djbaike.favorite_count': 'mdi-heart-outline',
}

/** 事实字段的中文名；认不出就返回原 key。 */
export function factLabel(key: string): string {
  const text = String(key || '').trim()
  return FACT_LABELS[text] || text || '未知'
}

/** 事实字段的图标；认不出给通用图形。 */
export function factIcon(key: string): string {
  const text = String(key || '').trim()
  return FACT_ICONS[text] || 'mdi-chart-line'
}

/** 百分比（分母为 0 时返回 `—`，不显示 NaN）。 */
export function percent(part: number, whole: number): string {
  const total = Number(whole) || 0
  if (total <= 0) return '—'
  return `${Math.round((Number(part) / total) * 100)}%`
}
