import type {
  AlarmAckParams,
  AlarmDetail,
  AlarmDispatchParams,
  AlarmItem,
  ApiResponse,
  FamilyElderItem,
  FamilyLoginParams,
  FamilyNotificationSettings,
  LoginResult,
  PageResult,
  UserInfo,
} from '@/types'

const STORAGE_KEYS = {
  TOKEN: 'sb_h5_access_token',
  USER: 'sb_h5_user_info',
  ALARMS: 'sb_h5_mock_alarms_v1',
  ELDERS: 'sb_h5_mock_elders_v1',
  NOTIFY_SETTINGS: 'sb_h5_notify_settings_v1',
}

/** 固定演示账号与验证码 */
export const MOCK_ACCOUNT = {
  PHONE: '13800000001',
  CODE: '123456',
}

/** 默认登录家属用户信息（与《接口契约 v1.0》3.3 完全一致） */
const DEFAULT_USER: UserInfo = {
  id: 'U010',
  username: '13800000001',
  nickname: '张女士',
  phone: '13800000001',
  roleCode: 'FAMILY',
  avatar: '/static/avatar-family.png',
  communityId: 'C01',
  communityName: '幸福里社区',
  permissions: ['family:read', 'alarm:ack'],
  menus: ['family'],
}

/** 初始 2 位绑定老人（与《接口契约 v1.0》3.8 完全一致） */
const INITIAL_ELDERS: FamilyElderItem[] = [
  {
    id: 'E001',
    name: '王秀兰',
    age: 78,
    roomNo: '302室',
    address: '幸福里社区 3 栋 302 室',
    communityName: '幸福里社区',
    avatar: '/static/avatar-elder-1.png',
    online: true,
    relation: '母亲',
    todayAlarmCount: 1,
    statusText: '有 1 条告警',
    lastActiveAt: '2026-11-19T16:42:15+08:00',
    healthTags: ['独居', '高血压'],
    latestAlarmId: 'A001',
  },
  {
    id: 'E002',
    name: '张建国',
    age: 81,
    roomNo: '104室',
    address: '幸福里社区 5 栋 104 室',
    communityName: '幸福里社区',
    avatar: '/static/avatar-elder-2.png',
    online: false,
    relation: '父亲',
    todayAlarmCount: 0,
    statusText: '一切正常',
    lastActiveAt: '2026-11-19T15:20:00+08:00',
    healthTags: ['空巢', '糖尿病'],
    latestAlarmId: 'A002',
  },
]

