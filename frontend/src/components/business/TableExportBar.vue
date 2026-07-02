<template>
  <div class="table-export-bar">
    <el-dropdown
      trigger="click"
      @command="(cmd) => onCommand(cmd)"
    >
      <el-button :size="size" :type="type" plain>
        <el-icon><Download /></el-icon>
        {{ label || '导出' }}
        <el-icon style="margin-left: 4px"><ArrowDown /></el-icon>
      </el-button>
      <template #dropdown>
        <el-dropdown-menu>
          <el-dropdown-item command="csv">
            <el-icon><Document /></el-icon> CSV (Excel 兼容)
          </el-dropdown-item>
          <el-dropdown-item command="excel">
            <el-icon><Document /></el-icon> Excel (.xlsx)
          </el-dropdown-item>
          <el-dropdown-item command="pdf" :disabled="pdfDisabled">
            <el-icon><Document /></el-icon> PDF (含中文)
          </el-dropdown-item>
          <el-dropdown-item command="json" divided>
            <el-icon><DataAnalysis /></el-icon> JSON (原始数据)
          </el-dropdown-item>
        </el-dropdown-menu>
      </template>
    </el-dropdown>
  </div>
</template>

<script setup lang="ts">
import { Download, ArrowDown, Document, DataAnalysis } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { exportCSV, exportExcel, exportJSON, exportPDFFromElement, timestampFilename, type Column } from '@/utils/exporters'

const props = withDefaults(defineProps<{
  /** 表格列定义 */
  columns: Column[]
  /** 表格数据 */
  data: any[]
  /** 文件名前缀（最终会加时间戳） */
  filename: string
  /** 按钮文字 */
  label?: string
  /** 按钮大小 */
  size?: 'small' | 'default' | 'large'
  /** 按钮类型 */
  type?: 'primary' | 'success' | 'warning' | 'danger' | 'info' | 'default'
  /** 导出 PDF 用的 DOM 元素（可选）。不传则 PDF 不可用 */
  pdfElement?: HTMLElement | null
  /** PDF 标题 */
  pdfTitle?: string
}>(), {
  label: '导出',
  size: 'small',
  type: 'default',
  pdfElement: null,
  pdfTitle: '',
})

const pdfDisabled = computed(() => !props.pdfElement)

function onCommand(cmd: string) {
  const fname = timestampFilename(props.filename)
  try {
    switch (cmd) {
      case 'csv':
        exportCSV(props.columns, props.data, fname)
        ElMessage.success('CSV 导出成功')
        break
      case 'excel':
        exportExcel(props.columns, props.data, fname)
        ElMessage.success('Excel 导出成功')
        break
      case 'pdf':
        if (!props.pdfElement) {
          ElMessage.warning('当前表格未提供 PDF 导出元素')
          return
        }
        exportPDFFromElement(props.pdfElement, fname, props.pdfTitle)
        break
      case 'json':
        exportJSON(props.data, fname)
        ElMessage.success('JSON 导出成功')
        break
    }
  } catch (e: any) {
    console.error('导出失败:', e)
    ElMessage.error(`导出失败: ${e?.message || '未知错误'}`)
  }
}
</script>

<style lang="scss" scoped>
.table-export-bar {
  display: inline-block;
}
</style>
