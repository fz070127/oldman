/**
 * 告警类型 —— 与《接口契约 v1.0》3.2 / 3.7 / 3.12 节保持一致
 */
import type { PageQuery } from './common'
import type { EventFeatures, EventHandleResult, EventLevel, EventType, StatsRange } from './event'

/** 告警状态枚举（契约 3.2 状态机全集，严禁缩写） */
export const AlarmStatus = {
  PENDING: 'PENDING',
  ACKNOWLEDGED: 'ACKNOWLEDGED',
  ESCALATED: 'ESCALATED',
  COMMUNITY_DISPATCHED: 'COMMUNITY_DISPATCHED',
  RESOLVED: 'RESOLVED',
  FALSE_POSITIVE: 'FALSE_POSITIVE',
} as const
export type AlarmStatus = (typeof AlarmStatus)[keyof typeof AlarmStatus]

/** 处置动作枚举（契约 3.2） */
export const AlarmActionType = {
  NOTIFY: 'NOTIFY',
  ACK: 'ACK',
  ESCALATE: 'ESCALATE',
  DISPATCH: 'DISPATCH',
  RESOLVE: 'RESOLVE',
  MARK_FALSE: 'MARK_FALSE',
  DEDUP: 'DEDUP',
} as const
export type AlarmActionType = (typeof AlarmActionType)[keyof typeof AlarmActionType]

/** 通知渠道枚举（契约 3.2） */
export const NotifyChannel = {
  PUSH: 'PUSH',
  SMS: 'SMS',
  CALL: 'CALL',
  WS: 'WS',
  INBOX: 'INBOX',
} as const
export type NotifyChannel = (typeof NotifyChannel)[keyof typeof NotifyChannel]

/** 通知发送结果枚举（契约 3.2） */
export const NotifyResultStatus = {
  SENT: 'SENT',
  FAILED: 'FAILED',
  DELIVERED: 'DELIVERED',
} as const
export type NotifyResultStatus = (typeof NotifyResultStatus)[keyof typeof NotifyResultStatus]

/** 告警列表项（契约 3.7 GET /alarms 的 list[i]） */
export interface AlarmItem {
  id: string
  level: EventLevel
  status: AlarmStatus
  elderId: string
  elderName: string
  roomNo: string
  communityName: string
  currentHandler: string
  escalateStep: number
  createdAt: string
  notifiedAt: string
  ackAt: string | null
  resolvedAt: string | null
  responseSec: number | null
  eventType: EventType
  confidence: number
  snapshotUrl: string
  /** PENDING 时返回距下一级升级的剩余秒数，其他状态为 null */
  remainingSec?: number | null
}

/** 处置流水项（契约 3.7 GET /alarms/{id} 的 actions[i]） */
export interface AlarmAction {
  id: number
  action: AlarmActionType
  actor: string
  actorName: string
  channel?: NotifyChannel
  result?: NotifyResultStatus
  detail?: Record<string, unknown>
  createdAt: string
}

/** 告警时间轴项（契约 3.7 GET /alarms/{id} 的 timeline[i]） */
export interface AlarmTimelineItem {
  ts: string
  text: string
}

/** 告警详情内嵌老人精简信息（契约 3.7 GET /alarms/{id} 的 elder） */
export interface AlarmElderInfo {
  id: string
  name: string
  age: number
  roomNo: string
  address: string
  phone: string
  healthTags: string[]
  primaryContact: {
    name: string
    phone: string
    relation: string
  } | null
}

/** 告警详情内嵌事件信息（契约 3.7 GET /alarms/{id} 的 event） */
export interface AlarmEventInfo {
  id: string
  type: EventType
  confidence: number
  occurredAt: string
  features: EventFeatures
  snapshotUrl: string
  clipUrl: string | null
  algoVersion: string
}

/** 告警详情（契约 3.7 GET /alarms/{id} 的 data） */
export interface AlarmDetail {
  id: string
  level: EventLevel
  status: AlarmStatus
  escalateStep: number
  currentHandler: string
  elder: AlarmElderInfo
  event: AlarmEventInfo
  notifiedAt: string
  ackAt: string | null
  resolvedAt: string | null
  responseSec: number | null
  actions: AlarmAction[]
  timeline: AlarmTimelineItem[]
  /** PENDING 时返回距下一级升级的剩余秒数，其他状态返回 null */
  remainingSec: number | null
}

/** GET /alarms 查询参数 */
export interface AlarmQuery extends Partial<PageQuery> {
  status?: AlarmStatus | ''
  level?: EventLevel | ''
  elderId?: string
  startTime?: string
  endTime?: string
}

/** POST /alarms/{id}/ack 请求体 */
export interface AlarmAckParams {
  note?: string
}

/** POST /alarms/{id}/dispatch 请求体 */
export interface AlarmDispatchParams {
  guardianId: string
  note?: string
}

/** POST /alarms/{id}/resolve 请求体（契约 3.7） */
export interface AlarmResolveParams {
  result: EventHandleResult
  note?: string
  needFollowUp: boolean
}

/** GET /alarms/pending-count 响应 */
export interface AlarmPendingCount {
  count: number
}

/** GET /alarms/stats 响应 */
export interface AlarmStats {
  range: StatsRange
  total: number
  todayTotal: number
  pendingCount: number
  acknowledgedCount: number
  escalatedCount: number
  dispatchedCount: number
  resolvedCount: number
  falsePositiveCount: number
  avgResponseSec: number
}

/** WebSocket 消息类型枚举（契约 3.12） */
export const WsMessageType = {
  ALARM_NEW: 'ALARM_NEW',
  ALARM_UPDATE: 'ALARM_UPDATE',
  DEVICE_STATUS: 'DEVICE_STATUS',
  PING: 'PING',
  PONG: 'PONG',
} as const
export type WsMessageType = (typeof WsMessageType)[keyof typeof WsMessageType]

/** WebSocket ALARM_NEW 负载（契约 3.12） */
export interface WsAlarmNewPayload {
  alarmId: string
  level: EventLevel
  elderId: string
  elderName: string
  communityName: string
  roomNo: string
  eventType: EventType
  confidence: number
  occurredAt: string
  snapshotUrl: string
  remainingSec: number
}

/** WebSocket ALARM_UPDATE 负载（契约 3.12） */
export interface WsAlarmUpdatePayload {
  alarmId: string
  status: AlarmStatus
  escalateStep: number
  currentHandler: string
}

/** WebSocket 通用消息结构 */
export interface WsMessage<T = unknown> {
  type: WsMessageType
  ts: string
  data: T
}
