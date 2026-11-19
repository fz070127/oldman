/**
 * 告警中心 Mock —— 《接口契约 v1.0》3.7
 * 覆盖：分页筛选、待处理数、统计、详情（actions + 中文 timeline）、ack / dispatch / resolve
 */
import dayjs from 'dayjs'
import type { MockMethod } from 'vite-plugin-mock'
import {
  AlarmActionType,
  AlarmStatus,
  WsMessageType,
  type AlarmAckParams,
  type AlarmDispatchParams,
  type AlarmResolveParams,
  type WsAlarmUpdatePayload,
} from '@/types/alarm'
import { ResultCode } from '@/types/common'
import { EventHandleResult, StatsRange } from '@/types/event'
import { mockWs } from './index'
import {
  GUARDIANS,
  alarmsStore,
  buildAlarmDetail,
  eventsStore,
  refreshPendingAlarmTimestamps,
  toAlarmListItem,
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
}

function emitAlarmUpdate(alarm: (typeof alarmsStore)[number]) {
  mockWs.emit<WsAlarmUpdatePayload>({
    type: WsMessageType.ALARM_UPDATE,
    ts: formatIsoOffset(new Date()),
    data: {
      alarmId: alarm.id,
      status: alarm.status,
      escalateStep: alarm.escalateStep,
      currentHandler: alarm.currentHandler,
    },
  })
}

