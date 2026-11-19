/**
 * 系统管理 API —— 《接口契约 v1.0》3.11
 */
import request from './request'
import type { PageQuery, PageResult } from '@/types/common'
import type { Guardian } from '@/types/system'

/** 网格员列表 */
export function getGuardianList(params: Partial<PageQuery> & { communityId?: string } = {}) {
  return request<PageResult<Guardian>>({ url: '/system/guardians', method: 'get', params })
}
