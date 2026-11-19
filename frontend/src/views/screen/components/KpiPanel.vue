<template>
  <ScreenCard title="核心监测指标" subtitle="OVERVIEW">
    <div class="kpi-list">
      <!-- 1. 老人总数 -->
      <div class="kpi-item is-cyan">
        <div class="kpi-item__head">
          <span class="kpi-item__label">在册老人总数</span>
          <span class="kpi-item__tag">护航中 {{ elderOnlineCount.formatted.value }} 人</span>
        </div>
        <div class="kpi-item__value-row">
          <span class="kpi-item__num">{{ elderTotalCount.formatted.value }}</span>
          <span class="kpi-item__unit">人</span>
        </div>
        <div class="kpi-item__bar">
          <div class="kpi-item__bar-fill" :style="{ width: `${elderOnlinePercent}%` }" />
        </div>
      </div>

      <!-- 2. 设备在线 -->
      <div class="kpi-item is-green">
        <div class="kpi-item__head">
          <span class="kpi-item__label">在线监测设备</span>
          <span class="kpi-item__tag">
            离线 {{ deviceOfflineCount.formatted.value }} / 共 {{ deviceTotalCount.formatted.value }} 台
          </span>
        </div>
        <div class="kpi-item__value-row">
          <span class="kpi-item__num">{{ deviceOnlineCount.formatted.value }}</span>
          <span class="kpi-item__unit">台</span>
        </div>
        <div class="kpi-item__bar">
          <div class="kpi-item__bar-fill" :style="{ width: `${deviceOnlinePercent}%` }" />
        </div>
      </div>

      <!-- 3. 今日告警 -->
      <div class="kpi-item is-red" :class="{ 'is-pulsing': (overview?.alarmPending ?? 0) > 0 }">
        <div class="kpi-item__head">
          <span class="kpi-item__label">今日告警总数</span>
          <span class="kpi-item__tag">
            待处理 {{ alarmPendingCount.formatted.value }} · P0 {{ alarmP0Count.formatted.value }}
          </span>
        </div>
        <div class="kpi-item__value-row">
          <span class="kpi-item__num">{{ alarmTodayCount.formatted.value }}</span>
          <span class="kpi-item__unit">起</span>
        </div>
        <div class="kpi-item__bar">
          <div class="kpi-item__bar-fill" :style="{ width: `${p0RatioPercent}%` }" />
        </div>
      </div>

      <!-- 4. 平均响应时长 -->
      <div class="kpi-item is-amber">
        <div class="kpi-item__head">
          <span class="kpi-item__label">平均响应时长</span>
          <span class="kpi-item__tag">误报率 {{ falsePositiveCount.formatted.value }}%</span>
        </div>
        <div class="kpi-item__value-row">
          <span class="kpi-item__num">{{ avgResponseCount.formatted.value }}</span>
          <span class="kpi-item__unit">秒</span>
        </div>
        <div class="kpi-item__bar">
          <div class="kpi-item__bar-fill" :style="{ width: `${responseScorePercent}%` }" />
        </div>
      </div>
    </div>
  </ScreenCard>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useCountUp } from '@/hooks/useCountUp'
import type { DashboardOverview } from '@/types/dashboard'
import ScreenCard from './ScreenCard.vue'

const props = defineProps<{
  overview: DashboardOverview | null
}>()

const elderTotalCount = useCountUp(() => props.overview?.elderTotal ?? 0)
const elderOnlineCount = useCountUp(() => props.overview?.elderOnline ?? 0)
const deviceOnlineCount = useCountUp(() => props.overview?.deviceOnline ?? 0)
const deviceTotalCount = useCountUp(() => props.overview?.deviceTotal ?? 0)
const deviceOfflineCount = useCountUp(() => props.overview?.deviceOffline ?? 0)
const alarmTodayCount = useCountUp(() => props.overview?.alarmToday ?? 0)
const alarmPendingCount = useCountUp(() => props.overview?.alarmPending ?? 0)
const alarmP0Count = useCountUp(() => props.overview?.alarmP0Today ?? 0)
const avgResponseCount = useCountUp(() => props.overview?.avgResponseSec ?? 0)
const falsePositiveCount = useCountUp(() => (props.overview?.falsePositiveRate ?? 0) * 100, {
  decimals: 1,
})

const elderOnlinePercent = computed(() => {
  const total = props.overview?.elderTotal ?? 0
  const online = props.overview?.elderOnline ?? 0
  return total > 0 ? Math.min(100, Math.round((online / total) * 100)) : 0
})

