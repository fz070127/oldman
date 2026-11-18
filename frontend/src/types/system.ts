/**
 * 系统管理与家属端类型 —— 与《接口契约 v1.0》3.8 & 3.11 节保持一致
 */
import type { DetectMode } from './elder'
import type { DeviceType } from './device'
import type { RoleCode } from './user'

/** 社区实体（契约 3.2 & 3.11） */
export interface Community {
  id: string
  name: string
  address: string
  contactName: string
  contactPhone: string
  /** 地图归一化横坐标 0~1 */
  x: number
  /** 地图归一化纵坐标 0~1 */
  y: number
  createdAt: string
}

/** 网格员档案（契约 3.2 & 3.11） */
export interface Guardian {
  id: string
  userId: string
  communityId: string
  communityName: string
  name: string
  phone: string
  elderCount: number
}

/** 系统用户（契约 3.2 & 3.11） */
export interface SystemUser {
  id: string
  username: string
  nickname: string
  phone: string
  avatar: string
  roleCode: RoleCode
  communityId: string
  communityName: string
  status: 1 | 2
  lastLoginAt: string | null
  createdAt: string
}

/** 角色项（契约 3.11 GET /system/roles） */
export interface RoleItem {
  id: string
  code: RoleCode
  name: string
  permissions: string[]
}

/** 字典选项 */
export interface DictOption<V = number> {
  value: V
  label: string
}

/** 系统字典（契约 3.11 GET /system/dicts 的 data） */
export interface SystemDicts {
  healthTags: string[]
  relations: string[]
  deviceTypes: DictOption<DeviceType>[]
  detectModes: DictOption<DetectMode>[]
}

/** 审计日志项（契约 3.11 GET /system/audit-logs） */
export interface AuditLogItem {
  id: string
  actorId: string
  actorName: string
  action: string
  target: string
  detail: Record<string, unknown>
  ip: string
  createdAt: string
}

/** 家属端监护老人项（契约 3.8 GET /family/elders 的 list[i]） */
export interface FamilyElderItem {
  id: string
  name: string
  age: number
  roomNo: string
  avatar: string
  online: boolean
  relation: string
  todayAlarmCount: number
  statusText: string
  lastActiveAt: string
}

/** 家属端今日概览（契约 3.8 GET /family/elders/{id}/overview） */
export interface FamilyElderOverview {
  elderId: string
  elderName: string
  age: number
  roomNo: string
  communityName: string
  deviceOnline: boolean
  lastHeartbeat: string | null
  todayAlarmCount: number
  pendingAlarmCount: number
  statusText: string
  guardianName: string
  guardianPhone: string
}

/** 家属端站内信通知（契约 3.2 & 3.8） */
export interface FamilyNotificationItem {
  id: string
  userId: string
  type: string
  title: string
  content: string
  bizId: string
  read: boolean
  createdAt: string
}
