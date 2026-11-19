import {
  mockGetCurrentUser,
  mockIsLoggedIn,
  mockLogin,
  mockLogout,
} from '@/mock'
import type { FamilyLoginParams, LoginResult, UserInfo } from '@/types'

function delay(ms = 120): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

/** 家属端登录（POST /api/v1/auth/login） */
export async function loginByPhone(params: FamilyLoginParams): Promise<LoginResult> {
  await delay(120)
  const res = mockLogin(params)
  if (res.code !== 0) {
    throw new Error(res.message || '登录失败')
  }
  return res.data
}

/** 获取当前登录家属信息（GET /api/v1/auth/me） */
export async function getCurrentUser(): Promise<UserInfo> {
  await delay(60)
  return mockGetCurrentUser()
}

/** 判断是否已登录 */
export function isLoggedIn(): boolean {
  return mockIsLoggedIn()
}

/** 退出登录（POST /api/v1/auth/logout） */
export async function logout(): Promise<void> {
  await delay(80)
  mockLogout()
}
