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
  message: string
}

export interface ImportResult {
  results: Record<string, number>
  total_files: number
}

/** 上传知识文档（U4：自动解析 + Milvus 索引 + .md 副本）*/
export async function uploadManual(file: File, onProgress?: (p: number) => void): Promise<UploadResult> {
  const form = new FormData()
  form.append('file', file)
  return await post<UploadResult>('/knowledge/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
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
  return await http.delete<{ deleted: string }>(`/knowledge/manuals/${encodeURIComponent(filename)}`)
}

/** 触发 RAG 全量重建（重建所有 manuals/cases/sops 索引）*/
export async function importAll(): Promise<{
  manuals: ImportResult
  cases_imported: number
  sops_imported: number
}> {
  return await post('/knowledge/import/all')
}
