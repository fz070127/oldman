/**
 * 事件类型 —— 与《接口契约 v1.0》3.2 / 3.6 / 3.9 节保持一致
 */
import type { PageQuery } from './common'

/** 事件类型枚举：FALL 跌倒 | LONG_LIE 久躺 */
export const EventType = {
  FALL: 'FALL',
  LONG_LIE: 'LONG_LIE',
} as const
export type EventType = (typeof EventType)[keyof typeof EventType]

/** 事件/告警级别枚举：P0 紧急 | P1 重要 | P2 一般 */
export const EventLevel = {
  P0: 'P0',
  P1: 'P1',
  P2: 'P2',
} as const
export type EventLevel = (typeof EventLevel)[keyof typeof EventLevel]

/** 事件处理结论枚举（契约 3.2） */
export const EventHandleResult = {
  TRUE_FALL: 'TRUE_FALL',
  FALSE_POSITIVE: 'FALSE_POSITIVE',
  UNKNOWN: 'UNKNOWN',
} as const
export type EventHandleResult = (typeof EventHandleResult)[keyof typeof EventHandleResult]

/** 统计时间范围枚举（契约 3.6 / 3.7） */
export const StatsRange = {
  TODAY: 'today',
  DAYS_7: '7d',
  DAYS_30: '30d',
} as const
export type StatsRange = (typeof StatsRange)[keyof typeof StatsRange]

/** 事件算法特征（契约 3.9，算法侧/后端/前端三处严格一致） */
export interface EventFeatures {
  /** 躯干与水平面夹角（度），站立 80-90，躺倒 <20 */
  torsoAngle: number
  /** 归一化高度降幅，0-1 */
  heightDrop: number
  /** 倒地后静止时长（秒） */
  stillDurationSec: number
  /** 目标跟踪 ID */
  trackId: number
  /** 人体框宽高比，站立 0.3-0.5，躺倒 1.5-3 */
  aspectRatio: number
  /** 关键点平均置信度 0-1 */
  kpConf: number
  /** 可选：判定过程中的原始信号明细 */
  signals?: Record<string, unknown>
}

/** 事件列表项（契约 3.6 GET /events 的 list[i]） */
export interface EventItem {
  id: string
  eventId: string
  elderId: string
  elderName: string
  roomNo: string
  deviceId: string
  deviceNo: string
  type: EventType
  level: EventLevel
  confidence: number
  occurredAt: string
  snapshotUrl: string
  clipUrl: string | null
  handled: boolean
  handleResult: EventHandleResult | null
  handleRemark: string | null
  handledAt: string | null
}

/** 事件详情（契约 3.6 GET /events/{id} = EventItem + features + algoVersion） */
export interface EventDetail extends EventItem {
  features: EventFeatures
  algoVersion: string
}

/** GET /events 查询参数 */
export interface EventQuery extends Partial<PageQuery> {
  elderId?: string
  deviceId?: string
  type?: EventType | ''
  level?: EventLevel | ''
  startTime?: string
  endTime?: string
  handled?: boolean | string
}

/** GET /events/{id}/media 响应 */
export interface EventMedia {
  snapshotUrl: string
  clipUrl: string | null
  keyframes: string[]
  expiresInSec: number
}

/** PUT /events/{id}/handle 请求体 */
export interface EventHandleParams {
  result: EventHandleResult
  remark?: string
}

/** GET /events/stats 响应 */
export interface EventStats {
  range: StatsRange
  total: number
  todayTotal: number
  todayP0: number
  unhandledCount: number
  falsePositiveCount: number
  falsePositiveRate: number
  byLevel: {
    p0: number
    p1: number
    p2: number
  }
  byType: {
    fall: number
    longLie: number
  }
}

/** POST /events/mock 请求体（契约 3.6） */
export interface EventMockParams {
  elderId: string
  type: EventType
  level: EventLevel
  confidence: number
}
