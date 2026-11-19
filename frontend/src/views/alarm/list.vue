<template>
  <div class="alarm-list-page">
    <!-- 顶部 3 个 StatCard：待处理 / 今日告警 / 平均响应时长（秒） -->
    <el-row :gutter="16" class="mb-16">
      <el-col :xs="24" :sm="8">
        <StatCard
          title="待处理告警"
          :value="stats?.pendingCount ?? alarmStore.pendingCount"
          unit="件"
          :value-color="(stats?.pendingCount ?? alarmStore.pendingCount) > 0 ? '#cf1322' : '#1f2329'"
          accent-color="#cf1322"
        />
      </el-col>
      <el-col :xs="24" :sm="8">
        <StatCard
          title="今日告警总数"
          :value="stats?.todayTotal ?? 0"
          unit="件"
          accent-color="#1677ff"
        />
      </el-col>
      <el-col :xs="24" :sm="8">
        <StatCard
          title="平均响应时长"
          :value="stats?.avgResponseSec ?? 0"
          unit="秒"
          accent-color="#52c41a"
        />
      </el-col>
    </el-row>

    <!-- 筛选区 -->
    <SearchForm :model-value="searchParams" @search="handleSearch" @reset="handleReset">
      <el-form-item label="级别">
        <el-select v-model="searchParams.level" placeholder="全部级别" clearable style="width: 130px">
          <el-option label="P0 紧急" :value="EventLevel.P0" />
          <el-option label="P1 重要" :value="EventLevel.P1" />
          <el-option label="P2 一般" :value="EventLevel.P2" />
        </el-select>
      </el-form-item>

      <el-form-item label="老人">
        <el-select
          v-model="searchParams.elderId"
          placeholder="搜索选择老人"
          filterable
          clearable
          style="width: 180px"
        >
          <el-option
            v-for="e in elderOptions"
            :key="e.id"
            :label="`${e.name}（${e.roomNo}）`"
            :value="e.id"
          />
        </el-select>
      </el-form-item>

      <el-form-item label="时间范围">
        <el-date-picker
          v-model="customDateRange"
          type="datetimerange"
          range-separator="至"
          start-placeholder="开始时间"
          end-placeholder="结束时间"
          format="YYYY-MM-DD HH:mm"
          style="width: 330px"
          clearable
          @change="onDateChange"
        />
      </el-form-item>
    </SearchForm>

    <!-- 主列表容器 -->
    <PageContainer title="告警处置中心">
      <template #extra>
        <!-- 非生产环境：答辩演示实时注入台（直接调 POST /events/mock 广播 ALARM_NEW） -->
        <div v-if="isNonProd" class="demo-toolbar">
          <span class="demo-toolbar__label">演示注入：</span>
          <el-button
            type="danger"
            size="small"
            :loading="injecting"
            @click="injectMockAlarm(1)"
          >
            模拟 P0 跌倒告警
          </el-button>
          <el-button
            type="warning"
            plain
            size="small"
            :loading="injecting"
            @click="injectMockAlarm(3)"
          >
            连发 3 条测试横幅排队
          </el-button>
        </div>
      </template>

      <!-- 状态 Tab：全部 / 待确认 / 已确认 / 已升级 / 已完结 -->
      <el-tabs v-model="activeStatusTab" class="alarm-status-tabs" @tab-change="onStatusTabChange">
        <el-tab-pane label="全部" name="ALL" />
        <el-tab-pane name="PENDING">
          <template #label>
            <span>待确认</span>
            <el-badge
              v-if="(stats?.pendingCount ?? alarmStore.pendingCount) > 0"
              :value="stats?.pendingCount ?? alarmStore.pendingCount"
              :max="99"
              type="danger"
              class="tab-badge"
            />
          </template>
        </el-tab-pane>
        <el-tab-pane label="已确认" name="ACKNOWLEDGED" />
        <el-tab-pane label="已升级" name="ESCALATED" />
        <el-tab-pane label="已完结" name="FINISHED" />
      </el-tabs>

      <!-- 表格列：级别 | 老人 | 房号 | 发生时间 | 状态 | 当前处理人 | 剩余升级倒计时 | 响应时长 | 操作 -->
      <ProTable
        ref="tableRef"
        :columns="columns"
        :request="fetchAlarms"
        :search-params="searchParams"
        :row-class-name="getRowClassName"
      >
        <!-- 级别 -->
        <template #level="{ row }">
          <StatusTag category="eventLevel" :status="row.level" />
        </template>

        <!-- 老人（点击跳老人档案详情） -->
        <template #elderName="{ row }">
          <el-link
            type="primary"
            :underline="false"
            class="elder-link"
            @click="router.push(`/elder/detail/${row.elderId}`)"
          >
            {{ row.elderName }}
          </el-link>
        </template>

        <!-- 发生时间 -->
        <template #createdAt="{ row }">
          <span class="mono-time">{{ formatTime(row.createdAt) }}</span>
        </template>

        <!-- 状态 -->
        <template #status="{ row }">
          <StatusTag category="alarmStatus" :status="row.status" />
        </template>

        <!-- 当前处理人 -->
        <template #currentHandler="{ row }">
          <span>{{ row.currentHandler || '-' }}</span>
          <el-tag
            v-if="row.escalateStep > 0"
            size="small"
            type="warning"
            effect="plain"
            class="ml-4"
          >
            升{{ row.escalateStep }}级
          </el-tag>
        </template>

        <!-- 剩余升级倒计时（仅 PENDING 行，格式 00:47，每秒更新） -->
        <template #countdown="{ row }">
          <template v-if="row.status === AlarmStatus.PENDING">
            <span
              class="countdown-pill"
              :class="{
                'is-urgent': (countdownMap[row.id] ?? 0) <= 15,
                'is-refreshing': refreshingIds.has(row.id),
              }"
            >
              <span class="countdown-pill__dot" />
              <span class="countdown-pill__text">
                {{ formatMMSS(countdownMap[row.id] ?? row.remainingSec ?? 0) }}
              </span>
            </span>
          </template>
          <span v-else class="text-muted">—</span>
        </template>

        <!-- 响应时长 -->
        <template #responseSec="{ row }">
          <span v-if="typeof row.responseSec === 'number'" class="mono-time">
            {{ row.responseSec }}s
          </span>
          <span v-else class="text-muted">—</span>
        </template>

        <!-- 操作：查看 / 确认（PENDING 时）/ 派单 / 完结 -->
        <template #actions="{ row }">
          <el-button link type="primary" size="small" @click="openDrawer(row.id)">
            查看
          </el-button>
          <el-button
            v-if="row.status === AlarmStatus.PENDING"
            link
            type="danger"
            size="small"
            @click="openAckDialog(row)"
          >
            确认
          </el-button>
          <el-button
            v-if="row.status === AlarmStatus.PENDING || row.status === AlarmStatus.ESCALATED"
            link
            type="warning"
            size="small"
            @click="openDispatchDialog(row)"
          >
            派单
          </el-button>
          <el-button
            v-if="
              row.status === AlarmStatus.ACKNOWLEDGED ||
              row.status === AlarmStatus.COMMUNITY_DISPATCHED
            "
            link
            type="success"
            size="small"
            @click="openResolveDialog(row, EventHandleResult.TRUE_FALL)"
          >
            完结
          </el-button>
        </template>
      </ProTable>
    </PageContainer>

    <!-- 告警详情抽屉（el-drawer，宽度 720px） -->
    <AlarmDetailDrawer
      v-model="drawerVisible"
      :loading="drawerLoading"
      :detail="drawerDetail"
      :countdown-sec="drawerCountdownSec"
      @request-ack="onDrawerRequestAck"
      @request-dispatch="onDrawerRequestDispatch"
      @request-resolve="onDrawerRequestResolve"
    />

    <!-- 确认 / 派单 / 完结弹窗 -->
    <AlarmActionDialogs
      v-model:ack-visible="ackDialogVisible"
      v-model:dispatch-visible="dispatchDialogVisible"
      v-model:resolve-visible="resolveDialogVisible"
      :target-alarm="dialogTarget"
      :default-resolve-result="defaultResolveResult"
      @success="onActionSuccess"
    />
  </div>
