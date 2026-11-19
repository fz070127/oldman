<template>
  <div class="dashboard-page">
    <!-- 顶部 4 个核心 KPI 统计卡片（数据来自 GET /dashboard/overview） -->
    <div v-if="overviewError" class="section-error-bar mb-16">
      <span>工作台 KPI 概览加载失败，请检查网络连接</span>
      <el-button type="danger" plain size="small" @click="loadOverview">
        加载失败，点击重试
      </el-button>
    </div>

    <el-row :gutter="16" class="mb-16">
      <template v-if="overviewLoading && !overview">
        <el-col v-for="idx in 4" :key="idx" :xs="24" :sm="12" :md="6">
          <div class="kpi-skeleton-card">
            <el-skeleton :rows="2" animated />
          </div>
        </el-col>
      </template>
      <template v-else>
        <el-col :xs="24" :sm="12" :md="6">
          <StatCard
            title="今日告警"
            :value="overview?.alarmToday ?? 0"
            unit="件"
            :trend-label="`今日 P0 紧急：${overview?.alarmP0Today ?? 0} 件`"
            accent-color="#1677ff"
          />
        </el-col>
        <el-col :xs="24" :sm="12" :md="6">
          <StatCard
            title="待处理"
            :value="overview?.alarmPending ?? 0"
            unit="件"
            :value-color="(overview?.alarmPending ?? 0) > 0 ? '#cf1322' : '#1f2329'"
            :trend-label="`在册老人：${overview?.elderOnline ?? 0} / ${overview?.elderTotal ?? 0} 在线`"
            accent-color="#cf1322"
          />
        </el-col>
        <el-col :xs="24" :sm="12" :md="6">
          <StatCard
            title="设备在线率"
            :value="deviceOnlineRateText"
            unit="%"
            value-color="#237804"
            :trend-label="`在线 ${overview?.deviceOnline ?? 0} / 共 ${overview?.deviceTotal ?? 0} 台`"
            accent-color="#52c41a"
          />
        </el-col>
        <el-col :xs="24" :sm="12" :md="6">
          <StatCard
            title="平均响应时长"
            :value="overview?.avgResponseSec ?? 0"
            unit="秒"
            :trend-label="`综合误报率：${((overview?.falsePositiveRate ?? 0) * 100).toFixed(1)}%`"
            accent-color="#faad14"
          />
        </el-col>
      </template>
    </el-row>

    <!-- 中部：左近 7 天告警趋势折线图 + 右最近告警列表（10 条） -->
    <el-row :gutter="16" class="mb-16">
      <!-- 左侧：近 7 天告警趋势折线（GET /dashboard/trend?days=7） -->
      <el-col :xs="24" :lg="12">
        <PageContainer title="近 7 天告警趋势" class="dashboard-panel">
          <template #extra>
            <div class="panel-extra">
              <el-tag size="small" type="info" effect="plain">
                近 7 日共 {{ trendTotalCount }} 件
              </el-tag>
              <el-button link type="primary" size="small" @click="router.push('/screen')">
                打开社区大屏 &rarr;
              </el-button>
            </div>
          </template>

          <div v-if="trendLoading && trendList.length === 0" class="panel-skeleton">
            <el-skeleton :rows="7" animated />
          </div>
          <EmptyState
            v-else-if="trendError"
            mode="error"
            title="趋势图加载失败"
            description="无法获取近 7 天告警趋势数据，请检查网络连接后重试"
            action-text="加载失败，点击重试"
            @action="loadTrend"
          />
          <EmptyState
            v-else-if="trendList.length === 0"
            mode="empty"
            title="暂无趋势数据"
            description="近期暂无告警统计数据"
            action-text="刷新重试"
            @action="loadTrend"
          />
          <DashboardTrendChart v-else :list="trendList" />
        </PageContainer>
      </el-col>

      <!-- 右侧：最近告警列表（10 条，点击跳 /alarm/list 或直接开详情抽屉） -->
      <el-col :xs="24" :lg="12">
        <PageContainer title="最近告警列表（近 10 条）" class="dashboard-panel">
          <template #extra>
            <el-button link type="primary" size="small" @click="router.push('/alarm')">
              全部告警 &rarr;
            </el-button>
          </template>

          <div v-if="alarmsLoading && recentAlarms.length === 0" class="panel-skeleton">
            <el-skeleton :rows="7" animated />
          </div>
          <EmptyState
            v-else-if="alarmsError"
            mode="error"
            title="最近告警加载失败"
            description="无法获取最近告警记录，请检查网络或服务状态"
            action-text="加载失败，点击重试"
            @action="loadRecentAlarms"
          />
          <EmptyState
            v-else-if="recentAlarms.length === 0"
            mode="empty"
            title="暂无告警记录"
            description="当前辖区内老人一切平安，暂无告警触发"
            action-text="刷新列表"
            @action="loadRecentAlarms"
          />
          <el-table
            v-else
            :data="recentAlarms"
            row-key="id"
            size="small"
            height="360"
            style="width: 100%"
            class="clickable-table"
            @row-click="onRecentRowClick"
          >
            <el-table-column prop="level" label="级别" width="90" align="center">
              <template #default="{ row }">
                <StatusTag category="eventLevel" :status="row.level" />
              </template>
            </el-table-column>

            <el-table-column
              prop="elderName"
              label="老人 / 房号"
              min-width="135"
              show-overflow-tooltip
            >
              <template #default="{ row }">
                <span class="elder-cell-name">{{ row.elderName }}</span>
                <span class="elder-cell-room">（{{ row.roomNo }}室）</span>
              </template>
            </el-table-column>

            <el-table-column
              prop="communityName"
              label="所属社区"
              min-width="115"
              show-overflow-tooltip
            />

            <el-table-column prop="createdAt" label="发生时间" width="135">
              <template #default="{ row }">
                <span class="mono-time">{{ formatShortTime(row.createdAt) }}</span>
              </template>
            </el-table-column>

            <el-table-column prop="status" label="状态" width="88" align="center">
              <template #default="{ row }">
                <StatusTag category="alarmStatus" :status="row.status" />
              </template>
            </el-table-column>

            <el-table-column label="操作" width="115" fixed="right" align="center">
              <template #default="{ row }">
                <el-button link type="primary" size="small" @click.stop="openAlarmDrawer(row.id)">
                  详情
                </el-button>
                <el-button link type="primary" size="small" @click.stop="router.push('/alarm')">
                  去处理
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </PageContainer>
      </el-col>
    </el-row>

    <!-- 底部：设备离线清单（GET /dashboard/device-status 的 offlineList） -->
    <PageContainer title="设备离线与异常清单">
      <template #extra>
        <div class="device-summary-bar">
          <el-tag size="small" type="success" effect="plain">
            在线 {{ deviceStatus?.online ?? 0 }} 台
          </el-tag>
          <el-tag size="small" type="danger" effect="plain">
            离线 {{ deviceStatus?.offline ?? 0 }} 台
          </el-tag>
          <el-tag size="small" type="warning" effect="plain">
            故障 {{ deviceStatus?.fault ?? 0 }} 台
          </el-tag>
          <el-tag size="small" type="info" effect="plain">
            未激活 {{ deviceStatus?.inactive ?? 0 }} 台
          </el-tag>
          <el-button link type="primary" size="small" @click="router.push('/device')">
            设备管理 &rarr;
          </el-button>
        </div>
      </template>

      <div v-if="deviceLoading && !deviceStatus" class="panel-skeleton">
        <el-skeleton :rows="5" animated />
      </div>
      <EmptyState
        v-else-if="deviceError"
        mode="error"
        title="设备状态清单加载失败"
        description="无法获取离线设备清单，请检查网络连接后重试"
        action-text="加载失败，点击重试"
        @action="loadDeviceStatus"
      />
      <EmptyState
        v-else-if="!offlineDevices.length"
        mode="empty"
        title="全部监测设备均在线运行"
        description="当前辖区内所有绑定设备心跳正常，无离线或故障设备"
        action-text="刷新状态"
        @action="loadDeviceStatus"
      />
      <el-table
        v-else
        :data="offlineDevices"
        row-key="id"
        style="width: 100%"
      >
        <el-table-column prop="deviceNo" label="设备号" width="150" show-overflow-tooltip>
          <template #default="{ row }">
            <el-link
              type="primary"
              :underline="false"
              class="mono-link"
              @click="router.push(`/device/detail/${row.id}`)"
            >
              {{ row.deviceNo }}
            </el-link>
          </template>
        </el-table-column>

        <el-table-column prop="elderName" label="绑定老人" width="130" show-overflow-tooltip>
          <template #default="{ row }">
            <el-link
              v-if="row.elderId && row.elderName"
              type="primary"
              :underline="false"
              @click="router.push(`/elder/detail/${row.elderId}`)"
            >
              {{ row.elderName }}
            </el-link>
            <span v-else class="text-disabled">未绑定</span>
          </template>
        </el-table-column>

        <el-table-column prop="communityName" label="所属社区" min-width="150" show-overflow-tooltip>
          <template #default="{ row }">
            <span>{{ row.communityName || '-' }}</span>
          </template>
        </el-table-column>

        <el-table-column prop="roomNo" label="房号" width="110" show-overflow-tooltip>
          <template #default="{ row }">
            <span>{{ row.roomNo ? `${row.roomNo}室` : '-' }}</span>
          </template>
        </el-table-column>

        <el-table-column prop="status" label="设备状态" width="110" align="center">
          <template #default="{ row }">
            <StatusTag category="deviceStatus" :status="row.status" />
          </template>
        </el-table-column>

        <el-table-column prop="lastHeartbeat" label="最后心跳时间" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">
            <span>{{ formatRelativeTime(row.lastHeartbeat) }}</span>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="160" fixed="right" align="center">
          <template #default="{ row }">
            <el-button
              link
              type="primary"
              size="small"
              @click="router.push(`/device/detail/${row.id}`)"
            >
              查看设备
            </el-button>
            <el-button
              v-if="row.elderId"
              link
              type="primary"
              size="small"
              @click="router.push(`/elder/detail/${row.elderId}`)"
            >
              老人档案
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </PageContainer>

    <!-- 告警详情抽屉（直接复用 F6 的 AlarmDetailDrawer 与处置弹窗） -->
    <AlarmDetailDrawer
      v-model="drawerVisible"
      :loading="drawerLoading"
      :detail="drawerDetail"
      :countdown-sec="drawerDetail?.remainingSec ?? null"
      @request-ack="onDrawerRequestAck"
      @request-dispatch="onDrawerRequestDispatch"
      @request-resolve="onDrawerRequestResolve"
    />

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
 * 工作台页面 /dashboard —— 登录后默认落地页（阶段 F9 核心）
 * - 顶部 4 个 KPI（今日告警 / 待处理 / 设备在线率 / 平均响应时长），来自 GET /dashboard/overview
 * - 左侧近 7 天告警趋势折线图（GET /dashboard/trend?days=7），用 defineAsyncComponent + 按需 ECharts
 * - 右侧最近告警列表（10 条，点击直接开详情抽屉或跳 /alarm/list）
 * - 底部设备离线清单（GET /dashboard/device-status 的 offlineList）
 */
