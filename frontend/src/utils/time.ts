/**
 * 时间格式化工具 —— 统一相对时间与心跳异常判定
 */
import dayjs from 'dayjs'

/**
 * 将时间戳转为中文相对时间：
 * - < 60 秒：「刚刚」或「X 秒前」
 * - < 60 分钟：「X 分钟前」
 * - < 24 小时：「X 小时前」
 * - < 30 天：「X 天前」
 * - 其余：YYYY-MM-DD HH:mm
 */
export function formatRelativeTime(ts?: string | null): string {
  if (!ts) return '暂无记录'
  const target = dayjs(ts)
  if (!target.isValid()) return '暂无记录'

  const diffSec = Math.max(0, Math.floor((Date.now() - target.valueOf()) / 1000))
  if (diffSec < 15) return '刚刚'
  if (diffSec < 60) return `${diffSec} 秒前`

  const diffMin = Math.floor(diffSec / 60)
  if (diffMin < 60) return `${diffMin} 分钟前`

  const diffHour = Math.floor(diffMin / 60)
  if (diffHour < 24) return `${diffHour} 小时前`

  const diffDay = Math.floor(diffHour / 24)
  if (diffDay < 30) return `${diffDay} 天前`

  return target.format('YYYY-MM-DD HH:mm')
}

/**
 * 判断心跳是否超过指定分钟数（默认 5 分钟）
 * 用于：设备状态为「在线」但心跳超过 5 分钟时标红提示异常
 */
export function isHeartbeatStale(ts?: string | null, thresholdMinutes = 5): boolean {
  if (!ts) return true
  const target = dayjs(ts)
  if (!target.isValid()) return true
  const diffSec = (Date.now() - target.valueOf()) / 1000
  return diffSec > thresholdMinutes * 60
}

/** 格式化完整日期时间 YYYY-MM-DD HH:mm:ss */
export function formatDateTime(ts?: string | null): string {
  if (!ts) return '-'
  const d = dayjs(ts)
  return d.isValid() ? d.format('YYYY-MM-DD HH:mm:ss') : '-'
}
