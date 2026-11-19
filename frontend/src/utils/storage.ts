/**
 * localStorage 封装，统一 key 前缀，避免与其他应用冲突
 */
const PREFIX = 'yl_'

export const StorageKeys = {
  TOKEN: 'token',
  REFRESH_TOKEN: 'refresh_token',
  USER_INFO: 'user_info',
  SIDEBAR_COLLAPSED: 'sidebar_collapsed',
  REMEMBER_USERNAME: 'remember_username',
  ALARM_MUTED: 'alarm_muted',
} as const

export const storage = {
  /** 读取原始字符串 */
  get(key: string): string | null {
    return localStorage.getItem(PREFIX + key)
  },
  set(key: string, value: string): void {
    localStorage.setItem(PREFIX + key, value)
  },
  /** 读取 JSON，解析失败返回 null */
  getJSON<T>(key: string): T | null {
    const raw = localStorage.getItem(PREFIX + key)
    if (!raw) return null
    try {
      return JSON.parse(raw) as T
    } catch {
      return null
    }
  },
  setJSON(key: string, value: unknown): void {
    localStorage.setItem(PREFIX + key, JSON.stringify(value))
  },
  remove(key: string): void {
    localStorage.removeItem(PREFIX + key)
  },
}
