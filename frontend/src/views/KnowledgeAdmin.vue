<template>
  <PageContainer>
    <SectionTitle title="知识库管理" icon="Files" badge="U6" badge-type="primary" />

    <el-row :gutter="16" class="mb-md">
      <el-col :xs="24" :sm="12" :md="6" v-for="s in statsCards" :key="s.label">
        <StatCard
          :value="s.value"
          :label="s.label"
          :icon="s.icon"
          :color="s.color"
        />
      </el-col>
    </el-row>

    <el-card class="upload-card mb-md" shadow="never">
      <template #header>
        <div class="card-header">
          <el-icon><Upload /></el-icon>
          <span>上传新文档</span>
          <span class="header-hint">支持 .md / .txt / .pdf / .docx</span>
        </div>
      </template>

      <el-upload
        drag
        multiple
        :auto-upload="true"
        :http-request="customUpload"
        :on-success="onUploadSuccess"
        :on-error="onUploadError"
        :show-file-list="false"
      >
        <el-icon class="upload-icon"><UploadFilled /></el-icon>
        <div class="upload-text">
          拖拽文件到此处，或<em>点击上传</em>
        </div>
        <template #tip>
          <div class="el-upload__tip">
            PDF / Word 文档上传后自动解析 + 生成 .md 副本（关键词搜索可用）<br />
            如果 Milvus 可用，还会自动进入向量索引
          </div>
        </template>
      </el-upload>

      <el-progress
        v-if="uploading"
        :percentage="uploadProgress"
        :status="uploadStatus"
        class="mt-sm"
      />
    </el-card>

    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <el-icon><Document /></el-icon>
          <span>已上传文件（{{ manuals.length }}）</span>
          <div class="header-actions">
            <el-button
              text
              :loading="rebuilding"
              @click="onRebuild"
            >
              <el-icon><Refresh /></el-icon>
              重建索引
            </el-button>
            <el-button text @click="loadManuals">
              <el-icon><Refresh /></el-icon>
              刷新
            </el-button>
          </div>
        </div>
      </template>

      <el-table
        :data="manuals"
        stripe
        v-loading="loading"
        style="width: 100%"
      >
        <el-table-column label="文件名" min-width="260" show-overflow-tooltip>
          <template #default="{ row }">
            <div class="file-name-cell">
              <el-icon :color="getFileColor(row.name)">
                <component :is="getFileIcon(row.name)" />
              </el-icon>
              <span>{{ row.name }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="大小" prop="size_kb" width="120" align="right">
          <template #default="{ row }">
            {{ row.size_kb }} KB
          </template>
        </el-table-column>
        <el-table-column label="上传时间" width="200" align="center">
          <template #default="{ row }">
            {{ formatTime(row.mtime) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" align="center">
          <template #default="{ row }">
            <el-button
              size="small"
              type="primary"
              text
              @click="onView(row)"
            >
              <el-icon><View /></el-icon>
              查看
            </el-button>
            <el-button
              size="small"
              type="danger"
              text
              @click="onDelete(row)"
            >
              <el-icon><Delete /></el-icon>
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <EmptyState
        v-if="!loading && manuals.length === 0"
        title="还没有上传任何文档"
        description="拖拽 PDF / Word / Markdown 文件到上方上传区"
        type="document"
        style="padding: 40px 0"
      />
    </el-card>

    <!-- FEAT + PDF-A.7: 查看手册 Tab 弹窗（全文 / 目录 / 表格清单 / 元数据） -->
    <el-dialog
      v-model="viewDialogVisible"
      :title="`查看手册：${viewingFile?.filename || '加载中...'}`"
      width="80%"
      top="5vh"
      :close-on-click-modal="false"
      @close="closeViewDialog"
    >
      <div v-loading="viewingLoading" class="view-content-wrapper" style="min-height: 400px;">
        <template v-if="viewingFile">
          <div class="view-meta">
            <el-tag size="small">{{ viewingFile.ext.toUpperCase().replace('.', '') }}</el-tag>
            <el-tag size="small" type="info">大小 {{ viewingFile.size_kb }} KB</el-tag>
            <el-tag v-if="viewingFile.truncated" size="small" type="warning">
              ⚠ 内容超过 200KB，已截断显示
            </el-tag>
          </div>

          <el-tabs v-if="viewingStructure || viewingStructureLoading" v-model="activeTab" class="view-tabs">
            <!-- Tab 1: 全文 -->
            <el-tab-pane label="全文" name="content">
              <pre v-if="!['.md', '.markdown'].includes(viewingFile.ext)" class="view-content view-content--plain">{{ viewingFile.content }}</pre>
              <div v-else class="markdown-body view-content" v-html="renderMd(viewingFile.content)"></div>
            </el-tab-pane>
            <!-- Tab 2: 目录（聚群 A） -->
            <el-tab-pane label="目录" name="outline" :disabled="!viewingStructure?.outline?.length">
              <template v-if="viewingStructure">
                <div v-if="viewingStructure.outline.length === 0" class="outline-empty">
                  <el-icon><Document /></el-icon>
                  <span>未识别到章节结构</span>
                </div>
                <div v-else class="outline-list">
                  <div
                    v-for="(item, i) in viewingStructure.outline"
                    :key="i"
                    class="outline-item"
                    :style="{ paddingLeft: 12 + (item.level - 1) * 24 + 'px' }"
                  >
                    <el-icon :size="14" class="outline-icon">
                      <CaretRight />
                    </el-icon>
                    <span class="outline-title">{{ item.title }}</span>
                    <el-tag size="small" type="info" effect="plain">第 {{ item.page_start }} 页</el-tag>
                  </div>
                </div>
              </template>
            </el-tab-pane>
            <!-- Tab 3: 表格清单（聚群 A） -->
            <el-tab-pane label="表格清单" name="tables" :disabled="!viewingStructure?.tables?.length">
              <template v-if="viewingStructure">
                <div v-if="viewingStructure.tables.length === 0" class="outline-empty">
                  <el-icon><Grid /></el-icon>
                  <span>未识别到表格</span>
                </div>
                <div v-else class="table-list">
                  <div
                    v-for="(t, i) in viewingStructure.tables"
                    :key="i"
                    class="table-card"
                  >
                    <div class="table-card-head">
                      <el-tag size="small" type="warning">📊 表格 #{{ i + 1 }}</el-tag>
                      <el-tag size="small" type="info" effect="plain">第 {{ t.page }} 页</el-tag>
                      <el-tag size="small" effect="plain">{{ t.rows }} × {{ t.cols }}</el-tag>
                    </div>
                    <div class="table-preview">{{ t.preview }}</div>
                  </div>
                </div>
              </template>
            </el-tab-pane>
            <!-- Tab 4: 元数据（聚群 A） -->
            <el-tab-pane label="元数据" name="meta" :disabled="!viewingStructure">
              <template v-if="viewingStructure">
                <el-descriptions :column="2" border>
                  <el-descriptions-item label="页数">{{ viewingStructure.page_count }}</el-descriptions-item>
                  <el-descriptions-item label="章节数">{{ viewingStructure.outline.length }}</el-descriptions-item>
                  <el-descriptions-item label="表格数">{{ viewingStructure.tables.length }}</el-descriptions-item>
                  <el-descriptions-item label="缓存状态">
                    {{ viewingStructure.cached ? '✅ 已缓存' : '🔄 即时构建' }}
                  </el-descriptions-item>
                </el-descriptions>
                <p v-if="viewingStructure.note" class="view-note">{{ viewingStructure.note }}</p>
              </template>
            </el-tab-pane>
          </el-tabs>
          <template v-else>
            <!-- 旧版兜底：无结构数据时显示纯文本 -->
            <pre v-if="!['.md', '.markdown'].includes(viewingFile.ext)" class="view-content view-content--plain">{{ viewingFile.content }}</pre>
            <div v-else class="markdown-body view-content" v-html="renderMd(viewingFile.content)"></div>
          </template>
        </template>
      </div>
      <template #footer>
        <el-button @click="closeViewDialog">关闭</el-button>
        <el-button
          v-if="viewingStructure"
          type="primary"
          @click="onReindexViewing"
          :loading="reindexing"
        >
          <el-icon><Refresh /></el-icon>
          重建索引
        </el-button>
      </template>
    </el-dialog>
  </PageContainer>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Upload, UploadFilled, Document, Refresh, Delete, Files, View, Grid, CaretRight,
} from '@element-plus/icons-vue'
import PageContainer from '@/components/base/PageContainer.vue'
import SectionTitle from '@/components/base/SectionTitle.vue'
import StatCard from '@/components/base/StatCard.vue'
import EmptyState from '@/components/base/EmptyState.vue'
import { renderSafeMarkdownCached } from '@/utils/markdown'
import {
  uploadManual, listManuals, importManuals, deleteManual, getManualContent,
  getManualStructure, reindexManual,
  type ManualFile, type UploadResult, type ManualContent, type ManualStructure,
} from '@/api/knowledgeAdmin'

const manuals = ref<ManualFile[]>([])
const loading = ref(false)
const uploading = ref(false)
const uploadProgress = ref(0)
const uploadStatus = ref<'success' | 'exception' | ''>('')
const rebuilding = ref(false)

// FEAT + PDF-A.7: 查看手册内容（弹窗 + Tab）
const viewDialogVisible = ref(false)
const viewingFile = ref<ManualContent | null>(null)
const viewingLoading = ref(false)
const viewingStructure = ref<ManualStructure | null>(null)
const viewingStructureLoading = ref(false)
const activeTab = ref<'content' | 'outline' | 'tables' | 'meta'>('content')
const reindexing = ref(false)

const statsCards = computed(() => [
  { label: '总文件数', value: manuals.value.length, icon: 'Document', color: 'primary' as const },
  { label: '总大小', value: manuals.value.reduce((s, m) => s + m.size_kb, 0).toFixed(1) + ' KB', icon: 'Files', color: 'info' as const },
  { label: '最近上传', value: manuals.value[0]?.name.split('_')[0] || '-', icon: 'Upload', color: 'success' as const },
  { label: '可搜索（.md）', value: manuals.value.filter(m => /\.(md|txt|markdown)$/i.test(m.name)).length, icon: 'Files', color: 'warning' as const },
])

async function loadManuals() {
  loading.value = true
  try {
    const res = await listManuals()
    manuals.value = res.manuals
  } catch (e) {
    ElMessage.error('加载列表失败: ' + (e as Error).message)
  } finally {
    loading.value = false
  }
}

async function customUpload(option: any) {
  uploading.value = true
  uploadProgress.value = 0
  uploadStatus.value = ''
  try {
    const file: File = option.file
    const res: UploadResult = await uploadManual(file, (p) => {
      uploadProgress.value = p
    })
    ElMessage.success(res.message)
    await loadManuals()
  } catch (e) {
    uploadStatus.value = 'exception'
    ElMessage.error('上传失败: ' + (e as Error).message)
  } finally {
    uploading.value = false
    uploadProgress.value = 0
  }
}

function onUploadSuccess() { /* el-upload v-model 关闭后 */ }
function onUploadError() { /* 同上 */ }

async function onRebuild() {
  try {
    await ElMessageBox.confirm('重建索引会扫描所有 manuals 并重新解析，过程较慢（约 10-30 秒），确定继续？', '重建索引', {
      type: 'warning',
      confirmButtonText: '开始重建',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  rebuilding.value = true
  try {
    const res = await importManuals()
    const total = Object.values(res.results).reduce((a, b) => a + b, 0)
    ElMessage.success(`重建完成，共处理 ${total} 个段落`)
    await loadManuals()
  } catch (e) {
    ElMessage.error('重建失败: ' + (e as Error).message)
  } finally {
    rebuilding.value = false
  }
}

async function onView(row: ManualFile) {
  viewDialogVisible.value = true
  viewingLoading.value = true
  viewingFile.value = null
  viewingStructure.value = null
  activeTab.value = 'content'
  try {
    viewingFile.value = await getManualContent(row.name)
  } catch (e) {
    ElMessage.error('查看失败: ' + (e as Error).message)
    viewDialogVisible.value = false
  } finally {
    viewingLoading.value = false
  }
  // PDF-A.7: 异步加载结构（不阻塞弹窗显示）
  viewingStructureLoading.value = true
  try {
    viewingStructure.value = await getManualStructure(row.name)
    if (viewingStructure.value.outline.length === 0) activeTab.value = 'content'
  } catch {
    // 失败不显示结构 Tab
    viewingStructure.value = null
  } finally {
    viewingStructureLoading.value = false
  }
}

async function onReindexViewing() {
  if (!viewingFile.value) return
  try {
    await ElMessageBox.confirm(
      `重新索引 "${viewingFile.value.filename}"？会删除旧 chunks 并重走解析流水线。`,
      '重建索引',
      { type: 'warning', confirmButtonText: '开始', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  reindexing.value = true
  try {
    const res = await reindexManual(viewingFile.value.filename)
    ElMessage.success(`重建完成：${res.reindexed ?? 0} 个 chunks`)
  } catch (e) {
    ElMessage.error('重建失败: ' + (e as Error).message)
  } finally {
    reindexing.value = false
  }
}

function closeViewDialog() {
  viewDialogVisible.value = false
  viewingFile.value = null
  viewingStructure.value = null
}

async function onDelete(row: ManualFile) {
  try {
    await ElMessageBox.confirm(`确认删除 "${row.name}"？删除后 RAG 检索将无法找到该文件内容。`, '删除确认', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  try {
    await deleteManual(row.name)
    ElMessage.success('已删除')
    await loadManuals()
  } catch (e) {
    ElMessage.error('删除失败: ' + (e as Error).message)
  }
}

function getFileIcon(name: string): string {
  const ext = name.split('.').pop()?.toLowerCase() || ''
  if (ext === 'pdf') return 'Document'
  if (['docx', 'doc'].includes(ext)) return 'Files'
  if (['md', 'markdown'].includes(ext)) return 'Document'
  return 'Files'
}

function getFileColor(name: string): string {
  const ext = name.split('.').pop()?.toLowerCase() || ''
  if (ext === 'pdf') return 'var(--danger)'
  if (['docx', 'doc'].includes(ext)) return 'var(--primary)'
  return 'var(--success)'
}

function formatTime(ts: number): string {
  const d = new Date(ts * 1000)
  return d.toLocaleString('zh-CN')
}

function renderMd(content: string): string {
  return renderSafeMarkdownCached(content)
}

onMounted(() => {
  loadManuals()
})
</script>

<style lang="scss" scoped>
.card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: var(--font-weight-semibold);

  .header-hint {
    margin-left: 8px;
    font-weight: normal;
    color: var(--text-muted);
    font-size: var(--font-size-sm);
  }

  .header-actions {
    margin-left: auto;
    display: flex;
    gap: 4px;
  }
}

.upload-card {
  :deep(.el-upload) {
    width: 100%;
  }
  :deep(.el-upload-dragger) {
    padding: 32px;
    background: var(--bg-primary);
    border: 2px dashed var(--border-color);
  }
}

.upload-icon {
  font-size: 48px;
  color: var(--primary-color);
  margin-bottom: 12px;
}

.upload-text {
  color: var(--text-secondary);
  font-size: var(--font-size-md);

  em {
    color: var(--primary-color);
    font-style: normal;
    font-weight: var(--font-weight-semibold);
  }
}

.file-name-cell {
  display: flex;
  align-items: center;
  gap: 8px;
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: var(--font-size-sm);
}

// FEAT: 查看手册 Dialog
.view-meta {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}

// PDF-A.7: Tab 视图
.view-tabs {
  :deep(.el-tabs__header) {
    margin-bottom: 12px;
  }
}

// 目录列表
.outline-list {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: 8px 0;
  max-height: 60vh;
  overflow-y: auto;
}

.outline-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-bottom: 1px solid var(--border-light);
  transition: background var(--transition-fast);

  &:last-child { border-bottom: none; }
  &:hover { background: var(--bg-tertiary); }
}

.outline-icon {
  color: var(--primary-color);
  flex-shrink: 0;
}

.outline-title {
  color: var(--text-primary);
  font-size: var(--font-size-md);
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.outline-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 40px;
  color: var(--text-muted);
}

// 表格清单
.table-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 12px;
  max-height: 60vh;
  overflow-y: auto;
}

.table-card {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: 12px;
  transition: all var(--transition-fast);

  &:hover {
    border-color: var(--primary-color);
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.06);
  }
}

.table-card-head {
  display: flex;
  gap: 6px;
  margin-bottom: 8px;
}

.table-preview {
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: var(--font-size-xs);
  color: var(--text-secondary);
  padding: 8px;
  background: var(--bg-tertiary);
  border-radius: var(--radius-sm);
  word-break: break-word;
  line-height: 1.5;
}

.view-note {
  margin-top: 12px;
  padding: 8px 12px;
  background: var(--bg-tertiary);
  color: var(--text-muted);
  font-size: var(--font-size-sm);
  border-radius: var(--radius-sm);
}

.view-content {
  max-height: 65vh;
  overflow-y: auto;
  padding: 20px 24px;
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  line-height: 1.7;
  font-size: var(--font-size-md);
  color: var(--text-primary);
}

.view-content--plain {
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: var(--font-size-sm);
  white-space: pre-wrap;
  word-break: break-word;
  margin: 0;
}

.view-content.markdown-body {
  :deep(h1), :deep(h2), :deep(h3) {
    color: var(--text-primary);
    margin: 16px 0 8px;
    font-weight: var(--font-weight-semibold);
  }
  :deep(h1) { font-size: 22px; border-bottom: 2px solid var(--primary-color); padding-bottom: 6px; }
  :deep(h2) { font-size: 18px; }
  :deep(h3) { font-size: 16px; }
  :deep(p) { margin: 8px 0; }
  :deep(ul), :deep(ol) { margin: 8px 0; padding-left: 24px; }
  :deep(li) { margin: 4px 0; }
  :deep(code) {
    background: var(--bg-tertiary);
    padding: 2px 6px;
    border-radius: var(--radius-sm);
    font-family: 'Consolas', 'Monaco', monospace;
    font-size: 0.9em;
  }
  :deep(pre) {
    background: var(--bg-primary);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-md);
    padding: 12px;
    overflow-x: auto;
    margin: 8px 0;
    code { background: transparent; padding: 0; }
  }
  :deep(strong) { color: var(--primary-color); font-weight: var(--font-weight-semibold); }
  :deep(table) {
    border-collapse: collapse;
    width: 100%;
    margin: 12px 0;
    th, td { border: 1px solid var(--border-color); padding: 6px 12px; text-align: left; }
    th { background: var(--bg-tertiary); font-weight: var(--font-weight-semibold); }
  }
}
</style>
