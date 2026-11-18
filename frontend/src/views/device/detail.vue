<template>
  <div v-loading="loading" class="device-detail-page">
    <PageContainer :title="device ? `设备详情 · ${device.deviceNo}` : '设备详情'">
      <template #extra>
        <el-button :icon="ArrowLeft" @click="router.push('/device')">返回列表</el-button>
        <el-button v-if="device" type="primary" :icon="Edit" @click="openEdit">编辑设备</el-button>
        <el-button
          v-if="device"
          type="warning"
          plain
          :loading="rebooting"
          @click="handleReboot"
        >
          远程重启
        </el-button>
      </template>

      <EmptyState v-if="!loading && !device" description="未找到该设备信息" />

      <div v-else-if="device" class="device-detail__content">
        <!-- 1. 基本信息 -->
        <section class="detail-block">
          <h3 class="detail-block__title">一、设备基本信息</h3>
          <el-descriptions :column="3" border label-width="96px">
            <el-descriptions-item label="设备编号">
              <span class="mono-text">{{ device.deviceNo }}</span>
            </el-descriptions-item>
            <el-descriptions-item label="设备类型">
              <StatusTag category="deviceType" :status="device.type" />
            </el-descriptions-item>
            <el-descriptions-item label="运行状态">
              <StatusTag category="deviceStatus" :status="device.status" />
            </el-descriptions-item>
            <el-descriptions-item label="绑定老人">
              <el-link
                v-if="device.elderId && device.elderName"
                type="primary"
                :underline="false"
                @click="router.push(`/elder/detail/${device.elderId}`)"
              >
                {{ device.elderName }}（{{ device.roomNo }}）
              </el-link>
              <span v-else class="text-disabled">未绑定</span>
            </el-descriptions-item>
            <el-descriptions-item label="所属社区">{{ device.communityName || '-' }}</el-descriptions-item>
            <el-descriptions-item label="算法版本">{{ device.algoVersion || '-' }}</el-descriptions-item>
            <el-descriptions-item label="最后心跳">
              <span :class="{ 'text-danger': isOnlineStale }">
                {{ formatRelativeTime(device.lastHeartbeat) }}
              </span>
              <el-tag v-if="isOnlineStale" size="small" type="danger" effect="plain" class="ml-8">
                心跳超时异常
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="安装地址" :span="2">{{ device.installAddr }}</el-descriptions-item>
          </el-descriptions>
        </section>

        <!-- 2. ROI 检测区域与家具抑制区（灰底占位图 + 归一化矩形叠加） -->
        <section class="detail-block">
          <div class="detail-block__head">
            <h3 class="detail-block__title">二、检测区域（ROI）与家具配置</h3>
            <div class="zone-legend">
              <span class="legend-item"><i class="dot is-roi" />检测区域 (ROI)</span>
              <span class="legend-item"><i class="dot is-furniture" />家具抑制区</span>
            </div>
          </div>

          <el-row :gutter="20">
            <el-col :xs="24" :lg="14">
              <div ref="stageRef" class="roi-stage">
                <div class="roi-stage__placeholder">
                  <span>画面占位区（{{ stageSize.width }} × {{ stageSize.height }}）</span>
                  <small>{{ device.deviceNo }} · 归一化坐标 0~1 映射</small>
                </div>

                <!-- ROI 矩形叠加 -->
                <div
                  v-for="(rect, idx) in roiRects"
                  :key="`roi-${idx}`"
                  class="zone-rect is-roi"
                  :style="toBoxStyle(rect)"
                >
                  <span class="zone-rect__label">ROI 检测区 {{ idx + 1 }}</span>
                </div>

                <!-- 家具矩形叠加 -->
                <div
                  v-for="(item, idx) in furnitureRects"
                  :key="`furn-${idx}`"
                  class="zone-rect is-furniture"
                  :style="toBoxStyle(item.rect)"
                >
                  <span class="zone-rect__label">{{ furnitureLabel(item.type) }}</span>
                </div>
              </div>
            </el-col>

            <el-col :xs="24" :lg="10">
              <el-card shadow="never" class="config-card">
                <template #header>
                  <span class="config-card__title">算法灵敏度与免打扰配置</span>
                </template>
                <el-form label-width="96px" size="default">
                  <el-form-item label="检测灵敏度">
                    <div class="slider-row">
                      <el-slider
                        v-model="configForm.sensitivity"
                        :min="0.1"
                        :max="1"
                        :step="0.05"
                        style="flex: 1"
                      />
                      <span class="slider-val">{{ configForm.sensitivity.toFixed(2) }}</span>
                    </div>
                  </el-form-item>

                  <el-form-item label="免打扰时段">
                    <el-input
                      v-model="quietHoursText"
                      placeholder="多个时段用逗号分隔，如 22:00-06:00"
                    />
                  </el-form-item>

                  <el-form-item label="ROI 数量">
                    <span>{{ roiRects.length }} 个区域</span>
                  </el-form-item>

                  <el-form-item label="家具抑制区">
                    <el-tag
                      v-for="(f, i) in furnitureRects"
                      :key="i"
                      size="small"
                      type="warning"
                      effect="plain"
                      class="mr-4"
                    >
                      {{ furnitureLabel(f.type) }}
                    </el-tag>
                    <span v-if="!furnitureRects.length" class="text-disabled">未配置</span>
                  </el-form-item>

                  <el-form-item>
                    <el-button type="primary" :loading="savingConfig" @click="saveConfig">
                      保存配置
                    </el-button>
                  </el-form-item>
                </el-form>
              </el-card>
            </el-col>
          </el-row>
        </section>

        <!-- 3. 近 24h 运行健康指标 -->
        <section class="detail-block">
          <h3 class="detail-block__title">三、近 24 小时运行健康趋势</h3>
          <el-row :gutter="16" class="mb-16">
            <el-col :span="8">
              <StatCard title="24h 心跳次数" :value="health?.heartbeats24h ?? 0" unit="次" />
            </el-col>
            <el-col :span="8">
              <StatCard
                title="平均帧率"
                :value="health?.avgFps ?? 0"
                unit="fps"
                accent-color="#52c41a"
              />
            </el-col>
            <el-col :span="8">
              <StatCard
                title="丢帧率"
                :value="health ? (health.dropRate * 100).toFixed(1) : '0.0'"
                unit="%"
                accent-color="#faad14"
              />
            </el-col>
          </el-row>
          <div ref="chartRef" class="health-chart" />
        </section>
      </div>
    </PageContainer>

    <!-- 编辑设备弹窗 -->
    <el-dialog v-model="editVisible" title="编辑设备信息" width="520px" destroy-on-close>
      <el-form ref="editFormRef" :model="editForm" :rules="editRules" label-width="96px">
        <el-form-item label="设备编号" prop="deviceNo">
          <el-input v-model.trim="editForm.deviceNo" disabled />
        </el-form-item>
        <el-form-item label="设备类型" prop="type">
          <el-select v-model="editForm.type" style="width: 100%">
            <el-option label="边缘盒子" :value="DeviceType.EDGE_BOX" />
            <el-option label="IPC 摄像机" :value="DeviceType.IPC" />
            <el-option label="毫米波雷达" :value="DeviceType.RADAR" />
          </el-select>
        </el-form-item>
        <el-form-item label="安装地址" prop="installAddr">
          <el-input v-model.trim="editForm.installAddr" placeholder="请输入安装地址" />
        </el-form-item>
        <el-form-item label="算法版本" prop="algoVersion">
          <el-input v-model.trim="editForm.algoVersion" placeholder="例如：fall-v1.2.1" />
        </el-form-item>
        <el-form-item label="RTSP 地址">
          <el-input v-model.trim="editForm.rtspUrl" placeholder="可选，雷达设备可留空" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取 消</el-button>
        <el-button type="primary" :loading="savingEdit" @click="submitEdit">保 存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import * as echarts from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([LineChart, GridComponent, LegendComponent, TooltipComponent, CanvasRenderer])
