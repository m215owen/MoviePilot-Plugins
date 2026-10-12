/**
 * 插件开发模板 —— 前后端共享的数据结构定义。
 *
 * 字段需与后端 `PluginTemplate._default_config()` 及 API 返回保持一致。
 */

/** 插件配置（对应后端 get_form 的默认模型） */
export interface PluginConfig {
  /** 是否启用插件 */
  enabled: boolean
  /** 定时任务 cron 表达式 */
  cron: string
  /** 任务完成后是否发送系统通知 */
  notify: boolean
  /** 示例文本，业务代码可自由替换 */
  message: string
  /** 执行记录保留条数上限 */
  max_records: number
  /** 启用后立即执行一次 */
  onlyonce?: boolean
  /** 运行期统计：累计执行次数（只读） */
  run_count?: number
}

/** 单条执行记录 */
export interface RunRecord {
  /** 执行时间 */
  time: string
  /** 触发方式：manual / cron / command / workflow / api / once */
  trigger: string
  /** 是否成功 */
  success: boolean
  /** 耗时（毫秒） */
  elapsed_ms: number
  /** 结果说明 */
  detail: string
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
