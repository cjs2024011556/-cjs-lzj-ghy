<template>
  <div class="skeleton" :class="`skeleton--${type}`">
    <div
      v-for="n in count"
      :key="n"
      class="skeleton-bar"
      :style="{ width: randomWidth(n) }"
    />
  </div>
</template>

<script setup lang="ts">
/**
 * 骨架屏组件
 * - text:  多行文字骨架（默认）
 * - rect:  单个矩形（占位图）
 * - circle: 圆形（头像占位）
 * - card:  卡片骨架（含标题 + 段落 + 按钮）
 */
withDefaults(defineProps<{
  type?: 'text' | 'rect' | 'circle' | 'card'
  count?: number
  /** rect/circle 模式下的尺寸（px） */
  size?: number
  /** 自定义宽度（text 模式下生效） */
  width?: string
}>(), {
  type: 'text',
  count: 3,
  size: 80,
  width: '100%',
})


function randomWidth(n: number): string {
  // text 模式：第 1/2 行 100%，后续 60-90%
  if (n === 1) return '100%'
  if (n === 2) return '90%'
  // 随机宽度让骨架更自然
  const widths = ['100%', '92%', '85%', '78%', '70%']
  return widths[(n - 1) % widths.length]
}
</script>

<style lang="scss" scoped>
.skeleton {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
  width: 100%;

  &--card {
    padding: var(--spacing-md);
    background: var(--bg-secondary);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-lg);
    gap: var(--spacing-md);
  }
}

.skeleton-bar {
  height: 14px;
  background: linear-gradient(
    90deg,
    var(--bg-tertiary) 0%,
    var(--bg-elevated) 50%,
    var(--bg-tertiary) 100%
  );
  background-size: 200% 100%;
  border-radius: var(--radius-sm);
  animation: skeleton-shimmer 1.6s ease-in-out infinite;

  .skeleton--card & {
    &:first-child {
      height: 20px;
      width: 40% !important;
    }
    &:last-child {
      height: 32px;
      width: 30% !important;
      margin-top: var(--spacing-sm);
    }
  }
}

.skeleton--rect {
  .skeleton-bar {
    height: v-bind('`${size}px`');
    width: 100%;
  }
}

.skeleton--circle {
  align-items: center;
  .skeleton-bar {
    width: v-bind('`${size}px`');
    height: v-bind('`${size}px`');
    border-radius: 50%;
  }
}

@keyframes skeleton-shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}
</style>
