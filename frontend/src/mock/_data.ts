/**
 * 全量 Mock 数据源（内存态单例，以 _ 开头不被 vite-plugin-mock 当作路由注册）
 *
 * 规模与边界要求（F2 阶段）：
 * - 老人 100 条：5 条无绑定设备、5 条设备离线、5 条 status=2 暂停、3 条无任何告警
 * - 设备 90 条：在线 80%(72) / 离线 12%(11) / 故障 5%(4) / 未激活 3%(3)
 * - 事件 500 条：近 30 天（含早晚高峰）、FALL 80%(400) / LONG_LIE 20%(100)、P0 10%(50) / P1 30%(150) / P2 60%(300)
 * - 告警 180 条：覆盖全部 6 种状态、PENDING 在近 10 分钟内、ESCALATED escalateStep>=1
 */
import dayjs from 'dayjs'
import {
  AlarmActionType,
  AlarmStatus,
  NotifyChannel,
  NotifyResultStatus,
  type AlarmAction,
  type AlarmDetail,
  type AlarmItem,
  type AlarmTimelineItem,
} from '@/types/alarm'
import {
  DeviceStatus,
  DeviceType,
  FurnitureType,
  type Device,
  type DeviceConfig,
} from '@/types/device'
import {
  DetectMode,
  ElderStatus,
  FAMILY_RELATIONS,
  Gender,
  HEALTH_TAGS,
  type Elder,
  type ElderDetail,
  type EmergencyContact,
  type FamilyBinding,
} from '@/types/elder'
import {
  EventHandleResult,
  EventLevel,
  EventType,
  type EventDetail,
  type EventFeatures,
} from '@/types/event'
import { calcAge, createSeededRandom, formatIsoOffset, maskPhone } from './_util'

const rand = createSeededRandom(20261118)

function randInt(min: number, max: number): number {
  return Math.floor(rand() * (max - min + 1)) + min
}

function randFloat(min: number, max: number, digits = 2): number {
  return Number((min + rand() * (max - min)).toFixed(digits))
}

function pick<T>(arr: readonly T[]): T {
  return arr[Math.floor(rand() * arr.length)]
}

// ---------------- 基础基础维表：社区 & 网格员 ----------------

export interface MockCommunity {
  id: string
  name: string
  address: string
  x: number
  y: number
}

export const COMMUNITIES: MockCommunity[] = [
  { id: 'C01', name: '幸福里社区', address: '幸福路 18 号', x: 0.28, y: 0.36 },
  { id: 'C02', name: '康乐苑社区', address: '康乐街 66 号', x: 0.62, y: 0.31 },
  { id: 'C03', name: '阳光花园社区', address: '阳光大道 102 号', x: 0.48, y: 0.58 },
  { id: 'C04', name: '翠竹园社区', address: '翠竹路 5 号', x: 0.22, y: 0.72 },
  { id: 'C05', name: '长青新村社区', address: '长青南路 88 号', x: 0.76, y: 0.67 },
]

export interface MockGuardian {
  id: string
  name: string
  phone: string
  communityId: string
}

export const GUARDIANS: MockGuardian[] = [
  { id: 'G01', name: '李网格', phone: '13700001001', communityId: 'C01' },
  { id: 'G02', name: '陈思远', phone: '13700001002', communityId: 'C01' },
  { id: 'G03', name: '王建国', phone: '13700001003', communityId: 'C02' },
  { id: 'G04', name: '赵敏', phone: '13700001004', communityId: 'C02' },
  { id: 'G05', name: '周文涛', phone: '13700001005', communityId: 'C03' },
  { id: 'G06', name: '吴晓梅', phone: '13700001006', communityId: 'C03' },
  { id: 'G07', name: '孙志强', phone: '13700001007', communityId: 'C04' },
  { id: 'G08', name: '林海燕', phone: '13700001008', communityId: 'C05' },
]

const ELDER_NAMES = [
  '王秀兰', '李国强', '张桂芳', '刘德华', '陈淑珍', '杨建华', '赵玉兰', '黄志明', '周秀英', '吴文彬',
  '徐桂英', '孙建国', '马玉珍', '朱德明', '胡秀珍', '郭志强', '何桂兰', '高建军', '林玉梅', '罗永康',
  '郑淑芬', '梁国华', '谢秀梅', '宋德福', '唐玉兰', '许志远', '韩桂芳', '冯建平', '邓秀英', '曹国栋',
  '彭淑华', '曾志明', '萧玉珍', '田建国', '董桂英', '袁德华', '潘秀兰', '于永强', '蒋玉梅', '蔡志刚',
  '余桂珍', '杜建军', '叶秀芳', '程国平', '苏玉兰', '魏志强', '吕淑珍', '丁建华', '任桂英', '沈德明',
  '姚秀梅', '卢永康', '姜玉珍', '崔建国', '钟桂芳', '谭志明', '陆秀兰', '汪国华', '范淑英', '金建平',
  '石玉兰', '廖德福', '贾志远', '夏桂英', '韦秀珍', '付国栋', '方玉梅', '白建军', '邹淑华', '孟志强',
  '熊桂兰', '秦建华', '邱秀英', '江德明', '尹玉珍', '薛国强', '闫桂芳', '段志刚', '雷秀兰', '侯永强',
  '龙玉梅', '史建平', '陶桂珍', '黎国华', '贺秀芳', '顾志明', '毛淑珍', '郝建国', '龚玉兰', '邵德华',
  '万秀梅', '钱志远', '严桂英', '武建军', '戴玉珍', '莫国平', '孔秀兰', '向志强', '汤淑芬', '常德明',
]

