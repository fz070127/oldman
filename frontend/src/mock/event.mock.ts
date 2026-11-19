/**
 * 事件中心 Mock —— 《接口契约 v1.0》3.6 & 3.9
 * 覆盖：多条件分页筛选、详情、媒体、标注处理、统计、POST /events/mock（同步生成告警 + WS 广播）
 */
import dayjs from 'dayjs'
import type { MockMethod } from 'vite-plugin-mock'
import {
  AlarmActionType,
  AlarmStatus,
  NotifyChannel,
  NotifyResultStatus,
  WsMessageType,
  type WsAlarmNewPayload,
} from '@/types/alarm'
import { ResultCode } from '@/types/common'
import {
  EventHandleResult,
  EventLevel,
  EventType,
  StatsRange,
  type EventHandleParams,
  type EventItem,
  type EventMockParams,
} from '@/types/event'
import { mockWs } from './index'
import {
  alarmsStore,
  devicesStore,
  eldersStore,
  eventsStore,
  syncElderAlarmStats,
  toAlarmListItem,
  type AlarmRecord,
  type EventRecord,
} from './_data'
import {
  extractPathParam,
  formatIsoOffset,
  getSearchParams,
  resultError,
  resultPage,
  resultSuccess,
} from './_util'

const BASE = '/api/v1'

interface MockReq<B = unknown> {
  url: string
  body: B
  headers?: Record<string, string | string[] | undefined>
}

function toEventListItem(ev: EventRecord): EventItem {
  return {
    id: ev.id,
    eventId: ev.eventId,
    elderId: ev.elderId,
    elderName: ev.elderName,
    roomNo: ev.roomNo,
    deviceId: ev.deviceId,
    deviceNo: ev.deviceNo,
    type: ev.type,
    level: ev.level,
    confidence: ev.confidence,
    occurredAt: ev.occurredAt,
    snapshotUrl: ev.snapshotUrl,
    clipUrl: ev.clipUrl,
    handled: ev.handled,
    handleResult: ev.handleResult,
    handleRemark: ev.handleRemark,
    handledAt: ev.handledAt,
    handlerName: ev.handlerName,
  }
}