</template>

<script setup lang="ts">
/**
 * 告警列表 /alarm/list —— 阶段 F6 答辩演示核心页
 *
 * 关键实现：
 * 1. 倒计时：以接口或 WS 返回的 remainingSec 为初值写入 countdownMap，
 *    页面级单一 setInterval(1000) 统一递减；绝不用本地时间戳反推。
 * 2. 倒计时归零：触发 refreshSingleAlarm(id) 重新请求 GET /alarms/{id}，
 *    同步更新列表行与抽屉详情（若后端已升级则状态自动切为 ESCALATED）。
 * 3. PENDING 且 P0 行脉动红边：通过 computed 预选当前页前 5 条符合条件的行 ID，
 *    最多 5 个同时加 CSS animation，超出不加动画，避免性能卡顿。
 * 4. 全局 WS 联动：订阅 alarmStore.onAlarmEvent，ALARM_NEW 实时插入列表顶部，
 *    ALARM_UPDATE 实时更新对应行状态。
 */
import dayjs from 'dayjs'
import { getAlarmDetail, getAlarmList, getAlarmStats } from '@/api/alarm'
import { getElderList } from '@/api/elder'
import { createMockEvent } from '@/api/event'
import PageContainer from '@/components/PageContainer.vue'
import ProTable, { type ProTableColumn, type ProTableInstance } from '@/components/ProTable.vue'
import SearchForm from '@/components/SearchForm.vue'
import StatCard from '@/components/StatCard.vue'
import StatusTag from '@/components/StatusTag.vue'
import { useAlarmStore } from '@/stores/alarm'
import {
  AlarmStatus,
  type AlarmDetail,
  type AlarmItem,
  type AlarmQuery,
  type AlarmStats,
  type WsAlarmNewPayload,
  type WsAlarmUpdatePayload,
} from '@/types/alarm'
import type { Elder } from '@/types/elder'
import { EventHandleResult, EventLevel, EventType, StatsRange } from '@/types/event'
import AlarmActionDialogs, { type AlarmDialogTarget } from './components/AlarmActionDialogs.vue'
import AlarmDetailDrawer from './components/AlarmDetailDrawer.vue'

