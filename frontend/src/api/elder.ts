/**
 * 老人档案 API —— 《接口契约 v1.0》3.4
 */
import request from './request'
import type { PageResult } from '@/types/common'
import type {
  BindFamilyParams,
  Elder,
  ElderDetail,
  ElderQuery,
  ElderSaveParams,
  FamilyBinding,
} from '@/types/elder'
import type { EventItem } from '@/types/event'

/** 分页获取老人列表 */
export function getElderList(params: ElderQuery) {
  return request<PageResult<Elder>>({ url: '/elders', method: 'get', params })
}

/** 获取老人详情（含设备、家属、最近 5 条事件） */
export function getElderDetail(id: string) {
  return request<ElderDetail>({ url: `/elders/${id}`, method: 'get' })
}

/** 新建老人 */
export function createElder(data: ElderSaveParams) {
  return request<Elder>({ url: '/elders', method: 'post', data })
}

/** 更新老人 */
export function updateElder(id: string, data: Partial<ElderSaveParams>) {
  return request<Elder>({ url: `/elders/${id}`, method: 'put', data })
}

/** 停用/逻辑删除老人 */
export function deleteElder(id: string) {
  return request<null>({ url: `/elders/${id}`, method: 'delete' })
}

/** 获取老人近 30 天事件时间轴 */
export function getElderTimeline(id: string) {
  return request<{ list: EventItem[] }>({ url: `/elders/${id}/timeline`, method: 'get' })
}

/** 获取老人绑定家属列表 */
export function getElderBindings(id: string) {
  return request<{ list: FamilyBinding[] }>({ url: `/elders/${id}/bindings`, method: 'get' })
}

/** 绑定家属 */
export function bindElderFamily(id: string, data: BindFamilyParams) {
  return request<FamilyBinding>({ url: `/elders/${id}/families`, method: 'post', data })
}

/** 解绑家属 */
export function unbindElderFamily(id: string, bindingId: string) {
  return request<null>({ url: `/elders/${id}/families/${bindingId}`, method: 'delete' })
}
