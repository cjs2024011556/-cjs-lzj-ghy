<template>
  <el-container class="app-container">
    <!-- 侧边栏（chatGPT 风格：logo 同行末尾放折叠按钮） -->
    <el-aside :width="collapse ? '64px' : '220px'" class="sidebar">
      <div class="sidebar-top">
        <div v-if="!collapse" class="logo">
          <el-icon :size="22" color="#00d4ff"><Tools /></el-icon>
          <span class="logo-text">A1 检修系统</span>
        </div>
        <el-tooltip :content="collapse ? '展开侧栏' : '折叠侧栏'" placement="right">
          <el-button
            text
            class="sidebar-collapse-btn"
            :class="{ 'sidebar-collapse-btn--collapsed': collapse }"
            @click="collapse = !collapse"
          >
            <el-icon :size="16"><Fold v-if="!collapse" /><Expand v-else /></el-icon>
          </el-button>
        </el-tooltip>
      </div>
      <el-menu
        :default-active="activeRoute"
        :collapse="collapse"
        router
        class="sidebar-menu"
      >
        <el-menu-item v-for="item in menuItems" :key="item.path" :index="item.path">
          <el-icon><component :is="item.icon" /></el-icon>
          <template #title>{{ item.title }}</template>
        </el-menu-item>
      </el-menu>

      <!-- 仅 Chat 页：右上角 avatar 透出到底栏（顶栏被砍，用户菜单必须有出口） -->
      <div v-if="$route.meta.showChatSidebar" class="sidebar-footer">
        <el-dropdown @command="handleUserCommand" trigger="click">
          <el-avatar
            :size="32"
            class="user-avatar-only"
            style="background: var(--primary-color); color: var(--text-inverse); cursor: pointer;"
          >
            {{ auth.displayName.charAt(0) }}
          </el-avatar>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item class="user-info-item" @click.stop>
                <div class="user-info-card">
                  <span class="user-info-name">{{ auth.displayName }}</span>
                  <span class="user-info-meta">{{ auth.user?.department }} · {{ auth.role }}</span>
                </div>
              </el-dropdown-item>
              <el-dropdown-item divided command="logout">
                <el-icon><SwitchButton /></el-icon>
                退出登录
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </el-aside>

    <el-container direction="vertical" :class="{ 'no-header': $route.meta.showChatSidebar }">
      <!-- 顶部栏（chat 页：整条砍掉，与 ChatGPT 一致） -->
      <el-header v-if="!$route.meta.showChatSidebar" class="header">
        <div class="header-left">
          <el-breadcrumb separator="/">
            <el-breadcrumb-item v-if="$route.meta.title">
              {{ $route.meta.title }}
            </el-breadcrumb-item>
          </el-breadcrumb>
          <!-- U.1.5 BrandStrip（品牌延续感 + 实时状态） -->
          <BrandStrip v-if="!$route.meta.showChatSidebar" />
          <!-- LLM 状态标签（chatGPT 风格：紧贴 BrandStrip，小型圆角 tag） -->
          <el-tooltip
            v-if="!$route.meta.showChatSidebar"
            :content="`当前模型: ${llmStore.status?.model || '加载中...'}`"
            placement="bottom"
          >
            <span class="llm-tag" :class="`llm-tag--${llmStore.status?.available ? 'ok' : 'off'}`">
              <span class="llm-dot"></span>
              {{ llmStore.status?.mode === 'cloud' ? '云端' : '本地' }} ·
              {{ llmStore.status?.available ? '就绪' : '离线' }}
            </span>
          </el-tooltip>
        </div>
        <div class="header-right">
          <!-- 用户菜单（chatGPT 风格：只显示头像，hover 看名字，点头像下拉退出） -->
          <el-dropdown @command="handleUserCommand" trigger="click">
            <el-avatar
              :size="32"
              class="user-avatar-only"
              style="background: var(--primary-color); color: var(--text-inverse); cursor: pointer;"
            >
              {{ auth.displayName.charAt(0) }}
            </el-avatar>
            <template #dropdown>
              <el-dropdown-menu>
                <!-- 用户信息卡（非 disabled，点击不做事，但保持原色） -->
                <el-dropdown-item class="user-info-item" @click.stop>
                  <div class="user-info-card">
                    <span class="user-info-name">{{ auth.displayName }}</span>
                    <span class="user-info-meta">{{ auth.user?.department }} · {{ auth.role }}</span>
                  </div>
                </el-dropdown-item>
                <el-dropdown-item divided command="logout">
                  <el-icon><SwitchButton /></el-icon>
                  退出登录
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>

      <!-- 主内容区（仅 Home 页显示 ChatSidebar） -->
      <el-container class="main" v-if="$route.meta.showChatSidebar">
        <ChatSidebar :collapsed="chatSidebarCollapsed" @toggle-collapse="chatSidebarCollapsed = !chatSidebarCollapsed" />
        <el-main class="main-content">
          <router-view v-slot="{ Component }">
            <transition name="fade" mode="out-in">
              <component :is="Component" />
            </transition>
          </router-view>
        </el-main>
      </el-container>

      <!-- 普通页面布局 -->
      <el-main class="main-page" v-else>
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </el-main>
    </el-container>

    <!-- 移动端提示 -->
    <el-dialog
      v-model="showMobileTip"
      title="请使用桌面端"
      width="360px"
      :show-close="false"
      :close-on-click-modal="false"
      :close-on-press-escape="false"
    >
      <p>本系统针对工业 PC 场景设计，建议在屏幕宽度 ≥ 1024px 的设备上使用。</p>
      <p>当前屏幕宽度：{{ screenWidth }}px</p>
      <template #footer>
        <el-button type="primary" @click="showMobileTip = false">我知道了</el-button>
      </template>
    </el-dialog>
  </el-container>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import { useLLMStore } from '@/stores/llm'
