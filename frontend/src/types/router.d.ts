/**
 * 路由 meta 类型约束（强类型 + 业务字段）
 */
import 'vue-router'

export const Role = {
  Admin: 'admin',
  Engineer: 'engineer',
  Reviewer: 'reviewer',
} as const
export type Role = typeof Role[keyof typeof Role]

declare module 'vue-router' {
  interface RouteMeta {
    /** 页面标题（用于面包屑 + document.title）*/
    title?: string
    /** 是否需要登录 */
    requiresAuth?: boolean
    /** 角色限制（满足其一即可）*/
    requiresRole?: Role
    /** 侧边栏菜单图标 */
    icon?: string
    /** 分组（用于侧边栏分类）*/
    group?: '业务' | '管理'
    /** keep-alive */
    keepAlive?: boolean
    /** 是否显示 ChatSidebar 布局（仅 Home 用）*/
    showChatSidebar?: boolean
  }
}

export {}
