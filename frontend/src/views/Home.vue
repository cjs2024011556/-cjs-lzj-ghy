<template>
  <div class="chat-page" :class="{ 'has-messages': messages.length > 0 }">
    <!-- ===== 新对话：ChatGPT 极简风格（仅输入框 + 建议） ===== -->
    <div v-if="messages.length === 0" class="welcome-stage">
      <h1 class="welcome-prompt">有什么想问的，尽管问</h1>

      <!-- 居中输入框 -->
      <div class="input-container center-input">
        <div class="input-row">
          <el-input
            v-model="input"
            type="textarea"
            :autosize="{ minRows: 1, maxRows: 6 }"
            placeholder="给 A1 设备检修助手发消息"
            :disabled="loading"
            @keydown.enter.exact.prevent="send"
          />
          <!-- 思考中：停止按钮（ChatGPT 风格黑色圆 + 白方块） -->
          <el-button
            v-if="loading"
            class="send-btn stop-btn"
            circle
            @click="stopStream"
          >
            <span class="stop-square"></span>
          </el-button>
          <!-- 正常：发送按钮（蓝色圆箭头） -->
          <el-button
            v-else
            class="send-btn"
            type="primary"
            circle
            :disabled="!input.trim()"
            @click="send"
          >
            <el-icon :size="18"><Promotion /></el-icon>
          </el-button>
        </div>
      </div>

      <!-- 建议按钮（输入框下方一行） -->
      <div class="suggestions">
        <div
          v-for="s in suggestionItems"
          :key="s"
          class="suggestion-chip"
          @click="quickAsk(s)"
        >
          <span>{{ s }}</span>
        </div>
      </div>

      <!-- 免责声明（welcome-stage 也有，新对话时也能看到） -->
      <div class="disclaimer">AI 生成内容仅供参考，检修操作请遵循设备 SOP 与安全规程</div>
    </div>

    <!-- ===== 已有消息：消息列表 + 底部输入框 ===== -->
    <template v-else>
      <div ref="messagesRef" class="messages-area">
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

      <!-- 底部输入区（仅已有消息时显示） -->
      <div class="input-area bottom">
        <div class="input-container">
          <div class="input-row">
            <el-input
              v-model="input"
              type="textarea"
              :autosize="{ minRows: 1, maxRows: 6 }"
              placeholder="输入你的问题，Enter 发送，Shift+Enter 换行..."
              :disabled="loading"
              @keydown.enter.exact.prevent="send"
            />
            <!-- 思考中：停止按钮（ChatGPT 风格黑色圆 + 白方块） -->
            <el-button
              v-if="loading"
              class="send-btn stop-btn"
              circle
              @click="stopStream"
            >
              <span class="stop-square"></span>
            </el-button>
            <!-- 正常：发送按钮 -->
            <el-button
              v-else
              class="send-btn"
              type="primary"
              circle
              :disabled="!input.trim()"
              @click="send"
            >
              <el-icon :size="18"><Promotion /></el-icon>
            </el-button>
          </div>
        </div>
        <div class="disclaimer">AI 生成内容仅供参考，检修操作请遵循设备 SOP 与安全规程</div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import {
  Tools, ChatLineRound, Cpu, DataAnalysis, Document,
  ArrowDown, Promotion,
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
let streamHandle: { abort: () => void } | null = null

// ChatGPT 风格：扁平化的建议列表（无分组标签）
const suggestionItems = [
  'FANUC 机器人报 SRVO-023 怎么处理？',
  '焊接机器人导电嘴粘连怎么解决？',
  'AGV 激光雷达脏污如何清洁？',
  '冲压机离合器打滑的常见原因？',
  '你好，请介绍一下你自己',
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
        chatHistory.clearStreamAbort()  // 流结束，注销 store 中的句柄引用
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
        chatHistory.clearStreamAbort()
        stopLoadingTextRotation()
      },
    },
  )
  // 注册到 store：用户切换时（auth.setUser）会自动 abort 这个流
  chatHistory.setStreamAbort(() => streamHandle?.abort())
}

function toggleSources(idx: number) {
  const m = messages.value[idx]
  if (m) m.sourcesOpen = !m.sourcesOpen
}

// ChatGPT 风格：停止生成（用户主动中断当前流式响应）
function stopStream() {
  if (streamHandle) {
    streamHandle.abort()
    streamHandle = null
  }
  chatHistory.clearStreamAbort()  // 注销 store 中注册的 abort 句柄
  // 删除最后一条 loading 状态的 assistant 消息（"作废"这条回复）
  const conv = chatHistory.activeConversation
  if (conv && conv.messages.length > 0) {
    const last = conv.messages[conv.messages.length - 1]
    if (last && last.loading) {
      conv.messages.pop()
    }
  }
  loading.value = false
  stopLoadingTextRotation()
  ElMessage.info('已停止生成')
}

