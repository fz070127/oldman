<template>
  <!-- 1. 确认告警弹窗（POST /alarms/{id}/ack） -->
  <el-dialog
    :model-value="ackVisible"
    title="确认告警接警"
    width="460px"
    destroy-on-close
    @update:model-value="emit('update:ackVisible', $event)"
  >
    <div v-if="targetAlarm" class="dialog-summary">
      <StatusTag category="eventLevel" :status="targetAlarm.level" />
      <span class="dialog-summary__name">{{ targetAlarm.elderName }}</span>
      <span class="dialog-summary__room">{{ targetAlarm.roomNo }} 室</span>
      <span class="dialog-summary__id">#{{ targetAlarm.id }}</span>
    </div>
    <el-form label-width="84px">
      <el-form-item label="确认备注">
        <el-input
          v-model="ackNote"
          type="textarea"
          :rows="3"
          maxlength="200"
          show-word-limit
          placeholder="选填：如已电话联系老人/家属，正在核实情况..."
        />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="emit('update:ackVisible', false)">取 消</el-button>
      <el-button type="primary" :loading="submitting" @click="submitAck">
        确认我已处理
      </el-button>
    </template>
  </el-dialog>

  <!-- 2. 派单给网格员弹窗（POST /alarms/{id}/dispatch） -->
  <el-dialog
    :model-value="dispatchVisible"
    title="派单给责任网格员"
    width="480px"
    destroy-on-close
    @update:model-value="emit('update:dispatchVisible', $event)"
  >
    <div v-if="targetAlarm" class="dialog-summary">
      <StatusTag category="eventLevel" :status="targetAlarm.level" />
      <span class="dialog-summary__name">{{ targetAlarm.elderName }}</span>
      <span class="dialog-summary__room">{{ targetAlarm.roomNo }} 室</span>
      <span class="dialog-summary__id">#{{ targetAlarm.id }}</span>
    </div>
    <el-form label-width="92px">
      <el-form-item label="指派网格员" required>
        <el-select v-model="selectedGuardianId" placeholder="请选择网格员" style="width: 100%">
          <el-option
            v-for="g in guardians"
            :key="g.id"
            :label="`${g.name}（${g.communityName} · ${g.phone}）`"
            :value="g.id"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="派单说明">
        <el-input
          v-model="dispatchNote"
          type="textarea"
          :rows="3"
          maxlength="200"
          show-word-limit
          placeholder="选填：请立即上门核查老人状态并回传现场情况"
        />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="emit('update:dispatchVisible', false)">取 消</el-button>
      <el-button type="warning" :loading="submitting" @click="submitDispatch">
        立即派单
      </el-button>
    </template>
  </el-dialog>

  <!-- 3. 完结 / 标记误报弹窗（POST /alarms/{id}/resolve） -->
  <el-dialog
    :model-value="resolveVisible"
    :title="resolveForm.result === EventHandleResult.FALSE_POSITIVE ? '标记误报并完结' : '完结告警处置'"
    width="500px"
    destroy-on-close
    @update:model-value="emit('update:resolveVisible', $event)"
  >
    <div v-if="targetAlarm" class="dialog-summary">
      <StatusTag category="eventLevel" :status="targetAlarm.level" />
      <span class="dialog-summary__name">{{ targetAlarm.elderName }}</span>
      <span class="dialog-summary__room">{{ targetAlarm.roomNo }} 室</span>
      <span class="dialog-summary__id">#{{ targetAlarm.id }}</span>
    </div>
    <el-form label-width="96px">
      <el-form-item label="处置结论" required>
        <el-radio-group v-model="resolveForm.result">
          <el-radio :value="EventHandleResult.TRUE_FALL">真实跌倒/异常（已妥善处置）</el-radio>
          <el-radio :value="EventHandleResult.FALSE_POSITIVE">误报（自动同步事件为误报）</el-radio>
        </el-radio-group>
      </el-form-item>
      <el-form-item label="后续跟进">
        <el-switch
          v-model="resolveForm.needFollowUp"
          active-text="需要社区定期回访跟进"
          inactive-text="无需额外回访"
        />
      </el-form-item>
      <el-form-item label="完结说明">
        <el-input
          v-model="resolveForm.note"
          type="textarea"
          :rows="3"
          maxlength="200"
          show-word-limit
          :placeholder="
            resolveForm.result === EventHandleResult.FALSE_POSITIVE
              ? '选填：经核实老人弯腰捡物/坐卧触发误报，已确认无碍'
              : '选填：已上门协助老人起身并通知家属，老人身体无大碍'
          "
        />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="emit('update:resolveVisible', false)">取 消</el-button>
      <el-button
        :type="resolveForm.result === EventHandleResult.FALSE_POSITIVE ? 'info' : 'success'"
        :loading="submitting"
        @click="submitResolve"
      >
        确认完结
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
/**
 * 告警处置三大弹窗：确认（ack）、派单（dispatch）、完结/误报（resolve）
 * 列表页与详情抽屉共用
 */
