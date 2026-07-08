/**
 * 数据导出工具 - 4 种格式
 * - CSV: 简单文本表格，Excel 兼容
 * - Excel: 多 sheet，OOXML 格式
 * - PDF: html2canvas + jsPDF 截图表格（保证中文不方块）
 * - JSON: 原始数据
 */

import * as XLSX from 'xlsx'
import { jsPDF } from 'jspdf'
import html2canvas from 'html2canvas'
import { ElMessage } from 'element-plus'

export interface Column {
  key: string
  label: string
  format?: (v: any, row: any) => string
  width?: number  // PDF 列宽（可选）
}

// ============================================================
// CSV
// ============================================================
function escapeCsvCell(v: any): string {
  if (v === null || v === undefined) return ''
  const s = String(v)
  // 含逗号/引号/换行的需要双引号包裹，内部双引号转义
  if (/[",\n\r]/.test(s)) {
    return '"' + s.replace(/"/g, '""') + '"'
  }
  return s
}

export function exportCSV(columns: Column[], rows: any[], filename: string) {
  const lines: string[] = []
  // 表头
  lines.push(columns.map(c => escapeCsvCell(c.label)).join(','))
  // 数据
  for (const row of rows) {
    lines.push(columns.map(c => escapeCsvCell(c.format ? c.format(c.key, row) : row[c.key])).join(','))
  }
  const csv = '﻿' + lines.join('\n')  // BOM 让 Excel 识别 UTF-8
  downloadBlob(new Blob([csv], { type: 'text/csv;charset=utf-8' }), `${filename}.csv`)
}

// ============================================================
// Excel
// ============================================================
export function exportExcel(
  columns: Column[],
  rows: any[],
  filename: string,
  sheetName = 'Sheet1',
) {
  const data = rows.map((row) => {
    const obj: Record<string, any> = {}
    for (const col of columns) {
      obj[col.label] = col.format ? col.format(col.key, row) : row[col.key]
    }
    return obj
  })
  const ws = XLSX.utils.json_to_sheet(data)
  // 自动列宽
  ws['!cols'] = columns.map(c => ({ wch: c.width || 18 }))
  const wb = XLSX.utils.book_new()
  XLSX.utils.book_append_sheet(wb, ws, sheetName)
  XLSX.writeFile(wb, `${filename}.xlsx`)
}

// ============================================================
// PDF（html2canvas 方案：DOM 转图嵌入）
// ============================================================
/** 内部 helper：把 canvas 渲染成 A4 横版多页 PDF */
function _canvasToPdf(canvas: HTMLCanvasElement, filename: string) {
  const imgData = canvas.toDataURL('image/png')
  const pdf = new jsPDF({ orientation: 'landscape', unit: 'mm', format: 'a4' })
  const pageWidth = pdf.internal.pageSize.getWidth()
  const pageHeight = pdf.internal.pageSize.getHeight()

  if (canvas.height * (pageWidth - 20) / canvas.width < pageHeight - 20) {
    // 单页
    pdf.addImage(imgData, 'PNG', 10, 10, pageWidth - 20, canvas.height * (pageWidth - 20) / canvas.width)
  } else {
    // 多页切片
    let srcY = 0
    let remaining = canvas.height
    let pageNum = 1
    while (remaining > 0) {
      const sliceHeight = Math.min(remaining, canvas.width * (pageHeight - 20) / (pageWidth - 20))
      const sliceCanvas = document.createElement('canvas')
      sliceCanvas.width = canvas.width
      sliceCanvas.height = sliceHeight
      const ctx = sliceCanvas.getContext('2d')!
      ctx.drawImage(canvas, 0, srcY, canvas.width, sliceHeight, 0, 0, canvas.width, sliceHeight)
      const sliceData = sliceCanvas.toDataURL('image/png')
      const sliceImgHeight = sliceHeight * (pageWidth - 20) / canvas.width
      if (pageNum > 1) pdf.addPage()
      pdf.addImage(sliceData, 'PNG', 10, 10, pageWidth - 20, sliceImgHeight)
      srcY += sliceHeight
      remaining -= sliceHeight
      pageNum++
    }
  }

  pdf.save(`${filename}.pdf`)
}

/** 构造 PDF 输出用的临时容器（title + 多个元素 outerHTML + footer） */
function _buildPdfWrapper(elements: HTMLElement[], title?: string): HTMLElement {
  const wrapper = document.createElement('div')
  wrapper.style.cssText = 'background: #ffffff; padding: 24px; font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", sans-serif; color: #0f172a;'
  wrapper.innerHTML = `
    ${title ? `<h1 style="font-size:20px; margin:0 0 16px; padding-bottom:12px; border-bottom:2px solid #2563eb;">${escapeHtml(title)}</h1>` : ''}
    <div class="report-content">${elements.map(e => e.outerHTML).join('<div style="height:12px"></div>')}</div>
    <div style="margin-top:24px; padding-top:12px; border-top:1px solid #e5e7eb; font-size:11px; color:#94a3b8; text-align:right;">
      A1 设备检修系统 · 导出时间 ${new Date().toLocaleString('zh-CN')}
    </div>
  `
  document.body.appendChild(wrapper)
  return wrapper
}

async function htmlToPdf(element: HTMLElement, filename: string, title?: string) {
  // U3: 把 title + table + footer 一起包到截图容器里，
  // 全部内容由 html2canvas 用浏览器原生字体渲染（含中文），
  // 避免 jsPDF 原生文字接口对中文的支持限制。

  const wrapper = _buildPdfWrapper([element], title)
  try {
    // 一次截图（title + 内容 + footer 全在内）
    const canvas = await html2canvas(wrapper, {
      scale: 2,
      backgroundColor: '#ffffff',
      useCORS: true,
      logging: false,
    })
    _canvasToPdf(canvas, filename)
  } finally {
    document.body.removeChild(wrapper)
  }
}

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')

}

/**
 * PDF 导出（从 DOM 元素）
 * 适用于表格页：传入 el-table 容器即可
 */
export async function exportPDFFromElement(
  element: HTMLElement,
  filename: string,
  title?: string,
) {
  try {
    ElMessage.info('正在生成 PDF...')
    await htmlToPdf(element, filename, title)
    ElMessage.success('PDF 导出成功')
  } catch (e: any) {
    console.error('PDF 导出失败:', e)
    ElMessage.error(`PDF 导出失败: ${e?.message || '未知错误'}`)
  }
}

/**
 * UPGRADE-1: PDF 导出（合并多个 DOM 元素）
 * 适用于"结构化报告"页（答案卡 + 引用卡 合并到一份 PDF）
 */
export async function exportPDFFromElements(
  elements: HTMLElement[],
  filename: string,
  title?: string,
) {
  try {
    ElMessage.info('正在生成 PDF...')
    const wrapper = _buildPdfWrapper(elements, title)
    try {
      const canvas = await html2canvas(wrapper, {
        scale: 2,
        backgroundColor: '#ffffff',
        useCORS: true,
        logging: false,
      })
      _canvasToPdf(canvas, filename)
      ElMessage.success('PDF 导出成功')
    } finally {
      document.body.removeChild(wrapper)
    }
  } catch (e: any) {
    console.error('PDF 导出失败:', e)
    ElMessage.error(`PDF 导出失败: ${e?.message || '未知错误'}`)
  }
}

// ============================================================
// JSON
// ============================================================
export function exportJSON(data: any, filename: string) {
  const json = JSON.stringify(data, null, 2)
  downloadBlob(new Blob([json], { type: 'application/json;charset=utf-8' }), `${filename}.json`)
}

// ============================================================
// UPGRADE-1: Markdown（结构化报告页专用）
// ============================================================
export interface MarkdownSection {
  heading: string
  body: string
}

export interface MarkdownDoc {
  title: string
  meta?: Record<string, string>
  sections: MarkdownSection[]
}

export function exportMarkdownBlob(doc: MarkdownDoc, filename: string) {
  const lines: string[] = []
  lines.push(`# ${doc.title}\n`)
  if (doc.meta) {
    for (const [k, v] of Object.entries(doc.meta)) {
      lines.push(`**${k}**: ${v}  `)
    }
    lines.push('\n---\n')
  }
  for (const s of doc.sections) {
    lines.push(`## ${s.heading}\n`)
    lines.push(`${s.body}\n`)
    lines.push('\n---\n')
  }
  const md = lines.join('\n')
  downloadBlob(new Blob([md], { type: 'text/markdown;charset=utf-8' }), `${filename}.md`)
}

// ============================================================
// 工具
// ============================================================
function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

/**
 * 生成带时间戳的文件名
 * 例：myCases_2026-06-26_1530
 */
export function timestampFilename(prefix: string): string {
  const d = new Date()
  const stamp = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}_${String(d.getHours()).padStart(2, '0')}${String(d.getMinutes()).padStart(2, '0')}`
  return `${prefix}_${stamp}`
}
