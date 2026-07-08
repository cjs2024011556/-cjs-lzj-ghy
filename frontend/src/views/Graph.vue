<template>
  <PageContainer with-grid>
    <SectionTitle title="故障图谱" icon="Share" badge="创新杀手锏" badge-type="warning">
      <template #sub>
        以图谱方式展示设备、部件、故障、案例、SOP、工具之间的关联关系，支持关键词查询、节点联动探索与专业分析洞察。
      </template>
    </SectionTitle>

    <!-- 主区：左 320px 过滤面板 + 右主区 -->
    <div class="graph-stage">
      <!-- 左侧：搜索 + 过滤 + 操作 + 统计 -->
      <aside class="control-panel">
        <!-- 搜索 -->
        <div class="panel-section">
          <div class="section-title">
            <el-icon><Search /></el-icon>
            <span>关键词搜索</span>
          </div>
          <el-input
            v-model="keywords"
            placeholder="焊接 虚焊 / AGV 电池 / FANUC SRVO-023"
            clearable
            @keyup.enter="searchRelated"
          />
          <div class="suggestion-chips">
            <div
              v-for="s in suggestionQueries"
              :key="s"
              class="suggestion-chip"
              @click="quickSearch(s)"
            >
              {{ s }}
            </div>
          </div>
          <el-button
            class="primary-action"
            type="primary"
            size="default"
            :loading="loading.search"
            @click="searchRelated"
          >
            <el-icon><Search /></el-icon>
            查询相关节点
          </el-button>
        </div>

        <!-- 图谱参数 -->
        <div class="panel-section">
          <div class="section-title">
            <el-icon><Setting /></el-icon>
            <span>图谱参数</span>
          </div>

          <div class="param-row">
            <div class="param-label">
              <span>展开层数 Max-Hops</span>
              <span class="param-value">{{ maxHops }}</span>
            </div>
            <el-slider v-model="maxHops" :min="1" :max="3" :step="1" :show-tooltip="false" />
          </div>

          <div class="param-row">
            <div class="param-label">
              <span>整图节点上限</span>
              <span class="param-value">{{ maxNodes }}</span>
            </div>
            <el-slider v-model="maxNodes" :min="50" :max="500" :step="50" :show-tooltip="false" />
          </div>

          <div class="param-row">
            <div class="param-label">
              <span>节点类型</span>
              <el-link v-if="nodeTypeFilter.length" type="primary" :underline="false" @click="nodeTypeFilter = []">
                清空
              </el-link>
            </div>
            <div class="type-chips">
              <el-checkbox-group v-model="nodeTypeFilter" class="chip-group">
                <el-checkbox v-for="t in nodeTypeDefs" :key="t.type" :value="t.type">
                  <span class="chip-dot" :style="{ background: t.color }"></span>
                  {{ t.label }}
                </el-checkbox>
              </el-checkbox-group>
            </div>
          </div>

          <div class="param-row">
            <div class="param-label">
              <span>关系类型</span>
              <el-link v-if="relTypeFilter.length" type="primary" :underline="false" @click="relTypeFilter = []">
                清空
              </el-link>
            </div>
            <div class="rel-chips">
              <el-tag
                v-for="rt in relTypeDefs"
                :key="rt.type"
                :type="relTypeFilter.includes(rt.type) ? 'primary' : 'info'"
                :effect="relTypeFilter.includes(rt.type) ? 'dark' : 'plain'"
                class="rel-chip"
                @click="toggleRelType(rt.type)"
              >
                {{ rt.type }}
              </el-tag>
            </div>
          </div>

          <div class="param-row">
            <div class="param-label"><span>布局算法</span></div>
            <el-radio-group v-model="layoutAlgo" class="layout-radio">
              <el-radio-button value="force">力学</el-radio-button>
              <el-radio-button value="circular">环形</el-radio-button>
              <el-radio-button value="none">固定</el-radio-button>
            </el-radio-group>
          </div>
        </div>

        <!-- 快捷操作 -->
        <div class="panel-section">
          <div class="section-title">
            <el-icon><Operation /></el-icon>
            <span>快捷操作</span>
          </div>
          <div class="action-buttons">
            <el-button :loading="loading.full" @click="loadFullGraph">
              <el-icon><FullScreen /></el-icon>
              整图浏览
            </el-button>
            <el-button :loading="loading.rebuild" @click="rebuildGraph">
              <el-icon><Refresh /></el-icon>
              重建图谱
            </el-button>
            <el-button :disabled="!hasData" @click="exportGraphPNG">
              <el-icon><Picture /></el-icon>
              导出 PNG
            </el-button>
            <el-button :disabled="!hasData" @click="exportGraphJSON">
              <el-icon><Document /></el-icon>
              导出 JSON
            </el-button>
          </div>
        </div>

        <!-- 统计 -->
        <div class="panel-section stats-section">
          <div class="section-title">
            <el-icon><DataAnalysis /></el-icon>
            <span>图谱统计</span>
          </div>
          <div class="stats-grid">
            <div class="stat-cell">
              <div class="stat-num">{{ stats.total_nodes || '—' }}</div>
              <div class="stat-label">节点</div>
            </div>
            <div class="stat-cell">
              <div class="stat-num">{{ stats.total_edges || '—' }}</div>
              <div class="stat-label">关系</div>
            </div>
            <div class="stat-cell">
              <div class="stat-num">{{ stats.density?.toFixed ? stats.density.toFixed(3) : '—' }}</div>
              <div class="stat-label">密度</div>
            </div>
          </div>
          <div v-if="Object.keys(stats.node_types || {}).length" class="stats-breakdown">
            <div
              v-for="(count, type) in stats.node_types"
              :key="type"
              class="breakdown-row"
            >
              <span class="br-dot" :style="{ background: colorOfType(type) }"></span>
              <span class="br-type">{{ type }}</span>
              <span class="br-count">{{ count }}</span>
            </div>
          </div>
        </div>
      </aside>

      <!-- 右侧：工具栏 + 图例 + 画布 + 分析面板 -->
      <main class="graph-main">
        <div class="toolbar">
          <div class="toolbar-left">
            <el-tag v-if="currentView === 'search'" type="primary" effect="dark">
              <el-icon><Aim /></el-icon>
              关键词子图：匹配 {{ matchedCount }} / 共 {{ visData.nodes.length }} 节点
            </el-tag>
            <el-tag v-else-if="currentView === 'full'" type="success" effect="dark">
              <el-icon><DataLine /></el-icon>
              整图视图：{{ visData.nodes.length }} 节点 / {{ visData.edges.length }} 关系
            </el-tag>
            <el-tag v-else-if="currentView === 'subgraph'" type="warning" effect="dark">
              <el-icon><Connection /></el-icon>
              从「{{ subgraphSeedLabel }}」展开 1-hop 子图
            </el-tag>
            <span v-if="(nodeTypeFilter.length || relTypeFilter.length) && hasData" class="filter-hint">
              <el-icon><Filter /></el-icon>
              已过滤：{{ nodeTypeFilter.length + relTypeFilter.length }} 项
            </span>
          </div>
          <div class="toolbar-right">
            <el-button text :disabled="!hasData" @click="fitView">
              <el-icon><FullScreen /></el-icon>
              自适应
            </el-button>
            <el-button text :disabled="!hasData" @click="reLayout">
              <el-icon><Refresh /></el-icon>
              重新布局
            </el-button>
            <el-button text @click="loadStats">
              <el-icon><DataAnalysis /></el-icon>
              刷新统计
            </el-button>
          </div>
        </div>

        <!-- 分组图例（节点 + 关系） -->
        <div class="legend-bar">
          <div class="legend-group">
            <span class="legend-group-title">节点</span>
            <span
              v-for="t in nodeTypeDefs"
              :key="t.type"
              class="legend-item"
              :class="{
                disabled: nodeTypeFilter.length && !nodeTypeFilter.includes(t.type),
                active: nodeTypeFilter.includes(t.type),
              }"
              @click="toggleNodeType(t.type)"
            >
              <span class="legend-dot" :style="{ background: t.color }"></span>
              {{ t.label }}
              <span class="legend-count">{{ stats.node_types?.[t.type] || 0 }}</span>
            </span>
          </div>
          <div class="legend-group">
            <span class="legend-group-title">关系</span>
            <span
              v-for="rt in relTypeDefs"
              :key="rt.type"
              class="legend-item rel"
              :class="{
                disabled: relTypeFilter.length && !relTypeFilter.includes(rt.type),
                active: relTypeFilter.includes(rt.type),
              }"
              @click="toggleRelType(rt.type)"
            >
              {{ rt.type }}
              <span class="legend-count">{{ stats.rel_types?.[rt.type] || 0 }}</span>
            </span>
          </div>
        </div>

        <!-- 画布容器 -->
        <div class="canvas-wrap">
          <v-chart
            v-if="hasData"
            ref="chartRef"
            class="graph-canvas"
            :option="chartOption"
            :autoresize="true"
            :init-options="chartInitOptions"
            @click="onChartClick"
            @mouseover="onChartHover"
            @mouseout="onChartLeave"
          />

          <!-- 加载态：3 步进度骨架屏 -->
          <div v-if="loadingAny && !hasData" class="canvas-state layer-loading">
            <div class="skeleton-graph">
              <div class="skel-step">
                <div class="step-icon"><el-icon :size="20"><Loading /></el-icon></div>
                <span>正在加载图谱元数据</span>
              </div>
              <div class="skel-step">
                <div class="step-icon"><el-icon :size="20"><Connection /></el-icon></div>
                <span>布局算法：{{ layoutAlgoText }} · {{ visData.nodes.length || 0 }} 节点</span>
              </div>
              <div class="skel-step">
                <div class="step-icon"><el-icon :size="20"><DataAnalysis /></el-icon></div>
                <span>力导向计算收敛…</span>
              </div>
              <div class="skel-bar">
                <div class="skel-bar-fill"></div>
              </div>
            </div>
          </div>

          <!-- 错误态 -->
          <div v-if="errorMessage" class="canvas-state">
            <ErrorState
              title="图谱加载失败"
              :description="errorMessage"
              @retry="retryAfterError"
            />
          </div>

          <!-- 空态（首次进入） -->
          <div v-if="!loadingAny && !hasData && !errorMessage" class="canvas-state empty-state-wrap">
            <div class="empty-card">
              <div class="empty-icon-big"><el-icon :size="48"><Share /></el-icon></div>
              <div class="empty-title">开始探索故障图谱</div>
              <div class="empty-desc">输入关键词查询相关节点，或浏览整图。所有节点与关系来自内置案例库与 SOP 库。</div>
              <ol class="empty-steps">
                <li>在左侧输入关键词（如「焊接 虚焊」）</li>
                <li>或点击<strong>快捷建议</strong>直接查询</li>
                <li>点击节点查看详情，<strong>双击节点</strong>展开 1-hop 子图</li>
              </ol>
              <div class="empty-actions">
                <el-button type="primary" @click="searchRelated">
                  <el-icon><Search /></el-icon>
                  推荐示例：焊接 虚焊
                </el-button>
                <el-button @click="loadFullGraph">
                  <el-icon><FullScreen /></el-icon>
                  浏览整图
                </el-button>
              </div>
            </div>
          </div>

          <!-- 无匹配 -->
          <div v-if="!loadingAny && hasData && visData.nodes.length === 0" class="canvas-state">
            <EmptyState
              title="未找到匹配的节点"
              :description="`没有匹配「${lastKeywords}」的节点，换个关键词试试？`"
              type="search"
            >
              <template #action>
                <el-button type="primary" @click="loadFullGraph">
                  <el-icon><FullScreen /></el-icon>
                  浏览整图
                </el-button>
              </template>
            </EmptyState>
          </div>

          <!-- Hover 小卡片（自定义浮动预览，跨整个画布） -->
          <Teleport to="body">
            <Transition name="hover-fade">
              <div
                v-if="hoveredNode && hoverPos.x && hoverPos.y"
                class="hover-mini-card"
                :style="{ top: hoverPos.y + 'px', left: hoverPos.x + 'px' }"
              >
                <div class="hmc-header">
                  <span class="hmc-dot" :style="{ background: hoveredNode.color }"></span>
                  <span class="hmc-label">{{ hoveredNode.label }}</span>
                </div>
                <el-tag
                  :color="hoveredNode.color"
                  effect="dark"
                  size="small"
                  class="hmc-type-tag"
                >{{ hoveredNode.type }}</el-tag>
                <div class="hmc-meta">
                  <span class="hmc-meta-row">
                    <span class="hmc-meta-label">度数</span>
                    <span class="hmc-meta-value">{{ hoveredNode.value }}</span>
                  </span>
                  <span class="hmc-meta-row">
                    <span class="hmc-meta-label">ID</span>
                    <span class="hmc-meta-value mono">{{ hoveredNode.id }}</span>
                  </span>
                </div>
                <div class="hmc-tip">💡 单击查看详情 / 双击展开子图</div>
              </div>
            </Transition>
          </Teleport>
        </div>

        <!-- 图谱分析面板（企业用户视角的洞察） -->
        <section class="analytics-panel" v-if="hasData && !loadingAny">
          <div class="analytics-header" @click="analyticsOpen = !analyticsOpen">
            <div class="analytics-header-left">
              <el-icon class="analytics-icon"><DataAnalysis /></el-icon>
              <span class="analytics-title">图谱分析</span>
              <span class="analytics-sub">企业用户视角：中心度 / 连通性 / 关键路径</span>
            </div>
            <el-icon :class="{ rotated: analyticsOpen }" class="analytics-toggle"><ArrowDown /></el-icon>
          </div>

          <Transition name="collapse">
            <div v-show="analyticsOpen" class="analytics-body">
              <div v-if="loading.analytics" class="analytics-loading">
                <el-icon class="is-loading"><Loading /></el-icon>
                <span>正在计算图谱分析指标…</span>
              </div>

              <div v-else-if="analytics" class="analytics-grid">
                <!-- 卡片 1：度中心度 Top 5 -->
                <div class="analytic-card">
                  <div class="card-title">
                    <el-icon><Trophy /></el-icon>
                    <span>度中心度 Top 5</span>
                  </div>
                  <div class="card-body centrality-list">
                    <div
                      v-for="(node, idx) in analytics.top_degree_centrality"
                      :key="node.id"
                      class="centrality-row"
                      @click="focusNodeFromAnalytic(node.id)"
                    >
                      <span class="rank-badge" :class="`rank-${idx + 1}`">{{ idx + 1 }}</span>
                      <span class="cn-dot" :style="{ background: node.color }"></span>
                      <span class="cn-label">{{ node.label }}</span>
                      <el-tag size="small" type="info" effect="plain" class="cn-type">{{ node.type }}</el-tag>
                      <div class="cn-bar-wrap">
                        <div
                          class="cn-bar"
                          :style="{
                            width: ((node.degree / maxDegree) * 100) + '%',
                            background: node.color,
                          }"
                        />
                      </div>
                      <span class="cn-degree">{{ node.degree }}</span>
                    </div>
                    <el-empty v-if="!analytics.top_degree_centrality.length" description="暂无数据" :image-size="50" />
                  </div>
                </div>

                <!-- 卡片 2：连通分量 -->
                <div class="analytic-card">
                  <div class="card-title">
                    <el-icon><Connection /></el-icon>
                    <span>连通分量</span>
                  </div>
                  <div class="card-body">
                    <div class="cc-summary">
                      <div class="cc-num">
                        <span class="n-value">{{ analytics.connected_components.count }}</span>
                        <span class="n-label">连通分量</span>
                      </div>
                      <div class="cc-num">
                        <span class="n-value">{{ analytics.connected_components.max_size }}</span>
                        <span class="n-label">最大分量（节点数）</span>
                      </div>
                    </div>
                    <div v-if="ccTotalVisual" class="cc-distribution">
                      <div
                        v-for="(count, label) in analytics.connected_components.sizes_distribution"
                        :key="label"
                        class="dist-row"
                      >
                        <span class="dist-label">{{ label }} 个节点</span>
                        <span class="dist-bar">
                          <span
                            class="dist-bar-fill"
                            :style="{ width: ccTotalVisual ? ((count / ccTotalVisual.max) * 100) + '%' : '0%' }"
                          />
                        </span>
                        <span class="dist-count">{{ count }}</span>
                      </div>
                    </div>
                  </div>
                </div>

                <!-- 卡片 3：节点类型密度 -->
                <div class="analytic-card">
                  <div class="card-title">
                    <el-icon><PieChart /></el-icon>
                    <span>节点类型分布</span>
                  </div>
                  <div class="card-body type-distribution">
                    <div
                      v-for="(count, type) in analytics.node_type_density"
                      :key="type"
                      class="type-row"
                      @click="focusNodeType(type)"
                    >
                      <span class="tr-dot" :style="{ background: colorOfType(type) }"></span>
                      <span class="tr-name">{{ type }}</span>
                      <span class="tr-count">{{ count }}</span>
                    </div>
                    <el-empty v-if="!Object.keys(analytics.node_type_density).length" description="暂无数据" :image-size="50" />
                  </div>
                </div>

                <!-- 卡片 4：关键路径示例 -->
                <div class="analytic-card path-card">
                  <div class="card-title">
                    <el-icon><Promotion /></el-icon>
                    <span>关键路径示例</span>
                    <el-tag size="small" type="warning" effect="plain">最大分量 · 长度 {{ analytics.shortest_path_sample?.length || '?' }}</el-tag>
                  </div>
                  <div class="card-body" v-if="analytics.shortest_path_sample">
                    <div class="path-flow">
                      <template v-for="(node, idx) in analytics.shortest_path_sample.path" :key="node.id">
                        <div class="path-step" :class="{ endpoint: idx === 0 || idx === analytics.shortest_path_sample.path.length - 1 }" @click="focusNodeFromAnalytic(node.id)">
                          <span class="ps-dot" :style="{ background: node.color }"></span>
                          <span class="ps-label">{{ node.label }}</span>
                          <span class="ps-type">{{ node.type }}</span>
                        </div>
                        <el-icon v-if="idx < analytics.shortest_path_sample.path.length - 1" class="path-arrow"><Right /></el-icon>
                      </template>
                    </div>
                    <div class="path-hint">
                      由 <strong>度数最低节点</strong> → <strong>度数最高节点</strong>（跨类型）BFS 最短路径
                    </div>
                  </div>
                  <el-empty v-else description="数据不足，无法计算关键路径" :image-size="60" />
                </div>
              </div>
            </div>
          </Transition>
        </section>
      </main>

      <!-- 节点详情抽屉（右侧滑入） -->
      <Transition name="drawer">
        <aside v-if="selectedNode" class="detail-drawer">
          <div class="drawer-header">
            <div class="drawer-title">
              <span class="node-dot" :style="{ background: selectedNode.color }"></span>
              <span>{{ selectedNode.label }}</span>
              <el-tag :color="selectedNode.color" effect="dark" size="small" class="node-type-tag">
                {{ selectedNode.type }}
              </el-tag>
            </div>
            <el-button text @click="closeDetail">
              <el-icon><Close /></el-icon>
            </el-button>
          </div>

          <div class="drawer-body">
            <section class="detail-section">
              <div class="section-title-small">基础信息</div>
              <el-descriptions :column="1" border size="small">
                <el-descriptions-item label="节点 ID">
                  <el-text class="mono-text" truncated>{{ selectedNode.id }}</el-text>
                </el-descriptions-item>
                <el-descriptions-item label="度数">{{ selectedNode.value }}</el-descriptions-item>
                <el-descriptions-item v-if="selectedNode.title" label="描述">
                  {{ selectedNode.title }}
                </el-descriptions-item>
              </el-descriptions>
            </section>

            <div v-if="loading.neighborhood" class="neighborhood-loading">
              <el-icon class="is-loading"><Loading /></el-icon>
              <span>加载邻居节点…</span>
            </div>

            <template v-else-if="neighborhood">
              <section class="detail-section">
                <div class="section-title-small">
                  邻居摘要
                  <el-tag size="small" type="primary" effect="dark">
                    {{ neighborhood.summary.total_unique_neighbors }} 唯一邻居
                  </el-tag>
                </div>
                <div class="neighbor-summary">
                  <div class="summary-cell">
                    <span class="sc-num">{{ neighborhood.summary.total_out }}</span>
                    <span class="sc-label">出边</span>
                  </div>
                  <div class="summary-cell">
                    <span class="sc-num">{{ neighborhood.summary.total_in }}</span>
                    <span class="sc-label">入边</span>
                  </div>
                  <div class="summary-cell">
                    <span class="sc-num">{{ Object.keys(neighborhood.summary.by_rel_type).length }}</span>
                    <span class="sc-label">关系类型</span>
                  </div>
                </div>
              </section>

              <section class="detail-section detail-actions">
                <el-button
                  type="primary"
                  size="small"
                  :loading="loading.expandFromNode"
                  @click="expandFromSelectedNode"
                >
                  <el-icon><Plus /></el-icon>
                  展开 1-hop 子图
                </el-button>
                <el-button size="small" @click="focusOnNode(selectedNode.id)">
                  <el-icon><Aim /></el-icon>
                  在图中定位
                </el-button>
                <el-button size="small" @click="askAboutNode">
                  <el-icon><ChatLineRound /></el-icon>
                  在对话中询问
                </el-button>
              </section>

              <section v-if="neighborhood.outgoing.length" class="detail-section">
                <div class="section-title-small">
                  <el-icon><Bottom /></el-icon>
                  出边（此节点 → 其他）· {{ neighborhood.summary.total_out }}
                </div>
                <div
                  v-for="group in neighborhood.outgoing"
                  :key="group.rel_type"
                  class="neighbor-group"
                >
                  <div class="group-header">
                    <el-tag type="warning" effect="plain" size="small">{{ group.rel_type }} · {{ group.count }}</el-tag>
                  </div>
                  <div class="group-items">
                    <div
                      v-for="n in group.neighbors"
                      :key="n.id"
                      class="neighbor-item"
                      @click="jumpToNode(n.id)"
                    >
                      <span class="n-dot" :style="{ background: n.color }"></span>
                      <span class="n-label">{{ n.label }}</span>
                      <el-tag type="info" effect="plain" size="small">{{ n.type }}</el-tag>
                    </div>
                  </div>
                </div>
              </section>

              <section v-if="neighborhood.incoming.length" class="detail-section">
                <div class="section-title-small">
                  <el-icon><Top /></el-icon>
                  入边（其他 → 此节点）· {{ neighborhood.summary.total_in }}
                </div>
                <div
                  v-for="group in neighborhood.incoming"
                  :key="group.rel_type"
                  class="neighbor-group"
                >
                  <div class="group-header">
                    <el-tag type="success" effect="plain" size="small">{{ group.rel_type }} · {{ group.count }}</el-tag>
                  </div>
                  <div class="group-items">
                    <div
                      v-for="n in group.neighbors"
                      :key="n.id"
                      class="neighbor-item"
                      @click="jumpToNode(n.id)"
                    >
                      <span class="n-dot" :style="{ background: n.color }"></span>
                      <span class="n-label">{{ n.label }}</span>
                      <el-tag type="info" effect="plain" size="small">{{ n.type }}</el-tag>
                    </div>
                  </div>
                </div>
              </section>

              <section
                v-if="!neighborhood.outgoing.length && !neighborhood.incoming.length"
                class="detail-section no-neighbor"
              >
                <el-empty description="孤立节点，无邻居" :image-size="80" />
              </section>
            </template>

            <div v-else class="neighborhood-empty">
              <el-icon><Warning /></el-icon>
              节点邻域数据加载失败
            </div>
          </div>
        </aside>
      </Transition>
    </div>
  </PageContainer>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick, watch, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Search, FullScreen, Refresh, Close,
  Setting, Picture, Document, DataAnalysis, Operation,
  Aim, DataLine, Connection, Filter,
  Loading, Plus, ChatLineRound, Bottom, Top, Warning, Share,
  ArrowDown, Trophy, PieChart, Promotion, Right,
} from '@element-plus/icons-vue'
import {
  visualizeGraph,
  findRelated,
  getGraphStats,
  buildGraph,
  getNodeNeighborhood,
  getGraphAnalytics,
  type GraphData,
  type GraphStats,
  type NodeNeighborhood,
  type GraphAnalytics,
} from '@/api/graph'
import PageContainer from '@/components/base/PageContainer.vue'
import SectionTitle from '@/components/base/SectionTitle.vue'
import EmptyState from '@/components/base/EmptyState.vue'
import ErrorState from '@/components/base/ErrorState.vue'
import { use } from 'echarts/core'
import { GraphChart } from 'echarts/charts'
import {
  TooltipComponent,
  TitleComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'

use([GraphChart, TooltipComponent, TitleComponent, CanvasRenderer])

// 节点类型定义
const nodeTypeDefs = [
  { type: 'Device', label: '设备', color: '#00d4ff' },
  { type: 'Part', label: '部件', color: '#ffb84d' },
  { type: 'Fault', label: '故障', color: '#ff4757' },
  { type: 'Case', label: '案例', color: '#00d97e' },
  { type: 'SOP', label: 'SOP', color: '#a855f7' },
  { type: 'Tool', label: '工具', color: '#94a3b8' },
] as const

const relTypeDefs = [
  { type: 'HAS_PART', label: '包含部件' },
  { type: 'CAUSES', label: '导致故障' },
  { type: 'HAS_FAULT', label: '设备有故障' },
  { type: 'RESOLVED_BY', label: '案例由 SOP 解决' },
  { type: 'REQUIRES', label: 'SOP 需要工具' },
  { type: 'APPEARS_IN', label: '故障出现在案例' },
] as const

// 节点 → ECharts shape 映射
const nodeShape: Record<string, string> = {
  Device: 'circle',
  Part: 'circle',
  Fault: 'diamond',         // 故障：菱形（警示）
  Case: 'roundRect',        // 案例：圆角矩形
  SOP: 'hexagon',           // SOP：六边形（流程）
  Tool: 'rect',             // 工具：方形
}

const suggestionQueries = ['焊接 虚焊', 'AGV 电池', 'FANUC SRVO-023', '冲压 离合器', '机器视觉']

const router = useRouter()

const keywords = ref('焊接 虚焊')
const maxHops = ref(2)
const maxNodes = ref(150)
const layoutAlgo = ref<'force' | 'circular' | 'none'>('force')
const nodeTypeFilter = ref<string[]>([])
const relTypeFilter = ref<string[]>([])
const stats = ref<GraphStats>({
  total_nodes: 0,
  total_edges: 0,
  node_types: {},
  rel_types: {},
  density: 0,
})
const selectedNode = ref<any>(null)
const neighborhood = ref<NodeNeighborhood | null>(null)
const errorMessage = ref<string>('')
const visData = reactive<{ nodes: any[]; edges: any[] }>({ nodes: [], edges: [] })
const currentView = ref<'search' | 'full' | 'subgraph' | 'idle'>('idle')
const matchedCount = ref(0)
const lastKeywords = ref('')
const subgraphSeedLabel = ref('')

const analytics = ref<GraphAnalytics | null>(null)
const analyticsOpen = ref(false)

// hover state
const hoveredNode = ref<any>(null)
const hoverPos = ref({ x: 0, y: 0 })

const loading = reactive({
  search: false,
  full: false,
  rebuild: false,
  neighborhood: false,
  expandFromNode: false,
  analytics: false,
})
const loadingAny = computed(() => loading.search || loading.full || loading.rebuild || loading.analytics)

const chartRef = ref<InstanceType<typeof VChart> | null>(null)
const chartInitOptions = { renderer: 'canvas' as const }

// ==================== Computed：ECharts 配置 ====================

const maxDegree = computed(() => {
  const arr = analytics.value?.top_degree_centrality
  return arr && arr.length ? arr[0].degree : 1
})

const ccTotalVisual = computed(() => {
  const dist = analytics.value?.connected_components.sizes_distribution
  if (!dist) return null
  const values = Object.values(dist)
  return { max: Math.max(...values, 1) }
})

const layoutAlgoText = computed(() => ({
  force: '力学导向',
  circular: '环形',
  none: '固定位置',
}[layoutAlgo.value]))

const chartOption = computed(() => {
  const filterType = nodeTypeFilter.value.length > 0
  const filterRel = relTypeFilter.value.length > 0

  // 节点：渐变 + 阴影 + shape + label
  const echartsNodes = visData.nodes.map(n => {
    const hidden = (filterType && !nodeTypeFilter.value.includes(n.type))
    return {
      id: n.id,
      name: n.label,
      symbolSize: Math.max(14, Math.min(46, 12 + Math.sqrt((n.value || 1)) * 6)),
      symbol: nodeShape[n.type] || 'circle',
      category: n.type,
      hidden,
      itemStyle: {
        color: hidden
          ? { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: '#64748b' }, { offset: 1, color: '#475569' }] }
          : {
              type: 'radial',
              x: 0.5,
              y: 0.5,
              r: 0.6,
              colorStops: [
                { offset: 0, color: lightenColor(n.color, 0.35) },
                { offset: 1, color: n.color },
              ],
            },
        borderColor: hidden ? '#475569' : '#fff',
        borderWidth: 2,
        shadowBlur: hidden ? 0 : 14,
        shadowColor: hidden ? 'transparent' : `${n.color}55`,
        opacity: hidden ? 0.45 : 1,
      },
      label: {
        show: !hidden,
        position: 'bottom',
        color: hidden ? '#64748b' : '#475569',
        fontSize: 11,
        fontWeight: 500,
        backgroundColor: 'rgba(255,255,255,0.85)',
        padding: [2, 6],
        borderRadius: 4,
        distance: 4,
      },
      value: n.value,
      nType: n.type,
      rawColor: n.color,
    }
  })

  // 边：线 + 箭头 + label
  const echartsLinks = visData.edges.map((e, i) => {
    const hidden = (filterRel && !relTypeFilter.value.includes(e.label))
    return {
      id: `e-${i}`,
      source: e.source,
      target: e.target,
      hidden,
      symbolSize: hidden ? 2 : 6,
      lineStyle: {
        color: hidden ? '#cbd5e1' : '#94a3b8',
        width: hidden ? 0.5 : 1.2,
        opacity: hidden ? 0.3 : 0.85,
        curveness: 0.12,
      },
      labelLayout: { moveOverlap: 'shiftY' },
      label: {
        show: !hidden,
        formatter: e.label,
        fontSize: 10,
        color: '#94a3b8',
        fontWeight: 500,
        backgroundColor: 'rgba(255,255,255,0.7)',
        padding: [1, 3],
        borderRadius: 2,
      },
    }
  })

  // categories 用于图例 / 自动配色
  const categories = nodeTypeDefs.map(t => ({
    name: t.type,
    itemStyle: { color: t.color },
    label: t.label,
  }))

  return {
    backgroundColor: 'transparent',
    tooltip: {
      show: false,  // 用自定义 hover mini-card
    },
    legend: {
      show: false,  // 用自定义分组图例
    },
    series: [{
      type: 'graph',
      layout: layoutAlgo.value,
      force: layoutAlgo.value === 'force' ? {
        repulsion: 380,
        gravity: 0.18,
        edgeLength: [50, 140],
        friction: 0.35,
        initLayout: 'circular',
      } : undefined,
      circular: layoutAlgo.value === 'circular' ? {
        rotateLabel: true,
      } : undefined,
      roam: true,
      draggable: true,
      focusNodeAdjacency: true,
      categories,
      nodes: echartsNodes,
      links: echartsLinks,
      edgeSymbol: ['none', 'arrow'],
      edgeSymbolSize: [0, 8],
      emphasis: {
        focus: 'adjacency',
        itemStyle: {
          shadowBlur: 28,
          shadowColor: 'rgba(0,0,0,0.45)',
          borderColor: '#fff',
          borderWidth: 3,
        },
        lineStyle: { width: 2.4, color: '#00d4ff' },
        label: { fontSize: 12, fontWeight: 600 },
      },
      animationDuration: 800,
      animationEasingUpdate: 'cubicOut',
    }],
  }
})

