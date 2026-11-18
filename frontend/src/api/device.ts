/**
 * 设备管理 API —— 《接口契约 v1.0》3.5
 */
import request from './request'
import type { PageResult } from '@/types/common'
import type {
  Device,
  DeviceConfig,
  DeviceHealth,
  DeviceQuery,
  DeviceSaveParams,
  DeviceSnapshot,
} from '@/types/device'

/** 分页获取设备列表 */
export function getDeviceList(params: DeviceQuery) {
  return request<PageResult<Device>>({ url: '/devices', method: 'get', params })
}

/** 获取设备详情 */
export function getDeviceDetail(id: string) {
  return request<Device>({ url: `/devices/${id}`, method: 'get' })
}

/** 新增设备 */
export function createDevice(data: DeviceSaveParams) {
  return request<Device>({ url: '/devices', method: 'post', data })
}

/** 更新设备 */
export function updateDevice(id: string, data: Partial<DeviceSaveParams>) {
  return request<Device>({ url: `/devices/${id}`, method: 'put', data })
}

/** 删除设备 */
export function deleteDevice(id: string) {
  return request<null>({ url: `/devices/${id}`, method: 'delete' })
}

/** 下发设备配置（ROI / 家具 / 灵敏度 / 免打扰） */
export function updateDeviceConfig(id: string, data: DeviceConfig) {
  return request<DeviceConfig>({ url: `/devices/${id}/config`, method: 'put', data })
}

/**
 * 远程重启设备（POST /devices/{id}/reboot）
 * 开启 silentError，使 5001 等业务失败交由调用方弹出友好提示而非红色报错
 */
export function rebootDevice(id: string) {
  return request<{ cmd: string; ok: boolean; msg: string }>({
    url: `/devices/${id}/reboot`,
    method: 'post',
    silentError: true,
  })
}

/** 获取近 24h 心跳与资源序列 */
export function getDeviceHealth(id: string) {
  return request<DeviceHealth>({ url: `/devices/${id}/health`, method: 'get' })
}

/** 拉取一帧快照用于配置 ROI */
export function captureDeviceSnapshot(id: string) {
  return request<DeviceSnapshot>({ url: `/devices/${id}/snapshot`, method: 'post' })
}
