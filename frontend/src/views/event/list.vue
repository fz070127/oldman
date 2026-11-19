<template>
  <div class="event-list-page">
    <!-- 顶部 4 个统计卡（数据来自 GET /events/stats?range=today） -->
    <el-row :gutter="16" class="mb-16">
      <el-col :xs="24" :sm="12" :md="6">
        <StatCard
          title="今日事件数"
          :value="stats?.todayTotal ?? 0"
          unit="件"
          accent-color="#1677ff"
        />
      </el-col>
      <el-col :xs="24" :sm="12" :md="6">
        <StatCard
          title="今日 P0 数"
          :value="stats?.todayP0 ?? 0"
          unit="件"
          value-color="#cf1322"
          accent-color="#cf1322"
        />
      </el-col>
      <el-col :xs="24" :sm="12" :md="6">
        <StatCard
          title="本月误报率"
          :value="stats ? (stats.falsePositiveRate * 100).toFixed(1) : '0.0'"
          unit="%"
          accent-color="#faad14"
        />
      </el-col>
      <el-col :xs="24" :sm="12" :md="6">
        <StatCard
          title="待处理数"
          :value="stats?.unhandledCount ?? 0"
          unit="件"
          :value-color="(stats?.unhandledCount ?? 0) > 0 ? '#d46b08' : '#1f2329'"
          accent-color="#fa8c16"
        />
      </el-col>
    </el-row>

    <!-- 筛选区 -->
    <SearchForm :model-value="searchParams" @search="handleSearch" @reset="handleReset">
      <el-form-item label="时间范围">
        <div class="time-filter-wrap">
          <el-radio-group v-model="activeRangePreset" size="default" @change="onPresetChange">
            <el-radio-button value="today">今天</el-radio-button>
            <el-radio-button value="7d">近7天</el-radio-button>
            <el-radio-button value="30d">近30天</el-radio-button>
          </el-radio-group>
          <el-date-picker
            v-model="customDateRange"
            type="datetimerange"
            range-separator="至"
            start-placeholder="开始时间"
            end-placeholder="结束时间"
            format="YYYY-MM-DD HH:mm"
            style="width: 330px"
            clearable
            @change="onCustomDateChange"
          />
        </div>
      </el-form-item>

      <el-form-item label="老人">
        <el-select
          v-model="searchParams.elderId"
          placeholder="搜索选择老人"
          filterable
          clearable
          style="width: 170px"
        >
          <el-option
            v-for="e in elderOptions"
            :key="e.id"
            :label="`${e.name}（${e.roomNo}）`"
            :value="e.id"
          />
        </el-select>
      </el-form-item>

      <el-form-item label="设备">
        <el-select
          v-model="searchParams.deviceId"
          placeholder="全部设备"
          filterable
          clearable
          style="width: 160px"
        >
          <el-option
            v-for="d in deviceOptions"
            :key="d.id"
            :label="d.deviceNo"
            :value="d.id"
          />
        </el-select>
      </el-form-item>

      <el-form-item label="事件类型">
        <el-select v-model="searchParams.type" placeholder="全部类型" clearable style="width: 130px">
          <el-option label="跌倒检测" :value="EventType.FALL" />
          <el-option label="久躺预警" :value="EventType.LONG_LIE" />
        </el-select>
      </el-form-item>

      <el-form-item label="级别">
        <el-select v-model="searchParams.level" placeholder="全部级别" clearable style="width: 130px">
          <el-option label="P0 紧急" :value="EventLevel.P0" />
          <el-option label="P1 重要" :value="EventLevel.P1" />
          <el-option label="P2 一般" :value="EventLevel.P2" />
        </el-select>
      </el-form-item>

      <el-form-item label="处理状态">
        <el-select v-model="searchParams.handled" placeholder="全部" clearable style="width: 130px">
          <el-option label="待处理" value="false" />
          <el-option label="已处理" value="true" />
        </el-select>
      </el-form-item>
    </SearchForm>

    <!-- 列表主体 -->
    <PageContainer title="事件中心列表">
      <ProTable
        ref="tableRef"
        :columns="columns"
        :request="fetchEvents"
        :search-params="searchParams"
        :row-class-name="getRowClassName"
      >
        <!-- 发生时间（MM-DD HH:mm:ss） -->
        <template #occurredAt="{ row }">
          <span class="mono-time">{{ formatOccurredTime(row.occurredAt) }}</span>
        </template>

        <!-- 老人姓名（点击跳老人详情） -->
        <template #elderName="{ row }">
          <el-link
            type="primary"
            :underline="false"
            class="elder-link"
            @click="goElderDetail(row.elderId)"
          >
            {{ row.elderName }}
          </el-link>
        </template>

        <!-- 事件类型 -->
        <template #type="{ row }">
          <el-tag
            size="small"
            :type="row.type === EventType.FALL ? 'danger' : 'warning'"
            effect="plain"
          >
            {{ row.type === EventType.FALL ? '跌倒' : '久躺' }}
          </el-tag>
        </template>

        <!-- 级别（P0 红 / P1 橙 / P2 蓝） -->
        <template #level="{ row }">
          <StatusTag category="eventLevel" :status="row.level" />
        </template>

        <!-- 置信度（进度条样式：>0.9 绿，0.7-0.9 橙，<0.7 灰） -->
        <template #confidence="{ row }">
          <div class="confidence-cell">
            <el-progress
              :percentage="Math.round(row.confidence * 100)"
              :color="getConfidenceColor(row.confidence)"
              :stroke-width="8"
            />
          </div>
        </template>

        <!-- 截图（有则缩略图，点击放大） -->
        <template #snapshotUrl="{ row }">
          <div v-if="row.snapshotUrl" class="snapshot-cell" @click="openPreview(row)">
            <img
              :src="toThumbnailUrl(row.snapshotUrl)"
              :alt="row.id"
              class="snapshot-thumb"
              loading="lazy"
            />
            <span class="snapshot-zoom-hint">放大</span>
          </div>
          <span v-else class="text-disabled">无截图</span>
        </template>

        <!-- 处理结果（无则“待处理”灰色） -->
        <template #handleResult="{ row }">
          <el-tag
            v-if="row.handled && row.handleResult === EventHandleResult.TRUE_FALL"
            size="small"
            type="danger"
            effect="light"
          >
            确认属实
          </el-tag>
          <el-tag
            v-else-if="row.handled && row.handleResult === EventHandleResult.FALSE_POSITIVE"
            size="small"
            type="info"
            effect="light"
          >
            误报
          </el-tag>
          <el-tag
            v-else-if="row.handled"
            size="small"
            type="warning"
            effect="light"
          >
            其他结论
          </el-tag>
          <el-tag v-else size="small" class="unhandled-tag" effect="plain">
            待处理
          </el-tag>
        </template>

        <!-- 操作 -->
        <template #actions="{ row }">
          <el-button link type="primary" size="small" @click="goDetail(row.id)">详情</el-button>
          <template v-if="!row.handled">
            <el-button
              link
              type="success"
              size="small"
              :loading="handlingId === row.id"
              @click="quickHandle(row, EventHandleResult.TRUE_FALL)"
            >
              确认属实
            </el-button>
            <el-button
              link
              type="warning"
              size="small"
              :loading="handlingId === row.id"
              @click="quickHandle(row, EventHandleResult.FALSE_POSITIVE)"
            >
              标记误报
            </el-button>
          </template>
        </template>
      </ProTable>
    </PageContainer>

    <!-- 截图放大预览弹窗 -->
    <el-dialog
      v-model="previewVisible"
      :title="previewTitle"
      width="720px"
      destroy-on-close
      align-center
    >
      <div class="preview-dialog-body">
        <img v-if="previewUrl" :src="previewUrl" alt="事件大图" class="preview-full-img" />
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import dayjs from 'dayjs'
import { getDeviceList } from '@/api/device'
import { getElderList } from '@/api/elder'
import { getEventList, getEventStats, handleEvent } from '@/api/event'
import PageContainer from '@/components/PageContainer.vue'
import ProTable, { type ProTableColumn, type ProTableInstance } from '@/components/ProTable.vue'
import SearchForm from '@/components/SearchForm.vue'
import StatCard from '@/components/StatCard.vue'
import StatusTag from '@/components/StatusTag.vue'
import type { Device } from '@/types/device'
import type { Elder } from '@/types/elder'
import {
  EventHandleResult,
  EventLevel,
  EventType,
  StatsRange,
  type EventItem,
  type EventQuery,
  type EventStats,
} from '@/types/event'

