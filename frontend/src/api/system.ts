/**
 * 系统管理 API —— 《接口契约 v1.0》3.11
 */
import request from './request'
import type { PageQuery, PageResult } from '@/types/common'
import type { Community, Guardian, RoleItem, SystemUser } from '@/types/system'

/** 网格员列表 */
export function getGuardianList(params: Partial<PageQuery> & { communityId?: string } = {}) {
  return request<PageResult<Guardian>>({ url: '/system/guardians', method: 'get', params })
}

/** 系统用户列表 */
export function getSystemUsers(
  params: Partial<PageQuery> & { keyword?: string; roleCode?: string; status?: number | '' } = {},
) {
  return request<PageResult<SystemUser>>({ url: '/system/users', method: 'get', params })
}

/** 新增系统用户 */
export function createSystemUser(data: Partial<SystemUser>) {
  return request<SystemUser>({ url: '/system/users', method: 'post', data })
}

/** 更新系统用户（含启停状态） */
export function updateSystemUser(id: string, data: Partial<SystemUser>) {
  return request<SystemUser>({ url: `/system/users/${id}`, method: 'put', data })
}

/** 删除系统用户 */
export function deleteSystemUser(id: string) {
  return request<null>({ url: `/system/users/${id}`, method: 'delete' })
}

/** 角色列表（只读） */
export function getSystemRoles() {
  return request<{ list: RoleItem[] }>({ url: '/system/roles', method: 'get' })
}

/** 社区列表 */
export function getSystemCommunities(params: Partial<PageQuery> & { keyword?: string } = {}) {
  return request<PageResult<Community>>({ url: '/system/communities', method: 'get', params })
}

/** 新增社区 */
export function createSystemCommunity(data: Partial<Community>) {
  return request<Community>({ url: '/system/communities', method: 'post', data })
}

/** 更新社区 */
export function updateSystemCommunity(id: string, data: Partial<Community>) {
  return request<Community>({ url: `/system/communities/${id}`, method: 'put', data })
}

/** 删除社区 */
export function deleteSystemCommunity(id: string) {
  return request<null>({ url: `/system/communities/${id}`, method: 'delete' })
}