const FAMILY_SURNAMES = ['张', '李', '王', '刘', '陈', '杨', '赵', '周', '吴', '徐']
const PHONE_PREFIXES = ['138', '139', '136', '135', '158', '159', '186', '188']

function genRawPhone(): string {
  const prefix = pick(PHONE_PREFIXES)
  const mid = String(randInt(1000, 9999))
  const tail = String(randInt(1000, 9999))
  return `${prefix}${mid}${tail}`
}

// ---------------- 内部存储记录（含详情需要的附加字段） ----------------

export interface ElderRecord extends Elder {
  rawPhone: string
  emergencyContact: EmergencyContact[]
  families: FamilyBinding[]
}

export interface EventRecord extends EventDetail {}

export interface AlarmRecord extends AlarmItem {
  eventId: string
  actions: AlarmAction[]
  remark: string | null
  needFollowUp?: boolean
}

const now = dayjs()

// ---------------- 1. 生成 100 条老人数据 ----------------

function buildElders(): ElderRecord[] {
  const list: ElderRecord[] = []
  for (let i = 0; i < 100; i++) {
    const id = `E${String(i + 1).padStart(3, '0')}`
    const name = ELDER_NAMES[i]
    const gender: Gender = i % 2 === 0 ? Gender.FEMALE : Gender.MALE
    const targetAge = 65 + (i % 28) // 65~92
    const birthDate = now
      .subtract(targetAge, 'year')
      .subtract(randInt(1, 300), 'day')
      .format('YYYY-MM-DD')
    const age = calcAge(birthDate)

    const community = COMMUNITIES[i % COMMUNITIES.length]
    const communityGuardians = GUARDIANS.filter((g) => g.communityId === community.id)
    const guardian = communityGuardians[i % communityGuardians.length]

    const building = randInt(1, 12)
    const floor = randInt(1, 6)
    const room = randInt(1, 4)
    const roomNo = `${floor}0${room}`
    const address = `${community.name} ${building} 栋`

    // healthTags: 0-3 个
    const tagCount = i % 4 // 0, 1, 2, 3
    const shuffledTags = [...HEALTH_TAGS].sort(() => rand() - 0.5)
    const healthTags = shuffledTags.slice(0, tagCount)

    const rawPhone = genRawPhone()
    const phone = maskPhone(rawPhone)

    // 边界态：索引 90..94（5条）为 status=2 暂停
    const status: ElderStatus = i >= 90 && i <= 94 ? ElderStatus.PAUSED : ElderStatus.ACTIVE
    const detectMode: DetectMode = ((i % 3) + 1) as DetectMode

    const familySurname = FAMILY_SURNAMES[i % FAMILY_SURNAMES.length]
    const familyPhone = genRawPhone()
    const relation = FAMILY_RELATIONS[i % 2]
    const contactName = `${familySurname}${gender === Gender.FEMALE ? '女士' : '先生'}`

    const emergencyContact: EmergencyContact[] = [
      { name: contactName, phone: familyPhone, relation, primary: true },
    ]
    if (i % 3 === 0) {
      emergencyContact.push({
        name: `${FAMILY_SURNAMES[(i + 3) % FAMILY_SURNAMES.length]}女士`,
        phone: genRawPhone(),
        relation: '其他亲属',
        primary: false,
      })
    }

    const families: FamilyBinding[] =
      i === 96
        ? [] // 覆盖“无家属”边界态
        : [
            {
              bindingId: `B${String(i + 1).padStart(3, '0')}`,
              userId: i === 0 ? 'U010' : `U${String(100 + i)}`,
              name: contactName,
              phone: maskPhone(familyPhone),
              relation,
              isPrimary: true,
              notifyOrder: 1,
            },
          ]

    list.push({
      id,
      name,
      gender,
      age,
      birthDate,
      phone,
      rawPhone,
      address,
      roomNo,
      communityId: community.id,
      communityName: community.name,
      guardianId: guardian.id,
      guardianName: guardian.name,
      healthTags,
      detectMode,
      status,
      deviceOnline: false, // 生成设备后统一回填
      lastAlarmAt: null, // 生成告警后统一回填
      alarmCount30d: 0, // 生成告警后统一回填
      createdAt: formatIsoOffset(now.subtract(randInt(30, 360), 'day')),
      emergencyContact,
      families,
    })
  }
  return list
}