const deviceOnlinePercent = computed(() => {
  const total = props.overview?.deviceTotal ?? 0
  const online = props.overview?.deviceOnline ?? 0
  return total > 0 ? Math.min(100, Math.round((online / total) * 100)) : 0
})

const p0RatioPercent = computed(() => {
  const total = props.overview?.alarmToday ?? 0
  const p0 = props.overview?.alarmP0Today ?? 0
  if (total <= 0) return 0
  return Math.min(100, Math.max(12, Math.round((p0 / total) * 100)))
})

const responseScorePercent = computed(() => {
  const sec = props.overview?.avgResponseSec ?? 0
  if (sec <= 0) return 0
  // 响应越快进度越满（以 120s 为基准）
  return Math.min(100, Math.max(15, Math.round(((120 - Math.min(sec, 120)) / 120) * 100)))
})
</script>

<style scoped lang="scss">
.kpi-list {
  display: grid;
  grid-template-rows: repeat(4, 1fr);
  gap: 12px;
  height: 100%;
}

.kpi-item {
  position: relative;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  padding: 12px 16px;
  background: linear-gradient(135deg, rgba(12, 28, 66, 0.85) 0%, rgba(16, 40, 88, 0.45) 100%);
  border: 1px solid rgba(0, 229, 255, 0.2);
  border-left: 3px solid #00e5ff;
  box-shadow: inset 0 0 18px rgba(0, 229, 255, 0.06);

  &.is-cyan {
    border-left-color: #00e5ff;

    .kpi-item__num {
      color: #00e5ff;
      text-shadow: 0 0 14px rgba(0, 229, 255, 0.45);
    }

    .kpi-item__bar-fill {
      background: linear-gradient(90deg, #2196f3, #00e5ff);
    }
  }

  &.is-green {
    border-left-color: #00e676;

    .kpi-item__num {
      color: #00e676;
      text-shadow: 0 0 14px rgba(0, 230, 118, 0.45);
    }

    .kpi-item__bar-fill {
      background: linear-gradient(90deg, #00c853, #00e676);
    }
  }

  &.is-red {
    border-left-color: #ff3b5c;

    .kpi-item__num {
      color: #ff3b5c;
      text-shadow: 0 0 14px rgba(255, 59, 92, 0.55);
    }

    .kpi-item__bar-fill {
      background: linear-gradient(90deg, #ff7043, #ff3b5c);
    }
  }

  &.is-amber {
    border-left-color: #ffb300;

    .kpi-item__num {
      color: #ffb300;
      text-shadow: 0 0 14px rgba(255, 179, 0, 0.45);
    }

    .kpi-item__bar-fill {
      background: linear-gradient(90deg, #ff8f00, #ffb300);
    }
  }

  &.is-pulsing {
    animation: kpi-pulse 2.2s ease-in-out infinite;
  }

  &__head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
  }

  &__label {
    font-size: 14px;
    font-weight: 500;
    color: #cfe6ff;
    letter-spacing: 0.5px;
  }

  &__tag {
    font-size: 12px;
    color: rgba(185, 215, 255, 0.72);
    font-variant-numeric: tabular-nums;
  }

  &__value-row {
    display: flex;
    align-items: baseline;
    gap: 8px;
    margin: 2px 0;
  }

  &__num {
    font-family: 'DIN Alternate', 'Consolas', 'Courier New', monospace;
    font-size: 38px;
    font-weight: 700;
    line-height: 1.05;
    letter-spacing: 1px;
    font-variant-numeric: tabular-nums;
  }

  &__unit {
    font-size: 14px;
    color: rgba(207, 230, 255, 0.72);
  }

  &__bar {
    width: 100%;
    height: 4px;
    overflow: hidden;
    background: rgba(255, 255, 255, 0.08);
    border-radius: 2px;
  }

  &__bar-fill {
    height: 100%;
    border-radius: 2px;
    transition: width 0.8s cubic-bezier(0.22, 1, 0.36, 1);
  }
}

@keyframes kpi-pulse {
  0%,
  100% {
    box-shadow: inset 0 0 18px rgba(255, 59, 92, 0.08);
  }
  50% {
    box-shadow:
      inset 0 0 24px rgba(255, 59, 92, 0.28),
      0 0 12px rgba(255, 59, 92, 0.2);
  }
}
</style>
