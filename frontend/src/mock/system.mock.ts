/**
 * 系统管理 Mock —— 《接口契约 v1.0》3.11
 * 覆盖：用户管理 / 角色列表 / 社区管理 / 网格员列表
 */
import type { MockMethod } from 'vite-plugin-mock'
import type { Community, Guardian, RoleItem, SystemUser } from '@/types/system'
import { RoleCode } from '@/types/user'
import { COMMUNITIES, GUARDIANS, eldersStore } from './_data'
import { formatIsoOffset, getSearchParams, resultError, resultPage, resultSuccess } from './_util'

const BASE = '/api/v1'

interface MockReq {
  url: string
  body?: Record<string, unknown>
}

const usersStore: SystemUser[] = [
  {
    id: 'U001',
    username: 'admin',
    nickname: '系统管理员',
    phone: '13800138000',
    avatar: '',
    roleCode: RoleCode.ADMIN,
    communityId: 'C01',
    communityName: '幸福里社区',
    status: 1,
    lastLoginAt: '2026-11-19T17:30:00+08:00',
    createdAt: '2026-01-01T09:00:00+08:00',
  },
  {
    id: 'U002',
    username: 'cadmin01',
    nickname: '幸福里主任',
    phone: '13800138001',
    avatar: '',
    roleCode: RoleCode.COMMUNITY_ADMIN,
    communityId: 'C01',
    communityName: '幸福里社区',
    status: 1,
    lastLoginAt: '2026-11-19T16:10:00+08:00',
    createdAt: '2026-01-05T10:00:00+08:00',
  },
  {
    id: 'U003',
    username: 'guardian01',
    nickname: '李网格',
    phone: '13700002222',
    avatar: '',
    roleCode: RoleCode.GUARDIAN,
    communityId: 'C01',
    communityName: '幸福里社区',
    status: 1,
    lastLoginAt: '2026-11-19T15:45:00+08:00',
    createdAt: '2026-01-10T10:00:00+08:00',
  },
  {
    id: 'U004',
    username: 'guardian02',
    nickname: '王建国',
    phone: '13700003333',
    avatar: '',
    roleCode: RoleCode.GUARDIAN,
    communityId: 'C02',
    communityName: '康乐苑社区',
    status: 1,
    lastLoginAt: '2026-11-19T11:20:00+08:00',
    createdAt: '2026-02-01T10:00:00+08:00',
  },
  {
    id: 'U005',
    username: 'family01',
    nickname: '张女士',
    phone: '13800000001',
    avatar: '',
    roleCode: RoleCode.FAMILY,
    communityId: 'C01',
    communityName: '幸福里社区',
    status: 1,
    lastLoginAt: '2026-11-19T17:15:00+08:00',
    createdAt: '2026-03-12T10:00:00+08:00',
  },
  {
    id: 'U006',
    username: 'viewer01',
    nickname: '街道巡检员',
    phone: '13600008888',
    avatar: '',
    roleCode: RoleCode.VIEWER,
    communityId: 'C01',
    communityName: '幸福里社区',
    status: 2,
    lastLoginAt: '2026-11-10T09:00:00+08:00',
    createdAt: '2026-04-01T10:00:00+08:00',
  },
]

const rolesStore: RoleItem[] = [
  {
    id: 'R01',
    code: RoleCode.ADMIN,
    name: '超级管理员',
    permissions: ['*'],
  },
  {
    id: 'R02',
    code: RoleCode.COMMUNITY_ADMIN,
    name: '社区管理员',
    permissions: [
      'elder:read',
      'elder:write',
      'device:read',
      'device:write',
      'event:read',
      'event:write',
      'alarm:read',
      'alarm:ack',
      'alarm:dispatch',
      'dashboard:read',
    ],
  },
  {
    id: 'R03',
    code: RoleCode.GUARDIAN,
    name: '网格员',
    permissions: ['elder:read', 'event:read', 'alarm:read', 'alarm:ack', 'alarm:dispatch'],
  },
  {
    id: 'R04',
    code: RoleCode.FAMILY,
    name: '家属',
    permissions: ['family:read', 'alarm:ack'],
  },
  {
    id: 'R05',
    code: RoleCode.VIEWER,
    name: '只读用户',
    permissions: ['dashboard:read'],
  },
]

const communitiesStore: Community[] = COMMUNITIES.map((c, idx) => ({
  id: c.id,
  name: c.name,
  address: `银铃示范区幸福大道 ${(idx + 1) * 18} 号`,
  contactName: GUARDIANS.find((g) => g.communityId === c.id)?.name || '李网格',
  contactPhone: GUARDIANS.find((g) => g.communityId === c.id)?.phone || '13800138000',
  x: c.x,
  y: c.y,
  createdAt: '2026-01-01T08:00:00+08:00',
}))

function toGuardian(g: (typeof GUARDIANS)[number]): Guardian {
  return {
    id: g.id,
    userId: g.id === 'G01' ? 'U002' : `U2${g.id.slice(1)}`,
    communityId: g.communityId,
    communityName: COMMUNITIES.find((c) => c.id === g.communityId)?.name || '',
    name: g.name,
    phone: g.phone,
    elderCount: eldersStore.filter((e) => e.guardianId === g.id).length,
  }
}