/** 初始 5 条告警详情数据（时间倒序，与《接口契约 v1.0》3.7 完全一致） */
const INITIAL_ALARM_DETAILS: AlarmDetail[] = [
  {
    id: 'A001',
    level: 'P0',
    status: 'PENDING',
    escalateStep: 0,
    currentHandler: '张女士（家属）',
    elder: {
      id: 'E001',
      name: '王秀兰',
      age: 78,
      roomNo: '302室',
      address: '幸福里社区 3 栋 302 室',
      phone: '138****8888',
      healthTags: ['独居', '高血压'],
      primaryContact: {
        name: '张女士',
        phone: '13800000001',
        relation: '子女',
      },
    },
    event: {
      id: 'EV001',
      type: 'FALL',
      confidence: 0.94,
      occurredAt: '2026-11-19T16:42:15+08:00',
      features: {
        torsoAngle: 16.4,
        heightDrop: 0.64,
        stillDurationSec: 15,
        trackId: 1,
        aspectRatio: 2.25,
        kpConf: 0.91,
      },
      snapshotUrl: '/static/fall-snapshot.png',
      clipUrl: null,
      algoVersion: 'fall-v1.2.0',
    },
    notifiedAt: '2026-11-19T16:42:17+08:00',
    ackAt: null,
    resolvedAt: null,
    responseSec: null,
    actions: [
      {
        id: 101,
        action: 'NOTIFY',
        actor: 'SYSTEM',
        actorName: '系统自动推送',
        channel: 'PUSH',
        result: 'DELIVERED',
        createdAt: '2026-11-19T16:42:17+08:00',
      },
    ],
    timeline: [
      {
        ts: '2026-11-19T16:42:15+08:00',
        text: '客厅边缘设备检测到老人跌倒（置信度 94%，静止 15 秒）',
      },
      {
        ts: '2026-11-19T16:42:17+08:00',
        text: '已向紧急联系人张女士（家属）发送推送与短信告警',
      },
    ],
    remainingSec: 58,
  },
  {
    id: 'A002',
    level: 'P1',
    status: 'COMMUNITY_DISPATCHED',
    escalateStep: 1,
    currentHandler: '李网格（幸福里社区）',
    elder: {
      id: 'E002',
      name: '张建国',
      age: 81,
      roomNo: '104室',
      address: '幸福里社区 5 栋 104 室',
      phone: '139****6622',
      healthTags: ['空巢', '糖尿病'],
      primaryContact: {
        name: '张女士',
        phone: '13800000001',
        relation: '子女',
      },
    },
    event: {
      id: 'EV002',
      type: 'LONG_LIE',
      confidence: 0.89,
      occurredAt: '2026-11-18T21:15:30+08:00',
      features: {
        torsoAngle: 19.2,
        heightDrop: 0.52,
        stillDurationSec: 42,
        trackId: 2,
        aspectRatio: 1.95,
        kpConf: 0.87,
      },
      snapshotUrl: '/static/fall-snapshot.png',
      clipUrl: null,
      algoVersion: 'fall-v1.2.0',
    },
    notifiedAt: '2026-11-18T21:15:32+08:00',
    ackAt: '2026-11-18T21:16:10+08:00',
    resolvedAt: null,
    responseSec: 38,
    actions: [
      {
        id: 201,
        action: 'NOTIFY',
        actor: 'SYSTEM',
        actorName: '系统',
        channel: 'PUSH',
        result: 'DELIVERED',
        createdAt: '2026-11-18T21:15:32+08:00',
      },
      {
        id: 202,
        action: 'DISPATCH',
        actor: 'U010',
        actorName: '张女士',
        channel: 'SMS',
        result: 'SENT',
        detail: { guardianId: 'G01', guardianName: '李网格' },
        createdAt: '2026-11-18T21:16:10+08:00',
      },
    ],
    timeline: [
      {
        ts: '2026-11-18T21:15:30+08:00',
        text: '卧室边缘设备检测到久躺未动异常（置信度 89%）',
      },
      {
        ts: '2026-11-18T21:15:32+08:00',
        text: '已推送家属（张女士）',
      },
      {
        ts: '2026-11-18T21:16:10+08:00',
        text: '家属求助社区，已指派责任网格员（李网格）前往核实',
      },
    ],
    remainingSec: null,
  },
  {
    id: 'A003',
    level: 'P0',
    status: 'ACKNOWLEDGED',
    escalateStep: 0,
    currentHandler: '张女士（家属）',
    elder: {
      id: 'E001',
      name: '王秀兰',
      age: 78,
      roomNo: '302室',
      address: '幸福里社区 3 栋 302 室',
      phone: '138****8888',
      healthTags: ['独居', '高血压'],
      primaryContact: {
        name: '张女士',
        phone: '13800000001',
        relation: '子女',
      },
    },
    event: {
      id: 'EV003',
      type: 'FALL',
      confidence: 0.92,
      occurredAt: '2026-11-17T14:08:22+08:00',
      features: {
        torsoAngle: 18.0,
        heightDrop: 0.59,
        stillDurationSec: 11,
        trackId: 4,
        aspectRatio: 2.08,
        kpConf: 0.89,
      },
      snapshotUrl: '/static/fall-snapshot.png',
      clipUrl: null,
      algoVersion: 'fall-v1.2.0',
    },
    notifiedAt: '2026-11-17T14:08:24+08:00',
    ackAt: '2026-11-17T14:08:50+08:00',
    resolvedAt: null,
    responseSec: 26,
    actions: [
      {
        id: 301,
        action: 'NOTIFY',
        actor: 'SYSTEM',
        actorName: '系统',
        channel: 'PUSH',
        result: 'DELIVERED',
        createdAt: '2026-11-17T14:08:24+08:00',
      },
      {
        id: 302,
        action: 'ACK',
        actor: 'U010',
        actorName: '张女士',
        createdAt: '2026-11-17T14:08:50+08:00',
      },
    ],
    timeline: [
      {
        ts: '2026-11-17T14:08:22+08:00',
        text: '检测到跌倒（置信度 92%）',
      },
      {
        ts: '2026-11-17T14:08:24+08:00',
        text: '已推送家属（张女士）',
      },
      {
        ts: '2026-11-17T14:08:50+08:00',
        text: '家属（张女士）已确认：我马上过去',
      },
    ],
    remainingSec: null,
  },
  {
    id: 'A004',
    level: 'P1',
    status: 'RESOLVED',
    escalateStep: 0,
    currentHandler: '李网格',
    elder: {
      id: 'E001',
      name: '王秀兰',
      age: 78,
      roomNo: '302室',
      address: '幸福里社区 3 栋 302 室',
      phone: '138****8888',
      healthTags: ['独居', '高血压'],
      primaryContact: {
        name: '张女士',
        phone: '13800000001',
        relation: '子女',
      },
    },
    event: {
      id: 'EV004',
      type: 'FALL',
      confidence: 0.88,
      occurredAt: '2026-11-15T08:35:10+08:00',
      features: {
        torsoAngle: 21.5,
        heightDrop: 0.55,
        stillDurationSec: 9,
        trackId: 2,
        aspectRatio: 1.82,
        kpConf: 0.86,
      },
      snapshotUrl: '/static/fall-snapshot.png',
      clipUrl: null,
      algoVersion: 'fall-v1.2.0',
    },
    notifiedAt: '2026-11-15T08:35:12+08:00',
    ackAt: '2026-11-15T08:35:45+08:00',
    resolvedAt: '2026-11-15T08:52:00+08:00',
    responseSec: 33,
    actions: [
      {
        id: 401,
        action: 'NOTIFY',
        actor: 'SYSTEM',
        actorName: '系统',
        channel: 'PUSH',
        result: 'DELIVERED',
        createdAt: '2026-11-15T08:35:12+08:00',
      },
      {
        id: 402,
        action: 'RESOLVE',
        actor: 'G01',
        actorName: '李网格',
        createdAt: '2026-11-15T08:52:00+08:00',
      },
    ],
    timeline: [
      {
        ts: '2026-11-15T08:35:10+08:00',
        text: '检测到跌倒（置信度 88%）',
      },
      {
        ts: '2026-11-15T08:35:45+08:00',
        text: '家属已确认响应',
      },
      {
        ts: '2026-11-15T08:52:00+08:00',
        text: '核实老人起身无大碍，告警已平安解除',
      },
    ],
    remainingSec: null,
  },
  {
    id: 'A005',
    level: 'P2',
    status: 'FALSE_POSITIVE',
    escalateStep: 0,
    currentHandler: '张女士（家属）',
    elder: {
      id: 'E002',
      name: '张建国',
      age: 81,
      roomNo: '104室',
      address: '幸福里社区 5 栋 104 室',
      phone: '139****6622',
      healthTags: ['空巢', '糖尿病'],
      primaryContact: {
        name: '张女士',
        phone: '13800000001',
        relation: '子女',
      },
    },
    event: {
      id: 'EV005',
      type: 'LONG_LIE',
      confidence: 0.79,
      occurredAt: '2026-11-12T19:50:44+08:00',
      features: {
        torsoAngle: 24.0,
        heightDrop: 0.45,
        stillDurationSec: 20,
        trackId: 6,
        aspectRatio: 1.65,
        kpConf: 0.81,
      },
      snapshotUrl: '/static/fall-snapshot.png',
      clipUrl: null,
      algoVersion: 'fall-v1.2.0',
    },
    notifiedAt: '2026-11-12T19:50:46+08:00',
    ackAt: '2026-11-12T19:51:20+08:00',
    resolvedAt: '2026-11-12T19:55:00+08:00',
    responseSec: 34,
    actions: [
      {
        id: 501,
        action: 'NOTIFY',
        actor: 'SYSTEM',
        actorName: '系统',
        channel: 'PUSH',
        result: 'DELIVERED',
        createdAt: '2026-11-12T19:50:46+08:00',
      },
      {
        id: 502,
        action: 'MARK_FALSE',
        actor: 'U010',
        actorName: '张女士',
        createdAt: '2026-11-12T19:55:00+08:00',
      },
    ],
    timeline: [
      {
        ts: '2026-11-12T19:50:44+08:00',
        text: '检测到久躺提醒（置信度 79%）',
      },
      {
        ts: '2026-11-12T19:55:00+08:00',
        text: '家属电话确认为午休弯腰拾物，标记为误报排除',
      },
    ],
    remainingSec: null,
  },
]