import dayjs from 'dayjs'
import type { FormInstance, FormRules } from 'element-plus'
import { ArrowLeft, Edit } from '@element-plus/icons-vue'
import {
  getDeviceDetail,
  getDeviceHealth,
  rebootDevice,
  updateDevice,
  updateDeviceConfig,
} from '@/api/device'
import EmptyState from '@/components/EmptyState.vue'
import PageContainer from '@/components/PageContainer.vue'
import StatCard from '@/components/StatCard.vue'
import StatusTag from '@/components/StatusTag.vue'
import { ResultCode, type ApiResult } from '@/types/common'
import {
  DeviceStatus,
  DeviceType,
  type Device,
  type DeviceHealth,
  type FurnitureZone,
  type NormalizedPoint,
  type NormalizedRect,
} from '@/types/device'
import { formatRelativeTime, isHeartbeatStale } from '@/utils/time'

const route = useRoute()
const router = useRouter()

const deviceId = computed(() => String(route.params.id || ''))
const loading = ref(false)
const device = ref<Device | null>(null)
const health = ref<DeviceHealth | null>(null)

const isOnlineStale = computed(
  () => !!device.value && device.value.status === DeviceStatus.ONLINE && isHeartbeatStale(device.value.lastHeartbeat, 5),
)

// ---------------- ROI 画布展示（支持 {x,y,w,h} 与 [[x,y]...] 两种格式） ----------------
const stageRef = ref<HTMLElement>()
const stageSize = reactive({ width: 640, height: 480 })

