<template>
  <ScreenCard title="社区实时态势分布" subtitle="COMMUNITY MAP" :alert="activeAlertIds.length > 0">
    <template #extra>
      <div class="map-legend">
        <span class="map-legend__item">
          <i class="dot is-normal" />
          正常运行
        </span>
        <span class="map-legend__item">
          <i class="dot is-alarm" />
          有告警社区
        </span>
        <span class="map-legend__item">
          <i class="dot is-live" />
          实时触发
        </span>
      </div>
    </template>

    <div class="map-stage">
      <!-- 底层科技地图示意装饰（雷达同心圆 + 扫描线 + 社区连线网格，零额外 ECharts 体积） -->
      <svg class="map-decor" viewBox="0 0 1000 560" preserveAspectRatio="none" aria-hidden="true">
        <defs>
          <radialGradient id="radarGlow" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stop-color="rgba(0, 229, 255, 0.14)" />
            <stop offset="65%" stop-color="rgba(33, 150, 243, 0.04)" />
            <stop offset="100%" stop-color="rgba(10, 17, 40, 0)" />
          </radialGradient>
        </defs>
        <circle cx="500" cy="280" r="240" fill="url(#radarGlow)" />
        <circle cx="500" cy="280" r="85" fill="none" stroke="rgba(0,229,255,0.14)" stroke-dasharray="4 6" />
        <circle cx="500" cy="280" r="165" fill="none" stroke="rgba(0,229,255,0.12)" stroke-dasharray="6 8" />
        <circle cx="500" cy="280" r="245" fill="none" stroke="rgba(0,229,255,0.09)" />
        <line x1="60" y1="280" x2="940" y2="280" stroke="rgba(0,229,255,0.08)" />
        <line x1="500" y1="25" x2="500" y2="535" stroke="rgba(0,229,255,0.08)" />
        <!-- 社区示意边界轮廓 -->
        <polygon
          points="150,150 420,90 790,130 880,360 680,480 260,470 110,320"
          fill="rgba(33, 150, 243, 0.05)"
          stroke="rgba(0, 229, 255, 0.22)"
          stroke-width="1.2"
          stroke-dasharray="8 6"
        />
      </svg>

      <!-- ECharts 社区散点与涟漪图 -->
      <div ref="chartRef" class="map-chart" />

      <!-- 底部社区摘要条 -->
      <div class="map-summary">
        <div
          v-for="item in list"
          :key="item.communityId"
          class="map-summary__chip"
          :class="{
            'is-alarm': item.alarmToday > 0,
            'is-live': isLiveAlert(item.communityId),
          }"
        >
          <span class="chip-name">{{ item.communityName }}</span>
          <span class="chip-stat">老人 {{ item.elderTotal }}</span>
          <span class="chip-alarm">告警 {{ item.alarmToday }}</span>
        </div>
      </div>
    </div>
  </ScreenCard>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import type { DistributionItem } from '@/types/dashboard'
import { echarts, type ECharts } from '../echarts'
import ScreenCard from './ScreenCard.vue'

const props = defineProps<{
  list: DistributionItem[]
  /** 刚通过 WS ALARM_NEW 触发实时告警的社区 ID 列表 */
  activeAlertIds: string[]
}>()

const chartRef = ref<HTMLElement>()
let chartInst: ECharts | null = null

function isLiveAlert(communityId: string): boolean {
  return props.activeAlertIds.includes(communityId)
}

interface PointDatum {
  name: string
  value: [number, number, number, number]
  communityId: string
  live: boolean
  hasAlarm: boolean
}

function toPoints(): PointDatum[] {
  return props.list.map((item) => {
    // 契约 x/y 为 0~1 归一化坐标；映射到 [8, 92] 避免标签贴边裁切
    const x = 8 + Math.min(1, Math.max(0, item.x)) * 84
    const y = 12 + Math.min(1, Math.max(0, 1 - item.y)) * 76
    const live = isLiveAlert(item.communityId)
    const hasAlarm = item.alarmToday > 0 || live
    return {
      name: item.communityName,
      value: [Number(x.toFixed(2)), Number(y.toFixed(2)), item.elderTotal, item.alarmToday],
      communityId: item.communityId,
      live,
      hasAlarm,
    }
  })
}

