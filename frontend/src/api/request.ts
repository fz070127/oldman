/**
 * Axios 封装 —— 全项目唯一 HTTP 出口
 * 约定见《接口契约 v1.0》3.1：统一响应体 {code, message, data, traceId}，业务错误也是 HTTP 200
 */
import axios, { type AxiosError, type AxiosRequestConfig, type InternalAxiosRequestConfig } from 'axios'
import { ElMessage } from 'element-plus'
import 'element-plus/es/components/message/style/css'
import { useUserStore } from '@/stores/user'
import { ResultCode, type ApiResult } from '@/types/common'
import type { LoginResult } from '@/types/user'

const baseURL = import.meta.env.VITE_API_BASE || '/api'

/** 标记该请求是否已因 1002 重放过，防止死循环 */
interface RetryableConfig extends InternalAxiosRequestConfig {
  _retried?: boolean
}

/** 无需鉴权 / 不参与刷新逻辑的接口 */
const AUTH_FREE_URLS = ['/auth/login', '/auth/refresh']

const service = axios.create({ baseURL, timeout: 15000 })

// ---------------- 请求拦截：注入 token ----------------
service.interceptors.request.use((config) => {
  const { token } = useUserStore()
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// ---------------- token 刷新（并发请求共享同一次刷新） ----------------
let refreshing: Promise<string> | null = null

function refreshAccessToken(): Promise<string> {
  if (refreshing) return refreshing
  const userStore = useUserStore()
  refreshing = axios
    // 使用裸 axios，避免被本实例拦截器递归处理
    .post<ApiResult<LoginResult>>(`${baseURL}/auth/refresh`, { refreshToken: userStore.refreshToken })
    .then(({ data: res }) => {
      if (res.code !== ResultCode.SUCCESS || !res.data?.accessToken) throw new Error(res.message)
      userStore.setTokens(res.data.accessToken, res.data.refreshToken || userStore.refreshToken)
      return res.data.accessToken
    })
    .finally(() => {
      refreshing = null
    })
  return refreshing
}

/**
 * 登录态失效处理器：由 main.ts 注入（内部使用 router 跳转），
 * 避免 request → router → layouts → store → request 的循环依赖
 */
let unauthorizedHandler: (() => void | Promise<void>) | null = null
export function setUnauthorizedHandler(fn: () => void | Promise<void>) {
  unauthorizedHandler = fn
}

/** 登录态失效：清本地数据并跳登录页 */
let redirecting = false
async function redirectToLogin() {
  if (redirecting) return
  redirecting = true
  try {
    useUserStore().clearAuth()
    if (unauthorizedHandler) await unauthorizedHandler()
    else window.location.href = '/login'
  } finally {
    redirecting = false
  }
}

// ---------------- 响应拦截：解包 + 错误处理 ----------------
service.interceptors.response.use(
  // 拦截器有意把 AxiosResponse 解包为 data，类型上无法自然表达，故此处返回 any
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  async (response): Promise<any> => {
    const res = response.data as ApiResult<unknown>
    const config = response.config as RetryableConfig

    // 非标准响应体（如文件流）直接返回
    if (!res || typeof res !== 'object' || !('code' in res)) return res

    if (res.code === ResultCode.SUCCESS) return res.data

    if (res.code === ResultCode.UNAUTHORIZED) {
      const isAuthApi = AUTH_FREE_URLS.some((u) => config.url?.endsWith(u))
      if (!isAuthApi && !config._retried && useUserStore().refreshToken) {
        try {
          const newToken = await refreshAccessToken()
          config._retried = true
          config.headers.Authorization = `Bearer ${newToken}`
          return service.request(config) // 重放一次
        } catch {
          /* 刷新失败，走下方跳登录 */
        }
      }
      if (!isAuthApi) {
        await redirectToLogin()
        return Promise.reject(res)
      }
    }

    ElMessage.error(res.message || '请求失败')
    return Promise.reject(res)
  },
  (error: AxiosError<ApiResult<unknown>>) => {
    if (axios.isCancel(error)) return Promise.reject(error)
    if (!error.response) {
      // 无响应：断网 / 超时 / 跨域等
      ElMessage.error('网络异常，请稍后重试')
    } else {
      // 有响应但 HTTP 非 2xx（契约中仅未捕获异常会返回 500）
      ElMessage.error(error.response.data?.message || `服务器错误（HTTP ${error.response.status}）`)
    }
    return Promise.reject(error)
  },
)

/**
 * 类型安全的请求函数：返回值即契约中的 data 本身
 * @example const me = await request<UserInfo>({ url: '/auth/me' })
 */
export function request<T = unknown>(config: AxiosRequestConfig): Promise<T> {
  return service.request(config) as unknown as Promise<T>
}

export default request