// ---------------- 2. 生成 90 条设备数据 ----------------
// status 分布：在线 80%(72) / 离线 12%(11) / 故障 5%(4) / 未激活 3%(3)
// 边界态：老人 E096~E100（索引 95..99）共 5 条无绑定设备；前 5 条离线设备绑定到老人，保证 ≥5 位老人设备离线

function buildDeviceConfig(): DeviceConfig {
  const rx = randFloat(0.05, 0.14)
  const ry = randFloat(0.1, 0.18)
  const rw = randFloat(0.74, 0.84)
  const rh = randFloat(0.7, 0.78)
  return {
    roi: [
      [rx, ry],
      [Number((rx + rw).toFixed(2)), ry],
      [Number((rx + rw).toFixed(2)), Number((ry + rh).toFixed(2))],
      [rx, Number((ry + rh).toFixed(2))],
    ],
    furniture: [
      {
        type: FurnitureType.BED,
        x: 0.58,
        y: 0.28,
        w: 0.36,
        h: 0.5,
        points: [
          [0.58, 0.28],
          [0.94, 0.28],
          [0.94, 0.78],
          [0.58, 0.78],
        ],
      },
      {
        type: FurnitureType.CHAIR,
        x: 0.12,
        y: 0.55,
        w: 0.16,
        h: 0.21,
        points: [
          [0.12, 0.55],
          [0.28, 0.55],
          [0.28, 0.76],
          [0.12, 0.76],
        ],
      },
    ],
    sensitivity: randFloat(0.6, 0.9, 1),
    quietHours: ['22:00-06:00'],
  }
}

function buildDevices(eldersList: ElderRecord[]): Device[] {
  const list: Device[] = []
  // 状态池：72 在线 + 11 离线 + 4 故障 + 3 未激活 = 90
  const statusPool: DeviceStatus[] = [
    ...Array<DeviceStatus>(72).fill(DeviceStatus.ONLINE),
    ...Array<DeviceStatus>(11).fill(DeviceStatus.OFFLINE),
    ...Array<DeviceStatus>(4).fill(DeviceStatus.FAULT),
    ...Array<DeviceStatus>(3).fill(DeviceStatus.INACTIVE),
  ]

  // 索引 0..89 绑定到老人 0..89（老人 95..99 无绑定设备；老人 90..94 也无设备或有部分无设备，此处确保至少 5 位无绑定设备）
  // 顺便把前 5 条离线设备放在老人索引 5..9 上，保证在册老人中有 ≥5 条设备离线
  const arrangedStatus: DeviceStatus[] = [...statusPool]
  // 把离线项放到索引 5..15，在线放 0..4 和 16..76，故障 77..80，未激活 81..83，其余在线
  const finalStatuses: DeviceStatus[] = new Array(90).fill(DeviceStatus.ONLINE)
  for (let i = 5; i < 16; i++) finalStatuses[i] = DeviceStatus.OFFLINE // 11 条离线
  for (let i = 80; i < 84; i++) finalStatuses[i] = DeviceStatus.FAULT // 4 条故障
  for (let i = 84; i < 87; i++) finalStatuses[i] = DeviceStatus.INACTIVE // 3 条未激活
  void arrangedStatus

  for (let i = 0; i < 90; i++) {
    const id = `D${String(i + 1).padStart(3, '0')}`
    const deviceNo = `EDGE-${String(i + 1).padStart(4, '0')}`
    // 前 90 位老人（E001~E090）每人绑定 1 台设备；E091~E100（含暂停的 5 位与无设备的 5 位）无设备
    const elder = eldersList[i]
    const status = finalStatuses[i]
    const type: DeviceType =
      i % 10 === 8 ? DeviceType.IPC : i % 10 === 9 ? DeviceType.RADAR : DeviceType.EDGE_BOX

    let lastHeartbeat: string | null = null
    if (status === DeviceStatus.ONLINE) {
      // 保留 2 台状态为「在线」但心跳超过 5 分钟的设备（索引 2、3），用于展示心跳延迟标红提示
      if (i === 2 || i === 3) {
        lastHeartbeat = formatIsoOffset(now.subtract(randInt(8, 25), 'minute'))
      } else {
        lastHeartbeat = formatIsoOffset(now.subtract(randInt(5, 55), 'second'))
      }
    } else if (status === DeviceStatus.OFFLINE) {
      lastHeartbeat = formatIsoOffset(now.subtract(randInt(120, 4320), 'minute'))
    } else if (status === DeviceStatus.FAULT) {
      lastHeartbeat = formatIsoOffset(now.subtract(randInt(30, 600), 'minute'))
    }

    list.push({
      id,
      deviceNo,
      elderId: elder.id,
      elderName: elder.name,
      communityId: elder.communityId,
      communityName: elder.communityName,
      roomNo: elder.roomNo,
      type,
      rtspUrl: type === DeviceType.RADAR ? undefined : `rtsp://192.168.10.${10 + i}:554/stream1`,
      installAddr: `${elder.address} ${elder.roomNo} 室客厅`,
      algoVersion: i % 3 === 0 ? 'fall-v1.2.1' : 'fall-v1.2.0',
      config: buildDeviceConfig(),
      status,
      lastHeartbeat,
      createdAt: elder.createdAt,
    })
  }
  return list
}

