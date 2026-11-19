<template>
  <div class="dashboard-trend-chart">
    <div ref="chartEl" class="dashboard-trend-chart__canvas" />
  </div>
</template>

<script setup lang="ts">
/**
 * 工作台近 7 天告警趋势折线图组件
 * - 严格复用 F7 大屏按需注册的 ECharts 模块（@/views/screen/echarts），不引入全量 echarts
 * - 父页面通过 defineAsyncComponent 异步按需挂载
 */
import type { TrendItem } from '@/types/dashboard'
import { echarts, type ECharts, type EChartsCoreOption } from '@/views/screen/echarts'

const props = defineProps<{
  list: TrendItem[]
}>()

const chartEl = ref<HTMLElement>()
let chart: ECharts | null = null

function buildOption(items: TrendItem[]): EChartsCoreOption {
  const dates = items.map((d) => String(d.date).slice(5))
  const p0Data = items.map((d) => d.p0)
  const p1Data = items.map((d) => d.p1)
  const p2Data = items.map((d) => d.p2)

  return {
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(255, 255, 255, 0.96)',
      borderColor: '#e5e6eb',
      borderWidth: 1,
      textStyle: { color: '#1f2329', fontSize: 13 },
    },
    legend: {
      top: 4,
      right: 12,
      icon: 'roundRect',
      itemWidth: 14,
      itemHeight: 8,
      textStyle: { color: '#4e5969', fontSize: 12 },
      data: ['P0 紧急', 'P1 重要', 'P2 一般'],
    },
    grid: {
      top: 40,
      left: 12,
      right: 16,
      bottom: 8,
      containLabel: true,
    },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: dates,
      axisLine: { lineStyle: { color: '#dcdfe6' } },
      axisTick: { show: false },
      axisLabel: { color: '#646a73', fontSize: 12 },
    },
    yAxis: {
      type: 'value',
      minInterval: 1,
      splitLine: { lineStyle: { color: '#f0f2f5', type: 'dashed' } },
      axisLabel: { color: '#646a73', fontSize: 12 },
    },
    series: [
      {
        name: 'P0 紧急',
        type: 'line',
        smooth: true,
        symbol: 'circle',
        symbolSize: 6,
        data: p0Data,
        itemStyle: { color: '#cf1322' },
        lineStyle: { width: 2.5, color: '#cf1322' },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(207, 19, 34, 0.24)' },
            { offset: 1, color: 'rgba(207, 19, 34, 0.01)' },
          ]),
        },
      },
      {
        name: 'P1 重要',
        type: 'line',
        smooth: true,
        symbol: 'circle',
        symbolSize: 6,
        data: p1Data,
        itemStyle: { color: '#fa8c16' },
        lineStyle: { width: 2.5, color: '#fa8c16' },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(250, 140, 22, 0.20)' },
            { offset: 1, color: 'rgba(250, 140, 22, 0.01)' },
          ]),
        },
      },
      {
        name: 'P2 一般',
        type: 'line',
        smooth: true,
        symbol: 'circle',
        symbolSize: 6,
        data: p2Data,
        itemStyle: { color: '#1677ff' },
        lineStyle: { width: 2.5, color: '#1677ff' },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(22, 119, 255, 0.18)' },
            { offset: 1, color: 'rgba(22, 119, 255, 0.01)' },
          ]),
        },
      },
    ],
  }
}

function renderChart() {
  if (!chartEl.value) return
  if (!chart) {
    chart = echarts.init(chartEl.value)
  }
  chart.setOption(buildOption(props.list), true)
}

function handleResize() {
  chart?.resize()
}

watch(
  () => props.list,
  () => {
    nextTick(() => renderChart())
  },
  { deep: true },
)

onMounted(() => {
  renderChart()
  window.addEventListener('resize', handleResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  chart?.dispose()
  chart = null
})
</script>

<style scoped lang="scss">
.dashboard-trend-chart {
  width: 100%;
  height: 360px;

  &__canvas {
    width: 100%;
    height: 100%;
  }
}
</style>
