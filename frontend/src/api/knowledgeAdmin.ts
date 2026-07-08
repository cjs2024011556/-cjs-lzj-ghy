/**
 * 知识库管理 API
 */
import { post, get, del } from './index'

export interface ManualFile {
  name: string
  size_kb: number
  mtime: number
}

export interface UploadResult {
  success: boolean
  filename: string
  path: string
  md_copy?: string | null
  size_kb: number
  section_count: number
  indexed_in_milvus: boolean
  searchable_now: boolean
  // PDF-A.6: 结构化摘要
  structure?: ManualStructureSummary | null
  message: string
}

export interface ImportResult {
  results: Record<string, number>
  total_files: number
}

export interface ManualContent {
  filename: string
  ext: string
  size_kb: number
  content: string
  truncated: boolean
}

// PDF-A.6: 结构化摘要
export interface OutlineItem {
  level: number         // 1=H1 / 2=H2 / 3=H3
  title: string
  page_start: number
}

export interface TableDigestItem {
  page: number
  rows: number
  cols: number
  preview: string
}

export interface ManualStructureSummary {
  outline: OutlineItem[]
  tables: TableDigestItem[]
  page_count: number
  chunk_count: number
  cached_at?: number
}

export interface ManualStructure {
  filename: string
  ext: string
  outline: OutlineItem[]
  tables: TableDigestItem[]
  page_count: number
  chunk_count: number
  cached: boolean
  note?: string
}

export interface ReindexResult {
  success: boolean
  reindexed?: number
  deleted?: number
  filename?: string
  total_chunks?: number
  total_vl_pages?: number   // PDF-B.6
  vl_pages_processed?: number   // PDF-B.6
  files?: Array<{ filename: string; chunks?: number; vl_pages?: number; ok: boolean; error?: string }>
}

// PDF-B.6: 视觉重分析结果
export interface ReanalyzeResult {
  success?: boolean
  reindexed?: number
  deleted?: number
  vl_pages_processed?: number
  filename?: string
  total_chunks?: number
  total_vl_pages?: number
  files?: Array<{ filename: string; chunks?: number; vl_pages?: number; ok: boolean; error?: string }>
}

/** 上传知识文档（U4 + PDF-A.6 自动构建结构摘要）

注：大 PDF 解析 + Milvus 索引可能耗时 15-30s，
    因此超时设 180s（默认 60s 不够）。
*/
export async function uploadManual(file: File, onProgress?: (p: number) => void): Promise<UploadResult> {
  const form = new FormData()
  form.append('file', file)
  return await post<UploadResult>('/knowledge/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 180_000,  // 180s: 适配大 PDF 解析 + Milvus 索引
    onUploadProgress: (e) => {
      if (onProgress && e.total) onProgress(Math.round((e.loaded * 100) / e.total))
    },
  })
}

/** 列出已上传的 manuals */
export async function listManuals(): Promise<{ manuals: ManualFile[]; total: number }> {
  return await get<{ manuals: ManualFile[]; total: number }>('/knowledge/manuals')
}

/** 触发全量 manuals 重建索引（关键词 fallback 重新解析）*/
export async function importManuals(): Promise<ImportResult> {
  return await post<ImportResult>('/knowledge/import/manuals')
}

/** 删除上传的 manual */
export async function deleteManual(filename: string): Promise<{ deleted: string }> {
  return await del<{ deleted: string }>(`/knowledge/manuals/${encodeURIComponent(filename)}`)
}

/** FEAT: 查看上传 manual 的内容（md 直接返回文本，pdf/docx 返回解析后的 markdown）*/
export async function getManualContent(filename: string): Promise<ManualContent> {
  return await get<ManualContent>(`/knowledge/manuals/${encodeURIComponent(filename)}/content`)
}

// PDF-A.6: 结构化摘要 + 重建索引
export async function getManualStructure(filename: string): Promise<ManualStructure> {
  return await get<ManualStructure>(`/knowledge/manuals/${encodeURIComponent(filename)}/structure`)
}

export async function reindexManual(filename: string): Promise<ReindexResult> {
  return await post<ReindexResult>(`/knowledge/manuals/${encodeURIComponent(filename)}/reindex`)
}

export async function reindexAll(): Promise<ReindexResult> {
  return await post<ReindexResult>('/knowledge/reindex')
}

// PDF-B.6: 视觉重分析
export async function reanalyzeManual(filename: string, force = false): Promise<ReanalyzeResult> {
  return await post<ReanalyzeResult>(
    `/knowledge/manuals/${encodeURIComponent(filename)}/re-analyze${force ? '?force=true' : ''}`,
  )
}

export async function reanalyzeAll(force = false): Promise<ReanalyzeResult> {
  return await post<ReanalyzeResult>(`/knowledge/re-analyze-all${force ? '?force=true' : ''}`)
}

/** 触发 RAG 全量重建（重建所有 manuals/cases/sops 索引）*/
export async function importAll(): Promise<{
  manuals: ImportResult
  cases_imported: number
  sops_imported: number
}> {
  return await post('/knowledge/import/all')
}
