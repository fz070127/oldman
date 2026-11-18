<template>
  <div class="elder-list-page">
    <!-- 顶部筛选区 -->
    <SearchForm :model-value="searchParams" @search="handleSearch" @reset="handleReset">
      <el-form-item label="关键字">
        <el-input
          v-model.trim="searchParams.keyword"
          placeholder="搜索姓名 / 房号 / 地址"
          clearable
          style="width: 220px"
          @keyup.enter="handleSearch"
        />
      </el-form-item>

      <el-form-item label="所属社区">
        <el-select v-model="searchParams.communityId" placeholder="全部社区" clearable style="width: 160px">
          <el-option v-for="c in communityOptions" :key="c.id" :label="c.name" :value="c.id" />
        </el-select>
      </el-form-item>

      <el-form-item label="档案状态">
        <el-select v-model="searchParams.status" placeholder="全部状态" clearable style="width: 140px">
          <el-option label="在册" :value="ElderStatus.ACTIVE" />
          <el-option label="暂停" :value="ElderStatus.PAUSED" />
        </el-select>
      </el-form-item>

      <el-form-item label="设备在线">
        <el-select v-model="searchParams.deviceOnline" placeholder="全部" clearable style="width: 140px">
          <el-option label="在线" value="true" />
          <el-option label="离线" value="false" />
        </el-select>
      </el-form-item>
    </SearchForm>

    <!-- 列表主体 -->
    <PageContainer title="老人档案列表">
      <template #extra>
        <el-button v-permission="'elder:write'" type="primary" :icon="Plus" @click="openCreate">
          新建老人
        </el-button>
      </template>

      <ProTable
        ref="tableRef"
        :columns="columns"
        :request="fetchElders"
        :search-params="searchParams"
        :row-class-name="getRowClassName"
      >
        <!-- 姓名：点击进入详情 -->
        <template #name="{ row }">
          <el-link type="primary" :underline="false" class="elder-name-link" @click="goDetail(row.id)">
            {{ row.name }}
          </el-link>
        </template>

        <!-- 性别 -->
        <template #gender="{ row }">
          <span>{{ row.gender === Gender.MALE ? '男' : '女' }}</span>
        </template>

        <!-- 健康标签：最多显示 3 个，超出显示 +N -->
        <template #healthTags="{ row }">
          <div v-if="row.healthTags && row.healthTags.length" class="tag-cell">
            <el-tag
              v-for="tag in row.healthTags.slice(0, 3)"
              :key="tag"
              size="small"
              effect="plain"
              class="mr-4"
            >
              {{ tag }}
            </el-tag>
            <el-tag v-if="row.healthTags.length > 3" size="small" type="info" effect="plain">
              +{{ row.healthTags.length - 3 }}
            </el-tag>
          </div>
          <span v-else class="text-disabled">无</span>
        </template>

        <!-- 档案状态：1 在册（绿）/ 2 暂停（灰）/ 3 离世（深灰） -->
        <template #status="{ row }">
          <StatusTag category="elderStatus" :status="row.status" />
        </template>

        <!-- 设备在线：绿点 + 在线 / 灰点 + 离线 / 无设备（不显示点） -->
        <template #deviceOnline="{ row }">
          <StatusTag
            category="elderOnline"
            :status="row.deviceOnline"
            :has-device="row.hasDevice !== false"
          />
        </template>

        <!-- 近 30 天告警数 -->
        <template #alarmCount30d="{ row }">
          <span :class="{ 'alarm-count-danger': row.alarmCount30d > 0 }">
            {{ row.alarmCount30d }}
          </span>
        </template>

        <!-- 操作：查看详情 / 编辑 / 停用 -->
        <template #actions="{ row }">
          <el-button link type="primary" size="small" @click="goDetail(row.id)">查看详情</el-button>
          <el-button
            v-permission="'elder:write'"
            link
            type="primary"
            size="small"
            @click="openEdit(row)"
          >
            编辑
          </el-button>
          <el-button
            v-if="row.status === ElderStatus.ACTIVE"
            v-permission="'elder:write'"
            link
            type="danger"
            size="small"
            @click="handleDisable(row)"
          >
            停用
          </el-button>
        </template>
      </ProTable>
    </PageContainer>

    <!-- 新建 / 编辑弹窗 -->
    <ElderFormDialog v-model="dialogVisible" :edit-data="editingElder" @success="handleFormSuccess" />
  </div>
</template>

