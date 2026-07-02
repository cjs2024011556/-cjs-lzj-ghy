/**
 * echarts 初始化 + 主题 + 配置工厂（合并 4 个 chart 组件的 use() / initOptions / buildEchartsTheme 重复）
 *
 * 用法：
 *   const { initOptions, buildTooltip, buildAxis, getTheme } = useEcharts()
 *   return { option: computed(() => ({ ...initOptions(), tooltip: buildTooltip(...), series: [...] })) }
 */
import { computed, watch, onUnmounted } from 'vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import {
  LineChart, BarChart, PieChart, GaugeChart, HeatmapChart,
} from 'echarts/charts'
import {
  TitleComponent, TooltipComponent, LegendComponent, GridComponent,
  VisualMapComponent, DataZoomComponent, MarkLineComponent, MarkAreaComponent,
} from 'echarts/components'
import { buildEchartsTheme, type EChartsTheme } from '@/utils/echarts-theme'

// 全局注册一次（多次调用安全）
let registered = false
function ensureRegistered() {
  if (registered) return
  use([
    LineChart, BarChart, PieChart, GaugeChart, HeatmapChart,
    TitleComponent, TooltipComponent, LegendComponent, GridComponent,
    VisualMapComponent, DataZoomComponent, MarkLineComponent, MarkAreaComponent,
    CanvasRenderer,
  ])
  registered = true
}

export function useEcharts() {
  ensureRegistered()

  /** echarts init options（renderer + 主题） */
  const initOptions = computed(() => ({
    renderer: 'canvas' as const,
  }))

  /** 缓存 theme（避免每次响应式触发 12 次 getComputedStyle） */
  let cachedTheme: EChartsTheme | null = null
  let cachedThemeKey = ''
  function getTheme() {
    const dataTheme = document.documentElement.getAttribute('data-theme') || 'light'
    if (cachedTheme && cachedThemeKey === dataTheme) return cachedTheme
    cachedTheme = buildEchartsTheme()
    cachedThemeKey = dataTheme
    return cachedTheme
  }

  /** data-theme 变化时清缓存 */
  const obs = new MutationObserver(() => {
    cachedTheme = null
  })
  obs.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] })
  onUnmounted(() => obs.disconnect())

  /** 通用 tooltip 配置 */
  function buildTooltip(trigger: 'axis' | 'item' = 'axis') {
    const t = getTheme()
    return {
      trigger,
      backgroundColor: t.tooltip.backgroundColor,
      borderColor: t.tooltip.borderColor,
      textStyle: t.tooltip.textStyle,
      ...(trigger === 'item' ? { formatter: '{b}: {c} ({d}%)' } : {}),
    }
  }

  /** 通用 grid 配置 */
  function buildGrid(extra: { top?: number; left?: number; right?: number; bottom?: number } = {}) {
    return {
      left: 50,
      right: 24,
      top: 40,
      bottom: 36,
      containLabel: true,
      ...extra,
    }
  }

  /** 通用坐标轴样式 */
  function buildAxis(theme = getTheme()) {
    return {
      axisLine: theme.axisLine,
      splitLine: theme.splitLine,
      axisLabel: { color: theme.legend.textStyle.color },
    }
  }

  /** 通用标题 */
  function buildTitle(text: string) {
    return {
      text,
      textStyle: getTheme().title.textStyle,
      left: 0,
      top: 0,
    }
  }

  return {
    initOptions,
    getTheme,
    buildTooltip,
    buildGrid,
    buildAxis,
    buildTitle,
  }
}
