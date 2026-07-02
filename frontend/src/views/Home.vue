<template>
  <div class="chat-page">
    <div v-if="messages.length === 0" class="welcome-area">
      <div class="welcome-glass stagger">
        <div class="logo-big">
          <el-icon :size="56" color="var(--primary-color)"><Tools /></el-icon>
        </div>
        <h1 class="welcome-title">A1 设备检修智能助手</h1>
        <p class="welcome-subtitle">基于多模态大模型 · 5 模型协同 · 国产化部署</p>

        <div class="suggestions">
          <div v-for="group in suggestionGroups" :key="group.label" class="suggest-group">
            <p class="suggest-label">
              <el-icon><component :is="group.icon" /></el-icon>
              {{ group.label }}
            </p>
            <el-space wrap :size="10">
              <div
                v-for="s in group.items"
                :key="s"
                class="suggestion-card"
                @click="quickAsk(s)"
              >
                <span>{{ s }}</span>
              </div>
            </el-space>
          </div>
        </div>

        <div class="knowledge-strip">
          <el-icon class="ks-icon"><Files /></el-icon>
          <span class="ks-text">
            <strong>已上传 {{ manualsCount }} 份知识</strong>
            <span class="ks-sub">（含 PDF / Word / Markdown，RAG 立即可搜）</span>
          </span>
          <el-button text type="primary" @click="quickAsk('焊接机器人飞溅大怎么处理')">
            <el-icon><Promotion /></el-icon>
            试问
          </el-button>
        </div>
      </div>
    </div>

    <div v-else ref="messagesRef" class="messages-area">
      <template v-for="(msg, idx) in messages" :key="idx">
        <div class="message-row fade-in" :class="msg.role">
          <div v-if="msg.role === 'user'" class="user-msg">
            <div class="bubble user-bubble">
              <div class="bubble-text">{{ msg.content }}</div>
              <div v-if="shouldShowTimestamp(idx)" class="bubble-time">
                {{ formatTime(msg.timestamp) }}
              </div>
            </div>
            <el-avatar :size="36" class="avatar user-avatar">
              {{ userInitial }}
            </el-avatar>
          </div>
          <div v-else class="ai-msg">
            <el-avatar :size="36" class="avatar ai-avatar">
              <el-icon><Cpu /></el-icon>
            </el-avatar>
            <div class="bubble ai-bubble">
              <div v-if="msg.loading" class="loading-bubble">
                <span class="dot"></span><span class="dot"></span><span class="dot"></span>
                <span class="loading-text">{{ msg.loadingText || '正在思考...' }}</span>
              </div>
              <template v-else>
                <div v-if="msg.intent" class="intent-row">
                  <el-tag :type="msg.intent === 'maintenance' ? 'warning' : 'info'" effect="dark" size="small" round>
                    <el-icon><Tools v-if="msg.intent === 'maintenance'" /><ChatLineRound v-else /></el-icon>
                    {{ msg.intent === 'maintenance' ? '检修问题' : '闲聊对话' }}
                  </el-tag>
                  <el-tag v-if="msg.used_rag" type="success" effect="dark" size="small" round>
                    <el-icon><DataAnalysis /></el-icon> 知识库增强
                  </el-tag>
                  <span class="meta-text">{{ msg.model }} · {{ msg.latency_ms }}ms</span>
                </div>
                <div class="bubble-text markdown-body" v-html="throttledRender(idx, msg.content)"></div>
                <div v-if="msg.sources && msg.sources.length > 0" class="sources-section">
                  <div class="sources-title" @click="toggleSources(idx)">
                    <el-icon><Document /></el-icon>
                    <span>参考来源（{{ msg.sources.length }}）</span>
                    <el-icon class="toggle-icon" :class="{ open: msg.sourcesOpen }">
                      <ArrowDown />
                    </el-icon>
                  </div>
                  <div v-show="msg.sourcesOpen" class="sources-list">
                    <div v-for="(src, sidx) in msg.sources" :key="sidx" class="source-item">
                      <div class="source-header">
                        <el-tag size="small" effect="plain" type="primary">{{ src.equipment_type || '通用' }}</el-tag>
                        <el-tag v-if="src.equipment_model" size="small" effect="plain">{{ src.equipment_model }}</el-tag>
                        <el-tag size="small" type="success" effect="plain">相关度 {{ (src.score).toFixed(2) }}</el-tag>
                      </div>
                      <div class="source-content">{{ src.content }}</div>
                      <div class="source-meta">{{ src.source }}</div>
                    </div>
                  </div>
                </div>
              </template>
            </div>
          </div>
        </div>
      </template>
    </div>

    <div class="input-area">
      <div class="input-container">
        <el-input
          v-model="input"
          type="textarea"
          :autosize="{ minRows: 1, maxRows: 6 }"
          placeholder="输入你的问题，Enter 发送，Shift+Enter 换行..."
          :disabled="loading"
          @keydown.enter.exact.prevent="send"
        />
        <div class="input-toolbar">
          <div class="input-hint">
            <el-icon><InfoFilled /></el-icon>
            <span>系统会智能识别：检修问题自动调取知识库 · 闲聊直接对话</span>
          </div>
          <div class="input-actions">
            <el-button v-if="messages.length > 0" text :disabled="loading" @click="clearAll">
              <el-icon><Delete /></el-icon> 清空
            </el-button>
            <el-button type="primary" :loading="loading" :disabled="!input.trim()" @click="send">
              <el-icon><Promotion /></el-icon> 发送
            </el-button>
          </div>
        </div>
      </div>
      <div class="disclaimer">AI 生成内容仅供参考，检修操作请遵循设备 SOP 与安全规程</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import {
  Tools, ChatLineRound, Cpu, DataAnalysis, Document,
  ArrowDown, Promotion, Delete, InfoFilled, SetUp, Sunny, Files,
} from '@element-plus/icons-vue'
import { renderSafeMarkdownCached } from '@/utils/markdown'
import { sendChat, streamChat, type ChatTurnMessage, type ChatSource } from '@/api/chat'
import { useAuthStore } from '@/stores/auth'
import { useChatHistoryStore } from '@/stores/chatHistory'

