/**
 * 认证与用户类型 —— 与《接口契约 v1.0》3.3 节保持一致
 */

/** 角色编码枚举（常量 + 联合类型） */
export const RoleCode = {
  ADMIN: 'ADMIN',
  COMMUNITY_ADMIN: 'COMMUNITY_ADMIN',
  GUARDIAN: 'GUARDIAN',
  FAMILY: 'FAMILY',
  VIEWER: 'VIEWER',
} as const
export type RoleCode = (typeof RoleCode)[keyof typeof RoleCode]

/** 角色中文名映射 */
export const ROLE_NAME_MAP: Record<RoleCode, string> = {
  ADMIN: '超级管理员',
  COMMUNITY_ADMIN: '社区管理员',
  GUARDIAN: '网格员',
  FAMILY: '家属',
  VIEWER: '只读用户',
}

/** 当前用户（POST /auth/login 的 data.user，GET /auth/me 的 data） */
export interface UserInfo {
  id: string
  username: string
  nickname: string
  roleCode: RoleCode
  avatar: string
  communityId: string
  permissions: string[]
  menus: string[]
}

/** POST /auth/login 请求 */
export interface LoginParams {
  username: string
  password: string
}

/** POST /auth/login 响应 data */
export interface LoginResult {
  accessToken: string
  refreshToken: string
  expiresIn: number
  user: UserInfo
}

/** POST /auth/refresh 请求 */
export interface RefreshParams {
  refreshToken: string
}

/** PUT /auth/password 请求（契约 3.3） */
export interface UpdatePasswordParams {
  oldPassword: string
  newPassword: string
}
