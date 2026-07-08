/**
 * 路由表（只声明路由 + meta，守卫拆到 guards.ts）
 */
import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'
import '@/types/router.d.ts'  // 触发 RouteMeta 类型扩展
import { setupAuthGuard, setupTitleGuard } from './guards'

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/Login.vue'),
    meta: { title: '登录', requiresAuth: false },
  },
  {
    path: '/',
    component: () => import('@/views/Layout.vue'),
    redirect: '/home',
    meta: { requiresAuth: true },
    children: [
      {
        path: 'home',
        name: 'Home',
        component: () => import('@/views/Home.vue'),
        meta: { title: '智能问答', icon: 'HomeFilled', keepAlive: true, group: '业务', showChatSidebar: true },
      },
      {
        path: 'retrieval',
        name: 'Retrieval',
        component: () => import('@/views/Retrieval.vue'),
        meta: { title: '多模态检索', icon: 'Search', keepAlive: true, group: '业务' },
      },
      {
        path: 'operation-guide',
        name: 'OperationGuide',
        component: () => import('@/views/OperationGuide.vue'),
        meta: { title: '作业指引', icon: 'Document', keepAlive: true, group: '业务' },
      },
      {
        path: 'knowledge',
        name: 'Knowledge',
        component: () => import('@/views/Knowledge.vue'),
        meta: { title: '知识管理', icon: 'Notebook', keepAlive: true, group: '业务' },
      },
      {
        path: 'graph',
        name: 'Graph',
        component: () => import('@/views/Graph.vue'),
        meta: { title: '故障图谱', icon: 'Share', keepAlive: true, group: '业务' },
      },
      {
        path: 'eval-report',
        name: 'EvalReport',
        component: () => import('@/views/EvalReport.vue'),
        meta: { title: '评测报告', icon: 'DataAnalysis', keepAlive: true, group: '业务' },
      },
      {
        path: 'knowledge-admin',
        name: 'KnowledgeAdmin',
        component: () => import('@/views/KnowledgeAdmin.vue'),
        meta: { title: '知识库管理', icon: 'Files', keepAlive: true, group: '管理', requiresRole: 'admin', badge: 'U6' },
      },
      {
        path: 'admin',
        name: 'Admin',
        component: () => import('@/views/Admin.vue'),
        meta: { title: '后台管理', icon: 'Setting', keepAlive: true, group: '管理', requiresRole: 'admin' },
      },
    ],
  },
  {
    path: '/404',
    name: 'NotFound',
    component: () => import('@/views/NotFound.vue'),
    meta: { requiresAuth: false },
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: '/404',
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// 守卫（分离）
setupAuthGuard(router)
setupTitleGuard(router)

export default router
