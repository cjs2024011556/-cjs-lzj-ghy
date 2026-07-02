<template>
  <div class="error-state">
    <svg class="error-icon" viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg">
      <circle cx="32" cy="32" r="28" fill="none" stroke="currentColor" stroke-width="2" opacity="0.3" />
      <circle cx="32" cy="32" r="20" fill="none" stroke="currentColor" stroke-width="1" opacity="0.5" stroke-dasharray="2 4" />
      <path d="M 24 24 L 40 40 M 40 24 L 24 40" stroke="currentColor" stroke-width="3" stroke-linecap="round" />
    </svg>
    <div class="error-title">{{ title }}</div>
    <div v-if="description" class="error-desc">{{ description }}</div>
    <div v-if="code" class="error-code">错误码：{{ code }}</div>
    <div v-if="$slots.action || showRetry" class="error-action">
      <slot name="action">
        <el-button v-if="showRetry" type="primary" @click="$emit('retry')">
          <el-icon><Refresh /></el-icon>
          重试
        </el-button>
      </slot>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Refresh } from '@element-plus/icons-vue'

withDefaults(defineProps<{
  title?: string
  description?: string
  code?: string | number
  showRetry?: boolean
}>(), {
  title: '加载失败',
  description: '请检查网络连接后重试',
  code: '',
  showRetry: true,
})

defineEmits<{ (e: 'retry'): void }>()
</script>

<style lang="scss" scoped>
.error-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--spacing-2xl) var(--spacing-lg);
  text-align: center;
}

.error-icon {
  width: 80px;
  height: 80px;
  color: var(--danger);
  margin-bottom: var(--spacing-md);
  opacity: 0.85;
}

.error-title {
  font-size: var(--font-size-lg);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
  margin-bottom: var(--spacing-xs);
}

.error-desc {
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  margin-bottom: var(--spacing-sm);
  max-width: 400px;
  line-height: 1.6;
}

.error-code {
  font-size: var(--font-size-xs);
  color: var(--text-muted);
  font-family: 'Consolas', 'Monaco', monospace;
  background: var(--bg-tertiary);
  padding: 4px 10px;
  border-radius: var(--radius-sm);
  margin-bottom: var(--spacing-md);
}

.error-action {
  margin-top: var(--spacing-sm);
}
</style>
