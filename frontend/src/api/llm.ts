/**
 * LLM 管理 API
 */
import { get, post } from './index'

export interface LLMStatus {
  mode: string
  model: string
  available: boolean
  message: string
}

export function getLLMStatus() {
  return get<LLMStatus>('/llm/status')
}

export function switchLLMMode(mode: 'cloud' | 'local') {
  return post<{ success: boolean; mode: string; model: string }>('/llm/switch', { mode })
}

export function testChat(message: string) {
  return post<{
    content: string
    model: string
    usage: any
    latency_ms: number
  }>('/llm/test', { message })
}