import { useAuthStore } from '@/stores/auth'
import { useChatHistoryStore } from '@/stores/chatHistory'
import BrandStrip from '@/components/layout/BrandStrip.vue'
import ChatSidebar from '@/components/business/ChatSidebar.vue'

const route = useRoute()
const router = useRouter()
const llmStore = useLLMStore()
const auth = useAuthStore()
const chatHistory = useChatHistoryStore()

// 当前对话标题（chat 页顶栏已被砍掉，不再需要 activeConvTitle 面包屑二级）
const collapse = ref(false)
const chatSidebarCollapsed = ref(false)
const screenWidth = ref(window.innerWidth)
const showMobileTip = ref(false)

const menuItems = [
  { path: '/home', title: '智能问答', icon: 'HomeFilled' },
  { path: '/retrieval', title: '多模态检索', icon: 'Search' },
  { path: '/operation-guide', title: '作业指引', icon: 'Document' },
  { path: '/knowledge', title: '知识管理', icon: 'Notebook' },
  { path: '/graph', title: '故障图谱', icon: 'Share' },
  { path: '/knowledge-admin', title: '知识库管理', icon: 'Files' },
  { path: '/admin', title: '后台管理', icon: 'Setting' },
]

const activeRoute = computed(() => route.path)

function handleResize() {
  screenWidth.value = window.innerWidth
  if (window.innerWidth < 1024 && !showMobileTip.value) {
    showMobileTip.value = true
  }
}

async function handleUserCommand(cmd: string) {
  if (cmd === 'logout') {
    try {
      await ElMessageBox.confirm('确定要退出登录吗？', '退出确认', { type: 'warning' })
      auth.logout()
      router.push('/login')
    } catch {
      // 取消
    }
  }
}

onMounted(() => {
  llmStore.refresh()
  // 关键：路由守卫里 auth.restore() 不会触发 chatHistory.setUser（避免循环依赖）
  // 这里统一处理：把 chatHistory 切到当前登录用户，再 hydrate 加载其历史
  chatHistory.setUser(auth.user?.username ?? null)
  chatHistory.hydrate()
  handleResize()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
})
</script>

<style lang="scss" scoped>
.app-container {
  height: 100vh;
  background: var(--bg-primary);
}

.main {
  flex: 1 1 0;
  min-height: 0;
  display: flex;
  height: calc(100vh - 60px);
}

// no-header 模式（chat 页）：顶栏砍掉，main 撑满整屏
.no-header .main {
  height: 100vh;
}

.main-content {
  background: var(--bg-primary);
  padding: 0;
  flex: 1 1 auto;
  min-height: 0;
  overflow: hidden;
}