const router = useRouter()
const tableRef = ref<ProTableInstance>()

// ---------------- 顶部统计卡 ----------------
const stats = ref<EventStats | null>(null)

async function loadStats() {
  stats.value = await getEventStats(StatsRange.TODAY)
}

// ---------------- 老人 / 设备下拉选项 ----------------
const elderOptions = ref<Elder[]>([])
const deviceOptions = ref<Device[]>([])

async function loadFilterOptions() {
  const [elderRes, devRes] = await Promise.all([
    getElderList({ page: 1, pageSize: 100 }),
    getDeviceList({ page: 1, pageSize: 100 }),
  ])
  elderOptions.value = elderRes.list || []
  deviceOptions.value = devRes.list || []
}

// ---------------- 时间筛选（必须转 ISO 8601 带时区） ----------------
type RangePreset = 'today' | '7d' | '30d' | ''
const activeRangePreset = ref<RangePreset>('')
const customDateRange = ref<[Date, Date] | null>(null)

function toIsoWithOffset(d: Date | dayjs.Dayjs): string {
  return dayjs(d).format('YYYY-MM-DDTHH:mm:ss+08:00')
}

const searchParams = reactive({
  elderId: '',
  deviceId: '',
  type: '' as EventType | '',
  level: '' as EventLevel | '',
  handled: '',
  startTime: '',
  endTime: '',
})

