<template>
  <div class="not-found-page">
    <div class="content fade-in">
      <div class="code-display">
        <span class="code-digit">4</span>
        <div class="logo">
          <el-icon :size="48" color="#00d4ff"><Tools /></el-icon>
        </div>
        <span class="code-digit">4</span>
      </div>

      <h1 class="title">页面未找到</h1>
      <p class="desc">
        抱歉，您访问的页面不存在或已被移除。
        <br />
        请检查 URL 是否正确，或返回首页继续浏览。
      </p>

      <div class="actions">
        <el-button type="primary" size="large" @click="goHome">
          <el-icon><HomeFilled /></el-icon>
          返回首页
        </el-button>
        <el-button size="large" @click="goBack">
          <el-icon><Back /></el-icon>
          返回上一页
        </el-button>
      </div>

      <div class="hint">
        <el-text type="info" size="small">
          错误码: 404 · 路径: <code>{{ route.fullPath }}</code>
        </el-text>
      </div>
    </div>

    <!-- 背景装饰 -->
    <div class="bg-decoration">
      <div class="grid-pattern"></div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useRoute, useRouter } from 'vue-router'
import { Tools, HomeFilled, Back } from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()

function goHome() {
  router.push('/home')
}

function goBack() {
  if (window.history.length > 1) {
    router.back()
  } else {
    router.push('/home')
  }
}
</script>

<style lang="scss" scoped>
.not-found-page {
  position: relative;
  width: 100vw;
  height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-primary);
  overflow: hidden;
}

.bg-decoration {
  position: absolute;
  inset: 0;
  pointer-events: none;
}

.grid-pattern {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(var(--primary-rgb), 0.04) 1px, transparent 1px),
    linear-gradient(90deg, rgba(var(--primary-rgb), 0.04) 1px, transparent 1px);
  background-size: 40px 40px;
  mask-image: radial-gradient(ellipse at center, black 30%, transparent 70%);
}

.content {
  position: relative;
  z-index: 1;
  text-align: center;
  max-width: 560px;
  padding: 24px;
}

.code-display {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  margin-bottom: 32px;
  font-size: 96px;
  font-weight: var(--font-weight-bold);
  line-height: 1;
}

.code-digit {
  color: var(--primary-color);
  text-shadow: 0 0 24px rgba(var(--primary-rgb), 0.5);
  animation: pulse 3s ease-in-out infinite;
}

.logo {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 80px;
  height: 80px;
  background: var(--bg-secondary);
  border: 2px solid var(--primary-color);
  border-radius: var(--radius-lg);
  animation: pulse 3s ease-in-out infinite 0.5s;
}

.title {
  font-size: var(--font-size-3xl);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
  margin: 0 0 16px 0;
}

.desc {
  font-size: var(--font-size-md);
  color: var(--text-secondary);
  line-height: var(--line-height-relaxed);
  margin: 0 0 32px 0;
}

.actions {
  display: flex;
  justify-content: center;
  gap: 16px;
  margin-bottom: 32px;
}

.hint code {
  background: var(--bg-secondary);
  padding: 2px 8px;
  border-radius: var(--radius-sm);
  color: var(--primary-color);
  font-family: 'Consolas', 'Monaco', monospace;
}
</style>
