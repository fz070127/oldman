/**
 * 统计与看板 Mock —— 《接口契约 v1.0》3.10
 * 覆盖：overview / trend（缺失日期补 0）/ distribution / realtime / device-status
 */
import dayjs from 'dayjs'
import type { MockMethod } from 'vite-plugin-mock'
import { AlarmStatus } from '@/types/alarm'
import type { DistributionItem, RealtimeItem, TrendItem } from '@/types/dashboard'
import { DeviceStatus } from '@/types/device'
import { ElderStatus } from '@/types/elder'
import { EventHandleResult, EventLevel } from '@/types/event'
import {
  COMMUNITIES,
  alarmsStore,
  devicesStore,
  eldersStore,
  eventsStore,
} from './_data'
import { formatIsoOffset, getSearchParams, resultSuccess } from './_util'

const BASE = '/api/v1'

interface MockReq {
  url: string
}

export default [
  // 顶部 KPI 概览
  {
    url: `${BASE}/dashboard/overview`,
    method: 'get',
    response: () => {
      const activeElders = eldersStore.filter((e) => e.status !== ElderStatus.DECEASED)
      const elderOnline = activeElders.filter((e) => e.deviceOnline).length

      const deviceOnline = devicesStore.filter((d) => d.status === DeviceStatus.ONLINE).length
      const deviceOffline = devicesStore.filter((d) => d.status !== DeviceStatus.ONLINE).length

      const todayStart = dayjs().startOf('day').valueOf()
      const todayAlarms = alarmsStore.filter((a) => new Date(a.createdAt).getTime() >= todayStart)
      const alarmPending = alarmsStore.filter((a) => a.status === AlarmStatus.PENDING).length
      const alarmP0Today = todayAlarms.filter((a) => a.level === EventLevel.P0).length

      const responded = alarmsStore.filter((a) => typeof a.responseSec === 'number')
      const avgResponseSec = responded.length
        ? Math.round(responded.reduce((s, a) => s + (a.responseSec || 0), 0) / responded.length)
        : 0

      const handledEvents = eventsStore.filter((e) => e.handled)
      const fpEvents = handledEvents.filter((e) => e.handleResult === EventHandleResult.FALSE_POSITIVE)
      const falsePositiveRate = handledEvents.length
        ? Number((fpEvents.length / handledEvents.length).toFixed(2))
        : 0

      return resultSuccess({
        elderTotal: activeElders.length,
        elderOnline,
        deviceTotal: devicesStore.length,
        deviceOnline,
        deviceOffline,
        alarmToday: todayAlarms.length,
        alarmPending,
        alarmP0Today,
        avgResponseSec,
        falsePositiveRate,
        updatedAt: formatIsoOffset(new Date()),
      })
    },
  },

  // 告警趋势（缺失日期补 0，条数严格等于 days）
  {
    url: `${BASE}/dashboard/trend`,
    method: 'get',
    response: ({ url }: MockReq) => {
      const sp = getSearchParams(url)
      const days = Math.min(Math.max(Number(sp.get('days') || 7), 1), 90)
      const today = dayjs().startOf('day')

      // 按 YYYY-MM-DD 聚合事件（也可直观反映 P0/P1/P2 每日趋势）
      const bucket = new Map<string, TrendItem>()
      for (let i = days - 1; i >= 0; i--) {
        const dStr = today.subtract(i, 'day').format('YYYY-MM-DD')
        bucket.set(dStr, { date: dStr, p0: 0, p1: 0, p2: 0, total: 0 })
      }

      for (const ev of eventsStore) {
        const dStr = dayjs(ev.occurredAt).format('YYYY-MM-DD')
        const item = bucket.get(dStr)
        if (!item) continue
        if (ev.level === EventLevel.P0) item.p0 += 1
        else if (ev.level === EventLevel.P1) item.p1 += 1
        else item.p2 += 1
        item.total += 1
      }

      return resultSuccess({ list: Array.from(bucket.values()) })
    },
  },

  // 社区分布
  {
    url: `${BASE}/dashboard/distribution`,
    method: 'get',
    response: () => {
      const todayStart = dayjs().startOf('day').valueOf()
      const list: DistributionItem[] = COMMUNITIES.map((comm) => {
        const elderTotal = eldersStore.filter(
          (e) => e.communityId === comm.id && e.status !== ElderStatus.DECEASED,
        ).length
        const alarmToday = alarmsStore.filter(
          (a) => a.communityName === comm.name && new Date(a.createdAt).getTime() >= todayStart,
        ).length
        return {
          communityId: comm.id,
          communityName: comm.name,
          elderTotal,
          alarmToday,
          x: comm.x,
          y: comm.y,
        }
      })

      return resultSuccess({ list })
    },
  },

  // 最近 20 条事件
  {
    url: `${BASE}/dashboard/realtime`,
    method: 'get',
    response: () => {
      const list: RealtimeItem[] = eventsStore.slice(0, 20).map((ev) => {
        const elder = eldersStore.find((e) => e.id === ev.elderId)
        return {
          id: ev.id,
          elderId: ev.elderId,
          elderName: ev.elderName,
          communityId: elder?.communityId || 'C01',
          communityName: elder?.communityName || '幸福里社区',
          roomNo: ev.roomNo,
          type: ev.type,
          level: ev.level,
          confidence: ev.confidence,
          occurredAt: ev.occurredAt,
          snapshotUrl: ev.snapshotUrl,
        }
      })

      return resultSuccess({ list })
    },
  },

  // 设备在线率与离线清单
  {
    url: `${BASE}/dashboard/device-status`,
    method: 'get',
    response: () => {
      const total = devicesStore.length
      const online = devicesStore.filter((d) => d.status === DeviceStatus.ONLINE).length
      const offline = devicesStore.filter((d) => d.status === DeviceStatus.OFFLINE).length
      const fault = devicesStore.filter((d) => d.status === DeviceStatus.FAULT).length
      const inactive = devicesStore.filter((d) => d.status === DeviceStatus.INACTIVE).length
      const offlineList = devicesStore
        .filter((d) => d.status !== DeviceStatus.ONLINE)
        .map((d) => ({
          id: d.id,
          deviceNo: d.deviceNo,
          elderId: d.elderId,
          elderName: d.elderName,
          communityName: d.communityName,
          roomNo: d.roomNo,
          status: d.status,
          lastHeartbeat: d.lastHeartbeat,
        }))

      return resultSuccess({
        total,
        online,
        offline,
        fault,
        inactive,
        onlineRate: total ? Number((online / total).toFixed(4)) : 0,
        offlineList,
      })
    },
  },
] as MockMethod[]
