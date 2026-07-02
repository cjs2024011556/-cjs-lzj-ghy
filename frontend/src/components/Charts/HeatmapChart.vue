<template>
  <v-chart
    class="chart"
    :option="chartOption"
    :autoresize="true"
    :init-options="initOptions"
  />
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { use } from 'echarts/core'
import { HeatmapChart } from 'echarts/charts'
import {
  TitleComponent,
  TooltipComponent,
  VisualMapComponent,
  GridComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'
import { buildEchartsTheme, defaultGrid } from '@/utils/echarts-theme'

use([
  HeatmapChart,
  TitleComponent,
  TooltipComponent,
  VisualMapComponent,
  GridComponent,
  CanvasRenderer,
])

interface HeatmapCell {
  x: string
  y: string
  value: number
}

const props = withDefaults(defineProps<{
  data: HeatmapCell[]
  xCategories: string[]
  yCategories: string[]
  title?: string
  height?: string
  max?: number
}>(), {
  height: '320px',
  max: 100,
})

const initOptions = computed(() => ({ renderer: 'canvas' as const }))

const chartOption = computed(() => {
  const theme = buildEchartsTheme()
  // 找到实际最大值用于 color 映射
  const maxVal = props.data.reduce((m, d) => Math.max(m, d.value), props.max)
  return {
    backgroundColor: theme.backgroundColor,
    color: theme.color,
    title: props.title ? {
      text: props.title,
      textStyle: theme.title.textStyle,
      left: 0,
      top: 0,
    } : undefined,
    tooltip: {
      position: 'top',
      backgroundColor: theme.tooltip.backgroundColor,
      borderColor: theme.tooltip.borderColor,
      textStyle: theme.tooltip.textStyle,
    },
    grid: { ...defaultGrid, top: props.title ? 50 : defaultGrid.top },
    xAxis: {
      type: 'category',
      data: props.xCategories,
      axisLine: theme.axisLine,
      axisLabel: { color: theme.legend.textStyle.color },
      splitArea: { show: true },
    },
    yAxis: {
      type: 'category',
      data: props.yCategories,
      axisLine: theme.axisLine,
      axisLabel: { color: theme.legend.textStyle.color },
      splitArea: { show: true },
    },
    visualMap: {
      min: 0,
      max: maxVal,
      calculable: true,
      orient: 'horizontal',
      left: 'center',
      bottom: 0,
      textStyle: { color: theme.legend.textStyle.color },
      inRange: { color: ['#0a1929', '#00d4ff', '#ff4757'] },
    },
    series: [{
      name: props.title || '热力',
      type: 'heatmap',
      data: props.data.map(d => [d.x, d.y, d.value]),
      label: { show: false },
      emphasis: {
        itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0, 0, 0, 0.5)' },
      },
    }],
  }
})
</script>

<style scoped>
.chart {
  width: 100%;
  height: v-bind(height);
}
</style>
