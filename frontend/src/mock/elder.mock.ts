/**
 * 老人档案 Mock —— 《接口契约 v1.0》3.4
 * 覆盖：分页筛选、详情、增删改、事件时间轴、家属绑定/解绑
 */
import type { MockMethod } from 'vite-plugin-mock'
import { ResultCode } from '@/types/common'
import {
  ElderStatus,
  type BindFamilyParams,
  type Elder,
  type ElderSaveParams,
} from '@/types/elder'
import {
  COMMUNITIES,
  GUARDIANS,
  buildElderDetail,
  devicesStore,
  eldersStore,
  eventsStore,
} from './_data'
import {
  calcAge,
  extractPathParam,
  formatIsoOffset,
  getSearchParams,
  maskPhone,
  nextId,
  resultError,
  resultPage,
  resultSuccess,
} from './_util'

const BASE = '/api/v1'

interface MockReq<B = unknown> {
  url: string
  body: B
}

function toElderListItem(r: (typeof eldersStore)[number]): Elder {
  const hasDevice = devicesStore.some((d) => d.elderId === r.id)
  return {
    id: r.id,
    name: r.name,
    gender: r.gender,
    age: calcAge(r.birthDate),
    birthDate: r.birthDate,
    phone: r.phone,
    address: r.address,
    roomNo: r.roomNo,
    communityId: r.communityId,
    communityName: r.communityName,
    guardianId: r.guardianId,
    guardianName: r.guardianName,
    healthTags: r.healthTags,
    detectMode: r.detectMode,
    status: r.status,
    deviceOnline: r.deviceOnline,
    hasDevice,
    lastAlarmAt: r.lastAlarmAt,
    alarmCount30d: r.alarmCount30d,
    createdAt: r.createdAt,
  }
}

