<template>
  <PageContainer>
    <SectionTitle title="📋 标准化作业指引" icon="Document" />

    <el-card class="config-card fade-in">
      <el-form :inline="true" label-width="100px">
        <el-form-item label="设备类型">
          <el-select v-model="form.equipment_type" placeholder="请选择" style="width: 180px" size="large">
            <el-option
              v-for="t in EQUIPMENT_TYPES"
              :key="t.value"
              :label="t.label"
              :value="t.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="设备型号">
          <el-input v-model="form.equipment_model" placeholder="可选" style="width: 200px" size="large" />
        </el-form-item>
        <el-form-item label="检修等级">
          <el-select v-model="form.maintenance_level" style="width: 160px" size="large">
            <el-option v-for="lv in levels" :key="lv.code" :label="lv.name" :value="lv.code" />
          </el-select>
        </el-form-item>
        <el-form-item label=" ">
          <el-button type="primary" size="large" :loading="loading" @click="generate">
            <el-icon><MagicStick /></el-icon>
            生成指引
          </el-button>
        </el-form-item>
      </el-form>

      <el-form-item label="故障描述" class="mt-sm">
        <el-input
          v-model="form.fault_description"
          type="textarea"
          :rows="2"
          placeholder="可选：描述具体故障现象，AI 将个性化定制 SOP"
        />
      </el-form-item>
    </el-card>

    <!-- 生成的指引 -->
    <div v-if="guide" class="guide-result fade-in mt-lg">
      <el-card>
        <template #header>
          <div class="guide-header">
            <div>
              <span style="font-size: 18px; font-weight: 600">{{ guide.name }}</span>
              <el-tag style="margin-left: 8px" size="small" effect="plain">
                {{ guide.sop_id }}
              </el-tag>
            </div>
            <div style="display: flex; gap: 12px; align-items: center">
              <el-tag :type="guide.source === 'sop_library' ? 'success' : 'warning'" effect="dark">
                {{ guide.source === 'sop_library' ? '📚 内置 SOP' : '🤖 AI 生成' }}
              </el-tag>
              <el-tag size="small" effect="plain">
                <el-icon><Timer /></el-icon> {{ guide.estimated_minutes }} 分钟
              </el-tag>
              <el-button text @click="exportGuide">
                <el-icon><Download /></el-icon> JSON
              </el-button>
              <el-button text @click="exportGuideExcel">
                <el-icon><Download /></el-icon> Excel
              </el-button>
              <el-button text @click="exportGuidePDF" type="primary">
                <el-icon><Download /></el-icon> PDF
              </el-button>
            </div>
          </div>
        </template>

        <!-- 安全警告 -->
        <el-alert
          v-if="guide.safety_warnings?.length"
          type="warning"
          :closable="false"
          show-icon
          class="safety-alert"
        >
          <template #title>⚠️ 安全警告（必读）</template>
          <ul style="margin: 8px 0 0 0; padding-left: 20px; line-height: 1.8">
            <li v-for="(w, i) in guide.safety_warnings" :key="i">{{ w }}</li>
          </ul>
        </el-alert>

        <!-- 工具清单 -->
        <el-card v-if="guide.tools?.length" shadow="never" class="sub-card mt-md">
          <template #header>
            <span><el-icon><Tools /></el-icon> 所需工具</span>
          </template>
          <el-space wrap>
            <el-tag v-for="t in guide.tools" :key="t" effect="plain" type="info">{{ t }}</el-tag>
          </el-space>
        </el-card>

        <!-- 步骤 -->
        <el-card shadow="never" class="sub-card mt-md">
          <template #header>
            <div style="display: flex; justify-content: space-between; align-items: center">
              <span><el-icon><List /></el-icon> 作业步骤</span>
              <el-button size="small" @click="toggleAll">
                {{ allCompleted ? '取消全选' : '全部完成' }}
              </el-button>
            </div>
          </template>
          <el-steps direction="vertical" :active="activeStep" finish-status="success">
            <el-step
              v-for="step in guide.steps"
              :key="step.step_no"
              :title="step.title"
            >
              <template #description>
                <el-card class="step-card" shadow="never">
                  <div class="step-meta">
                    <el-tag :type="riskColor(step.risk_level)" size="small">
                      风险: {{ riskText(step.risk_level) }}
                    </el-tag>
                    <el-tag size="small" effect="plain">
                      <el-icon><Timer /></el-icon> {{ step.estimated_minutes }}min
                    </el-tag>
                    <el-checkbox v-model="step.completed">
                      已完成
                    </el-checkbox>
                  </div>
                  <div class="step-action">{{ step.action }}</div>
                  <div v-if="step.tools?.length" class="step-section">
                    <strong>工具：</strong>
                    <el-tag v-for="t in step.tools" :key="t" size="small" effect="plain" type="info" style="margin-right: 4px">
                      {{ t }}
                    </el-tag>
                  </div>
                  <div v-if="step.compliance?.length" class="step-section compliance">
                    <strong>✓ 合规校验：</strong>
                    <ul style="margin: 4px 0 0 0; padding-left: 20px">
                      <li v-for="(c, i) in step.compliance" :key="i">{{ c }}</li>
                    </ul>
                  </div>
                </el-card>
              </template>
            </el-step>
          </el-steps>
        </el-card>

        <!-- 个性化建议 -->
        <el-card v-if="guide.personalized_notes" shadow="never" class="sub-card mt-md">
          <template #header>
            <span><el-icon><ChatLineRound /></el-icon> 个性化建议</span>
          </template>
          <div style="line-height: 1.8; color: var(--text-secondary); white-space: pre-wrap">
            {{ guide.personalized_notes }}
          </div>
        </el-card>

        <!-- 进度条 -->
        <div class="progress-section mt-md">
          <el-progress
            :percentage="progress"
            :status="progressStatus"
            :stroke-width="20"
            :text-inside="true"
            :color="progressColors"
          />
          <div class="mt-sm progress-summary">
            完成 {{ completedCount }} / {{ guide.steps.length }} 步
            <span v-if="progress === 100"> · 可执行提交记录</span>
          </div>
        </div>

        <div v-if="progress === 100" style="text-align: right; margin-top: 16px">
          <el-button type="success" @click="finishExecution">
            <el-icon><Check /></el-icon>
            提交并沉淀为案例
          </el-button>
        </div>
      </el-card>
    </div>

    <EmptyState
      v-else
      title="请选择设备类型和检修等级"
      description="在表单中填入设备信息和检修等级后，点击'生成指引'按钮"
      type="document"
    />
  </PageContainer>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { EQUIPMENT_TYPES } from '@/constants/equipment'