export default [
  // 事件统计（必须在 /events/:id 之前注册）
  {
    url: `${BASE}/events/stats`,
    method: 'get',
    response: ({ url }: MockReq) => {
      const sp = getSearchParams(url)
      const range = (sp.get('range') as StatsRange) || StatsRange.DAYS_7
      const now = dayjs()
      const cutoff =
        range === StatsRange.TODAY
          ? now.startOf('day')
          : range === StatsRange.DAYS_30
            ? now.subtract(30, 'day').startOf('day')
            : now.subtract(7, 'day').startOf('day')

      const scoped = eventsStore.filter((e) => dayjs(e.occurredAt).valueOf() >= cutoff.valueOf())
      const todayStart = now.startOf('day').valueOf()
      const todayEvents = eventsStore.filter((e) => dayjs(e.occurredAt).valueOf() >= todayStart)

      const handledList = scoped.filter((e) => e.handled)
      const fpCount = handledList.filter((e) => e.handleResult === EventHandleResult.FALSE_POSITIVE).length
      const monthCutoff = now.subtract(30, 'day').startOf('day').valueOf()
      const monthHandled = eventsStore.filter(
        (e) => e.handled && dayjs(e.occurredAt).valueOf() >= monthCutoff,
      )
      const monthFp = monthHandled.filter((e) => e.handleResult === EventHandleResult.FALSE_POSITIVE).length
      const effectiveHandled = handledList.length > 0 ? handledList : monthHandled
      const effectiveFp = handledList.length > 0 ? fpCount : monthFp

      return resultSuccess({
        range,
        total: scoped.length,
        todayTotal: todayEvents.length,
        todayP0: todayEvents.filter((e) => e.level === EventLevel.P0).length,
        unhandledCount: scoped.filter((e) => !e.handled).length,
        falsePositiveCount: fpCount,
        falsePositiveRate: effectiveHandled.length
          ? Number((effectiveFp / effectiveHandled.length).toFixed(2))
          : 0,
        byLevel: {
          p0: scoped.filter((e) => e.level === EventLevel.P0).length,
          p1: scoped.filter((e) => e.level === EventLevel.P1).length,
          p2: scoped.filter((e) => e.level === EventLevel.P2).length,
        },
        byType: {
          fall: scoped.filter((e) => e.type === EventType.FALL).length,
          longLie: scoped.filter((e) => e.type === EventType.LONG_LIE).length,
        },
      })
    },
  },

  // 注入模拟事件（非生产环境演示用）
  {
    url: `${BASE}/events/mock`,
    method: 'post',
    response: ({ body }: MockReq<Partial<EventMockParams>>) => {
      const elder = eldersStore.find((e) => e.id === body?.elderId) || eldersStore[0]
      const device = devicesStore.find((d) => d.elderId === elder.id) || devicesStore[0]
      const type = body?.type || EventType.FALL
      const level = body?.level || EventLevel.P0
      const confidence = typeof body?.confidence === 'number' ? body.confidence : 0.93

      const now = dayjs()
      const occurredAt = formatIsoOffset(now)
      const createdAt = formatIsoOffset(now.add(1, 'second'))
      const evId = `EV${String(eventsStore.length + 1).padStart(4, '0')}`
      const alarmId = `A${String(alarmsStore.length + 1).padStart(4, '0')}`
      const primaryFamily = elder.families[0]?.name || '张女士'

      const newEvent: EventRecord = {
        id: evId,
        eventId: `uuid-mock-${Date.now()}`,
        elderId: elder.id,
        elderName: elder.name,
        roomNo: elder.roomNo,
        deviceId: device.id,
        deviceNo: device.deviceNo,
        type,
        level,
        confidence,
        occurredAt,
        snapshotUrl: `https://picsum.photos/seed/${evId}/640/480`,
        clipUrl: null,
        handled: false,
        handleResult: null,
        handleRemark: null,
        handledAt: null,
        features: {
          torsoAngle: 78.2,
          heightDrop: 0.61,
          stillDurationSec: 12,
          trackId: 3,
          aspectRatio: 2.1,
          kpConf: 0.42,
        },
        algoVersion: device.algoVersion,
      }

      const newAlarm: AlarmRecord = {
        id: alarmId,
        eventId: evId,
        level,
        status: AlarmStatus.PENDING,
        elderId: elder.id,
        elderName: elder.name,
        roomNo: elder.roomNo,
        communityName: elder.communityName,
        currentHandler: primaryFamily,
        escalateStep: 0,
        createdAt,
        notifiedAt: createdAt,
        ackAt: null,
        resolvedAt: null,
        responseSec: null,
        eventType: type,
        confidence,
        snapshotUrl: newEvent.snapshotUrl,
        actions: [
          {
            id: 1,
            action: AlarmActionType.NOTIFY,
            actor: 'SYSTEM',
            actorName: '系统',
            channel: NotifyChannel.PUSH,
            result: NotifyResultStatus.SENT,
            detail: { target: primaryFamily },
            createdAt,
          },
        ],
        remark: null,
      }

      // 插入数组头部，确保列表第一条即为新生成项
      eventsStore.unshift(newEvent)
      alarmsStore.unshift(newAlarm)
      syncElderAlarmStats()

      // 通过 mockWs 广播 ALARM_NEW
      mockWs.emit<WsAlarmNewPayload>({
        type: WsMessageType.ALARM_NEW,
        ts: createdAt,
        data: {
          alarmId,
          level,
          elderId: elder.id,
          elderName: elder.name,
          communityName: elder.communityName,
          roomNo: elder.roomNo,
          eventType: type,
          confidence,
          occurredAt,
          snapshotUrl: newEvent.snapshotUrl,
          remainingSec: 60,
        },
      })

      return resultSuccess({
        event: toEventListItem(newEvent),
        alarm: toAlarmListItem(newAlarm),
      })
    },
  },

  // 事件分页列表
  {
    url: `${BASE}/events`,
    method: 'get',
    response: ({ url }: MockReq) => {
      const sp = getSearchParams(url)
      const elderId = sp.get('elderId') || ''
      const deviceId = sp.get('deviceId') || ''
      const type = sp.get('type') || ''
      const level = sp.get('level') || ''
      const startTime = sp.get('startTime') || ''
      const endTime = sp.get('endTime') || ''
      const handledStr = sp.get('handled') ?? ''
      const page = Number(sp.get('page') || 1)
      const pageSize = Number(sp.get('pageSize') || 20)

      let list = [...eventsStore]
      if (elderId) list = list.filter((e) => e.elderId === elderId)
      if (deviceId) list = list.filter((e) => e.deviceId === deviceId)
      if (type) list = list.filter((e) => e.type === type)
      if (level) list = list.filter((e) => e.level === level)
      if (startTime) {
        const startMs = new Date(startTime).getTime()
        if (!Number.isNaN(startMs)) list = list.filter((e) => new Date(e.occurredAt).getTime() >= startMs)
      }
      if (endTime) {
        const endMs = new Date(endTime).getTime()
        if (!Number.isNaN(endMs)) list = list.filter((e) => new Date(e.occurredAt).getTime() <= endMs)
      }
      if (handledStr === 'true' || handledStr === 'false') {
        const want = handledStr === 'true'
        list = list.filter((e) => e.handled === want)
      }

      return resultPage(list.map(toEventListItem), page, pageSize)
    },
  },

  // 媒体 URL
  {
    url: `${BASE}/events/:id/media`,
    method: 'get',
    response: ({ url }: MockReq) => {
      const id = extractPathParam(url, /\/events\/([^/]+)\/media/)
      const ev = eventsStore.find((e) => e.id === id)
      if (!ev) return resultError(ResultCode.NOT_FOUND, '事件不存在')

      const keyframes = Array.from(
        { length: 6 },
        (_, idx) => `https://picsum.photos/seed/${ev.id}-kf-${idx + 1}/320/240`,
      )
      return resultSuccess({
        snapshotUrl: `${ev.snapshotUrl}?sig=mock-sig`,
        clipUrl: ev.clipUrl
          ? `${ev.clipUrl}?sig=mock-sig`
          : 'https://interactive-examples.mdn.mozilla.net/media/cc0-videos/flower.mp4',
        keyframes,
        expiresInSec: 900,
      })
    },
  },

  // 标注处理事件
  {
    url: `${BASE}/events/:id/handle`,
    method: 'put',
    response: ({ url, body }: MockReq<EventHandleParams>) => {
      const id = extractPathParam(url, /\/events\/([^/]+)\/handle/)
      const ev = eventsStore.find((e) => e.id === id)
      if (!ev) return resultError(ResultCode.NOT_FOUND, '事件不存在')
      if (!body?.result) return resultError(ResultCode.PARAM_ERROR, '缺少处理结论')

      ev.handled = true
      ev.handleResult = body.result
      ev.handleRemark = body.remark || ''
      ev.handledAt = formatIsoOffset(new Date())
      ev.handlerName = '系统管理员'
      return resultSuccess(toEventListItem(ev))
    },
  },

  // 事件详情
  {
    url: `${BASE}/events/:id`,
    method: 'get',
    response: ({ url }: MockReq) => {
      const id = extractPathParam(url, /\/events\/([^/]+)$/)
      const ev = eventsStore.find((e) => e.id === id)
      if (!ev) return resultError(ResultCode.NOT_FOUND, '事件不存在')

      const keyframes = Array.from(
        { length: 6 },
        (_, idx) => `https://picsum.photos/seed/${ev.id}-kf-${idx + 1}/320/240`,
      )
      return resultSuccess({
        ...ev,
        media: {
          snapshotUrl: `${ev.snapshotUrl}?sig=mock-sig`,
          clipUrl: ev.clipUrl
            ? `${ev.clipUrl}?sig=mock-sig`
            : 'https://interactive-examples.mdn.mozilla.net/media/cc0-videos/flower.mp4',
          keyframes,
          expiresInSec: 900,
        },
      })
    },
  },
] as MockMethod[]
