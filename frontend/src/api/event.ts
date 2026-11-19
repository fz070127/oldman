/**
 * 事件中心 API —— 《接口契约 v1.0》3.6
 */
import request from './request'
import type { PageResult } from '@/types/common'
import type {
  EventDetail,
  EventHandleParams,
  EventItem,
  EventMedia,
  EventMockParams,
  EventQuery,
  EventStats,
  StatsRange,
} from '@/types/event'
import type { AlarmItem } from '@/types/alarm'

/** 分页获取事件列表 */
export function getEventList(params: EventQuery) {
  return request<PageResult<EventItem>>({ url: '/events', method: 'get', params })
}

/** 获取事件详情 */
export function getEventDetail(id: string) {
  return request<EventDetail>({ url: `/events/${id}`, method: 'get' })
}

/** 获取带时效签名的事件媒体（关键帧序列、截图、脱敏片段） */
export function getEventMedia(id: string) {
  return request<EventMedia>({ url: `/events/${id}/media`, method: 'get' })
}

/** 标注处理事件（确认属实 / 标记误报） */
export function handleEvent(id: string, data: EventHandleParams) {
  return request<EventItem>({ url: `/events/${id}/handle`, method: 'put', data })
}

/** 获取事件统计数据（today | 7d | 30d） */
export function getEventStats(range: StatsRange = 'today') {
  return request<EventStats>({ url: '/events/stats', method: 'get', params: { range } })
}

/** 注入模拟事件（非生产环境演示用） */
export function createMockEvent(data: EventMockParams) {
  return request<{ event: EventItem; alarm: AlarmItem }>({ url: '/events/mock', method: 'post', data })
}
