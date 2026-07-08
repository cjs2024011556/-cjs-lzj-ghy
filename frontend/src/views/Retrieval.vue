<template>
  <PageContainer>
    <!-- ENT-1: 页面标题行（克制，不带渐变 / emoji） -->
    <div class="page-header">
      <div class="page-title-block">
        <h2 class="page-title">多模态知识检索</h2>
        <p class="page-desc">基于工业 RAG 的跨模态检索 · 文本 / 图像 / 设备型号</p>
      </div>
      <div class="page-meta">
        <span class="meta-item">
          <span class="meta-label">知识库</span>
          <span class="meta-value">A1-Manuals · v1.0</span>
        </span>
        <el-divider direction="vertical" />
        <span class="meta-item">
          <span class="meta-label">嵌入模型</span>
          <span class="meta-value">text-embedding-v3</span>
        </span>
        <el-divider direction="vertical" />
        <span class="meta-item">
          <span class="meta-label">检索模式</span>
          <span class="meta-value">语义 + Rerank</span>
        </span>
      </div>
    </div>

    <!-- ENT-1: 主布局 — 左筛选 / 右结果 -->
    <div class="retrieval-layout">
      <!-- 左侧：检索条件面板（固定宽度） -->
      <aside class="retrieval-aside">
        <el-card class="aside-card" shadow="never">
          <template #header>
            <div class="aside-header">
              <el-icon><Filter /></el-icon>
              <span>检索条件</span>
              <el-button text size="small" class="aside-clear" @click="clearAll" :disabled="!hasAnyInput">
                <el-icon><RefreshLeft /></el-icon>
                重置
              </el-button>
            </div>
          </template>

          <!-- 主输入：故障描述 -->
          <div class="form-block">
            <label class="form-label">
              <span class="form-label-text">查询文本</span>
              <span class="form-label-required">必填</span>
            </label>
            <el-input
              v-model="query"
              type="textarea"
              :rows="4"
              placeholder="描述故障现象或问题，例如：液压站压力波动、电机轴承温度高、阀门内漏…"
              :disabled="loading"
              maxlength="500"
              show-word-limit
              @keydown.ctrl.enter="handleSearch"
            />
          </div>

          <!-- 设备型号 -->
          <div class="form-block">
            <label class="form-label">
              <span class="form-label-text">设备型号</span>
              <span class="form-label-optional">可选</span>
            </label>
            <el-input
              v-model="equipmentModel"
              placeholder="如：YUKEN A37、YE3 160M-4"
              :disabled="loading"
              clearable
            />
          </div>

          <!-- 图片 -->
          <div class="form-block">
            <label class="form-label">
              <span class="form-label-text">故障图像</span>
              <span class="form-label-optional">可选</span>
            </label>
            <el-upload
              v-model:file-list="fileList"
              :auto-upload="false"
              :limit="1"
              accept="image/*"
              :on-change="handleFileChange"
              :on-remove="handleFileRemove"
              :show-file-list="false"
            >
              <div v-if="!imagePreviewUrl" class="upload-trigger">
                <el-icon :size="20"><Picture /></el-icon>
                <span>选择图片</span>
                <span class="upload-hint">jpg / png / webp · ≤ 5MB</span>
              </div>
              <el-image
                v-else
                :src="imagePreviewUrl"
                :preview-src-list="[imagePreviewUrl]"
                :initial-index="0"
                fit="cover"
                class="upload-preview"
              >
                <template #error>
                  <div class="image-error">
                    <el-icon><Picture /></el-icon>
                  </div>
                </template>
              </el-image>
            </el-upload>
          </div>

          <!-- 来源类型筛选 -->
          <div class="form-block">
            <label class="form-label">
              <span class="form-label-text">来源类型</span>
              <span class="form-label-optional">多选</span>
            </label>
            <el-checkbox-group v-model="sourceTypeFilter" :disabled="loading" class="source-filter">
              <el-checkbox value="manual">手册</el-checkbox>
              <el-checkbox value="case">案例</el-checkbox>
              <el-checkbox value="sop">SOP</el-checkbox>
            </el-checkbox-group>
          </div>

          <!-- Top-K 滑块（紧凑） -->
          <div class="form-block">
            <label class="form-label">
              <span class="form-label-text">返回条数</span>
              <span class="form-label-value">Top {{ topK }}</span>
            </label>
            <el-slider
              v-model="topK"
              :min="1"
              :max="20"
              :step="1"
              :disabled="loading"
              show-stops
              :marks="{ 5: '5', 10: '10', 20: '20' }"
            />
          </div>

          <!-- 高级选项折叠 -->
          <el-collapse v-model="advancedOpen" class="advanced-collapse">
            <el-collapse-item name="1" title="高级选项">
              <div class="form-block">
                <label class="form-label">
                  <span class="form-label-text">最低相关度</span>
                  <span class="form-label-value">≥ {{ minScore }}%</span>
                </label>
                <el-slider
                  v-model="minScore"
                  :min="0"
                  :max="100"
                  :step="5"
                  :disabled="loading"
                />
              </div>
              <div class="form-block">
                <label class="form-label">
                  <span class="form-label-text">检索深度</span>
                </label>
                <el-radio-group v-model="searchMode" :disabled="loading" size="small">
                  <el-radio-button value="hybrid">混合</el-radio-button>
                  <el-radio-button value="semantic">语义</el-radio-button>
                  <el-radio-button value="keyword">关键词</el-radio-button>
                </el-radio-group>
              </div>
            </el-collapse-item>
          </el-collapse>

          <div class="form-actions">
            <el-button
              type="primary"
              :loading="loading"
              :disabled="!canSearch"
              @click="handleSearch"
              class="search-btn"
            >
              <el-icon><Search /></el-icon>
              开始检索
            </el-button>
          </div>
        </el-card>
      </aside>

      <!-- 右侧：结果区 -->
      <main class="retrieval-main">
        <!-- 空状态：未检索 -->
        <div v-if="!result && !loading && !errorState" class="empty-state">
          <el-empty :image-size="120" description="输入查询条件后开始检索" />
          <div class="empty-tips">
            <div class="empty-tip-item">
              <span class="tip-num">1</span>
              <span>在左侧输入故障描述（必填）</span>
            </div>
            <div class="empty-tip-item">
              <span class="tip-num">2</span>
              <span>可选：填设备型号精准过滤 / 上传故障图</span>
            </div>
            <div class="empty-tip-item">
              <span class="tip-num">3</span>
              <span>点「开始检索」查看 AI 解答 + 引用来源</span>
            </div>
          </div>
        </div>

        <!-- 加载中 -->
        <div v-else-if="loading" class="loading-state">
          <LoadingState text="正在检索知识库…" full />
        </div>

        <!-- 错误状态 -->
        <div v-else-if="errorState" class="error-state">
          <el-result icon="error" :title="errorState.title" :sub-title="errorState.detail">
            <template #extra>
              <el-tag size="small" type="info">错误码 {{ errorState.code }}</el-tag>
              <el-button type="primary" plain @click="handleSearch" class="ml-sm">
                <el-icon><RefreshRight /></el-icon>
                重试
              </el-button>
            </template>
          </el-result>
        </div>

        <!-- 正常结果 -->
        <template v-else-if="result">
          <!-- AI 解答 -->
          <el-card
            ref="answerCardRef"
            class="result-card"
            shadow="never"
          >
            <template #header>
              <div class="result-header">
                <div class="result-header-left">
                  <span class="result-title">AI 解答</span>
                  <el-tag size="small" effect="plain" type="info">
                    基于 {{ filteredHits.length }} 条引用
                  </el-tag>
                </div>
                <div class="result-header-right">
                  <span class="result-meta-item">
                    <span class="result-meta-label">模型</span>
                    <span class="result-meta-value">{{ result.model }}</span>
                  </span>
                  <el-divider direction="vertical" />
                  <span class="result-meta-item">
                    <span class="result-meta-label">检索</span>
                    <span class="result-meta-value">{{ result.latency_ms }} ms</span>
                  </span>
                  <span v-if="result.usage?.total_tokens" class="result-meta-item">
                    <span class="result-meta-label">消耗</span>
                    <span class="result-meta-value">{{ result.usage.total_tokens }} tokens</span>
                  </span>
                  <el-divider direction="vertical" />
                  <el-dropdown trigger="click" @command="(cmd) => onExportCommand(cmd)">
                    <el-button size="small" plain>
                      <el-icon><Download /></el-icon>
                      导出
                      <el-icon><ArrowDown /></el-icon>
                    </el-button>
                    <template #dropdown>
                      <el-dropdown-menu>
                        <el-dropdown-item command="pdf">PDF 报告</el-dropdown-item>
                        <el-dropdown-item command="md">Markdown</el-dropdown-item>
                        <el-dropdown-item command="json">JSON 原始</el-dropdown-item>
                      </el-dropdown-menu>
                    </template>
                  </el-dropdown>
                </div>
              </div>
            </template>
            <div class="answer-content" v-html="renderedAnswer" @click="onAnswerClick"></div>
          </el-card>

          <!-- 引用来源（结构化） -->
          <el-card
            v-if="filteredHits.length > 0"
            ref="hitsCardRef"
            class="result-card hits-card"
            shadow="never"
          >
            <template #header>
              <div class="result-header">
                <div class="result-header-left">
                  <span class="result-title">引用来源</span>
                  <span class="result-count">{{ filteredHits.length }} 条命中</span>
                </div>
                <div class="result-header-right">
                  <span class="result-meta-item">
                    <span class="result-meta-label">排序</span>
                    <span class="result-meta-value">按相关度</span>
                  </span>
                </div>
              </div>
            </template>
            <ul class="hits-list">
              <li
                v-for="(hit, idx) in filteredHits"
                :key="hit.chunk_id"
                :id="`hit-${idx + 1}`"
                class="hit-item"
                :class="{ expanded: expandedHits.has(hit.chunk_id), highlighted: highlightedHitId === hit.chunk_id }"
              >
                <div class="hit-summary" @click="toggleHitExpand(hit.chunk_id)">
                  <div class="hit-summary-left">
                    <span class="hit-index">{{ String(idx + 1).padStart(2, '0') }}</span>
                    <el-icon :size="14" class="hit-type-icon">
                      <component :is="getDocTypeIcon(hit.doc_type)" />
                    </el-icon>
                    <span class="hit-title">{{ hitDocTitle(hit) }}</span>
                  </div>
                  <div class="hit-summary-right">
                    <div class="hit-score-bar" :title="`相关度 ${(hit.score * 100).toFixed(1)}%`">
                      <div class="hit-score-fill" :style="{ width: (hit.score * 100) + '%' }"></div>
                    </div>
                    <span class="hit-score-text">{{ (hit.score * 100).toFixed(0) }}%</span>
                    <el-icon class="hit-expand-icon">
                      <ArrowDown v-if="!expandedHits.has(hit.chunk_id)" />
                      <ArrowUp v-else />
                    </el-icon>
                  </div>
                </div>
                <div v-if="expandedHits.has(hit.chunk_id)" class="hit-detail">
                  <div class="hit-meta">
                    <span class="hit-meta-item">
                      <span class="hit-meta-label">类型</span>
                      <span class="hit-meta-value">{{ docTypeName(hit.doc_type) }}</span>
                    </span>
                    <el-divider direction="vertical" />
                    <span class="hit-meta-item">
                      <span class="hit-meta-label">设备</span>
                      <span class="hit-meta-value">{{ hit.equipment_type || '—' }}</span>
                    </span>
                    <span v-if="hit.equipment_model" class="hit-meta-item">
                      <span class="hit-meta-label">型号</span>
                      <span class="hit-meta-value">{{ hit.equipment_model }}</span>
                    </span>
                    <el-divider direction="vertical" />
                    <span class="hit-meta-item">
                      <span class="hit-meta-label">源文件</span>
                      <span class="hit-meta-value hit-source">{{ hit.source }}</span>
                    </span>
                  </div>

                  <!-- PDF-A.7: 结构化元信息（章节 / 页码 / 类型） -->
                  <div v-if="hasStructuredMeta(hit)" class="hit-structured-meta">
                    <el-tag
                      v-if="hit.page_number"
                      type="info"
                      size="small"
                      effect="dark"
                      round
                    >
                      📄 第 {{ hit.page_number }}{{ hit.page_end && hit.page_end > hit.page_number ? '-' + hit.page_end : '' }} 页
                    </el-tag>
                    <el-tag
                      v-if="hit.chapter"
                      type="primary"
                      size="small"
                      effect="plain"
                      round
                    >
                      {{ hit.chapter }}
                    </el-tag>
                    <el-tag
                      v-if="hit.section_title && hit.section_title !== hit.chapter"
                      size="small"
                      effect="plain"
                      round
                    >
                      §{{ hit.section_title }}
                    </el-tag>
                    <el-tag
                      v-if="hit.section_type === 'table'"
                      type="warning"
                      size="small"
                      effect="dark"
                      round
                    >
                      📊 表格
                    </el-tag>
                    <el-tag
                      v-else-if="hit.section_type === 'heading'"
                      type="success"
                      size="small"
                      effect="plain"
                      round
                    >
                      📌 标题锚点
                    </el-tag>
                  </div>

                  <!-- PDF-B.7: 视觉理解增强（聚群 B） -->
                  <div v-if="hit.image_description" class="hit-vl-box">
                    <div class="vl-box-head">
                      <el-icon :size="14"><Picture /></el-icon>
                      <span class="vl-box-title">视觉理解（VL 增强）</span>
                    </div>
                    <div class="vl-box-desc">{{ hit.image_description }}</div>
                    <div v-if="hit.image_facts" class="vl-box-facts">
                      <el-tag
                        v-for="(f, fi) in splitFacts(hit.image_facts)"
                        :key="fi"
                        size="small"
                        type="success"
                        effect="plain"
                        round
                        class="vl-fact-tag"
                      >
                        {{ f }}
                      </el-tag>
                    </div>
                  </div>

                  <div class="hit-content">{{ hit.content }}</div>
                  <div class="hit-actions">
                    <el-button size="small" text @click.stop="copyHitContent(hit)">
                      <el-icon><CopyDocument /></el-icon>
                      复制内容
                    </el-button>
                    <el-button size="small" text @click.stop="copyCitation(hit, idx)">
                      <el-icon><Link /></el-icon>
                      复制引用
                    </el-button>
                  </div>
                </div>
              </li>
            </ul>
          </el-card>

          <!-- 引用为空（命中 0 条） -->
          <el-card v-else class="result-card no-hits-card" shadow="never">
            <el-empty
              :image-size="80"
              title="未检索到匹配的引用来源"
              description="AI 解答基于通用知识生成，建议补充更具体的设备型号或故障现象"
            />
          </el-card>

          <!-- 反馈 -->
          <el-card class="result-card" shadow="never">
            <template #header>
              <span class="result-title">答案反馈</span>
            </template>
            <div class="feedback-row">
              <el-rate v-model="rating" :texts="['差', '一般', '可用', '好', '很好']" show-text />
              <el-button
                type="primary"
                size="small"
                :disabled="!rating"
                :loading="feedbackSubmitting"
                @click="submitFeedback"
              >
                提交
              </el-button>
            </div>
            <el-input
              v-model="feedback"
              type="textarea"
              :rows="2"
              placeholder="补充说明（可选）：答案哪里不准 / 漏了什么 / 引用是否相关"
              class="feedback-input"
            />
          </el-card>
        </template>
      </main>
    </div>
  </PageContainer>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import type { UploadFile, UploadUserFile } from 'element-plus'
