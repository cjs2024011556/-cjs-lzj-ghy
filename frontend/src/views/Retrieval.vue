<template>
  <PageContainer>
    <SectionTitle title="多模态知识检索" icon="Search" />

    <el-card class="search-card fade-in">
      <el-form @submit.prevent="handleSearch">
        <el-form-item>
          <el-input
            v-model="query"
            type="textarea"
            :rows="3"
            placeholder="描述您的故障现象或问题，例如：液压站压力波动、电机轴承温度高、阀门内漏..."
            size="large"
            clearable
            @keyup.ctrl.enter="handleSearch"
          />
        </el-form-item>

        <el-row :gutter="16">
          <el-col :xs="24" :sm="12">
            <el-form-item label="设备型号（可选）">
              <el-input v-model="equipmentModel" placeholder="如：YUKEN A37、YE3 160M-4" clearable />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :sm="12">
            <el-form-item label="上传故障图片（可选）">
              <el-upload
                v-model:file-list="fileList"
                :auto-upload="false"
                :limit="1"
                accept="image/*"
                list-type="picture"
                :on-change="handleFileChange"
                :on-remove="handleFileRemove"
              >
                <el-button>
                  <el-icon><Picture /></el-icon>
                  选择图片
                </el-button>
                <template #tip>
                  <div style="color: var(--text-muted); font-size: 12px">
                    支持 jpg/png/webp，最大 5MB
                  </div>
                </template>
              </el-upload>
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item>
          <div style="display: flex; gap: 12px; align-items: center; width: 100%">
            <el-button
              type="primary"
              size="large"
              :loading="loading"
              @click="handleSearch"
              style="min-width: 140px"
            >
              <el-icon><Search /></el-icon>
              智能检索
            </el-button>
            <el-button size="large" @click="clearAll">清空</el-button>
            <div style="flex: 1; text-align: right; color: var(--text-muted); font-size: 13px">
              快捷键: <kbd>Ctrl</kbd> + <kbd>Enter</kbd>
            </div>
          </div>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 检索结果 -->
    <div v-if="result" class="result-section fade-in mt-lg">
      <el-card>
        <template #header>
          <div class="result-header">
            <span>
              <el-icon><ChatLineSquare /></el-icon>
              AI 解答
            </span>
            <div style="display: flex; gap: 12px; align-items: center; font-size: 13px; color: var(--text-muted)">
              <el-tag size="small" effect="plain">{{ result.model }}</el-tag>
              <span><el-icon><Timer /></el-icon> {{ result.latency_ms }}ms</span>
              <span v-if="result.usage?.total_tokens">
                <el-icon><Coin /></el-icon> {{ result.usage.total_tokens }} tokens
              </span>
            </div>
          </div>
        </template>
        <div class="answer-content" v-html="renderedAnswer"></div>
      </el-card>

      <el-card class="mt-md" v-if="result.hits?.length">
        <template #header>
          <div class="result-header">
            <span>
              <el-icon><Files /></el-icon>
              引用来源（{{ result.hits.length }}）
            </span>
            <span style="font-size: 13px; color: var(--text-muted)">
              按相关度排序
            </span>
          </div>
        </template>
        <div class="hits-list">
          <el-card
            v-for="(hit, idx) in result.hits"
            :key="hit.chunk_id"
            class="hit-item"
            shadow="hover"
          >
            <div class="hit-header">
              <span class="hit-num">【{{ idx + 1 }}】</span>
              <el-tag size="small" :type="docTypeColor(hit.doc_type)">{{ docTypeName(hit.doc_type) }}</el-tag>
              <el-tag size="small" effect="plain">{{ hit.equipment_type }}</el-tag>
              <el-tag v-if="hit.equipment_model" size="small" effect="plain" type="success">
                {{ hit.equipment_model }}
              </el-tag>
              <span class="hit-score">相关度: {{ (hit.score * 100).toFixed(1) }}%</span>
            </div>
            <div class="hit-content">{{ hit.content }}</div>
            <div class="hit-source">来源: {{ hit.source }}</div>
          </el-card>
        </div>
      </el-card>

      <!-- 反馈 -->
      <el-card class="mt-md">
        <template #header>
          <span><el-icon><Star /></el-icon> 答案反馈</span>
        </template>
        <el-rate v-model="rating" show-text :texts="['差', '一般', '可用', '好', '很好']" />
        <el-input
          v-model="feedback"
          type="textarea"
          :rows="2"
          placeholder="如果答案有误或不完整，请说明（可选）"
          class="mt-sm"
        />
        <div class="mt-sm feedback-actions">
          <el-button type="primary" plain @click="submitFeedback" :disabled="!result">
            <el-icon><Promotion /></el-icon>
            提交反馈
          </el-button>
        </div>
      </el-card>
    </div>
  </PageContainer>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import type { UploadFile, UploadUserFile } from 'element-plus'