import {
  generateGuide,
  listMaintenanceLevels,
  type GuideResponse,
  type Step,
} from '@/api/guide'
import PageContainer from '@/components/base/PageContainer.vue'
import SectionTitle from '@/components/base/SectionTitle.vue'
import EmptyState from '@/components/base/EmptyState.vue'
import { exportJSON, exportExcel, exportPDFFromElement, type Column } from '@/utils/exporters'

const form = ref({
  equipment_type: '液压系统',
  equipment_model: '',
  maintenance_level: 'level_2',
  fault_description: '',
})

const levels = ref<{ code: string; name: string }[]>([])
const loading = ref(false)
const guide = ref<GuideResponse | null>(null)

// 给每个 step 加 completed 字段
const completedCount = computed(() => {
  if (!guide.value) return 0
  return guide.value.steps.filter((s: any) => s.completed).length
})

const progress = computed(() => {
  if (!guide.value?.steps.length) return 0
  return Math.round((completedCount.value / guide.value.steps.length) * 100)
})

const allCompleted = computed(() => progress.value === 100)

// U.3.7 进度条分阶段变色（蓝→橙→绿）
const progressStatus = computed(() => {
  if (progress.value === 100) return 'success'
  if (progress.value >= 80) return 'warning'
  return ''
})
const progressColors = [
  { color: '#00d4ff', percentage: 0 },
  { color: '#ffb84d', percentage: 80 },
  { color: '#00d97e', percentage: 100 },
]
const activeStep = computed(() => completedCount.value)

