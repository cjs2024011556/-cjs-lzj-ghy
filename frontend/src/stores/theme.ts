/**
 * 主题切换 Store
 * 暗色（默认）/ 亮色，通过 [data-theme] CSS 变量切换
 */
import { defineStore } from 'pinia'
import { ref, watch } from 'vue'

type ThemeMode = 'dark' | 'light'

const STORAGE_KEY = 'a1_theme'

export const useThemeStore = defineStore('theme', () => {
  const theme = ref<ThemeMode>('dark')

  function init() {
    try {
      const saved = localStorage.getItem(STORAGE_KEY) as ThemeMode | null
      if (saved === 'dark' || saved === 'light') {
        theme.value = saved
      } else {
        // 默认暗色
        theme.value = 'dark'
      }
    } catch {
      theme.value = 'dark'
    }
    apply()
  }

  function apply() {
    document.documentElement.setAttribute('data-theme', theme.value)
  }

  function setTheme(mode: ThemeMode) {
    theme.value = mode
    localStorage.setItem(STORAGE_KEY, mode)
    apply()
  }

  function toggle() {
    setTheme(theme.value === 'dark' ? 'light' : 'dark')
  }

  return { theme, init, setTheme, toggle }
})