function wrapResponse<T>(data: T, code = 0, message = 'ok'): ApiResponse<T> {
  return {
    code,
    message,
    data,
    traceId: `h5-${Date.now().toString(36)}`,
  }
}

/** 读取持久化的告警列表，若无则使用初始 5 条数据 */
function loadAlarmDetails(): AlarmDetail[] {
  try {
    const raw = uni.getStorageSync(STORAGE_KEYS.ALARMS)
    if (raw) {
      const parsed = typeof raw === 'string' ? JSON.parse(raw) : raw
      if (Array.isArray(parsed) && parsed.length > 0) {
        return parsed
      }
    }
  } catch {
    // ignore storage parse error
  }
  return JSON.parse(JSON.stringify(INITIAL_ALARM_DETAILS))
}

function saveAlarmDetails(list: AlarmDetail[]): void {
  try {
    uni.setStorageSync(STORAGE_KEYS.ALARMS, JSON.stringify(list))
  } catch {
    // ignore storage write error
  }
}

/** 将 AlarmDetail 转换为列表项 AlarmItem（契约 3.7） */
function toAlarmItem(detail: AlarmDetail): AlarmItem {
  return {
    id: detail.id,
    level: detail.level,
    status: detail.status,
    elderId: detail.elder.id,
    elderName: detail.elder.name,
    roomNo: detail.elder.roomNo,
    communityName: '幸福里社区',
    currentHandler: detail.currentHandler,
    escalateStep: detail.escalateStep,
    createdAt: detail.event.occurredAt,
    notifiedAt: detail.notifiedAt,
    ackAt: detail.ackAt,
    resolvedAt: detail.resolvedAt,
    responseSec: detail.responseSec,
    eventType: detail.event.type,
    confidence: detail.event.confidence,
    snapshotUrl: detail.event.snapshotUrl,
    remainingSec: detail.remainingSec,
  }
}