import { defineAsyncComponent } from 'vue'
import dayjs from 'dayjs'
import { getAlarmDetail, getAlarmList } from '@/api/alarm'
import {
  getDashboardDeviceStatus,
  getDashboardOverview,
  getDashboardTrend,
} from '@/api/dashboard'
import EmptyState from '@/components/EmptyState.vue'
import PageContainer from '@/components/PageContainer.vue'
import StatCard from '@/components/StatCard.vue'
import StatusTag from '@/components/StatusTag.vue'
import { useAlarmStore } from '@/stores/alarm'
import type { AlarmDetail, AlarmItem } from '@/types/alarm'
import type {
  DashboardDeviceStatus,
  DashboardOverview,
  OfflineDeviceItem,
  TrendItem,
} from '@/types/dashboard'
import { EventHandleResult } from '@/types/event'
import { formatRelativeTime } from '@/utils/time'
import AlarmActionDialogs, {
  type AlarmDialogTarget,
} from '@/views/alarm/components/AlarmActionDialogs.vue'
import AlarmDetailDrawer from '@/views/alarm/components/AlarmDetailDrawer.vue'

const DashboardTrendChart = defineAsyncComponent(
  () => import('./components/DashboardTrendChart.vue'),
)

const router = useRouter()
const alarmStore = useAlarmStore()