const MAX_PULSING_P0_ROWS = 5

const route = useRoute()
const router = useRouter()
const alarmStore = useAlarmStore()
const tableRef = ref<ProTableInstance<AlarmItem>>()

const isNonProd = import.meta.env.MODE !== 'production' || import.meta.env.VITE_USE_MOCK === 'true'

// ---------------- 顶部统计卡 ----------------
const stats = ref<AlarmStats | null>(null)

async function loadStats() {
  stats.value = await getAlarmStats(StatsRange.TODAY)
}

// ---------------- 老人下拉选项 ----------------
const elderOptions = ref<Elder[]>([])

async function loadElders() {
  const res = await getElderList({ page: 1, pageSize: 100 }).catch(() => null)
  elderOptions.value = res?.list || []
}

// ---------------- 状态 Tab 与筛选参数 ----------------
type StatusTabName = 'ALL' | 'PENDING' | 'ACKNOWLEDGED' | 'ESCALATED' | 'FINISHED'
const activeStatusTab = ref<StatusTabName>('ALL')
const customDateRange = ref<[Date, Date] | null>(null)

const searchParams = reactive({
  status: '',
  level: '' as EventLevel | '',
  elderId: '',
  startTime: '',
  endTime: '',
})

function onStatusTabChange(tab: string | number) {
  const name = String(tab) as StatusTabName
  if (name === 'ALL') {
    searchParams.status = ''
  } else if (name === 'FINISHED') {
    searchParams.status = `${AlarmStatus.RESOLVED},${AlarmStatus.FALSE_POSITIVE}`
  } else {
    searchParams.status = name
  }
}

function onDateChange(val: [Date, Date] | null) {
  if (!val || val.length !== 2) {
    searchParams.startTime = ''
    searchParams.endTime = ''
    return
  }
  searchParams.startTime = dayjs(val[0]).format('YYYY-MM-DDTHH:mm:ss+08:00')
  searchParams.endTime = dayjs(val[1]).format('YYYY-MM-DDTHH:mm:ss+08:00')
}