// ---------------- 3. 生成 500 条事件数据 ----------------
// 近 30 天，早晚高峰（6-9 点、18-21 点更多）
// FALL 80%(400) / LONG_LIE 20%(100)
// P0 10%(50) / P1 30%(150) / P2 60%(300)
// handled: 60%(300) true，其中 25%(75) FALSE_POSITIVE
// 保留 E098, E099, E100 无任何事件与告警

const PEAK_HOURS = [
  6, 6, 7, 7, 7, 8, 8, 8, 9, 9,
  18, 18, 19, 19, 19, 20, 20, 20, 21, 21,
  10, 11, 14, 15, 16, 22,
]

function buildEventFeatures(type: EventType): EventFeatures {
  const isLongLie = type === EventType.LONG_LIE
  return {
    torsoAngle: isLongLie ? randFloat(55, 72, 1) : randFloat(62, 90, 1),
    heightDrop: randFloat(0.4, 0.8, 2),
    stillDurationSec: isLongLie ? randInt(30, 120) : randInt(3, 45),
    trackId: randInt(1, 5),
    aspectRatio: randFloat(0.9, 2.6, 2),
    kpConf: randFloat(0.25, 0.85, 2),
  }
}

function buildEvents(eldersList: ElderRecord[], devicesList: Device[]): EventRecord[] {
  const list: EventRecord[] = []
  // 有设备的老人范围（E001~E090）作为事件主来源，E098~E100 保证无任何告警
  const eligibleElders = eldersList.slice(0, 90)

  // 预分配分布（再确定性洗牌）
  const types: EventType[] = [
    ...Array<EventType>(400).fill(EventType.FALL),
    ...Array<EventType>(100).fill(EventType.LONG_LIE),
  ].sort(() => rand() - 0.5)

  const levels: EventLevel[] = [
    ...Array<EventLevel>(50).fill(EventLevel.P0),
    ...Array<EventLevel>(150).fill(EventLevel.P1),
    ...Array<EventLevel>(300).fill(EventLevel.P2),
  ].sort(() => rand() - 0.5)

  // handled: 300 true (75 FALSE_POSITIVE + 225 TRUE_FALL) + 200 false
  const handleStates: Array<{ handled: boolean; result: EventHandleResult | null }> = [
    ...Array.from({ length: 75 }, () => ({ handled: true, result: EventHandleResult.FALSE_POSITIVE })),
    ...Array.from({ length: 225 }, () => ({ handled: true, result: EventHandleResult.TRUE_FALL })),
    ...Array.from({ length: 200 }, () => ({ handled: false, result: null })),
  ].sort(() => rand() - 0.5)

  // 生成时间戳（近 30 天内，含今天）
  const rawDates: dayjs.Dayjs[] = []
  for (let i = 0; i < 500; i++) {
    const dayOffset = i < 20 ? 0 : randInt(0, 29)
    const hour = dayOffset === 0 ? randInt(0, Math.max(0, now.hour())) : pick(PEAK_HOURS)
    const minute = dayOffset === 0 && hour === now.hour() ? randInt(0, Math.max(0, now.minute())) : randInt(0, 59)
    const second = randInt(0, 59)
    const dt = now
      .subtract(dayOffset, 'day')
      .hour(hour)
      .minute(minute)
      .second(second)
    rawDates.push(dt)
  }
  // 按发生时间倒序排列（最新事件在最前）
  rawDates.sort((a, b) => b.valueOf() - a.valueOf())

  for (let i = 0; i < 500; i++) {
    const id = `EV${String(500 - i).padStart(4, '0')}`
    const elder = eligibleElders[i % eligibleElders.length]
    const device = devicesList.find((d) => d.elderId === elder.id) || devicesList[0]
    const type = types[i]
    const level = levels[i]
    const confidence =
      level === EventLevel.P0
        ? randFloat(0.85, 0.99, 2)
        : level === EventLevel.P1
          ? randFloat(0.7, 0.9, 2)
          : randFloat(0.55, 0.78, 2)

    const occurredDay = rawDates[i]
    const occurredAt = formatIsoOffset(occurredDay)
    const hs = handleStates[i]
    const handledAt = hs.handled
      ? formatIsoOffset(occurredDay.add(randInt(2, 45), 'minute'))
      : null

    list.push({
      id,
      eventId: `uuid-${id.toLowerCase()}-${String(1000 + i)}`,
      elderId: elder.id,
      elderName: elder.name,
      roomNo: elder.roomNo,
      deviceId: device.id,
      deviceNo: device.deviceNo,
      type,
      level,
      confidence,
      occurredAt,
      snapshotUrl: `https://picsum.photos/seed/${id}/640/480`,
      clipUrl: i % 3 === 0 ? `https://example.com/mock-clips/${id}.mp4` : null,
      handled: hs.handled,
      handleResult: hs.result,
      handleRemark: hs.handled
        ? hs.result === EventHandleResult.FALSE_POSITIVE
          ? '老人弯腰拾物/坐卧误触，已确认无碍'
          : '已联系家属并上门确认安全'
        : null,
      handledAt,
      features: buildEventFeatures(type),
      algoVersion: device.algoVersion,
    })
  }
  return list
}