.sidebar {
  background: #ffffff;
  border-right: 1px solid var(--border-color);
  transition: width 0.3s;
  overflow: hidden;
  box-shadow: 1px 0 0 rgba(0, 0, 0, 0.04);
  display: flex;
  flex-direction: column;
}

// 侧栏顶部：logo + 折叠按钮同行（chatGPT 风格）
.sidebar-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 12px 12px 16px;
  border-bottom: 1px solid var(--border-color);
  flex-shrink: 0;
  min-height: 52px;
  box-sizing: border-box;
}

.logo {
  display: flex;
  align-items: center;
  gap: 10px;
  overflow: hidden;

  .logo-text {
    font-size: 15px;
    font-weight: 600;
    color: var(--text-primary);
    white-space: nowrap;
    letter-spacing: 0.2px;
  }
}

// 侧栏折叠按钮（chatGPT 风格：贴着 logo 右边）
.sidebar-collapse-btn {
  flex-shrink: 0;
  padding: 6px;
  border-radius: 6px;
  color: var(--text-secondary);
  transition: all var(--transition-fast);

  &:hover {
    background: var(--bg-tertiary);
    color: var(--primary-color);
  }

  &--collapsed {
    margin: 0 auto;  // 折叠态：按钮居中
  }
}

// 仅 chat 页：侧栏底部放用户头像（因顶栏被砍）
.sidebar-footer {
  margin-top: auto;
  padding: 12px;
  border-top: 1px solid var(--border-color);
  display: flex;
  justify-content: center;
  flex-shrink: 0;
}

.sidebar-menu {
  border: none;
  padding-top: 8px;
  flex: 1 1 auto;
  overflow-y: auto;

  &::-webkit-scrollbar { width: 4px; }
  &::-webkit-scrollbar-thumb { background: var(--border-color); border-radius: 2px; }
}

.header {
  background: #ffffff;
  border-bottom: 1px solid var(--border-color);
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 20px;
  box-shadow: 0 1px 0 rgba(0, 0, 0, 0.04);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.user-info {
  display: flex;
  align-items: center;
  cursor: pointer;
  color: var(--text-primary);
  padding: 4px 8px;
  border-radius: 4px;

  &:hover {
    background: var(--bg-elevated);
  }
}

// chatGPT 风格：LLM 状态小标签（紧贴 BrandStrip，弱化视觉重量）
.llm-tag {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  height: 26px;
  padding: 0 10px;
  font-size: var(--font-size-xs);
  color: var(--text-secondary);
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-full);
  white-space: nowrap;
  cursor: default;
  user-select: none;
  transition: all var(--transition-fast);

  &:hover {
    border-color: var(--primary-color);
    color: var(--primary-color);
  }
}

.llm-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
}

.llm-tag--ok .llm-dot {
  background: var(--success);
  box-shadow: 0 0 6px var(--success);
  animation: pulse 2s ease-in-out infinite;
}

.llm-tag--off .llm-dot {
  background: var(--danger);
  box-shadow: 0 0 6px var(--danger);
}

// chatGPT 风格：用户头像单独显示（无文字、无箭头，hover 提示）
.user-avatar-only {
  transition: box-shadow var(--transition-fast), transform var(--transition-fast);

  &:hover {
    box-shadow: 0 0 0 3px rgba(var(--primary-rgb), 0.15);
    transform: scale(1.05);
  }
}

// 用户信息卡（dropdown 第一项）：保持原色 + 不可点击
.user-info-item {
  cursor: default !important;
  opacity: 1 !important;
  pointer-events: none;  // 完全不响应点击（视觉提示 + 防误触）

  &:hover {
    background: transparent !important;
  }
}

.user-info-card {
  display: flex;
  flex-direction: column;
  gap: 2px;
  line-height: 1.4;
  padding: 2px 0;
}

.user-info-name {
  color: var(--text-primary);
  font-weight: var(--font-weight-medium);
  font-size: var(--font-size-sm);
}

.user-info-meta {
  font-size: 12px;
  color: var(--text-muted);
}

.main-page {
  padding: 24px;
  background: var(--bg-primary);
  overflow-y: auto;
}

// 路由过渡
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
