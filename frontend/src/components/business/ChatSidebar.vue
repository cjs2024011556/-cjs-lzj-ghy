<template>
  <aside class="chat-sidebar" :class="{ collapsed }">
    <!-- 顶部：Logo + 新对话 + 折叠 -->
    <div class="sidebar-header">
      <div v-if="!collapsed" class="sidebar-brand">
        <el-icon :size="18" color="var(--primary-color)"><ChatLineRound /></el-icon>
        <span>智能问答</span>
      </div>
      <el-tooltip :content="collapsed ? '展开' : '折叠'" placement="bottom">
        <el-button text circle size="small" @click="$emit('toggle-collapse')">
          <el-icon :size="16"><Fold v-if="!collapsed" /><Expand v-else /></el-icon>
        </el-button>
      </el-tooltip>
    </div>

    <!-- 新对话按钮（ChatGPT 风格：圆角图标 + 文字） -->
    <div v-if="!collapsed" class="new-conv-row">
      <button class="new-btn" @click="onNew">
        <el-icon :size="16"><Plus /></el-icon>
        <span>新对话</span>
      </button>
    </div>

    <!-- 搜索框（ChatGPT 风格） -->
    <div v-if="!collapsed" class="search-row">
      <el-input
        v-model="searchKey"
        size="small"
        placeholder="搜索对话..."
        clearable
        class="search-input"
      >
        <template #prefix>
          <el-icon><Search /></el-icon>
        </template>
      </el-input>
    </div>

    <!-- 对话列表 -->
    <div class="sidebar-list" v-if="!collapsed">
      <div v-if="filteredConvs.length === 0" class="empty-hint">
        <el-icon :size="18"><ChatLineRound /></el-icon>
        <span>{{ searchKey ? '无匹配对话' : '暂无对话' }}</span>
      </div>

      <div
        v-for="conv in filteredConvs"
        :key="conv.id"
        class="conv-item"
        :class="{ active: conv.id === store.activeId }"
        @click="store.switchTo(conv.id)"
      >
        <el-icon v-if="conv.id === store.activeId" class="conv-icon"><ChatLineRound /></el-icon>
        <div class="conv-title">{{ conv.title || '新对话' }}</div>
        <el-dropdown trigger="click" @command="(cmd) => onCommand(cmd, conv.id)" @click.stop>
          <el-button text circle size="small" class="conv-action" @click.stop>
            <el-icon><MoreFilled /></el-icon>
          </el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="rename">
                <el-icon><Edit /></el-icon>
                重命名
              </el-dropdown-item>
              <el-dropdown-item command="delete" divided>
                <el-icon color="var(--danger)"><Delete /></el-icon>
                <span style="color: var(--danger)">删除</span>
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </div>

    <!-- 底部：用户信息（折叠时也显示） -->
    <div v-if="!collapsed" class="sidebar-footer">
      <el-button text size="small" @click="onClearAll" class="clear-all-btn">
        <el-icon><Delete /></el-icon>
        <span>清空所有对话</span>
      </el-button>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Plus,
  Fold,
  Expand,
  ChatLineRound,
  MoreFilled,
  Edit,
  Delete,
  Search,
} from '@element-plus/icons-vue'
import { useChatHistoryStore } from '@/stores/chatHistory'

defineProps<{ collapsed?: boolean }>()
defineEmits<{ (e: 'toggle-collapse'): void }>()

const store = useChatHistoryStore()
const searchKey = ref('')

// 搜索过滤（标题包含关键字的对话）
const filteredConvs = computed(() => {
  const key = searchKey.value.trim().toLowerCase()
  if (!key) return store.sortedConversations
  return store.sortedConversations.filter((c) =>
    (c.title || '').toLowerCase().includes(key),
  )
})

function onNew() {
  store.create()
  ElMessage.success('已创建新对话')
}

