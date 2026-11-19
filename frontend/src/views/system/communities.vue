<template>
  <div class="system-communities-page">
    <SearchForm :model-value="searchParams" @search="handleSearch" @reset="handleReset">
      <el-form-item label="关键字">
        <el-input
          v-model.trim="searchParams.keyword"
          placeholder="搜索社区名称 / 地址 / 负责人"
          clearable
          style="width: 240px"
          @keyup.enter="handleSearch"
        />
      </el-form-item>
    </SearchForm>

    <PageContainer title="社区档案管理">
      <template #extra>
        <el-button type="primary" :icon="Plus" @click="openCreate">新建社区</el-button>
      </template>

      <ProTable
        ref="tableRef"
        :columns="columns"
        :request="fetchCommunities"
        :search-params="searchParams"
      >
        <template #createdAt="{ row }">
          <span>{{ formatDateTime(row.createdAt) }}</span>
        </template>

        <template #actions="{ row }">
          <el-button link type="primary" size="small" @click="openEdit(row)">编辑</el-button>
          <el-button link type="danger" size="small" @click="handleDelete(row)">删除</el-button>
        </template>
      </ProTable>
    </PageContainer>

    <el-dialog
      v-model="dialogVisible"
      :title="editingId ? '编辑社区' : '新建社区'"
      width="480px"
      destroy-on-close
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="96px" status-icon>
        <el-form-item label="社区名称" prop="name">
          <el-input v-model.trim="form.name" placeholder="请输入社区名称" maxlength="32" />
        </el-form-item>
        <el-form-item label="社区地址" prop="address">
          <el-input v-model.trim="form.address" placeholder="请输入详细街道地址" maxlength="100" />
        </el-form-item>
        <el-form-item label="负责人姓名" prop="contactName">
          <el-input v-model.trim="form.contactName" placeholder="请输入社区联系人" maxlength="24" />
        </el-form-item>
        <el-form-item label="联系电话" prop="contactPhone">
          <el-input v-model.trim="form.contactPhone" placeholder="请输入 11 位手机号" maxlength="11" />
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
  createSystemCommunity,
  deleteSystemCommunity,
  getSystemCommunities,
  updateSystemCommunity,
} from '@/api/system'
import PageContainer from '@/components/PageContainer.vue'
import ProTable, { type ProTableColumn, type ProTableInstance } from '@/components/ProTable.vue'
import SearchForm from '@/components/SearchForm.vue'
import type { Community } from '@/types/system'
import { formatDateTime } from '@/utils/time'

const tableRef = ref<ProTableInstance<Community>>()

const searchParams = reactive({
  keyword: '',
})

const columns: ProTableColumn<Community>[] = [
  { prop: 'id', label: '社区编号', width: 110 },
  { prop: 'name', label: '社区名称', width: 160 },
  { prop: 'address', label: '详细地址', minWidth: 220 },
  { prop: 'contactName', label: '负责人', width: 120 },
  { prop: 'contactPhone', label: '联系电话', width: 140 },
  { prop: 'createdAt', label: '建档时间', width: 170, slot: 'createdAt' },
  { label: '操作', width: 140, fixed: 'right', slot: 'actions', showOverflowTooltip: false },
]

function fetchCommunities(params: Record<string, unknown>) {
  return getSystemCommunities(params)
}

function handleSearch() {
  tableRef.value?.reload(true)
}

function handleReset() {
  searchParams.keyword = ''
  tableRef.value?.reload(true)
}

// ---------------- 新建 / 编辑 / 删除 ----------------
const dialogVisible = ref(false)
const submitting = ref(false)
const editingId = ref('')
const formRef = ref<FormInstance>()

const form = reactive({
  name: '',
  address: '',
  contactName: '',
  contactPhone: '',
})

const rules: FormRules = {
  name: [{ required: true, message: '请输入社区名称', trigger: 'blur' }],
  address: [{ required: true, message: '请输入社区地址', trigger: 'blur' }],
  contactName: [{ required: true, message: '请输入负责人姓名', trigger: 'blur' }],
  contactPhone: [
    { required: true, message: '请输入联系电话', trigger: 'blur' },
    { pattern: /^1\d{10}$/, message: '请输入以 1 开头的 11 位手机号', trigger: 'blur' },
  ],
}

function openCreate() {
  editingId.value = ''
  form.name = ''
  form.address = ''
  form.contactName = ''
  form.contactPhone = ''
  dialogVisible.value = true
}

function openEdit(row: Community) {
  editingId.value = row.id
  form.name = row.name
  form.address = row.address
  form.contactName = row.contactName
  form.contactPhone = row.contactPhone
  dialogVisible.value = true
}

async function submitForm() {
  if (submitting.value) return
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    if (editingId.value) {
      await updateSystemCommunity(editingId.value, { ...form })
      ElMessage.success('社区信息已更新')
    } else {
      await createSystemCommunity({ ...form })
      ElMessage.success('新建社区成功')
    }
    dialogVisible.value = false
    tableRef.value?.reload(false)
  } finally {
    submitting.value = false
  }
}

async function handleDelete(row: Community) {
  await ElMessageBox.confirm(
    `确定删除社区「${row.name}」吗？删除后关联的网格归属需重新分配。`,
    '删除确认',
    { type: 'warning', confirmButtonText: '确定删除', cancelButtonText: '取消' },
  )
  await deleteSystemCommunity(row.id)
  ElMessage.success(`已删除社区「${row.name}」`)
  tableRef.value?.reload(false)
}
</script>