// ---------------- 1. 顶部 KPI 概览 ----------------
const overview = ref<DashboardOverview | null>(null)
const overviewLoading = ref(false)
const overviewError = ref(false)

const deviceOnlineRateText = computed(() => {
  const total = overview.value?.deviceTotal ?? 0
  const online = overview.value?.deviceOnline ?? 0
  if (!total) return '0.0'
  return ((online / total) * 100).toFixed(1)
})

async function loadOverview() {
  overviewLoading.value = true
  overviewError.value = false
  try {
    overview.value = await getDashboardOverview()
  } catch {
    overviewError.value = true
  } finally {
    overviewLoading.value = false
  }
}

// ---------------- 2. 左侧近 7 天告警趋势 ----------------
const trendList = ref<TrendItem[]>([])
const trendLoading = ref(false)
const trendError = ref(false)

const trendTotalCount = computed(() =>
  trendList.value.reduce((sum, item) => sum + (item.total || 0), 0),
)

async function loadTrend() {
  trendLoading.value = true
  trendError.value = false
  try {
    const res = await getDashboardTrend(7)
    trendList.value = res?.list ?? []
  } catch {
    trendError.value = true
  } finally {
    trendLoading.value = false
  }
}

// ---------------- 3. 右侧最近 10 条告警 ----------------
const recentAlarms = ref<AlarmItem[]>([])
const alarmsLoading = ref(false)
const alarmsError = ref(false)