function onPresetChange(val: string | number | boolean | undefined) {
  const preset = (val || '') as RangePreset
  if (!preset) return
  const now = dayjs()
  const start =
    preset === 'today'
      ? now.startOf('day')
      : preset === '7d'
        ? now.subtract(7, 'day').startOf('day')
        : now.subtract(30, 'day').startOf('day')
  const end = now.endOf('day')
  customDateRange.value = [start.toDate(), end.toDate()]
  searchParams.startTime = toIsoWithOffset(start)
  searchParams.endTime = toIsoWithOffset(end)
}

function onCustomDateChange(val: [Date, Date] | null) {
  activeRangePreset.value = ''
  if (!val || val.length !== 2) {
    searchParams.startTime = ''
    searchParams.endTime = ''
    return
  }
  searchParams.startTime = toIsoWithOffset(val[0])
  searchParams.endTime = toIsoWithOffset(val[1])
}

// ---------------- 表格列与数据请求 ----------------
const columns: ProTableColumn<EventItem>[] = [
  { prop: 'occurredAt', label: '发生时间', width: 155, slot: 'occurredAt' },
  { prop: 'elderName', label: '老人姓名', width: 110, slot: 'elderName' },
  { prop: 'roomNo', label: '房号', width: 85 },
  { prop: 'type', label: '类型', width: 95, align: 'center', slot: 'type' },
  { prop: 'level', label: '级别', width: 105, align: 'center', slot: 'level' },
  { prop: 'confidence', label: '置信度', width: 165, slot: 'confidence', showOverflowTooltip: false },
  { prop: 'snapshotUrl', label: '截图', width: 105, align: 'center', slot: 'snapshotUrl', showOverflowTooltip: false },
  { prop: 'handleResult', label: '处理结果', width: 110, align: 'center', slot: 'handleResult' },
  { label: '操作', width: 210, fixed: 'right', slot: 'actions', showOverflowTooltip: false },
]

function fetchEvents(params: Record<string, unknown>) {
  return getEventList(params as EventQuery)
}

/** P0 行加淡红色背景 */
function getRowClassName({ row }: { row: EventItem }): string {
  if (row.level === EventLevel.P0) return 'is-p0-row'
  return ''
}

/** 发生时间格式化为 MM-DD HH:mm:ss */
function formatOccurredTime(ts?: string | null): string {
  if (!ts) return '-'
  const d = dayjs(ts)
  return d.isValid() ? d.format('MM-DD HH:mm:ss') : '-'
}

/**
 * 置信度进度条颜色分档：
 * - > 0.9 绿 (#52c41a)
 * - 0.7 - 0.9 橙 (#faad14)
 * - < 0.7 灰 (#909399)
 */
