<template>
  <div class="quick-action" :class="`action--${color}`" @click="$emit('click')">
    <div class="action-icon">
      <el-icon :size="22"><component :is="icon" /></el-icon>
    </div>
    <div class="action-label">{{ label }}</div>
    <div v-if="description" class="action-desc">{{ description }}</div>
  </div>
</template>

<script setup lang="ts">
withDefaults(defineProps<{
  label: string
  description?: string
  icon: string
  color?: 'primary' | 'success' | 'warning' | 'danger' | 'info'
}>(), { color: 'primary' })

defineEmits<{ (e: 'click'): void }>()
</script>

<style lang="scss" scoped>
.quick-action {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: var(--spacing-md) var(--spacing-sm);
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  cursor: pointer;
  transition: all var(--transition-base);
  text-align: center;
  min-height: 110px;

  &:hover {
    transform: translateY(-3px);
    border-color: var(--primary-color);
    box-shadow: var(--shadow-glow);
  }

  &--success:hover { border-color: var(--success); box-shadow: 0 0 16px rgba(0, 217, 126, 0.3); }
  &--warning:hover { border-color: var(--warning); box-shadow: 0 0 16px rgba(255, 184, 77, 0.3); }
  &--info:hover    { border-color: var(--info);    box-shadow: 0 0 16px rgba(0, 212, 255, 0.3); }
}

.action-icon {
  width: 44px;
  height: 44px;
  border-radius: var(--radius-md);
  background: rgba(var(--primary-rgb), 0.12);
  color: var(--primary-color);
  display: flex;
  align-items: center;
  justify-content: center;
  transition: transform var(--transition-base);

  .quick-action:hover & {
    transform: scale(1.1);
  }

  .action--success & { background: rgba(0, 217, 126, 0.12); color: var(--success); }
  .action--warning & { background: rgba(255, 184, 77, 0.12); color: var(--warning); }
  .action--info    & { background: rgba(0, 212, 255, 0.12); color: var(--info); }
}

.action-label {
  font-size: var(--font-size-md);
  font-weight: var(--font-weight-medium);
  color: var(--text-primary);
}

.action-desc {
  font-size: var(--font-size-xs);
  color: var(--text-muted);
}
</style>
