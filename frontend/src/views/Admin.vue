<template>
  <PageContainer>
    <SectionTitle title="⚙️ 后台管理" icon="Setting" />

    <el-tabs v-model="activeTab" class="fade-in">
      <!-- 系统概览 -->
      <el-tab-pane name="overview" label="系统概览">
        <OverviewPanel />
      </el-tab-pane>

      <!-- LLM 管理 -->
      <el-tab-pane name="llm" label="LLM 管理">
        <el-row :gutter="20">
          <el-col :xs="24" :md="14">
            <el-card>
              <template #header>
                <span><el-icon><Cpu /></el-icon> 模型状态</span>
              </template>

              <el-descriptions :column="1" border>
                <el-descriptions-item label="当前模式">
                  <el-tag :type="llmStore.status?.mode === 'cloud' ? 'success' : 'warning'" effect="dark" size="large">
                    {{ llmStore.status?.mode === 'cloud' ? '☁️ 云端 API' : '💻 本地模型' }}
                  </el-tag>
                </el-descriptions-item>
                <el-descriptions-item label="使用模型">
                  <code style="color: var(--primary-color); font-size: 14px">
                    {{ llmStore.status?.model || '-' }}
                  </code>
                </el-descriptions-item>
                <el-descriptions-item label="服务状态">
                  <el-tag :type="llmStore.status?.available ? 'success' : 'danger'" effect="dark">
                    {{ llmStore.status?.available ? '✅ 健康' : '❌ 异常' }}
                  </el-tag>
                </el-descriptions-item>
                <el-descriptions-item label="状态消息">
                  {{ llmStore.status?.message || '-' }}
                </el-descriptions-item>
              </el-descriptions>

              <div class="mt-lg">
                <h4 style="color: var(--text-primary)">🔄 切换模型模式</h4>
                <p style="color: var(--text-muted); font-size: 13px; line-height: 1.6">
                  系统支持双模式无缝切换：<br>
                  • <strong>云端 API</strong>：调用阿里云百炼平台，效果强、速度快<br>
                  • <strong>本地模型</strong>：Qwen2-VL-7B 离线运行，无外网时使用
                </p>
                <el-space>
                  <el-button
                    type="primary"
                    :loading="llmStore.switching"
                    :disabled="llmStore.status?.mode === 'cloud'"
                    @click="onSwitch('cloud')"
                  >
                    <el-icon><Connection /></el-icon>
                    切换到云端
                  </el-button>
                  <el-button
                    type="warning"
                    :loading="llmStore.switching"
                    :disabled="llmStore.status?.mode === 'local'"
                    @click="onSwitch('local')"
                  >
                    <el-icon><Cpu /></el-icon>
                    切换到本地
                  </el-button>
                  <el-button @click="llmStore.refresh()" :loading="llmStore.loading">
                    <el-icon><Refresh /></el-icon>
                    刷新状态
                  </el-button>
                </el-space>
              </div>
            </el-card>
          </el-col>

          <el-col :xs="24" :md="10">
            <el-card>
              <template #header>
                <span><el-icon><ChatLineSquare /></el-icon> 模型测试</span>
              </template>
              <el-input v-model="testMsg" type="textarea" :rows="3" placeholder="输入测试消息..." />
              <el-button
                type="primary"
                class="mt-sm test-send-btn"
                :loading="testLoading"
                @click="onTest"
              >
                发送测试
              </el-button>
              <div v-if="testResult" class="test-result mt-sm">
                <div class="test-meta">
                  {{ testResult.model }} · {{ testResult.latency_ms }}ms
                </div>
                <div class="test-content">
                  {{ testResult.content }}
                </div>
              </div>
            </el-card>
          </el-col>
        </el-row>
      </el-tab-pane>

      <!-- 案例审核 -->
      <el-tab-pane name="review" label="案例审核">
        <el-card>
          <div class="filter-bar">
            <el-radio-group v-model="reviewStatus" @change="loadReviewCases">
              <el-radio-button value="pending">待审核 ({{ counts.pending }})</el-radio-button>
              <el-radio-button value="approved">已通过</el-radio-button>
              <el-radio-button value="rejected">已驳回</el-radio-button>
            </el-radio-group>
            <TableExportBar
              style="margin-left: auto"
              :columns="reviewColumns"
              :data="reviewCases"
              filename="案例审核"
              :pdf-element="reviewTableRef"
              pdf-title="案例审核 - A1 设备检修系统"
            />
            <el-button @click="loadReviewCases">
              <el-icon><Refresh /></el-icon>
              刷新
            </el-button>
          </div>

          <div ref="reviewTableRef">
          <div v-if="reviewLoading && reviewCases.length === 0" class="table-skeleton">
            <Skeleton v-for="i in 5" :key="i" type="card" />
          </div>
          <el-table v-else :data="reviewCases" stripe v-loading="reviewLoading" class="mt-md">
            <el-table-column prop="case_id" label="ID" width="180" />
            <el-table-column prop="title" label="标题" show-overflow-tooltip />
            <el-table-column prop="equipment_type" label="设备" width="120" />
            <el-table-column prop="submitter" label="提交人" width="100" />
            <el-table-column prop="submitted_at" label="时间" width="180" />
            <el-table-column label="操作" width="200" fixed="right">
              <template #default="{ row }">
                <el-button size="small" @click="viewCase(row)">查看</el-button>
                <el-button
                  v-if="row.status === 'pending'"
                  size="small"
                  type="success"
                  @click="onReview(row, true)"
                >
                  通过
                </el-button>
                <el-button
                  v-if="row.status === 'pending'"
                  size="small"
                  type="danger"
                  @click="onReview(row, false)"
                >
                  驳回
                </el-button>
              </template>
            </el-table-column>
          </el-table>
          </div>
        </el-card>
      </el-tab-pane>

      <!-- 知识库导入 -->
      <el-tab-pane name="import" label="知识库导入">
        <el-card>
          <template #header>
            <span><el-icon><FolderOpened /></el-icon> 内置数据</span>
          </template>
          <el-alert type="info" :closable="false" show-icon style="margin-bottom: 16px">
            <template #title>演示用知识库</template>
            系统内置了 4 份检修手册、10 个故障案例、4 个 SOP。点击下方按钮一键导入。
          </el-alert>

          <el-row :gutter="16">
            <el-col :xs="24" :sm="12" v-for="action in importActions" :key="action.key">
              <ImportCard
                :title="action.title"
                :description="action.desc"
                :icon="action.icon"
                :color="action.color"
                :loading="importing === action.key"
                @click="onImport(action.key)"
              />
            </el-col>
          </el-row>
        </el-card>

        <el-card class="mt-md">
          <template #header>
            <span><el-icon><DataAnalysis /></el-icon> 知识库统计</span>
          </template>
          <el-row :gutter="16">
            <el-col :xs="12" :sm="6" v-for="s in statsList" :key="s.label">
              <StatCard
                :value="s.value"
                :label="s.label"
                :icon="s.icon"
                :color="s.color"
                :animate="false"
              />
            </el-col>
          </el-row>
          <el-button @click="loadStats" class="mt-md" type="primary" plain>
            <el-icon><Refresh /></el-icon>
            刷新统计
          </el-button>
        </el-card>
      </el-tab-pane>
    </el-tabs>

    <!-- 案例详情（复用 CaseDetailDialog） -->
    <CaseDetailDialog
      v-model="showDetail"
      :case-data="currentCase"
      :show-review="currentCase?.status === 'pending'"
      :submitting="false"
      @reviewed="onReviewed"
    />
  </PageContainer>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Connection,
  DataAnalysis,
  Document,
  FolderOpened,
  Notebook,
  Tickets,
} from '@element-plus/icons-vue'
import Skeleton from '@/components/base/Skeleton.vue'
import { useLLMStore } from '@/stores/llm'
import {
  listCases,
  reviewCase,
  importAll,
  importManuals,
  importCases as importCasesApi,
  importSops,
  knowledgeStats,
  type CaseRecord,
} from '@/api/knowledge'
import { testChat } from '@/api/llm'
import PageContainer from '@/components/base/PageContainer.vue'
import SectionTitle from '@/components/base/SectionTitle.vue'
import StatCard from '@/components/base/StatCard.vue'
import ImportCard from '@/components/business/ImportCard.vue'
import CaseDetailDialog from '@/components/business/CaseDetailDialog.vue'
import OverviewPanel from '@/components/business/OverviewPanel.vue'
import TableExportBar from '@/components/business/TableExportBar.vue'
import type { Column } from '@/utils/exporters'

