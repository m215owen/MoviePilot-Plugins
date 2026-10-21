/**
 * 短剧百科数据源 —— 面板共用的展示口径。
 *
 * 这三处必须完全一致，否则同一个字段在不同位置换一副面孔：
 * 搜索结果的作品卡、演员卡里的作品墙、以及缓存 / URL 库点开的展开区。
 * 所以口径只留这一份实现。
 */
import type { MediaRecord, WorkItem } from './types'

/** JSON 美化（「原始数据」展开块） */
export function pretty(value: unknown): string {
  return JSON.stringify(value ?? null, null, 2)
}

/** 把大数字还原成人看得懂的量级（后端给的已经是绝对值：354万 → 3540000） */
export function formatCount(value?: number): string {
  if (!value) return ''
  if (value >= 100000000) return `${(value / 100000000).toFixed(1)} 亿`
  if (value >= 10000) return `${Math.round(value / 10000)} 万`
  return String(value)
}

/**
 * 作品一行摘要（卡片、作品墙、展开区共用）。
 *
 * ⚠️ 站点给的「时长」是**全集总时长**（77 集共 130 分钟那种），不是单集时长 ——
 * 标成「单集」是错的。单集时长由后端按集数折算后单独给（`episode_minutes`）。
 *
 * @param withOrigin 是否附上「来源 详情页 / 检索结果」—— 作品卡需要，作品墙里 trivially 都是详情页
 */
export function recordMeta(record: WorkItem | MediaRecord | null | undefined, withOrigin = false): string {
  if (!record) return ''
  const parts: string[] = []
  const release = String(record.release_date || '').trim()
  const year = String(record.year || '').trim()
  if (record.kind) parts.push(String(record.kind))
  if (release) parts.push(`首播 ${release}`)
  else if (year) parts.push(year)
  if (record.episode_count) parts.push(`共 ${record.episode_count} 集`)
  if (record.duration_minutes) {
    parts.push(
      `全集 ${record.duration_minutes} 分钟`
      + (record.episode_minutes ? `（单集约 ${record.episode_minutes} 分钟）` : ''),
    )
  }
  if (record.studio) parts.push(String(record.studio))
  if (record.rating) parts.push(`评分 ${record.rating}`)
  if (record.heat) parts.push(`热度 ${formatCount(record.heat)}`)
  if (record.play_count) parts.push(`播放 ${formatCount(record.play_count)}`)
  if (record.favorite_count) parts.push(`收藏 ${formatCount(record.favorite_count)}`)
  if (withOrigin) parts.push(`来源 ${record.origin === 'detail' ? '详情页' : '检索结果'}`)
  return parts.join(' ｜ ')
}

/** 主演一行（作品卡用）：`张三（饰 李四）、王五` */
export function castLine(record: MediaRecord | null | undefined): string {
  const actors = record?.actors || []
  if (!actors.length) return ''
  return actors
    .slice(0, 10)
    .map((actor) => (actor.character ? `${actor.name}（饰 ${actor.character}）` : actor.name))
    .join('、')
}
