<template>
  <div class="tool-timeline">
    <div v-for="(step, i) in steps" :key="i" class="timeline-step">
      <!-- 左侧序号 + 图标 -->
      <div class="step-left">
        <div class="step-num" :class="stepClass(step)">
          <el-icon v-if="step.type === 'thought'"><Loading v-if="i === steps.length - 1" /><ChatLineRound v-else /></el-icon>
          <el-icon v-else-if="step.type === 'tool_call'"><Tools /></el-icon>
          <el-icon v-else-if="step.type === 'tool_result'"><CircleCheck v-if="step.ok" /><CircleClose v-else /></el-icon>
          <el-icon v-else><Document /></el-icon>
        </div>
        <div v-if="i < steps.length - 1" class="step-line" />
      </div>

      <!-- 右侧内容 -->
      <div class="step-content">
        <div class="step-label">
          <span v-if="step.type === 'thought'" class="step-type">思考</span>
          <span v-else-if="step.type === 'tool_call'" class="step-type">调用 {{ step.name }}</span>
          <span v-else-if="step.type === 'tool_result'" class="step-type">
            {{ step.name }} · {{ step.ok ? '成功' : '失败' }}
          </span>
          <span v-else class="step-type">{{ step.type }}</span>
        </div>

        <!-- 思考内容 -->
        <div v-if="step.type === 'thought' && step.content" class="step-body thought">
          {{ step.content }}
        </div>

        <!-- 工具调用参数 -->
        <div v-if="step.type === 'tool_call'" class="step-body args">
          <code class="args-json">{{ formatJson(step.arguments) }}</code>
        </div>

        <!-- 工具结果 -->
        <div v-if="step.type === 'tool_result'" class="step-body result">
          <pre class="result-text">{{ formatResult(step.result) }}</pre>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ChatLineRound, CircleCheck, CircleClose, Document, Loading, Tools } from '@element-plus/icons-vue'

interface TimelineStep {
  type: 'thought' | 'tool_call' | 'tool_result' | 'answer' | 'error' | 'other'
  step?: number
  name?: string
  arguments?: Record<string, any>
  content?: string
  ok?: boolean
  result?: any
}

const props = defineProps<{ steps: TimelineStep[] }>()

function stepClass(step: TimelineStep): string {
  if (step.type === 'thought') return 'step-thought'
  if (step.type === 'tool_call') return 'step-tool'
  if (step.type === 'tool_result') return step.ok ? 'step-ok' : 'step-fail'
  return 'step-other'
}

function formatJson(args?: Record<string, any>): string {
  if (!args) return ''
  return JSON.stringify(args, null, 2)
}

function formatResult(r: any): string {
  if (r === undefined || r === null) return ''
  if (typeof r === 'string') return r.slice(0, 500)
  return JSON.stringify(r, null, 2).slice(0, 500)
}
</script>

<style lang="scss" scoped>
.tool-timeline {
  display: flex;
  flex-direction: column;
  gap: 0;
  padding: 8px 0;
}

.timeline-step {
  display: flex;
  gap: 12px;
  align-items: stretch;
}

.step-left {
  display: flex;
  flex-direction: column;
  align-items: center;
  flex-shrink: 0;
  width: 28px;
}

.step-num {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: 14px;
  flex-shrink: 0;
  transition: all 0.2s;
}
.step-thought { background: var(--info-color, #909399); }
.step-tool { background: var(--primary-color); }
.step-ok { background: var(--success-color, #10b981); }
.step-fail { background: var(--danger-color, #f56c6c); }
.step-other { background: var(--text-muted, #909399); }

.step-line {
  flex: 1;
  width: 2px;
  background: var(--border-color, #ebeef5);
  margin: 4px 0;
  min-height: 12px;
}

.step-content {
  flex: 1;
  padding-bottom: 12px;
}

.step-label {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 4px;
}
.step-type {
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
}

.step-body {
  background: var(--bg-secondary);
  border-radius: var(--radius-sm);
  padding: 6px 10px;
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  line-height: 1.5;
  word-break: break-word;
}
.step-body.thought { font-style: italic; }
.step-body.args { padding: 4px 0; background: transparent; }
.args-json {
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 12px;
  color: var(--primary-color);
  background: var(--bg-tertiary);
  padding: 6px 8px;
  border-radius: var(--radius-sm);
  display: block;
  white-space: pre-wrap;
  word-break: break-word;
}
.step-body.result { padding: 8px 10px; }
.result-text {
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 12px;
  color: var(--text-secondary);
  white-space: pre-wrap;
  word-break: break-word;
  margin: 0;
  max-height: 200px;
  overflow-y: auto;
}
</style>
