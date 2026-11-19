/**
 * 系统管理 Mock —— 《接口契约 v1.0》3.11（F6 先补网格员列表，供告警派单使用）
 */
import type { MockMethod } from 'vite-plugin-mock'
import type { Guardian } from '@/types/system'
import { COMMUNITIES, GUARDIANS, eldersStore } from './_data'
import { getSearchParams, resultPage } from './_util'

const BASE = '/api/v1'

interface MockReq {
  url: string
}

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
] as MockMethod[]