function handleSearch() {
  tableRef.value?.reload(true)
}

function handleReset() {
  activeStatusTab.value = 'ALL'
  customDateRange.value = null
  searchParams.status = ''
  searchParams.level = ''
  searchParams.elderId = ''
  searchParams.startTime = ''
  searchParams.endTime = ''
  tableRef.value?.reload(true)
}

// ---------------- 表格列定义 ----------------
const columns: ProTableColumn<AlarmItem>[] = [
  { prop: 'level', label: '级别', width: 96, align: 'center', slot: 'level' },
  { prop: 'elderName', label: '老人', width: 96, slot: 'elderName' },
  { prop: 'roomNo', label: '房号', width: 76, align: 'center' },
  { prop: 'createdAt', label: '发生时间', width: 145, slot: 'createdAt' },
  { prop: 'status', label: '状态', width: 96, align: 'center', slot: 'status' },
  { prop: 'currentHandler', label: '当前处理人', minWidth: 120, slot: 'currentHandler' },
  {
    prop: 'remainingSec',
    label: '剩余升级倒计时',
    width: 136,
    align: 'center',
    slot: 'countdown',
    showOverflowTooltip: false,
  },
  { prop: 'responseSec', label: '响应时长', width: 92, align: 'center', slot: 'responseSec' },
  { label: '操作', width: 175, fixed: 'right', slot: 'actions', showOverflowTooltip: false },
]

// ---------------- 倒计时状态机（以 remainingSec 为初值，本地 setInterval 递减） ----------------
const countdownMap = reactive<Record<string, number>>({})
const refreshingIds = reactive(new Set<string>())
let countdownTimer: ReturnType<typeof setInterval> | null = null

/** 用后端返回的 remainingSec 初始化/重置倒计时 */
function seedRowCountdown(id: string, status: AlarmStatus, remainingSec?: number | null) {
  if (status !== AlarmStatus.PENDING) {
    delete countdownMap[id]
    return
  }
  const initSec =
    typeof remainingSec === 'number' && remainingSec >= 0 ? Math.floor(remainingSec) : 60
  countdownMap[id] = initSec
}

async function fetchAlarms(params: Record<string, unknown>) {
  const res = await getAlarmList(params as AlarmQuery)
  for (const item of res.list) {
    seedRowCountdown(item.id, item.status, item.remainingSec)
  }
  return res
}

/**
 * 倒计时归零时重新请求该行（GET /alarms/{id}）：
 * - 若后端已升级（status 变为 ESCALATED），更新列表行状态、处理人、升级步数并移除倒计时
 * - 若后端仍在 PENDING 且返回新的 remainingSec，则按后端新值继续倒计时
 * - 若详情抽屉正打开同一条告警，同步更新抽屉数据
 */
async function refreshSingleAlarm(alarmId: string) {
  if (refreshingIds.has(alarmId)) return
  refreshingIds.add(alarmId)
  try {
    const detail = await getAlarmDetail(alarmId)
    applyDetailToRow(detail)
    if (drawerVisible.value && drawerDetail.value?.id === alarmId) {
      drawerDetail.value = detail
    }
    await Promise.all([loadStats(), alarmStore.syncPendingCount()])
  } catch {
    // 忽略单行刷新异常
  } finally {
    refreshingIds.delete(alarmId)
  }
}

function applyDetailToRow(detail: AlarmDetail) {
  const rows = tableRef.value?.tableData
  if (rows) {
    const idx = rows.findIndex((r) => r.id === detail.id)
    if (idx >= 0) {
      rows[idx] = {
        ...rows[idx],
        level: detail.level,
        status: detail.status,
        currentHandler: detail.currentHandler,
        escalateStep: detail.escalateStep,
        ackAt: detail.ackAt,
        resolvedAt: detail.resolvedAt,
        responseSec: detail.responseSec,
        remainingSec: detail.remainingSec,
      }
    }
  }
  if (detail.status === AlarmStatus.PENDING) {
    // 若归零重拉时后端因毫厘之差仍返回 0，给 2 秒缓冲后再次重拉
    countdownMap[detail.id] =
      typeof detail.remainingSec === 'number' && detail.remainingSec > 0
        ? Math.floor(detail.remainingSec)
        : 2
  } else {
    delete countdownMap[detail.id]
  }
}

