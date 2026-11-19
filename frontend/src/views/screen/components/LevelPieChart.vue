<template>
  <ScreenCard title="今日告警级别占比" subtitle="LEVEL RATIO">
    <div class="pie-layout">
      <div class="pie-visual">
        <div ref="chartRef" class="pie-chart" />
        <!-- 环形图中心显示今日总数（useCountUp 滚动动画） -->
        <div class="pie-center">
          <span class="pie-center__num">{{ todayTotalCount.formatted.value }}</span>
          <span class="pie-center__label">今日总数</span>
        </div>
      </div>

      <div class="pie-legend">
        <div v-for="row in rows" :key="row.key" class="pie-legend__row">
          <span class="pie-legend__dot" :style="{ backgroundColor: row.color }" />
          <span class="pie-legend__name">{{ row.name }}</span>
          <span class="pie-legend__val">{{ row.value }}</span>
          <span class="pie-legend__pct">{{ row.percent }}%</span>
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
  p0: number
  p1: number
  p2: number
  todayTotal: number
}>()

const todayTotalCount = useCountUp(() => props.todayTotal)

const rows = computed(() => {
  const sum = props.p0 + props.p1 + props.p2
  const pct = (v: number) => (sum > 0 ? ((v / sum) * 100).toFixed(1) : '0.0')
  return [
    { key: 'P0', name: 'P0 紧急', value: props.p0, percent: pct(props.p0), color: '#FF3B5C' },
    { key: 'P1', name: 'P1 重要', value: props.p1, percent: pct(props.p1), color: '#FFB300' },
    { key: 'P2', name: 'P2 一般', value: props.p2, percent: pct(props.p2), color: '#2196F3' },
  ]
})

const chartRef = ref<HTMLElement>()
let chartInst: ECharts | null = null

function renderChart() {
  if (!chartRef.value) return
  if (!chartInst) {
    chartInst = echarts.init(chartRef.value)
  }

  const hasData = props.p0 + props.p1 + props.p2 > 0
  const seriesData = hasData
    ? [
        { name: 'P0 紧急', value: props.p0, itemStyle: { color: '#FF3B5C' } },
        { name: 'P1 重要', value: props.p1, itemStyle: { color: '#FFB300' } },
        { name: 'P2 一般', value: props.p2, itemStyle: { color: '#2196F3' } },
      ]
    : [{ name: '暂无告警', value: 1, itemStyle: { color: 'rgba(0, 229, 255, 0.18)' } }]

  chartInst.setOption({
    tooltip: {
      trigger: 'item',
      backgroundColor: 'rgba(10, 20, 48, 0.94)',
      borderColor: '#00E5FF',
      borderWidth: 1,
      textStyle: { color: '#EAF6FF', fontSize: 12 },
      formatter: hasData ? '{b}：{c} 起 ({d}%)' : '今日暂无告警',
    },
    series: [
      {
        name: '今日告警级别',
        type: 'pie',
        radius: ['58%', '80%'],
        center: ['50%', '50%'],
        avoidLabelOverlap: false,
        padAngle: hasData ? 3 : 0,
        itemStyle: {
          borderRadius: 4,
          borderColor: '#0A1128',
          borderWidth: 2,
        },
        label: { show: false },
        labelLine: { show: false },
        data: seriesData,
      },
    ],
  })
}

watch(
  () => [props.p0, props.p1, props.p2],
  () => renderChart(),
)

onMounted(() => renderChart())
onBeforeUnmount(() => {
  chartInst?.dispose()
  chartInst = null
})
</script>

<style scoped lang="scss">
.pie-layout {
  display: grid;
  grid-template-columns: 1.1fr 0.9fr;
  align-items: center;
  gap: 12px;
  height: 100%;
}

.pie-visual {
  position: relative;
  width: 100%;
  height: 100%;
}

.pie-chart {
  width: 100%;
  height: 100%;
}

.pie-center {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  pointer-events: none;

  &__num {
    font-family: 'DIN Alternate', 'Consolas', monospace;
    font-size: 38px;
    font-weight: 700;
    line-height: 1.05;
    color: #00e5ff;
    text-shadow: 0 0 14px rgba(0, 229, 255, 0.5);
    font-variant-numeric: tabular-nums;
  }

  &__label {
    margin-top: 4px;
    font-size: 12px;
    color: rgba(207, 230, 255, 0.72);
  }
}

.pie-legend {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding-right: 8px;

  &__row {
    display: grid;
    grid-template-columns: 10px 1fr 44px 52px;
    align-items: center;
    gap: 8px;
    padding: 8px 10px;
    background: rgba(10, 24, 58, 0.65);
    border: 1px solid rgba(0, 229, 255, 0.14);
  }

  &__dot {
    width: 10px;
    height: 10px;
    border-radius: 2px;
  }

  &__name {
    font-size: 13px;
    color: #dceeff;
  }

  &__val {
    font-family: 'DIN Alternate', 'Consolas', monospace;
    font-size: 18px;
    font-weight: 700;
    color: #ffffff;
    text-align: right;
  }

  &__pct {
    font-family: 'DIN Alternate', 'Consolas', monospace;
    font-size: 13px;
    color: rgba(0, 229, 255, 0.85);
    text-align: right;
  }
}
</style>