async function onClearAll() {
  try {
    await ElMessageBox.confirm(
      `确定清空所有对话吗？共 ${store.conversations.length} 个对话将被删除，此操作不可恢复。`,
      '清空所有对话',
      { type: 'warning', confirmButtonText: '清空', cancelButtonText: '取消' },
    )
    store.clearAll()
    ElMessage.success('已清空所有对话')
  } catch {
    // 取消
  }
}

async function onCommand(cmd: string, convId: string) {
  const conv = store.conversations.find((c) => c.id === convId)
  if (!conv) return

  if (cmd === 'delete') {
    try {
      await ElMessageBox.confirm(
        `确定删除对话「${conv.title}」吗？此操作不可恢复。`,
        '删除确认',
        { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
      )
      store.deleteConv(convId)
      ElMessage.success('已删除')
    } catch {
      // 取消
    }
  } else if (cmd === 'rename') {
    try {
      const { value } = await ElMessageBox.prompt('新对话标题', '重命名', {
        inputValue: conv.title,
        inputValidator: (v) => (v && v.trim() ? true : '标题不能为空'),
      })
      store.rename(convId, value)
    } catch {
      // 取消
    }
  }
}
</script>

<style lang="scss" scoped>
.chat-sidebar {
  width: 260px;
  height: 100%;
  background: var(--bg-secondary);
  border-right: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
  transition: width var(--transition-base);
  flex-shrink: 0;

  &.collapsed {
    width: 60px;

    .sidebar-header { padding: 12px 8px; }
  }
}

.sidebar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 12px 8px;
  gap: 8px;
}

.sidebar-brand {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: var(--font-size-md);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
}

// ChatGPT 风格：新对话按钮 — 自定义圆角按钮（不用 element 默认色）
.new-conv-row {
  padding: 4px 8px 8px;
}

.new-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 8px 12px;
  background: transparent;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  color: var(--text-primary);
  font-size: var(--font-size-sm);
  cursor: pointer;
  transition: all var(--transition-fast);

  &:hover {
    background: var(--bg-tertiary);
    border-color: var(--primary-color);
    color: var(--primary-color);
  }
}

// ChatGPT 风格：搜索框
.search-row {
  padding: 0 8px 8px;
}

.search-input :deep(.el-input__wrapper) {
  background: transparent;
  border-radius: 8px;
  padding: 2px 8px;
  box-shadow: 0 0 0 1px var(--border-color) inset;

  &:hover, &.is-focus {
    box-shadow: 0 0 0 1px var(--primary-color) inset;
  }
}

.sidebar-list {
  flex: 1;
  overflow-y: auto;
  padding: 4px 8px;
  display: flex;
  flex-direction: column;
  gap: 2px;

  &::-webkit-scrollbar { width: 4px; }
}

.empty-hint {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 24px 12px;
  color: var(--text-muted);
  font-size: var(--font-size-xs);
}

// ChatGPT 风格：极简对话项
.conv-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 10px;
  border-radius: 8px;
  cursor: pointer;
  transition: background var(--transition-fast);
  position: relative;

  &:hover {
    background: var(--bg-tertiary);

    .conv-action { opacity: 1; }
  }

  &.active {
    background: rgba(var(--primary-rgb), 0.12);

    .conv-title { color: var(--primary-color); font-weight: var(--font-weight-semibold); }
  }
}

.conv-icon {
  color: var(--primary-color);
  flex-shrink: 0;
  font-size: 14px;
}

.conv-title {
  flex: 1;
  min-width: 0;
  font-size: var(--font-size-sm);
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.conv-action {
  opacity: 0;
  transition: opacity var(--transition-fast);
  flex-shrink: 0;
}

// 底部清空按钮
.sidebar-footer {
  padding: 8px;
  border-top: 1px solid var(--border-color);
}

.clear-all-btn {
  width: 100%;
  justify-content: flex-start;
  color: var(--text-muted);
  font-size: var(--font-size-xs);

  &:hover {
    color: var(--danger);
  }
}
</style>
