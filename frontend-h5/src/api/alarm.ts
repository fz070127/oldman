import {
  mockAckAlarm,
  mockDispatchAlarm,
  mockGetAlarmDetail,
  mockGetAlarmList,
} from '@/mock'
import type {
  AlarmAckParams,
  AlarmDetail,
  AlarmDispatchParams,
  AlarmItem,
  PageResult,
} from '@/types'

function delay(ms = 100): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

/** 分页获取告警列表（契约 3.7 GET /api/v1/alarms） */
export async function getAlarmList(elderId?: string): Promise<PageResult<AlarmItem>> {
  await delay(100)
  const res = mockGetAlarmList(elderId)
  return res.data
}

/** 获取告警详情（契约 3.7 GET /api/v1/alarms/{id}） */
export async function getAlarmDetail(id: string): Promise<AlarmDetail> {
  await delay(100)
  const res = mockGetAlarmDetail(id)
  return res.data
}

/** 家属确认告警 [我马上过去]（契约 3.7 POST /api/v1/alarms/{id}/ack） */
export async function ackAlarm(id: string, data?: AlarmAckParams): Promise<AlarmDetail> {
  await delay(150)
  const res = mockAckAlarm(id, data)
  return res.data
}

/** 家属求助社区派单 [联系不上，求助社区]（契约 3.7 POST /api/v1/alarms/{id}/dispatch） */
export async function dispatchAlarm(
  id: string,
  data: AlarmDispatchParams
): Promise<AlarmDetail> {
  await delay(150)
  const res = mockDispatchAlarm(id, data)
  return res.data
}
