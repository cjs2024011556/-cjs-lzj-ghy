/**
 * 鉴权 Store（mock 登录版 + 本地注册）
 *
 * 提供：
 * - 4 个 mock 账号（admin / 检修员 / 审核员）
 * - 用户自助注册（持久化到 localStorage）
 * - localStorage 持久化 token
 * - 路由元信息 auth.requiresAuth 守卫
 * - **登录态变化时同步切换 chatHistory.setUser（聊天历史按用户隔离）**
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { useChatHistoryStore } from './chatHistory'

export type UserRole = 'admin' | 'engineer' | 'reviewer'

export interface UserInfo {
  username: string
  display_name: string
  role: UserRole
  department: string
  login_at: string
}

/** 注册表单 payload */
export interface RegisterPayload {
  username: string
  password: string
  confirm_password: string
  full_name: string
  department?: string
  role: 'admin' | 'engineer'  // 注册时只允许这两种
}

const STORAGE_KEY = 'a1_auth'
const REGISTERED_KEY = 'a1_registered_users'

/** 注册用户记录（含 hashed 密码，仅前端演示） */
interface RegisteredUserRecord {
  password: string
  user: UserInfo
}

// 角色中文显示名映射
const ROLE_LABEL: Record<UserRole, string> = {
  admin: '系统管理员',
  engineer: '普通用户',
  reviewer: '审核员',
}

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

/** 读取已注册用户 */
function loadRegisteredUsers(): Record<string, RegisteredUserRecord> {
  try {
    const raw = localStorage.getItem(REGISTERED_KEY)
    return raw ? JSON.parse(raw) : {}
  } catch (e) {
    console.error('读取已注册用户失败:', e)
    return {}
  }
}

/** 保存已注册用户 */
function saveRegisteredUsers(users: Record<string, RegisteredUserRecord>) {
  try {
    localStorage.setItem(REGISTERED_KEY, JSON.stringify(users))
  } catch (e) {
    console.error('保存已注册用户失败:', e)
  }
}

/** 用户名规则：字母开头，3-20 位字母/数字/下划线 */
const USERNAME_PATTERN = /^[A-Za-z][A-Za-z0-9_]{2,19}$/

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

  /** 登录（兼容 mock + 已注册用户） */
  function login(username: string, password: string): { success: boolean; message?: string } {
    // 1. 先查 mock 账号
    let record = MOCK_USERS[username]
    // 2. 再查已注册用户
    if (!record) {
      const registered = loadRegisteredUsers()
      record = registered[username]
    }
    if (!record) {
      return { success: false, message: '账号不存在' }
    }
    if (record.password !== password) {
      return { success: false, message: '密码错误' }
    }
    user.value = { ...record.user, login_at: new Date().toISOString() }
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

  /** 注册 */
  function register(payload: RegisterPayload): { success: boolean; message?: string } {
    // 1. 校验
    if (!USERNAME_PATTERN.test(payload.username)) {
      return { success: false, message: '账号必须以字母开头，仅含字母/数字/下划线，长度 3-20 位' }
    }
    if (payload.password.length < 6) {
      return { success: false, message: '密码至少 6 位' }
    }
    if (payload.password !== payload.confirm_password) {
      return { success: false, message: '两次输入的密码不一致' }
    }
    if (!payload.full_name.trim()) {
      return { success: false, message: '请输入姓名' }
    }
    if (!['admin', 'engineer'].includes(payload.role)) {
      return { success: false, message: '非法角色' }
    }

    // 2. 检查重名（mock + 已注册）
    if (MOCK_USERS[payload.username]) {
      return { success: false, message: '账号已存在' }
    }
    const registered = loadRegisteredUsers()
    if (registered[payload.username]) {
      return { success: false, message: '账号已存在' }
    }

    // 3. 写入
    registered[payload.username] = {
      password: payload.password,
      user: {
        username: payload.username,
        display_name: payload.full_name,
        role: payload.role,
        department: payload.department || '',
        login_at: '',
      },
    }
    saveRegisteredUsers(registered)

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
    let record = MOCK_USERS[username]
    if (!record) {
      const registered = loadRegisteredUsers()
      record = registered[username]
    }
    if (record) {
      logout()
      return login(username, record.password)
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
    register,
    logout,
    switchTo,
  }
})

export { MOCK_USERS, ROLE_LABEL }
export type { RegisteredUserRecord }