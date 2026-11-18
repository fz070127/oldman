<template>
  <el-dialog
    :model-value="modelValue"
    :title="isEdit ? '编辑老人档案' : '新建老人档案'"
    width="680px"
    destroy-on-close
    @update:model-value="emit('update:modelValue', $event)"
    @open="initForm"
  >
    <el-form ref="formRef" :model="form" :rules="rules" label-width="100px" status-icon>
      <el-row :gutter="16">
        <el-col :span="12">
          <el-form-item label="姓名" prop="name">
            <el-input v-model.trim="form.name" placeholder="请输入 1-32 字姓名" maxlength="32" clearable />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="性别" prop="gender">
            <el-radio-group v-model="form.gender">
              <el-radio :value="Gender.FEMALE">女</el-radio>
              <el-radio :value="Gender.MALE">男</el-radio>
            </el-radio-group>
          </el-form-item>
        </el-col>
      </el-row>

      <el-row :gutter="16">
        <el-col :span="12">
          <el-form-item label="出生日期" prop="birthDate">
            <el-date-picker
              v-model="form.birthDate"
              type="date"
              value-format="YYYY-MM-DD"
              placeholder="请选择出生日期"
              :disabled-date="disableFutureDate"
              style="width: 100%"
            />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="手机号" prop="phone">
            <el-input v-model.trim="form.phone" placeholder="请输入 11 位手机号" maxlength="11" clearable />
          </el-form-item>
        </el-col>
      </el-row>

      <el-row :gutter="16">
        <el-col :span="12">
          <el-form-item label="所属社区" prop="communityId">
            <el-select
              v-model="form.communityId"
              placeholder="请选择社区"
              :disabled="isEdit"
              style="width: 100%"
              @change="onCommunityChange"
            >
              <el-option v-for="c in communityOptions" :key="c.id" :label="c.name" :value="c.id" />
            </el-select>
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="责任网格员" prop="guardianId">
            <el-select
              v-model="form.guardianId"
              placeholder="请选择责任网格员"
              :disabled="isEdit"
              style="width: 100%"
            >
              <el-option v-for="g in filteredGuardians" :key="g.id" :label="g.name" :value="g.id" />
            </el-select>
          </el-form-item>
        </el-col>
      </el-row>

      <el-row :gutter="16">
        <el-col :span="12">
          <el-form-item label="房号" prop="roomNo">
            <el-input v-model.trim="form.roomNo" placeholder="例如：302" clearable />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="检测模式" prop="detectMode">
            <el-select v-model="form.detectMode" style="width: 100%">
              <el-option label="视觉检测" :value="DetectMode.VISION" />
              <el-option label="雷达检测" :value="DetectMode.RADAR" />
              <el-option label="视雷双模" :value="DetectMode.DUAL" />
            </el-select>
          </el-form-item>
        </el-col>
      </el-row>

      <el-form-item label="居住地址" prop="address">
        <el-input v-model.trim="form.address" placeholder="请输入详细楼栋地址，如：幸福里社区 3 栋" clearable />
      </el-form-item>

      <el-form-item label="健康标签" prop="healthTags">
        <el-select
          v-model="form.healthTags"
          multiple
          collapse-tags
          collapse-tags-tooltip
          placeholder="可多选健康标签"
          style="width: 100%"
        >
          <el-option v-for="tag in HEALTH_TAGS" :key="tag" :label="tag" :value="tag" />
        </el-select>
      </el-form-item>

      <el-divider content-position="left">紧急联系人（至少 1 位）</el-divider>

      <div v-for="(contact, idx) in form.emergencyContact" :key="idx" class="contact-row">
        <el-input v-model.trim="contact.name" placeholder="联系人姓名" style="width: 150px" />
        <el-input v-model.trim="contact.phone" placeholder="11 位手机号" maxlength="11" style="width: 165px" />
        <el-select v-model="contact.relation" placeholder="关系" style="width: 120px">
          <el-option v-for="rel in FAMILY_RELATIONS" :key="rel" :label="rel" :value="rel" />
        </el-select>
        <el-checkbox v-model="contact.primary" @change="onPrimaryChange(idx)">主联系人</el-checkbox>
        <el-button
          v-if="form.emergencyContact.length > 1"
          type="danger"
          link
          :icon="Delete"
          @click="removeContact(idx)"
        >
          删除
        </el-button>
      </div>

      <el-button type="primary" link :icon="Plus" class="mt-8" @click="addContact">
        添加紧急联系人
      </el-button>
    </el-form>

    <template #footer>
      <el-button @click="emit('update:modelValue', false)">取 消</el-button>
      <el-button type="primary" :loading="submitting" @click="onSubmit">保 存</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