function colorOfType(type: string): string {
  return nodeTypeDefs.find(t => t.type === type)?.color || '#999'
}

// 浅化 hex color
function lightenColor(hex: string, amount: number): string {
  if (!hex.startsWith('#')) return hex
  let num = parseInt(hex.slice(1), 16)
  let r = (num >> 16) + Math.round((255 - (num >> 16)) * amount)
  let g = ((num >> 8) & 0x00ff) + Math.round((255 - ((num >> 8) & 0x00ff)) * amount)
  let b = (num & 0x0000ff) + Math.round((255 - (num & 0x0000ff)) * amount)
  r = Math.min(255, r)
  g = Math.min(255, g)
  b = Math.min(255, b)
  return `#${((r << 16) | (g << 8) | b).toString(16).padStart(6, '0')}`
}

// ==================== ECharts 事件 ====================

function onChartClick(params: any) {
  if (params?.dataType !== 'node') return
  const node = visData.nodes.find(n => n.id === params.data.id)
  if (node) {
    selectedNode.value = node
    loadNeighborhood(node.id)
  }
}

function onChartHover(params: any) {
  if (params?.dataType !== 'node') return
  const node = visData.nodes.find(n => n.id === params.data.id)
  if (node) {
    hoveredNode.value = node
    // params.event.event 是原生事件
    const evt = params.event?.event
    if (evt) {
      hoverPos.value = {
        x: evt.clientX + 14,
        y: evt.clientY + 14,
      }
    }
  }
}

