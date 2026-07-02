<template>
  <div class="empty-state">
    <div class="empty-icon" :class="`empty-icon--${type}`">
      <el-icon :size="iconSize"><component :is="iconComponent" /></el-icon>
    </div>
    <div class="empty-text">
      <div class="empty-title">{{ title }}</div>
      <div v-if="description" class="empty-desc">{{ description }}</div>
    </div>
    <div v-if="$slots.action" class="empty-action">
      <slot name="action" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Box, Search, Document, DataAnalysis } from '@element-plus/icons-vue'

/**
 * 空状态（统一所有 el-empty 风格）
 */
const props = withDefaults(defineProps<{
  title: string
  description?: string
  type?: 'default' | 'search' | 'document' | 'data'
  iconSize?: number
}>(), {
  type: 'default',
  iconSize: 64,
})

const iconComponent = computed(() => {
  return {
    default: Box,
    search: Search,
    document: Document,
    data: DataAnalysis,
  }[props.type]
})
</script>

<style lang="scss" scoped>
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--spacing-2xl) var(--spacing-lg);
  text-align: center;
}

.empty-icon {
  width: 80px;
  height: 80px;
  border-radius: var(--radius-full);
  background: rgba(var(--primary-rgb), 0.08);
  color: var(--primary-color);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: var(--spacing-md);
  opacity: 0.6;

  &--search  { background: rgba(255, 184, 77, 0.08); color: var(--warning); }
  &--document { background: rgba(0, 212, 255, 0.08); color: var(--info); }
  &--data    { background: rgba(168, 85, 247, 0.08); color: #a855f7; }
}

.empty-title {
  font-size: var(--font-size-md);
  font-weight: var(--font-weight-medium);
  color: var(--text-secondary);
  margin-bottom: 4px;
}

.empty-desc {
  font-size: var(--font-size-sm);
  color: var(--text-muted);
  margin-bottom: var(--spacing-md);
  max-width: 320px;
}

.empty-action {
  display: flex;
  gap: var(--spacing-sm);
}
</style>
