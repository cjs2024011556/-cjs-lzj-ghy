<template>
  <el-dialog
    :model-value="modelValue"
    @update:model-value="(v) => emit('update:modelValue', v)"
    :title="caseData?.title || '案例详情'"
    width="720px"
    destroy-on-close
    class="case-detail-dialog"
  >
    <div v-if="caseData" class="case-detail">
      <el-descriptions :column="2" border>
        <el-descriptions-item label="案例 ID">
          <code class="case-id">{{ caseData.case_id }}</code>
        </el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="statusType(caseData.status)" effect="dark">
            {{ statusText(caseData.status) }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="设备类型">
          {{ caseData.equipment_type }}
        </el-descriptions-item>
        <el-descriptions-item label="设备型号">
          {{ caseData.equipment_model || '—' }}
        </el-descriptions-item>
        <el-descriptions-item label="提交人">
          {{ caseData.submitter }}
        </el-descriptions-item>
        <el-descriptions-item v-if="caseData.department" label="部门">
          {{ caseData.department }}
        </el-descriptions-item>
        <el-descriptions-item label="提交时间" :span="2">
          {{ caseData.submitted_at }}
        </el-descriptions-item>
        <el-descriptions-item v-if="caseData.reviewed_at" label="审核时间" :span="2">
          {{ caseData.reviewed_at }}
        </el-descriptions-item>
      </el-descriptions>

      <section class="case-section">
        <h4 class="section-label">🔍 故障描述</h4>
        <div class="text-block">{{ caseData.fault_description }}</div>
      </section>

      <section class="case-section">
        <h4 class="section-label">🔧 解决方案</h4>
        <div class="text-block solution">{{ caseData.solution }}</div>
      </section>

      <section v-if="caseData.root_cause || caseData.prevention" class="case-section">
        <div v-if="caseData.root_cause" class="analysis-row">
          <span class="analysis-label">🎯 根本原因</span>
          <span class="analysis-text">{{ caseData.root_cause }}</span>
        </div>
        <div v-if="caseData.prevention" class="analysis-row">
          <span class="analysis-label">🛡 预防措施</span>
          <span class="analysis-text">{{ caseData.prevention }}</span>
        </div>
      </section>

      <section v-if="caseData.tags?.length" class="case-section">
        <h4 class="section-label">🏷 标签</h4>
        <el-space wrap>
          <el-tag v-for="t in caseData.tags" :key="t" effect="plain" size="small">
            {{ t }}
          </el-tag>
        </el-space>
      </section>

      <section v-if="caseData.duration_hours || caseData.downtime_cost_yuan" class="case-section case-meta-grid">
        <div v-if="caseData.duration_hours" class="meta-item">
          <div class="meta-num">
            <AnimatedNumber :value="caseData.duration_hours" />
            <span class="meta-unit">h</span>
          </div>
          <div class="meta-label">维修耗时</div>
        </div>
        <div v-if="caseData.downtime_cost_yuan" class="meta-item">
          <div class="meta-num">
            ¥<AnimatedNumber :value="caseData.downtime_cost_yuan" />
          </div>
          <div class="meta-label">停机损失</div>
        </div>
      </section>

      <el-alert
        v-if="caseData.review_comment"
        :title="`审核意见: ${caseData.review_comment}`"
        :type="caseData.status === 'approved' ? 'success' : 'error'"
        show-icon
        :closable="false"
        class="review-alert"
      />
    </div>

    <template v-if="showReview" #footer>
      <el-button @click="emit('update:modelValue', false)">关闭</el-button>
      <el-button type="danger" :loading="submitting" @click="onReview(false)">驳回</el-button>
      <el-button type="success" :loading="submitting" @click="onReview(true)">通过</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ElMessage, ElMessageBox } from 'element-plus'
import { reviewCase } from '@/api/knowledge'
import type { CaseRecord } from '@/api/knowledge'
import AnimatedNumber from '@/components/base/AnimatedNumber.vue'

const props = defineProps<{
  modelValue: boolean
  caseData: CaseRecord | null
  showReview?: boolean
  submitting?: boolean
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', v: boolean): void
  (e: 'reviewed'): void
}>()

function statusType(s: string) {
  return { pending: 'warning', approved: 'success', rejected: 'danger' }[s] || 'info'
}
function statusText(s: string) {
  return { pending: '待审核', approved: '已通过', rejected: '已驳回' }[s] || s
}

async function onReview(approved: boolean) {
  if (!props.caseData) return
  let comment = ''
  if (!approved) {
    try {
      const { value } = await ElMessageBox.prompt('请输入驳回原因', '驳回审核', {
        confirmButtonText: '确认驳回',
        cancelButtonText: '取消',
        inputType: 'textarea',
        inputValidator: (v) => (v && v.trim() ? true : '请填写驳回原因'),
      })
      comment = value
    } catch {
      return
    }
  }
  try {
    await reviewCase({
      case_id: props.caseData.case_id,
      approved,
      review_comment: comment,
    })
    ElMessage.success(approved ? '已通过' : '已驳回')
    emit('reviewed')
    emit('update:modelValue', false)
  } catch (e) {
    // axios 拦截器已经提示
  }
}
</script>

<style lang="scss" scoped>
.case-detail-dialog :deep(.el-dialog__body) {
  padding: 16px 24px;
}

.case-detail {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.case-id {
  background: var(--bg-tertiary);
  padding: 2px 8px;
  border-radius: var(--radius-sm);
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: var(--font-size-sm);
  color: var(--primary-color);
}

.case-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.section-label {
  margin: 0;
  font-size: var(--font-size-md);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
}

.text-block {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: 12px;
  line-height: 1.7;
  color: var(--text-secondary);
  white-space: pre-wrap;

  &.solution {
    border-left: 3px solid var(--primary-color);
  }
}

.analysis-row {
  display: flex;
  gap: 12px;
  padding: 8px 12px;
  background: var(--bg-secondary);
  border-radius: var(--radius-md);
  border-left: 3px solid var(--warning);
}

.analysis-label {
  font-weight: var(--font-weight-semibold);
  color: var(--warning);
  flex-shrink: 0;
}

.analysis-text {
  color: var(--text-secondary);
  line-height: 1.6;
}

.case-meta-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
  background: var(--bg-tertiary);
  padding: 16px;
  border-radius: var(--radius-md);
}

.meta-item {
  text-align: center;
}

.meta-num {
  font-size: var(--font-size-2xl);
  font-weight: var(--font-weight-bold);
  color: var(--primary-color);
  font-variant-numeric: tabular-nums;
}

.meta-unit {
  font-size: var(--font-size-md);
  color: var(--text-muted);
  margin-left: 2px;
}

.meta-label {
  font-size: var(--font-size-xs);
  color: var(--text-muted);
  margin-top: 4px;
}

.review-alert {
  margin-top: 8px;
}
</style>