// ---------------- 4. 生成 180 条告警数据 ----------------
// status 分布：
//   PENDING 8%(14) / ACKNOWLEDGED 22%(40) / ESCALATED 10%(18)
//   COMMUNITY_DISPATCHED 5%(9) / RESOLVED 40%(72) / FALSE_POSITIVE 15%(27)
// PENDING 的 createdAt 必须在近 10 分钟内（此处设在 10~45 秒内，这样 60s 倒计时在刚启动时也都是正数）

function buildAlarms(eldersList: ElderRecord[], eventsList: EventRecord[]): AlarmRecord[] {
  const list: AlarmRecord[] = []
  // 被 PENDING 告警改写过 occurredAt 的事件，收尾时统一重排
  const pendingLinkedEvents: EventRecord[] = []

  // 前 14 条：PENDING（近 10 分钟内，且保证在 10~50 秒前创建，便于演示倒计时）
  // 第 15~180 条（共 166 条）：按配额分配给其余 5 种状态
  const nonPendingStatuses: AlarmStatus[] = [
    ...Array<AlarmStatus>(40).fill(AlarmStatus.ACKNOWLEDGED),
    ...Array<AlarmStatus>(18).fill(AlarmStatus.ESCALATED),
    ...Array<AlarmStatus>(9).fill(AlarmStatus.COMMUNITY_DISPATCHED),
    ...Array<AlarmStatus>(72).fill(AlarmStatus.RESOLVED),
    ...Array<AlarmStatus>(27).fill(AlarmStatus.FALSE_POSITIVE),
  ].sort(() => rand() - 0.5)

  // 优先选 P0/P1 事件关联告警，不足再从全部事件顺序补齐到 180 条
  const p01Events = eventsList.filter((e) => e.level === EventLevel.P0 || e.level === EventLevel.P1)
  const p2Events = eventsList.filter((e) => e.level === EventLevel.P2)
  const linkedEvents = [...p01Events, ...p2Events].slice(0, 180)

  for (let i = 0; i < 180; i++) {
    const id = `A${String(180 - i).padStart(4, '0')}`
    const ev = linkedEvents[i]
    const elder = eldersList.find((e) => e.id === ev.elderId) || eldersList[0]
    const primaryFamily = elder.families[0]?.name || '张女士'

    const isPending = i < 14
    const status: AlarmStatus = isPending ? AlarmStatus.PENDING : nonPendingStatuses[i - 14]

    // PENDING 告警发生在近 10~50 秒内（严格在近 10 分钟内）
    const baseTime = isPending ? now.subtract(10 + i * 3, 'second') : dayjs(ev.occurredAt)
    if (isPending) {
      ev.occurredAt = formatIsoOffset(baseTime)
      ev.handled = false
      ev.handleResult = null
      ev.handleRemark = null
      ev.handledAt = null
      // 事件时间被改写到"刚刚"，而 eventsStore 是按下标排的，必须重排一次；
      // 否则这几条会留在列表中部、时间却晚于相邻项，列表看起来是乱序的
      pendingLinkedEvents.push(ev)
    }

    const createdAt = formatIsoOffset(baseTime.add(2, 'second'))
    const notifiedAt = createdAt

    let escalateStep = 0
    let currentHandler = primaryFamily
    let ackAt: string | null = null
    let resolvedAt: string | null = null
    let responseSec: number | null = null
    let remark: string | null = null

    const actions: AlarmAction[] = [
      {
        id: 1,
        action: AlarmActionType.NOTIFY,
        actor: 'SYSTEM',
        actorName: '系统',
        channel: NotifyChannel.PUSH,
        result: NotifyResultStatus.SENT,
        detail: { target: primaryFamily },
        createdAt: notifiedAt,
      },
    ]

    if (status === AlarmStatus.ESCALATED) {
      escalateStep = i % 3 === 0 ? 2 : 1
      currentHandler = elder.guardianName
      const escAt = formatIsoOffset(baseTime.add(62, 'second'))
      actions.push({
        id: 2,
        action: AlarmActionType.ESCALATE,
        actor: 'SYSTEM',
        actorName: '系统',
        channel: NotifyChannel.SMS,
        result: NotifyResultStatus.DELIVERED,
        detail: { from: '家属', to: `网格员（${elder.guardianName}）` },
        createdAt: escAt,
      })
    } else if (status === AlarmStatus.ACKNOWLEDGED) {
      const resp = randInt(12, 55)
      ackAt = formatIsoOffset(baseTime.add(2 + resp, 'second'))
      responseSec = resp
      currentHandler = primaryFamily
      actions.push({
        id: 2,
        action: AlarmActionType.ACK,
        actor: elder.families[0]?.userId || 'U010',
        actorName: primaryFamily,
        createdAt: ackAt,
      })
    } else if (status === AlarmStatus.COMMUNITY_DISPATCHED) {
      escalateStep = 1
      currentHandler = elder.guardianName
      const escAt = formatIsoOffset(baseTime.add(62, 'second'))
      const dispAt = formatIsoOffset(baseTime.add(95, 'second'))
      actions.push(
        {
          id: 2,
          action: AlarmActionType.ESCALATE,
          actor: 'SYSTEM',
          actorName: '系统',
          channel: NotifyChannel.SMS,
          result: NotifyResultStatus.DELIVERED,
          detail: { from: '家属', to: `网格员（${elder.guardianName}）` },
          createdAt: escAt,
        },
        {
          id: 3,
          action: AlarmActionType.DISPATCH,
          actor: 'U001',
          actorName: '社区值班员',
          detail: { guardianName: elder.guardianName },
          createdAt: dispAt,
        },
      )
    } else if (status === AlarmStatus.RESOLVED || status === AlarmStatus.FALSE_POSITIVE) {
      const resp = randInt(15, 110)
      const ackD = baseTime.add(2 + resp, 'second')
      const resD = ackD.add(randInt(180, 900), 'second')
      ackAt = formatIsoOffset(ackD)
      resolvedAt = formatIsoOffset(resD)
      responseSec = resp
      if (resp > 60) {
        escalateStep = 1
        currentHandler = elder.guardianName
        actions.push({
          id: 2,
          action: AlarmActionType.ESCALATE,
          actor: 'SYSTEM',
          actorName: '系统',
          channel: NotifyChannel.SMS,
          result: NotifyResultStatus.DELIVERED,
          detail: { from: '家属', to: `网格员（${elder.guardianName}）` },
          createdAt: formatIsoOffset(baseTime.add(62, 'second')),
        })
      }
      actions.push(
        {
          id: actions.length + 1,
          action: AlarmActionType.ACK,
          actor: resp > 60 ? elder.guardianId : elder.families[0]?.userId || 'U010',
          actorName: currentHandler,
          createdAt: ackAt,
        },
        {
          id: actions.length + 2,
          action:
            status === AlarmStatus.FALSE_POSITIVE
              ? AlarmActionType.MARK_FALSE
              : AlarmActionType.RESOLVE,
          actor: currentHandler === primaryFamily ? 'U010' : elder.guardianId,
          actorName: currentHandler,
          detail: {
            note: status === AlarmStatus.FALSE_POSITIVE ? '经核实为误报' : '已上门核查，老人安全',
          },
          createdAt: resolvedAt,
        },
      )
      remark = status === AlarmStatus.FALSE_POSITIVE ? '误报关闭' : '已上门处置完成'
      // 同步事件状态
      ev.handled = true
      ev.handleResult =
        status === AlarmStatus.FALSE_POSITIVE
          ? EventHandleResult.FALSE_POSITIVE
          : EventHandleResult.TRUE_FALL
      ev.handledAt = resolvedAt
    }

    list.push({
      id,
      eventId: ev.id,
      level: ev.level,
      status,
      elderId: elder.id,
      elderName: elder.name,
      roomNo: elder.roomNo,
      communityName: elder.communityName,
      currentHandler,
      escalateStep,
      createdAt,
      notifiedAt,
      ackAt,
      resolvedAt,
      responseSec,
      eventType: ev.type,
      confidence: ev.confidence,
      snapshotUrl: ev.snapshotUrl,
      actions,
      remark,
    })
  }

  // PENDING 告警把关联事件的时间推到了"刚刚"，这里统一按发生时间重排，
  // 保证 /events 列表始终严格倒序（前端按列表顺序直接展示）
  if (pendingLinkedEvents.length > 0) {
    eventsList.sort((a, b) => new Date(b.occurredAt).getTime() - new Date(a.occurredAt).getTime())
  }

  return list
}