function startCountdownLoop() {
  stopCountdownLoop()
  countdownTimer = setInterval(() => {
    const expiredIds: string[] = []
    for (const id of Object.keys(countdownMap)) {
      const cur = countdownMap[id]
      if (typeof cur !== 'number') continue
      if (cur > 1) {
        countdownMap[id] = cur - 1
      } else {
        countdownMap[id] = 0
        expiredIds.push(id)
      }
    }
    for (const id of expiredIds) {
      refreshSingleAlarm(id)
    }
  }, 1000)
}

function stopCountdownLoop() {
  if (countdownTimer) {
    clearInterval(countdownTimer)
    countdownTimer = null
  }
}

// ---------------- PENDING 且 P0 行脉动红边（严格限制最多 5 个同时加动画） ----------------
const animatedP0RowIdSet = computed<Set<string>>(() => {
  const rows = tableRef.value?.tableData ?? []
  const set = new Set<string>()
  for (const row of rows) {
    if (row.status === AlarmStatus.PENDING && row.level === EventLevel.P0) {
      set.add(row.id)
      if (set.size >= MAX_PULSING_P0_ROWS) break
    }
  }
  return set
})

function getRowClassName({ row }: { row: AlarmItem }): string {
  if (row.status === AlarmStatus.PENDING && row.level === EventLevel.P0) {
    return animatedP0RowIdSet.value.has(row.id)
      ? 'is-p0-pending-pulse'
      : 'is-p0-pending-static'
  }
  return ''
}

// ---------------- 实时 WS 分发联动：ALARM_NEW 插顶 & ALARM_UPDATE 更新 ----------------
function matchesCurrentFilter(item: AlarmItem): boolean {
  if (searchParams.status) {
    const allowed = searchParams.status.split(',')
    if (!allowed.includes(item.status)) return false
  }
  if (searchParams.level && item.level !== searchParams.level) return false
  if (searchParams.elderId && item.elderId !== searchParams.elderId) return false
  return true
}

function handleWsNewAlarm(payload: WsAlarmNewPayload, ts: string) {
  const newItem: AlarmItem = {
    id: payload.alarmId,
    level: payload.level,
    status: AlarmStatus.PENDING,
    elderId: payload.elderId,
    elderName: payload.elderName,
    roomNo: payload.roomNo,
    communityName: payload.communityName,
    currentHandler: '家属主联系人',
    escalateStep: 0,
    createdAt: ts || payload.occurredAt,
    notifiedAt: ts || payload.occurredAt,
    ackAt: null,
    resolvedAt: null,
    responseSec: null,
    eventType: payload.eventType,
    confidence: payload.confidence,
    snapshotUrl: payload.snapshotUrl,
    remainingSec: payload.remainingSec,
  }

  seedRowCountdown(newItem.id, newItem.status, newItem.remainingSec)

  const rows = tableRef.value?.tableData
  if (rows && matchesCurrentFilter(newItem)) {
    const existsIdx = rows.findIndex((r) => r.id === newItem.id)
    if (existsIdx >= 0) {
      rows.splice(existsIdx, 1)
    }
    rows.unshift(newItem)
    if (tableRef.value) {
      tableRef.value.total += existsIdx >= 0 ? 0 : 1
    }
  }
  loadStats()
}

function handleWsUpdateAlarm(payload: WsAlarmUpdatePayload) {
  const rows = tableRef.value?.tableData
  if (rows) {
    const row = rows.find((r) => r.id === payload.alarmId)
    if (row) {
      row.status = payload.status
      row.escalateStep = payload.escalateStep
      row.currentHandler = payload.currentHandler
    }
  }
  if (payload.status !== AlarmStatus.PENDING) {
    delete countdownMap[payload.alarmId]
  }
  if (drawerVisible.value && drawerDetail.value?.id === payload.alarmId) {
    getAlarmDetail(payload.alarmId)
      .then((d) => {
        drawerDetail.value = d
      })
      .catch(() => undefined)
  }
  loadStats()
}

