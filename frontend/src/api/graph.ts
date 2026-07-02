/**
 * 故障图谱 API
 */
import { get, post } from './index'

export interface GraphNode {
  id: string
  label: string
  type: string
  color: string
  title: string
  value: number
}

export interface GraphEdge {
  source: string
  target: string
  label: string
  weight: number
  arrows: string
}

export interface GraphData {
  nodes: GraphNode[]
  edges: GraphEdge[]
  matched_keywords?: string[]
  matched_count?: number
}

export interface GraphStats {
  total_nodes: number
  total_edges: number
  node_types: Record<string, number>
  rel_types: Record<string, number>
  density: number
}

export async function visualizeGraph(maxNodes: number = 200): Promise<GraphData> {
  return await get<GraphData>('/graph/visualize', { params: { max_nodes: maxNodes } })
}

export async function findRelated(keywords: string[], maxHops: number = 2): Promise<GraphData> {
  return await post<GraphData>('/graph/related', { keywords, max_hops: maxHops })
}

export async function getGraphStats(): Promise<GraphStats> {
  return await get<GraphStats>('/graph/stats')
}

export async function buildGraph(): Promise<{ success: boolean; stats: GraphStats }> {
  return await post<{ success: boolean; stats: GraphStats }>('/graph/build')
}