const GLOBAL_DATA_KEY = '__SILVER_BELL_MOCK_DATA__'

interface MockDataSingleton {
  eldersStore: ElderRecord[]
  devicesStore: Device[]
  eventsStore: EventRecord[]
  alarmsStore: AlarmRecord[]
}

function initMockDataSingleton(): MockDataSingleton {
  const g = globalThis as unknown as Record<string, MockDataSingleton | undefined>
  if (g[GLOBAL_DATA_KEY]) return g[GLOBAL_DATA_KEY] as MockDataSingleton

  const elders = buildElders()
  const devices = buildDevices(elders)
  for (const elder of elders) {
    elder.deviceOnline = devices.some(
      (d) => d.elderId === elder.id && d.status === DeviceStatus.ONLINE,
    )
  }
  const events = buildEvents(elders, devices)
  const alarms = buildAlarms(elders, events)

  const singleton: MockDataSingleton = {
    eldersStore: elders,
    devicesStore: devices,
    eventsStore: events,
    alarmsStore: alarms,
  }
  g[GLOBAL_DATA_KEY] = singleton
  return singleton
}

const _singleton = initMockDataSingleton()
export const eldersStore: ElderRecord[] = _singleton.eldersStore
export const devicesStore: Device[] = _singleton.devicesStore
export const eventsStore: EventRecord[] = _singleton.eventsStore
export const alarmsStore: AlarmRecord[] = _singleton.alarmsStore

