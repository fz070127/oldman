import { defineStore } from 'pinia'
import { login as loginApi, logout as logoutApi, getMe } from '@/api/auth'
import { storage, StorageKeys } from '@/utils/storage'
import type { LoginParams, UserInfo } from '@/types/user'

interface UserState {
  token: string
  refreshToken: string
  userInfo: UserInfo | null
  permissions: string[]
  menus: string[]
}

export const useUserStore = defineStore('user', {
  state: (): UserState => {
    const userInfo = storage.getJSON<UserInfo>(StorageKeys.USER_INFO)
    return {
      // token 直接存原始字符串，便于调试时手动写入
      token: storage.get(StorageKeys.TOKEN) || '',
      refreshToken: storage.get(StorageKeys.REFRESH_TOKEN) || '',
      userInfo,
      permissions: userInfo?.permissions ?? [],
      menus: userInfo?.menus ?? [],
    }
  },

  getters: {
    isLoggedIn: (state) => !!state.token,
    displayName: (state) => state.userInfo?.nickname || state.userInfo?.username || '未命名用户',
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

    /** 清除本地登录态（不调接口） */
    clearAuth() {
      this.token = ''
      this.refreshToken = ''
      this.userInfo = null
      this.permissions = []
      this.menus = []
      storage.remove(StorageKeys.TOKEN)
      storage.remove(StorageKeys.REFRESH_TOKEN)
      storage.remove(StorageKeys.USER_INFO)
    },

    /** 登录：存 token 与用户信息 */
    async login(params: LoginParams) {
      const res = await loginApi(params)
      this.setTokens(res.accessToken, res.refreshToken)
      this.setUserInfo(res.user)
      return res
    },

    /** 拉取当前用户信息 */
    async fetchMe() {
      const info = await getMe()
      this.setUserInfo(info)
      return info
    },

    /** 登出：调接口（失败也继续）→ 清本地 */
    async logout() {
      try {
        if (this.token) await logoutApi()
      } finally {
        this.clearAuth()
      }
    },
  },
})
