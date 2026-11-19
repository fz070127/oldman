<template>
  <div class="system-users-page">
    <SearchForm :model-value="searchParams" @search="handleSearch" @reset="handleReset">
      <el-form-item label="关键字">
        <el-input
          v-model.trim="searchParams.keyword"
          placeholder="搜索账号 / 昵称 / 手机号"
          clearable
          style="width: 220px"
          @keyup.enter="handleSearch"
        />
      </el-form-item>

      <el-form-item label="角色">
        <el-select v-model="searchParams.roleCode" placeholder="全部角色" clearable style="width: 150px">
          <el-option
            v-for="(label, code) in ROLE_NAME_MAP"
            :key="code"
            :label="label"
            :value="code"
          />
        </el-select>
      </el-form-item>

      <el-form-item label="状态">
        <el-select v-model="searchParams.status" placeholder="全部状态" clearable style="width: 130px">
          <el-option label="启用" :value="1" />
          <el-option label="停用" :value="2" />
        </el-select>
      </el-form-item>
    </SearchForm>

    <PageContainer title="系统用户管理">
      <template #extra>
        <el-button type="primary" :icon="Plus" @click="openCreate">新建用户</el-button>
      </template>

      <ProTable
        ref="tableRef"
        :columns="columns"
        :request="fetchUsers"
        :search-params="searchParams"
      >
        <template #roleCode="{ row }">
          <el-tag size="small" effect="plain">
            {{ ROLE_NAME_MAP[row.roleCode as RoleCode] || row.roleCode }}
          </el-tag>
        </template>

        <template #status="{ row }">
          <el-tag :type="row.status === 1 ? 'success' : 'info'" size="small">
            {{ row.status === 1 ? '启用' : '已停用' }}
          </el-tag>
        </template>

        <template #lastLoginAt="{ row }">
          <span>{{ formatDateTime(row.lastLoginAt) }}</span>
        </template>

        <template #actions="{ row }">
          <el-button link type="primary" size="small" @click="openEdit(row)">编辑</el-button>
          <el-button
            v-if="row.username !== 'admin'"
            link
            :type="row.status === 1 ? 'warning' : 'success'"
            size="small"
            @click="handleToggleStatus(row)"
          >
            {{ row.status === 1 ? '停用' : '启用' }}
          </el-button>
          <el-button
            v-if="row.username !== 'admin'"
            link
            type="danger"
            size="small"
            @click="handleDelete(row)"
          >
            删除
          </el-button>
        </template>
      </ProTable>
    </PageContainer>

    <el-dialog
      v-model="dialogVisible"
      :title="editingId ? '编辑用户' : '新建用户'"
      width="480px"
      destroy-on-close
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="92px" status-icon>
        <el-form-item label="登录账号" prop="username">
          <el-input
            v-model.trim="form.username"
            :disabled="Boolean(editingId)"
            placeholder="请输入 3-24 位字母或数字账号"
            maxlength="24"
          />
        </el-form-item>
        <el-form-item label="用户昵称" prop="nickname">
          <el-input v-model.trim="form.nickname" placeholder="请输入姓名或昵称" maxlength="32" />
        </el-form-item>
        <el-form-item label="手机号码" prop="phone">
          <el-input v-model.trim="form.phone" placeholder="请输入 11 位手机号" maxlength="11" />
        </el-form-item>
        <el-form-item label="角色权限" prop="roleCode">
          <el-select v-model="form.roleCode" style="width: 100%">
            <el-option
              v-for="(label, code) in ROLE_NAME_MAP"
              :key="code"
              :label="label"
              :value="code"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="所属社区" prop="communityId">
          <el-select v-model="form.communityId" style="width: 100%">
            <el-option v-for="c in communityOptions" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取 消</el-button>
        <el-button type="primary" :loading="submitting" :disabled="submitting" @click="submitForm">
          保 存
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import type { FormInstance, FormRules } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import {
  createSystemUser,
  deleteSystemUser,
  getSystemUsers,
  updateSystemUser,
} from '@/api/system'
import PageContainer from '@/components/PageContainer.vue'
import ProTable, { type ProTableColumn, type ProTableInstance } from '@/components/ProTable.vue'
import SearchForm from '@/components/SearchForm.vue'
import type { SystemUser } from '@/types/system'
import { ROLE_NAME_MAP, RoleCode } from '@/types/user'
import { formatDateTime } from '@/utils/time'

const tableRef = ref<ProTableInstance<SystemUser>>()

