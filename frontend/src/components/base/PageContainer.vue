<template>
  <div class="page-container" :class="{ 'is-narrow': narrow, 'has-grid': withGrid }">
    <slot />
  </div>
</template>

<script setup lang="ts">
/**
 * 页面外层容器
 * - 默认最大宽度 1400px
 * - narrow=true 时 800px（用于 ChatGPT 风格的窄布局）
 * - withGrid=true 时背景显示极淡 grid pattern（U.2.5）
 */
withDefaults(defineProps<{ narrow?: boolean; withGrid?: boolean }>(), {
  narrow: false,
  withGrid: false,
})
</script>

<style lang="scss" scoped>
.page-container {
  position: relative;
  width: 100%;
  margin: 0 auto;
  padding: var(--spacing-lg);
  max-width: var(--content-max-width, 1400px);

  &.is-narrow {
    max-width: 1000px;
  }

  // U.2.5 全局背景 grid pattern（强度 0.02）
  &.has-grid::before {
    content: '';
    position: fixed;
    inset: 0;
    background-image:
      linear-gradient(rgba(var(--primary-rgb), 0.02) 1px, transparent 1px),
      linear-gradient(90deg, rgba(var(--primary-rgb), 0.02) 1px, transparent 1px);
    background-size: 40px 40px;
    pointer-events: none;
    z-index: -1;
  }
}
</style>

