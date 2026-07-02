<template>
  <div class="section-title-wrap">
    <h2 class="section-title">
      <el-icon v-if="icon" class="title-icon"><component :is="icon" /></el-icon>
      <span>{{ title }}</span>
      <el-tag v-if="badge" :type="badgeType" effect="dark" round size="small">
        {{ badge }}
      </el-tag>
    </h2>
    <div v-if="$slots.extra" class="extra">
      <slot name="extra" />
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * 区块标题（所有页面统一）
 * - 主标题 + 可选图标 + 可选徽章 + 右侧额外操作
 */
withDefaults(defineProps<{
  title: string
  icon?: string
  badge?: string | number
  badgeType?: 'primary' | 'success' | 'warning' | 'danger' | 'info'
}>(), {
  badgeType: 'primary',
})
</script>

<style lang="scss" scoped>
.section-title-wrap {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--spacing-md);
  gap: var(--spacing-md);
  flex-wrap: wrap;
}

.section-title {
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-sm);
  font-size: var(--font-size-2xl);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
  padding-bottom: var(--spacing-sm);
  border-bottom: 2px solid var(--primary-color);
  margin: 0;
}

.title-icon {
  color: var(--primary-color);
  font-size: var(--font-size-xl);
}

.extra {
  display: flex;
  gap: var(--spacing-sm);
  align-items: center;
}
</style>
