<template>
  <div class="device-list-page">
    <!-- 顶部筛选区 -->
    <SearchForm :model-value="searchParams" @search="handleSearch" @reset="handleReset">
      <el-form-item label="关键字">
        <el-input
          v-model.trim="searchParams.keyword"
          placeholder="搜索设备号 / 老人姓名 / 地址"
          clearable
          style="width: 240px"
          @keyup.enter="handleSearch"
        />
      </el-form-item>

      <el-form-item label="运行状态">
        <el-select v-model="searchParams.status" placeholder="全部状态" clearable style="width: 140px">
          <el-option label="在线" :value="DeviceStatus.ONLINE" />
          <el-option label="离线" :value="DeviceStatus.OFFLINE" />
          <el-option label="故障" :value="DeviceStatus.FAULT" />
          <el-option label="未激活" :value="DeviceStatus.INACTIVE" />
        </el-select>
      </el-form-item>

      <el-form-item label="所属社区">
        <el-select v-model="searchParams.communityId" placeholder="全部社区" clearable style="width: 160px">
          <el-option v-for="c in communityOptions" :key="c.id" :label="c.name" :value="c.id" />
        </el-select>
      </el-form-item>
    </SearchForm>

    <!-- 列表主体 -->
    <PageContainer title="设备管理列表">
      <ProTable
        ref="tableRef"
        :columns="columns"
        :request="fetchDevices"
        :search-params="searchParams"
      >
        <!-- 设备号：点击进入详情 -->
        <template #deviceNo="{ row }">
          <el-link type="primary" :underline="false" class="device-no-link" @click="goDetail(row.id)">
            {{ row.deviceNo }}
          </el-link>
        </template>

        <!-- 绑定老人 -->
        <template #elderName="{ row }">
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

        <!-- 设备类型 -->
        <template #type="{ row }">
          <StatusTag category="deviceType" :status="row.type" />
        </template>

        <!-- 运行状态：0 未激活（灰）/ 1 在线（绿）/ 2 离线（红）/ 3 故障（橙） -->
        <template #status="{ row }">
          <StatusTag category="deviceStatus" :status="row.status" />
        </template>

        <!-- 最后心跳：相对时间；若状态为「在线」但心跳超过 5 分钟，标红提示异常 -->
        <template #lastHeartbeat="{ row }">
          <div class="heartbeat-cell" :class="{ 'is-stale': isOnlineButStale(row) }">
            <span>{{ formatRelativeTime(row.lastHeartbeat) }}</span>
            <el-tag
              v-if="isOnlineButStale(row)"
              size="small"
              type="danger"
              effect="plain"
              class="ml-8"
            >
              心跳超时异常
            </el-tag>
          </div>
        </template>

        <!-- 操作：编辑 / 重启 -->
        <template #actions="{ row }">
          <el-button link type="primary" size="small" @click="goDetail(row.id)">编辑</el-button>
          <el-button
            link
            type="warning"
            size="small"
            :loading="rebootingId === row.id"
            @click="handleReboot(row)"
          >
            重启
          </el-button>
        </template>
      </ProTable>
    </PageContainer>
  </div>
</template>

<script setup lang="ts">
import { getDeviceList, rebootDevice } from '@/api/device'
import PageContainer from '@/components/PageContainer.vue'
import ProTable, { type ProTableColumn, type ProTableInstance } from '@/components/ProTable.vue'
import SearchForm from '@/components/SearchForm.vue'
import StatusTag from '@/components/StatusTag.vue'
import { ResultCode, type ApiResult } from '@/types/common'
import { DeviceStatus, type Device, type DeviceQuery } from '@/types/device'
import { formatRelativeTime, isHeartbeatStale } from '@/utils/time'

const router = useRouter()
const tableRef = ref<ProTableInstance>()

const communityOptions = [
  { id: 'C01', name: '幸福里社区' },
  { id: 'C02', name: '康乐苑社区' },
  { id: 'C03', name: '阳光花园社区' },
  { id: 'C04', name: '翠竹园社区' },
  { id: 'C05', name: '长青新村社区' },
]

const searchParams = reactive({
  keyword: '',
  status: '' as DeviceStatus | '',
  communityId: '',
})

const columns: ProTableColumn<Device>[] = [
  { prop: 'deviceNo', label: '设备号', width: 140, slot: 'deviceNo' },
  { prop: 'elderName', label: '老人姓名', width: 120, slot: 'elderName' },
  { prop: 'type', label: '类型', width: 120, slot: 'type' },
  { prop: 'installAddr', label: '安装地址', minWidth: 200 },
  { prop: 'status', label: '状态', width: 95, align: 'center', slot: 'status' },
  { prop: 'lastHeartbeat', label: '最后心跳', minWidth: 180, slot: 'lastHeartbeat', showOverflowTooltip: false },
  { prop: 'algoVersion', label: '算法版本', width: 130 },
  { label: '操作', width: 140, fixed: 'right', slot: 'actions', showOverflowTooltip: false },
]

function fetchDevices(params: Record<string, unknown>) {
  return getDeviceList(params as DeviceQuery)
}

function isOnlineButStale(row: Device): boolean {
  return row.status === DeviceStatus.ONLINE && isHeartbeatStale(row.lastHeartbeat, 5)
}

function handleSearch() {
  tableRef.value?.reload(true)
}

function handleReset() {
  searchParams.keyword = ''
  searchParams.status = ''
  searchParams.communityId = ''
  tableRef.value?.reload(true)
}

function goDetail(id: string) {
  router.push(`/device/detail/${id}`)
}

const rebootingId = ref('')
async function handleReboot(row: Device) {
  await ElMessageBox.confirm(
    `确定向设备「${row.deviceNo}」下发远程重启指令吗？重启期间设备将短暂离线。`,
    '远程重启确认',
    { type: 'warning', confirmButtonText: '确定重启', cancelButtonText: '取消' },
  )
  rebootingId.value = row.id
  try {
    await rebootDevice(row.id)
    ElMessage.success(`已向设备 ${row.deviceNo} 下发远程重启指令`)
    tableRef.value?.reload(false)
  } catch (err) {
    // 5001 下游不可用或设备离线：弹出友好黄底提示，不弹红色报错
    const apiErr = err as Partial<ApiResult<unknown>> | undefined
    if (apiErr && apiErr.code === ResultCode.DOWNSTREAM_UNAVAILABLE) {
      ElMessage.warning('设备离线，无法远程重启')
    } else if (row.status !== DeviceStatus.ONLINE) {
      ElMessage.warning('设备离线，无法远程重启')
    } else {
      ElMessage.warning(apiErr?.message || '设备离线，无法远程重启')
    }
  } finally {
    rebootingId.value = ''
  }
}
</script>

<style scoped lang="scss">
.device-no-link {
  font-family: monospace;
  font-weight: 600;
}

.heartbeat-cell {
  display: inline-flex;
  align-items: center;

  &.is-stale {
    font-weight: 600;
    color: $color-danger;
  }
}
</style>