<script setup lang="ts">
import { Plus } from '@element-plus/icons-vue'
import { getElderList, updateElder } from '@/api/elder'
import PageContainer from '@/components/PageContainer.vue'
import ProTable, { type ProTableColumn, type ProTableInstance } from '@/components/ProTable.vue'
import SearchForm from '@/components/SearchForm.vue'
import StatusTag from '@/components/StatusTag.vue'
import { ElderStatus, Gender, type Elder, type ElderQuery } from '@/types/elder'
import ElderFormDialog from './components/ElderFormDialog.vue'

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
  communityId: '',
  status: '' as ElderStatus | '',
  deviceOnline: '',
})

/** 记录在本页被手动“停用”的老人 ID，在默认列表（未选状态筛选）中隐藏，切到“暂停”筛选时可见 */
const manuallyPausedIds = ref<Set<string>>(new Set())

const columns: ProTableColumn<Elder>[] = [
  { prop: 'name', label: '姓名', width: 110, slot: 'name' },
  { prop: 'age', label: '年龄', width: 75, align: 'center' },
  { prop: 'gender', label: '性别', width: 70, align: 'center', slot: 'gender' },
  { prop: 'roomNo', label: '房号', width: 90 },
  { prop: 'communityName', label: '社区', minWidth: 130 },
  { prop: 'guardianName', label: '责任网格员', width: 110 },
  { prop: 'healthTags', label: '健康标签', minWidth: 200, slot: 'healthTags', showOverflowTooltip: false },
  { prop: 'status', label: '状态', width: 90, align: 'center', slot: 'status' },
  { prop: 'deviceOnline', label: '设备在线', width: 105, slot: 'deviceOnline' },
  { prop: 'alarmCount30d', label: '近30天告警', width: 110, align: 'center', slot: 'alarmCount30d' },
  { label: '操作', width: 180, fixed: 'right', slot: 'actions', showOverflowTooltip: false },
]

async function fetchElders(params: Record<string, unknown>) {
  const res = await getElderList(params as ElderQuery)
  // 若未指定 status 筛选，隐藏本次会话内刚被点击“停用”的老人（验收第 6 条：停用老人 → 状态变「暂停」，默认列表看不到）
  if (!params.status && manuallyPausedIds.value.size > 0) {
    const filtered = res.list.filter((item) => !manuallyPausedIds.value.has(item.id))
    return {
      ...res,
      list: filtered,
      total: Math.max(0, res.total - manuallyPausedIds.value.size),
    }
  }
  return res
}

function getRowClassName({ row }: { row: Elder }): string {
  if (!row.deviceOnline) return 'is-offline-row'
  return ''
}

function handleSearch() {
  tableRef.value?.reload(true)
}

function handleReset() {
  searchParams.keyword = ''
  searchParams.communityId = ''
  searchParams.status = ''
  searchParams.deviceOnline = ''
  tableRef.value?.reload(true)
}

function goDetail(id: string) {
  router.push(`/elder/detail/${id}`)
}

// ---------------- 新建 / 编辑 / 停用 ----------------
const dialogVisible = ref(false)
const editingElder = ref<Elder | null>(null)

function openCreate() {
  editingElder.value = null
  dialogVisible.value = true
}

function openEdit(row: Elder) {
  editingElder.value = row
  dialogVisible.value = true
}

function handleFormSuccess() {
  tableRef.value?.reload(false)
}

async function handleDisable(row: Elder) {
  await ElMessageBox.confirm(
    `确定停用老人「${row.name}」的档案吗？停用后状态将变为「暂停」，默认列表不再展示。`,
    '停用确认',
    { type: 'warning', confirmButtonText: '确定停用', cancelButtonText: '取消' },
  )
  await updateElder(row.id, { status: ElderStatus.PAUSED })
  manuallyPausedIds.value.add(row.id)
  ElMessage.success(`已将「${row.name}」状态设为暂停`)
  tableRef.value?.reload(false)
}
</script>

<style scoped lang="scss">
.elder-name-link {
  font-weight: 600;
}

/* 多个标签保持单行，避免单元格内换行导致行高不一致 */
.tag-cell {
  display: flex;
  flex-wrap: nowrap;
  align-items: center;
  overflow: hidden;

  :deep(.el-tag) {
    flex-shrink: 0;
    white-space: nowrap;
  }
}

.alarm-count-danger {
  font-weight: 700;
  color: $color-danger;
}

:deep(.el-table .is-offline-row) {
  color: $text-regular;
  background-color: #fafafa;

  td:first-child {
    box-shadow: inset 4px 0 0 $color-warning;
  }
}
</style>
