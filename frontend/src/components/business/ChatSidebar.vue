<template>
  <aside class="chat-sidebar" :class="{ collapsed }">
    <!-- 顶部：新建按钮 + 折叠 -->
    <div class="sidebar-header">
      <el-button type="primary" size="small" class="new-btn" @click="onNew">
        <el-icon><Plus /></el-icon>
        <span v-if="!collapsed">新对话</span>
      </el-button>
      <el-tooltip :content="collapsed ? '展开侧边栏' : '折叠侧边栏'" placement="bottom">
        <el-button text circle @click="$emit('toggle-collapse')">
          <el-icon><Fold v-if="!collapsed" /><Expand v-else /></el-icon>
        </el-button>
      </el-tooltip>
    </div>

    <!-- 对话列表 -->
    <div class="sidebar-list" v-if="!collapsed">
      <div v-if="store.sortedConversations.length === 0" class="empty-hint">
        <el-icon :size="20"><ChatLineRound /></el-icon>
        <span>暂无对话</span>
      </div>

      <div
        v-for="conv in store.sortedConversations"
        :key="conv.id"
        class="conv-item"
        :class="{ active: conv.id === store.activeId }"
        @click="store.switchTo(conv.id)"
      >
        <el-icon class="conv-icon"><ChatLineRound /></el-icon>
        <div class="conv-content">
          <div class="conv-title">{{ conv.title || '新对话' }}</div>
          <div class="conv-meta">
            <span>{{ conv.messages.length }} 条消息</span>
            <span class="dot">·</span>
            <span>{{ formatRelativeTime(conv.updatedAt) }}</span>
          </div>
        </div>
        <el-dropdown trigger="click" @command="(cmd) => onCommand(cmd, conv.id)" @click.stop>
          <el-button text circle class="conv-action" @click.stop>
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
  </aside>
</template>

<script setup lang="ts">
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Plus,
  Fold,
  Expand,
  ChatLineRound,
  MoreFilled,
  Edit,
  Delete,
} from '@element-plus/icons-vue'
import { useChatHistoryStore, formatRelativeTime } from '@/stores/chatHistory'

defineProps<{ collapsed?: boolean }>()
defineEmits<{ (e: 'toggle-collapse'): void }>()

const store = useChatHistoryStore()

function onNew() {
  store.create()
  ElMessage.success('已创建新对话')
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
  gap: 8px;
  padding: 12px;
  border-bottom: 1px solid var(--border-color);
}

.new-btn {
  flex: 1;
  justify-content: flex-start;
  background: rgba(var(--primary-rgb), 0.12) !important;
  border-color: rgba(var(--primary-rgb), 0.3) !important;
  color: var(--primary-color) !important;
  font-weight: var(--font-weight-medium);

  &:hover {
    background: rgba(var(--primary-rgb), 0.2) !important;
    border-color: var(--primary-color) !important;
  }
}

.sidebar-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
  display: flex;
  flex-direction: column;
  gap: 4px;

  &::-webkit-scrollbar { width: 4px; }
}

.empty-hint {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 32px 16px;
  color: var(--text-muted);
  font-size: var(--font-size-sm);
}

.conv-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all var(--transition-fast);
  border: 1px solid transparent;
  position: relative;

  &:hover {
    background: var(--bg-tertiary);

    .conv-action { opacity: 1; }
  }

  &.active {
    background: rgba(var(--primary-rgb), 0.12);
    border-color: rgba(var(--primary-rgb), 0.4);

    .conv-title { color: var(--primary-color); }
  }
}

.conv-icon {
  color: var(--text-muted);
  flex-shrink: 0;
  font-size: 16px;

  .conv-item.active & { color: var(--primary-color); }
}

.conv-content {
  flex: 1;
  min-width: 0;
  overflow: hidden;
}

.conv-title {
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-medium);
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-bottom: 2px;
}

.conv-meta {
  font-size: var(--font-size-xs);
  color: var(--text-muted);
  display: flex;
  gap: 4px;
  align-items: center;

  .dot { opacity: 0.5; }
}

.conv-action {
  opacity: 0;
  transition: opacity var(--transition-fast);
  flex-shrink: 0;
}
</style>
