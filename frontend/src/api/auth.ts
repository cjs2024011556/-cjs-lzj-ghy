/**
 * 认证相关 API
 *
 * 当前状态：
 * - 后端 stub 模式（POST /api/v1/auth/register 返回 503）
 * - 前端实际注册通过 stores/auth.ts 的 localStorage 完成
 * - 本文件为未来真接后端预留调用入口
 */
import { post } from './index'

export interface RegisterRequest {
  username: string
  password: string
  confirm_password: string
  full_name: string
  department?: string
  role: 'admin' | 'engineer'
}

export interface RegisterResponse {
  success: boolean
  message: string
  user?: {
    username: string
    full_name: string
    role: string
    department: string
  }
}

/**
 * 调用后端注册接口
 *
 * 当前后端返回 503（待数据库连接后启用）。
 * 失败会被统一拦截器转成 ElMessage.error，前端 catch 后回退到本地注册。
 */
export async function registerUser(payload: RegisterRequest): Promise<RegisterResponse> {
  try {
    return await post<RegisterResponse>('/auth/register', payload)
  } catch (e) {
    // 后端未启用时返回 503，由调用方决定是否回退到本地注册
    return { success: false, message: '后端注册暂未启用，已使用本地注册' }
  }
}