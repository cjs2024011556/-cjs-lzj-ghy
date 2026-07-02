/**
 * ECharts 主题 - 从 design tokens 映射
 * 通过 getComputedStyle 读 CSS 变量，主题切换时自动跟随
 */

export interface EChartsTheme {
  backgroundColor: string
  textStyle: { color: string; fontFamily: string }
  title: { textStyle: { color: string } }
  legend: { textStyle: { color: string } }
  axisLine: { lineStyle: { color: string } }
  splitLine: { lineStyle: { color: string } }
  tooltip: { backgroundColor: string; borderColor: string; textStyle: { color: string } }
  color: string[]
}

function getCssVar(name: string, fallback = ''): string {
  if (typeof window === 'undefined') return fallback
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim()
  return v || fallback
}

export function buildEchartsTheme(): EChartsTheme {
  const primary = getCssVar('--primary-color', '#00d4ff')
  const success = getCssVar('--success', '#00d97e')
  const warning = getCssVar('--warning', '#ffb84d')
  const danger = getCssVar('--danger', '#ff4757')
  const info = getCssVar('--info', '#00d4ff')
  const purple = '#a855f7'
  const textPrimary = getCssVar('--text-primary', '#e6f1ff')
  const textMuted = getCssVar('--text-muted', '#8892b0')
  const bgSecondary = getCssVar('--bg-secondary', '#112240')
  const bgTertiary = getCssVar('--bg-tertiary', '#1a3654')
  const borderColor = getCssVar('--border-color', '#1e3a5f')
  const fontFamily = getCssVar('--font-family', 'system-ui, sans-serif')

  return {
    backgroundColor: 'transparent',
    textStyle: { color: textPrimary, fontFamily },
    title: { textStyle: { color: textPrimary } },
    legend: { textStyle: { color: textMuted } },
    axisLine: { lineStyle: { color: borderColor } },
    splitLine: { lineStyle: { color: borderColor } },
    tooltip: {
      backgroundColor: bgSecondary,
      borderColor: borderColor,
      textStyle: { color: textPrimary },
    },
    color: [primary, success, warning, danger, info, purple],
  }
}

/**
 * 通用 grid 边距（4 图统一）
 */
export const defaultGrid = {
  left: 50,
  right: 24,
  top: 40,
  bottom: 36,
  containLabel: true,
}
