/**
 * 检索相关 API
 */
import { post, postForm, get } from './index'

export interface RetrievalHit {
  chunk_id: string
  content: string
  source: string
  doc_type: string
  equipment_type: string
  equipment_model: string
  score: number
  chunk_index: number
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

export interface RetrievalResponse {
  query: string
  answer: string
  hits: RetrievalHit[]
  model: string
  latency_ms: number
  usage: Record<string, number>
}

export function retrieveByText(payload: {
  query: string
  equipment_model?: string
  top_k?: number
}) {
  return post<RetrievalResponse>('/retrieval/text', payload)
}

export function retrieveMultimodal(formData: FormData) {
  return postForm<RetrievalResponse>('/retrieval/multimodal', formData)
}

export function retrievalStats() {
  return get<{ indexed_chunks: number }>('/retrieval/stats')
}