import { renderSafeMarkdownCached } from '@/utils/markdown'
import PageContainer from '@/components/base/PageContainer.vue'
import LoadingState from '@/components/base/LoadingState.vue'
import {
  retrieveByText,
  retrieveMultimodal,
  type RetrievalResponse,
  type RetrievalHit,
} from '@/api/retrieval'
import { submitFeedback } from '@/api/knowledge'
import {
  exportPDFFromElements,
  exportMarkdownBlob,
  exportJSON,
  timestampFilename,
} from '@/utils/exporters'

// ============================================================
// ENT-2: 表单状态
// ============================================================
const query = ref('')
const equipmentModel = ref('')
const fileList = ref<UploadUserFile[]>([])
const imageFile = ref<File | null>(null)
const imagePreviewUrl = ref<string | null>(null)
const topK = ref(5)
const minScore = ref(0)  // 最低相关度（%）
const sourceTypeFilter = ref<string[]>(['manual', 'case', 'sop'])  // 来源类型多选
const searchMode = ref<'hybrid' | 'semantic' | 'keyword'>('hybrid')
const advancedOpen = ref<string[]>([])  // 高级选项折叠状态

// ============================================================
// ENT-4: 状态机（loading / error / empty / success）
// ============================================================
const loading = ref(false)
const result = ref<RetrievalResponse | null>(null)
const errorState = ref<{ code: number; title: string; detail: string } | null>(null)

