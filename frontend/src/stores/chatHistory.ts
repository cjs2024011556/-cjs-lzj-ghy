/**
 * 对话历史 Store（ChatGPT 风格多对话管理）
 *
 * 特性：
 * - 最多 50 个对话，LRU 淘汰
 * - localStorage 持久化，debounce 500ms
 * - 第一条 user 消息作为对话标题
 * - 容量超限自动清理最旧
 * - **多用户隔离**：每个用户的对话独立存于 `a1_chat_history_<username>`
 */
import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'

const STORAGE_KEY_PREFIX = 'a1_chat_history_'
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

function storageKeyFor(username: string | null): string {
  // 未登录用 'guest' 兜底（不写盘）
  return STORAGE_KEY_PREFIX + (username || 'guest')
}

export const useChatHistoryStore = defineStore('chatHistory', () => {
  const conversations = ref<Conversation[]>([])
  const activeId = ref<string | null>(null)
  const currentUser = ref<string | null>(null)
  let saveTimer: number | null = null
  let streamAbort: (() => void) | null = null  // 当前流式句柄（Home 注册）

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
    if (!currentUser.value) return  // 未登录不写盘
    try {
      const data = JSON.stringify({
        conversations: conversations.value,
        activeId: activeId.value,
      })
      localStorage.setItem(storageKeyFor(currentUser.value), data)
    } catch (e) {
      console.warn('对话历史保存失败:', e)
    }
  }

  function saveDebounced() {
    if (saveTimer) clearTimeout(saveTimer)
    saveTimer = window.setTimeout(save, 500)
  }

  function hydrate() {
    if (!currentUser.value) {
      // 未登录：清空内存
      conversations.value = []
      activeId.value = null
      return
    }
    try {
      const raw = localStorage.getItem(storageKeyFor(currentUser.value))
      if (!raw) {
        // 该用户首次访问：ChatGPT 行为 — 无对话，让用户点"新对话"开始
        conversations.value = []
        activeId.value = null
        return
      }
      const data = JSON.parse(raw)
      conversations.value = Array.isArray(data.conversations) ? data.conversations : []
      activeId.value = data.activeId ?? (conversations.value[0]?.id ?? null)
    } catch (e) {
      console.warn('对话历史恢复失败:', e)
      conversations.value = []
      activeId.value = null
    }
  }

  /**
   * 切换当前用户（登录后 / 登出时调用）
   * - **abort 当前流式响应**（防止切用户后旧 conv 的 chunk 写到新用户盘上）
   * - 立即把当前内存的对话写回上一个用户的 localStorage（防止数据丢失）
   * - 重置内存，从新用户的 localStorage 读取
   * - 必须在路由跳转到聊天页之前调用
   */
  function setUser(username: string | null) {
    // 0. abort 当前流式（如果有）— 否则旧用户的 onDelta 会写到已被清空的 conversations
    if (streamAbort) {
      streamAbort()
      streamAbort = null
    }
    // 1. 先把当前用户的数据 flush 到盘（如果有）
    if (currentUser.value) {
      // 取消 debounce 等待，立即写
      if (saveTimer) {
        clearTimeout(saveTimer)
        saveTimer = null
      }
      save()
    }
    // 2. 切到新用户
    currentUser.value = username
    // 3. 从新用户的 localStorage 重新加载
    hydrate()
  }

  /**
   * 注册/清除当前流式 abort 句柄
   * - Home.vue 在 streamChat 拿到句柄时调用 setStreamAbort
   * - 流结束时（onDone/onError）调用 clearStreamAbort
   * - setUser / 用户切换时会自动调用注册的 abort
   */
  function setStreamAbort(abort: (() => void) | null) {
    streamAbort = abort
  }

  function clearStreamAbort() {
    streamAbort = null
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
    // 不更新 updatedAt — ChatGPT 行为：仅查看/切换不改变排序
    // 只有主动发消息（appendMessage）时才让对话排到顶部
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
    currentUser,
    // computed
    activeConversation,
    activeMessages,
    sortedConversations,
    // actions
    hydrate,
    setUser,
    setStreamAbort,
    clearStreamAbort,
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