function renderChart() {
  if (!chartRef.value) return
  if (!chartInst) {
    chartInst = echarts.init(chartRef.value)
  }

  const allPoints = toPoints()
  const normalPoints = allPoints.filter((p) => !p.hasAlarm)
  const alarmPoints = allPoints.filter((p) => p.hasAlarm && !p.live)
  const livePoints = allPoints.filter((p) => p.live)

  chartInst.setOption(
    {
      animationDurationUpdate: 450,
      tooltip: {
        trigger: 'item',
        backgroundColor: 'rgba(10, 20, 48, 0.94)',
        borderColor: '#00E5FF',
        borderWidth: 1,
        textStyle: { color: '#EAF6FF', fontSize: 13 },
        formatter: (params: { data?: PointDatum }) => {
          const d = params.data
          if (!d) return ''
          const [, , elders, alarms] = d.value
          const statusHtml = d.live
            ? '<span style="color:#FF3B5C;font-weight:700">● 实时告警触发</span>'
            : d.hasAlarm
              ? '<span style="color:#FF3B5C;font-weight:600">● 今日有告警</span>'
              : '<span style="color:#00E676">● 运行正常</span>'
          return [
            `<div style="font-weight:700;margin-bottom:4px;color:#00E5FF">${d.name}</div>`,
            `<div>状态：${statusHtml}</div>`,
            `<div>在册老人：<b style="font-family:'DIN Alternate',monospace">${elders}</b> 人</div>`,
            `<div>今日告警：<b style="font-family:'DIN Alternate',monospace;color:${alarms > 0 ? '#FF3B5C' : '#00E676'}">${alarms}</b> 起</div>`,
          ].join('')
        },
      },
      grid: { left: 16, right: 16, top: 16, bottom: 24, containLabel: false },
      xAxis: {
        type: 'value',
        min: 0,
        max: 100,
        show: false,
      },
      yAxis: {
        type: 'value',
        min: 0,
        max: 100,
        show: false,
      },
      series: [
        // 正常社区：青色涟漪
        {
          name: '正常社区',
          type: 'effectScatter',
          coordinateSystem: 'cartesian2d',
          rippleEffect: {
            brushType: 'stroke',
            scale: 3.4,
            period: 4.5,
          },
          symbolSize: 15,
          itemStyle: {
            color: '#00E5FF',
            shadowBlur: 14,
            shadowColor: 'rgba(0, 229, 255, 0.8)',
          },
          label: {
            show: true,
            position: 'bottom',
            distance: 10,
            color: '#CFE6FF',
            fontSize: 13,
            fontWeight: 500,
            formatter: (params: { data?: PointDatum }) => {
              const d = params.data
              return d ? `${d.name}\n${d.value[2]}人` : ''
            },
            lineHeight: 17,
          },
          data: normalPoints,
        },
        // 今日有告警社区：危红放大 + 涟漪
        {
          name: '有告警社区',
          type: 'effectScatter',
          coordinateSystem: 'cartesian2d',
          rippleEffect: {
            brushType: 'stroke',
            scale: 4.2,
            period: 3.2,
          },
          symbolSize: 22,
          itemStyle: {
            color: '#FF3B5C',
            shadowBlur: 18,
            shadowColor: 'rgba(255, 59, 92, 0.9)',
          },
          label: {
            show: true,
            position: 'bottom',
            distance: 12,
            color: '#FFD4DC',
            fontSize: 13,
            fontWeight: 600,
            formatter: (params: { data?: PointDatum }) => {
              const d = params.data
              return d ? `${d.name}\n告警 ${d.value[3]} 起` : ''
            },
            lineHeight: 17,
          },
          data: alarmPoints,
        },
        // WS 实时触发告警社区：超大危红脉冲点 + 高亮标注
        {
          name: '实时触发',
          type: 'effectScatter',
          coordinateSystem: 'cartesian2d',
          zlevel: 3,
          rippleEffect: {
            brushType: 'fill',
            scale: 5.5,
            period: 1.8,
          },
          symbolSize: 30,
          itemStyle: {
            color: '#FF3B5C',
            borderColor: '#FFFFFF',
            borderWidth: 2,
            shadowBlur: 26,
            shadowColor: '#FF3B5C',
          },
          label: {
            show: true,
            position: 'top',
            distance: 14,
            color: '#FFFFFF',
            backgroundColor: 'rgba(255, 59, 92, 0.92)',
            borderColor: '#FFB3C1',
            borderWidth: 1,
            borderRadius: 4,
            padding: [4, 8],
            fontSize: 13,
            fontWeight: 700,
            formatter: (params: { data?: PointDatum }) => {
              const d = params.data
              return d ? `● 告警：${d.name}（今日 ${d.value[3]} 起）` : ''
            },
          },
          data: livePoints,
        },
        // 中心定位内核点（辅助锚点）
        {
          name: '社区锚点',
          type: 'scatter',
          coordinateSystem: 'cartesian2d',
          silent: true,
          symbolSize: 5,
          itemStyle: { color: '#FFFFFF' },
          data: allPoints.map((p) => ({ value: [p.value[0], p.value[1]] })),
        },
      ],
    },
    true,
  )
}

