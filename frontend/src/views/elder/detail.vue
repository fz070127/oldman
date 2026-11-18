<template>
  <div v-loading="loading" class="elder-detail-page">
    <!-- 顶部操作栏 -->
    <PageContainer :title="detail ? `老人档案详情 · ${detail.name}` : '老人档案详情'">
      <template #extra>
        <el-button :icon="ArrowLeft" @click="router.push('/elder')">返回列表</el-button>
        <el-button
          v-if="detail"
          v-permission="'elder:write'"
          type="primary"
          :icon="Edit"
          @click="openEdit"
        >
          编辑
        </el-button>
        <el-button
          v-if="detail && detail.status === ElderStatus.ACTIVE"
          v-permission="'elder:write'"
          type="danger"
          plain
          @click="handleDisable"
        >
          停用
        </el-button>
      </template>

      <EmptyState v-if="!loading && !detail" description="未找到该老人档案信息" />

      <div v-else-if="detail" class="elder-detail__blocks">
        <!-- 1. 基本信息 -->
        <section class="detail-block">
          <h3 class="detail-block__title">一、基本信息</h3>
          <el-descriptions :column="3" border>
            <el-descriptions-item label="姓名">{{ detail.name }}</el-descriptions-item>
            <el-descriptions-item label="性别">
              {{ detail.gender === Gender.MALE ? '男' : '女' }}
            </el-descriptions-item>
            <el-descriptions-item label="出生日期">{{ detail.birthDate }}</el-descriptions-item>
            <el-descriptions-item label="年龄">{{ detail.age }} 岁</el-descriptions-item>
            <el-descriptions-item label="手机号">{{ detail.phone }}</el-descriptions-item>
            <el-descriptions-item label="档案状态">
              <StatusTag category="elderStatus" :status="detail.status" />
            </el-descriptions-item>
            <el-descriptions-item label="所属社区">{{ detail.communityName }}</el-descriptions-item>
            <el-descriptions-item label="房号">{{ detail.roomNo }}</el-descriptions-item>
            <el-descriptions-item label="责任网格员">{{ detail.guardianName }}</el-descriptions-item>
            <el-descriptions-item label="检测模式">
              <StatusTag category="detectMode" :status="detail.detectMode" />
            </el-descriptions-item>
            <el-descriptions-item label="居住地址" :span="2">
              {{ detail.address }} {{ detail.roomNo }}
            </el-descriptions-item>
          </el-descriptions>
        </section>

        <!-- 2. 健康档案 -->
        <section class="detail-block">
          <h3 class="detail-block__title">二、健康档案与紧急联系人</h3>
          <el-descriptions :column="1" border>
            <el-descriptions-item label="健康标签">
              <template v-if="detail.healthTags.length">
                <el-tag
                  v-for="tag in detail.healthTags"
                  :key="tag"
                  size="small"
                  effect="plain"
                  class="mr-8"
                >
                  {{ tag }}
                </el-tag>
              </template>
              <span v-else class="text-disabled">暂无健康标签</span>
            </el-descriptions-item>
            <el-descriptions-item label="紧急联系人">
              <el-table
                v-if="detail.emergencyContact.length"
                :data="detail.emergencyContact"
                size="small"
                border
                style="width: 100%"
              >
                <el-table-column prop="name" label="姓名" width="140" />
                <el-table-column prop="relation" label="关系" width="120" />
                <el-table-column prop="phone" label="联系电话" min-width="160" />
                <el-table-column label="主联系人" width="120" align="center">
                  <template #default="{ row }">
                    <el-tag v-if="row.primary" size="small" type="success">是</el-tag>
                    <span v-else class="text-disabled">否</span>
                  </template>
                </el-table-column>
              </el-table>
              <span v-else class="text-disabled">暂无紧急联系人</span>
            </el-descriptions-item>
          </el-descriptions>
        </section>

        <!-- 3. 设备信息 -->
        <section class="detail-block">
          <h3 class="detail-block__title">三、绑定设备信息</h3>
          <template v-if="detail.devices.length">
            <el-descriptions
              v-for="dev in detail.devices"
              :key="dev.id"
              :column="3"
              border
              class="mb-12"
            >
              <el-descriptions-item label="设备号">
                <el-link type="primary" :underline="false" @click="router.push(`/device/detail/${dev.id}`)">
                  {{ dev.deviceNo }}
                </el-link>
              </el-descriptions-item>
              <el-descriptions-item label="设备类型">
                <StatusTag category="deviceType" :status="dev.type" />
              </el-descriptions-item>
              <el-descriptions-item label="运行状态">
                <StatusTag category="deviceStatus" :status="dev.status" />
              </el-descriptions-item>
              <el-descriptions-item label="最后心跳">
                <span :class="{ 'text-danger': dev.status === 1 && isHeartbeatStale(dev.lastHeartbeat) }">
                  {{ formatRelativeTime(dev.lastHeartbeat) }}
                </span>
              </el-descriptions-item>
              <el-descriptions-item label="算法版本">{{ dev.algoVersion }}</el-descriptions-item>
              <el-descriptions-item label="操作">
                <el-button link type="primary" size="small" @click="router.push(`/device/detail/${dev.id}`)">
                  查看设备配置
                </el-button>
              </el-descriptions-item>
            </el-descriptions>
          </template>
          <EmptyState v-else description="该老人暂未绑定任何检测设备" />
        </section>

        <!-- 4. 家属绑定 -->
        <section class="detail-block">
          <div class="detail-block__head">
            <h3 class="detail-block__title">四、家属绑定</h3>
            <el-button
              v-permission="'elder:write'"
              type="primary"
              link
              size="small"
              @click="bindDialogVisible = true"
            >
              + 绑定家属
            </el-button>
          </div>
          <template v-if="detail.families.length">
            <el-descriptions
              v-for="fam in detail.families"
              :key="fam.bindingId"
              :column="5"
              border
              class="mb-12"
            >
              <el-descriptions-item label="姓名">{{ fam.name }}</el-descriptions-item>
              <el-descriptions-item label="关系">{{ fam.relation }}</el-descriptions-item>
              <el-descriptions-item label="手机号">{{ fam.phone }}</el-descriptions-item>
              <el-descriptions-item label="是否主要联系人">
                <el-tag v-if="fam.isPrimary" size="small" type="success">主要联系人</el-tag>
                <el-tag v-else size="small" type="info">普通联系人</el-tag>
              </el-descriptions-item>
              <el-descriptions-item label="通知顺序">
                第 {{ fam.notifyOrder }} 顺位
                <el-button
                  v-permission="'elder:write'"
                  link
                  type="danger"
                  size="small"
                  class="ml-12"
                  @click="handleUnbind(fam.bindingId, fam.name)"
                >
                  解绑
                </el-button>
              </el-descriptions-item>
            </el-descriptions>
          </template>
          <EmptyState v-else description="暂未绑定家属账号" />
        </section>

        <!-- 5. 最近事件（5 条，点击跳转事件详情） -->
        <section class="detail-block">
          <h3 class="detail-block__title">五、最近事件（近 5 条）</h3>
          <template v-if="detail.recentEvents.length">
            <el-descriptions
              v-for="ev in detail.recentEvents"
              :key="ev.id"
              :column="4"
              border
              class="mb-12"
            >
              <el-descriptions-item label="发生时间">
                {{ formatDateTime(ev.occurredAt) }}
              </el-descriptions-item>
              <el-descriptions-item label="事件类型">
                {{ ev.type === 'LONG_LIE' ? '久躺预警' : '跌倒检测' }}
              </el-descriptions-item>
              <el-descriptions-item label="事件级别">
                <StatusTag category="eventLevel" :status="ev.level" />
              </el-descriptions-item>
              <el-descriptions-item label="置信度 / 详情">
                <span class="mr-12">{{ Math.round(ev.confidence * 100) }}%</span>
                <el-button link type="primary" size="small" @click="goEventDetail(ev.id)">
                  查看事件
                </el-button>
              </el-descriptions-item>
            </el-descriptions>
          </template>
          <EmptyState v-else description="近期无异常检测事件" />
        </section>
      </div>
    </PageContainer>

    <!-- 编辑老人弹窗 -->
    <ElderFormDialog v-model="editDialogVisible" :edit-data="elderAsRow" @success="loadDetail" />

    <!-- 绑定家属弹窗 -->
    <el-dialog v-model="bindDialogVisible" title="绑定家属" width="440px" destroy-on-close>
      <el-form :model="bindForm" label-width="96px">
        <el-form-item label="家属姓名">
          <el-input v-model.trim="bindForm.name" placeholder="请输入家属姓名" />
        </el-form-item>
        <el-form-item label="手机号码">
          <el-input v-model.trim="bindForm.phone" placeholder="11 位手机号" maxlength="11" />
        </el-form-item>
        <el-form-item label="亲属关系">
          <el-select v-model="bindForm.relation" style="width: 100%">
            <el-option v-for="r in FAMILY_RELATIONS" :key="r" :label="r" :value="r" />
          </el-select>
        </el-form-item>
        <el-form-item label="通知顺序">
          <el-input-number v-model="bindForm.notifyOrder" :min="1" :max="10" />
        </el-form-item>
        <el-form-item label="主要联系人">
          <el-switch v-model="bindForm.isPrimary" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="bindDialogVisible = false">取 消</el-button>
        <el-button type="primary" :loading="bindingSubmit" @click="submitBindFamily">确 定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ArrowLeft, Edit } from '@element-plus/icons-vue'