const auth = useAuthStore()
const chatHistory = useChatHistoryStore()
const userInitial = auth.user?.display_name?.charAt(0) || 'U'

const input = ref('')
const loading = ref(false)
const messages = computed<any[]>(() => chatHistory.activeMessages)
const messagesRef = ref<HTMLElement | null>(null)
const manualsCount = ref(0)
let streamHandle: { abort: () => void } | null = null

const suggestionGroups = [
  {
    label: '故障诊断', icon: 'SetUp',
    items: [
      'FANUC 机器人报 SRVO-023 怎么处理？',
      '焊接机器人导电嘴粘连怎么解决？',
      'AGV 激光雷达脏污如何清洁？',
      '冲压机离合器打滑的常见原因？',
    ],
  },
  {
    label: '闲聊试试', icon: 'Sunny',
    items: [
      '你好，请介绍一下你自己',
      '上海今天天气怎么样？',
    ],
  },
]

const loadingTexts = ['正在识别意图...', '正在检索知识库...', '正在组织语言...', '正在思考...']
let loadingTextIdx = 0
let loadingTextTimer: number | null = null

function startLoadingTextRotation(convId: string) {
  loadingTextIdx = 0
  chatHistory.updateMessageIn(convId, (m: any) => {
    if (m.loading) m.loadingText = loadingTexts[0]
  })
  if (loadingTextTimer) clearInterval(loadingTextTimer)
  loadingTextTimer = window.setInterval(() => {
    loadingTextIdx = (loadingTextIdx + 1) % loadingTexts.length
    chatHistory.updateMessageIn(convId, (m: any) => {
      if (m.loading) m.loadingText = loadingTexts[loadingTextIdx]
    })
  }, 2000)
}

function stopLoadingTextRotation() {
  if (loadingTextTimer) {
    clearInterval(loadingTextTimer)
    loadingTextTimer = null
  }
}