function updateStageSize() {
  if (!stageRef.value) return
  stageSize.width = Math.round(stageRef.value.clientWidth || 640)
  stageSize.height = Math.round(stageRef.value.clientHeight || 480)
}

function pointsToRect(points: NormalizedPoint[]): NormalizedRect | null {
  if (!points.length) return null
  const xs = points.map((p) => p[0])
  const ys = points.map((p) => p[1])
  const minX = Math.min(...xs)
  const maxX = Math.max(...xs)
  const minY = Math.min(...ys)
  const maxY = Math.max(...ys)
  return { x: minX, y: minY, w: Math.max(0.02, maxX - minX), h: Math.max(0.02, maxY - minY) }
}

const roiRects = computed<NormalizedRect[]>(() => {
  const roi = device.value?.config?.roi
  if (!Array.isArray(roi) || !roi.length) return []
  const first = roi[0]
  // 矩形数组格式：[{x, y, w, h}]
  if (typeof first === 'object' && !Array.isArray(first) && 'x' in first) {
    return roi as NormalizedRect[]
  }
  // 多边形顶点格式：[[x, y], ...]
  const rect = pointsToRect(roi as NormalizedPoint[])
  return rect ? [rect] : []
})

const furnitureRects = computed<Array<{ type: string; rect: NormalizedRect }>>(() => {
  const list = device.value?.config?.furniture || []
  const res: Array<{ type: string; rect: NormalizedRect }> = []
  for (const item of list as FurnitureZone[]) {
    if (
      typeof item.x === 'number' &&
      typeof item.y === 'number' &&
      typeof item.w === 'number' &&
      typeof item.h === 'number'
    ) {
      res.push({ type: item.type, rect: { x: item.x, y: item.y, w: item.w, h: item.h } })
    } else if (Array.isArray(item.points) && item.points.length) {
      const rect = pointsToRect(item.points)
      if (rect) res.push({ type: item.type, rect })
    }
  }
  return res
})

function toBoxStyle(rect: NormalizedRect) {
  return {
    left: `${Math.round(rect.x * stageSize.width)}px`,
    top: `${Math.round(rect.y * stageSize.height)}px`,
    width: `${Math.round(rect.w * stageSize.width)}px`,
    height: `${Math.round(rect.h * stageSize.height)}px`,
  }
}