import {
  bindElderFamily,
  getElderDetail,
  unbindElderFamily,
  updateElder,
} from '@/api/elder'
import EmptyState from '@/components/EmptyState.vue'
import PageContainer from '@/components/PageContainer.vue'
import StatusTag from '@/components/StatusTag.vue'
import {
  ElderStatus,
  FAMILY_RELATIONS,
  Gender,
  type Elder,
  type ElderDetail,
} from '@/types/elder'
import { formatDateTime, formatRelativeTime, isHeartbeatStale } from '@/utils/time'
import ElderFormDialog from './components/ElderFormDialog.vue'

const route = useRoute()
const router = useRouter()

const loading = ref(false)
const detail = ref<ElderDetail | null>(null)
const editDialogVisible = ref(false)

const elderId = computed(() => String(route.params.id || ''))

const elderAsRow = computed<Elder | null>(() => {
  if (!detail.value) return null
  const d = detail.value
  return {
    id: d.id,
    name: d.name,
    gender: d.gender,
    age: d.age,
    birthDate: d.birthDate,
    phone: d.phone,
    address: d.address,
    roomNo: d.roomNo,
    communityId: d.communityId,
    communityName: d.communityName,
    guardianId: d.guardianId,
    guardianName: d.guardianName,
    healthTags: d.healthTags,
    detectMode: d.detectMode,
    status: d.status,
    deviceOnline: d.devices.some((dev) => dev.status === 1),
    lastAlarmAt: d.recentEvents[0]?.occurredAt ?? null,
    alarmCount30d: d.recentEvents.length,
    createdAt: '',
  }
})

