/**
 * 统计与看板 API —— 《接口契约 v1.0》3.10
 */
import request from './request'
import type {
  DashboardDeviceStatus,
  DashboardOverview,
  DistributionItem,
  RealtimeItem,
  TrendItem,
} from '@/types/dashboard'

/** 获取顶部 KPI 概览 */
export function getDashboardOverview() {
  return request<DashboardOverview>({ url: '/dashboard/overview', method: 'get' })
}

/** 获取告警趋势（默认近 7 天，缺失日期补 0） */
export function getDashboardTrend(days = 7) {
  return request<{ list: TrendItem[] }>({
    url: '/dashboard/trend',
    method: 'get',
    params: { days },
  })
}

/** 获取社区分布（含地图归一化坐标 x/y） */
export function getDashboardDistribution() {
  return request<{ list: DistributionItem[] }>({
    url: '/dashboard/distribution',
    method: 'get',
  })
}

/** 获取最近 20 条实时事件 */
export function getDashboardRealtime() {
  return request<{ list: RealtimeItem[] }>({
    url: '/dashboard/realtime',
    method: 'get',
  })
}

/** 获取设备在线率与离线清单 */
export function getDashboardDeviceStatus() {
  return request<DashboardDeviceStatus>({
    url: '/dashboard/device-status',
    method: 'get',
  })
}
