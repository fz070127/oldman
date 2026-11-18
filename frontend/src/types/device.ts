/**
 * 设备类型 —— 与《接口契约 v1.0》3.2 & 3.5 节保持一致
 */
import type { PageQuery } from './common'

/** 设备类型枚举：1 边缘盒子 | 2 IPC | 3 雷达 */
export const DeviceType = {
  EDGE_BOX: 1,
  IPC: 2,
  RADAR: 3,
} as const
export type DeviceType = (typeof DeviceType)[keyof typeof DeviceType]

/** 设备状态枚举：0 未激活 | 1 在线 | 2 离线 | 3 故障 */
export const DeviceStatus = {
  INACTIVE: 0,
  ONLINE: 1,
  OFFLINE: 2,
  FAULT: 3,
} as const
export type DeviceStatus = (typeof DeviceStatus)[keyof typeof DeviceStatus]

/** 下行指令枚举（契约 3.13） */
export const DeviceCmd = {
  CONFIG_RELOAD: 'config.reload',
  CAPTURE: 'capture',
  RESTART: 'restart',
} as const
export type DeviceCmd = (typeof DeviceCmd)[keyof typeof DeviceCmd]

/** 归一化二维坐标点 [x, y]，取值 0~1 */
export type NormalizedPoint = [number, number]

/** 家具区域类型 */
export const FurnitureType = {
  BED: 'bed',
  SOFA: 'sofa',
  CHAIR: 'chair',
  TABLE: 'table',
} as const
export type FurnitureType = (typeof FurnitureType)[keyof typeof FurnitureType]

/** 家具抑制区域（契约 3.5） */
export interface FurnitureZone {
  type: FurnitureType
  points: NormalizedPoint[]
}

/** 设备配置（PUT /devices/{id}/config 请求体及 device.config 字段） */
export interface DeviceConfig {
  roi: NormalizedPoint[]
  furniture: FurnitureZone[]
  sensitivity: number
  quietHours: string[]
}

/** 老人详情内嵌的精简设备信息（契约 3.4 GET /elders/{id} 的 devices[i]） */
export interface ElderDeviceBrief {
  id: string
  deviceNo: string
  type: DeviceType
  status: DeviceStatus
  lastHeartbeat: string | null
  algoVersion: string
}

/** 设备对象（GET /devices 列表项及 GET /devices/{id} 详情） */
export interface Device {
  id: string
  deviceNo: string
  elderId: string | null
  elderName: string | null
  communityId: string | null
  communityName: string | null
  roomNo: string | null
  type: DeviceType
  rtspUrl?: string
  installAddr: string
  algoVersion: string
  config: DeviceConfig
  status: DeviceStatus
  lastHeartbeat: string | null
  createdAt: string
}

/** GET /devices 查询参数 */
export interface DeviceQuery extends Partial<PageQuery> {
  keyword?: string
  status?: DeviceStatus | ''
  elderId?: string
  communityId?: string
}

/** POST / PUT /devices 请求体 */
export interface DeviceSaveParams {
  deviceNo: string
  elderId?: string | null
  type: DeviceType
  rtspUrl?: string
  installAddr: string
  algoVersion?: string
}

/** 设备健康序列单点（契约 3.5 GET /devices/{id}/health） */
export interface DeviceHealthPoint {
  ts: string
  cpu: number
  mem: number
  fps: number
}

/** 设备近 24h 心跳与资源序列（GET /devices/{id}/health 的 data） */
export interface DeviceHealth {
  heartbeats24h: number
  avgFps: number
  dropRate: number
  series: DeviceHealthPoint[]
}

/** POST /devices/{id}/snapshot 响应 */
export interface DeviceSnapshot {
  snapshotUrl: string
  capturedAt: string
}