// 反馈
const rating = ref(0)
const feedback = ref('')
const feedbackSubmitting = ref(false)

// 引用展开（默认展开前 3 条）
const expandedHits = ref<Set<string>>(new Set())

// ENT-8: 引用标号高亮（点击答案【N】时短暂高亮对应 hit 卡）
const highlightedHitId = ref<string | null>(null)

// DOM refs（PDF 导出用）
const answerCardRef = ref()
const hitsCardRef = ref()

// ============================================================
// ENT-2: 计算属性
// ============================================================
const hasAnyInput = computed(() => !!query.value.trim() || !!imageFile.value)
const canSearch = computed(() => hasAnyInput.value && !loading.value)

/** 根据来源类型 + 最低相关度 过滤后的 hits */
const filteredHits = computed<RetrievalHit[]>(() => {
  if (!result.value?.hits) return []
  return result.value.hits.filter((h) => {
    // 来源类型
    if (sourceTypeFilter.value.length > 0 && !sourceTypeFilter.value.includes(h.doc_type)) {
      return false
    }
    // 最低相关度
    if (minScore.value > 0 && h.score * 100 < minScore.value) {
      return false
    }
    return true
  })
})

// ============================================================
// ENT-3: 命中卡片辅助
// ============================================================
function getDocTypeIcon(t: string): string {
  if (t === 'manual') return 'Document'
  if (t === 'case') return 'Collection'
  if (t === 'sop') return 'SetUp'
  return 'Files'
}