async function loadRecentAlarms() {
  alarmsLoading.value = true
  alarmsError.value = false
  try {
    const res = await getAlarmList({ page: 1, pageSize: 10 })
    recentAlarms.value = (res?.list ?? []).slice(0, 10)
  } catch {
    alarmsError.value = true
  } finally {
    alarmsLoading.value = false
  }
}

function formatShortTime(ts?: string | null): string {
  if (!ts) return '-'
  const d = dayjs(ts)
  return d.isValid() ? d.format('MM-DD HH:mm:ss') : '-'
}

// ---------------- 4. 底部设备离线清单 ----------------
const deviceStatus = ref<DashboardDeviceStatus | null>(null)
const deviceLoading = ref(false)
const deviceError = ref(false)

const offlineDevices = computed<OfflineDeviceItem[]>(() => deviceStatus.value?.offlineList ?? [])

async function loadDeviceStatus() {
  deviceLoading.value = true
  deviceError.value = false
  try {
    deviceStatus.value = await getDashboardDeviceStatus()
  } catch {
    deviceError.value = true
  } finally {
    deviceLoading.value = false
  }
}

// ---------------- 5. 告警详情抽屉与处置弹窗 ----------------
const drawerVisible = ref(false)
const drawerLoading = ref(false)
const drawerDetail = ref<AlarmDetail | null>(null)

const dialogTarget = ref<AlarmDialogTarget | null>(null)
const ackDialogVisible = ref(false)
const dispatchDialogVisible = ref(false)
const resolveDialogVisible = ref(false)
const defaultResolveResult = ref<EventHandleResult>(EventHandleResult.TRUE_FALL)

function onRecentRowClick(row: AlarmItem) {
  openAlarmDrawer(row.id)
}

async function openAlarmDrawer(id: string) {
  drawerVisible.value = true
  drawerLoading.value = true
  try {
    drawerDetail.value = await getAlarmDetail(id)
  } finally {
    drawerLoading.value = false
  }
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

async function onActionSuccess(updated: AlarmDetail) {
  drawerDetail.value = updated
  await Promise.all([loadOverview(), loadRecentAlarms(), alarmStore.syncPendingCount()])
}

function loadAllDashboardData() {
  loadOverview()
  loadTrend()
  loadRecentAlarms()
  loadDeviceStatus()
}

let offBus: (() => void) | null = null

onMounted(() => {
  loadAllDashboardData()
  offBus = alarmStore.onAlarmEvent(() => {
    loadOverview()
    loadTrend()
    loadRecentAlarms()
  })
})

onBeforeUnmount(() => {
  offBus?.()
})
</script>

<style scoped lang="scss">
.section-error-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  font-size: 13px;
  color: $color-danger;
  background: #fff1f0;
  border: 1px solid #ffa39e;
  border-radius: $radius-large;
}

.kpi-skeleton-card {
  padding: 16px 20px;
  background: $bg-white;
  border-radius: $radius-large;
  box-shadow: $shadow-card;
}

.dashboard-panel {
  height: 100%;
}

.panel-extra {
  display: inline-flex;
  align-items: center;
  gap: 12px;
}

.panel-skeleton {
  padding: 16px 8px;
}

.device-summary-bar {
  display: inline-flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.clickable-table {
  :deep(.el-table__row) {
    cursor: pointer;
  }
}

.elder-cell-name {
  font-weight: 600;
  color: $text-primary;
}

.elder-cell-room {
  font-size: 12px;
  color: $text-regular;
}

.mono-time {
  font-family: monospace;
  font-size: 12px;
}

.mono-link {
  font-family: monospace;
  font-weight: 600;
}
</style>