const FURNITURE_LABEL_MAP: Record<string, string> = {
  bed: '床铺区',
  sofa: '沙发区',
  chair: '座椅区',
  table: '桌台区',
}
function furnitureLabel(type: string): string {
  return FURNITURE_LABEL_MAP[type] || type
}

// ---------------- 配置保存 ----------------
const savingConfig = ref(false)
const configForm = reactive({ sensitivity: 0.7 })
const quietHoursText = ref('')

async function saveConfig() {
  if (!device.value) return
  savingConfig.value = true
  try {
    const quietHours = quietHoursText.value
      .split(/[,，]/)
      .map((s) => s.trim())
      .filter(Boolean)
    const updated = await updateDeviceConfig(device.value.id, {
      roi: device.value.config.roi,
      furniture: device.value.config.furniture,
      sensitivity: configForm.sensitivity,
      quietHours,
    })
    device.value.config = updated
    ElMessage.success('设备配置已下发')
  } finally {
    savingConfig.value = false
  }
}

// ---------------- ECharts 24h 健康折线图 ----------------
const chartRef = ref<HTMLElement>()
let chartInst: echarts.ECharts | null = null

function renderChart() {
  if (!chartRef.value || !health.value) return
  if (!chartInst) chartInst = echarts.init(chartRef.value)

  const series = health.value.series || []
  chartInst.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: ['CPU (%)', '内存 (%)'] },
    grid: { left: 44, right: 20, top: 36, bottom: 28 },
    xAxis: {
      type: 'category',
      data: series.map((s) => dayjs(s.ts).format('HH:mm')),
    },
    yAxis: { type: 'value', max: 100, axisLabel: { formatter: '{value}%' } },
    series: [
      {
        name: 'CPU (%)',
        type: 'line',
        smooth: true,
        data: series.map((s) => s.cpu),
        itemStyle: { color: '#1677ff' },
      },
      {
        name: '内存 (%)',
        type: 'line',
        smooth: true,
        data: series.map((s) => s.mem),
        itemStyle: { color: '#52c41a' },
      },
    ],
  })
}

function handleResize() {
  updateStageSize()
  chartInst?.resize()
}

// ---------------- 加载数据 ----------------
async function loadData() {
  if (!deviceId.value) return
  loading.value = true
  try {
    const [dev, h] = await Promise.all([
      getDeviceDetail(deviceId.value),
      getDeviceHealth(deviceId.value).catch(() => null),
    ])
    device.value = dev
    health.value = h
    configForm.sensitivity = dev.config?.sensitivity ?? 0.7
    quietHoursText.value = (dev.config?.quietHours || []).join(', ')
    await nextTick()
    updateStageSize()
    renderChart()
  } finally {
    loading.value = false
  }
}

// ---------------- 重启与编辑 ----------------
const rebooting = ref(false)
async function handleReboot() {
  if (!device.value) return
  rebooting.value = true
  try {
    await rebootDevice(device.value.id)
    ElMessage.success(`已向设备 ${device.value.deviceNo} 下发远程重启指令`)
    await loadData()
  } catch (err) {
    const apiErr = err as Partial<ApiResult<unknown>> | undefined
    if (apiErr?.code === ResultCode.DOWNSTREAM_UNAVAILABLE || device.value.status !== DeviceStatus.ONLINE) {
      ElMessage.warning('设备离线，无法远程重启')
    } else {
      ElMessage.warning(apiErr?.message || '设备离线，无法远程重启')
    }
  } finally {
    rebooting.value = false
  }
}

const editVisible = ref(false)
const savingEdit = ref(false)
const editFormRef = ref<FormInstance>()
const editForm = reactive({
  deviceNo: '',
  type: DeviceType.EDGE_BOX as DeviceType,
  installAddr: '',
  algoVersion: '',
  rtspUrl: '',
})
const editRules: FormRules = {
  installAddr: [{ required: true, message: '请输入安装地址', trigger: 'blur' }],
}