function hitDocTitle(hit: RetrievalHit): string {
  // 从 source 字段提取可读标题（路径最后一段 / 章节名）
  const src = hit.source || ''
  const parts = src.split('/')
  const fileName = parts[parts.length - 1] || src
  // 去掉扩展名
  return fileName.replace(/\.(md|txt|markdown)$/i, '') || '未命名文档'
}

function toggleHitExpand(id: string) {
  if (expandedHits.value.has(id)) {
    expandedHits.value.delete(id)
  } else {
    expandedHits.value.add(id)
  }
  // 触发响应式
  expandedHits.value = new Set(expandedHits.value)
}

async function copyHitContent(hit: RetrievalHit) {
  try {
    await navigator.clipboard.writeText(hit.content)
    ElMessage.success('已复制到剪贴板')
  } catch {
    ElMessage.warning('复制失败，请手动选择')
  }
}

async function copyCitation(hit: RetrievalHit, idx: number) {
  const cite = `【${idx + 1}】 ${hitDocTitle(hit)} (相关度 ${(hit.score * 100).toFixed(1)}%)\n来源：${hit.source}`
  try {
    await navigator.clipboard.writeText(cite)
    ElMessage.success('引用已复制')
  } catch {
    ElMessage.warning('复制失败')
  }
}

const renderedAnswer = computed(() => {
  if (!result.value?.answer) return ''
  let html = renderSafeMarkdownCached(result.value.answer)
  // 把【1】【2】这种引用标号替换成可点击的锚点链接
  html = html.replace(/【(\d+)】/g, (_match, n) => {
    return `<a class="ref-link" href="#hit-${n}" data-ref="${n}">${n}</a>`
  })
  return html
})

