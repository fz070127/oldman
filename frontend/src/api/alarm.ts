/**
 * 告警中心 API —— 《接口契约 v1.0》3.7
 */
import request from './request'
import type { PageResult } from '@/types/common'
import type {
  AlarmAckParams,
  AlarmDetail,
  AlarmDispatchParams,
  AlarmItem,
  AlarmPendingCount,
  AlarmQuery,
  AlarmResolveParams,
  AlarmStats,
} from '@/types/alarm'
import type { StatsRange } from '@/types/event'

/** 分页获取告警列表 */
export function getAlarmList(params: AlarmQuery) {
  return request<PageResult<AlarmItem>>({ url: '/alarms', method: 'get', params })
}

/** 获取告警详情 */
export function getAlarmDetail(id: string) {
  return request<AlarmDetail>({ url: `/alarms/${id}`, method: 'get' })
}

/** 确认告警（PENDING | ESCALATED → ACKNOWLEDGED） */
export function ackAlarm(id: string, data?: AlarmAckParams) {
  return request<AlarmDetail>({ url: `/alarms/${id}/ack`, method: 'post', data: data ?? {} })
}

/** 派单网格员（PENDING | ESCALATED → COMMUNITY_DISPATCHED） */
export function dispatchAlarm(id: string, data: AlarmDispatchParams) {
  return request<AlarmDetail>({ url: `/alarms/${id}/dispatch`, method: 'post', data })
}

/** 完结告警（ACKNOWLEDGED | COMMUNITY_DISPATCHED → RESOLVED | FALSE_POSITIVE） */
export function resolveAlarm(id: string, data: AlarmResolveParams) {
  return request<AlarmDetail>({ url: `/alarms/${id}/resolve`, method: 'post', data })
}

/** 获取当前用户待处理告警数 */
export function getAlarmPendingCount() {
  return request<AlarmPendingCount>({ url: '/alarms/pending-count', method: 'get' })
}

/** 获取告警统计（today | 7d | 30d） */
export function getAlarmStats(range: StatsRange = 'today') {
  return request<AlarmStats>({ url: '/alarms/stats', method: 'get', params: { range } })
}
