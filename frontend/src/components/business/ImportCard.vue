<template>
  <div class="import-card" @click="onClick">
    <div class="card-icon" :style="{ color: color }">
      <el-icon :size="40"><component :is="icon" /></el-icon>
    </div>
    <div class="card-title">{{ title }}</div>
    <div class="card-desc">{{ description }}</div>
    <el-button type="primary" :loading="loading" size="small" style="margin-top: 8px" @click.stop="onClick">
      {{ loading ? '导入中...' : '导入' }}
    </el-button>
  </div>
</template>

<script setup lang="ts">
/**
 * 知识库导入卡片（Admin 用）
 */
const props = defineProps<{
  title: string
  description: string
  icon: string
  color: string
  loading?: boolean
}>()

const emit = defineEmits<{ (e: 'click'): void }>()

function onClick() {
  if (props.loading) return
  emit('click')
}
</script>

<style lang="scss" scoped>
.import-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: var(--spacing-lg);
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  cursor: pointer;
  transition: all var(--transition-base);
  min-height: 180px;

  &:hover {
    transform: translateY(-3px);
    border-color: var(--primary-color);
    box-shadow: var(--shadow-md);
  }
}

.card-icon {
  margin-bottom: 8px;
  transition: transform var(--transition-base);

  .import-card:hover & {
    transform: scale(1.1);
  }
}

.card-title {
  font-size: var(--font-size-md);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
  margin-bottom: 4px;
}

.card-desc {
  font-size: var(--font-size-xs);
  color: var(--text-muted);
}
</style>
