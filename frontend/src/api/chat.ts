/**
 * 聊天 API（智能问答 - ChatGPT 风格）
 * - sendChat: 一次性返回
 * - streamChat: SSE 流式（打字机效果）
 * - streamAgentChat: 工具链 ReAct Agent（聚群 C）
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
  // PDF-A.7 聚群 A: 结构化字段
  page_number?: number
  page_end?: number
  chapter?: string
  section_title?: string
  section_type?: 'text' | 'table' | 'heading' | 'footer'
  section_level?: number
  doc_id?: string
  // PDF-B.7 聚群 B: 视觉理解字段
  image_description?: string
  image_facts?: string
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

// 聚群 C: 工具调用事件
export interface ToolCallEvent {
  id: string
  name: string
  arguments: Record<string, any>
  step: number
}

export interface ToolResultEvent {
  id: string
  name: string
  ok: boolean
  result: any
  step: number
}

export interface ThoughtEvent {
  content: string
  step: number
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
  // 聚群 C: 工具调用事件
  onThought?: (data: ThoughtEvent) => void
  onToolCall?: (data: ToolCallEvent) => void
  onToolResult?: (data: ToolResultEvent) => void
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
      let parseErrorCount = 0  // 累计解析失败行数；超过阈值则在 stream 末尾提示用户

      // 阈值：偶发 1-2 次不打扰（容忍网络抖动），多次失败明确告知
      const PARSE_ERROR_WARN_THRESHOLD = 5

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
                // 聚群 C: 工具链事件
                case 'thought':
                  callbacks.onThought?.(data)
                  break
                case 'tool_call':
                  callbacks.onToolCall?.(data)
                  break
                case 'tool_result':
                  callbacks.onToolResult?.(data)
                  break
              }
            } catch (e) {
              console.warn('SSE data 解析失败:', e, dataStr.slice(0, 100))
              parseErrorCount++
            }
          }
        }
      }

      // Stream 正常结束后，若累计失败过多，提示用户消息可能不完整
      // 避免单次偶发失败打扰用户（容忍网络抖动），多次失败明确告知
      if (parseErrorCount >= PARSE_ERROR_WARN_THRESHOLD) {
        callbacks.onError?.(
          `流式响应可能不完整（${parseErrorCount} 行解析失败），建议重试`,
        )
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

// ============================================================
// 聚群 C: 工具链 ReAct Agent 流式
// ============================================================
export interface AgentRequestPayload {
  message: string
  history?: ChatTurnMessage[]
  max_steps?: number
}

export interface AgentCallbacks {
  onThought?: (data: ThoughtEvent) => void
  onToolCall?: (data: ToolCallEvent) => void
  onToolResult?: (data: ToolResultEvent) => void
  onAnswer?: (data: { content: string; step: number }) => void
  onError?: (message: string) => void
  onDone?: (data: { model: string; latency_ms: number; events_count: number; final_answer: string }) => void
}

export function streamAgentChat(
  req: AgentRequestPayload,
  callbacks: AgentCallbacks,
): StreamHandle {
  const controller = new AbortController()
  const apiBase = (import.meta.env.VITE_API_BASE as string) || 'http://localhost:8000'

  ;(async () => {
    try {
      const resp = await fetch(`${apiBase}/api/v1/chat/agent`, {
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
      let parseErrorCount = 0

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() ?? ''

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
                case 'thought':
                  callbacks.onThought?.(data)
                  break
                case 'tool_call':
                  callbacks.onToolCall?.(data)
                  break
                case 'tool_result':
                  callbacks.onToolResult?.(data)
                  break
                case 'answer':
                  callbacks.onAnswer?.(data)
                  break
                case 'done':
                  callbacks.onDone?.(data)
                  break
                case 'error':
                  callbacks.onError?.(data.message || '未知错误')
                  break
              }
            } catch (e) {
              console.warn('Agent SSE parse fail:', e, dataStr.slice(0, 100))
              parseErrorCount++
            }
          }
        }
      }
    } catch (e: any) {
      if (e.name === 'AbortError') return
      console.error('Agent SSE error:', e)
      callbacks.onError?.(e?.message || '网络错误')
    }
  })()

  return {
    abort: () => controller.abort(),
  }
}

// ============================================================
// 聚群 C: 评测端点
// ============================================================
export interface EvalReport {
  timestamp: string
  elapsed_ms: number
  total: number
  top_k: number
  metrics: {
    total: number
    hit_rate_at_5: number
    hit_rate_at_10: number
    mrr: number
    ndcg_at_5: number
    ndcg_at_10: number
    citation_accuracy: number | null
  }
  items: Array<{
    query: string
    hit: boolean
    first_relevant_rank: number | null
    ndcg: number
    citation_correct: boolean | null
  }>
}

export function runEval(top_k = 5): Promise<EvalReport> {
  return post<EvalReport>(`/chat/eval/run?top_k=${top_k}`)
}

export function getEvalReport(path = 'logs/eval_report.json'): Promise<EvalReport> {
  return post<EvalReport>(`/chat/eval/report?path=${encodeURIComponent(path)}`)
}