import { marked } from 'marked'
import PageContainer from '@/components/base/PageContainer.vue'
import SectionTitle from '@/components/base/SectionTitle.vue'
import {
  retrieveByText,
  retrieveMultimodal,
  type RetrievalResponse,
} from '@/api/retrieval'
import { submitFeedback } from '@/api/knowledge'

const query = ref('')
const equipmentModel = ref('')
const fileList = ref<UploadUserFile[]>([])
const imageFile = ref<File | null>(null)
const loading = ref(false)
const result = ref<RetrievalResponse | null>(null)
const rating = ref(0)
const feedback = ref('')

const renderedAnswer = computed(() => {
  if (!result.value?.answer) return ''
  return marked.parse(result.value.answer, { breaks: true })
})

function docTypeColor(t: string) {
  return { manual: 'primary', case: 'success', sop: 'warning' }[t] || 'info'
}

function docTypeName(t: string) {
  return { manual: '手册', case: '案例', sop: 'SOP' }[t] || t
}

function handleFileChange(file: UploadFile) {
  imageFile.value = file.raw as File
}

function handleFileRemove() {
  imageFile.value = null
}

function clearAll() {
  query.value = ''
  equipmentModel.value = ''
  fileList.value = []
  imageFile.value = null
  result.value = null
  rating.value = 0
  feedback.value = ''
}

async function handleSearch() {
  if (!query.value.trim() && !imageFile.value) {
    ElMessage.warning('请输入问题或上传图片')
    return
  }

  loading.value = true
  try {
    let resp: RetrievalResponse
    if (imageFile.value) {
      // 多模态检索
      const formData = new FormData()
      formData.append('query', query.value || '请分析这张故障图片')
      if (equipmentModel.value) formData.append('equipment_model', equipmentModel.value)
      formData.append('image', imageFile.value)
      resp = await retrieveMultimodal(formData)
    } else {
      // 纯文本检索
      resp = await retrieveByText({
        query: query.value,
        equipment_model: equipmentModel.value || undefined,
        top_k: 5,
      })
    }
    result.value = resp
    ElMessage.success(`检索完成 (${resp.latency_ms}ms)`)
  } catch (e) {
    // 错误已由 axios 拦截器提示
  } finally {
    loading.value = false
  }
}

async function submitFeedback() {
  if (!result.value) return
  try {
    await submitFeedback({
      query: result.value.query,
      original_answer: result.value.answer,
      correction: feedback.value,
      rating: rating.value || 5,
    })
    ElMessage.success('反馈已提交，感谢您的支持')
    feedback.value = ''
    rating.value = 0
  } catch (e) {
    // ignore
  }
}
</script>

<style lang="scss" scoped>
.feedback-actions {
  text-align: right;
}
.search-card {
  background: var(--bg-tertiary);
}

.result-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  color: var(--text-primary);
}

.answer-content {
  font-size: 15px;
  line-height: 1.8;
  color: var(--text-primary);

  :deep(pre) {
    background: var(--bg-secondary);
    padding: 12px;
    border-radius: 4px;
    overflow-x: auto;
  }

  :deep(code) {
    background: var(--bg-secondary);
    padding: 2px 6px;
    border-radius: 3px;
    color: var(--primary-color);
  }
}

.hits-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.hit-item {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);

  .hit-header {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 8px;
    flex-wrap: wrap;
  }

  .hit-num {
    color: var(--primary-color);
    font-weight: 600;
  }

  .hit-score {
    margin-left: auto;
    color: var(--success);
    font-size: 13px;
  }

  .hit-content {
    color: var(--text-secondary);
    line-height: 1.7;
    font-size: 14px;
  }

  .hit-source {
    margin-top: 8px;
    color: var(--text-muted);
    font-size: 12px;
    font-family: monospace;
  }
}
</style>
