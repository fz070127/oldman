/**
 * 认证与权限 Mock —— 《接口契约 v1.0》3.3
 * 覆盖：login / refresh / logout / me / password，以及 5 类角色完整权限矩阵
 */
import type { MockMethod } from 'vite-plugin-mock'
import { RoleCode, type UserInfo } from '@/types/user'
import { getRequestToken, resultError, resultSuccess } from './_util'

const BASE = '/api/v1'
const DEFAULT_PASSWORD = '123456'

/** 契约 3.3 角色权限与菜单矩阵 */
const ROLE_MATRIX: Record<RoleCode, { permissions: string[]; menus: string[] }> = {
  [RoleCode.ADMIN]: {
    permissions: ['*'],
    menus: ['dashboard', 'elder', 'device', 'event', 'alarm', 'screen', 'system'],
  },
  [RoleCode.COMMUNITY_ADMIN]: {
    permissions: ['elder:read', 'elder:write', 'device:*', 'event:*', 'alarm:*', 'dashboard:*'],
    menus: ['dashboard', 'elder', 'device', 'event', 'alarm', 'screen'],
  },
  [RoleCode.GUARDIAN]: {
    permissions: ['elder:read', 'event:read', 'alarm:read', 'alarm:ack', 'alarm:dispatch'],
    menus: ['dashboard', 'elder', 'alarm', 'event'],
  },
  [RoleCode.FAMILY]: {
    permissions: ['family:read', 'alarm:ack'],
    menus: ['family'],
  },
  [RoleCode.VIEWER]: {
    permissions: ['dashboard:read'],
    menus: ['dashboard', 'screen'],
  },
}

interface MockAccount {
  id: string
  username: string
  nickname: string
  roleCode: RoleCode
  avatar: string
  communityId: string
  password?: string
}

const GLOBAL_AUTH_KEY = '__SILVER_BELL_MOCK_AUTH__'

function initAccounts(): Record<string, MockAccount> {
  const g = globalThis as unknown as Record<string, Record<string, MockAccount> | undefined>
  if (g[GLOBAL_AUTH_KEY]) return g[GLOBAL_AUTH_KEY] as Record<string, MockAccount>

  const accounts: Record<string, MockAccount> = {
    admin: {
      id: 'U001',
      username: 'admin',
      nickname: '系统管理员',
      roleCode: RoleCode.ADMIN,
      avatar: '',
      communityId: 'C01',
    },
    community01: {
      id: 'U003',
      username: 'community01',
      nickname: '王主任',
      roleCode: RoleCode.COMMUNITY_ADMIN,
      avatar: '',
      communityId: 'C01',
    },
    guardian01: {
      id: 'U002',
      username: 'guardian01',
      nickname: '李网格',
      roleCode: RoleCode.GUARDIAN,
      avatar: '',
      communityId: 'C01',
    },
    family01: {
      id: 'U010',
      username: 'family01',
      nickname: '张女士',
      roleCode: RoleCode.FAMILY,
      avatar: '',
      communityId: 'C01',
    },
    viewer01: {
      id: 'U020',
      username: 'viewer01',
      nickname: '值班观察员',
      roleCode: RoleCode.VIEWER,
      avatar: '',
      communityId: 'C01',
    },
  }
  g[GLOBAL_AUTH_KEY] = accounts
  return accounts
}

const accounts = initAccounts()

/** 按账号组装完整 UserInfo（permissions / menus 从契约矩阵动态按 roleCode 读取） */
function toUserInfo(acc: MockAccount): UserInfo {
  const matrix = ROLE_MATRIX[acc.roleCode]
  return {
    id: acc.id,
    username: acc.username,
    nickname: acc.nickname,
    roleCode: acc.roleCode,
    avatar: acc.avatar,
    communityId: acc.communityId,
    permissions: [...matrix.permissions],
    menus: [...matrix.menus],
  }
}

/** token 格式：mock-token-{username}；refreshToken 格式：mock-refresh-{username} */
function accountFromToken(token: string | null, prefix: string): MockAccount | null {
  if (!token || !token.startsWith(prefix)) return null
  const name = token.slice(prefix.length)
  return accounts[name] ?? null
}

function issue(acc: MockAccount) {
  return {
    accessToken: `mock-token-${acc.username}`,
    refreshToken: `mock-refresh-${acc.username}`,
    expiresIn: 1800,
    user: toUserInfo(acc),
  }
}

export default [
  {
    url: `${BASE}/auth/login`,
    method: 'post',
    timeout: 200,
    response: ({ body }: { body: { username?: string; password?: string } }) => {
      const { username, password } = body || {}
      if (!username || !password) return resultError(1001, '用户名和密码不能为空')
      const acc = accounts[username]
      const expectedPwd = acc?.password ?? DEFAULT_PASSWORD
      if (!acc || password !== expectedPwd) return resultError(1001, '用户名或密码错误')
      return resultSuccess(issue(acc))
    },
  },
  {
    url: `${BASE}/auth/refresh`,
    method: 'post',
    response: ({ body }: { body: { refreshToken?: string } }) => {
      const acc = accountFromToken(body?.refreshToken ?? null, 'mock-refresh-')
      if (!acc) return resultError(1002, 'refreshToken 无效或已过期')
      return resultSuccess(issue(acc))
    },
  },
  {
    url: `${BASE}/auth/logout`,
    method: 'post',
    response: () => resultSuccess(null),
  },
  {
    url: `${BASE}/auth/me`,
    method: 'get',
    response: ({ headers }: { headers: Record<string, string> }) => {
      const acc = accountFromToken(getRequestToken(headers), 'mock-token-')
      if (!acc) return resultError(1002, '未登录或 token 已失效')
      return resultSuccess(toUserInfo(acc))
    },
  },
  {
    url: `${BASE}/auth/password`,
    method: 'put',
    response: ({
      headers,
      body,
    }: {
      headers: Record<string, string>
      body: { oldPassword?: string; newPassword?: string }
    }) => {
      const acc = accountFromToken(getRequestToken(headers), 'mock-token-')
      if (!acc) return resultError(1002, '未登录或 token 已失效')
      const { oldPassword, newPassword } = body || {}
      if (!oldPassword || !newPassword) return resultError(1001, '原密码和新密码不能为空')
      if (newPassword.length < 6) return resultError(1001, '新密码长度不能少于 6 位')
      const currentPwd = acc.password ?? DEFAULT_PASSWORD
      if (oldPassword !== currentPwd) return resultError(1001, '原密码不正确')
      acc.password = newPassword
      return resultSuccess(null)
    },
  },
] as MockMethod[]
