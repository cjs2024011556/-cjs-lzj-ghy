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
import { GaugeChart } from 'echarts/charts'
import { TitleComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'
import { buildEchartsTheme } from '@/utils/echarts-theme'

use([GaugeChart, TitleComponent, TooltipComponent, CanvasRenderer])

const props = withDefaults(defineProps<{
  value: number
  title?: string
  unit?: string
  min?: number
  max?: number
  height?: string
  color?: 'primary' | 'success' | 'warning' | 'danger'
}>(), {
  min: 0,
  max: 100,
  height: '280px',
  unit: '%',
  color: 'primary',
})

const initOptions = computed(() => ({ renderer: 'canvas' as const }))

const chartOption = computed(() => {
  const theme = buildEchartsTheme()
  const colorMap = {
    primary: ['#00d4ff', '#0a4a6a'],
    success: ['#00d97e', '#0a5a3a'],
    warning: ['#ffb84d', '#6a4a0a'],
    danger: ['#ff4757', '#6a1a2a'],
  }
  const [c1, c2] = colorMap[props.color]
  return {
    backgroundColor: theme.backgroundColor,
    title: props.title ? {
      text: props.title,
      textStyle: theme.title.textStyle,
      left: 0,
      top: 0,
    } : undefined,
    series: [{
      type: 'gauge',
      radius: '90%',
      center: ['50%', '60%'],
      startAngle: 200,
      endAngle: -20,
      min: props.min,
      max: props.max,
      progress: { show: true, width: 16, itemStyle: { color: c1 } },
      axisLine: { lineStyle: { width: 16, color: [[1, c2]] } },
      pointer: { show: false },
      axisTick: { show: false },
      splitLine: { show: false },
      axisLabel: { show: false },
      anchor: { show: false },
      title: { show: false },
      detail: {
        valueAnimation: true,
        formatter: (v: number) => '{value|' + v.toFixed(1) + '}{unit|' + props.unit + '}',
        rich: {
          value: { fontSize: 36, fontWeight: 'bold', color: c1 },
          unit: { fontSize: 14, color: theme.legend.textStyle.color, padding: [0, 0, 0, 4] },
        },
        offsetCenter: [0, '10%'],
      },
      data: [{ value: props.value }],
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
