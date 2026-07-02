/**
 * 健康检查 API
 */
import { get } from './index'

export interface HealthInfo {
  status: string
  app: string
  version: string
  env: string
  llm_mode: string
  llm_model: string
  timestamp: string
}

export function getHealth() {
  return get<HealthInfo>('/health')
}
