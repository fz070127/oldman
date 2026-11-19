<template>
  <ScreenCard title="设备在线率" subtitle="DEVICE ONLINE">
    <div class="online-layout">
      <div class="ring-visual">
        <div ref="chartRef" class="ring-chart" />
        <div class="ring-center">
          <div class="ring-center__val">
            <span>{{ onlineRateCount.formatted.value }}</span>
            <small>%</small>
          </div>
          <span class="ring-center__label">实时在线率</span>
        </div>
      </div>

      <div class="online-metrics">
        <div class="metric-box is-green">
          <span class="metric-box__label">在线设备</span>
          <strong class="metric-box__num">{{ onlineCount.formatted.value }}</strong>
        </div>
        <div class="metric-box is-red">
          <span class="metric-box__label">离线 / 异常</span>
          <strong class="metric-box__num">{{ offlineCount.formatted.value }}</strong>
        </div>
        <div class="metric-box is-cyan">
          <span class="metric-box__label">设备总数</span>
          <strong class="metric-box__num">{{ totalCount.formatted.value }}</strong>
        </div>
      </div>
    </div>
  </ScreenCard>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useCountUp } from '@/hooks/useCountUp'
import { echarts, type ECharts } from '../echarts'
import ScreenCard from './ScreenCard.vue'

const props = defineProps<{
  online: number
  offline: number
  total: number
}>()

const ratePercent = computed(() => {
  if (props.total <= 0) return 0
  return Number(((props.online / props.total) * 100).toFixed(1))
})

const onlineRateCount = useCountUp(ratePercent, { decimals: 1 })
const onlineCount = useCountUp(() => props.online)
const offlineCount = useCountUp(() => props.offline)
const totalCount = useCountUp(() => props.total)

const chartRef = ref<HTMLElement>()
let chartInst: ECharts | null = null

function renderChart() {
  if (!chartRef.value) return
  if (!chartInst) {
    chartInst = echarts.init(chartRef.value)
  }

  const pct = Math.min(100, Math.max(0, ratePercent.value))
  const rest = Number((100 - pct).toFixed(1))

  chartInst.setOption({
    tooltip: {
      trigger: 'item',
      backgroundColor: 'rgba(10, 20, 48, 0.94)',
      borderColor: '#00E5FF',
      borderWidth: 1,
      textStyle: { color: '#EAF6FF', fontSize: 12 },
      formatter: '{b}：{c}%',
    },
    series: [
      // 外装饰细环
      {
        type: 'pie',
        radius: ['84%', '87%'],
        center: ['50%', '50%'],
        silent: true,
        label: { show: false },
        data: [{ value: 100, itemStyle: { color: 'rgba(0, 229, 255, 0.2)' } }],
      },
      // 主环形进度
      {
        name: '设备在线率',
        type: 'pie',
        radius: ['62%', '78%'],
        center: ['50%', '50%'],
        startAngle: 90,
        clockwise: true,
        label: { show: false },
        labelLine: { show: false },
        data: [
          {
            name: '在线率',
            value: pct,
            itemStyle: {
              borderRadius: 6,
              color: new echarts.graphic.LinearGradient(0, 0, 1, 1, [
                { offset: 0, color: '#00E5FF' },
                { offset: 1, color: '#00E676' },
              ]),
              shadowBlur: 12,
              shadowColor: 'rgba(0, 230, 118, 0.45)',
            },
          },
          {
            name: '离线/异常占比',
            value: rest,
            itemStyle: {
              color: 'rgba(255, 255, 255, 0.08)',
            },
          },
        ],
      },
    ],
  })
}

watch(
  () => [props.online, props.offline, props.total],
  () => renderChart(),
)

onMounted(() => renderChart())
onBeforeUnmount(() => {
  chartInst?.dispose()
  chartInst = null
})
</script>

<style scoped lang="scss">
.online-layout {
  display: grid;
  grid-template-columns: 1.15fr 0.85fr;
  align-items: center;
  gap: 12px;
  height: 100%;
}

.ring-visual {
  position: relative;
  width: 100%;
  height: 100%;
}

.ring-chart {
  width: 100%;
  height: 100%;
}

.ring-center {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  pointer-events: none;

  &__val {
    display: flex;
    align-items: baseline;
    font-family: 'DIN Alternate', 'Consolas', monospace;
    font-size: 36px;
    font-weight: 700;
    line-height: 1;
    color: #00e676;
    text-shadow: 0 0 14px rgba(0, 230, 118, 0.45);
    font-variant-numeric: tabular-nums;

    small {
      margin-left: 2px;
      font-size: 16px;
      color: #00e5ff;
    }
  }

  &__label {
    margin-top: 6px;
    font-size: 12px;
    color: rgba(207, 230, 255, 0.72);
  }
}

.online-metrics {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding-right: 8px;
}

.metric-box {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  background: rgba(10, 24, 58, 0.65);
  border: 1px solid rgba(0, 229, 255, 0.14);
  border-left: 3px solid #00e5ff;

  &.is-green {
    border-left-color: #00e676;

    .metric-box__num {
      color: #00e676;
    }
  }

  &.is-red {
    border-left-color: #ff3b5c;

    .metric-box__num {
      color: #ff3b5c;
    }
  }

  &.is-cyan {
    border-left-color: #00e5ff;

    .metric-box__num {
      color: #00e5ff;
    }
  }

  &__label {
    font-size: 13px;
    color: #cfe6ff;
  }

  &__num {
    font-family: 'DIN Alternate', 'Consolas', monospace;
    font-size: 22px;
    font-weight: 700;
    font-variant-numeric: tabular-nums;
  }
}
</style>