function onChartLeave() {
  hoveredNode.value = null
}

// ==================== API ====================

async function searchRelated() {
  if (!keywords.value.trim()) {
    ElMessage.warning('请输入关键词')
    return
  }
  loading.search = true
  errorMessage.value = ''
  visData.nodes = []
  visData.edges = []
  try {
    const kws = keywords.value.trim().split(/[\s,，]+/).filter(Boolean)
    const data = await findRelated(kws, maxHops.value)
    matchedCount.value = data.matched_count || 0
    lastKeywords.value = keywords.value
    if (data.nodes.length === 0) {
      currentView.value = 'search'
      ElMessage.info(`未找到匹配「${keywords.value}」的节点`)
      return
    }
    visData.nodes = data.nodes
    visData.edges = data.edges
    currentView.value = 'search'
    ElMessage.success(`匹配 ${matchedCount.value} 个节点，子图共 ${data.nodes.length} 节点`)
    if (analyticsOpen.value) refreshAnalytics()
  } catch (e: any) {
    errorMessage.value =
      e?.response?.data?.detail || e?.message || '查询相关节点失败，请稍后重试'
  } finally {
    loading.search = false
  }
}

async function loadFullGraph() {
  loading.full = true
  errorMessage.value = ''
  visData.nodes = []
  visData.edges = []
  try {
    const data = await visualizeGraph(maxNodes.value)
    visData.nodes = data.nodes
    visData.edges = data.edges
    currentView.value = 'full'
    matchedCount.value = 0
    ElMessage.success(`整图加载完成：${data.nodes.length} 节点 / ${data.edges.length} 关系`)
    if (analyticsOpen.value) refreshAnalytics()
  } catch (e: any) {
    errorMessage.value =
      e?.response?.data?.detail || e?.message || '加载整图失败，请稍后重试'
  } finally {
    loading.full = false
  }
}