const activeTab = ref('overview')
const llmStore = useLLMStore()

// 测试
const testMsg = ref('你是谁？请用一句话介绍。')
const testLoading = ref(false)
const testResult = ref<any>(null)

async function onTest() {
  testLoading.value = true
  try {
    testResult.value = await testChat(testMsg.value)
  } finally {
    testLoading.value = false
  }
}

async function onSwitch(mode: 'cloud' | 'local') {
  try {
    await ElMessageBox.confirm(
      `确认切换到【${mode === 'cloud' ? '云端 API' : '本地模型'}】模式？`,
      '切换确认',
      { type: 'warning' },
    )
    await llmStore.switchMode(mode)
    ElMessage.success('切换成功')
  } catch (e) {
    // 取消
  }
}

// 审核
const reviewStatus = ref('pending')
const reviewCases = ref<CaseRecord[]>([])
const reviewLoading = ref(false)
const reviewTableRef = ref<HTMLElement | null>(null)
const counts = ref({ pending: 0, approved: 0, rejected: 0 })

const reviewColumns: Column[] = [
  { key: 'case_id', label: '案例 ID', width: 20 },
  { key: 'title', label: '标题', width: 30 },
  { key: 'equipment_type', label: '设备类型', width: 14 },
  { key: 'equipment_model', label: '设备型号', width: 16 },
  { key: 'submitter', label: '提交人', width: 10 },
  { key: 'status', label: '状态', format: (k, row) => ({ pending: '待审核', approved: '已通过', rejected: '已驳回' }[row.status] || row.status), width: 10 },
  { key: 'submitted_at', label: '提交时间', width: 20 },
]

