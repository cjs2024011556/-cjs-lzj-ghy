/**
 * 路由守卫（auth.beforeEach + title.afterEach）
 */
import { ElMessage } from 'element-plus'
import type { Router, RouteLocationNormalized } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

export function setupAuthGuard(router: Router) {
  router.beforeEach((to, _from, next) => {
    const auth = useAuthStore()
    if (!auth.token) auth.restore()

    // 公开页面：登录、404
    if (to.meta.requiresAuth === false) {
      if (to.name === 'Login' && auth.isLoggedIn) return next('/home')
      return next()
    }

    // 未登录 → 跳登录页（带 redirect）
    if (!auth.isLoggedIn) {
      return next({ path: '/login', query: { redirect: to.fullPath } })
    }

    // 角色检查
    if (to.meta.requiresRole && auth.role !== to.meta.requiresRole) {
      ElMessage.error(`此页面需要 ${to.meta.requiresRole} 权限`)
      return next('/home')
    }

    next()
  })
}

export function setupTitleGuard(router: Router) {
  router.afterEach((to: RouteLocationNormalized) => {
    if (to.meta.title) {
      document.title = `${to.meta.title} - A1 设备检修智能系统`
    }
  })
}