async function rebuildGraph() {
  try {
    await ElMessageBox.confirm('将从内置数据重建故障图谱（约 5-10 秒），是否继续？', '重建图谱', {
      type: 'warning',
    })
    loading.rebuild = true
    errorMessage.value = ''
    await buildGraph()
    await loadStats()
    ElMessage.success('图谱重建完成')
    analytics.value = null
    analyticsOpen.value = false
    await loadFullGraph()
  } catch (e: any) {
    if (e === 'cancel' || e?.message === 'cancel') return
    errorMessage.value =
      e?.response?.data?.detail || e?.message || '图谱重建失败，请稍后重试'
  } finally {
    loading.rebuild = false
  }
}

async function loadStats() {
  try {
    stats.value = await getGraphStats()
  } catch (e: any) {
    console.error('加载图谱统计失败:', e)
  }
}

async function loadAnalytics() {
  loading.analytics = true
  try {
    analytics.value = await getGraphAnalytics()
  } catch (e: any) {
    console.error('加载图谱分析失败:', e)
  } finally {
    loading.analytics = false
  }
}

async function refreshAnalytics() {
  await loadAnalytics()
}

async function loadNeighborhood(nodeId: string) {
  loading.neighborhood = true
  try {
    const data = await getNodeNeighborhood(nodeId)
    if (data.error) {
      ElMessage.warning(data.error)
      neighborhood.value = null
    } else {
      neighborhood.value = data
    }
  } catch (e: any) {
    neighborhood.value = null
    console.error('加载邻居失败:', e)
  } finally {
    loading.neighborhood = false
  }
}