async function loadReviewCases() {
  reviewLoading.value = true
  try {
    const r = await listCases(reviewStatus.value)
    reviewCases.value = r.cases
  } finally {
    reviewLoading.value = false
  }
}

async function loadCounts() {
  try {
    const s = await knowledgeStats()
    counts.value = {
      pending: s.pending_cases,
      approved: s.approved_cases,
      rejected: s.total_cases - s.pending_cases - s.approved_cases,
    }
  } catch (e) {
    // ignore
  }
}

const showDetail = ref(false)
const currentCase = ref<CaseRecord | null>(null)

function viewCase(row: CaseRecord) {
  currentCase.value = row
  showDetail.value = true
}

async function onReview(row: CaseRecord, approved: boolean) {
  try {
    if (!approved) {
      const { value } = await ElMessageBox.prompt('请输入驳回原因', '驳回审核', {
        confirmButtonText: '确认驳回',
        cancelButtonText: '取消',
        inputType: 'textarea',
        inputValidator: (v) => (v && v.trim() ? true : '请填写驳回原因'),
      })
      await reviewCase({ case_id: row.case_id, approved: false, review_comment: value })
    } else {
      await reviewCase({ case_id: row.case_id, approved: true })
    }
    ElMessage.success('审核完成')
    await loadReviewCases()
    await loadCounts()
  } catch (e) {
    // 取消
  }
}

async function onReviewed() {
  await loadReviewCases()
  await loadCounts()
}

// 导入
const importing = ref<string>('')
const importActions = [
  { key: 'all', title: '一键导入全部', desc: '手册 + 案例 + SOP', icon: 'FolderOpened', color: '#00d4ff' },
  { key: 'manuals', title: '导入手册', desc: '4 份检修手册', icon: 'Notebook', color: '#00d97e' },
  { key: 'cases', title: '导入案例', desc: '10 个故障案例', icon: 'Document', color: '#ffb84d' },
  { key: 'sops', title: '导入 SOP', desc: '4 个标准作业流程', icon: 'Tickets', color: '#ff4757' },
]

async function onImport(key: string) {
  importing.value = key
  try {
    if (key === 'all') await importAll()
    else if (key === 'manuals') await importManuals()
    else if (key === 'cases') await importCasesApi()
    else if (key === 'sops') await importSops()

    ElMessage.success('导入成功')
    await loadStats()
    await loadCounts()
  } finally {
    importing.value = ''
  }
}

// 统计
const stats = ref<any>(null)
const statsList = computed(() => [
  { label: '索引条目', value: stats.value?.total_chunks ?? '-', icon: 'DataAnalysis', color: 'primary' },
  { label: '案例总数', value: stats.value?.total_cases ?? '-', icon: 'Document', color: 'success' },
  { label: '待审核', value: stats.value?.pending_cases ?? '-', icon: 'Tickets', color: 'warning' },
  { label: '已通过', value: stats.value?.approved_cases ?? '-', icon: 'FolderOpened', color: 'info' },
])

async function loadStats() {
  try {
    stats.value = await knowledgeStats()
  } catch (e) {
    // ignore
  }
}

onMounted(() => {
  llmStore.refresh()
  loadReviewCases()
  loadCounts()
  loadStats()
})
</script>

<style lang="scss" scoped>
.filter-bar {
  display: flex;
  align-items: center;
  gap: 12px;
}

.test-send-btn {
  width: 100%;
}

.test-meta {
  color: var(--primary-color);
  font-size: var(--font-size-sm);
}

.test-content {
  margin-top: var(--spacing-sm);
  line-height: 1.6;
  color: var(--text-primary);
}

.table-skeleton {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
  padding: var(--spacing-md) 0;
}
</style>