/** 点击答案中的【N】引用标号 → 跳转到对应 hit 卡 + 高亮 */
function onAnswerClick(e: MouseEvent) {
  const target = e.target as HTMLElement
  if (target.classList.contains('ref-link')) {
    e.preventDefault()
    const refNum = target.dataset.ref
    if (!refNum) return
    const idx = parseInt(refNum, 10) - 1
    const hit = filteredHits.value[idx]
    if (!hit) return
    // 1. 高亮
    highlightedHitId.value = hit.chunk_id
    // 2. 展开
    expandedHits.value.add(hit.chunk_id)
    expandedHits.value = new Set(expandedHits.value)
    // 3. 滚动到该 hit
    setTimeout(() => {
      const el = document.getElementById(`hit-${idx + 1}`)
      if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'center' })
      }
    }, 50)
    // 4. 2 秒后取消高亮
    setTimeout(() => {
      if (highlightedHitId.value === hit.chunk_id) {
        highlightedHitId.value = null
      }
    }, 2000)
  }
}

function docTypeColor(t: string) {
  return { manual: 'primary', case: 'success', sop: 'warning' }[t] || 'info'
}

function docTypeName(t: string) {
  return { manual: '手册', case: '案例', sop: 'SOP' }[t] || t
}

// PDF-A.7: 命中是否含聚群 A 结构化字段
function hasStructuredMeta(hit: RetrievalHit): boolean {
  return !!(
    hit.page_number ||
    hit.chapter ||
    hit.section_title ||
    (hit.section_type && hit.section_type !== 'text')
  )
}

// PDF-B.7: 把 VL image_facts 字符串按逗号拆成数组
function splitFacts(factsStr?: string): string[] {
  if (!factsStr) return []
  return factsStr
    .split(/[,，;；]/)
    .map((s) => s.trim())
    .filter((s) => s.length > 0)
    .slice(0, 8)
}

function handleFileChange(file: UploadFile) {
  imageFile.value = file.raw as File
  // UPGRADE-2: 释放旧 URL + 创建新 Blob URL（用于预览）
  if (imagePreviewUrl.value) URL.revokeObjectURL(imagePreviewUrl.value)
  imagePreviewUrl.value = URL.createObjectURL(file.raw as File)
}

function handleFileRemove() {
  imageFile.value = null
  if (imagePreviewUrl.value) {
    URL.revokeObjectURL(imagePreviewUrl.value)
    imagePreviewUrl.value = null
  }
}

function clearAll() {
  query.value = ''
  equipmentModel.value = ''
  fileList.value = []
  imageFile.value = null
  if (imagePreviewUrl.value) {
    URL.revokeObjectURL(imagePreviewUrl.value)
    imagePreviewUrl.value = null
  }
  result.value = null
  errorState.value = null
  rating.value = 0
  feedback.value = ''
  expandedHits.value = new Set()
}

async function handleSearch() {
  if (!canSearch.value) return

  // ENT-4: 重置状态
  loading.value = true
  errorState.value = null
  result.value = null

  try {
    let resp: RetrievalResponse
    if (imageFile.value) {
      // 多模态检索
      const formData = new FormData()
      formData.append('query', query.value || '请分析这张故障图片')
      if (equipmentModel.value) formData.append('equipment_model', equipmentModel.value)
      formData.append('image', imageFile.value)
      formData.append('top_k', String(topK.value))
      resp = await retrieveMultimodal(formData)
    } else {
      // 纯文本检索
      resp = await retrieveByText({
        query: query.value,
        equipment_model: equipmentModel.value || undefined,
        top_k: topK.value,
      })
    }
    result.value = resp
    // 默认展开前 3 条命中
    expandedHits.value = new Set(
      (resp.hits || []).slice(0, 3).map((h) => h.chunk_id),
    )
  } catch (e: any) {
    // ENT-4: 错误状态结构化（不靠 ElMessage 一把梭）
    const status = e?.response?.status
    const detail = e?.response?.data?.detail || e?.message || '未知错误'
    if (status === 503) {
      errorState.value = {
        code: 503,
        title: '检索服务暂时不可用',
        detail: detail + '（可稍后重试，或检查后端 Milvus 服务）',
      }
    } else if (status === 422 || status === 400) {
      errorState.value = { code: status, title: '参数不合法', detail }
    } else if (!status) {
      errorState.value = {
        code: 0,
        title: '网络异常',
        detail: '无法连接到后端服务，请检查网络或后端是否启动（localhost:8000）',
      }
    } else {
      errorState.value = { code: status || 500, title: '检索失败', detail }
    }
  } finally {
    loading.value = false
  }
}

async function submitFeedback() {
  if (!result.value || !rating.value) return
  feedbackSubmitting.value = true
  try {
    await submitFeedback({
      query: result.value.query,
      original_answer: result.value.answer,
      correction: feedback.value,
      rating: rating.value,
    })
    ElMessage.success('反馈已提交')
    feedback.value = ''
    rating.value = 0
  } catch (e: any) {
    ElMessage.error('反馈提交失败：' + (e?.message || '未知错误'))
  } finally {
    feedbackSubmitting.value = false
  }
}

