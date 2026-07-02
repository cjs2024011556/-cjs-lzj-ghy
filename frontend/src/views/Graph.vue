<template>
  <PageContainer>
    <SectionTitle title="🕸️ 故障图谱" icon="Share" badge="创新" badge-type="warning" />

    <el-card class="control-card fade-in">
      <div class="control-bar">
        <el-input
          v-model="keywords"
          placeholder="输入关键词（如：焊接 虚焊 AGV 电池）"
          style="width: 360px"
          size="large"
          clearable
          @keyup.enter="searchRelated"
        />
        <el-button type="primary" size="large" :loading="loading" @click="searchRelated">
          <el-icon><Search /></el-icon>
          查询相关节点
        </el-button>
        <el-button size="large" @click="loadFullGraph">
          <el-icon><FullScreen /></el-icon>
          整图浏览
        </el-button>
        <el-button size="large" @click="rebuildGraph">
          <el-icon><Refresh /></el-icon>
          重建图谱
        </el-button>
        <div class="stats-info">
          <el-tag type="info" effect="dark">节点 {{ stats.total_nodes || '—' }}</el-tag>
          <el-tag type="success" effect="dark">关系 {{ stats.total_edges || '—' }}</el-tag>
        </div>
      </div>
    </el-card>

    <!-- 图例 -->
    <div class="legend">
      <el-tag color="#00d4ff" effect="dark" size="small">设备</el-tag>
      <el-tag color="#ffb84d" effect="dark" size="small">部件</el-tag>
      <el-tag color="#ff4757" effect="dark" size="small">故障</el-tag>
      <el-tag color="#00d97e" effect="dark" size="small">案例</el-tag>
      <el-tag color="#a855f7" effect="dark" size="small">SOP</el-tag>
      <el-tag color="#94a3b8" effect="dark" size="small">工具</el-tag>
    </div>

    <!-- 图谱画布 -->
    <el-card class="graph-card">
      <div ref="graphContainer" class="graph-canvas"></div>
      <div v-if="!loading && !hasData" class="empty-tip">
        <EmptyState
          title="暂无图谱数据"
          description="请输入关键词查询，或点击'整图浏览'加载默认数据"
          type="data"
        />
      </div>
    </el-card>

    <!-- 节点详情 -->
    <el-card v-if="selectedNode" class="detail-card fade-in">
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center">
          <span>
            <el-tag :color="selectedNode.color" effect="dark" style="margin-right: 8px">
              {{ selectedNode.type }}
            </el-tag>
            <span style="font-size: 16px; font-weight: 600">{{ selectedNode.label }}</span>
          </span>
          <el-button text @click="selectedNode = null">
            <el-icon><Close /></el-icon>
          </el-button>
        </div>
      </template>
      <el-descriptions :column="2" border>
        <el-descriptions-item label="节点 ID">{{ selectedNode.id }}</el-descriptions-item>
        <el-descriptions-item label="度数">{{ selectedNode.value }}</el-descriptions-item>
        <el-descriptions-item v-if="selectedNode.title" label="描述" :span="2">
          {{ selectedNode.title }}
        </el-descriptions-item>
      </el-descriptions>
    </el-card>
  </PageContainer>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, FullScreen, Refresh, Close } from '@element-plus/icons-vue'
import {
  visualizeGraph,
  findRelated,
  getGraphStats,
  buildGraph,
  type GraphData,
  type GraphStats,
} from '@/api/graph'
import PageContainer from '@/components/base/PageContainer.vue'
import SectionTitle from '@/components/base/SectionTitle.vue'
import EmptyState from '@/components/base/EmptyState.vue'

const keywords = ref('焊接 虚焊')
const loading = ref(false)
const hasData = ref(false)
const stats = ref<GraphStats>({ total_nodes: 0, total_edges: 0, node_types: {}, rel_types: {} })
const selectedNode = ref<any>(null)

const graphContainer = ref<HTMLElement | null>(null)
let visNetwork: any = null
let visData = { nodes: [] as any[], edges: [] as any[] }

async function loadVisLib() {
  // 动态加载 vis-network CDN
  if ((window as any).vis) return
  await new Promise<void>((resolve, reject) => {
    const css = document.createElement('link')
    css.rel = 'stylesheet'
    css.href = 'https://unpkg.com/vis-network@9.1.9/styles/vis-network.min.css'
    document.head.appendChild(css)
    const script = document.createElement('script')
    script.src = 'https://unpkg.com/vis-network@9.1.9/standalone/umd/vis-network.min.js'
    script.onload = () => resolve()
    script.onerror = () => reject(new Error('vis-network 加载失败'))
    document.head.appendChild(script)
  })
}