// onMounted 空函数已删除（原内容只有注释）

onUnmounted(() => {
  if (streamHandle) {
    streamHandle.abort()
    streamHandle = null
  }
  chatHistory.clearStreamAbort()  // Home 卸载时注销句柄
  stopLoadingTextRotation()
})
</script>

<style lang="scss" scoped>
.chat-page {
  position: relative;
  width: 100%;
  height: 100%;  // 顶栏已砍掉，整屏填充
  display: flex;
  flex-direction: column;
  max-width: 768px;  // ChatGPT 风格：输入框宽度限制（约 768px，居中）
  margin: 0 auto;
  padding: 0;
}

// 新对话：ChatGPT 极简居中布局
.welcome-stage {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 24px;
  gap: 24px;
}

// ChatGPT 风格引导语（一行短句，无 logo 无副标题）
.welcome-prompt {
  font-size: 28px;
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
  margin: 0;
  text-align: center;
  letter-spacing: 0.5px;
}

// 居中输入框（welcome-stage 内部）
.input-container.center-input {
  width: 100%;
  background: #ffffff;
  border: 1px solid var(--border-color);
  border-radius: 28px;
  padding: 8px 12px 8px 16px;
  box-shadow: 0 2px 12px rgba(15, 23, 42, 0.06);
  transition: all var(--transition-fast);

  &:focus-within {
    border-color: var(--primary-color);
    box-shadow: 0 0 0 2px rgba(var(--primary-rgb), 0.15), 0 6px 16px rgba(15, 23, 42, 0.08);
  }
}

// ChatGPT 风格建议按钮（圆角 pill）
.suggestions {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 10px;
  max-width: 720px;
}

.suggestion-chip {
  display: inline-flex;
  align-items: center;
  padding: 8px 16px;
  background: transparent;
  border: 1px solid var(--border-color);
  border-radius: 20px;
  color: var(--text-secondary);
  font-size: var(--font-size-sm);
  cursor: pointer;
  transition: all var(--transition-fast);

  &:hover {
    border-color: var(--primary-color);
    color: var(--primary-color);
    background: rgba(var(--primary-rgb), 0.04);
  }
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

  // ChatGPT 风格滚动条：细、淡、半透明，hover 时变深
  &::-webkit-scrollbar { width: 6px; }
  &::-webkit-scrollbar-track { background: transparent; }
  &::-webkit-scrollbar-thumb {
    background: rgba(0, 0, 0, 0.15);
    border-radius: 3px;
    transition: background var(--transition-fast);
  }
  &::-webkit-scrollbar-thumb:hover { background: rgba(0, 0, 0, 0.3); }
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

.user-msg { justify-content: flex-end; }

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

// 底部输入区（已有消息时）— ChatGPT 风格
.input-area {
  flex-shrink: 0;
  padding: 16px 0 8px;
  background: transparent;
  position: relative;
  z-index: 10;
}

.input-container {
  background: #ffffff;
  border: 1px solid var(--border-color);
  border-radius: 28px;
  padding: 8px 12px 8px 16px;
  box-shadow: 0 2px 12px rgba(15, 23, 42, 0.06);
  transition: all var(--transition-fast);

  &:focus-within {
    border-color: var(--primary-color);
    box-shadow: 0 0 0 2px rgba(var(--primary-rgb), 0.15), 0 6px 16px rgba(15, 23, 42, 0.08);
  }

  :deep(.el-textarea__inner) {
    background: transparent !important;
    border: none !important;
    color: var(--text-primary) !important;
    box-shadow: none !important;
    resize: none;
    padding: 4px 0;
    font-size: 16px;
    line-height: 24px;
    min-height: 24px !important;
  }
}

// ChatGPT 风格：textarea 在左 + 圆形发送按钮在右，跟随增高贴底
.input-row {
  display: flex;
  align-items: flex-end;
  gap: 8px;

  :deep(.el-textarea) {
    flex: 1;
    min-width: 0;  // 防止 textarea 内容过长撑破 flex
  }
}

.send-btn {
  flex-shrink: 0;
  width: 32px;
  height: 32px;
  padding: 0;
}

.send-btn.stop-btn {
  background: var(--text-primary);
  border-color: var(--text-primary);
  color: #fff;

  &:hover {
    background: #1e293b;  // text-primary 的 hover 色（更深）
    border-color: #1e293b;
  }
}

// 停止按钮里的白色方块（ChatGPT 风格）
.stop-square {
  display: inline-block;
  width: 10px;
  height: 10px;
  background: #ffffff;
  border-radius: 2px;
}

.disclaimer {
  text-align: center;
  font-size: var(--font-size-xs);
  color: var(--text-muted);
  margin-top: 8px;
}

@media (max-width: 768px) {
  .user-msg, .ai-msg { max-width: 95%; }
}
</style>
