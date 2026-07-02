/**
 * 作业指引 API
 */
import { post, get } from './index'

export interface Step {
  step_no: number
  title: string
  action: string
  risk_level: 'low' | 'medium' | 'high' | string
  tools: string[]
  compliance: string[]
  estimated_minutes: number
}

export interface GuideResponse {
  sop_id: string
  name: string
  equipment_type: string
  equipment_model?: string
  maintenance_level: string
  estimated_minutes: number
  tools: string[]
  safety_warnings: string[]
  steps: Step[]
  personalized_notes?: string
  source: string
  model: string
  latency_ms: number
}

export function generateGuide(payload: {
  equipment_type: string
  equipment_model?: string
  maintenance_level: string
  fault_description?: string
}) {
  return post<GuideResponse>('/operation-guide/generate', payload)
}

export function listSops() {
  return get<{ sops: any[] }>('/operation-guide/sops')
}

export function listMaintenanceLevels() {
  return get<{ levels: { code: string; name: string }[] }>('/operation-guide/levels')
}
