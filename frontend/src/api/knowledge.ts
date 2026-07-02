/**
 * 知识管理 API
 */
import { post, get } from './index'

export interface CaseRecord {
  case_id: string
  title: string
  equipment_type: string
  equipment_model: string
  fault_description: string
  solution: string
  tags: string[]
  status: 'pending' | 'approved' | 'rejected'
  submitter: string
  reviewer?: string
  review_comment?: string
  submitted_at: string
  indexed_count?: number
}

export interface Feedback {
  feedback_id: string
  query: string
  original_answer: string
  correction: string
  rating: number
  user: string
  created_at: string
}

export function submitCase(payload: {
  title: string
  equipment_type: string
  equipment_model?: string
  fault_description: string
  solution: string
  tags?: string[]
  submitter?: string
}) {
  return post<CaseRecord>('/knowledge/case/submit', payload)
}

export function reviewCase(payload: {
  case_id: string
  approved: boolean
  reviewer?: string
  review_comment?: string
}) {
  return post<CaseRecord>('/knowledge/case/review', payload)
}

export function listCases(status?: string) {
  return get<{ cases: CaseRecord[] }>('/knowledge/case/list', {
    params: status ? { status } : {},
  })
}

export function submitFeedback(payload: {
  query: string
  original_answer: string
  correction?: string
  rating?: number
  user?: string
}) {
  return post<Feedback>('/knowledge/feedback', payload)
}

export function listFeedback() {
  return get<{ feedback: Feedback[] }>('/knowledge/feedback')
}

export function importAll() {
  return post<any>('/knowledge/import/all')
}

export function importManuals() {
  return post<any>('/knowledge/import/manuals')
}

export function importCases() {
  return post<any>('/knowledge/import/cases')
}

export function importSops() {
  return post<any>('/knowledge/import/sops')
}

export function knowledgeStats() {
  return get<{
    total_chunks: number
    total_cases: number
    pending_cases: number
    approved_cases: number
    total_feedback: number
  }>('/knowledge/stats')
}