watch(
  () => [props.list, props.activeAlertIds],
  () => renderChart(),
  { deep: true },
)

onMounted(() => {
  renderChart()
})

onBeforeUnmount(() => {
  chartInst?.dispose()
  chartInst = null
})
</script>

<style scoped lang="scss">
.map-legend {
  display: inline-flex;
  align-items: center;
  gap: 14px;
  font-size: 12px;
  color: rgba(207, 230, 255, 0.85);

  &__item {
    display: inline-flex;
    align-items: center;
    gap: 5px;
  }

  .dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;

    &.is-normal {
      background: #00e5ff;
      box-shadow: 0 0 6px #00e5ff;
    }

    &.is-alarm {
      background: #ff3b5c;
      box-shadow: 0 0 6px #ff3b5c;
    }

    &.is-live {
      background: #ff3b5c;
      border: 1px solid #fff;
      box-shadow: 0 0 10px #ff3b5c;
    }
  }
}

.map-stage {
  position: relative;
  display: flex;
  flex-direction: column;
  width: 100%;
  height: 100%;
  overflow: hidden;
}

.map-decor {
  position: absolute;
  inset: 0;
  width: 100%;
  height: calc(100% - 54px);
  pointer-events: none;
}

.map-chart {
  position: relative;
  z-index: 1;
  flex: 1;
  width: 100%;
  min-height: 0;
}

.map-summary {
  position: relative;
  z-index: 2;
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 8px;
  flex-shrink: 0;
  padding-top: 8px;
  border-top: 1px solid rgba(0, 229, 255, 0.14);

  &__chip {
    display: flex;
    flex-direction: column;
    gap: 2px;
    padding: 6px 8px;
    font-size: 12px;
    background: rgba(10, 22, 54, 0.72);
    border: 1px solid rgba(0, 229, 255, 0.2);
    transition: all 0.3s ease;

    &.is-alarm {
      border-color: rgba(255, 59, 92, 0.55);
      background: rgba(255, 59, 92, 0.1);

      .chip-alarm {
        color: #ff3b5c;
      }
    }

    &.is-live {
      border-color: #ff3b5c;
      background: rgba(255, 59, 92, 0.24);
      box-shadow: 0 0 12px rgba(255, 59, 92, 0.4);
    }

    .chip-name {
      overflow: hidden;
      font-weight: 600;
      color: #eaf6ff;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .chip-stat {
      font-family: 'DIN Alternate', 'Consolas', monospace;
      font-size: 11px;
      color: rgba(185, 215, 255, 0.72);
    }

    .chip-alarm {
      font-family: 'DIN Alternate', 'Consolas', monospace;
      font-size: 11px;
      font-weight: 600;
      color: #00e676;
    }
  }
}
</style>