function closeDetail() {
  selectedNode.value = null
  neighborhood.value = null
}

function jumpToNode(nodeId: string) {
  if (!chartRef.value) return
  const nodeData = visData.nodes.find(n => n.id === nodeId)
  if (!nodeData) {
    ElMessage.info('该节点不在当前视图中')
    return
  }
  selectedNode.value = nodeData
  loadNeighborhood(nodeId)
  // ECharts dispatch focus
  try {
    chartRef.value.dispatchAction({ type: 'showTip', seriesIndex: 0, })
    chartRef.value.dispatchAction({ type: 'focusNodeAdjacency', nodeId })
  } catch (e) { /* ignore */ }
}

function focusOnNode(nodeId: string) {
  try {
    chartRef.value?.dispatchAction({ type: 'focusNodeAdjacency', nodeId })
  } catch (e) { /* ignore */ }
}

function focusNodeFromAnalytic(nodeId: string) {
  const node = visData.nodes.find(n => n.id === nodeId)
  if (!node) {
    ElMessage.info(`节点「${nodeId}」不在当前视图，先点击「整图浏览」`)
    return
  }
  selectedNode.value = node
  loadNeighborhood(nodeId)
  jumpToNode(nodeId)
}

function focusNodeType(type: string) {
  // 打开时再次查整图，然后聚焦该类型
  if (currentView.value !== 'full') {
    loadFullGraph().then(() => {
      nextTick(() => dispatchFocusByType(type))
    })
  } else {
    dispatchFocusByType(type)
  }
  ElMessage.info(`正在聚焦「${type}」类型节点`)
}

function dispatchFocusByType(type: string) {
  if (!chartRef.value) return
  const ids = visData.nodes.filter(n => n.type === type).map(n => n.id)
  if (!ids.length) return
  try {
    ids.forEach(id => chartRef.value?.dispatchAction({ type: 'highlight', seriesIndex: 0, dataIndex: id }))
  } catch (e) { /* ignore */ }
}