/** Mock: 家属手机号+验证码登录 */
export function mockLogin(params: FamilyLoginParams): ApiResponse<LoginResult> {
  const phone = (params.phone || '').trim()
  const code = (params.code || '').trim()

  if (!/^1\d{10}$/.test(phone)) {
    return wrapResponse(null as unknown as LoginResult, 1001, '请输入正确的 11 位手机号')
  }
  if (code !== MOCK_ACCOUNT.CODE) {
    return wrapResponse(null as unknown as LoginResult, 1001, '验证码错误，固定验证码为 123456')
  }

  const user: UserInfo = {
    ...DEFAULT_USER,
    username: phone,
    phone,
  }
  const token = `mock-jwt-family-${Date.now()}`
  uni.setStorageSync(STORAGE_KEYS.TOKEN, token)
  uni.setStorageSync(STORAGE_KEYS.USER, JSON.stringify(user))
  uni.removeStorageSync(STORAGE_KEYS.ALARMS)

  return wrapResponse({
    accessToken: token,
    refreshToken: `mock-refresh-${Date.now()}`,
    expiresIn: 1800,
    user,
  })
}

/** Mock: 获取当前登录家属信息 */
export function mockGetCurrentUser(): UserInfo {
  try {
    const raw = uni.getStorageSync(STORAGE_KEYS.USER)
    if (raw) {
      return typeof raw === 'string' ? JSON.parse(raw) : raw
    }
  } catch {
    // ignore
  }
  return DEFAULT_USER
}

/** Mock: 是否已登录 */
export function mockIsLoggedIn(): boolean {
  try {
    return Boolean(uni.getStorageSync(STORAGE_KEYS.TOKEN))
  } catch {
    return false
  }
}

/** Mock: 退出登录 */
export function mockLogout(): ApiResponse<null> {
  try {
    uni.removeStorageSync(STORAGE_KEYS.TOKEN)
    uni.removeStorageSync(STORAGE_KEYS.USER)
    uni.removeStorageSync(STORAGE_KEYS.ALARMS)
  } catch {
    // ignore
  }
  return wrapResponse(null)
}

/** Mock: 获取我监护的老人列表（GET /api/v1/family/elders） */
export function mockGetFamilyElders(): ApiResponse<FamilyElderItem[]> {
  const alarms = loadAlarmDetails()
  const e1Pending = alarms.filter(
    (a) => a.elder.id === 'E001' && (a.status === 'PENDING' || a.status === 'ESCALATED')
  ).length

  const elders = INITIAL_ELDERS.map((elder) => {
    if (elder.id === 'E001') {
      return {
        ...elder,
        todayAlarmCount: e1Pending > 0 ? e1Pending : 1,
        statusText: '有 1 条告警',
      }
    }
    return { ...elder }
  })
  return wrapResponse(elders)
}