export default [
  // 网格员列表
  {
    url: `${BASE}/system/guardians`,
    method: 'get',
    response: ({ url }: MockReq) => {
      const sp = getSearchParams(url)
      const communityId = sp.get('communityId') || ''
      const page = Number(sp.get('page') || 1)
      const pageSize = Number(sp.get('pageSize') || 20)
      let list = GUARDIANS.map(toGuardian)
      if (communityId) list = list.filter((g) => g.communityId === communityId)
      return resultPage(list, page, pageSize)
    },
  },

  // 用户列表
  {
    url: `${BASE}/system/users`,
    method: 'get',
    response: ({ url }: MockReq) => {
      const sp = getSearchParams(url)
      const keyword = (sp.get('keyword') || '').trim().toLowerCase()
      const roleCode = sp.get('roleCode') || ''
      const status = sp.get('status') || ''
      const page = Number(sp.get('page') || 1)
      const pageSize = Number(sp.get('pageSize') || 20)

      let list = [...usersStore]
      if (keyword) {
        list = list.filter(
          (u) =>
            u.username.toLowerCase().includes(keyword) ||
            u.nickname.toLowerCase().includes(keyword) ||
            u.phone.includes(keyword),
        )
      }
      if (roleCode) list = list.filter((u) => u.roleCode === roleCode)
      if (status) list = list.filter((u) => String(u.status) === String(status))
      return resultPage(list, page, pageSize)
    },
  },

  // 新增用户
  {
    url: `${BASE}/system/users`,
    method: 'post',
    response: ({ body }: MockReq) => {
      const commId = String(body?.communityId || 'C01')
      const comm = communitiesStore.find((c) => c.id === commId)
      const newUser: SystemUser = {
        id: `U${String(usersStore.length + 10).padStart(3, '0')}`,
        username: String(body?.username || `user${Date.now()}`),
        nickname: String(body?.nickname || '新用户'),
        phone: String(body?.phone || '13800001111'),
        avatar: '',
        roleCode: (body?.roleCode as RoleCode) || RoleCode.GUARDIAN,
        communityId: commId,
        communityName: comm?.name || '幸福里社区',
        status: 1,
        lastLoginAt: null,
        createdAt: formatIsoOffset(new Date()),
      }
      usersStore.unshift(newUser)
      return resultSuccess(newUser)
    },
  },

  // 更新用户
  {
    url: new RegExp(`^${BASE}/system/users/([^/]+)$`),
    method: 'put',
    response: ({ url, body }: MockReq) => {
      const id = url.split('/').pop() || ''
      const target = usersStore.find((u) => u.id === id)
      if (!target) return resultError(1004, '用户不存在')
      if (body?.nickname !== undefined) target.nickname = String(body.nickname)
      if (body?.phone !== undefined) target.phone = String(body.phone)
      if (body?.roleCode !== undefined) target.roleCode = body.roleCode as RoleCode
      if (body?.communityId !== undefined) {
        target.communityId = String(body.communityId)
        target.communityName =
          communitiesStore.find((c) => c.id === target.communityId)?.name || target.communityName
      }
      if (body?.status !== undefined) target.status = Number(body.status) as 1 | 2
      return resultSuccess(target)
    },
  },

  // 删除用户
  {
    url: new RegExp(`^${BASE}/system/users/([^/]+)$`),
    method: 'delete',
    response: ({ url }: MockReq) => {
      const id = url.split('/').pop() || ''
      const idx = usersStore.findIndex((u) => u.id === id)
      if (idx >= 0) usersStore.splice(idx, 1)
      return resultSuccess(null)
    },
  },

  // 角色列表
  {
    url: `${BASE}/system/roles`,
    method: 'get',
    response: () => resultSuccess({ list: rolesStore }),
  },

  // 社区列表
  {
    url: `${BASE}/system/communities`,
    method: 'get',
    response: ({ url }: MockReq) => {
      const sp = getSearchParams(url)
      const keyword = (sp.get('keyword') || '').trim().toLowerCase()
      const page = Number(sp.get('page') || 1)
      const pageSize = Number(sp.get('pageSize') || 20)
      let list = [...communitiesStore]
      if (keyword) {
        list = list.filter(
          (c) =>
            c.name.toLowerCase().includes(keyword) ||
            c.address.toLowerCase().includes(keyword) ||
            c.contactName.toLowerCase().includes(keyword),
        )
      }
      return resultPage(list, page, pageSize)
    },
  },

  // 新增社区
  {
    url: `${BASE}/system/communities`,
    method: 'post',
    response: ({ body }: MockReq) => {
      const item: Community = {
        id: `C${String(communitiesStore.length + 1).padStart(2, '0')}`,
        name: String(body?.name || '新建社区'),
        address: String(body?.address || ''),
        contactName: String(body?.contactName || ''),
        contactPhone: String(body?.contactPhone || ''),
        x: 0.5,
        y: 0.5,
        createdAt: formatIsoOffset(new Date()),
      }
      communitiesStore.push(item)
      return resultSuccess(item)
    },
  },

  // 更新社区
  {
    url: new RegExp(`^${BASE}/system/communities/([^/]+)$`),
    method: 'put',
    response: ({ url, body }: MockReq) => {
      const id = url.split('/').pop() || ''
      const target = communitiesStore.find((c) => c.id === id)
      if (!target) return resultError(1004, '社区不存在')
      if (body?.name !== undefined) target.name = String(body.name)
      if (body?.address !== undefined) target.address = String(body.address)
      if (body?.contactName !== undefined) target.contactName = String(body.contactName)
      if (body?.contactPhone !== undefined) target.contactPhone = String(body.contactPhone)
      return resultSuccess(target)
    },
  },

  // 删除社区
  {
    url: new RegExp(`^${BASE}/system/communities/([^/]+)$`),
    method: 'delete',
    response: ({ url }: MockReq) => {
      const id = url.split('/').pop() || ''
      const idx = communitiesStore.findIndex((c) => c.id === id)
      if (idx >= 0) communitiesStore.splice(idx, 1)
      return resultSuccess(null)
    },
  },
] as MockMethod[]
