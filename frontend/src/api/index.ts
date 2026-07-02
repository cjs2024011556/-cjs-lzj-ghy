/**
 * API 客户端 - axios 封装
 */
import axios, { type AxiosInstance, type AxiosRequestConfig } from 'axios'
import { ElMessage } from 'element-plus'

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000'

const instance: AxiosInstance = axios.create({
  baseURL: `${API_BASE}/api/v1`,
  timeout: 60000,
  headers: { 'Content-Type': 'application/json' },
})

// 请求拦截
instance.interceptors.request.use(
  (config) => {
    // 未来加 token
    return config
  },
  (err) => Promise.reject(err),
)

// 响应拦截
instance.interceptors.response.use(
  (resp) => resp.data,
  (err) => {
    const msg = err.response?.data?.detail || err.response?.data?.message || err.message
    ElMessage.error(`请求失败: ${msg}`)
    return Promise.reject(err)
  },
)

export async function get<T = any>(url: string, config?: AxiosRequestConfig): Promise<T> {
  return instance.get(url, config)
}

export async function post<T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T> {
  return instance.post(url, data, config)
}

export async function postForm<T = any>(url: string, formData: FormData, config?: AxiosRequestConfig): Promise<T> {
  return (await instance.post(url, formData, config)).data
}

export async function del<T = any>(url: string, config?: AxiosRequestConfig): Promise<T> {
  return (await instance.delete(url, config)).data
}