// ---------------- 详情抽屉 ----------------
const drawerVisible = ref(false)
const drawerLoading = ref(false)
const drawerDetail = ref<AlarmDetail | null>(null)

const drawerCountdownSec = computed<number | null>(() => {
  const d = drawerDetail.value
  if (!d || d.status !== AlarmStatus.PENDING) return null
  if (typeof countdownMap[d.id] === 'number') return countdownMap[d.id]
  return d.remainingSec
})

async function openDrawer(alarmId: string) {
  drawerVisible.value = true
  drawerLoading.value = true
  try {
    const detail = await getAlarmDetail(alarmId)
    drawerDetail.value = detail
    seedRowCountdown(detail.id, detail.status, detail.remainingSec)
  } finally {
    drawerLoading.value = false
  }
}

// ---------------- 确认 / 派单 / 完结弹窗 ----------------
const dialogTarget = ref<AlarmDialogTarget | null>(null)
const ackDialogVisible = ref(false)
const dispatchDialogVisible = ref(false)
const resolveDialogVisible = ref(false)
const defaultResolveResult = ref<EventHandleResult>(EventHandleResult.TRUE_FALL)

function toTarget(row: {
  id: string
  level: EventLevel
  elderName: string
  roomNo: string
}): AlarmDialogTarget {
  return {
    id: row.id,
    level: row.level,
    elderName: row.elderName,
    roomNo: row.roomNo,
  }
}

function openAckDialog(row: AlarmItem) {
  dialogTarget.value = toTarget(row)
  ackDialogVisible.value = true
}

function openDispatchDialog(row: AlarmItem) {
  dialogTarget.value = toTarget(row)
  dispatchDialogVisible.value = true
}

function openResolveDialog(row: AlarmItem, result: EventHandleResult) {
  dialogTarget.value = toTarget(row)
  defaultResolveResult.value = result
  resolveDialogVisible.value = true
}

function onDrawerRequestAck(d: AlarmDetail) {
  dialogTarget.value = {
    id: d.id,
    level: d.level,
    elderName: d.elder.name,
    roomNo: d.elder.roomNo,
  }
  ackDialogVisible.value = true
}

function onDrawerRequestDispatch(d: AlarmDetail) {
  dialogTarget.value = {
    id: d.id,
    level: d.level,
    elderName: d.elder.name,
    roomNo: d.elder.roomNo,
  }
  dispatchDialogVisible.value = true
}

function onDrawerRequestResolve(d: AlarmDetail, result: EventHandleResult) {
  dialogTarget.value = {
    id: d.id,
    level: d.level,
    elderName: d.elder.name,
    roomNo: d.elder.roomNo,
  }
  defaultResolveResult.value = result
  resolveDialogVisible.value = true
}

async function onActionSuccess(updatedDetail: AlarmDetail) {
  applyDetailToRow(updatedDetail)
  if (drawerVisible.value && drawerDetail.value?.id === updatedDetail.id) {
    drawerDetail.value = updatedDetail
  }
  await Promise.all([loadStats(), alarmStore.syncPendingCount()])
}

// ---------------- 演示注入：POST /events/mock ----------------
const injecting = ref(false)

async function injectMockAlarm(count = 1) {
  if (injecting.value) return
  injecting.value = true
  try {
    for (let i = 0; i < count; i++) {
      await createMockEvent({
        elderId: '',
        type: EventType.FALL,
        level: EventLevel.P0,
        confidence: Number((0.91 + Math.random() * 0.07).toFixed(2)),
      })
    }
  } finally {
    injecting.value = false
  }
}

// ---------------- 横幅「去看看」query.inspect 自动打开对应详情抽屉 ----------------
watch(
  () => route.query.inspect,
  (inspectId) => {
    if (typeof inspectId === 'string' && inspectId) {
      openDrawer(inspectId)
      router.replace({ path: route.path, query: { ...route.query, inspect: undefined } })
    }
  },
  { immediate: true },
)

