<template>
  <div class="login-page">
    <!-- 背景装饰 -->
    <div class="bg-decoration">
      <div class="grid-pattern"></div>
      <div class="glow glow-1"></div>
      <div class="glow glow-2"></div>
    </div>

    <div class="login-container">
      <!-- 左侧：品牌区 -->
      <div class="brand-side">
        <div class="brand-content">
          <div class="brand-logo">
            <el-icon :size="48" color="#00d4ff"><Tools /></el-icon>
          </div>
          <h1 class="brand-title">A1 设备检修智能系统</h1>
          <p class="brand-subtitle">基于多模态大模型 · 国产化部署 · 5 模型协同</p>

          <ul class="feature-list">
            <li><el-icon color="#00d4ff"><Check /></el-icon> 多模态知识检索</li>
            <li><el-icon color="#00d4ff"><Check /></el-icon> 标准化作业指引</li>
            <li><el-icon color="#00d4ff"><Check /></el-icon> 知识沉淀闭环</li>
            <li><el-icon color="#00d4ff"><Check /></el-icon> 故障图谱推理</li>
            <li><el-icon color="#00d4ff"><Check /></el-icon> 阿里云百炼模型</li>
          </ul>

          <p class="brand-footer">
            国产化平台：龙芯 LoongArch · 银河麒麟 V11/V10
          </p>
        </div>
      </div>

      <!-- 右侧：登录表单 -->
      <div class="form-side">
        <el-card class="login-card" shadow="always">
          <h2 class="form-title">欢迎登录</h2>
          <p class="form-desc">请使用您的账号登录系统</p>

          <el-form
            ref="formRef"
            :model="form"
            :rules="rules"
            size="large"
            @keyup.enter="onLogin"
          >
            <el-form-item prop="username">
              <el-input
                v-model="form.username"
                placeholder="账号"
                :prefix-icon="User"
                clearable
                autocomplete="username"
              />
            </el-form-item>
            <el-form-item prop="password">
              <el-input
                v-model="form.password"
                type="password"
                placeholder="密码"
                :prefix-icon="Lock"
                show-password
                autocomplete="current-password"
              />
            </el-form-item>
            <el-form-item>
              <el-checkbox v-model="form.remember">记住我（30 天免登录）</el-checkbox>
            </el-form-item>
            <el-form-item>
              <el-button
                type="primary"
                size="large"
                :loading="loading"
                style="width: 100%"
                @click="onLogin"
              >
                登 录
              </el-button>
            </el-form-item>
          </el-form>

          <el-divider>演示账号（密码均为 123456）</el-divider>
          <div class="quick-accounts">
            <el-tag
              v-for="acc in MOCK_USERS"
              :key="acc.user.username"
              :type="form.username === acc.user.username ? 'primary' : 'info'"
              effect="dark"
              class="account-tag"
              @click="useAccount(acc.user.username)"
            >
              <el-icon><UserFilled /></el-icon>
              {{ acc.user.display_name }}（{{ acc.user.role }}）
            </el-tag>
          </div>
        </el-card>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { User, Lock, UserFilled, Check, Tools } from '@element-plus/icons-vue'
import { useAuthStore, MOCK_USERS } from '@/stores/auth'

const router = useRouter()
const auth = useAuthStore()

const formRef = ref<FormInstance>()
const loading = ref(false)

const form = ref({
  username: 'admin',
  password: '123456',
  remember: true,
})

const rules: FormRules = {
  username: [{ required: true, message: '请输入账号', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }, { min: 6, message: '密码至少 6 位', trigger: 'blur' }],
}

function useAccount(username: string) {
  form.value.username = username
  form.value.password = '123456'
  ElMessage.info(`已填入 ${MOCK_USERS[username].user.display_name} 的账号`)
}

async function onLogin() {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (!valid) return
    loading.value = true
    try {
      // 模拟 0.5s 网络延迟
      await new Promise((r) => setTimeout(r, 500))
      const result = auth.login(form.value.username, form.value.password)
      if (result.success) {
        ElMessage.success(`欢迎回来，${auth.displayName}！`)
        router.push((router.currentRoute.value.query.redirect as string) || '/home')
      } else {
        ElMessage.error(result.message || '登录失败')
      }
    } finally {
      loading.value = false
    }
  })
}

