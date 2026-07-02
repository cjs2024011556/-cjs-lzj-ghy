<template>
  <div class="stat-card" :class="`stat-card--${color}`" @click="$emit('click')">
    <div class="stat-card__header">
      <div v-if="icon" class="stat-card__icon">
        <el-icon :size="24"><component :is="icon" /></el-icon>
      </div>
      <div v-if="trend" class="stat-card__trend" :class="`trend--${trend}`">
        <el-icon :size="12">
          <CaretTop v-if="trend === 'up'" />
          <CaretBottom v-else />
        </el-icon>
        <span>{{ trendValue }}</span>
      </div>
    </div>
    <div class="stat-card__value">
      <AnimatedNumber v-if="animate" :value="value" />
      <span v-else>{{ value }}</span>
      <span v-if="suffix" class="suffix">{{ suffix }}</span>
    </div>
    <div class="stat-card__label">{{ label }}</div>
    <div v-if="subtext" class="stat-card__subtext">{{ subtext }}</div>
  </div>
</template>

<script setup lang="ts">
import { CaretTop, CaretBottom } from '@element-plus/icons-vue'
import AnimatedNumber from './AnimatedNumber.vue'

/**
 * 统计卡片（Home / Admin 复用）
 */
withDefaults(defineProps<{
  /** 数值 */
  value: number | string
  /** 标签 */
  label: string
  /** 后缀（%、次等） */
  suffix?: string
  /** 图标名 */
  icon?: string
  /** 主题色 */
  color?: 'primary' | 'success' | 'warning' | 'danger' | 'info' | 'purple'
  /** 副标题 */
  subtext?: string
  /** 趋势 up / down */
  trend?: 'up' | 'down'
  /** 趋势值（如 +5.2%） */
  trendValue?: string
  /** 是否数字滚动动画 */
  animate?: boolean
}>(), {
  color: 'primary',
  animate: true,
})

defineEmits<{ (e: 'click'): void }>()
</script>

<style lang="scss" scoped>
.stat-card {
  background: var(--bg-tertiary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  padding: var(--spacing-md) var(--spacing-lg);
  position: relative;
  overflow: hidden;
  cursor: pointer;
  background: linear-gradient(135deg, var(--bg-tertiary) 0%, var(--bg-elevated) 100%);
  transition: all var(--transition-spring);

  &:hover {
    transform: translateY(-4px);
    border-color: var(--primary-color);
    box-shadow: 0 12px 24px rgba(0, 0, 0, 0.3), 0 0 20px rgba(var(--primary-rgb), 0.3);
    background: linear-gradient(135deg, var(--bg-elevated) 0%, var(--bg-tertiary) 100%);

    .stat-card__value {
      transform: scale(1.05);
      color: var(--primary-color);
    }
  }

  // 左侧色条
  &::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    width: 3px;
    height: 100%;
    background: var(--primary-color);
    transition: width var(--transition-base);
  }

  &:hover::before { width: 4px; }

  &--success::before { background: var(--success); }
  &--warning::before { background: var(--warning); }
  &--danger::before  { background: var(--danger); }
  &--info::before    { background: var(--info); }
  &--purple::before  { background: #a855f7; }
}

.stat-card__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--spacing-sm);
}

.stat-card__icon {
  width: 40px;
  height: 40px;
  border-radius: var(--radius-md);
  background: rgba(var(--primary-rgb), 0.12);
  color: var(--primary-color);
  display: flex;
  align-items: center;
  justify-content: center;

  .stat-card--success & { background: rgba(0, 217, 126, 0.12); color: var(--success); }
  .stat-card--warning & { background: rgba(255, 184, 77, 0.12); color: var(--warning); }
  .stat-card--danger  & { background: rgba(255, 71, 87, 0.12);  color: var(--danger); }
  .stat-card--info    & { background: rgba(0, 212, 255, 0.12);  color: var(--info); }
  .stat-card--purple  & { background: rgba(168, 85, 247, 0.12); color: #a855f7; }
}

.stat-card__trend {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  padding: 2px 8px;
  border-radius: var(--radius-full);
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-medium);

  &.trend--up { background: rgba(0, 217, 126, 0.15); color: var(--success); }
  &.trend--down { background: rgba(255, 71, 87, 0.15); color: var(--danger); }
}

.stat-card__value {
  font-size: var(--font-size-3xl);
  font-weight: var(--font-weight-bold);
  color: var(--text-primary);
  line-height: 1.2;
  display: flex;
  align-items: baseline;
  gap: 4px;
  transition: all var(--transition-base);

  .suffix {
    font-size: var(--font-size-md);
    color: var(--text-muted);
    font-weight: var(--font-weight-normal);
  }
}

.stat-card__label {
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  margin-top: var(--spacing-xs);
}

.stat-card__subtext {
  font-size: var(--font-size-xs);
  color: var(--text-muted);
  margin-top: 4px;
}
</style>