export default [
  // 老人分页列表
  {
    url: `${BASE}/elders`,
    method: 'get',
    response: ({ url }: MockReq) => {
      const sp = getSearchParams(url)
      const keyword = (sp.get('keyword') || '').trim().toLowerCase()
      const communityId = sp.get('communityId') || ''
      const statusStr = sp.get('status') || ''
      const guardianId = sp.get('guardianId') || ''
      const onlineStr = sp.get('deviceOnline') ?? sp.get('online') ?? ''
      const page = Number(sp.get('page') || 1)
      const pageSize = Number(sp.get('pageSize') || 20)

      let list = eldersStore.filter((e) => e.status !== ElderStatus.DECEASED)

      if (keyword) {
        list = list.filter(
          (e) =>
            e.name.toLowerCase().includes(keyword) ||
            e.roomNo.toLowerCase().includes(keyword) ||
            e.address.toLowerCase().includes(keyword),
        )
      }
      if (communityId) {
        list = list.filter((e) => e.communityId === communityId)
      }
      if (statusStr !== '') {
        const st = Number(statusStr)
        list = list.filter((e) => e.status === st)
      }
      if (guardianId) {
        list = list.filter((e) => e.guardianId === guardianId)
      }
      if (onlineStr === 'true' || onlineStr === 'false') {
        const wantOnline = onlineStr === 'true'
        list = list.filter((e) => e.deviceOnline === wantOnline)
      }

      return resultPage(list.map(toElderListItem), page, pageSize)
    },
  },

  // 近 30 天事件时间轴
  {
    url: `${BASE}/elders/:id/timeline`,
    method: 'get',
    response: ({ url }: MockReq) => {
      const id = extractPathParam(url, /\/elders\/([^/]+)\/timeline/)
      const elder = eldersStore.find((e) => e.id === id)
      if (!elder) return resultError(ResultCode.NOT_FOUND, '老人档案不存在')

      const list = eventsStore
        .filter((ev) => ev.elderId === id)
        .map(({ features: _f, algoVersion: _a, ...item }) => item)
      return resultSuccess({ list })
    },
  },

  // 获取老人绑定家属列表（F4 补充）
  {
    url: `${BASE}/elders/:id/bindings`,
    method: 'get',
    response: ({ url }: MockReq) => {
      const id = extractPathParam(url, /\/elders\/([^/]+)\/bindings/)
      const elder = eldersStore.find((e) => e.id === id)
      if (!elder) return resultError(ResultCode.NOT_FOUND, '老人档案不存在')
      return resultSuccess({ list: elder.families })
    },
  },

  // 绑定家属（同时兼容 /families 与 /bindings）
  {
    url: `${BASE}/elders/:id/families`,
    method: 'post',
    response: ({ url, body }: MockReq<BindFamilyParams>) => {
      const id = extractPathParam(url, /\/elders\/([^/]+)\/families/)
      const elder = eldersStore.find((e) => e.id === id)
      if (!elder) return resultError(ResultCode.NOT_FOUND, '老人档案不存在')
      if (!body?.name || !body?.phone) {
        return resultError(ResultCode.PARAM_ERROR, '家属姓名和手机号不能为空')
      }

      const binding = {
        bindingId: `B${Date.now().toString().slice(-6)}`,
        userId: body.userId || `U${Date.now().toString().slice(-4)}`,
        name: body.name,
        phone: maskPhone(body.phone),
        relation: body.relation || '子女',
        isPrimary: !!body.isPrimary,
        notifyOrder: body.notifyOrder || elder.families.length + 1,
      }
      if (binding.isPrimary) {
        elder.families.forEach((f) => {
          f.isPrimary = false
        })
      }
      elder.families.push(binding)
      return resultSuccess(binding)
    },
  },
  {
    url: `${BASE}/elders/:id/bindings`,
    method: 'post',
    response: ({ url, body }: MockReq<BindFamilyParams>) => {
      const id = extractPathParam(url, /\/elders\/([^/]+)\/bindings/)
      const elder = eldersStore.find((e) => e.id === id)
      if (!elder) return resultError(ResultCode.NOT_FOUND, '老人档案不存在')
      if (!body?.name || !body?.phone) {
        return resultError(ResultCode.PARAM_ERROR, '家属姓名和手机号不能为空')
      }

      const binding = {
        bindingId: `B${Date.now().toString().slice(-6)}`,
        userId: body.userId || `U${Date.now().toString().slice(-4)}`,
        name: body.name,
        phone: maskPhone(body.phone),
        relation: body.relation || '子女',
        isPrimary: !!body.isPrimary,
        notifyOrder: body.notifyOrder || elder.families.length + 1,
      }
      if (binding.isPrimary) {
        elder.families.forEach((f) => {
          f.isPrimary = false
        })
      }
      elder.families.push(binding)
      return resultSuccess(binding)
    },
  },

  // 解绑家属（同时兼容 /families/:bindingId 与 /bindings/:bindingId）
  {
    url: `${BASE}/elders/:id/families/:bindingId`,
    method: 'delete',
    response: ({ url }: MockReq) => {
      const pathname = url.split('?')[0]
      const matched = pathname.match(/\/elders\/([^/]+)\/families\/([^/]+)/)
      if (!matched) return resultError(ResultCode.PARAM_ERROR, '参数错误')
      const [, id, bindingId] = matched
      const elder = eldersStore.find((e) => e.id === id)
      if (!elder) return resultError(ResultCode.NOT_FOUND, '老人档案不存在')

      const idx = elder.families.findIndex((f) => f.bindingId === bindingId)
      if (idx < 0) return resultError(ResultCode.NOT_FOUND, '绑定关系不存在')
      elder.families.splice(idx, 1)
      return resultSuccess(null)
    },
  },
  {
    url: `${BASE}/elders/:id/bindings/:bindingId`,
    method: 'delete',
    response: ({ url }: MockReq) => {
      const pathname = url.split('?')[0]
      const matched = pathname.match(/\/elders\/([^/]+)\/bindings\/([^/]+)/)
      if (!matched) return resultError(ResultCode.PARAM_ERROR, '参数错误')
      const [, id, bindingId] = matched
      const elder = eldersStore.find((e) => e.id === id)
      if (!elder) return resultError(ResultCode.NOT_FOUND, '老人档案不存在')

      const idx = elder.families.findIndex((f) => f.bindingId === bindingId)
      if (idx < 0) return resultError(ResultCode.NOT_FOUND, '绑定关系不存在')
      elder.families.splice(idx, 1)
      return resultSuccess(null)
    },
  },

  // 老人详情
  {
    url: `${BASE}/elders/:id`,
    method: 'get',
    response: ({ url }: MockReq) => {
      const id = extractPathParam(url, /\/elders\/([^/]+)$/)
      const elder = eldersStore.find((e) => e.id === id)
      if (!elder) return resultError(ResultCode.NOT_FOUND, '老人档案不存在')
      return resultSuccess(buildElderDetail(elder))
    },
  },

  // 新建老人
  {
    url: `${BASE}/elders`,
    method: 'post',
    response: ({ body }: MockReq<ElderSaveParams>) => {
      if (!body?.name || !body?.birthDate) {
        return resultError(ResultCode.PARAM_ERROR, '姓名和出生日期不能为空')
      }
      const community = COMMUNITIES.find((c) => c.id === body.communityId) || COMMUNITIES[0]
      const guardian = GUARDIANS.find((g) => g.id === body.guardianId) || GUARDIANS[0]
      // 逻辑删除会让列表长度不变，不能用 length+1（会撞已存在的 id）
      const id = nextId('E', eldersStore)
      const rawPhone = body.phone || '13800000000'

      const created = {
        id,
        name: body.name,
        gender: body.gender,
        age: calcAge(body.birthDate),
        birthDate: body.birthDate,
        phone: maskPhone(rawPhone),
        rawPhone,
        address: body.address,
        roomNo: body.roomNo,
        communityId: community.id,
        communityName: community.name,
        guardianId: guardian.id,
        guardianName: guardian.name,
        healthTags: body.healthTags || [],
        detectMode: body.detectMode,
        status: body.status ?? ElderStatus.ACTIVE,
        deviceOnline: false,
        lastAlarmAt: null,
        alarmCount30d: 0,
        createdAt: formatIsoOffset(new Date()),
        emergencyContact: body.emergencyContact || [],
        families: [],
      }
      eldersStore.unshift(created)
      return resultSuccess(toElderListItem(created))
    },
  },

  // 更新老人
  {
    url: `${BASE}/elders/:id`,
    method: 'put',
    response: ({ url, body }: MockReq<Partial<ElderSaveParams>>) => {
      const id = extractPathParam(url, /\/elders\/([^/]+)$/)
      const elder = eldersStore.find((e) => e.id === id)
      if (!elder) return resultError(ResultCode.NOT_FOUND, '老人档案不存在')

      if (body.name !== undefined) elder.name = body.name
      if (body.gender !== undefined) elder.gender = body.gender
      if (body.birthDate !== undefined) {
        elder.birthDate = body.birthDate
        elder.age = calcAge(body.birthDate)
      }
      if (body.phone !== undefined) {
        elder.rawPhone = body.phone
        elder.phone = maskPhone(body.phone)
      }
      if (body.communityId !== undefined) {
        const comm = COMMUNITIES.find((c) => c.id === body.communityId)
        if (comm) {
          elder.communityId = comm.id
          elder.communityName = comm.name
        }
      }
      if (body.guardianId !== undefined) {
        const g = GUARDIANS.find((item) => item.id === body.guardianId)
        if (g) {
          elder.guardianId = g.id
          elder.guardianName = g.name
        }
      }
      if (body.address !== undefined) elder.address = body.address
      if (body.roomNo !== undefined) elder.roomNo = body.roomNo
      if (body.healthTags !== undefined) elder.healthTags = body.healthTags
      if (body.detectMode !== undefined) elder.detectMode = body.detectMode
      if (body.status !== undefined) elder.status = body.status
      if (body.emergencyContact !== undefined) elder.emergencyContact = body.emergencyContact

      return resultSuccess(toElderListItem(elder))
    },
  },

  // 软删除/停用老人（status=2 暂停）
  {
    url: `${BASE}/elders/:id`,
    method: 'delete',
    response: ({ url }: MockReq) => {
      const id = extractPathParam(url, /\/elders\/([^/]+)$/)
      const elder = eldersStore.find((e) => e.id === id)
      if (!elder) return resultError(ResultCode.NOT_FOUND, '老人档案不存在')
      elder.status = ElderStatus.PAUSED
      return resultSuccess(null)
    },
  },
] as MockMethod[]