const communityOptions = [
  { id: 'C01', name: '幸福里社区' },
  { id: 'C02', name: '康乐苑社区' },
  { id: 'C03', name: '阳光花园社区' },
  { id: 'C04', name: '翠竹园社区' },
  { id: 'C05', name: '长青新村社区' },
]

const searchParams = reactive({
  keyword: '',
  roleCode: '',
  status: '' as number | '',
})

const columns: ProTableColumn<SystemUser>[] = [
  { prop: 'username', label: '登录账号', width: 130 },
  { prop: 'nickname', label: '昵称 / 姓名', width: 130 },
  { prop: 'phone', label: '手机号码', width: 135 },
  { prop: 'roleCode', label: '所属角色', width: 130, slot: 'roleCode' },
  { prop: 'communityName', label: '所属社区', minWidth: 140 },
  { prop: 'status', label: '状态', width: 95, align: 'center', slot: 'status' },
  { prop: 'lastLoginAt', label: '最后登录时间', minWidth: 165, slot: 'lastLoginAt' },
  { label: '操作', width: 170, fixed: 'right', slot: 'actions', showOverflowTooltip: false },
]

function fetchUsers(params: Record<string, unknown>) {
  return getSystemUsers(params)
}

function handleSearch() {
  tableRef.value?.reload(true)
}

function handleReset() {
  searchParams.keyword = ''
  searchParams.roleCode = ''
  searchParams.status = ''
  tableRef.value?.reload(true)
}

// ---------------- 新建 / 编辑 / 停用 / 删除 ----------------
const dialogVisible = ref(false)
const submitting = ref(false)
const editingId = ref('')
const formRef = ref<FormInstance>()

const form = reactive({
  username: '',
  nickname: '',
  phone: '',
  roleCode: RoleCode.GUARDIAN as RoleCode,
  communityId: 'C01',
})

const rules: FormRules = {
  username: [
    { required: true, message: '请输入登录账号', trigger: 'blur' },
    { min: 3, max: 24, message: '账号长度需在 3-24 位之间', trigger: 'blur' },
  ],
  nickname: [{ required: true, message: '请输入用户昵称', trigger: 'blur' }],
  phone: [
    { required: true, message: '请输入手机号码', trigger: 'blur' },
    { pattern: /^1\d{10}$/, message: '请输入以 1 开头的 11 位手机号', trigger: 'blur' },
  ],
  roleCode: [{ required: true, message: '请选择角色', trigger: 'change' }],
  communityId: [{ required: true, message: '请选择所属社区', trigger: 'change' }],
}

function openCreate() {
  editingId.value = ''
  form.username = ''
  form.nickname = ''
  form.phone = ''
  form.roleCode = RoleCode.GUARDIAN
  form.communityId = 'C01'
  dialogVisible.value = true
}

function openEdit(row: SystemUser) {
  editingId.value = row.id
  form.username = row.username
  form.nickname = row.nickname
  form.phone = row.phone
  form.roleCode = row.roleCode
  form.communityId = row.communityId
  dialogVisible.value = true
}

async function submitForm() {
  if (submitting.value) return
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    if (editingId.value) {
      await updateSystemUser(editingId.value, { ...form })
      ElMessage.success('用户信息已更新')
    } else {
      await createSystemUser({ ...form })
      ElMessage.success('新建用户成功')
    }
    dialogVisible.value = false
    tableRef.value?.reload(false)
  } finally {
    submitting.value = false
  }
}

async function handleToggleStatus(row: SystemUser) {
  const nextStatus = row.status === 1 ? 2 : 1
  const actionLabel = nextStatus === 2 ? '停用' : '启用'
  await ElMessageBox.confirm(
    `确定要${actionLabel}用户「${row.nickname}（${row.username}）」吗？`,
    `${actionLabel}确认`,
    { type: 'warning', confirmButtonText: `确定${actionLabel}`, cancelButtonText: '取消' },
  )
  await updateSystemUser(row.id, { status: nextStatus })
  ElMessage.success(`已${actionLabel}用户「${row.nickname}」`)
  tableRef.value?.reload(false)
}

async function handleDelete(row: SystemUser) {
  await ElMessageBox.confirm(
    `确定删除用户「${row.nickname}（${row.username}）」吗？此操作不可恢复。`,
    '删除确认',
    { type: 'warning', confirmButtonText: '确定删除', cancelButtonText: '取消' },
  )
  await deleteSystemUser(row.id)
  ElMessage.success(`已删除用户「${row.nickname}」`)
  tableRef.value?.reload(false)
}
</script>
