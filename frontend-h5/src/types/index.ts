/**
 * 家属端 H5 核心类型定义
 * 严格遵循《接口契约 v1.0》3.1 / 3.2 / 3.3 / 3.7 / 3.8 / 3.9 节，
 * 与主 Web 端（frontend/src/types）保持字段命名（camelCase）与枚举全集 100% 一致
 */

/** 统一接口响应包装（契约 3.1） */
export interface ApiResponse<T = unknown> {
  code: number
  message: string
  data: T
  traceId: string
}

/** 分页响应结构（契约 3.1） */
export interface PageResult<T> {
  list: T[]
  total: number
  page: number
  pageSize: number
}

/** 角色编码（契约 3.2 & 3.3） */
export type RoleCode = 'ADMIN' | 'COMMUNITY_ADMIN' | 'GUARDIAN' | 'FAMILY' | 'VIEWER'

/** 事件类型（契约 3.2 & 3.6） */
export const EventType = {
  FALL: 'FALL',
  LONG_LIE: 'LONG_LIE',
} as const
export type EventType = (typeof EventType)[keyof typeof EventType]

/** 事件/告警级别（契约 3.2 & 3.6） */
export const EventLevel = {
  P0: 'P0',
  P1: 'P1',
  P2: 'P2',
} as const
export type EventLevel = (typeof EventLevel)[keyof typeof EventLevel]

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
export type AlarmActionType =
  | 'NOTIFY'
  | 'ACK'
  | 'ESCALATE'
  | 'DISPATCH'
  | 'RESOLVE'
  | 'MARK_FALSE'
  | 'DEDUP'

/** 通知渠道枚举（契约 3.2） */
export type NotifyChannel = 'PUSH' | 'SMS' | 'CALL' | 'WS' | 'INBOX'

/** 通知发送结果枚举（契约 3.2） */
export type NotifyResultStatus = 'SENT' | 'FAILED' | 'DELIVERED'

/** 当前登录用户信息（契约 3.3 POST /auth/login & GET /auth/me） */
export interface UserInfo {
  id: string
  username: string
  nickname: string
  phone: string
  roleCode: RoleCode
  avatar: string
  communityId: string
  communityName: string
  permissions: string[]
  menus: string[]
}

/** 登录请求参数 */
export interface FamilyLoginParams {
  phone: string
  code: string
}

/** 登录返回结果（契约 3.3） */
export interface LoginResult {
  accessToken: string
  refreshToken: string
  expiresIn: number
  user: UserInfo
}

/** 家属端监护老人卡片项（契约 3.8 GET /family/elders 的 list[i]） */
export interface FamilyElderItem {
  id: string
  name: string
  age: number
  roomNo: string
  address: string
  communityName: string
  avatar: string
  online: boolean
  relation: string
  todayAlarmCount: number
  statusText: string
  lastActiveAt: string
  healthTags: string[]
  /** 关联的最新告警 ID，供点击老人卡片直接跳转告警页 */
  latestAlarmId: string
}

/** 事件算法特征（契约 3.9） */
export interface EventFeatures {
  torsoAngle: number
  heightDrop: number
  stillDurationSec: number
  trackId: number
  aspectRatio: number
  kpConf: number
}

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

/** 告警详情内嵌老人信息（契约 3.7 GET /alarms/{id} 的 elder） */
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
  remainingSec: number | null
}

/** POST /alarms/{id}/ack 请求体（契约 3.7） */
export interface AlarmAckParams {
  note?: string
}

/** POST /alarms/{id}/dispatch 请求体（契约 3.7） */
export interface AlarmDispatchParams {
  guardianId: string
  note?: string
}

/** 家属通知偏好设置（我的页通知开关） */
export interface FamilyNotificationSettings {
  pushEnabled: boolean
  smsEnabled: boolean
  callNightEnabled: boolean
}
