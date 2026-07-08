/**
 * 主题 Store — 仅保留白色简约风格（light）
 *
 * 历史：之前支持 dark/light 切换（任务 A3），现统一为 white 简约风格，
 * 移除切换按钮（ThemeSwitcher 已删除）。本 store 仍负责在启动时
 * 把 <html data-theme="light"> 应用上去，兼容旧用户 localStorage。
 */
import { defineStore } from 'pinia'

const STORAGE_KEY = 'a1_theme'
type ThemeMode = 'light' | 'dark'

export const useThemeStore = defineStore('theme', () => {
  function init() {
    // 不论 localStorage 之前存的是什么，都强制设为 light（白简约）
    apply('light')
    // 清掉旧值，避免误导
    try {
      localStorage.removeItem(STORAGE_KEY)
    } catch {
      /* localStorage 可能不可用，忽略 */
    }
  }

  function apply(mode: ThemeMode) {
    if (typeof document !== 'undefined') {
      document.documentElement.setAttribute('data-theme', mode)
    }
  }

  return { init }
})