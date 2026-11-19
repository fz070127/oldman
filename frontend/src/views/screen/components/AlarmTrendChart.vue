<template>
  <ScreenCard title="近 7 日告警趋势" subtitle="7-DAY TREND">
    <template #extra>
      <span class="trend-total">7日累计 {{ total7dCount.formatted.value }} 起</span>
    </template>
    <div ref="chartRef" class="chart-box" />
  </ScreenCard>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import dayjs from 'dayjs'
import { useCountUp } from '@/hooks/useCountUp'
import type { TrendItem } from '@/types/dashboard'
import { echarts, type ECharts } from '../echarts'
import ScreenCard from './ScreenCard.vue'

const props = defineProps<{
  list: TrendItem[]
}>()

const total7d = computed(() => props.list.reduce((sum, item) => sum + item.total, 0))
const total7dCount = useCountUp(total7d)

const chartRef = ref<HTMLElement>()
let chartInst: ECharts | null = null

function makeAreaColor(rgbaStart: string, rgbaEnd: string) {
  return new echarts.graphic.LinearGradient(0, 0, 0, 1, [
    { offset: 0, color: rgbaStart },
    { offset: 1, color: rgbaEnd },
  ])
}

function renderChart() {
  if (!chartRef.value) return
  if (!chartInst) {
    chartInst = echarts.init(chartRef.value)
  }

  const dates = props.list.map((d) => {
    const parsed = dayjs(d.date)
    return parsed.isValid() ? parsed.format('MM-DD') : d.date
  })

  chartInst.setOption({
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(10, 20, 48, 0.94)',
      borderColor: '#00E5FF',
      borderWidth: 1,
      textStyle: { color: '#EAF6FF', fontSize: 12 },
    },
    legend: {
      top: 0,
      right: 6,
      itemWidth: 14,
      itemHeight: 8,
      textStyle: { color: '#B8D4F5', fontSize: 12 },
      data: ['P0 紧急', 'P1 重要', 'P2 一般'],
    },
    grid: { left: 42, right: 16, top: 34, bottom: 28 },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: dates,
      axisLine: { lineStyle: { color: 'rgba(0, 229, 255, 0.25)' } },
      axisTick: { show: false },
      axisLabel: {
        color: '#9EC5EB',
        fontFamily: "'DIN Alternate', Consolas, monospace",
        fontSize: 12,
      },
    },
    yAxis: {
      type: 'value',
      minInterval: 1,
      splitLine: { lineStyle: { color: 'rgba(0, 229, 255, 0.1)', type: 'dashed' } },
      axisLabel: {
        color: '#9EC5EB',
        fontFamily: "'DIN Alternate', Consolas, monospace",
        fontSize: 12,
      },
    },
    series: [
      {
        name: 'P0 紧急',
        type: 'line',
        smooth: true,
        symbol: 'circle',
        symbolSize: 6,
        lineStyle: { width: 2.5, color: '#FF3B5C' },
        itemStyle: { color: '#FF3B5C' },
        areaStyle: { color: makeAreaColor('rgba(255, 59, 92, 0.42)', 'rgba(255, 59, 92, 0.02)') },
        data: props.list.map((d) => d.p0),
      },
      {
        name: 'P1 重要',
        type: 'line',
        smooth: true,
        symbol: 'circle',
        symbolSize: 6,
        lineStyle: { width: 2.5, color: '#FFB300' },
        itemStyle: { color: '#FFB300' },
        areaStyle: { color: makeAreaColor('rgba(255, 179, 0, 0.35)', 'rgba(255, 179, 0, 0.02)') },
        data: props.list.map((d) => d.p1),
      },
      {
        name: 'P2 一般',
        type: 'line',
        smooth: true,
        symbol: 'circle',
        symbolSize: 6,
        lineStyle: { width: 2.5, color: '#2196F3' },
        itemStyle: { color: '#2196F3' },
        areaStyle: { color: makeAreaColor('rgba(33, 150, 243, 0.35)', 'rgba(33, 150, 243, 0.02)') },
        data: props.list.map((d) => d.p2),
      },
    ],
  })
}

watch(
  () => props.list,
  () => renderChart(),
  { deep: true },
)

onMounted(() => renderChart())
onBeforeUnmount(() => {
  chartInst?.dispose()
  chartInst = null
})
</script>

<style scoped lang="scss">
.trend-total {
  font-family: 'DIN Alternate', 'Consolas', monospace;
  font-size: 13px;
  color: #00e5ff;
}

.chart-box {
  width: 100%;
  height: 100%;
}
</style>
