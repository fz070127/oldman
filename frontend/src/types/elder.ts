/**
 * 老人档案类型 —— 与《接口契约 v1.0》3.2 & 3.4 节保持一致
 */
import type { PageQuery } from './common'
import type { ElderDeviceBrief } from './device'
import type { EventItem } from './event'

/** 性别枚举：1 男 | 2 女 */
export const Gender = {
  MALE: 1,
  FEMALE: 2,
} as const
export type Gender = (typeof Gender)[keyof typeof Gender]

/** 检测模式枚举：1 视觉 | 2 雷达 | 3 双模 */
export const DetectMode = {
  VISION: 1,
  RADAR: 2,
  DUAL: 3,
} as const
export type DetectMode = (typeof DetectMode)[keyof typeof DetectMode]

/** 老人状态枚举：1 在册 | 2 暂停 | 3 离世 */
export const ElderStatus = {
  ACTIVE: 1,
  PAUSED: 2,
  DECEASED: 3,
} as const
export type ElderStatus = (typeof ElderStatus)[keyof typeof ElderStatus]

/** 健康标签字典常量（契约 3.11） */
export const HEALTH_TAGS = ['独居', '空巢', '高血压', '糖尿病', '认知障碍', '心脏病'] as const
export type HealthTag = (typeof HEALTH_TAGS)[number]

/** 亲属关系字典常量（契约 3.11） */
export const FAMILY_RELATIONS = ['子女', '配偶', '兄弟姐妹', '其他亲属', '护工'] as const
export type FamilyRelation = (typeof FAMILY_RELATIONS)[number]

/** 紧急联系人（契约 3.2 & 3.4） */
export interface EmergencyContact {
  name: string
  phone: string
  relation: string
  primary: boolean
}

/** 家属绑定（契约 3.4 GET /elders/{id} 的 families[i]） */
export interface FamilyBinding {
  bindingId: string
  userId: string
  name: string
  phone: string
  relation: string
  isPrimary: boolean
  notifyOrder: number
}

/** 老人列表项（契约 3.4 GET /elders 的 list[i]） */
export interface Elder {
  id: string
  name: string
  gender: Gender
  age: number
  birthDate: string
  phone: string
  address: string
  roomNo: string
  communityId: string
  communityName: string
  guardianId: string
  guardianName: string
  healthTags: string[]
  detectMode: DetectMode
  status: ElderStatus
  deviceOnline: boolean
  lastAlarmAt: string | null
  alarmCount30d: number
  createdAt: string
}

/** 老人详情（契约 3.4 GET /elders/{id} 的 data） */
export interface ElderDetail {
  id: string
  name: string
  gender: Gender
  age: number
  birthDate: string
  phone: string
  address: string
  roomNo: string
  communityId: string
  communityName: string
  guardianId: string
  guardianName: string
  healthTags: string[]
  detectMode: DetectMode
  status: ElderStatus
  emergencyContact: EmergencyContact[]
  devices: ElderDeviceBrief[]
  families: FamilyBinding[]
  recentEvents: EventItem[]
}

/** GET /elders 查询参数 */
export interface ElderQuery extends Partial<PageQuery> {
  keyword?: string
  communityId?: string
  status?: ElderStatus | ''
  guardianId?: string
  deviceOnline?: boolean | string
}

/** POST / PUT /elders 请求体 */
export interface ElderSaveParams {
  name: string
  gender: Gender
  birthDate: string
  phone: string
  communityId: string
  address: string
  roomNo: string
  guardianId: string
  healthTags: string[]
  detectMode: DetectMode
  status?: ElderStatus
  emergencyContact: EmergencyContact[]
}

/** POST /elders/{id}/families 请求体 */
export interface BindFamilyParams {
  userId?: string
  name: string
  phone: string
  relation: string
  isPrimary: boolean
  notifyOrder: number
}