export default [
  // 当前待处理告警数（必须在 /alarms/:id 之前注册）
  {
    url: `${BASE}/alarms/pending-count`,
    method: 'get',
    response: () => {
      refreshPendingAlarmTimestamps()
      const count = alarmsStore.filter((a) => a.status === AlarmStatus.PENDING).length
      return resultSuccess({ count })
    },
  },

  // 告警统计（必须在 /alarms/:id 之前注册）
  {
    url: `${BASE}/alarms/stats`,
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

      const scoped = alarmsStore.filter((a) => dayjs(a.createdAt).valueOf() >= cutoff.valueOf())
      const todayStart = now.startOf('day').valueOf()
      const todayTotal = alarmsStore.filter((a) => dayjs(a.createdAt).valueOf() >= todayStart).length

      const withResp = scoped.filter((a) => typeof a.responseSec === 'number')
      const avgResponseSec = withResp.length
        ? Math.round(withResp.reduce((s, a) => s + (a.responseSec || 0), 0) / withResp.length)
        : 0

      return resultSuccess({
        range,
        total: scoped.length,
        todayTotal,
        pendingCount: alarmsStore.filter((a) => a.status === AlarmStatus.PENDING).length,
        acknowledgedCount: scoped.filter((a) => a.status === AlarmStatus.ACKNOWLEDGED).length,
        escalatedCount: scoped.filter((a) => a.status === AlarmStatus.ESCALATED).length,
        dispatchedCount: scoped.filter((a) => a.status === AlarmStatus.COMMUNITY_DISPATCHED).length,
        resolvedCount: scoped.filter((a) => a.status === AlarmStatus.RESOLVED).length,
        falsePositiveCount: scoped.filter((a) => a.status === AlarmStatus.FALSE_POSITIVE).length,
        avgResponseSec,
      })
    },
  },

  // 告警分页列表
  {
    url: `${BASE}/alarms`,
    method: 'get',
    response: ({ url }: MockReq) => {
      const sp = getSearchParams(url)
      const status = sp.get('status') || ''
      const level = sp.get('level') || ''
      const elderId = sp.get('elderId') || ''
      const startTime = sp.get('startTime') || ''
      const endTime = sp.get('endTime') || ''
      const page = Number(sp.get('page') || 1)
      const pageSize = Number(sp.get('pageSize') || 20)

      // 先结算到点的升级，避免 status 筛选与返回值不一致
      refreshPendingAlarmTimestamps()
      let list = [...alarmsStore]
      // status 支持单个枚举或逗号分隔多状态（如 RESOLVED,FALSE_POSITIVE 用于“已完结”Tab）
      if (status) {
        const statusSet = new Set(
          status
            .split(',')
            .map((s) => s.trim())
            .filter(Boolean),
        )
        if (statusSet.size > 0) list = list.filter((a) => statusSet.has(a.status))
      }
      if (level) list = list.filter((a) => a.level === level)
      if (elderId) list = list.filter((a) => a.elderId === elderId)
      if (startTime) {
        const startMs = new Date(startTime).getTime()
        if (!Number.isNaN(startMs)) list = list.filter((a) => new Date(a.createdAt).getTime() >= startMs)
      }
      if (endTime) {
        const endMs = new Date(endTime).getTime()
        if (!Number.isNaN(endMs)) list = list.filter((a) => new Date(a.createdAt).getTime() <= endMs)
      }

      return resultPage(list.map(toAlarmListItem), page, pageSize)
    },
  },

  // 确认告警（PENDING | ESCALATED → ACKNOWLEDGED）
  {
    url: `${BASE}/alarms/:id/ack`,
    method: 'post',
    response: ({ url, body }: MockReq<AlarmAckParams>) => {
      const id = extractPathParam(url, /\/alarms\/([^/]+)\/ack/)
      const alarm = alarmsStore.find((a) => a.id === id)
      if (!alarm) return resultError(ResultCode.NOT_FOUND, '告警不存在')
      if (alarm.status !== AlarmStatus.PENDING && alarm.status !== AlarmStatus.ESCALATED) {
        return resultError(ResultCode.STATE_CONFLICT, '当前状态不允许确认操作')
      }

      const nowStr = formatIsoOffset(new Date())
      alarm.status = AlarmStatus.ACKNOWLEDGED
      alarm.ackAt = nowStr
      alarm.responseSec = Math.max(
        1,
        Math.round((new Date(nowStr).getTime() - new Date(alarm.notifiedAt).getTime()) / 1000),
      )
      alarm.actions.push({
        id: alarm.actions.length + 1,
        action: AlarmActionType.ACK,
        actor: 'U001',
        actorName: alarm.currentHandler || '值班员',
        detail: body?.note ? { note: body.note } : undefined,
        createdAt: nowStr,
      })
      emitAlarmUpdate(alarm)
      return resultSuccess(buildAlarmDetail(alarm))
    },
  },

  // 派单网格员（ESCALATED | PENDING → COMMUNITY_DISPATCHED）
  {
    url: `${BASE}/alarms/:id/dispatch`,
    method: 'post',
    response: ({ url, body }: MockReq<AlarmDispatchParams>) => {
      const id = extractPathParam(url, /\/alarms\/([^/]+)\/dispatch/)
      const alarm = alarmsStore.find((a) => a.id === id)
      if (!alarm) return resultError(ResultCode.NOT_FOUND, '告警不存在')
      if (alarm.status !== AlarmStatus.PENDING && alarm.status !== AlarmStatus.ESCALATED) {
        return resultError(ResultCode.STATE_CONFLICT, '当前状态不允许派单操作')
      }

      const guardian = GUARDIANS.find((g) => g.id === body?.guardianId) || GUARDIANS[0]
      const nowStr = formatIsoOffset(new Date())
      alarm.status = AlarmStatus.COMMUNITY_DISPATCHED
      alarm.currentHandler = guardian.name
      alarm.actions.push({
        id: alarm.actions.length + 1,
        action: AlarmActionType.DISPATCH,
        actor: 'U001',
        actorName: '社区值班员',
        detail: { guardianId: guardian.id, guardianName: guardian.name, note: body?.note },
        createdAt: nowStr,
      })
      emitAlarmUpdate(alarm)
      return resultSuccess(buildAlarmDetail(alarm))
    },
  },

  // 完结告警（ACKNOWLEDGED | COMMUNITY_DISPATCHED → RESOLVED | FALSE_POSITIVE）
  {
    url: `${BASE}/alarms/:id/resolve`,
    method: 'post',
    response: ({ url, body }: MockReq<AlarmResolveParams>) => {
      const id = extractPathParam(url, /\/alarms\/([^/]+)\/resolve/)
      const alarm = alarmsStore.find((a) => a.id === id)
      if (!alarm) return resultError(ResultCode.NOT_FOUND, '告警不存在')
      if (
        alarm.status !== AlarmStatus.ACKNOWLEDGED &&
        alarm.status !== AlarmStatus.COMMUNITY_DISPATCHED
      ) {
        return resultError(ResultCode.STATE_CONFLICT, '当前状态不允许完结操作')
      }

      const nowStr = formatIsoOffset(new Date())
      const isFalse = body?.result === EventHandleResult.FALSE_POSITIVE
      alarm.status = isFalse ? AlarmStatus.FALSE_POSITIVE : AlarmStatus.RESOLVED
      alarm.resolvedAt = nowStr
      alarm.remark = body?.note || null
      alarm.needFollowUp = !!body?.needFollowUp
      if (!alarm.ackAt) alarm.ackAt = nowStr
      if (alarm.responseSec === null) {
        alarm.responseSec = Math.max(
          1,
          Math.round((new Date(alarm.ackAt).getTime() - new Date(alarm.notifiedAt).getTime()) / 1000),
        )
      }

      alarm.actions.push({
        id: alarm.actions.length + 1,
        action: isFalse ? AlarmActionType.MARK_FALSE : AlarmActionType.RESOLVE,
        actor: 'U001',
        actorName: alarm.currentHandler || '值班员',
        detail: { note: body?.note, needFollowUp: !!body?.needFollowUp },
        createdAt: nowStr,
      })

      // 契约 3.7：result 为 FALSE_POSITIVE 时联动更新关联事件 handleResult
      const ev = eventsStore.find((e) => e.id === alarm.eventId)
      if (ev) {
        ev.handled = true
        ev.handleResult = body?.result || EventHandleResult.TRUE_FALL
        ev.handleRemark = body?.note || ev.handleRemark
        ev.handledAt = nowStr
      }

      emitAlarmUpdate(alarm)
      return resultSuccess(buildAlarmDetail(alarm))
    },
  },

  // 告警详情
  {
    url: `${BASE}/alarms/:id`,
    method: 'get',
    response: ({ url }: MockReq) => {
      const id = extractPathParam(url, /\/alarms\/([^/]+)$/)
      const alarm = alarmsStore.find((a) => a.id === id)
      if (!alarm) return resultError(ResultCode.NOT_FOUND, '告警不存在')
      return resultSuccess(buildAlarmDetail(alarm))
    },
  },
] as MockMethod[]