// ============================================================
// ENT-1: 导出当前检索结果（下拉命令统一处理）
// ============================================================
function buildResultMeta(): Record<string, string> {
  if (!result.value) return {}
  return {
    '问题': result.value.query,
    '设备型号': equipmentModel.value || '（未指定）',
    '模型': result.value.model,
    '耗时': `${result.value.latency_ms} ms`,
    '命中数': `${result.value.hits.length}`,
    '导出时间': new Date().toLocaleString('zh-CN'),
  }
}

function buildResultFilename(): string {
  return timestampFilename('retrieval')
}

async function onExportCommand(cmd: string) {
  if (!result.value) return
  if (cmd === 'pdf') {
    const answerEl = answerCardRef.value?.$el
    const hitsEl = filteredHits.value.length > 0 ? hitsCardRef.value?.$el : null
    const elements: HTMLElement[] = []
    if (answerEl) elements.push(answerEl)
    if (hitsEl) elements.push(hitsEl)
    if (elements.length === 0) {
      ElMessage.warning('暂无可导出的内容')
      return
    }
    await exportPDFFromElements(elements, buildResultFilename(), '检索结果报告')
  } else if (cmd === 'md') {
    const r = result.value
    const sections = [
      { heading: 'AI 解答', body: r.answer || '（无）' },
      ...(filteredHits.value.length > 0
        ? filteredHits.value.map((h, i) => ({
            heading: `[${String(i + 1).padStart(2, '0')}] ${hitDocTitle(h)} (相关度 ${(h.score * 100).toFixed(1)}%)`,
            body: [
              `- 文档类型：${docTypeName(h.doc_type)}`,
              `- 设备类型：${h.equipment_type || '—'}`,
              `- 设备型号：${h.equipment_model || '—'}`,
              `- 源文件：${h.source}`,
              '',
              '> ' + h.content.replace(/\n/g, '\n> '),
            ].join('\n'),
          }))
        : []),
    ]
    exportMarkdownBlob(
      { title: '检索结果报告', meta: buildResultMeta(), sections },
      buildResultFilename(),
    )
    ElMessage.success('Markdown 已导出')
  } else if (cmd === 'json') {
    exportJSON(result.value, buildResultFilename())
    ElMessage.success('JSON 已导出')
  }
}
</script>

<style lang="scss" scoped>
// ============================================================
// ENT-1: 页面 header（克制，不带渐变 / emoji）
// ============================================================
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  padding: 4px 0 20px;
  border-bottom: 1px solid var(--border-color);
  margin-bottom: 20px;
  flex-wrap: wrap;
  gap: 16px;
}
.page-title-block { flex: 1; min-width: 0; }
.page-title {
  margin: 0;
  font-size: 20px;
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
  letter-spacing: 0.2px;
}
.page-desc {
  margin: 4px 0 0;
  font-size: 13px;
  color: var(--text-muted);
}
.page-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--text-muted);
}
.meta-item { display: inline-flex; gap: 4px; align-items: baseline; }
.meta-label { color: var(--text-muted); }
.meta-value {
  color: var(--text-primary);
  font-weight: var(--font-weight-medium);
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 12px;
}

// ============================================================
// ENT-1: 主布局 — 左筛选 / 右结果
// ============================================================
.retrieval-layout {
  display: grid;
  grid-template-columns: 320px 1fr;
  gap: 20px;
  align-items: flex-start;
}
@media (max-width: 960px) {
  .retrieval-layout { grid-template-columns: 1fr; }
}
.retrieval-aside {
  position: sticky;
  top: 0;
}
.aside-card { background: var(--bg-secondary); }
.aside-header {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
}
.aside-clear { margin-left: auto; color: var(--text-muted); }

// ============================================================
// ENT-2: 表单块
// ============================================================
.form-block { margin-bottom: 20px; }
.form-block:last-of-type { margin-bottom: 0; }
.form-label {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 6px;
  font-size: 13px;
  color: var(--text-primary);
}
.form-label-text { font-weight: var(--font-weight-medium); }
.form-label-required {
  font-size: 11px;
  color: var(--danger);
  background: rgba(239, 68, 68, 0.08);
  padding: 1px 6px;
  border-radius: 3px;
}
.form-label-optional {
  font-size: 11px;
  color: var(--text-muted);
}
.form-label-value {
  font-size: 12px;
  color: var(--text-secondary);
  font-family: 'Consolas', 'Monaco', monospace;
}
.source-filter {
  display: flex;
  flex-wrap: wrap;
  gap: 0;
  :deep(.el-checkbox) { margin-right: 12px; }
}
.advanced-collapse {
  :deep(.el-collapse-item__header) {
    padding-left: 0;
    padding-right: 0;
    font-size: 13px;
    color: var(--text-secondary);
    border-bottom: none;
  }
  :deep(.el-collapse-item__wrap) { border-bottom: none; }
  :deep(.el-collapse-item__content) { padding-bottom: 0; }
}
.form-actions { margin-top: 24px; }
.search-btn { width: 100%; }