function riskColor(r: string) {
  return { low: 'success', medium: 'warning', high: 'danger' }[r] || 'info'
}
function riskText(r: string) {
  return { low: '低', medium: '中', high: '高' }[r] || r
}

function toggleAll() {
  if (!guide.value) return
  guide.value.steps.forEach((s: any) => (s.completed = !allCompleted.value))
}

async function generate() {
  if (!form.value.equipment_type || !form.value.maintenance_level) {
    ElMessage.warning('请选择设备类型和检修等级')
    return
  }
  loading.value = true
  try {
    const result = await generateGuide(form.value)
    // 注入 completed 字段
    result.steps = result.steps.map((s: Step) => ({ ...s, completed: false }))
    guide.value = result
    ElMessage.success(`生成完成 (${result.latency_ms}ms)`)
  } catch (e) {
    // ignore
  } finally {
    loading.value = false
  }
}

function exportGuide() {
  if (!guide.value) return
  exportJSON(guide.value, `${guide.value.sop_id}_${Date.now()}`)
}

const guideTableRef = ref<HTMLElement | null>(null)
function exportGuidePDF() {
  if (!guide.value) return
  if (!guideTableRef.value) {
    ElMessage.warning('SOP 内容未渲染，无法导出 PDF')
    return
  }
  exportPDFFromElement(
    guideTableRef.value,
    `${guide.value.sop_id}_${Date.now()}`,
    `${guide.value.name} (${guide.value.sop_id})`,
  )
}

function exportGuideExcel() {
  if (!guide.value) return
  // 把嵌套的 steps 展平为表格行
  const rows: any[] = []
  for (const step of guide.value.steps) {
    rows.push({
      step_no: step.step_no,
      title: step.title,
      action: step.action,
      risk_level: riskText(step.risk_level),
      tools: (step.tools || []).join(' / '),
      compliance: (step.compliance || []).join(' / '),
      estimated_minutes: step.estimated_minutes,
    })
  }
  const columns: Column[] = [
    { key: 'step_no', label: '步骤', width: 8 },
    { key: 'title', label: '标题', width: 24 },
    { key: 'action', label: '操作', width: 50 },
    { key: 'risk_level', label: '风险', width: 10 },
    { key: 'tools', label: '工具', width: 20 },
    { key: 'compliance', label: '合规', width: 30 },
    { key: 'estimated_minutes', label: '耗时(min)', width: 10 },
  ]
  exportExcel(columns, rows, `${guide.value.sop_id}_${Date.now()}`)
}

function finishExecution() {
  ElMessage.success('执行记录已提交，可用于案例沉淀')
}

onMounted(async () => {
  try {
    const r = await listMaintenanceLevels()
    levels.value = r.levels
  } catch (e) {
    // 后端不可用时 levels 留空（前端不再硬编码兜底，避免与后端 drift）
  }
})
</script>

<style lang="scss" scoped>
.config-card {
  background: var(--bg-tertiary);
}

.guide-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.safety-alert {
  margin-bottom: 16px;
}

.sub-card {
  background: var(--bg-secondary);
}

.step-card {
  background: var(--bg-tertiary);
  border: 1px solid var(--border-color);
  margin-top: 8px;
}

.step-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  flex-wrap: wrap;
}

.step-action {
  color: var(--text-primary);
  line-height: 1.7;
  font-size: 14px;
  margin: 8px 0;
}

.step-section {
  margin-top: 8px;
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.7;

  strong {
    color: var(--text-primary);
  }
}

.compliance {
  background: var(--bg-secondary);
  padding: 8px 12px;
  border-left: 3px solid var(--success);
  border-radius: 4px;
}

.progress-summary {
  text-align: center;
  color: var(--text-muted);
}

.progress-section {
  background: var(--bg-secondary);
  padding: 16px;
  border-radius: 8px;
}
</style>