function getConfidenceColor(conf: number): string {
  if (conf > 0.9) return '#52c41a'
  if (conf >= 0.7) return '#faad14'
  return '#909399'
}

/** 将截图原图地址转换为轻量缩略图地址，点击弹窗时再加载大图 */
function toThumbnailUrl(url: string): string {
  return url.replace(/\/640\/480(\?.*)?$/, '/160/120$1')
}

function handleSearch() {
  tableRef.value?.reload(true)
}

function handleReset() {
  activeRangePreset.value = ''
  customDateRange.value = null
  searchParams.elderId = ''
  searchParams.deviceId = ''
  searchParams.type = ''
  searchParams.level = ''
  searchParams.handled = ''
  searchParams.startTime = ''
  searchParams.endTime = ''
  tableRef.value?.reload(true)
}

function goDetail(id: string) {
  router.push(`/event/detail/${id}`)
}

function goElderDetail(elderId: string) {
  router.push(`/elder/detail/${elderId}`)
}

// ---------------- 截图点击放大弹窗 ----------------
const previewVisible = ref(false)
const previewUrl = ref('')
const previewTitle = ref('事件截图预览')

function openPreview(row: EventItem) {
  previewTitle.value = `事件截图 · ${row.elderName}（${formatOccurredTime(row.occurredAt)}）`
  previewUrl.value = row.snapshotUrl
  previewVisible.value = true
}

// ---------------- 快捷处置（确认属实 / 标记误报） ----------------
const handlingId = ref('')

async function quickHandle(row: EventItem, result: EventHandleResult) {
  const isFalse = result === EventHandleResult.FALSE_POSITIVE
  const label = isFalse ? '标记为误报' : '确认事件属实'
  await ElMessageBox.confirm(
    `确定将老人「${row.elderName}」的该条事件${label}吗？`,
    '事件复核确认',
    { type: isFalse ? 'warning' : 'info', confirmButtonText: '确定提交', cancelButtonText: '取消' },
  )
  const defaultRemark = isFalse ? '列表快捷标记误报' : '列表快捷确认属实'
  handlingId.value = row.id
  try {
    await handleEvent(row.id, { result, remark: defaultRemark })
    ElMessage.success(isFalse ? '已标记为误报' : '已确认事件属实')
    // 重新拉取当前分页列表与顶部统计卡，确保处理结果即时同步且分页不乱
    await Promise.all([tableRef.value?.reload(false), loadStats()])
  } finally {
    handlingId.value = ''
  }
}

onMounted(() => {
  loadStats()
  loadFilterOptions()
})
</script>

<style scoped lang="scss">
.time-filter-wrap {
  display: inline-flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.mono-time {
  font-family: monospace;
  font-size: 13px;
}

.elder-link {
  font-weight: 600;
}

.confidence-cell {
  width: 135px;

  :deep(.el-progress__text) {
    min-width: 36px;
    font-size: 12px !important;
    font-weight: 600;
  }
}

.snapshot-cell {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 64px;
  height: 44px;
  overflow: hidden;
  cursor: pointer;
  border: 1px solid $border-color;
  border-radius: 4px;

  &:hover .snapshot-zoom-hint {
    opacity: 1;
  }
}

.snapshot-thumb {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.snapshot-zoom-hint {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  color: #fff;
  background: rgba(0, 0, 0, 0.45);
  opacity: 0;
  transition: opacity 0.15s ease;
}

.unhandled-tag {
  color: #646a73;
  background-color: #f2f3f5;
  border-color: #dcdfe6;
}

.preview-dialog-body {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 360px;
  background: #0f131a;
  border-radius: $radius-base;
  overflow: hidden;
}

.preview-full-img {
  max-width: 100%;
  max-height: 520px;
  object-fit: contain;
}

/* P0 行淡红色背景 */
:deep(.el-table .is-p0-row) {
  --el-table-tr-bg-color: #fff1f0;
  background-color: #fff1f0 !important;

  td.el-table__cell {
    background-color: #fff1f0 !important;
  }

  &:hover > td.el-table__cell {
    background-color: #ffe7e6 !important;
  }
}
</style>
