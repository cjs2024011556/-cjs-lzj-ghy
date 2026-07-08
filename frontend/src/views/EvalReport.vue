<template>
  <PageContainer>
    <SectionTitle title="评测报告" icon="DataAnalysis" badge="C" badge-type="primary" />

    <el-row :gutter="16" class="mb-md">
      <el-col :xs="24" :sm="12" :md="6" v-for="card in metricCards" :key="card.label">
        <StatCard
          :value="card.value"
          :label="card.label"
          :icon="card.icon"
          :color="card.color"
        />
      </el-col>
    </el-row>

    <el-card class="mb-md" shadow="never">
      <template #header>
        <div class="card-header">
          <el-icon><Histogram /></el-icon>
          <span>核心指标</span>
          <div class="header-actions">
            <el-button text :loading="running" @click="onRun">
              <el-icon><Refresh /></el-icon>
              运行评测
            </el-button>
            <el-button text @click="onLoad">
              <el-icon><Document /></el-icon>
              加载报告
            </el-button>
          </div>
        </div>
      </template>

      <div v-if="!report" class="empty-state">
        <el-empty description="还没有评测报告，点击「运行评测」生成" />
      </div>
      <div v-else>
        <el-row :gutter="16">
          <el-col :xs="24" :md="12">
            <div ref="radarRef" class="chart-area" style="height: 320px"></div>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-table :data="failureRows" stripe size="small" style="width: 100%">
              <el-table-column label="问题" min-width="200" show-overflow-tooltip prop="query" />
              <el-table-column label="状态" width="80" align="center">
                <template #default="{ row }">
                  <el-tag v-if="row.hit" type="success" size="small">命中</el-tag>
                  <el-tag v-else type="danger" size="small">未命中</el-tag>
                </template>
              </el-table-column>
              <el-table-column label="首命中位" width="80" align="center" prop="first_relevant_rank">
                <template #default="{ row }">
                  <span v-if="row.first_relevant_rank">#{{ row.first_relevant_rank }}</span>
                  <span v-else style="color: var(--text-muted)">—</span>
                </template>
              </el-table-column>
            </el-table>
          </el-col>
        </el-row>
      </div>
    </el-card>

    <el-card v-if="report" shadow="never">
      <template #header>
        <div class="card-header">
          <el-icon><List /></el-icon>
          <span>评测详情（{{ report.total }} 题）</span>
        </div>
      </template>
      <el-table :data="report.items" stripe size="small" style="width: 100%">
        <el-table-column label="问题" min-width="240" show-overflow-tooltip prop="query" />
        <el-table-column label="命中" width="80" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.hit" type="success" size="small">✓</el-tag>
            <el-tag v-else type="danger" size="small">✗</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="首命中位" width="100" align="center" prop="first_relevant_rank">
          <template #default="{ row }">
            <span v-if="row.first_relevant_rank">#{{ row.first_relevant_rank }}</span>
            <span v-else style="color: var(--text-muted)">—</span>
          </template>
        </el-table-column>
        <el-table-column label="NDCG" width="100" align="center" prop="ndcg">
          <template #default="{ row }">
            {{ (row.ndcg * 100).toFixed(1) }}%
          </template>
        </el-table-column>
        <el-table-column label="页码引用" width="100" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.citation_correct === true" type="success" size="small">正确</el-tag>
            <el-tag v-else-if="row.citation_correct === false" type="danger" size="small">错误</el-tag>
            <span v-else style="color: var(--text-muted)">—</span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </PageContainer>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import {
  DataAnalysis, Document, Histogram, List, Refresh,
} from '@element-plus/icons-vue'
import PageContainer from '@/components/base/PageContainer.vue'
import SectionTitle from '@/components/base/SectionTitle.vue'
import StatCard from '@/components/base/StatCard.vue'
import { runEval, getEvalReport, type EvalReport } from '@/api/chat'

const report = ref<EvalReport | null>(null)
const running = ref(false)
const radarRef = ref<HTMLDivElement>()

const metricCards = computed(() => {
  if (!report.value) {
    return [
      { label: '题目数', value: '—', icon: 'List', color: 'primary' as const },
      { label: 'Hit Rate@5', value: '—', icon: 'Aim', color: 'success' as const },
      { label: 'MRR', value: '—', icon: 'TrendCharts', color: 'info' as const },
      { label: 'NDCG@5', value: '—', icon: 'DataLine', color: 'warning' as const },
    ]
  }
  const m = report.value.metrics
  return [
    { label: '题目数', value: String(m.total), icon: 'List', color: 'primary' as const },
    { label: 'Hit Rate@5', value: percent(m.hit_rate_at_5), icon: 'Aim', color: 'success' as const },
    { label: 'MRR', value: percent(m.mrr), icon: 'TrendCharts', color: 'info' as const },
    { label: 'NDCG@5', value: percent(m.ndcg_at_5), icon: 'DataLine', color: 'warning' as const },
  ]
})

const failureRows = computed(() => {
  if (!report.value) return []
  return report.value.items.filter((it) => !it.hit)
})

function percent(v: number): string {
  return `${(v * 100).toFixed(1)}%`
}

async function onRun() {
  running.value = true
  try {
    report.value = await runEval(5)
    ElMessage.success(`评测完成：${report.value.total} 题`)
    await nextTick()
    renderRadar()
  } catch (e) {
    ElMessage.error('评测失败: ' + (e as Error).message)
  } finally {
    running.value = false
  }
}

async function onLoad() {
  try {
    report.value = await getEvalReport()
    await nextTick()
    renderRadar()
  } catch (e: any) {
    ElMessage.warning(e?.message || '暂无报告，请先运行评测')
  }
}

function renderRadar() {
  if (!radarRef.value || !report.value) return
  import('echarts').then((echarts) => {
    const m = report.value!.metrics
    const option = {
      tooltip: { trigger: 'item' },
      radar: {
        indicator: [
          { name: 'Hit@5', max: 1 },
          { name: 'Hit@10', max: 1 },
          { name: 'MRR', max: 1 },
          { name: 'NDCG@5', max: 1 },
          { name: 'NDCG@10', max: 1 },
          { name: 'Citation', max: 1 },
        ],
        splitArea: { areaStyle: { color: ['#fafafa', '#fff'] } },
      },
      series: [{
        type: 'radar',
        data: [{
          value: [m.hit_rate_at_5, m.hit_rate_at_10, m.mrr, m.ndcg_at_5, m.ndcg_at_10, m.citation_accuracy ?? 0],
          name: '当前',
          areaStyle: { color: 'rgba(64, 158, 255, 0.2)' },
          lineStyle: { color: '#409eff', width: 2 },
          itemStyle: { color: '#409eff' },
        }],
      }],
    }
    const chart = echarts.init(radarRef.value)
    chart.setOption(option)
  })
}

watch(report, () => nextTick(renderRadar))
onMounted(onLoad)
</script>

<style lang="scss" scoped>
.card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: var(--font-weight-semibold);

  .header-actions {
    margin-left: auto;
    display: flex;
    gap: 4px;
  }
}

.empty-state {
  padding: 40px 0;
}
</style>
