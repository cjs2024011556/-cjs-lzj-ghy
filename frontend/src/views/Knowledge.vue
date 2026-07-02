<template>
  <PageContainer>
    <SectionTitle title="📚 知识管理" icon="Notebook" />

    <el-tabs v-model="activeTab" class="fade-in">
      <!-- 提交案例 -->
      <el-tab-pane name="submit" label="提交案例">
        <el-card>
          <el-form :model="form" :rules="rules" ref="formRef" label-width="100px">
            <el-form-item label="案例标题" prop="title">
              <el-input v-model="form.title" placeholder="简洁描述案例，如：液压站压力波动大" />
            </el-form-item>
            <el-row :gutter="16">
              <el-col :span="12">
                <el-form-item label="设备类型" prop="equipment_type">
                  <el-select v-model="form.equipment_type" placeholder="选择" style="width: 100%">
                    <el-option
                      v-for="t in EQUIPMENT_TYPES"
                      :key="t.value"
                      :label="t.label"
                      :value="t.value"
                    />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="设备型号">
                  <el-input v-model="form.equipment_model" placeholder="可选" />
                </el-form-item>
              </el-col>
            </el-row>
            <el-form-item label="故障描述" prop="fault_description">
              <el-input v-model="form.fault_description" type="textarea" :rows="3" placeholder="详细描述故障现象、发生条件、已观察到的异常" />
            </el-form-item>
            <el-form-item label="处理方案" prop="solution">
              <el-input v-model="form.solution" type="textarea" :rows="4" placeholder="详细描述处理步骤、所用工具、更换的零部件" />
            </el-form-item>
            <el-form-item label="标签">
              <el-input v-model="tagsInput" placeholder="多个标签用英文逗号分隔" />
            </el-form-item>
            <el-form-item label="提交人">
              <el-input v-model="form.submitter" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="submitting" @click="onSubmit">
                <el-icon><Promotion /></el-icon>
                提交审核
              </el-button>
              <el-button @click="resetForm">重置</el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-tab-pane>

      <!-- 我的案例 -->
      <el-tab-pane name="my" label="我的案例">
        <el-card>
          <div class="filter-bar">
            <el-radio-group v-model="myStatus" @change="loadMyCases">
              <el-radio-button value="">全部</el-radio-button>
              <el-radio-button value="pending">待审核</el-radio-button>
              <el-radio-button value="approved">已通过</el-radio-button>
              <el-radio-button value="rejected">已驳回</el-radio-button>
            </el-radio-group>
            <TableExportBar
              style="margin-left: auto"
              :columns="myCaseColumns"
              :data="myCases"
              filename="我的案例"
              :pdf-element="myCasesTableRef"
              pdf-title="我的案例 - A1 设备检修系统"
              type="primary"
            />
            <el-button @click="loadMyCases">
              <el-icon><Refresh /></el-icon>
              刷新
            </el-button>
          </div>

          <div ref="myCasesTableRef">
          <el-table :data="myCases" stripe v-loading="myLoading" class="mt-md">
            <el-table-column prop="case_id" label="ID" width="180" />
            <el-table-column prop="title" label="标题" show-overflow-tooltip />
            <el-table-column prop="equipment_type" label="设备类型" width="120" />
            <el-table-column prop="submitter" label="提交人" width="100" />
            <el-table-column label="状态" width="120">
              <template #default="{ row }">
                <el-tag :type="statusType(row.status)" effect="dark">
                  {{ statusText(row.status) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="submitted_at" label="提交时间" width="180" />
            <el-table-column label="操作" width="100" fixed="right">
              <template #default="{ row }">
                <el-button size="small" text @click="viewCase(row)">查看</el-button>
              </template>
            </el-table-column>
          </el-table>
          </div>
        </el-card>
      </el-tab-pane>

      <!-- 反馈历史 -->
      <el-tab-pane name="feedback" label="我的反馈">
        <el-card>
          <div class="filter-bar" style="margin-bottom: 12px">
            <TableExportBar
              style="margin-left: auto"
              :columns="feedbackColumns"
              :data="feedbacks"
              filename="我的反馈"
            />
          </div>
          <el-table :data="feedbacks" stripe v-loading="fbLoading">
            <el-table-column prop="feedback_id" label="ID" width="160" />
            <el-table-column prop="query" label="原问题" show-overflow-tooltip />
            <el-table-column label="评分" width="100">
              <template #default="{ row }">
                <el-rate v-model="row.rating" disabled show-score />
              </template>
            </el-table-column>
            <el-table-column prop="correction" label="纠正" show-overflow-tooltip />
            <el-table-column prop="created_at" label="时间" width="180" />
          </el-table>
        </el-card>
      </el-tab-pane>
    </el-tabs>

    <!-- 案例详情（统一复用 CaseDetailDialog） -->
    <CaseDetailDialog v-model="showDetail" :case-data="currentCase" @reviewed="loadMyCases" />
  </PageContainer>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage, type FormInstance } from 'element-plus'
import { EQUIPMENT_TYPES } from '@/constants/equipment'
import {
  submitCase,
  listCases,
  listFeedback,
  type CaseRecord,
  type Feedback,
} from '@/api/knowledge'
import PageContainer from '@/components/base/PageContainer.vue'
import SectionTitle from '@/components/base/SectionTitle.vue'
import CaseDetailDialog from '@/components/business/CaseDetailDialog.vue'
import TableExportBar from '@/components/business/TableExportBar.vue'
import type { Column } from '@/utils/exporters'

const activeTab = ref('submit')
const formRef = ref<FormInstance>()
const submitting = ref(false)
const tagsInput = ref('')

const form = ref({
  title: '',
  equipment_type: '',
  equipment_model: '',
  fault_description: '',
  solution: '',
  submitter: '王师傅',
})

const rules = {
  title: [{ required: true, message: '请输入标题', trigger: 'blur' }],
  equipment_type: [{ required: true, message: '请选择设备类型', trigger: 'change' }],
  fault_description: [{ required: true, message: '请输入故障描述', trigger: 'blur' }],
  solution: [{ required: true, message: '请输入解决方案', trigger: 'blur' }],
}

const myStatus = ref('')
const myCases = ref<CaseRecord[]>([])
const myLoading = ref(false)
const myCasesTableRef = ref<HTMLElement | null>(null)

const myCaseColumns: Column[] = [
  { key: 'case_id', label: '案例 ID', width: 20 },
  { key: 'title', label: '标题', width: 30 },
  { key: 'equipment_type', label: '设备类型', width: 14 },
  { key: 'equipment_model', label: '设备型号', width: 16 },
  { key: 'submitter', label: '提交人', width: 10 },
  { key: 'status', label: '状态', format: (k, row) => statusText(row.status), width: 10 },
  { key: 'submitted_at', label: '提交时间', width: 20 },
]

async function loadMyCases() {
  myLoading.value = true
  try {
    const r = await listCases(myStatus.value || undefined)
    myCases.value = r.cases
  } finally {
    myLoading.value = false
  }
}

const showDetail = ref(false)
const currentCase = ref<CaseRecord | null>(null)
function viewCase(row: CaseRecord) {
  currentCase.value = row
  showDetail.value = true
}

const feedbacks = ref<Feedback[]>([])
const fbLoading = ref(false)
const feedbackColumns: Column[] = [
  { key: 'feedback_id', label: '反馈 ID', width: 18 },
  { key: 'query', label: '原问题', width: 40 },
  { key: 'rating', label: '评分', width: 8 },
  { key: 'correction', label: '纠正', width: 40 },
  { key: 'created_at', label: '时间', width: 20 },
]
async function loadFeedback() {
  fbLoading.value = true
  try {
    const r = await listFeedback()
    feedbacks.value = r.feedback
  } finally {
    fbLoading.value = false
  }
}

function statusType(s: string) {
  return { pending: 'warning', approved: 'success', rejected: 'danger' }[s] || 'info'
}
function statusText(s: string) {
  return { pending: '待审核', approved: '已通过', rejected: '已驳回' }[s] || s
}

async function onSubmit() {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (!valid) return
    submitting.value = true
    try {
      const tags = tagsInput.value.split(',').map((t) => t.trim()).filter(Boolean)
      const r = await submitCase({ ...form.value, tags })
      ElMessage.success(`提交成功！案例 ID: ${r.case_id}，待审核`)
      resetForm()
    } catch (e) {
      // ignore
    } finally {
      submitting.value = false
    }
  })
}

function resetForm() {
  form.value = {
    title: '',
    equipment_type: '',
    equipment_model: '',
    fault_description: '',
    solution: '',
    submitter: '王师傅',
  }
  tagsInput.value = ''
  formRef.value?.resetFields()
}

onMounted(() => {
  loadMyCases()
  loadFeedback()
})
</script>

<style lang="scss" scoped>
.filter-bar {
  display: flex;
  align-items: center;
  gap: 12px;
}
</style>