// ---------------- 工具函数 ----------------
function formatMMSS(sec: number): string {
  const safe = Math.max(0, Math.floor(sec))
  const mm = String(Math.floor(safe / 60)).padStart(2, '0')
  const ss = String(safe % 60).padStart(2, '0')
  return `${mm}:${ss}`
}

function formatTime(ts?: string | null): string {
  if (!ts) return '-'
  const d = dayjs(ts)
  return d.isValid() ? d.format('MM-DD HH:mm:ss') : '-'
}

let offBus: (() => void) | null = null

onMounted(() => {
  loadStats()
  loadElders()
  startCountdownLoop()
  offBus = alarmStore.onAlarmEvent((evt) => {
    if (evt.type === 'new') {
      handleWsNewAlarm(evt.payload, evt.ts)
    } else if (evt.type === 'update') {
      handleWsUpdateAlarm(evt.payload)
    }
  })
})

onBeforeUnmount(() => {
  stopCountdownLoop()
  offBus?.()
})
</script>

<style scoped lang="scss">
.demo-toolbar {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 4px 10px;
  background: #fff2f0;
  border: 1px dashed #ffa39e;
  border-radius: 6px;

  &__label {
    font-size: 12px;
    font-weight: 600;
    color: #cf1322;
  }
}

.alarm-status-tabs {
  margin-bottom: 12px;

  :deep(.el-tabs__header) {
    margin-bottom: 4px;
  }
}

.tab-badge {
  margin-left: 6px;
  vertical-align: middle;
}

.mono-time {
  font-family: monospace;
  font-size: 13px;
}

.elder-link {
  font-weight: 600;
}

.ml-4 {
  margin-left: 6px;
}

.text-muted {
  color: $text-disabled;
}

/* 倒计时胶囊 */
.countdown-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 2px 10px;
  font-family: monospace;
  font-size: 13px;
  font-weight: 700;
  color: #d46b08;
  background: #fff7e6;
  border: 1px solid #ffd591;
  border-radius: 12px;

  &__dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: #fa8c16;
    animation: dot-blink 1s ease-in-out infinite;
  }

  &.is-urgent {
    color: #cf1322;
    background: #fff1f0;
    border-color: #ffa39e;

    .countdown-pill__dot {
      background: #cf1322;
    }
  }

  &.is-refreshing {
    opacity: 0.65;
  }
}

/* PENDING 且 P0 行：前 5 条整行脉动红边（CSS animation） */
:deep(.el-table .is-p0-pending-pulse) {
  --el-table-tr-bg-color: #fff2f0;
  background-color: #fff2f0 !important;
  animation: p0-row-pulse 1.8s ease-in-out infinite;

  td.el-table__cell {
    background-color: #fff2f0 !important;
    border-top: 1px solid rgba(207, 19, 34, 0.45);
    border-bottom: 1px solid rgba(207, 19, 34, 0.45);
    animation: p0-cell-pulse 1.8s ease-in-out infinite;
  }

  td.el-table__cell:first-child {
    border-left: 4px solid #cf1322;
  }

  td.el-table__cell:last-child {
    border-right: 2px solid rgba(207, 19, 34, 0.55);
  }
}

/* 超出 5 条上限的 PENDING+P0 行：保留静态红边与浅红底，不加动画避免性能问题 */
:deep(.el-table .is-p0-pending-static) {
  --el-table-tr-bg-color: #fff2f0;
  background-color: #fff2f0 !important;

  td.el-table__cell {
    background-color: #fff2f0 !important;
  }

  td.el-table__cell:first-child {
    border-left: 4px solid #cf1322;
  }
}

@keyframes p0-row-pulse {
  0%,
  100% {
    box-shadow: inset 0 0 0 1px rgba(207, 19, 34, 0.28);
  }
  50% {
    box-shadow:
      inset 0 0 0 2px rgba(207, 19, 34, 0.88),
      0 0 10px rgba(207, 19, 34, 0.18);
  }
}

@keyframes p0-cell-pulse {
  0%,
  100% {
    background-color: #fff2f0;
  }
  50% {
    background-color: #ffe3e0;
  }
}

@keyframes dot-blink {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.25;
  }
}
</style>
