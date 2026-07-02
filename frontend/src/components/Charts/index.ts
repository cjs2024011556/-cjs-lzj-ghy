/**
 * ECharts 按需引入（关键优化：避免全量 1MB）
 * 只注册业务需要的 chart type 和 component
 */
import * as echarts from 'echarts/core'
import { LineChart, PieChart, GaugeChart, HeatmapChart, BarChart } from 'echarts/charts'
import {
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
  VisualMapComponent,
  DataZoomComponent,
  MarkLineComponent,
  MarkAreaComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([
  LineChart,
  PieChart,
  GaugeChart,
  HeatmapChart,
  BarChart,
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
  VisualMapComponent,
  DataZoomComponent,
  MarkLineComponent,
  MarkAreaComponent,
  CanvasRenderer,
])

export default echarts
