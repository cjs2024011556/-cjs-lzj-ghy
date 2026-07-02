<template>
  <div class="brand-strip">
    <svg class="brand-logo" viewBox="0 0 32 32" xmlns="http://www.w3.org/2000/svg">
      <!-- 外环 -->
      <circle cx="16" cy="16" r="14" fill="none" stroke="currentColor" stroke-width="1.5" opacity="0.3" />
      <!-- 雷达扫描弧 -->
      <path
        d="M 16 16 L 28 8 A 14 14 0 0 0 22 4"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        stroke-linecap="round"
      />
      <!-- 中心点 -->
      <circle cx="16" cy="16" r="3" fill="currentColor" />
      <!-- 齿轮齿（4 个方向） -->
      <rect x="15" y="2" width="2" height="3" fill="currentColor" rx="0.5" />
      <rect x="15" y="27" width="2" height="3" fill="currentColor" rx="0.5" />
      <rect x="2" y="15" width="3" height="2" fill="currentColor" rx="0.5" />
      <rect x="27" y="15" width="3" height="2" fill="currentColor" rx="0.5" />
    </svg>
    <span class="brand-text">
      <span class="brand-name">A1</span>
      <span class="brand-divider">·</span>
      <span class="brand-sub">工业智能检修平台</span>
    </span>
    <span class="brand-divider-2">|</span>
    <span class="brand-status">
      <span class="status-dot" :class="`status--${status.level}`"></span>
      {{ status.text }}
    </span>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'

const status = ref({ level: 'success' as 'success' | 'warning' | 'danger', text: '在线 · 实时' })
let timer: number | null = null

function updateStatus() {
  // 按小时切状态
  const hour = new Date().getHours()
  if (hour >= 9 && hour < 18) {
    status.value = { level: 'success', text: '在线 · 实时调度' }
  } else if (hour >= 18 && hour < 22) {
    status.value = { level: 'warning', text: '在线 · 加班模式' }
  } else {
    status.value = { level: 'success', text: '在线 · 夜间值守' }
  }
}

/** 距下一个整点的毫秒数 */
function msUntilNextHour() {
  const now = new Date()
  const next = new Date(now)
  next.setHours(now.getHours() + 1, 0, 0, 0)
  return next.getTime() - now.getTime()
}

function scheduleNextUpdate() {
  if (timer) clearTimeout(timer)
  // 第一次刷新在下一个整点 + 之后每小时一次（避免 60s 心跳浪费）
  timer = window.setTimeout(() => {
    updateStatus()
    scheduleNextUpdate()
  }, msUntilNextHour())
}

onMounted(() => {
  updateStatus()
  scheduleNextUpdate()  // 对齐整点的 setTimeout（避免 60s 心跳浪费）
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>

<style lang="scss" scoped>
.brand-strip {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 12px;
  background: rgba(var(--primary-rgb), 0.04);
  border: 1px solid rgba(var(--primary-rgb), 0.15);
  border-radius: var(--radius-full);
  font-size: var(--font-size-xs);
  color: var(--text-secondary);
  white-space: nowrap;
  height: 26px;
}

.brand-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: rgba(var(--primary-rgb), 0.15);
  color: var(--primary-color);
  flex-shrink: 0;
}

.brand-logo {
  width: 18px;
  height: 18px;
  color: var(--primary-color);
  flex-shrink: 0;
  filter: drop-shadow(0 0 4px rgba(var(--primary-rgb), 0.4));
}

.brand-name {
  font-weight: var(--font-weight-bold);
  color: var(--primary-color);
  font-size: 13px;
  letter-spacing: 0.5px;
}

.brand-divider,
.brand-divider-2 {
  color: var(--text-muted);
  opacity: 0.4;
  margin: 0 2px;
}

.brand-sub {
  color: var(--text-secondary);
}

.brand-status {
  display: flex;
  align-items: center;
  gap: 4px;
  color: var(--text-muted);
  font-size: var(--font-size-xs);
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;

  &.status--success { background: var(--success); box-shadow: 0 0 6px var(--success); animation: pulse 2s ease-in-out infinite; }
  &.status--warning { background: var(--warning); box-shadow: 0 0 6px var(--warning); }
  &.status--danger  { background: var(--danger);  box-shadow: 0 0 6px var(--danger); }
}
</style>
