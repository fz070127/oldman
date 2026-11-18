/**
 * 设备管理 Mock —— 《接口契约 v1.0》3.5
 * 覆盖：分页筛选、详情、增删改、配置下发（ROI/家具/灵敏度/免打扰）、重启、24h 健康序列、抓拍快照
 */
import dayjs from 'dayjs'
import type { MockMethod } from 'vite-plugin-mock'
import { ResultCode } from '@/types/common'
import {
  DeviceStatus,
  type DeviceConfig,
  type DeviceHealthPoint,
  type DeviceSaveParams,
} from '@/types/device'
import { devicesStore, eldersStore } from './_data'
import {
  extractPathParam,
  formatIsoOffset,
  getSearchParams,
  nextId,
  resultError,
  resultPage,
  resultSuccess,
} from './_util'

const BASE = '/api/v1'

interface MockReq<B = unknown> {
  url: string
  body: B
}

function buildHealthSeries(): DeviceHealthPoint[] {
  const now = dayjs()
  const series: DeviceHealthPoint[] = []
  for (let i = 23; i >= 0; i--) {
    series.push({
      ts: formatIsoOffset(now.subtract(i, 'hour').minute(0).second(0)),
      cpu: 30 + ((i * 7) % 35),
      mem: 48 + ((i * 5) % 28),
      fps: 14 + (i % 2),
    })
  }
  return series
}