function quickAsk(text: string) {
  input.value = text
  send()
}

function scrollToBottom() {
  nextTick(() => {
    if (messagesRef.value) {
      messagesRef.value.scrollTop = messagesRef.value.scrollHeight
    }
  })
}

function shouldShowTimestamp(idx: number): boolean {
  if (idx === 0) return true
  const cur = messages.value[idx]
  const prev = messages.value[idx - 1]
  if (!cur || !prev) return true
  if (cur.role !== prev.role) return true
  if (cur.timestamp && prev.timestamp) {
    return new Date(cur.timestamp).getMinutes() !== new Date(prev.timestamp).getMinutes()
  }
  return false
}

function formatTime(iso?: string): string {
  if (!iso) return ''
  const d = new Date(iso)
  const now = new Date()
  const sameDay = d.toDateString() === now.toDateString()
  if (sameDay) {
    return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
  }
  return `${d.getMonth() + 1}/${d.getDate()} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

// 节流 markdown 渲染：流式时每 120ms 才重新 render（避免每 chunk 都重跑 marked + DOMPurify）
const RENDER_THROTTLE_MS = 120
const lastRenderTime = ref(0)
const cachedRender = ref(new Map<number, string>())

function throttledRender(idx: number, content: string): string {
  // 流式时（msg.loading === true）：每 120ms 才 render（但立即返回旧值保证 UI 响应）
  // 流结束（msg.loading === false）：立即 render
  const isStreaming = messages.value[idx]?.loading
  const now = Date.now()
  const cached = cachedRender.value.get(idx)
  if (cached && isStreaming && (now - lastRenderTime.value < RENDER_THROTTLE_MS)) {
    return cached
  }
  const html = renderSafeMarkdownCached(content)
  cachedRender.value.set(idx, html)
  lastRenderTime.value = now
  return html
}

async function send() {
  const text = input.value.trim()
  if (!text || loading.value) return

  if (streamHandle) { streamHandle.abort(); streamHandle = null }
  const convId = chatHistory.activeId || chatHistory.create().id

  chatHistory.appendMessage({ role: 'user', content: text, timestamp: new Date().toISOString() } as any)
  input.value = ''

  chatHistory.appendMessage({
    role: 'assistant',
    content: '',
    loading: true,
    loadingText: loadingTexts[0],
    timestamp: new Date().toISOString(),
  } as any)
  loading.value = true
  scrollToBottom()
  startLoadingTextRotation(convId)

  const completed = messages.value.filter((m: any) => !m.loading)
  const history: ChatTurnMessage[] = completed
    .slice(Math.max(0, completed.length - 13), completed.length - 1)
    .map((m: any) => ({ role: m.role, content: m.content }))

  streamHandle = streamChat(
    { message: text, history },
    {
      onIntent: (data) => {
        chatHistory.updateMessageIn(convId, (m: any) => {
          m.intent = data.intent
          m.reason = data.reason
          m.loadingText = data.intent === 'maintenance' ? '正在检索知识库...' : loadingTexts[loadingTextIdx]
        })
      },
      onSources: (data) => {
        chatHistory.updateMessageIn(convId, (m: any) => {
          m.sources = data.sources
          m.used_rag = data.used_rag
          m.sourcesOpen = (data.sources?.length ?? 0) > 0
        })
      },
      onDelta: (chunk) => {
        chatHistory.updateMessageIn(convId, (m: any) => {
          if (m.loading) {
            m.loading = false
            m.loadingText = ''
            stopLoadingTextRotation()
          }
          m.content = (m.content || '') + chunk
        })
        scrollToBottom()
      },
      onDone: (data) => {
        chatHistory.updateMessageIn(convId, (m: any) => {
          m.model = data.model
          m.latency_ms = data.latency_ms
        })
        loading.value = false
        streamHandle = null
        stopLoadingTextRotation()
        scrollToBottom()
      },
      onError: (msg) => {
        chatHistory.updateMessageIn(convId, (m: any) => {
          m.loading = false
          m.loadingText = ''
          m.content = '❌ 请求失败：' + msg + '\n\n请检查后端服务是否正常运行。'
        })
        input.value = text
        ElMessage.error('对话请求失败')
        loading.value = false
        streamHandle = null
        stopLoadingTextRotation()
      },
    },
  )
}

function toggleSources(idx: number) {
  const m = messages.value[idx]
  if (m) m.sourcesOpen = !m.sourcesOpen
}

function clearAll() {
  if (streamHandle) { streamHandle.abort(); streamHandle = null }
  stopLoadingTextRotation()
  chatHistory.clearActive()
  ElMessage.success('已清空当前对话')
}

// onMounted 空函数已删除（原内容只有注释）

onUnmounted(() => {
  if (streamHandle) {
    streamHandle.abort()
    streamHandle = null
  }
  stopLoadingTextRotation()
})
</script>

<style lang="scss" scoped>
.chat-page {
  position: relative;
  width: 100%;
  height: calc(100vh - 56px - 48px);
  display: flex;
  flex-direction: column;
  max-width: 1000px;
  margin: 0 auto;
  padding: 0;
}

.welcome-area {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
}

.welcome-glass {
  position: relative;
  text-align: center;
  max-width: 720px;
  padding: 56px 64px;
  background: #ffffff;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-xl);
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04), 0 8px 24px rgba(15, 23, 42, 0.06);
  overflow: hidden;
}

.logo-big {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 96px;
  height: 96px;
  margin: 0 auto 24px;
  background: var(--bg-secondary);
  border: 2px solid var(--primary-color);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-glow);
}

.welcome-title {
  font-size: var(--font-size-3xl);
  font-weight: var(--font-weight-bold);
  color: var(--text-primary);
  margin: 0 0 8px;
  letter-spacing: 1px;
}

.welcome-subtitle {
  font-size: var(--font-size-md);
  color: var(--text-secondary);
  margin: 0 0 40px;
}

.suggestions {
  text-align: left;
  max-width: 640px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.suggest-group {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.suggest-label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-medium);
  color: var(--primary-color);
  margin: 0;
}

.suggestion-card {
  display: inline-flex;
  align-items: center;
  padding: 10px 16px;
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  color: var(--text-primary);
  font-size: var(--font-size-sm);
  cursor: pointer;
  transition: all var(--transition-fast);

  &:hover {
    border-color: var(--primary-color);
    transform: translateY(-1px);
    box-shadow: var(--shadow-glow);
  }
}

.knowledge-strip {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 20px;
  padding: 10px 14px;
  background: rgba(var(--primary-rgb), 0.06);
  border: 1px solid rgba(var(--primary-rgb), 0.2);
  border-radius: var(--radius-lg);
  font-size: var(--font-size-sm);
}

.ks-icon {
  font-size: 18px;
  color: var(--primary-color);
  flex-shrink: 0;
}

.ks-text {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  flex: 1;
  min-width: 0;

  strong { color: var(--text-primary); font-weight: var(--font-weight-semibold); }
  .ks-sub { color: var(--text-muted); font-size: 12px; margin-top: 2px; }
}

.suggest-icon {
  color: var(--primary-color);
  font-size: 16px;
}

.messages-area {
  flex: 1;
  overflow-y: auto;
  padding: 24px 0 0;
  scroll-behavior: smooth;

  &::-webkit-scrollbar { width: 6px; }
}

.message-row {
  margin-bottom: 24px;
  display: flex;

  &.user { justify-content: flex-end; }
  &.assistant { justify-content: flex-start; }
}

.user-msg, .ai-msg {
  display: flex;
  gap: 12px;
  max-width: 85%;
  align-items: flex-start;
}

.user-msg { flex-direction: row-reverse; }

.avatar {
  flex-shrink: 0;
  font-weight: var(--font-weight-semibold);
}

.user-avatar {
  background: var(--primary-color);
  color: var(--text-inverse);
}

.ai-avatar {
  background: var(--bg-tertiary);
  color: var(--primary-color);
  border: 1px solid var(--primary-color);
}

.bubble {
  padding: 12px 16px;
  border-radius: var(--radius-lg);
  line-height: 1.6;
  word-break: break-word;
}

.user-bubble {
  background: var(--primary-color);
  color: var(--text-inverse);
  border-bottom-right-radius: 4px;
}

.ai-bubble {
  background: var(--bg-secondary);
  color: var(--text-primary);
  border: 1px solid var(--border-color);
  border-bottom-left-radius: 4px;
  width: 100%;
}

.bubble-text {
  font-size: var(--font-size-md);
  white-space: pre-wrap;
  word-break: break-word;
}

.bubble-time {
  font-size: var(--font-size-xs);
  color: var(--text-muted);
  margin-top: 6px;
  opacity: 0.7;
}

.user-bubble .bubble-time {
  color: rgba(255, 255, 255, 0.7);
}

.markdown-body {
  :deep(p) { margin: 8px 0; }
  :deep(ul), :deep(ol) { margin: 8px 0; padding-left: 24px; }
  :deep(li) { margin: 4px 0; }
  :deep(strong) { color: var(--primary-color); font-weight: var(--font-weight-semibold); }
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
}

.loading-bubble {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 120px;
  color: var(--text-secondary);
}

.dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--primary-color);
  animation: bounce 1.4s infinite ease-in-out both;

  &:nth-child(1) { animation-delay: -0.32s; }
  &:nth-child(2) { animation-delay: -0.16s; }
}

@keyframes bounce {
  0%, 80%, 100% { transform: scale(0); }
  40% { transform: scale(1); }
}

.loading-text { font-size: var(--font-size-sm); margin-left: 4px; }

.intent-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
  padding-bottom: 10px;
  border-bottom: 1px dashed var(--border-color);
}

.meta-text {
  font-size: var(--font-size-xs);
  color: var(--text-muted);
  margin-left: auto;
}

.sources-section {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--border-color);
}

.sources-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: var(--font-size-sm);
  color: var(--primary-color);
  cursor: pointer;
  user-select: none;
  font-weight: var(--font-weight-medium);

  &:hover { color: var(--primary-light); }
}

.toggle-icon {
  transition: transform var(--transition-fast);

  &.open { transform: rotate(180deg); }
}

.sources-list {
  margin-top: 8px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.source-item {
  padding: 10px 12px;
  background: var(--bg-tertiary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  font-size: var(--font-size-sm);
}

.source-header { display: flex; gap: 6px; margin-bottom: 6px; flex-wrap: wrap; }
.source-content { color: var(--text-secondary); line-height: 1.6; white-space: pre-wrap; margin: 4px 0; }
.source-meta { color: var(--text-muted); font-size: var(--font-size-xs); margin-top: 4px; }

.input-area {
  flex-shrink: 0;
  padding: 12px 0 8px;
  background: var(--bg-primary);
  border-top: 1px solid var(--border-color);
  position: relative;
  z-index: 10;
}

.input-container {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  padding: 12px 16px;
  transition: border-color var(--transition-fast);

  &:focus-within {
    border-color: var(--primary-color);
    box-shadow: 0 0 0 2px rgba(var(--primary-rgb), 0.2);
  }

  :deep(.el-textarea__inner) {
    background: transparent !important;
    border: none !important;
    color: var(--text-primary) !important;
    box-shadow: none !important;
    resize: none;
    padding: 0;
    font-size: var(--font-size-md);
  }
}

.input-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 8px;
  gap: 12px;
}

.input-hint {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: var(--font-size-xs);
  color: var(--text-muted);
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.input-actions {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}

.disclaimer {
  text-align: center;
  font-size: var(--font-size-xs);
  color: var(--text-muted);
  margin-top: 8px;
}

@media (max-width: 768px) {
  .user-msg, .ai-msg { max-width: 95%; }
  .welcome-title { font-size: 24px; }
}
</style>
