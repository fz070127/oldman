/**
 * 认证 Mock（F1 最小可用版：login / refresh / logout / me）
 * 账号与权限矩阵见《接口契约 v1.0》3.3；F2 阶段再扩充全量 mock
 */
import type { MockMethod } from 'vite-plugin-mock'
import { getRequestToken, resultError, resultSuccess } from './_util'

const BASE = '/api/v1'
const PASSWORD = '123456'

const users = {
  admin: {
    id: 'U001',
    username: 'admin',
    nickname: '系统管理员',
    roleCode: 'ADMIN',
    avatar: '',
    communityId: 'C01',
    permissions: ['*'],
    menus: ['dashboard', 'elder', 'device', 'event', 'alarm', 'screen', 'system'],
  },
  guardian01: {
    id: 'U002',
    username: 'guardian01',
    nickname: '李网格',
    roleCode: 'GUARDIAN',
    avatar: '',
    communityId: 'C01',
    permissions: ['elder:read', 'event:read', 'alarm:read', 'alarm:ack', 'alarm:dispatch'],
    menus: ['dashboard', 'elder', 'alarm', 'event'],
  },
  family01: {
    id: 'U010',
    username: 'family01',
    nickname: '张女士',
    roleCode: 'FAMILY',
    avatar: '',
    communityId: 'C01',
    permissions: ['family:read', 'alarm:ack'],
    menus: ['family'],
  },
} as const

type Username = keyof typeof users

/** token 格式：mock-token-{username}；refreshToken 格式：mock-refresh-{username} */
function userFromToken(token: string | null, prefix: string) {
  if (!token || !token.startsWith(prefix)) return null
  const name = token.slice(prefix.length) as Username
  return users[name] ?? null
}

function issue(username: Username) {
  return {
    accessToken: `mock-token-${username}`,
    refreshToken: `mock-refresh-${username}`,
    expiresIn: 1800,
    user: users[username],
  }
}

export default [
  {
    url: `${BASE}/auth/login`,
    method: 'post',
    timeout: 300,
    response: ({ body }: { body: { username?: string; password?: string } }) => {
      const { username, password } = body || {}
      if (!username || !password) return resultError(1001, '用户名和密码不能为空')
      if (!(username in users) || password !== PASSWORD) return resultError(1001, '用户名或密码错误')
      return resultSuccess(issue(username as Username))
    },
  },
  {
    url: `${BASE}/auth/refresh`,
    method: 'post',
    response: ({ body }: { body: { refreshToken?: string } }) => {
      const user = userFromToken(body?.refreshToken ?? null, 'mock-refresh-')
      if (!user) return resultError(1002, 'refreshToken 无效或已过期')
      return resultSuccess(issue(user.username))
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
      const user = userFromToken(getRequestToken(headers), 'mock-token-')
      if (!user) return resultError(1002, '未登录或 token 已失效')
      return resultSuccess(user)
    },
  },
] as MockMethod[]