// ============================================================
// ENT-2: 图片上传（trigger 风格）
// ============================================================
.upload-trigger {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  width: 100%;
  height: 88px;
  background: var(--bg-primary);
  border: 1px dashed var(--border-color);
  border-radius: var(--radius-md);
  cursor: pointer;
  color: var(--text-secondary);
  font-size: 13px;
  transition: all var(--transition-fast);

  &:hover {
    border-color: var(--primary-color);
    color: var(--primary-color);
    background: rgba(var(--primary-rgb), 0.04);
  }
}
.upload-hint {
  font-size: 11px;
  color: var(--text-muted);
}
.upload-preview {
  width: 100%;
  height: 88px;
  border-radius: var(--radius-md);
  cursor: pointer;
  object-fit: cover;
}
.image-error {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;
  background: var(--bg-tertiary);
  color: var(--text-muted);
}

// ============================================================
// ENT-1: 主结果区
// ============================================================
.retrieval-main {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-width: 0;  // grid 子项防止溢出
}
.result-card {
  background: #ffffff;
  border: 1px solid var(--border-color);
}
.result-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}
.result-header-left { display: flex; align-items: center; gap: 8px; }
.result-header-right { display: flex; align-items: center; gap: 12px; font-size: 12px; color: var(--text-muted); }
.result-title {
  font-size: 15px;
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
}
.result-count {
  font-size: 12px;
  color: var(--text-muted);
  font-family: 'Consolas', 'Monaco', monospace;
}
.result-meta-item { display: inline-flex; gap: 4px; align-items: baseline; }
.result-meta-label { color: var(--text-muted); }
.result-meta-value {
  color: var(--text-primary);
  font-weight: var(--font-weight-medium);
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 12px;
}

// ============================================================
// ENT-3: 引用命中卡片（结构化）
// ============================================================
.hits-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.hit-item {
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  background: var(--bg-primary);
  transition: all var(--transition-fast);
  overflow: hidden;

  &:hover { border-color: rgba(var(--primary-rgb), 0.4); }

  &.expanded { border-color: rgba(var(--primary-rgb), 0.3); }

  // ENT-8: 引用标号点击后的高亮态
  &.highlighted {
    border-color: var(--primary-color);
    box-shadow: 0 0 0 3px rgba(var(--primary-rgb), 0.15);
    animation: hit-pulse 0.4s ease-out;
  }
}

@keyframes hit-pulse {
  0% { transform: scale(0.98); }
  50% { transform: scale(1.01); }
  100% { transform: scale(1); }
}
.hit-summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  cursor: pointer;
  user-select: none;
  gap: 16px;
}
.hit-summary-left {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 1;
  min-width: 0;
}
.hit-index {
  display: inline-block;
  min-width: 22px;
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 12px;
  color: var(--text-muted);
  font-weight: var(--font-weight-medium);
}
.hit-type-icon { color: var(--text-secondary); flex-shrink: 0; }
.hit-title {
  font-size: 14px;
  color: var(--text-primary);
  font-weight: var(--font-weight-medium);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.hit-summary-right {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
}
.hit-score-bar {
  width: 60px;
  height: 4px;
  background: var(--border-color);
  border-radius: 2px;
  overflow: hidden;
}
.hit-score-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--primary-color), var(--primary-light));
  transition: width var(--transition-base);
}
.hit-score-text {
  font-size: 12px;
  color: var(--text-secondary);
  font-family: 'Consolas', 'Monaco', monospace;
  min-width: 32px;
  text-align: right;
}
.hit-expand-icon { color: var(--text-muted); transition: transform var(--transition-fast); }
.hit-item.expanded .hit-expand-icon { transform: rotate(180deg); }

.hit-detail {
  padding: 0 16px 14px;
  border-top: 1px solid var(--border-light);
  margin-top: -1px;
}
.hit-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 12px 0 10px;
  font-size: 12px;
  color: var(--text-muted);
  flex-wrap: wrap;

  .el-divider--vertical { margin: 0 4px; }
}
.hit-meta-item { display: inline-flex; gap: 4px; }
.hit-meta-label { color: var(--text-muted); }
.hit-meta-value { color: var(--text-primary); font-weight: var(--font-weight-medium); }
.hit-source {
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 11px;
}
// PDF-A.7: 结构化元信息栏（聚群 A：页码 + 章节 chip）
.hit-structured-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  padding: 8px 12px;
  margin-bottom: 10px;
  background: linear-gradient(135deg, var(--bg-primary), var(--bg-secondary));
  border-left: 3px solid var(--primary-color);
  border-radius: var(--radius-sm);
}

