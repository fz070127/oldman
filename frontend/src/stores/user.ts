import { defineStore } from 'pinia'
import { login as loginApi, logout as logoutApi, getMe } from '@/api/auth'
import router, { resetDynamicRoutes } from '@/router'
import { useTabsStore } from '@/stores/tabs'
import { storage, StorageKeys } from '@/utils/storage'
import { ROLE_NAME_MAP, type LoginParams, type UserInfo } from '@/types/user'

interface UserState {
  token: string
  refreshToken: string
  userInfo: UserInfo | null
  permissions: string[]
  menus: string[]
}

/**
 * 权限码单条匹配：支持全通配 "*" 与模块级通配 "module:*"（如 "device:*" 匹配 "device:read"）
 */
function matchPermission(owned: string, required: string): boolean {
  if (owned === '*' || owned === required) return true
  if (owned.endsWith(':*')) {
    const prefix = owned.slice(0, -1) // e.g. "device:"
    return required.startsWith(prefix)
  }
  return false
}

export const useUserStore = defineStore('user', {
  state: (): UserState => {
    const userInfo = storage.getJSON<UserInfo>(StorageKeys.USER_INFO)
    return {
      // token 持久化到 localStorage，刷新页面不丢登录态
      token: storage.get(StorageKeys.TOKEN) || '',
      refreshToken: storage.get(StorageKeys.REFRESH_TOKEN) || '',
      // userInfo 从接口实时为准（刷新时触发守卫 fetchMe 重新拉取并落盘）
      userInfo: null,
      permissions: userInfo?.permissions ?? [],
      menus: userInfo?.menus ?? [],
    }
  },

  getters: {
    isLoggedIn: (state) => !!state.token,
    displayName: (state) => state.userInfo?.nickname || state.userInfo?.username || '未命名用户',
    roleName: (state) =>
      state.userInfo?.roleCode ? ROLE_NAME_MAP[state.userInfo.roleCode] || state.userInfo.roleCode : '',
  },

  actions: {
    setTokens(token: string, refreshToken: string) {
      this.token = token
      this.refreshToken = refreshToken
      storage.set(StorageKeys.TOKEN, token)
      storage.set(StorageKeys.REFRESH_TOKEN, refreshToken)
    },

    setUserInfo(info: UserInfo) {
      this.userInfo = info
      this.permissions = info.permissions ?? []
      this.menus = info.menus ?? []
      storage.setJSON(StorageKeys.USER_INFO, info)
    },

    /**
     * 校验是否拥有指定权限码（支持 "*" 全局通配及 "xxx:*" 模块通配）
     */
    hasPermission(code: string): boolean {
      if (!code) return true
      return this.permissions.some((p) => matchPermission(p, code))
    },

    /** 清除本地登录态与动态路由（不调接口） */
    clearAuth() {
      this.token = ''
      this.refreshToken = ''
      this.userInfo = null
      this.permissions = []
      this.menus = []
      storage.remove(StorageKeys.TOKEN)
      storage.remove(StorageKeys.REFRESH_TOKEN)
      storage.remove(StorageKeys.USER_INFO)
      resetDynamicRoutes()
      useTabsStore().resetTabs()
    },

    /** 登录：调 /auth/login 存 accessToken/refreshToken，再调 fetchMe() 拉取完整权限与菜单 */
    async login(params: LoginParams) {
      const res = await loginApi(params)
      this.setTokens(res.accessToken, res.refreshToken)
      await this.fetchMe()
      return res
    },

    /** 拉取当前用户信息（写 userInfo / permissions / menus） */
    async fetchMe() {
      const info = await getMe()
      this.setUserInfo(info)
      return info
    },

    /** 登出：调接口（失败也继续）→ 清本地与动态路由 → 跳登录页 */
    async logout() {
      try {
        if (this.token) await logoutApi()
      } catch {
        // 忽略网络或鉴权异常，确保本地登出必成功
      } finally {
        this.clearAuth()
        if (router.currentRoute.value.path !== '/login') {
          await router.replace('/login')
        }
      }
    },
  },
})
