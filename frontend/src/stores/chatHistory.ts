/**
 * 对话历史 Store（ChatGPT 风格多对话管理）
 *
 * 特性：
 * - 最多 50 个对话，LRU 淘汰
 * - localStorage 持久化，debounce 500ms
 * - 第一条 user 消息作为对话标题
 * - 容量超限自动清理最旧
 */
import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'

const STORAGE_KEY = 'a1_chat_history'
const MAX_CONVERSATIONS = 50
const TITLE_MAX_LEN = 30

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  loading?: boolean
  loadingText?: string
  intent?: string
  reason?: string
  used_rag?: boolean
  sources?: any[]
  sourcesOpen?: boolean
  model?: string
  latency_ms?: number
}

export interface Conversation {
  id: string
  title: string
  messages: ChatMessage[]
  createdAt: string
  updatedAt: string
}

function uuid(): string {
  return 'c-' + Date.now().toString(36) + '-' + Math.random().toString(36).slice(2, 8)
}

function nowIso(): string {
  return new Date().toISOString()
}

function deriveTitle(messages: ChatMessage[]): string {
  const firstUser = messages.find((m) => m.role === 'user' && m.content.trim())
  if (!firstUser) return '新对话'
  const t = firstUser.content.replace(/\s+/g, ' ').trim()
  return t.length > TITLE_MAX_LEN ? t.slice(0, TITLE_MAX_LEN) + '…' : t
}

export const useChatHistoryStore = defineStore('chatHistory', () => {
  const conversations = ref<Conversation[]>([])
  const activeId = ref<string | null>(null)
  let saveTimer: number | null = null

  // ---- 计算属性 ----
  const activeConversation = computed<Conversation | null>(() => {
    if (!activeId.value) return null
    return conversations.value.find((c) => c.id === activeId.value) || null
  })

  const activeMessages = computed<ChatMessage[]>(() => {
    return activeConversation.value?.messages ?? []
  })

  const sortedConversations = computed<Conversation[]>(() => {
    return [...conversations.value].sort(
      (a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime(),
    )
  })

  // ---- 持久化 ----
  function save() {
    try {
      const data = JSON.stringify({
        conversations: conversations.value,
        activeId: activeId.value,
      })
      localStorage.setItem(STORAGE_KEY, data)
    } catch (e) {
      console.warn('对话历史保存失败:', e)
    }
  }

  function saveDebounced() {
    if (saveTimer) clearTimeout(saveTimer)
    saveTimer = window.setTimeout(save, 500)
  }

  function hydrate() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY)
      if (!raw) {
        // 首次访问：自动创建一个空对话
        create()
        return
      }
      const data = JSON.parse(raw)
      conversations.value = Array.isArray(data.conversations) ? data.conversations : []
      activeId.value = data.activeId ?? (conversations.value[0]?.id ?? null)
      // 如果没有 active，对话列表也为空，创建一个
      if (!activeId.value) create()
    } catch (e) {
      console.warn('对话历史恢复失败:', e)
      create()
    }
  }

  // 自动持久化
  watch(
    [conversations, activeId],
    () => saveDebounced(),
    { deep: true },
  )

  // ---- 容量管理 ----
  function evictIfOverflow() {
    if (conversations.value.length <= MAX_CONVERSATIONS) return
    // 删最旧（按 updatedAt 升序，保留最近 N 个）
    const sorted = [...conversations.value].sort(
      (a, b) => new Date(a.updatedAt).getTime() - new Date(b.updatedAt).getTime(),
    )
    const toRemove = sorted.slice(0, conversations.value.length - MAX_CONVERSATIONS)
    const removeIds = new Set(toRemove.map((c) => c.id))
    conversations.value = conversations.value.filter((c) => !removeIds.has(c.id))
    // 如果 active 被删了，切到第一个
    if (activeId.value && removeIds.has(activeId.value)) {
      activeId.value = conversations.value[0]?.id ?? null
    }
  }

  // ---- Actions ----
  function create(): Conversation {
    const conv: Conversation = {
      id: uuid(),
      title: '新对话',
      messages: [],
      createdAt: nowIso(),
      updatedAt: nowIso(),
    }
    conversations.value.unshift(conv)
    activeId.value = conv.id
    evictIfOverflow()
    return conv
  }

  function switchTo(id: string) {
    const conv = conversations.value.find((c) => c.id === id)
    if (!conv) return
    activeId.value = id
    // 更新 updatedAt 让排序靠前
    conv.updatedAt = nowIso()
  }

  function deleteConv(id: string) {
    const idx = conversations.value.findIndex((c) => c.id === id)
    if (idx < 0) return
    conversations.value.splice(idx, 1)
    if (activeId.value === id) {
      // 切到下一个（最近的）
      activeId.value = conversations.value[0]?.id ?? null
      if (!activeId.value) create()
    }
  }

  function rename(id: string, title: string) {
    const conv = conversations.value.find((c) => c.id === id)
    if (conv) {
      conv.title = title.trim() || '新对话'
      conv.updatedAt = nowIso()
    }
  }

  function appendMessage(msg: ChatMessage) {
    if (!activeId.value) create()
    const conv = conversations.value.find((c) => c.id === activeId.value)
    if (!conv) return
    conv.messages.push(msg)
    // 如果是首条 user 消息，派生标题
    if (conv.title === '新对话' && msg.role === 'user') {
      conv.title = deriveTitle(conv.messages)
    }
    conv.updatedAt = nowIso()
  }

  function clearActive() {
    if (!activeId.value) return
    const conv = conversations.value.find((c) => c.id === activeId.value)
    if (conv) {
      conv.messages = []
      conv.title = '新对话'
      conv.updatedAt = nowIso()
    }
  }

  function clearAll() {
    conversations.value = []
    activeId.value = null
    create()
  }

  /** 通过 id 获取会话（不依赖 activeId，H.1.1 流式切换对话用） */
  function getConversation(id: string): Conversation | null {
    return conversations.value.find((c) => c.id === id) ?? null
  }

  /**
   * 更新指定会话的最后一条消息（H.1.1 流式切换对话用）
   * - 用 convId 而不是 activeId 定位，避免用户中途切对话后写到错误位置
   */
  function updateMessageIn(convId: string, updater: (msg: ChatMessage) => void) {
    const conv = getConversation(convId)
    if (!conv || conv.messages.length === 0) return
    updater(conv.messages[conv.messages.length - 1])
    conv.updatedAt = nowIso()
  }

  return {
    // state
    conversations,
    activeId,
    // computed
    activeConversation,
    activeMessages,
    sortedConversations,
    // actions
    hydrate,
    create,
    switchTo,
    deleteConv,
    rename,
    appendMessage,
    updateMessageIn,
    getConversation,
    clearActive,
    clearAll,
  }
})

// 工具：相对时间（用于侧边栏时间显示）
export function formatRelativeTime(iso: string): string {
  const now = Date.now()
  const t = new Date(iso).getTime()
  const diff = Math.floor((now - t) / 1000)
  if (diff < 60) return '刚刚'
  if (diff < 3600) return `${Math.floor(diff / 60)} 分钟前`
  if (diff < 86400) return `${Math.floor(diff / 3600)} 小时前`
  if (diff < 7 * 86400) return `${Math.floor(diff / 86400)} 天前`
  return new Date(iso).toLocaleDateString('zh-CN')
}
