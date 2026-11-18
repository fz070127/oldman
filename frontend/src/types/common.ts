/**
 * 通用类型 —— 与《接口契约 v1.0》3.1 节保持一致
 */

/** 分页查询参数（page 从 1 开始，pageSize 默认 20，上限 100） */
export interface PageQuery {
  page: number
  pageSize: number
}

/** 分页结果 */
export interface PageResult<T> {
  list: T[]
  total: number
  page: number
  pageSize: number
}

/** 统一响应体 */
export interface ApiResult<T> {
  code: number
  message: string
  data: T
  traceId: string
}

/** 业务 code 枚举 */
export enum ResultCode {
  SUCCESS = 0,
  PARAM_ERROR = 1001,
  UNAUTHORIZED = 1002,
  FORBIDDEN = 1003,
  NOT_FOUND = 1004,
  STATE_CONFLICT = 1005,
  RATE_LIMITED = 1006,
  SERVER_ERROR = 5000,
  DOWNSTREAM_UNAVAILABLE = 5001,
}
