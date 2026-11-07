/**
 * 当前主站（`net` / `org`）在前端的**唯一真源**。
 *
 * 为什么要单开一个模块：主站不是配置页的私有字段 —— 顶栏的站点 chip、概览里的
 * 「站点」链接、查询框的示例 media_id、排除开关的说法（漫剧 / AI 剧）全都要跟着变。
 * 以前这些位置各写各的 `duanjubaike.net` 字面量，用户在配置页切到新站后，
 * 界面上所有站点文案还是老站，看着就像「切换没生效」。
 *
 * 取值来源只有一处：后端 `GET /status` 的 `site`（= `constants.site()`，已归一）。
 * 配置页保存成功后调 :func:`setSite` 即时同步，不必等下一次轮询。
 */

import { computed, ref } from 'vue'
import { fetchStatus } from './api'
import type { PluginApi } from './types'

/** 站点键（与后端 `constants.SITE_NET` / `SITE_ORG` 同值）。 */
export type SiteKey = 'net' | 'org'

export interface SiteInfo {
  key: SiteKey
  /** 完整写法，用在卡片标题 / 下拉候选 */
  label: string
  /** 域名，用在 chip / 链接文字 */
  host: string
  /** 站点根地址（外链用） */
  base: string
  /** 该站点「排除开关」排的是什么（文案用） */
  excludeName: string
  /** 该站点 media_id 示例（查询框 placeholder 用） */
  sampleId: string
}

export const SITE_INFO: Record<SiteKey, SiteInfo> = {
  net: {
    key: 'net',
    label: 'duanjubaike.net（老站）',
    host: 'duanjubaike.net',
    base: 'https://www.duanjubaike.net',
    excludeName: '漫剧',
    sampleId: 'duanju:7696',
  },
  org: {
    key: 'org',
    label: 'duanjubaike.org（新站）',
    host: 'duanjubaike.org',
    base: 'https://duanjubaike.org',
    excludeName: 'AI 剧',
    sampleId: 'drama:13502',
  },
}

/** 归一：只有 `org` 是新站，其它（含空）一律老站。 */
export function toSiteKey(value: unknown): SiteKey {
  return String(value || '').trim().toLowerCase() === 'org' ? 'org' : 'net'
}

const current = ref<SiteKey>('net')
/** 是否已经从后端读到过一次（避免每个组件各发一次 /status）。 */
const resolved = ref(false)
let inflight: Promise<void> | null = null

/** 当前主站键（只读）。 */
export const siteKey = computed<SiteKey>(() => current.value)

/** 当前主站信息（模板里直接 `siteInfo.host` / `siteInfo.base`）。 */
export const siteInfo = computed<SiteInfo>(() => SITE_INFO[current.value])

/** 写入当前主站（配置页保存成功后 / 读到 `/status` 后调用）。 */
export function setSite(value: unknown): SiteKey {
  const key = toSiteKey(value)
  current.value = key
  resolved.value = true
  return key
}

/**
 * 确保主站已从后端读出来（并发调用只发一次请求）。
 *
 * 失败不抛：面板其余功能照常，站点文案保持上一次的值 —— 站点标识错了
 * 不该把整个面板变成错误页。
 */
export function ensureSite(api?: PluginApi, force = false): Promise<void> {
  if (resolved.value && !force) return Promise.resolve()
  if (inflight) return inflight
  inflight = (async () => {
    try {
      const status = await fetchStatus({ api })
      if (status) setSite((status as { site?: string }).site)
    } catch {
      // 读不到就维持现状；下一次打开面板会再试
      resolved.value = true
    } finally {
      inflight = null
    }
  })()
  return inflight
}
