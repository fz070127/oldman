import type { AlarmStatus, EventLevel, EventType } from '@/types'

/**
 * 根据当前小时返回问候语（早上好 / 下午好 / 晚上好）
 */
export function getGreetingByTime(date: Date = new Date()): string {
  const hour = date.getHours()
  if (hour >= 5 && hour < 12) {
    return '早上好'
  }
  if (hour >= 12 && hour < 18) {
    return '下午好'
  }
  return '晚上好'
}

/**
 * 事件类型中文名映射
 */
export function getEventTypeLabel(type: EventType): string {
  const map: Record<EventType, string> = {
    FALL: '跌倒告警',
    LONG_LIE: '久躺告警',
  }
  return map[type] || '异常告警'
}

/**
 * 告警页顶部大标题映射
 */
export function getAlarmTitleLabel(type: EventType): string {
  const map: Record<EventType, string> = {
    FALL: '检测到跌倒',
    LONG_LIE: '检测到跌倒',
  }
  return map[type] || '检测到跌倒'
}

/**
 * 告警级别文案映射
 */
export function getLevelLabel(level: EventLevel): string {
  const map: Record<EventLevel, string> = {
    P0: 'P0 紧急',
    P1: 'P1 重要',
    P2: 'P2 一般',
  }
  return map[level] || level
}

/**
 * 告警状态中文名与样式分类映射
 */
export function getAlarmStatusMeta(status: AlarmStatus): {
  label: string
  theme: 'danger' | 'primary' | 'warning' | 'success' | 'muted'
} {
  const map: Record<
    AlarmStatus,
    { label: string; theme: 'danger' | 'primary' | 'warning' | 'success' | 'muted' }
  > = {
    PENDING: { label: '待处理', theme: 'danger' },
    ESCALATED: { label: '已升级待处理', theme: 'danger' },
    ACKNOWLEDGED: { label: '家属已响应', theme: 'primary' },
    COMMUNITY_DISPATCHED: { label: '网格员前往中', theme: 'warning' },
    RESOLVED: { label: '已平安解除', theme: 'success' },
    FALSE_POSITIVE: { label: '误报已排除', theme: 'muted' },
  }
  return map[status] || { label: status, theme: 'muted' }
}

/**
 * 格式化 ISO 时间为 YYYY-MM-DD HH:mm:ss 或 MM-DD HH:mm
 */
export function formatDateTime(isoStr: string, full = false): string {
  if (!isoStr) return '--'
  const d = new Date(isoStr)
  if (Number.isNaN(d.getTime())) return isoStr
  const pad = (n: number) => String(n).padStart(2, '0')
  const year = d.getFullYear()
  const month = pad(d.getMonth() + 1)
  const day = pad(d.getDate())
  const hours = pad(d.getHours())
  const minutes = pad(d.getMinutes())
  const seconds = pad(d.getSeconds())
  if (full) {
    return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`
  }
  return `${month}-${day} ${hours}:${minutes}`
}
