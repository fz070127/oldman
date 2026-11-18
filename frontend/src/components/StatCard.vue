<template>
  <div class="stat-card" :style="{ borderTopColor: accentColor }">
    <div class="stat-card__header">
      <span class="stat-card__title">{{ title }}</span>
      <slot name="icon" />
    </div>
    <div class="stat-card__body">
      <span class="stat-card__value" :style="{ color: valueColor }">{{ value }}</span>
      <span v-if="unit" class="stat-card__unit">{{ unit }}</span>
    </div>
    <div v-if="trend !== undefined || trendLabel" class="stat-card__footer">
      <span class="stat-card__trend-label">{{ trendLabel }}</span>
      <span
        v-if="trend !== undefined"
        class="stat-card__trend"
        :class="{ 'is-up': trend > 0, 'is-down': trend < 0 }"
      >
        <el-icon v-if="trend > 0"><Top /></el-icon>
        <el-icon v-else-if="trend < 0"><Bottom /></el-icon>
        {{ Math.abs(trend) }}%
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
/** 数字统计卡：标题 + 大数字 + 单位 + 环比 */
import { Bottom, Top } from '@element-plus/icons-vue'

withDefaults(
  defineProps<{
    title: string
    value: number | string
    unit?: string
    /** 环比百分比，正数上升、负数下降 */
    trend?: number
    trendLabel?: string
    valueColor?: string
    accentColor?: string
  }>(),
  {
    unit: '',
    trend: undefined,
    trendLabel: '较昨日',
    valueColor: '#1f2329',
    accentColor: '#1677ff',
  },
)
</script>

<style scoped lang="scss">
.stat-card {
  padding: 16px 20px;
  background: $bg-white;
  border-top: 3px solid $color-primary;
  border-radius: $radius-large;
  box-shadow: $shadow-card;

  &__header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    font-size: 13px;
    color: $text-regular;
  }

  &__body {
    display: flex;
    align-items: baseline;
    gap: 6px;
    margin-top: 10px;
  }

  &__value {
    font-size: 28px;
    font-weight: 700;
    line-height: 1.2;
    color: $text-primary;
  }

  &__unit {
    font-size: 13px;
    color: $text-regular;
  }

  &__footer {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-top: 10px;
    font-size: 12px;
    color: $text-disabled;
  }

  &__trend {
    display: inline-flex;
    align-items: center;
    font-weight: 500;

    &.is-up {
      color: $color-danger;
    }

    &.is-down {
      color: $color-success;
    }
  }
}
</style>
