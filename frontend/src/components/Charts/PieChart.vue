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
import { PieChart } from 'echarts/charts'
import {
  TitleComponent,
  TooltipComponent,
  LegendComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'
import { buildEchartsTheme } from '@/utils/echarts-theme'

use([PieChart, TitleComponent, TooltipComponent, LegendComponent, CanvasRenderer])

interface PieData {
  name: string
  value: number
}

const props = withDefaults(defineProps<{
  data: PieData[]
  title?: string
  height?: string
  showLegend?: boolean
  roseType?: boolean
}>(), {
  height: '280px',
  showLegend: true,
  roseType: false,
})

const initOptions = computed(() => ({ renderer: 'canvas' as const }))

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
      trigger: 'item',
      backgroundColor: theme.tooltip.backgroundColor,
      borderColor: theme.tooltip.borderColor,
      textStyle: theme.tooltip.textStyle,
      formatter: '{b}: {c} ({d}%)',
    },
    legend: props.showLegend ? {
      orient: 'vertical',
      right: 0,
      top: 'middle',
      textStyle: theme.legend.textStyle,
    } : { show: false },
    series: [{
      name: props.title || '占比',
      type: 'pie',
      radius: props.roseType ? ['30%', '70%'] : ['50%', '75%'],
      center: props.showLegend ? ['38%', '55%'] : ['50%', '55%'],
      avoidLabelOverlap: true,
      itemStyle: { borderRadius: 4, borderColor: theme.backgroundColor, borderWidth: 2 },
      label: { color: theme.textStyle.color, formatter: '{b}\n{d}%' },
      labelLine: { lineStyle: { color: theme.legend.textStyle.color } },
      data: props.data,
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