async function expandFromNode(nodeId: string) {
  loading.expandFromNode = true
  try {
    const data = await findRelated([nodeId], 1)
    if (!data.nodes.length) {
      ElMessage.info('该节点无相关连接')
      return
    }
    visData.nodes = data.nodes
    visData.edges = data.edges
    currentView.value = 'subgraph'
    matchedCount.value = 1
    ElMessage.success(`已展开「${subgraphSeedLabel.value}」的 1-hop 子图：${data.nodes.length} 节点`)
    selectedNode.value = null
    neighborhood.value = null
  } catch (e: any) {
    ElMessage.error('展开子图失败：' + (e?.message || '未知错误'))
  } finally {
    loading.expandFromNode = false
  }
}

function expandFromSelectedNode() {
  if (!selectedNode.value) return
  subgraphSeedLabel.value = selectedNode.value.label
  expandFromNode(selectedNode.value.id)
}

function askAboutNode() {
  if (!selectedNode.value) return
  const label = selectedNode.value.label
  router.push({ path: '/', query: { q: `${label} 怎么办？` } })
  ElMessage.info('已打开智能问答，请按回车发送')
}

function quickSearch(text: string) {
  keywords.value = text
  searchRelated()
}

// ==================== 视图操作 ====================

function fitView() {
  // ECharts graph 没有 fit API — 用 dispatchAction 不行；用户拖拽/缩放即解决
  // 这里给一个动画 reload 提示
  try {
    chartRef.value?.resize()
  } catch (e) { /* ignore */ }
}

function reLayout() {
  if (!chartRef.value) return
  // 触发 setOption 让 force layout 重新收敛
  // vue-echarts 通过 :option 响应式已经更新，这里强制 resize
  try {
    chartRef.value.resize()
  } catch (e) { /* ignore */ }
}

// ==================== 导出 ====================

function exportGraphPNG() {
  if (!chartRef.value) {
    ElMessage.warning('暂无可导出的图谱')
    return
  }
  try {
    const chart = chartRef.value as any
    const dataUrl = chart.getDataURL({
      type: 'png',
      pixelRatio: 2,
      backgroundColor: '#ffffff',
    })
    const link = document.createElement('a')
    link.href = dataUrl
    const stamp = new Date().toISOString().slice(0, 19).replace(/[T:]/g, '-')
    link.download = `故障图谱_${stamp}.png`
    link.click()
    ElMessage.success('PNG 导出成功')
  } catch (e: any) {
    ElMessage.error('PNG 导出失败：' + e?.message)
  }
}

function exportGraphJSON() {
  if (!visData.nodes.length) {
    ElMessage.warning('暂无可导出的图谱')
    return
  }
  try {
    const payload = {
      exported_at: new Date().toISOString(),
      view: currentView.value,
      keywords: lastKeywords.value,
      stats: stats.value,
      nodes: visData.nodes,
      edges: visData.edges,
    }
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    const stamp = new Date().toISOString().slice(0, 19).replace(/[T:]/g, '-')
    link.download = `故障图谱_${stamp}.json`
    link.click()
    setTimeout(() => URL.revokeObjectURL(url), 100)
    ElMessage.success('JSON 导出成功')
  } catch (e: any) {
    ElMessage.error('JSON 导出失败：' + e?.message)
  }
}

// ==================== Filter / Layout ====================

function toggleNodeType(type: string) {
  const idx = nodeTypeFilter.value.indexOf(type)
  if (idx >= 0) nodeTypeFilter.value = nodeTypeFilter.value.filter(t => t !== type)
  else nodeTypeFilter.value = [...nodeTypeFilter.value, type]
}

function toggleRelType(type: string) {
  const idx = relTypeFilter.value.indexOf(type)
  if (idx >= 0) relTypeFilter.value = relTypeFilter.value.filter(t => t !== type)
  else relTypeFilter.value = [...relTypeFilter.value, type]
}

const hasData = computed(() => visData.nodes.length > 0)

function retryAfterError() {
  errorMessage.value = ''
  if (currentView.value === 'search') searchRelated()
  else loadFullGraph()
}

function applyRouteQuery() {
  const q = router.currentRoute.value.query.q
  if (typeof q === 'string' && q.trim()) {
    keywords.value = q
    searchRelated()
  }
}

watch(analyticsOpen, (open) => {
  if (open && !analytics.value && !loading.analytics) {
    loadAnalytics()
  }
})

// ==================== 生命周期 ====================

onMounted(async () => {
  await loadStats()
  await nextTick()
  applyRouteQuery()
  if (currentView.value === 'idle') {
    await searchRelated()
  }
})

onUnmounted(() => {
  // ECharts 实例会随组件卸载自动 dispose
})
</script>

<style lang="scss" scoped>
// 主区：左 320 + 右 flex-grow
.graph-stage {
  display: grid;
  grid-template-columns: 320px 1fr;
  gap: var(--spacing-md);
  margin-top: var(--spacing-md);
  align-items: start;
  min-height: calc(100vh - 200px);
  transition: grid-template-columns 0.2s ease;
}

// ==================== 左侧控制面板 ====================
.control-panel {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  padding: var(--spacing-md);
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
  position: sticky;
  top: 72px;
  max-height: calc(100vh - 88px);
  overflow-y: auto;
  box-shadow: var(--shadow-sm);

  &::-webkit-scrollbar { width: 6px; }
  &::-webkit-scrollbar-thumb { background: var(--scrollbar-thumb); border-radius: 3px; }
}

.panel-section {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding-bottom: var(--spacing-md);
  border-bottom: 1px solid var(--border-light);
  &:last-child { border-bottom: none; padding-bottom: 0; }
}

.section-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
  .el-icon { color: var(--primary-color); font-size: 14px; }
}

.section-title-small {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-semibold);
  color: var(--text-secondary);
  margin-bottom: 6px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.primary-action {
  width: 100%;
  margin-top: 4px;
}

.suggestion-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: -4px;
}
.suggestion-chip {
  padding: 3px 10px;
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  font-size: 12px;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all var(--transition-fast);
  &:hover {
    border-color: var(--primary-color);
    color: var(--primary-color);
    background: rgba(var(--primary-rgb), 0.04);
  }
}

.param-row {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.param-label {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: var(--font-size-xs);
  color: var(--text-secondary);
  .param-value {
    font-weight: var(--font-weight-semibold);
    color: var(--primary-color);
    font-family: 'Consolas', monospace;
  }
}

.type-chips {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.chip-group {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 4px;
}
.chip-group :deep(.el-checkbox) {
  margin-right: 0 !important;
  white-space: nowrap;
}
.chip-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-right: 4px;
  vertical-align: middle;
}

.rel-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
.rel-chip {
  cursor: pointer;
  user-select: none;
  font-family: 'Consolas', monospace;
  font-size: 11px;
  margin: 0;
  transition: all var(--transition-fast);
}

.layout-radio {
  width: 100%;
}
.layout-radio :deep(.el-radio-button) { flex: 1; }
.layout-radio :deep(.el-radio-button__inner) {
  width: 100%;
  padding: 6px 8px;
  font-size: 12px;
}

.action-buttons {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  :deep(.el-button) {
    width: 100%;
    margin-left: 0;
  }
}

.stats-section {
  background: var(--bg-tertiary);
  border-radius: var(--radius-md);
  padding: var(--spacing-sm);
  margin: 0 calc(-1 * var(--spacing-md)) calc(-1 * var(--spacing-md));
  border-bottom: none;
  border-top: 1px solid var(--border-light);
}
.stats-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 4px;
}
.stat-cell {
  text-align: center;
  padding: 8px 4px;
  background: var(--bg-primary);
  border-radius: var(--radius-sm);
}
.stat-num {
  font-size: var(--font-size-md);
  font-weight: var(--font-weight-semibold);
  color: var(--primary-color);
  font-family: 'Consolas', monospace;
}
.stat-label {
  font-size: 11px;
  color: var(--text-muted);
  margin-top: 2px;
}
.stats-breakdown {
  margin-top: 8px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.breakdown-row {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  padding: 4px 8px;
  background: var(--bg-primary);
  border-radius: var(--radius-sm);
}
.br-dot { width: 8px; height: 8px; border-radius: 50%; }
.br-type { flex: 1; color: var(--text-secondary); }
.br-count { color: var(--text-primary); font-weight: var(--font-weight-medium); font-family: 'Consolas', monospace; }

// ==================== 右侧主区 ====================
.graph-main {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  padding: var(--spacing-md);
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
  min-height: calc(100vh - 200px);
  box-shadow: var(--shadow-sm);
  position: relative;
}

.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.toolbar-left {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  font-size: var(--font-size-sm);
}
.toolbar-right {
  display: flex;
  gap: 4px;
}
.filter-hint {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--text-secondary);
  .el-icon { color: var(--primary-color); }
}