async function loadDetail() {
  if (!elderId.value) return
  loading.value = true
  try {
    detail.value = await getElderDetail(elderId.value)
  } finally {
    loading.value = false
  }
}

function openEdit() {
  editDialogVisible.value = true
}

async function handleDisable() {
  if (!detail.value) return
  await ElMessageBox.confirm(
    `确定停用老人「${detail.value.name}」的档案吗？`,
    '停用确认',
    { type: 'warning' },
  )
  await updateElder(detail.value.id, { status: ElderStatus.PAUSED })
  ElMessage.success('档案状态已更新为暂停')
  await loadDetail()
}

function goEventDetail(eventId: string) {
  router.push({ path: '/event', query: { eventId } })
}

// ---------------- 家属绑定 / 解绑 ----------------
const bindDialogVisible = ref(false)
const bindingSubmit = ref(false)
const bindForm = reactive({
  name: '',
  phone: '',
  relation: '子女',
  isPrimary: true,
  notifyOrder: 1,
})

async function submitBindFamily() {
  if (!detail.value) return
  if (!bindForm.name || !/^1\d{10}$/.test(bindForm.phone)) {
    ElMessage.warning('请填写正确的家属姓名和 11 位手机号')
    return
  }
  bindingSubmit.value = true
  try {
    await bindElderFamily(detail.value.id, { ...bindForm })
    ElMessage.success('绑定家属成功')
    bindDialogVisible.value = false
    bindForm.name = ''
    bindForm.phone = ''
    await loadDetail()
  } finally {
    bindingSubmit.value = false
  }
}

async function handleUnbind(bindingId: string, name: string) {
  if (!detail.value) return
  await ElMessageBox.confirm(`确定解绑家属「${name}」吗？`, '解绑确认', { type: 'warning' })
  await unbindElderFamily(detail.value.id, bindingId)
  ElMessage.success('已解绑')
  await loadDetail()
}

watch(elderId, () => loadDetail(), { immediate: true })
</script>

<style scoped lang="scss">
.elder-detail__blocks {
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
</style>
