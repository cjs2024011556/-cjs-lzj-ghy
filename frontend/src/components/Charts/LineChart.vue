<template>
  <v-chart
    class="chart"
    :option="chartOption"
    :autoresize="true"
    :init-options="initOptions"
    @click="onClick"
  />
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { use } from 'echarts/core'
import { LineChart } from 'echarts/charts'
import {
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
  DataZoomComponent,
  MarkLineComponent,
  MarkAreaComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'
import { buildEchartsTheme, defaultGrid } from '@/utils/echarts-theme'

use([LineChart, TitleComponent, TooltipComponent, LegendComponent, GridComponent, DataZoomComponent, MarkLineComponent, MarkAreaComponent, CanvasRenderer])

interface SeriesItem {
  name: string
  data: number[]
}

const props = withDefaults(defineProps<{
  xAxis: string[]
  series: SeriesItem[]
  title?: string
  height?: string
  showLegend?: boolean
  smooth?: boolean
  area?: boolean
}>(), {
  height: '280px',
  showLegend: true,
  smooth: true,
  area: true,
})

defineEmits<{ (e: 'click', params: any): void }>()

const initOptions = computed(() => ({
  renderer: 'canvas' as const,
}))

const chartOption = computed(() => {
  const theme = buildEchartsTheme()
  return {
    color: theme.color,
    backgroundColor: theme.backgroundColor,
    title: props.title ? {
      text: props.title,
      textStyle: theme.title.textStyle,
      left: 0,
      top: 0,
    } : undefined,
    tooltip: {
      trigger: 'axis',
      backgroundColor: theme.tooltip.backgroundColor,
      borderColor: theme.tooltip.borderColor,
      textStyle: theme.tooltip.textStyle,
    },
    legend: props.showLegend ? {
      data: props.series.map(s => s.name),
      textStyle: theme.legend.textStyle,
      right: 0,
      top: 0,
    } : undefined,
    grid: { ...defaultGrid, top: props.title ? 50 : defaultGrid.top },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: props.xAxis,
      axisLine: theme.axisLine,
      axisLabel: { color: theme.legend.textStyle.color },
    },
    yAxis: {
      type: 'value',
      axisLine: theme.axisLine,
      splitLine: theme.splitLine,
      axisLabel: { color: theme.legend.textStyle.color },
    },
    series: props.series.map(s => ({
      name: s.name,
      type: 'line',
      smooth: props.smooth,
      symbol: 'circle',
      symbolSize: 6,
      data: s.data,
      areaStyle: props.area ? { opacity: 0.2 } : undefined,
      emphasis: { focus: 'series' },
    })),
  }
})

function onClick(_params: any) {
  // 暂不处理 click
}
</script>

<style scoped>
.chart {
  width: 100%;
  height: v-bind(height);
}
</style>
