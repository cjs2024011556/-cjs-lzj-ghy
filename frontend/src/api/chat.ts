/**
 * 聊天 API（首页 - ChatGPT 风格）
 * - sendChat: 一次性返回
 * - streamChat: SSE 流式（打字机效果）
 */
import { post } from './index'

export interface ChatTurnMessage {
  role: 'user' | 'assistant'
  content: string
}

export interface ChatSource {
  chunk_id: string
  content: string
  source: string
  score: number
  equipment_type: string
  equipment_model: string
}

export interface ChatResponse {
  intent: 'maintenance' | 'casual'
  confidence: number
  reason: string
  answer: string
  sources: ChatSource[]
  model: string
  latency_ms: number
  used_rag: boolean
  retrieval_latency_ms: number
}

export interface ChatRequestPayload {
  message: string
  history?: ChatTurnMessage[]
  top_k?: number
}

// ============================================================
// 非流式（保留兼容）
// ============================================================
export async function sendChat(req: ChatRequestPayload): Promise<ChatResponse> {
  return await post<ChatResponse>('/chat', req)
}

// ============================================================
// 流式（SSE，打字机效果）
// ============================================================
export interface StreamCallbacks {
  onIntent?: (data: { intent: string; confidence: number; reason: string }) => void
  onSources?: (data: { sources: ChatSource[]; used_rag: boolean }) => void
  onDelta?: (content: string) => void
  onDone?: (data: { model: string; latency_ms: number; used_rag: boolean; total_chars: number }) => void
  onError?: (message: string) => void
}

export interface StreamHandle {
  abort: () => void
}

/**
 * 流式聊天（SSE）
 * - 走 fetch + ReadableStream，不走 axios（浏览器对 stream 支持差）
 * - 解析 SSE 协议（event:/data:）
 */
export function streamChat(
  req: ChatRequestPayload,
  callbacks: StreamCallbacks,
): StreamHandle {
  const controller = new AbortController()
  const apiBase = (import.meta.env.VITE_API_BASE as string) || 'http://localhost:8000'

  ;(async () => {
    try {
      const resp = await fetch(`${apiBase}/api/v1/chat/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(req),
        signal: controller.signal,
      })

      if (!resp.ok || !resp.body) {
        callbacks.onError?.(`HTTP ${resp.status}: ${await resp.text()}`)
        return
      }

      const reader = resp.body.getReader()
      const decoder = new TextDecoder('utf-8')
      let buffer = ''
      let currentEvent = 'message'

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() ?? ''  // 保留不完整行

        for (const line of lines) {
          if (!line) continue
          if (line.startsWith('event:')) {
            currentEvent = line.slice(6).trim()
          } else if (line.startsWith('data:')) {
            const dataStr = line.slice(5).trim()
            if (!dataStr) continue
            try {
              const data = JSON.parse(dataStr)
              switch (currentEvent) {
                case 'intent':
                  callbacks.onIntent?.(data)
                  break
                case 'sources':
                  callbacks.onSources?.(data)
                  break
                case 'delta':
                  callbacks.onDelta?.(data.content || '')
                  break
                case 'done':
                  callbacks.onDone?.(data)
                  break
                case 'error':
                  callbacks.onError?.(data.message || '未知错误')
                  break
              }
            } catch (e) {
              console.warn('SSE data 解析失败:', e, dataStr.slice(0, 100))
            }
          }
        }
      }
    } catch (e: any) {
      if (e.name === 'AbortError') {
        // 用户主动取消，忽略
        return
      }
      console.error('SSE 连接错误:', e)
      callbacks.onError?.(e?.message || '网络错误')
    }
  })()

  return {
    abort: () => controller.abort(),
  }
}
