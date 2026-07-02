<template>
  <div class="feature-item">
    <div class="feature-icon" :class="`icon--${color}`">
      <el-icon :size="22"><component :is="icon" /></el-icon>
    </div>
    <div class="feature-content">
      <div class="feature-title">{{ title }}</div>
      <div class="feature-desc">{{ description }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
withDefaults(defineProps<{
  title: string
  description: string
  icon: string
  color?: 'primary' | 'success' | 'warning' | 'danger' | 'info'
}>(), { color: 'primary' })
</script>

<style lang="scss" scoped>
.feature-item {
  display: flex;
  align-items: flex-start;
  gap: var(--spacing-md);
  padding: var(--spacing-md);
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  transition: all var(--transition-base);

  &:hover {
    border-color: var(--primary-color);
    transform: translateY(-2px);
    box-shadow: var(--shadow-md);
  }
}

.feature-icon {
  width: 44px;
  height: 44px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  background: rgba(var(--primary-rgb), 0.12);
  color: var(--primary-color);

  &--success { background: rgba(0, 217, 126, 0.12); color: var(--success); }
  &--warning { background: rgba(255, 184, 77, 0.12); color: var(--warning); }
  &--danger  { background: rgba(255, 71, 87, 0.12);  color: var(--danger); }
  &--info    { background: rgba(0, 212, 255, 0.12);  color: var(--info); }
}

.feature-content { flex: 1; min-width: 0; }

.feature-title {
  font-size: var(--font-size-md);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
  margin-bottom: 4px;
}

.feature-desc {
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  line-height: 1.6;
}
</style>
