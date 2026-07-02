<template>
  <span class="animated-number">{{ displayValue }}</span>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'

/**
 * 数字滚动动画（演示"哇"点）
 * 数值变化时 600ms 缓动到目标值
 */
const props = defineProps<{ value: number }>()

const displayValue = ref(0)
let raf: number | null = null

function animateTo(target: number) {
  if (raf) cancelAnimationFrame(raf)
  const start = performance.now()
  const from = displayValue.value
  const delta = target - from
  const duration = 600

  function step(now: number) {
    const elapsed = now - start
    const t = Math.min(elapsed / duration, 1)
    // easeOutCubic
    const eased = 1 - Math.pow(1 - t, 3)
    displayValue.value = Math.round(from + delta * eased)
    if (t < 1) {
      raf = requestAnimationFrame(step)
    } else {
      displayValue.value = target
      raf = null
    }
  }
  raf = requestAnimationFrame(step)
}

watch(
  () => props.value,
  (v) => animateTo(v),
  { immediate: true },
)
</script>

<style lang="scss" scoped>
.animated-number {
  font-variant-numeric: tabular-nums;
  display: inline-block;
}
</style>