onMounted(() => {
  if (auth.isLoggedIn) {
    ElMessageBox.confirm(
      '您已登录，是否直接进入系统？',
      '已登录',
      { confirmButtonText: '进入', cancelButtonText: '切换账号', type: 'info' },
    )
      .then(() => router.push('/home'))
      .catch(() => auth.logout())
  }
})
</script>

<style lang="scss" scoped>
.login-page {
  position: relative;
  width: 100vw;
  height: 100vh;
  overflow: hidden;
  background: var(--bg-primary);
}

.bg-decoration {
  position: absolute;
  inset: 0;
  pointer-events: none;
  z-index: 0;
}

.grid-pattern {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(var(--primary-rgb), 0.05) 1px, transparent 1px),
    linear-gradient(90deg, rgba(var(--primary-rgb), 0.05) 1px, transparent 1px);
  background-size: 40px 40px;
  mask-image: radial-gradient(ellipse at center, black 30%, transparent 70%);
}

.glow {
  position: absolute;
  border-radius: 50%;
  filter: blur(80px);
  opacity: 0.4;
}

.glow-1 {
  width: 500px;
  height: 500px;
  top: -100px;
  left: -100px;
  background: var(--primary-color);
  opacity: 0.15;
}

.glow-2 {
  width: 400px;
  height: 400px;
  bottom: -100px;
  right: -100px;
  background: var(--primary-color);
  opacity: 0.1;
}

.login-container {
  position: relative;
  z-index: 1;
  display: flex;
  width: 100%;
  height: 100vh;
  max-width: 1200px;
  margin: 0 auto;
}

.brand-side {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 48px;
}

.brand-content {
  max-width: 480px;
}

.brand-logo {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 80px;
  height: 80px;
  background: var(--bg-secondary);
  border: 2px solid var(--primary-color);
  border-radius: var(--radius-lg);
  margin-bottom: var(--spacing-lg);
  box-shadow: var(--shadow-glow);
}

.brand-title {
  font-size: var(--font-size-3xl);
  font-weight: var(--font-weight-bold);
  color: var(--text-primary);
  margin: 0 0 var(--spacing-sm) 0;
  letter-spacing: 1px;
}

.brand-subtitle {
  font-size: var(--font-size-md);
  color: var(--text-secondary);
  margin: 0 0 var(--spacing-xl) 0;
}

.feature-list {
  list-style: none;
  padding: 0;
  margin: 0 0 var(--spacing-xl) 0;

  li {
    display: flex;
    align-items: center;
    gap: var(--spacing-sm);
    padding: var(--spacing-sm) 0;
    color: var(--text-primary);
    font-size: var(--font-size-md);
  }
}

.brand-footer {
  font-size: var(--font-size-sm);
  color: var(--text-muted);
  border-top: 1px solid var(--border-color);
  padding-top: var(--spacing-md);
  margin-top: var(--spacing-xl);
}

.form-side {
  flex: 0 0 480px;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 48px;
}

.login-card {
  width: 100%;
  background: var(--bg-secondary) !important;
  border: 1px solid var(--border-color) !important;
  padding: var(--spacing-lg);
  box-shadow: var(--shadow-xl);
}

.form-title {
  font-size: var(--font-size-2xl);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
  margin: 0 0 var(--spacing-xs) 0;
}

.form-desc {
  font-size: var(--font-size-md);
  color: var(--text-muted);
  margin: 0 0 var(--spacing-lg) 0;
}

.quick-accounts {
  display: flex;
  flex-wrap: wrap;
  gap: var(--spacing-sm);
}

.account-tag {
  cursor: pointer;
  padding: var(--spacing-xs) var(--spacing-sm);
  transition: all var(--transition-fast);

  &:hover {
    transform: translateY(-1px);
  }
}

// 响应式
@media (max-width: 900px) {
  .brand-side { display: none; }
  .form-side { flex: 1; padding: 24px; }
  .login-container { max-width: 480px; }
}
</style>
