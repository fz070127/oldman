/**
 * 认证接口 —— 《接口契约 v1.0》3.3
 */
import request from './request'
import type { LoginParams, LoginResult, RefreshParams, UserInfo } from '@/types/user'

/** 登录 */
export function login(data: LoginParams) {
  return request<LoginResult>({ url: '/auth/login', method: 'post', data })
}

/** 刷新 token（拦截器内部使用裸 axios 调用，此处供显式调用场景） */
export function refreshToken(data: RefreshParams) {
  return request<LoginResult>({ url: '/auth/refresh', method: 'post', data })
}

/** 登出 */
export function logout() {
  return request<null>({ url: '/auth/logout', method: 'post' })
}

/** 当前用户 + permissions + menus */
export function getMe() {
  return request<UserInfo>({ url: '/auth/me', method: 'get' })
}