function openEdit() {
  if (!device.value) return
  editForm.deviceNo = device.value.deviceNo
  editForm.type = device.value.type
  editForm.installAddr = device.value.installAddr
  editForm.algoVersion = device.value.algoVersion
  editForm.rtspUrl = device.value.rtspUrl || ''
  editVisible.value = true
}

async function submitEdit() {
  if (!device.value || savingEdit.value) return
  const valid = await editFormRef.value?.validate().catch(() => false)
  if (!valid) return
  savingEdit.value = true
  try {
    await updateDevice(device.value.id, {
      type: editForm.type,
      installAddr: editForm.installAddr,
      algoVersion: editForm.algoVersion,
      rtspUrl: editForm.rtspUrl || undefined,
    })
    ElMessage.success('设备信息已更新')
    editVisible.value = false
    await loadData()
  } finally {
    savingEdit.value = false
  }
}

watch(deviceId, () => loadData(), { immediate: true })
onMounted(() => window.addEventListener('resize', handleResize))
onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  chartInst?.dispose()
  chartInst = null
})
</script>

<style scoped lang="scss">
.device-detail__content {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.detail-block {
  &__head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 12px;
  }

  &__title {
    margin-bottom: 12px;
    font-size: 15px;
    font-weight: 600;
    color: $text-primary;
    border-left: 3px solid $color-primary;
    padding-left: 10px;
  }

  &__head &__title {
    margin-bottom: 0;
  }
}

.mono-text {
  font-family: monospace;
  font-weight: 600;
}

.zone-legend {
  display: flex;
  gap: 16px;
  font-size: 13px;
  color: $text-regular;

  .legend-item {
    display: inline-flex;
    align-items: center;
    gap: 6px;
  }

  .dot {
    display: inline-block;
    width: 10px;
    height: 10px;
    border-radius: 2px;

    &.is-roi {
      background: rgba(22, 119, 255, 0.35);
      border: 1px solid #1677ff;
    }

    &.is-furniture {
      background: rgba(250, 173, 20, 0.35);
      border: 1px solid #faad14;
    }
  }
}

.roi-stage {
  position: relative;
  width: 100%;
  aspect-ratio: 4 / 3;
  overflow: hidden;
  background: linear-gradient(135deg, #dfe4ec 0%, #cfd6e0 100%);
  border: 1px solid $border-color;
  border-radius: $radius-large;

  &__placeholder {
    position: absolute;
    inset: 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 6px;
    color: #5c6676;
    font-size: 14px;
    user-select: none;

    small {
      font-size: 12px;
      opacity: 0.8;
    }
  }
}

.zone-rect {
  position: absolute;
  box-sizing: border-box;
  border-radius: 4px;
  pointer-events: none;

  &.is-roi {
    background: rgba(22, 119, 255, 0.16);
    border: 2px solid #1677ff;

    .zone-rect__label {
      background: #1677ff;
    }
  }

  &.is-furniture {
    background: rgba(250, 173, 20, 0.2);
    border: 2px dashed #faad14;

    .zone-rect__label {
      background: #faad14;
    }
  }

  &__label {
    display: inline-block;
    padding: 2px 6px;
    font-size: 11px;
    line-height: 1.4;
    color: #fff;
    border-radius: 0 0 4px 0;
  }
}

.config-card {
  height: 100%;

  &__title {
    font-weight: 600;
    color: $text-primary;
  }
}

.slider-row {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
}

.slider-val {
  min-width: 36px;
  font-weight: 600;
  color: $color-primary;
  text-align: right;
}

.health-chart {
  width: 100%;
  height: 260px;
  background: #fafbfc;
  border: 1px solid $border-color-light;
  border-radius: $radius-base;
}
</style>
