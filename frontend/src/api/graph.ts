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

export interface NeighborInfo {
  id: string
  label: string
  type: string
  color: string
  weight: number
}

export interface NeighborGroup {
  rel_type: string
  count: number
  neighbors: NeighborInfo[]
}

export interface NodeNeighborhood {
  node: {
    id: string
    label: string
    type: string
    color: string
    degree: number
    in_degree: number
    out_degree: number
    attrs: Record<string, any>
  } | null
  outgoing: NeighborGroup[]
  incoming: NeighborGroup[]
  summary: {
    total_out: number
    total_in: number
    total_unique_neighbors: number
    by_rel_type: Record<string, number>
  }
  error?: string
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

export async function getNodeNeighborhood(nodeId: string): Promise<NodeNeighborhood> {
  return await get<NodeNeighborhood>(`/graph/node/${encodeURIComponent(nodeId)}/neighborhood`)
}

export interface GraphAnalytics {
  top_degree_centrality: Array<{
    id: string
    label: string
    type: string
    color: string
    degree: number
  }>
  connected_components: {
    count: number
    max_size: number
    sizes_distribution: Record<string, number>
  }
  node_type_density: Record<string, number>
  rel_type_density: Record<string, number>
  shortest_path_sample: {
    source: { id: string; label: string; type: string; color: string }
    target: { id: string; label: string; type: string; color: string }
    path: Array<{ id: string; label: string; type: string; color: string }>
    length: number
  } | null
}

export async function getGraphAnalytics(): Promise<GraphAnalytics> {
  return await get<GraphAnalytics>('/graph/analytics')
}
