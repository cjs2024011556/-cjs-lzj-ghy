<template>
  <div class="loading-state" :class="{ 'is-full': full }">
    <div class="loading-spinner">
      <div class="spinner-ring"></div>
    </div>
    <div v-if="text" class="loading-text">{{ text }}</div>
  </div>
</template>

<script setup lang="ts">
withDefaults(defineProps<{
  text?: string
  full?: boolean
}>(), { full: false })
</script>

<style lang="scss" scoped>
.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--spacing-lg);
  gap: var(--spacing-sm);

  &.is-full {
    min-height: 200px;
  }
}

.loading-spinner {
  width: 32px;
  height: 32px;
  position: relative;
}

.spinner-ring {
  width: 100%;
  height: 100%;
  border: 3px solid var(--border-color);
  border-top-color: var(--primary-color);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.loading-text {
  font-size: var(--font-size-sm);
  color: var(--text-muted);
}
</style>
