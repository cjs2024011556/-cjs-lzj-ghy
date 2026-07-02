<template>
  <div class="overview-panel">
    <!-- 顶部 4 指标卡 -->
    <el-row :gutter="16" class="stat-row">
      <el-col :xs="12" :sm="6" v-for="s in stats" :key="s.label">
        <StatCard
          :value="s.value"
          :label="s.label"
          :icon="s.icon"
          :color="s.color"
          :trend="s.trend"
          :trend-value="s.trendValue"
        />
      </el-col>
    </el-row>

    <!-- 4 图 2x2 网格 -->
    <el-row :gutter="16" class="chart-row">
      <el-col :xs="24" :lg="12">
        <el-card shadow="never" class="chart-card">
          <LineChart :x-axis="trendData.xAxis" :series="trendData.series" title="近 7 天活动趋势" />
        </el-card>
      </el-col>
      <el-col :xs="24" :lg="12">
        <el-card shadow="never" class="chart-card">
          <PieChart :data="distributionData" title="设备类型分布" />
        </el-card>
      </el-col>
      <el-col :xs="24" :lg="12">
        <el-card shadow="never" class="chart-card">
          <GaugeChart :value="healthScore" title="OEE 综合指标" color="success" />
        </el-card>
      </el-col>
      <el-col :xs="24" :lg="12">
        <el-card shadow="never" class="chart-card">
          <HeatmapChart
            :data="heatmapData"
            :x-categories="heatmapX"
            :y-categories="heatmapY"
            title="故障时段分布"
          />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import StatCard from '@/components/base/StatCard.vue'
import LineChart from '@/components/Charts/LineChart.vue'
import PieChart from '@/components/Charts/PieChart.vue'
import GaugeChart from '@/components/Charts/GaugeChart.vue'
import HeatmapChart from '@/components/Charts/HeatmapChart.vue'

// ---- 顶部统计卡（mock 演示数据）----
const stats = ref([
  { label: '今日检索', value: 142, icon: 'Search', color: 'primary', trend: 'up' as const, trendValue: '+12%' },
  { label: '已审核案例', value: 86, icon: 'Document', color: 'success', trend: 'up' as const, trendValue: '+8%' },
  { label: '待审核', value: 12, icon: 'Tickets', color: 'warning' },
  { label: 'OEE 设备效率', value: 87.3, suffix: '%', icon: 'Cpu', color: 'info', trend: 'up' as const, trendValue: '+2.1%' },
])

// ---- 趋势图（近 7 天案例 + 检索）----
const trendData = ref({
  xAxis: ['6/20', '6/21', '6/22', '6/23', '6/24', '6/25', '6/26'],
  series: [
    { name: '检索次数', data: [88, 102, 95, 128, 110, 132, 142] },
    { name: '案例提交', data: [3, 5, 2, 6, 4, 7, 5] },
  ],
})

// ---- 设备类型分布（饼图）----
const distributionData = ref([
  { name: '焊接机器人', value: 35 },
  { name: 'AGV', value: 25 },
  { name: '冲压机', value: 22 },
  { name: '机器视觉', value: 18 },
])

// ---- OEE 综合指标（仪表盘）----
const healthScore = ref(87.3)

// ---- 故障时段热力图（设备 × 时段）----
const heatmapX = ref(['00', '04', '08', '12', '16', '20'])
const heatmapY = ref(['焊接机器人', 'AGV', '冲压机', '视觉系统'])

const heatmapData = ref([
  // 焊接机器人 — 主要在白班（08-16）出现故障
  { x: '08', y: '焊接机器人', value: 28 },
  { x: '12', y: '焊接机器人', value: 45 },
  { x: '16', y: '焊接机器人', value: 32 },
  { x: '20', y: '焊接机器人', value: 8 },
  // AGV — 24h 作业，分布较均匀
  { x: '00', y: 'AGV', value: 5 },
  { x: '04', y: 'AGV', value: 3 },
  { x: '08', y: 'AGV', value: 12 },
  { x: '12', y: 'AGV', value: 18 },
  { x: '16', y: 'AGV', value: 15 },
  { x: '20', y: 'AGV', value: 9 },
  // 冲压机 — 高负荷班次
  { x: '08', y: '冲压机', value: 38 },
  { x: '12', y: '冲压机', value: 52 },
  { x: '16', y: '冲压机', value: 41 },
  // 视觉系统 — 集中在白班
  { x: '08', y: '视觉系统', value: 15 },
  { x: '12', y: '视觉系统', value: 22 },
  { x: '16', y: '视觉系统', value: 18 },
])
</script>

<style lang="scss" scoped>
.overview-panel {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
}

.stat-row {
  margin-bottom: 4px;
}

.chart-row {
  row-gap: var(--spacing-md);
}

.chart-card {
  background: var(--bg-secondary) !important;
  border: 1px solid var(--border-color) !important;
  padding: 8px 4px;

  :deep(.el-card__body) {
    padding: 8px;
  }
}
</style>