import { ackAlarm, dispatchAlarm, resolveAlarm } from '@/api/alarm'
import { getGuardianList } from '@/api/system'
import StatusTag from '@/components/StatusTag.vue'
import type { AlarmDetail } from '@/types/alarm'
import { EventHandleResult, type EventLevel } from '@/types/event'
import type { Guardian } from '@/types/system'

export interface AlarmDialogTarget {
  id: string
  level: EventLevel
  elderName: string
  roomNo: string
}

const props = withDefaults(
  defineProps<{
    targetAlarm: AlarmDialogTarget | null
    ackVisible: boolean
    dispatchVisible: boolean
    resolveVisible: boolean
    defaultResolveResult?: EventHandleResult
  }>(),
  {
    defaultResolveResult: EventHandleResult.TRUE_FALL,
  },
)

const emit = defineEmits<{
  (e: 'update:ackVisible', val: boolean): void
  (e: 'update:dispatchVisible', val: boolean): void
  (e: 'update:resolveVisible', val: boolean): void
  (e: 'success', detail: AlarmDetail): void
}>()

const submitting = ref(false)

// ---------------- 1. 确认 ----------------
const ackNote = ref('')

watch(
  () => props.ackVisible,
  (v) => {
    if (v) ackNote.value = ''
  },
)

async function submitAck() {
  if (!props.targetAlarm || submitting.value) return
  submitting.value = true
  try {
    const detail = await ackAlarm(props.targetAlarm.id, {
      note: ackNote.value.trim() || undefined,
    })
    ElMessage.success('已确认接警')
    emit('update:ackVisible', false)
    emit('success', detail)
  } finally {
    submitting.value = false
  }
}

// ---------------- 2. 派单 ----------------
const guardians = ref<Guardian[]>([])
const selectedGuardianId = ref('')
const dispatchNote = ref('')

async function ensureGuardians() {
  if (guardians.value.length > 0) return
  const res = await getGuardianList({ page: 1, pageSize: 50 }).catch(() => null)
  guardians.value = res?.list || []
  if (guardians.value.length > 0 && !selectedGuardianId.value) {
    selectedGuardianId.value = guardians.value[0].id
  }
}

watch(
  () => props.dispatchVisible,
  async (v) => {
    if (!v) return
    dispatchNote.value = ''
    await ensureGuardians()
    if (guardians.value.length > 0 && !selectedGuardianId.value) {
      selectedGuardianId.value = guardians.value[0].id
    }
  },
)

async function submitDispatch() {
  if (!props.targetAlarm || submitting.value) return
  if (!selectedGuardianId.value) {
    ElMessage.warning('请选择要指派的网格员')
    return
  }
  submitting.value = true
  try {
    const detail = await dispatchAlarm(props.targetAlarm.id, {
      guardianId: selectedGuardianId.value,
      note: dispatchNote.value.trim() || '请立即上门核查老人状态',
    })
    ElMessage.success('已派单至责任网格员')
    emit('update:dispatchVisible', false)
    emit('success', detail)
  } finally {
    submitting.value = false
  }
}

// ---------------- 3. 完结 / 标记误报 ----------------
const resolveForm = reactive({
  result: EventHandleResult.TRUE_FALL as EventHandleResult,
  needFollowUp: false,
  note: '',
})

watch(
  () => props.resolveVisible,
  (v) => {
    if (!v) return
    resolveForm.result = props.defaultResolveResult || EventHandleResult.TRUE_FALL
    resolveForm.needFollowUp = false
    resolveForm.note = ''
  },
)

async function submitResolve() {
  if (!props.targetAlarm || submitting.value) return
  const isFalse = resolveForm.result === EventHandleResult.FALSE_POSITIVE
  const fallbackNote = isFalse ? '经核实为误报并关闭' : '已上门核实处置，老人安全'
  submitting.value = true
  try {
    const detail = await resolveAlarm(props.targetAlarm.id, {
      result: resolveForm.result,
      needFollowUp: resolveForm.needFollowUp,
      note: resolveForm.note.trim() || fallbackNote,
    })
    ElMessage.success(isFalse ? '已标记为误报并完结' : '告警已完结')
    emit('update:resolveVisible', false)
    emit('success', detail)
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped lang="scss">
.dialog-summary {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  margin-bottom: 16px;
  background: #f7f8fa;
  border: 1px solid $border-color-light;
  border-radius: 6px;

  &__name {
    font-size: 15px;
    font-weight: 700;
    color: $text-primary;
  }

  &__room {
    font-size: 13px;
    color: $text-regular;
  }

  &__id {
    margin-left: auto;
    font-family: monospace;
    font-size: 12px;
    color: $text-regular;
  }
}
</style>