// PDF-B.7: 视觉理解增强框
.hit-vl-box {
  margin-bottom: 10px;
  padding: 10px 12px;
  background: linear-gradient(135deg, #f0f9ff 0%, #f0fdf4 100%);
  border-left: 3px solid var(--success-color, #10b981);
  border-radius: var(--radius-sm);
  font-size: var(--font-size-sm);
}
.vl-box-head {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--success-color, #059669);
  font-weight: var(--font-weight-semibold);
  margin-bottom: 4px;
}
.vl-box-title { font-size: var(--font-size-sm); }
.vl-box-desc {
  color: var(--text-secondary);
  line-height: 1.6;
  margin-bottom: 6px;
}
.vl-box-facts {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
.vl-fact-tag { font-size: 11px; }
.hit-content {
  padding: 12px;
  background: var(--bg-secondary);
  border-radius: var(--radius-sm);
  color: var(--text-secondary);
  line-height: 1.7;
  font-size: 13px;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 200px;
  overflow-y: auto;
}
.hit-actions {
  display: flex;
  gap: 8px;
  margin-top: 10px;
  justify-content: flex-end;
}

// ============================================================
// ENT-3: 答案内容
// ============================================================
.answer-content {
  font-size: 14px;
  line-height: 1.75;
  color: var(--text-primary);

  // 段落
  :deep(p) {
    margin: 10px 0;
    &:first-child { margin-top: 0; }
    &:last-child { margin-bottom: 0; }
  }

  // 标题（参考 Notion / 飞书文档）
  :deep(h1) {
    margin: 24px 0 12px;
    font-size: 20px;
    font-weight: var(--font-weight-semibold);
    color: var(--text-primary);
    padding-bottom: 6px;
    border-bottom: 1px solid var(--border-color);
  }
  :deep(h2) {
    margin: 20px 0 10px;
    font-size: 17px;
    font-weight: var(--font-weight-semibold);
    color: var(--text-primary);
    display: flex;
    align-items: center;
    gap: 6px;
    &::before {
      content: '';
      display: inline-block;
      width: 3px;
      height: 14px;
      background: var(--primary-color);
      border-radius: 2px;
    }
  }
  :deep(h3) {
    margin: 16px 0 8px;
    font-size: 15px;
    font-weight: var(--font-weight-semibold);
    color: var(--text-primary);
  }
  :deep(h4), :deep(h5), :deep(h6) {
    margin: 12px 0 6px;
    font-size: 14px;
    font-weight: var(--font-weight-semibold);
    color: var(--text-secondary);
  }

  // 列表
  :deep(ul), :deep(ol) {
    margin: 10px 0;
    padding-left: 24px;
  }
  :deep(li) {
    margin: 4px 0;
    line-height: 1.7;
  }
  :deep(li::marker) { color: var(--text-muted); }

  // 引用
  :deep(blockquote) {
    margin: 12px 0;
    padding: 8px 14px;
    border-left: 3px solid var(--primary-color);
    background: var(--bg-secondary);
    color: var(--text-secondary);
    border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
  }

  // 代码
  :deep(pre) {
    background: var(--bg-secondary);
    padding: 12px 14px;
    border-radius: var(--radius-sm);
    overflow-x: auto;
    margin: 10px 0;
    border: 1px solid var(--border-light);
  }
  :deep(code) {
    background: var(--bg-secondary);
    padding: 2px 6px;
    border-radius: 3px;
    color: var(--primary-color);
    font-family: 'Consolas', 'Monaco', monospace;
    font-size: 0.9em;
  }
  :deep(pre code) {
    background: transparent;
    padding: 0;
    color: var(--text-primary);
  }

  :deep(strong) { color: var(--primary-color); font-weight: var(--font-weight-semibold); }
  :deep(em) { color: var(--text-secondary); font-style: italic; }

  // 表格
  :deep(table) {
    border-collapse: collapse;
    width: 100%;
    margin: 12px 0;
    font-size: 13px;
    th, td {
      border: 1px solid var(--border-color);
      padding: 6px 10px;
      text-align: left;
    }
    th {
      background: var(--bg-secondary);
      font-weight: var(--font-weight-semibold);
    }
  }

  // 引用标号【1】【2】可点击
  :deep(.ref-link) {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 22px;
    height: 18px;
    padding: 0 6px;
    margin: 0 2px;
    background: rgba(var(--primary-rgb), 0.08);
    color: var(--primary-color);
    border-radius: 4px;
    font-size: 11px;
    font-weight: var(--font-weight-semibold);
    cursor: pointer;
    transition: all var(--transition-fast);
    text-decoration: none;
    vertical-align: 1px;

    &:hover {
      background: var(--primary-color);
      color: #fff;
      transform: translateY(-1px);
    }
  }
}

// ============================================================
// ENT-4: 状态展示
// ============================================================
.empty-state {
  background: #ffffff;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: 64px 24px;
  text-align: center;
}
.empty-tips {
  display: inline-flex;
  flex-direction: column;
  gap: 12px;
  margin-top: 24px;
  text-align: left;
}
.empty-tip-item {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 13px;
  color: var(--text-secondary);
}
.tip-num {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: var(--bg-tertiary);
  color: var(--text-muted);
  font-size: 12px;
  font-weight: var(--font-weight-medium);
}

.loading-state {
  background: #ffffff;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: 24px;
}

.error-state {
  background: #ffffff;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: 24px;
}

.no-hits-card {
  text-align: center;
}

// ============================================================
// 反馈
// ============================================================
.feedback-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 12px;
}
.feedback-input { margin-top: 4px; }

.ml-sm { margin-left: 8px; }
</style>