async function renderGraph(data: GraphData) {
  await loadVisLib()
  const vis = (window as any).vis
  if (!graphContainer.value) return

  visData = data
  const nodes = new vis.DataSet(
    data.nodes.map((n) => ({
      id: n.id,
      label: n.label.length > 16 ? n.label.slice(0, 16) + '…' : n.label,
      color: { background: n.color, border: '#fff', highlight: { background: n.color, border: '#00d4ff' } },
      title: n.title,
      value: n.value,
      font: { color: '#fff', size: 14, face: 'sans-serif' },
      shape: n.type === 'Case' ? 'box' : n.type === 'SOP' ? 'ellipse' : 'dot',
    })),
  )
  const edges = new vis.DataSet(
    data.edges.map((e) => ({
      from: e.source,
      to: e.target,
      label: e.label,
      arrows: 'to',
      color: { color: '#475569', highlight: '#00d4ff' },
      font: { color: '#94a3b8', size: 10, strokeWidth: 0, align: 'middle' },
      smooth: { type: 'continuous' },
    })),
  )

  const options = {
    nodes: { borderWidth: 2, shadow: false },
    edges: { width: 1.5, smooth: { type: 'continuous' } },
    physics: {
      enabled: true,
      barnesHut: { gravitationalConstant: -8000, centralGravity: 0.3, springLength: 95, springConstant: 0.04, damping: 0.09 },
      stabilization: { iterations: 200 },
    },
    interaction: { hover: true, tooltipDelay: 100, zoomView: true, dragView: true },
    layout: { improvedLayout: true },
  }

  if (visNetwork) {
    visNetwork.setData({ nodes, edges })
  } else {
    visNetwork = new vis.Network(graphContainer.value, { nodes, edges }, options)
    visNetwork.on('selectNode', (params: any) => {
      const nodeId = params.nodes[0]
      const node = data.nodes.find((n) => n.id === nodeId)
      if (node) selectedNode.value = node
    })
  }
  hasData.value = true
}

async function searchRelated() {
  if (!keywords.value.trim()) {
    ElMessage.warning('请输入关键词')
    return
  }
  loading.value = true
  try {
    const kws = keywords.value.trim().split(/[\s,，]+/)
    const data = await findRelated(kws, 2)
    if (data.nodes.length === 0) {
      ElMessage.info('未找到相关节点')
      return
    }
    await renderGraph(data)
    ElMessage.success(`找到 ${data.matched_count} 个匹配节点，子图共 ${data.nodes.length} 节点`)
  } catch (e) {
    // ignore
  } finally {
    loading.value = false
  }
}

async function loadFullGraph() {
  loading.value = true
  try {
    const data = await visualizeGraph(100)
    await renderGraph(data)
    ElMessage.success(`整图加载完成: ${data.nodes.length} 节点`)
  } catch (e) {
    // ignore
  } finally {
    loading.value = false
  }
}

async function rebuildGraph() {
  try {
    await ElMessageBox.confirm('将从内置数据重建故障图谱（约 5-10 秒），是否继续？', '重建图谱', {
      type: 'warning',
    })
    loading.value = true
    await buildGraph()
    await loadStats()
    ElMessage.success('图谱重建完成')
  } catch (e) {
    // 取消
  } finally {
    loading.value = false
  }
}

async function loadStats() {
  try {
    stats.value = await getGraphStats()
  } catch (e) {
    // ignore
  }
}

onMounted(async () => {
  await loadStats()
  await nextTick()
  // 默认查询一次
  await searchRelated()
})

onUnmounted(() => {
  if (visNetwork) {
    visNetwork.destroy()
    visNetwork = null
  }
})
</script>

<style lang="scss" scoped>
.control-card {
  background: var(--bg-tertiary);
  margin-bottom: 16px;
}
.control-bar {
  display: flex;
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
}
.stats-info {
  margin-left: auto;
  display: flex;
  gap: 8px;
}
.legend {
  margin-bottom: 12px;
  display: flex;
  gap: 8px;
}
.graph-card {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  min-height: 600px;
}
.graph-canvas {
  width: 100%;
  height: 600px;
  background:
    radial-gradient(ellipse at center, var(--bg-tertiary) 0%, var(--bg-primary) 100%),
    linear-gradient(rgba(var(--primary-rgb), 0.02) 1px, transparent 1px),
    linear-gradient(90deg, rgba(var(--primary-rgb), 0.02) 1px, transparent 1px);
  background-size: 100% 100%, 24px 24px, 24px 24px;
  background-blend-mode: normal, overlay, overlay;
  border-radius: var(--radius-md);
  border: 1px solid var(--border-color);
  box-shadow: inset 0 0 24px rgba(0, 0, 0, 0.3);
  position: relative;
  overflow: hidden;
}

// U.3.3 vis-network tooltip 暗色化
:deep(.vis-tooltip) {
  background: var(--bg-secondary) !important;
  border: 1px solid var(--primary-color) !important;
  color: var(--text-primary) !important;
  font-family: inherit !important;
  font-size: var(--font-size-sm) !important;
  padding: 8px 12px !important;
  border-radius: var(--radius-sm) !important;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.5) !important;
  max-width: 300px;
  white-space: pre-wrap;
}
.empty-tip {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
}
.detail-card {
  margin-top: 16px;
  background: var(--bg-tertiary);
}
</style>
