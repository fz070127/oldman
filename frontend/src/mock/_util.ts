/**
 * Mock 工具函数（文件名以 _ 开头，不会被 vite-plugin-mock 当作接口注册）
 * 响应结构严格遵循《接口契约 v1.0》3.1
 */
import dayjs from 'dayjs'
import type { ApiResult, PageResult } from '@/types/common'

/** 生成 traceId */
export function genTraceId(): string {
  return Math.random().toString(16).slice(2, 14).padEnd(12, '0')
}

export function resultSuccess<T>(data: T, message = 'ok'): ApiResult<T> {
  return { code: 0, message, data, traceId: genTraceId() }
}

export function resultError(code: number, message: string): ApiResult<null> {
  return { code, message, data: null, traceId: genTraceId() }
}

export function resultPage<T>(list: T[], page = 1, pageSize = 20): ApiResult<PageResult<T>> {
  const size = Math.min(Math.max(Number(pageSize) || 20, 1), 100)
  const p = Math.max(Number(page) || 1, 1)
  const start = (p - 1) * size
  return resultSuccess({
    list: list.slice(start, start + size),
    total: list.length,
    page: p,
    pageSize: size,
  })
}

/** 从请求头中取 Bearer token */
export function getRequestToken(headers?: Record<string, string | string[] | undefined>): string | null {
  const raw = headers?.authorization ?? headers?.Authorization
  const value = Array.isArray(raw) ? raw[0] : raw
  if (!value || !value.startsWith('Bearer ')) return null
  return value.slice(7)
}

/**
 * 从请求 URL 提取 URLSearchParams
 * 避免 vite-plugin-mock 在动态路由匹配时覆盖 query 对象导致查询参数丢失
 */
export function getSearchParams(url?: string): URLSearchParams {
  if (!url) return new URLSearchParams()
  const idx = url.indexOf('?')
  return idx >= 0 ? new URLSearchParams(url.slice(idx + 1)) : new URLSearchParams()
}

/** 从路径末尾或指定段提取路由参数 */
export function extractPathParam(url: string | undefined, pattern: RegExp): string {
  if (!url) return ''
  const pathname = url.split('?')[0]
  const matched = pathname.match(pattern)
  return matched?.[1] ? decodeURIComponent(matched[1]) : ''
}

/** 格式化为带 +08:00 时区的 ISO 8601 字符串（契约 3.1：如 2026-11-18T10:23:45+08:00） */
export function formatIsoOffset(date: Date | number | string | dayjs.Dayjs): string {
  const d = dayjs(date)
  // 统一输出东八区 ISO 格式（YYYY-MM-DDTHH:mm:ss+08:00）
  return d.format('YYYY-MM-DDTHH:mm:ss+08:00')
}

/** 手机号脱敏：13812348888 → 138****8888 */
export function maskPhone(phone: string): string {
  if (!phone || phone.length < 7) return phone
  if (phone.includes('*')) return phone
  return `${phone.slice(0, 3)}****${phone.slice(-4)}`
}

/** 根据 birthDate（YYYY-MM-DD）动态计算年龄 */
export function calcAge(birthDate: string, refDate?: Date): number {
  const birth = dayjs(birthDate)
  const now = refDate ? dayjs(refDate) : dayjs()
  return Math.max(0, now.diff(birth, 'year'))
}

/**
 * 生成集合内唯一的自增业务 ID：取现有最大编号 +1
 *
 * 不能再用 `list.length + 1`——删除会让 length 变小，算出的编号会撞上已存在的记录。
 * 例：删掉 D001 后 length=89，`D090` 已被占用却会被再次分配。
 *
 * @param prefix 编号前缀，须与既有 ID 完全匹配（`E` 不会误匹配 `EV0500`）
 * @param list   现有记录，只需 id 字段
 * @param pad    编号补零位数
 */
export function nextId(prefix: string, list: ReadonlyArray<{ id: string }>, pad = 3): string {
  const pattern = new RegExp(`^${prefix}(\\d+)$`)
  let max = 0
  for (const item of list) {
    const matched = pattern.exec(item.id)
    if (matched) max = Math.max(max, Number(matched[1]))
  }
  return `${prefix}${String(max + 1).padStart(pad, '0')}`
}

/** 确定性伪随机数生成器（Mulberry32），保证每次重启基础分布可复现 */
export function createSeededRandom(seed: number): () => number {
  let s = seed >>> 0
  return () => {
    s += 0x6d2b79f5
    let t = Math.imul(s ^ (s >>> 15), 1 | s)
    t ^= t + Math.imul(t ^ (t >>> 7), 61 | t)
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}
