<template>
  <el-container class="app-container">
    <!-- 侧边栏 -->
    <el-aside :width="collapse ? '64px' : '220px'" class="sidebar">
      <div class="logo">
        <el-icon :size="28" color="#00d4ff"><Tools /></el-icon>
        <span v-if="!collapse" class="logo-text">A1 检修系统</span>
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
    </el-aside>

    <el-container direction="vertical">
      <!-- 顶部栏 -->
      <el-header class="header">
        <div class="header-left">
          <el-button text @click="collapse = !collapse">
            <el-icon :size="20"><Fold v-if="!collapse" /><Expand v-else /></el-icon>
          </el-button>
          <el-breadcrumb separator="/">
            <el-breadcrumb-item :to="{ path: '/' }">首页</el-breadcrumb-item>
            <el-breadcrumb-item v-if="$route.meta.title">
              {{ $route.meta.title }}
            </el-breadcrumb-item>
          </el-breadcrumb>
          <!-- U.1.5 BrandStrip（品牌延续感 + 实时状态） -->
          <BrandStrip v-if="!$route.meta.showChatSidebar" />
        </div>
        <div class="header-right">
          <el-tooltip :content="`当前模型: ${llmStore.status?.model || '加载中...'}`">
            <el-tag :type="llmStore.status?.available ? 'success' : 'danger'" effect="dark" round>
              <el-icon style="vertical-align: middle"><Cpu /></el-icon>
              {{ llmStore.status?.mode === 'cloud' ? '云端' : '本地' }} ·
              {{ llmStore.status?.available ? '就绪' : '离线' }}
            </el-tag>
          </el-tooltip>
          <!-- 主题切换 -->
          <ThemeSwitcher />
          <!-- 用户菜单 -->
          <el-dropdown @command="handleUserCommand">
            <span class="user-info">
              <el-avatar :size="32" style="background: var(--primary-color); color: var(--text-inverse)">
                {{ auth.displayName.charAt(0) }}
              </el-avatar>
              <span class="user-name">{{ auth.displayName }}</span>
              <el-icon><ArrowDown /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item disabled>
                  {{ auth.user?.department }} · {{ auth.role }}
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
import ThemeSwitcher from '@/components/layout/ThemeSwitcher.vue'
import BrandStrip from '@/components/layout/BrandStrip.vue'
import ChatSidebar from '@/components/business/ChatSidebar.vue'

const route = useRoute()
const router = useRouter()
const llmStore = useLLMStore()
const auth = useAuthStore()
const chatHistory = useChatHistoryStore()
const collapse = ref(false)
const chatSidebarCollapsed = ref(false)
const screenWidth = ref(window.innerWidth)
const showMobileTip = ref(false)

const menuItems = [
  { path: '/home', title: '首页', icon: 'HomeFilled' },
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
}

.logo {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 20px 16px;
  border-bottom: 1px solid var(--border-color);

  .logo-text {
    font-size: 16px;
    font-weight: 600;
    color: var(--text-primary);
    white-space: nowrap;
  }
}

.sidebar-menu {
  border: none;
  padding-top: 8px;
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