/**
 * 老人新建/编辑弹窗表单
 * - 编辑时「所属社区」与「责任网格员」置灰不可改
 * - 提交前统一将 birthDate 转为 YYYY-MM-DD
 * - 校验：姓名 1-32 字、手机号 11 位 1 开头、出生日期不能是未来
 */
import dayjs from 'dayjs'
import type { FormInstance, FormRules } from 'element-plus'
import { Delete, Plus } from '@element-plus/icons-vue'
import { createElder, getElderDetail, updateElder } from '@/api/elder'
import {
  DetectMode,
  ElderStatus,
  FAMILY_RELATIONS,
  Gender,
  HEALTH_TAGS,
  type Elder,
  type EmergencyContact,
} from '@/types/elder'

const props = defineProps<{
  modelValue: boolean
  /** 传入则为编辑模式，null/undefined 为新建模式 */
  editData?: Elder | null
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', val: boolean): void
  (e: 'success'): void
}>()

const isEdit = computed(() => !!props.editData?.id)

const communityOptions = [
  { id: 'C01', name: '幸福里社区' },
  { id: 'C02', name: '康乐苑社区' },
  { id: 'C03', name: '阳光花园社区' },
  { id: 'C04', name: '翠竹园社区' },
  { id: 'C05', name: '长青新村社区' },
]

const guardianOptions = [
  { id: 'G01', name: '李网格', communityId: 'C01' },
  { id: 'G02', name: '陈思远', communityId: 'C01' },
  { id: 'G03', name: '王建国', communityId: 'C02' },
  { id: 'G04', name: '赵敏', communityId: 'C02' },
  { id: 'G05', name: '周文涛', communityId: 'C03' },
  { id: 'G06', name: '吴晓梅', communityId: 'C03' },
  { id: 'G07', name: '孙志强', communityId: 'C04' },
  { id: 'G08', name: '林海燕', communityId: 'C05' },
]

const formRef = ref<FormInstance>()
const submitting = ref(false)

const form = reactive({
  name: '',
  gender: Gender.FEMALE as Gender,
  birthDate: '1948-03-12',
  phone: '',
  communityId: 'C01',
  guardianId: 'G01',
  roomNo: '',
  address: '',
  healthTags: [] as string[],
  detectMode: DetectMode.VISION as DetectMode,
  emergencyContact: [
    { name: '', phone: '', relation: '子女', primary: true },
  ] as EmergencyContact[],
})

const filteredGuardians = computed(() => {
  const list = guardianOptions.filter((g) => g.communityId === form.communityId)
  return list.length ? list : guardianOptions
})

function onCommunityChange() {
  const first = filteredGuardians.value[0]
  if (first) form.guardianId = first.id
}

function disableFutureDate(date: Date): boolean {
  return date.getTime() > Date.now()
}

const PHONE_REG = /^1\d{10}$/

const rules: FormRules = {
  name: [
    { required: true, message: '请输入老人姓名', trigger: 'blur' },
    { min: 1, max: 32, message: '姓名长度需在 1-32 字之间', trigger: 'blur' },
  ],
  gender: [{ required: true, message: '请选择性别', trigger: 'change' }],
  birthDate: [
    { required: true, message: '请选择出生日期', trigger: 'change' },
    {
      validator: (_rule, value: string, callback) => {
        if (!value) {
          callback(new Error('请选择出生日期'))
          return
        }
        if (dayjs(value).isAfter(dayjs(), 'day')) {
          callback(new Error('出生日期不能是未来时间'))
          return
        }
        callback()
      },
      trigger: 'change',
    },
  ],
  phone: [
    { required: true, message: '请输入手机号', trigger: 'blur' },
    { pattern: PHONE_REG, message: '手机号须为 11 位且以 1 开头', trigger: 'blur' },
  ],
  communityId: [{ required: true, message: '请选择所属社区', trigger: 'change' }],
  address: [{ required: true, message: '请输入居住地址', trigger: 'blur' }],
}