export default [
  // 设备分页列表
  {
    url: `${BASE}/devices`,
    method: 'get',
    response: ({ url }: MockReq) => {
      const sp = getSearchParams(url)
      const keyword = (sp.get('keyword') || '').trim().toLowerCase()
      const statusStr = sp.get('status') || ''
      const elderId = sp.get('elderId') || ''
      const communityId = sp.get('communityId') || ''
      const page = Number(sp.get('page') || 1)
      const pageSize = Number(sp.get('pageSize') || 20)

      let list = [...devicesStore]
      if (keyword) {
        list = list.filter(
          (d) =>
            d.deviceNo.toLowerCase().includes(keyword) ||
            (d.elderName && d.elderName.toLowerCase().includes(keyword)) ||
            d.installAddr.toLowerCase().includes(keyword),
        )
      }
      if (statusStr !== '') {
        const st = Number(statusStr)
        list = list.filter((d) => d.status === st)
      }
      if (elderId) {
        list = list.filter((d) => d.elderId === elderId)
      }
      if (communityId) {
        list = list.filter((d) => d.communityId === communityId)
      }

      return resultPage(list, page, pageSize)
    },
  },

  // 下发设备配置（ROI / 家具 / 灵敏度 / 免打扰）
  {
    url: `${BASE}/devices/:id/config`,
    method: 'put',
    response: ({ url, body }: MockReq<DeviceConfig>) => {
      const id = extractPathParam(url, /\/devices\/([^/]+)\/config/)
      const device = devicesStore.find((d) => d.id === id)
      if (!device) return resultError(ResultCode.NOT_FOUND, '设备不存在')

      device.config = {
        roi: body.roi ?? device.config.roi,
        furniture: body.furniture ?? device.config.furniture,
        sensitivity: body.sensitivity ?? device.config.sensitivity,
        quietHours: body.quietHours ?? device.config.quietHours,
      }
      return resultSuccess(device.config)
    },
  },

  // 远程重启（支持契约 /restart 与 F4 /reboot 两种路径；离线设备返回 5001）
  {
    url: `${BASE}/devices/:id/restart`,
    method: 'post',
    response: ({ url }: MockReq) => {
      const id = extractPathParam(url, /\/devices\/([^/]+)\/restart/)
      const device = devicesStore.find((d) => d.id === id)
      if (!device) return resultError(ResultCode.NOT_FOUND, '设备不存在')
      if (device.status !== DeviceStatus.ONLINE) {
        return resultError(ResultCode.DOWNSTREAM_UNAVAILABLE, '设备离线，无法远程重启')
      }
      device.lastHeartbeat = formatIsoOffset(new Date())
      return resultSuccess({ cmd: 'restart', ok: true, msg: '重启指令已下发' })
    },
  },
  {
    url: `${BASE}/devices/:id/reboot`,
    method: 'post',
    response: ({ url }: MockReq) => {
      const id = extractPathParam(url, /\/devices\/([^/]+)\/reboot/)
      const device = devicesStore.find((d) => d.id === id)
      if (!device) return resultError(ResultCode.NOT_FOUND, '设备不存在')
      if (device.status !== DeviceStatus.ONLINE) {
        return resultError(ResultCode.DOWNSTREAM_UNAVAILABLE, '设备离线，无法远程重启')
      }
      return resultError(ResultCode.DOWNSTREAM_UNAVAILABLE, '设备离线，无法远程重启')
    },
  },

  // 近 24h 心跳与资源序列
  {
    url: `${BASE}/devices/:id/health`,
    method: 'get',
    response: ({ url }: MockReq) => {
      const id = extractPathParam(url, /\/devices\/([^/]+)\/health/)
      const device = devicesStore.find((d) => d.id === id)
      if (!device) return resultError(ResultCode.NOT_FOUND, '设备不存在')

      const isOnline = device.status === DeviceStatus.ONLINE
      return resultSuccess({
        heartbeats24h: isOnline ? 2876 : 412,
        avgFps: isOnline ? 14.8 : 0,
        dropRate: isOnline ? 0.02 : 0.35,
        series: buildHealthSeries(),
      })
    },
  },

  // 拉取一帧快照用于配置 ROI
  {
    url: `${BASE}/devices/:id/snapshot`,
    method: 'post',
    response: ({ url }: MockReq) => {
      const id = extractPathParam(url, /\/devices\/([^/]+)\/snapshot/)
      const device = devicesStore.find((d) => d.id === id)
      if (!device) return resultError(ResultCode.NOT_FOUND, '设备不存在')
      return resultSuccess({
        snapshotUrl: `https://picsum.photos/seed/roi-${device.deviceNo}/640/480`,
        capturedAt: formatIsoOffset(new Date()),
      })
    },
  },

  // 设备详情
  {
    url: `${BASE}/devices/:id`,
    method: 'get',
    response: ({ url }: MockReq) => {
      const id = extractPathParam(url, /\/devices\/([^/]+)$/)
      const device = devicesStore.find((d) => d.id === id)
      if (!device) return resultError(ResultCode.NOT_FOUND, '设备不存在')
      return resultSuccess(device)
    },
  },

  // 新增设备
  {
    url: `${BASE}/devices`,
    method: 'post',
    response: ({ body }: MockReq<DeviceSaveParams>) => {
      if (!body?.deviceNo) return resultError(ResultCode.PARAM_ERROR, '设备编号不能为空')
      const elder = body.elderId ? eldersStore.find((e) => e.id === body.elderId) : undefined
      // 设备是硬删，length+1 会撞上已存在的编号（删 D001 后算出 D090）
      const id = nextId('D', devicesStore)
      const created = {
        id,
        deviceNo: body.deviceNo,
        elderId: elder?.id ?? null,
        elderName: elder?.name ?? null,
        communityId: elder?.communityId ?? null,
        communityName: elder?.communityName ?? null,
        roomNo: elder?.roomNo ?? null,
        type: body.type,
        rtspUrl: body.rtspUrl,
        installAddr: body.installAddr,
        algoVersion: body.algoVersion || 'fall-v1.2.1',
        config: {
          roi: [
            [0.1, 0.15],
            [0.9, 0.15],
            [0.9, 0.9],
            [0.1, 0.9],
          ] as [number, number][],
          furniture: [],
          sensitivity: 0.7,
          quietHours: ['22:00-06:00'],
        },
        status: DeviceStatus.INACTIVE,
        lastHeartbeat: null,
        createdAt: formatIsoOffset(new Date()),
      }
      devicesStore.unshift(created)
      return resultSuccess(created)
    },
  },

  // 更新设备
  {
    url: `${BASE}/devices/:id`,
    method: 'put',
    response: ({ url, body }: MockReq<Partial<DeviceSaveParams>>) => {
      const id = extractPathParam(url, /\/devices\/([^/]+)$/)
      const device = devicesStore.find((d) => d.id === id)
      if (!device) return resultError(ResultCode.NOT_FOUND, '设备不存在')

      if (body.deviceNo !== undefined) device.deviceNo = body.deviceNo
      if (body.type !== undefined) device.type = body.type
      if (body.rtspUrl !== undefined) device.rtspUrl = body.rtspUrl
      if (body.installAddr !== undefined) device.installAddr = body.installAddr
      if (body.algoVersion !== undefined) device.algoVersion = body.algoVersion
      if (body.elderId !== undefined) {
        const elder = body.elderId ? eldersStore.find((e) => e.id === body.elderId) : undefined
        device.elderId = elder?.id ?? null
        device.elderName = elder?.name ?? null
        device.communityId = elder?.communityId ?? null
        device.communityName = elder?.communityName ?? null
        device.roomNo = elder?.roomNo ?? null
      }
      return resultSuccess(device)
    },
  },

  // 删除设备
  {
    url: `${BASE}/devices/:id`,
    method: 'delete',
    response: ({ url }: MockReq) => {
      const id = extractPathParam(url, /\/devices\/([^/]+)$/)
      const idx = devicesStore.findIndex((d) => d.id === id)
      if (idx < 0) return resultError(ResultCode.NOT_FOUND, '设备不存在')
      devicesStore.splice(idx, 1)
      return resultSuccess(null)
    },
  },
] as MockMethod[]
