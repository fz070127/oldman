/**
 * 大屏专用 ECharts 按需引入模块
 *
 * 教训（F4）：全量 import * as echarts from 'echarts' 会导致单 chunk 超过 1 MB。
 * 此处仅注册大屏实际使用的 4 种图表 + 3 个组件 + Canvas 渲染器，确保 chunk 体积可控。
 */
import * as echarts from 'echarts/core'
import { EffectScatterChart, LineChart, PieChart, ScatterChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([
  LineChart,
  PieChart,
  ScatterChart,
  EffectScatterChart,
  GridComponent,
  LegendComponent,
  TooltipComponent,
  CanvasRenderer,
])

export type { ECharts, EChartsCoreOption } from 'echarts/core'
export { echarts }