/** Mock: 获取告警分页列表（GET /api/v1/alarms，按时间倒序） */
export function mockGetAlarmList(elderId?: string): ApiResponse<PageResult<AlarmItem>> {
  const details = loadAlarmDetails()
  const filtered = elderId ? details.filter((d) => d.elder.id === elderId) : details
  const sorted = [...filtered].sort(
    (a, b) => new Date(b.event.occurredAt).getTime() - new Date(a.event.occurredAt).getTime()
  )
  const list = sorted.map(toAlarmItem)
  return wrapResponse({
    list,
    total: list.length,
    page: 1,
    pageSize: 20,
  })
}

/** Mock: 获取单条告警详情（GET /api/v1/alarms/{id}） */
export function mockGetAlarmDetail(id: string): ApiResponse<AlarmDetail> {
  const details = loadAlarmDetails()
  const found = details.find((d) => d.id === id) || details[0]
  return wrapResponse(JSON.parse(JSON.stringify(found)))
}

/** Mock: 家属确认告警 [我马上过去]（POST /api/v1/alarms/{id}/ack） */
export function mockAckAlarm(id: string, params?: AlarmAckParams): ApiResponse<AlarmDetail> {
  const details = loadAlarmDetails()
  const idx = details.findIndex((d) => d.id === id)
  const target = idx >= 0 ? details[idx] : details[0]
  const nowIso = new Date().toISOString()

  target.status = 'ACKNOWLEDGED'
  target.ackAt = nowIso
  target.currentHandler = '张女士（家属前往中）'
  target.remainingSec = null
  target.responseSec = 25
  target.actions.push({
    id: Date.now(),
    action: 'ACK',
    actor: 'U010',
    actorName: '张女士',
    detail: { note: params?.note || '家属确认：我马上过去' },
    createdAt: nowIso,
  })
  target.timeline.push({
    ts: nowIso,
    text: params?.note || '家属（张女士）点击「我马上过去」，已通知社区网格员协同备勤',
  })

  saveAlarmDetails(details)
  return wrapResponse(JSON.parse(JSON.stringify(target)))
}

/** Mock: 家属求助社区派单 [联系不上，求助社区]（POST /api/v1/alarms/{id}/dispatch） */
export function mockDispatchAlarm(
  id: string,
  params: AlarmDispatchParams
): ApiResponse<AlarmDetail> {
  const details = loadAlarmDetails()
  const idx = details.findIndex((d) => d.id === id)
  const target = idx >= 0 ? details[idx] : details[0]
  const nowIso = new Date().toISOString()

  target.status = 'COMMUNITY_DISPATCHED'
  target.ackAt = target.ackAt || nowIso
  target.escalateStep = Math.max(target.escalateStep, 1)
  target.currentHandler = '李网格（幸福里社区网格员）'
  target.remainingSec = null
  target.responseSec = target.responseSec || 30
  target.actions.push({
    id: Date.now(),
    action: 'DISPATCH',
    actor: 'U010',
    actorName: '张女士',
    channel: 'SMS',
    result: 'SENT',
    detail: {
      guardianId: params.guardianId || 'G01',
      guardianName: '李网格',
      note: params.note || '家属联系不上老人，求助社区网格员紧急上门',
    },
    createdAt: nowIso,
  })
  target.timeline.push({
    ts: nowIso,
    text: '已通知社区，责任网格员（李网格 13700002222）正在前往老人住所',
  })

  saveAlarmDetails(details)
  return wrapResponse(JSON.parse(JSON.stringify(target)))
}

/** Mock: 读取/保存通知设置 */
export function mockGetNotificationSettings(): FamilyNotificationSettings {
  try {
    const raw = uni.getStorageSync(STORAGE_KEYS.NOTIFY_SETTINGS)
    if (raw) {
      return typeof raw === 'string' ? JSON.parse(raw) : raw
    }
  } catch {
    // ignore
  }
  return {
    pushEnabled: true,
    smsEnabled: true,
    callNightEnabled: true,
  }
}

export function mockSaveNotificationSettings(
  settings: FamilyNotificationSettings
): FamilyNotificationSettings {
  try {
    uni.setStorageSync(STORAGE_KEYS.NOTIFY_SETTINGS, JSON.stringify(settings))
  } catch {
    // ignore
  }
  return settings
}