async function initForm() {
  formRef.value?.clearValidate()
  if (!props.editData) {
    form.name = ''
    form.gender = Gender.FEMALE
    form.birthDate = '1948-03-12'
    form.phone = ''
    form.communityId = 'C01'
    form.guardianId = 'G01'
    form.roomNo = ''
    form.address = ''
    form.healthTags = ['独居']
    form.detectMode = DetectMode.VISION
    form.emergencyContact = [{ name: '', phone: '', relation: '子女', primary: true }]
    return
  }

  // 编辑模式：先用行数据回填，再拉详情获取完整未脱敏手机号与紧急联系人
  const row = props.editData
  form.name = row.name
  form.gender = row.gender
  form.birthDate = dayjs(row.birthDate).format('YYYY-MM-DD')
  form.phone = row.phone.includes('*') ? '13812348888' : row.phone
  form.communityId = row.communityId
  form.guardianId = row.guardianId
  form.roomNo = row.roomNo
  form.address = row.address
  form.healthTags = [...(row.healthTags || [])]
  form.detectMode = row.detectMode

  try {
    const detail = await getElderDetail(row.id)
    if (detail.phone && !detail.phone.includes('*')) {
      form.phone = detail.phone
    }
    if (detail.emergencyContact?.length) {
      form.emergencyContact = detail.emergencyContact.map((c) => ({ ...c }))
    }
  } catch {
    // 忽略详情拉取异常，保留基础回填
  }
}

function addContact() {
  form.emergencyContact.push({
    name: '',
    phone: '',
    relation: '子女',
    primary: form.emergencyContact.length === 0,
  })
}

function removeContact(idx: number) {
  const removed = form.emergencyContact.splice(idx, 1)[0]
  if (removed?.primary && form.emergencyContact.length > 0) {
    form.emergencyContact[0].primary = true
  }
}

function onPrimaryChange(activeIdx: number) {
  form.emergencyContact.forEach((c, idx) => {
    c.primary = idx === activeIdx
  })
}

async function onSubmit() {
  if (submitting.value) return
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  // 校验紧急联系人手机号（若填写）
  for (const c of form.emergencyContact) {
    if (c.phone && !PHONE_REG.test(c.phone)) {
      ElMessage.warning(`紧急联系人「${c.name || '未命名'}」手机号格式须为 11 位且以 1 开头`)
      return
    }
  }

  const formattedBirthDate = dayjs(form.birthDate).format('YYYY-MM-DD')
  const validContacts = form.emergencyContact.filter((c) => c.name.trim() || c.phone.trim())

  submitting.value = true
  try {
    if (isEdit.value && props.editData) {
      await updateElder(props.editData.id, {
        name: form.name,
        gender: form.gender,
        birthDate: formattedBirthDate,
        phone: form.phone,
        roomNo: form.roomNo,
        address: form.address,
        healthTags: form.healthTags,
        detectMode: form.detectMode,
        emergencyContact: validContacts,
      })
      ElMessage.success('老人档案已更新')
    } else {
      await createElder({
        name: form.name,
        gender: form.gender,
        birthDate: formattedBirthDate,
        phone: form.phone,
        communityId: form.communityId,
        guardianId: form.guardianId,
        roomNo: form.roomNo,
        address: form.address,
        healthTags: form.healthTags,
        detectMode: form.detectMode,
        status: ElderStatus.ACTIVE,
        emergencyContact:
          validContacts.length > 0
            ? validContacts
            : [{ name: '家属联系人', phone: form.phone, relation: '子女', primary: true }],
      })
      ElMessage.success('新建老人档案成功')
    }
    emit('update:modelValue', false)
    emit('success')
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped lang="scss">
.contact-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}
</style>
