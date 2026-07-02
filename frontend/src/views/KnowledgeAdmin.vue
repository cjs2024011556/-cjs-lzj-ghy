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
      >
        <el-table-column label="文件名" min-width="240">
          <template #default="{ row }">
            <div class="file-name-cell">
              <el-icon :color="getFileColor(row.name)">
                <component :is="getFileIcon(row.name)" />
              </el-icon>
              <span>{{ row.name }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="大小" prop="size_kb" width="100">
          <template #default="{ row }">
            {{ row.size_kb }} KB
          </template>
        </el-table-column>
        <el-table-column label="上传时间" width="200">
          <template #default="{ row }">
            {{ formatTime(row.mtime) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
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
  </PageContainer>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Upload, UploadFilled, Document, Refresh, Delete, Files,
} from '@element-plus/icons-vue'
import PageContainer from '@/components/base/PageContainer.vue'
import SectionTitle from '@/components/base/SectionTitle.vue'
import StatCard from '@/components/base/StatCard.vue'
import EmptyState from '@/components/base/EmptyState.vue'
import {
  uploadManual, listManuals, importManuals, deleteManual,
  type ManualFile, type UploadResult,
} from '@/api/knowledgeAdmin'

const manuals = ref<ManualFile[]>([])
const loading = ref(false)
const uploading = ref(false)
const uploadProgress = ref(0)
const uploadStatus = ref<'success' | 'exception' | ''>('')
const rebuilding = ref(false)

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
</style>
