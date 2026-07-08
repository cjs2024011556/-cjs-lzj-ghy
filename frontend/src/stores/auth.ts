/**
 * 鉴权 Store（mock 登录版）
 *
 * 提供：
 * - 3 个 mock 账号（admin / 检修员 / 审核员）
 * - localStorage 持久化 token
 * - 路由元信息 auth.requiresAuth 守卫
 * - **登录态变化时同步切换 chatHistory.setUser（聊天历史按用户隔离）**
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { useChatHistoryStore } from './chatHistory'

export interface UserInfo {
  username: string
  display_name: string
  role: 'admin' | 'engineer' | 'reviewer'
  department: string
  login_at: string
}

const STORAGE_KEY = 'a1_auth'

// Mock 账号库（演示用，密码均为 123456）
const MOCK_USERS: Record<string, { password: string; user: UserInfo }> = {
  admin: {
    password: '123456',
    user: {
      username: 'admin',
      display_name: '系统管理员',
      role: 'admin',
      department: '信息技术部',
      login_at: '',
    },
  },
  zhang: {
    password: '123456',
    user: {
      username: 'zhang',
      display_name: '张班长',
      role: 'engineer',
      department: '焊装车间 A 班',
      login_at: '',
    },
  },
  wang: {
    password: '123456',
    user: {
      username: 'wang',
      display_name: '王师傅',
      role: 'engineer',
      department: '总装车间',
      login_at: '',
    },
  },
  li: {
    password: '123456',
    user: {
      username: 'li',
      display_name: '李工',
      role: 'reviewer',
      department: '设备工程部',
      login_at: '',
    },
  },
}

export const useAuthStore = defineStore('auth', () => {
  const user = ref<UserInfo | null>(null)
  const token = ref<string>('')

  const isLoggedIn = computed(() => !!token.value && !!user.value)
  const displayName = computed(() => user.value?.display_name || '未登录')
  const role = computed(() => user.value?.role || 'guest')

  /** 从 localStorage 恢复（刷新不掉登录） */
  function restore() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY)
      if (raw) {
        const data = JSON.parse(raw)
        user.value = data.user
        token.value = data.token
        // 注意：不要在这里调 setUser()，路由守卫运行早于 chatHistory store 初始化
        // setUser 由 Layout.vue 的 onMounted 统一调用
      }
    } catch (e) {
      console.error('恢复登录状态失败:', e)
    }
  }

  /** 登录 */
  function login(username: string, password: string): { success: boolean; message?: string } {
    const u = MOCK_USERS[username]
    if (!u) {
      return { success: false, message: '账号不存在' }
    }
    if (u.password !== password) {
      return { success: false, message: '密码错误' }
    }
    user.value = { ...u.user, login_at: new Date().toISOString() }
    // Mock token（base64 编码 username + 时间戳）
    token.value = btoa(`${username}:${Date.now()}`)

    // 持久化
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({ user: user.value, token: token.value }))
    } catch (e) {
      console.error('保存登录状态失败:', e)
    }
    // 切换聊天历史到当前用户
    useChatHistoryStore().setUser(user.value.username)
    return { success: true }
  }

  /** 登出 */
  function logout() {
    user.value = null
    token.value = ''
    localStorage.removeItem(STORAGE_KEY)
    // 清空内存中的聊天历史（不动其他用户的 localStorage 数据）
    useChatHistoryStore().setUser(null)
  }

  /** 切换账号（演示用） */
  function switchTo(username: string) {
    const u = MOCK_USERS[username]
    if (u) {
      logout()
      return login(username, u.password)
    }
    return { success: false, message: '账号不存在' }
  }

  return {
    user,
    token,
    isLoggedIn,
    displayName,
    role,
    restore,
    login,
    logout,
    switchTo,
  }
})

export { MOCK_USERS }