// 分组图例
.legend-bar {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 8px 12px;
  background: var(--bg-tertiary);
  border-radius: var(--radius-md);
  font-size: var(--font-size-xs);
}
.legend-group {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}
.legend-group-title {
  font-weight: var(--font-weight-semibold);
  color: var(--text-secondary);
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-right: 4px;
  flex-shrink: 0;
}
.legend-item {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  cursor: pointer;
  padding: 3px 8px;
  border-radius: var(--radius-sm);
  border: 1px solid transparent;
  transition: all var(--transition-fast);
  font-family: 'Consolas', monospace;
  font-size: 11px;
  &:hover {
    background: var(--bg-primary);
    border-color: var(--border-color);
  }
  &.active {
    border-color: var(--primary-color);
    background: rgba(var(--primary-rgb), 0.06);
  }
  &.disabled {
    opacity: 0.4;
    text-decoration: line-through;
  }
  .legend-count {
    background: var(--bg-primary);
    padding: 0 5px;
    border-radius: 8px;
    color: var(--text-muted);
    font-size: 10px;
    margin-left: 2px;
    border: 1px solid var(--border-color);
  }
}
.legend-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  display: inline-block;
}

// 画布容器
.canvas-wrap {
  position: relative;
  flex: 1;
  min-height: 580px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  overflow: hidden;
  background: linear-gradient(135deg, var(--bg-primary) 0%, var(--bg-secondary) 100%);
}
.graph-canvas {
  width: 100%;
  height: 100%;
  min-height: 580px;
}
.canvas-state {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.85);
  backdrop-filter: blur(8px);
  z-index: 5;
}
.empty-state-wrap {
  padding: var(--spacing-lg);
}
.empty-card {
  max-width: 480px;
  text-align: center;
  background: var(--bg-primary);
  padding: var(--spacing-xl);
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-color);
  box-shadow: var(--shadow-md);
}
.empty-icon-big {
  width: 80px;
  height: 80px;
  margin: 0 auto var(--spacing-md);
  border-radius: 50%;
  background: rgba(var(--primary-rgb), 0.08);
  color: var(--primary-color);
  display: flex;
  align-items: center;
  justify-content: center;
}
.empty-title {
  font-size: var(--font-size-lg);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
  margin-bottom: 6px;
}
.empty-desc {
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  margin-bottom: var(--spacing-md);
  line-height: 1.6;
}
.empty-steps {
  text-align: left;
  background: var(--bg-tertiary);
  padding: var(--spacing-md) var(--spacing-md) var(--spacing-md) var(--spacing-xl);
  border-radius: var(--radius-md);
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  line-height: 1.8;
  margin-bottom: var(--spacing-md);
  li { margin: 2px 0; }
  strong { color: var(--primary-color); }
}
.empty-actions {
  display: flex;
  gap: var(--spacing-sm);
  justify-content: center;
}

// ==================== 骨架加载 ====================
.skeleton-graph {
  display: flex;
  flex-direction: column;
  gap: 12px;
  width: 360px;
  padding: var(--spacing-xl);
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-md);
}
.skel-step {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  .step-icon {
    width: 32px;
    height: 32px;
    border-radius: var(--radius-sm);
    background: rgba(var(--primary-rgb), 0.08);
    color: var(--primary-color);
    display: flex;
    align-items: center;
    justify-content: center;
  }
}
.skel-bar {
  margin-top: 4px;
  height: 4px;
  background: var(--bg-tertiary);
  border-radius: 2px;
  overflow: hidden;
}
.skel-bar-fill {
  width: 30%;
  height: 100%;
  background: linear-gradient(90deg, var(--primary-color), var(--primary-light));
  border-radius: 2px;
  animation: bar-slide 1.6s ease-in-out infinite;
}
@keyframes bar-slide {
  0% { transform: translateX(-100%); }
  100% { transform: translateX(400%); }
}