// 回填老人的 lastAlarmAt 与 alarmCount30d
export function syncElderAlarmStats(): void {
  const cutoff = dayjs().subtract(30, 'day').valueOf()
  for (const elder of eldersStore) {
    const elderAlarms = alarmsStore.filter((a) => a.elderId === elder.id)
    if (elderAlarms.length === 0) {
      elder.lastAlarmAt = null
      elder.alarmCount30d = 0
      continue
    }
    const sorted = [...elderAlarms].sort(
      (a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime(),
    )
    elder.lastAlarmAt = sorted[0].createdAt
    elder.alarmCount30d = elderAlarms.filter((a) => new Date(a.createdAt).getTime() >= cutoff).length
  }
}

syncElderAlarmStats()

// ---------------- 5. 公共组装辅助函数 ----------------

const ESCALATE_CYCLE_SEC = 60

/**
 * 修正 PENDING 告警随 dev server 运行产生的时间漂移：
 * 若某条 PENDING 告警距离当前时间已满/超过 60s（或出现异常未来时间），
 * 自动将其 createdAt / notifiedAt 及关联事件的 occurredAt 重锚定到当前近 8~50 秒内，
 * 保证任意时刻查询，createdAt 都在近 1 分钟内且 remainingSec 严格在 10~52 正整数区间，绝不出现负数。
 */
export function refreshPendingAlarmTimestamps(): void {
  const nowMs = Date.now()
  let eventChanged = false
  let pendingIdx = 0

  for (const alarm of alarmsStore) {
    if (alarm.status !== AlarmStatus.PENDING) continue
    const elapsedSec = Math.floor((nowMs - new Date(alarm.createdAt).getTime()) / 1000)
    if (elapsedSec >= ESCALATE_CYCLE_SEC - 2 || elapsedSec < 0) {
      const freshAgeSec = 8 + ((pendingIdx * 3) % 42) // 8~49 秒前
      const baseTime = dayjs(nowMs).subtract(freshAgeSec + 2, 'second')
      const freshCreated = formatIsoOffset(baseTime.add(2, 'second'))
      alarm.createdAt = freshCreated
      alarm.notifiedAt = freshCreated

      const notifyAct = alarm.actions.find((a) => a.action === AlarmActionType.NOTIFY)
      if (notifyAct) notifyAct.createdAt = freshCreated

      const ev = eventsStore.find((e) => e.id === alarm.eventId)
      if (ev) {
        ev.occurredAt = formatIsoOffset(baseTime)
        eventChanged = true
      }
    }
    pendingIdx += 1
  }

  if (eventChanged) {
    eventsStore.sort((a, b) => new Date(b.occurredAt).getTime() - new Date(a.occurredAt).getTime())
  }
}

/** 计算 PENDING 告警距下一级升级的剩余秒数，非 PENDING 返回 null */
export function calcRemainingSec(alarm: AlarmRecord): number | null {
  if (alarm.status !== AlarmStatus.PENDING) return null
  refreshPendingAlarmTimestamps()
  const elapsed = Math.max(0, Math.floor((Date.now() - new Date(alarm.createdAt).getTime()) / 1000))
  return Math.max(1, ESCALATE_CYCLE_SEC - elapsed)
}

/** 构造对外返回的 AlarmItem（自动刷新漂移时间 + 实时计算 remainingSec） */
export function toAlarmListItem(alarm: AlarmRecord): AlarmItem {
  if (alarm.status === AlarmStatus.PENDING) {
    refreshPendingAlarmTimestamps()
  }
  return {
    id: alarm.id,
    level: alarm.level,
    status: alarm.status,
    elderId: alarm.elderId,
    elderName: alarm.elderName,
    roomNo: alarm.roomNo,
    communityName: alarm.communityName,
    currentHandler: alarm.currentHandler,
    escalateStep: alarm.escalateStep,
    createdAt: alarm.createdAt,
    notifiedAt: alarm.notifiedAt,
    ackAt: alarm.ackAt,
    resolvedAt: alarm.resolvedAt,
    responseSec: alarm.responseSec,
    eventType: alarm.eventType,
    confidence: alarm.confidence,
    snapshotUrl: alarm.snapshotUrl,
    remainingSec: calcRemainingSec(alarm),
  }
}

/** 生成告警详情的中文时间轴（按时间正序） */
export function buildAlarmTimeline(alarm: AlarmRecord, ev: EventRecord): AlarmTimelineItem[] {
  const typeLabel = ev.type === EventType.LONG_LIE ? '久躺' : '跌倒'
  const items: AlarmTimelineItem[] = [
    {
      ts: ev.occurredAt,
      text: `检测到${typeLabel}（置信度 ${Math.round(ev.confidence * 100)}%）`,
    },
  ]

  const sortedActions = [...alarm.actions].sort(
    (a, b) => new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime(),
  )

  for (const act of sortedActions) {
    if (act.action === AlarmActionType.NOTIFY) {
      const target = (act.detail?.target as string) || alarm.currentHandler
      items.push({ ts: act.createdAt, text: `已推送家属（${target}）` })
    } else if (act.action === AlarmActionType.ESCALATE) {
      const to = (act.detail?.to as string) || `网格员（${alarm.currentHandler}）`
      items.push({ ts: act.createdAt, text: `超时未确认，升级至${to}` })
    } else if (act.action === AlarmActionType.ACK) {
      items.push({ ts: act.createdAt, text: `${act.actorName}已确认接警` })
    } else if (act.action === AlarmActionType.DISPATCH) {
      const guardianName = (act.detail?.guardianName as string) || alarm.currentHandler
      items.push({ ts: act.createdAt, text: `已派单至网格员（${guardianName}）` })
    } else if (act.action === AlarmActionType.RESOLVE) {
      items.push({ ts: act.createdAt, text: `${act.actorName}已处置完结` })
    } else if (act.action === AlarmActionType.MARK_FALSE) {
      items.push({ ts: act.createdAt, text: `${act.actorName}标记为误报并关闭` })
    } else if (act.action === AlarmActionType.DEDUP) {
      items.push({ ts: act.createdAt, text: '5 分钟内重复事件，已自动去重合并' })
    }
  }

  return items.sort((a, b) => new Date(a.ts).getTime() - new Date(b.ts).getTime())
}

/** 构造完整告警详情（GET /alarms/{id}） */
export function buildAlarmDetail(alarm: AlarmRecord): AlarmDetail {
  if (alarm.status === AlarmStatus.PENDING) {
    refreshPendingAlarmTimestamps()
  }
  const elder = eldersStore.find((e) => e.id === alarm.elderId) || eldersStore[0]
  const ev = eventsStore.find((e) => e.id === alarm.eventId) || eventsStore[0]
  const primary = elder.emergencyContact.find((c) => c.primary) || elder.emergencyContact[0] || null

  return {
    id: alarm.id,
    level: alarm.level,
    status: alarm.status,
    escalateStep: alarm.escalateStep,
    currentHandler: alarm.currentHandler,
    elder: {
      id: elder.id,
      name: elder.name,
      age: calcAge(elder.birthDate),
      roomNo: elder.roomNo,
      address: `${elder.address} ${elder.roomNo}`,
      phone: elder.phone,
      healthTags: elder.healthTags,
      primaryContact: primary
        ? { name: primary.name, phone: primary.phone, relation: primary.relation }
        : null,
    },
    event: {
      id: ev.id,
      type: ev.type,
      confidence: ev.confidence,
      occurredAt: ev.occurredAt,
      features: ev.features,
      snapshotUrl: ev.snapshotUrl,
      clipUrl: ev.clipUrl,
      algoVersion: ev.algoVersion,
    },
    notifiedAt: alarm.notifiedAt,
    ackAt: alarm.ackAt,
    resolvedAt: alarm.resolvedAt,
    responseSec: alarm.responseSec,
    actions: alarm.actions,
    timeline: buildAlarmTimeline(alarm, ev),
    remainingSec: calcRemainingSec(alarm),
  }
}

/** 构造老人详情（GET /elders/{id}） */
export function buildElderDetail(elder: ElderRecord): ElderDetail {
  const devices = devicesStore
    .filter((d) => d.elderId === elder.id)
    .map((d) => ({
      id: d.id,
      deviceNo: d.deviceNo,
      type: d.type,
      status: d.status,
      lastHeartbeat: d.lastHeartbeat,
      algoVersion: d.algoVersion,
    }))

  const recentEvents = eventsStore
    .filter((e) => e.elderId === elder.id)
    .slice(0, 5)
    .map(({ features: _f, algoVersion: _a, ...item }) => item)

  return {
    id: elder.id,
    name: elder.name,
    gender: elder.gender,
    age: calcAge(elder.birthDate),
    birthDate: elder.birthDate,
    phone: elder.rawPhone,
    address: elder.address,
    roomNo: elder.roomNo,
    communityId: elder.communityId,
    communityName: elder.communityName,
    guardianId: elder.guardianId,
    guardianName: elder.guardianName,
    healthTags: elder.healthTags,
    detectMode: elder.detectMode,
    status: elder.status,
    emergencyContact: elder.emergencyContact,
    devices,
    families: elder.families,
    recentEvents,
  }
}
