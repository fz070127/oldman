<template>
  <!-- 老人设备在线状态：绿点 + 在线 / 灰点 + 离线 / 无设备（不显示点） -->
  <span v-if="category === 'elderOnline'" class="status-dot-wrap">
    <template v-if="hasDevice === false">
      <span class="status-dot__text is-muted">无设备</span>
    </template>
    <template v-else-if="status === true || status === 'true' || status === 1">
      <span class="status-dot is-online" />
      <span class="status-dot__text is-online">在线</span>
    </template>
    <template v-else>
      <span class="status-dot is-offline" />
      <span class="status-dot__text is-offline">离线</span>
    </template>
  </span>

  <!-- 其余枚举状态标签 -->
  <el-tag
    v-else
    :size="size"
    :effect="effect"
    :class="['status-tag', badge.className]"
    disable-transitions
  >
    {{ badge.label }}
  </el-tag>
</template>

<script setup lang="ts">
/**
 * 统一状态标签组件（老人状态 / 设备状态 / 告警与事件级别 / 告警状态 / 设备在线通用）
 *
 * 状态映射要求：
 * - elder.status:  1 在册（绿）/ 2 暂停（灰）/ 3 离世（深灰）
 * - device.status: 0 未激活（灰）/ 1 在线（绿）/ 2 离线（红）/ 3 故障（橙）
 * - level:         P0（红）/ P1（橙）/ P2（蓝）
 * - elderOnline:   绿点 + 在线 / 灰点 + 离线 / 无设备（不显示点）
 */
export type StatusCategory =
  | 'elderStatus'
  | 'deviceStatus'
  | 'elderOnline'
  | 'eventLevel'
  | 'alarmStatus'
  | 'deviceType'
  | 'detectMode'

const props = withDefaults(
  defineProps<{
    category: StatusCategory
    status?: string | number | boolean | null
    /** 仅 category='elderOnline' 时使用：false 表示未绑定设备（显示“无设备”且不显示圆点） */
    hasDevice?: boolean
    size?: 'small' | 'default' | 'large'
    effect?: 'light' | 'dark' | 'plain'
  }>(),
  {
    status: '',
    hasDevice: true,
    size: 'small',
    effect: 'light',
  },
)

interface BadgeConfig {
  label: string
  className: string
}

const ELDER_STATUS_MAP: Record<number, BadgeConfig> = {
  1: { label: '在册', className: 'is-green' },
  2: { label: '暂停', className: 'is-gray' },
  3: { label: '离世', className: 'is-dark-gray' },
}

const DEVICE_STATUS_MAP: Record<number, BadgeConfig> = {
  0: { label: '未激活', className: 'is-gray' },
  1: { label: '在线', className: 'is-green' },
  2: { label: '离线', className: 'is-red' },
  3: { label: '故障', className: 'is-orange' },
}

const EVENT_LEVEL_MAP: Record<string, BadgeConfig> = {
  P0: { label: 'P0 紧急', className: 'is-red' },
  P1: { label: 'P1 重要', className: 'is-orange' },
  P2: { label: 'P2 一般', className: 'is-blue' },
}

const ALARM_STATUS_MAP: Record<string, BadgeConfig> = {
  PENDING: { label: '待确认', className: 'is-red' },
  ACKNOWLEDGED: { label: '已确认', className: 'is-blue' },
  ESCALATED: { label: '已升级', className: 'is-orange' },
  COMMUNITY_DISPATCHED: { label: '已派单', className: 'is-orange' },
  RESOLVED: { label: '已完结', className: 'is-green' },
  FALSE_POSITIVE: { label: '误报', className: 'is-gray' },
}

const DEVICE_TYPE_MAP: Record<number, BadgeConfig> = {
  1: { label: '边缘盒子', className: 'is-blue' },
  2: { label: 'IPC 摄像机', className: 'is-blue' },
  3: { label: '毫米波雷达', className: 'is-blue' },
}

const DETECT_MODE_MAP: Record<number, BadgeConfig> = {
  1: { label: '视觉检测', className: 'is-blue' },
  2: { label: '雷达检测', className: 'is-blue' },
  3: { label: '视雷双模', className: 'is-green' },
}

const badge = computed<BadgeConfig>(() => {
  const val = props.status
  switch (props.category) {
    case 'elderStatus':
      return ELDER_STATUS_MAP[Number(val)] ?? { label: '未知', className: 'is-gray' }
    case 'deviceStatus':
      return DEVICE_STATUS_MAP[Number(val)] ?? { label: '未知', className: 'is-gray' }
    case 'eventLevel':
      return EVENT_LEVEL_MAP[String(val)] ?? { label: String(val || '-'), className: 'is-gray' }
    case 'alarmStatus':
      return ALARM_STATUS_MAP[String(val)] ?? { label: String(val || '-'), className: 'is-gray' }
    case 'deviceType':
      return DEVICE_TYPE_MAP[Number(val)] ?? { label: '未知设备', className: 'is-gray' }
    case 'detectMode':
      return DETECT_MODE_MAP[Number(val)] ?? { label: '未知模式', className: 'is-gray' }
    default:
      return { label: String(val ?? '-'), className: 'is-gray' }
  }
})
</script>

<style scoped lang="scss">
.status-tag {
  font-weight: 500;
  border-width: 1px;

  &.is-green {
    color: #237804;
    background-color: #f6ffed;
    border-color: #b7eb8f;
  }

  &.is-gray {
    color: #646a73;
    background-color: #f2f3f5;
    border-color: #dcdfe6;
  }

  &.is-dark-gray {
    color: #ffffff;
    background-color: #4e5969;
    border-color: #4e5969;
  }

  &.is-red {
    color: #cf1322;
    background-color: #fff1f0;
    border-color: #ffa39e;
  }

  &.is-orange {
    color: #d46b08;
    background-color: #fff7e6;
    border-color: #ffd591;
  }

  &.is-blue {
    color: #0958d9;
    background-color: #e6f4ff;
    border-color: #91caff;
  }
}

.status-dot-wrap {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
}

.status-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;

  &.is-online {
    background-color: $color-success;
    box-shadow: 0 0 0 2px rgba(82, 196, 26, 0.2);
  }

  &.is-offline {
    background-color: #909399;
  }
}

.status-dot__text {
  &.is-online {
    color: $text-primary;
  }

  &.is-offline {
    color: $text-regular;
  }

  &.is-muted {
    color: $text-disabled;
  }
}
</style>