// ==================== Hover Mini-card ====================
.hover-mini-card {
  position: fixed;
  z-index: 1000;
  background: var(--bg-elevated);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-lg);
  padding: 10px 12px;
  min-width: 220px;
  max-width: 280px;
  pointer-events: none;
  font-size: var(--font-size-sm);
}
.hmc-header {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 6px;
}
.hmc-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
}
.hmc-label {
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
  font-size: var(--font-size-md);
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.hmc-type-tag {
  margin-left: 4px;
  font-family: 'Consolas', monospace;
  font-size: 10px;
}
.hmc-meta {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding-top: 6px;
  border-top: 1px dashed var(--border-color);
}
.hmc-meta-row {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
}
.hmc-meta-label { color: var(--text-muted); }
.hmc-meta-value {
  color: var(--text-primary);
  font-weight: var(--font-weight-medium);
  &.mono { font-family: 'Consolas', monospace; font-size: 11px; max-width: 160px; overflow: hidden; text-overflow: ellipsis; }
}
.hmc-tip {
  margin-top: 8px;
  padding-top: 6px;
  border-top: 1px dashed var(--border-color);
  font-size: 11px;
  color: var(--text-muted);
}
.hover-fade-enter-active,
.hover-fade-leave-active {
  transition: opacity 0.12s ease, transform 0.12s ease;
}
.hover-fade-enter-from,
.hover-fade-leave-to {
  opacity: 0;
  transform: translateY(4px);
}

// ==================== 图谱分析面板 ====================
.analytics-panel {
  margin-top: var(--spacing-sm);
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  overflow: hidden;
  transition: all var(--transition-base);
}
.analytics-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  cursor: pointer;
  user-select: none;
  background: var(--bg-tertiary);
  transition: background var(--transition-fast);
  &:hover { background: var(--bg-secondary); }
}
.analytics-header-left {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.analytics-icon { color: var(--primary-color); font-size: 16px; }
.analytics-title {
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
  font-size: var(--font-size-md);
}
.analytics-sub {
  font-size: 12px;
  color: var(--text-muted);
}
.analytics-toggle {
  transition: transform var(--transition-base);
  color: var(--text-muted);
  &.rotated { transform: rotate(180deg); }
}

.analytics-body {
  padding: 16px;
  overflow: hidden;
}
.analytics-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: var(--spacing-2xl);
  color: var(--text-secondary);
}
.analytics-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}
.analytic-card {
  background: var(--bg-secondary);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  padding: 12px 14px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  transition: all var(--transition-fast);
  &:hover {
    border-color: rgba(var(--primary-rgb), 0.3);
    box-shadow: 0 0 0 1px rgba(var(--primary-rgb), 0.1);
  }
  &.path-card { grid-column: span 2; }
}
.card-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
  .el-icon { color: var(--primary-color); font-size: 14px; }
}
.card-body {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

// 中心度 Top 5
.centrality-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.centrality-row {
  display: grid;
  grid-template-columns: 22px 12px 1fr auto 80px auto;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  background: var(--bg-primary);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all var(--transition-fast);
  font-size: 12px;
  &:hover {
    border-color: var(--primary-color);
    transform: translateX(2px);
  }
}
.rank-badge {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: var(--font-weight-bold);
  font-size: 11px;
  background: var(--bg-tertiary);
  color: var(--text-secondary);
}
.rank-1 { background: linear-gradient(135deg, #fbbf24, #f59e0b); color: #fff; box-shadow: 0 1px 4px rgba(245, 158, 11, 0.4); }
.rank-2 { background: linear-gradient(135deg, #cbd5e1, #94a3b8); color: #fff; }
.rank-3 { background: linear-gradient(135deg, #f59e0b, #b45309); color: #fff; }
.cn-dot { width: 10px; height: 10px; border-radius: 50%; }
.cn-label {
  color: var(--text-primary);
  font-weight: var(--font-weight-medium);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.cn-type {
  font-family: 'Consolas', monospace;
  font-size: 10px !important;
  height: 18px !important;
  padding: 0 6px !important;
}
.cn-bar-wrap {
  height: 6px;
  background: var(--bg-tertiary);
  border-radius: 3px;
  overflow: hidden;
}
.cn-bar {
  height: 100%;
  border-radius: 3px;
  transition: width var(--transition-base);
}
.cn-degree {
  font-family: 'Consolas', monospace;
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
  min-width: 24px;
  text-align: right;
}

// 连通分量
.cc-summary {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}
.cc-num {
  text-align: center;
  padding: 12px 8px;
  background: var(--bg-primary);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-sm);
  display: flex;
  flex-direction: column;
  align-items: center;
  .n-value {
    font-size: var(--font-size-xl);
    font-weight: var(--font-weight-semibold);
    color: var(--primary-color);
    font-family: 'Consolas', monospace;
    line-height: 1.2;
  }
  .n-label {
    font-size: 11px;
    color: var(--text-muted);
    margin-top: 2px;
  }
}
.cc-distribution {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.dist-row {
  display: grid;
  grid-template-columns: 60px 1fr 30px;
  align-items: center;
  gap: 8px;
  font-size: 11px;
  color: var(--text-secondary);
  .dist-label { white-space: nowrap; }
  .dist-bar {
    height: 6px;
    background: var(--bg-tertiary);
    border-radius: 3px;
    overflow: hidden;
  }
  .dist-bar-fill {
    display: block;
    height: 100%;
    background: linear-gradient(90deg, var(--primary-color), var(--primary-light));
    border-radius: 3px;
    transition: width var(--transition-base);
  }
  .dist-count {
    font-family: 'Consolas', monospace;
    font-weight: var(--font-weight-semibold);
    color: var(--text-primary);
    text-align: right;
  }
}

// 节点类型分布
.type-distribution {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 4px;
}
.type-row {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 8px;
  background: var(--bg-primary);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all var(--transition-fast);
  font-size: 12px;
  &:hover {
    border-color: var(--primary-color);
    background: rgba(var(--primary-rgb), 0.04);
  }
  .tr-dot { width: 8px; height: 8px; border-radius: 50%; }
  .tr-name {
    flex: 1;
    color: var(--text-secondary);
    font-family: 'Consolas', monospace;
  }
  .tr-count {
    color: var(--text-primary);
    font-weight: var(--font-weight-semibold);
    font-family: 'Consolas', monospace;
  }
}

// 关键路径
.path-flow {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  padding: 10px 0;
}
.path-step {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  padding: 6px 10px;
  background: var(--bg-primary);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all var(--transition-fast);
  min-width: 80px;
  text-align: center;
  &:hover {
    border-color: var(--primary-color);
    transform: translateY(-1px);
  }
  &.endpoint {
    border-color: var(--primary-color);
    background: rgba(var(--primary-rgb), 0.06);
  }
  .ps-dot { width: 10px; height: 10px; border-radius: 50%; }
  .ps-label {
    color: var(--text-primary);
    font-weight: var(--font-weight-semibold);
    font-size: 12px;
  }
  .ps-type {
    color: var(--text-muted);
    font-size: 10px;
    font-family: 'Consolas', monospace;
  }
}
.path-arrow {
  color: var(--text-muted);
  font-size: 16px;
}
.path-hint {
  margin-top: 6px;
  padding: 6px 10px;
  background: var(--bg-tertiary);
  border-radius: var(--radius-sm);
  font-size: 11px;
  color: var(--text-muted);
  strong { color: var(--primary-color); }
}

// collapse 过渡
.collapse-enter-active,
.collapse-leave-active {
  transition: max-height 0.32s ease, opacity 0.24s ease, padding 0.24s ease;
  overflow: hidden;
}
.collapse-enter-from,
.collapse-leave-to {
  max-height: 0;
  opacity: 0;
  padding-top: 0;
  padding-bottom: 0;
}
.collapse-enter-to,
.collapse-leave-from {
  max-height: 800px;
  opacity: 1;
}

// ==================== 节点详情抽屉 ====================
.detail-drawer {
  position: fixed;
  top: 56px;
  right: 0;
  bottom: 0;
  width: 360px;
  background: var(--bg-primary);
  border-left: 1px solid var(--border-color);
  box-shadow: -4px 0 24px rgba(0, 0, 0, 0.08);
  z-index: 100;
  display: flex;
  flex-direction: column;
}
.drawer-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--spacing-md);
  border-bottom: 1px solid var(--border-color);
  flex-shrink: 0;
}
.drawer-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: var(--font-weight-semibold);
  font-size: var(--font-size-md);
  color: var(--text-primary);
  flex: 1;
  min-width: 0;
}
.node-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
}
.node-type-tag {
  margin-left: 4px;
  font-family: 'Consolas', monospace;
  font-size: 11px;
}
.drawer-body {
  flex: 1;
  overflow-y: auto;
  padding: var(--spacing-md);
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
  &::-webkit-scrollbar { width: 6px; }
  &::-webkit-scrollbar-thumb { background: var(--scrollbar-thumb); border-radius: 3px; }
}
.detail-section {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.detail-actions {
  flex-direction: row;
  flex-wrap: wrap;
  gap: 6px;
  :deep(.el-button) { flex: 1; min-width: 110px; }
}
.neighbor-summary {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 6px;
}
.summary-cell {
  text-align: center;
  padding: 10px 6px;
  background: var(--bg-secondary);
  border-radius: var(--radius-sm);
  border: 1px solid var(--border-light);
  .sc-num {
    display: block;
    font-size: var(--font-size-lg);
    font-weight: var(--font-weight-semibold);
    color: var(--primary-color);
    font-family: 'Consolas', monospace;
  }
  .sc-label {
    font-size: 11px;
    color: var(--text-muted);
    margin-top: 2px;
  }
}
.neighbor-group { margin-bottom: 12px; }
.group-header { margin-bottom: 6px; }
.group-items {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.neighbor-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 8px;
  background: var(--bg-secondary);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-sm);
  cursor: pointer;
  font-size: var(--font-size-sm);
  transition: all var(--transition-fast);
  .n-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
  .n-label { flex: 1; color: var(--text-primary); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  &:hover {
    background: rgba(var(--primary-rgb), 0.06);
    border-color: var(--primary-color);
  }
}
.neighborhood-loading,
.neighborhood-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: var(--spacing-md);
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  background: var(--bg-secondary);
  border-radius: var(--radius-md);
}
.no-neighbor { align-items: center; }
.mono-text {
  font-family: 'Consolas', monospace;
  font-size: 12px;
}
.drawer-enter-active,
.drawer-leave-active {
  transition: transform var(--transition-base), opacity var(--transition-base);
}
.drawer-enter-from,
.drawer-leave-to {
  transform: translateX(20px);
  opacity: 0;
}

// 响应式
@media (max-width: 1024px) {
  .graph-stage { grid-template-columns: 1fr; }
  .control-panel { position: static; max-height: none; }
  .detail-drawer { width: 100%; }
  .analytics-grid { grid-template-columns: 1fr; }
  .analytic-card.path-card { grid-column: span 1; }
}
</style>
