/**
 * 统计与看板类型 —— 与《接口契约 v1.0》3.10 节保持一致
 */
import type { DeviceStatus } from './device'
import type { EventLevel, EventType } from './event'

/** 顶部 KPI 概览（契约 3.10 GET /dashboard/overview 的 data） */
export interface DashboardOverview {
  elderTotal: number
  elderOnline: number
  deviceTotal: number
  deviceOnline: number
  deviceOffline: number
  alarmToday: number
  alarmPending: number
  alarmP0Today: number
  avgResponseSec: number
  falsePositiveRate: number
  updatedAt: string
}

/** 告警趋势单日项（契约 3.10 GET /dashboard/trend 的 list[i]） */
export interface TrendItem {
  date: string
  p0: number
  p1: number
  p2: number
  total: number
}

/** 社区分布项（契约 3.10 GET /dashboard/distribution 的 list[i]） */
export interface DistributionItem {
  communityId: string
  communityName: string
  elderTotal: number
  alarmToday: number
  /** 地图归一化横坐标 0~1 */
  x: number
  /** 地图归一化纵坐标 0~1 */
  y: number
}

/** 实时事件流项（契约 3.10 GET /dashboard/realtime 的 list[i]） */
export interface RealtimeItem {
  id: string
  elderId: string
  elderName: string
  communityId: string
  communityName: string
  roomNo: string
  type: EventType
  level: EventLevel
  confidence: number
  occurredAt: string
  snapshotUrl: string
}

/** 离线设备简要项 */
export interface OfflineDeviceItem {
  id: string
  deviceNo: string
  elderId: string | null
  elderName: string | null
  communityName: string | null
  roomNo: string | null
  status: DeviceStatus
  lastHeartbeat: string | null
}

/** 设备在线率与离线清单（GET /dashboard/device-status 的 data） */
export interface DashboardDeviceStatus {
  total: number
  online: number
  offline: number
  fault: number
  inactive: number
  onlineRate: number
  offlineList: OfflineDeviceItem[]
}
