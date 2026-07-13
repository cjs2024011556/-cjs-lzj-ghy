<template>
  <div class="register-page">
    <!-- 背景装饰 -->
    <div class="bg-decoration">
      <div class="grid-pattern"></div>
      <div class="glow glow-1"></div>
      <div class="glow glow-2"></div>
    </div>

    <div class="register-container">
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

      <!-- 右侧：注册表单 -->
      <div class="form-side">
        <el-card class="register-card" shadow="always">
          <h2 class="form-title">创建新账号</h2>
          <p class="form-desc">请填写以下信息完成注册</p>

          <el-form
            ref="formRef"
            :model="form"
            :rules="rules"
            size="large"
            @keyup.enter="onRegister"
          >
            <el-form-item prop="username">
              <el-input
                v-model="form.username"
                placeholder="账号（字母开头，3-20 位）"
                :prefix-icon="User"
                clearable
                autocomplete="username"
              />
            </el-form-item>
            <el-form-item prop="full_name">
              <el-input
                v-model="form.full_name"
                placeholder="姓名"
                :prefix-icon="UserFilled"
                clearable
              />
            </el-form-item>
            <el-form-item prop="department">
              <el-input
                v-model="form.department"
                placeholder="部门（可选）"
                :prefix-icon="OfficeBuilding"
                clearable
              />
            </el-form-item>
            <el-form-item prop="role" label="角色">
              <el-radio-group v-model="form.role" class="role-radio">
                <el-radio-button value="engineer">普通用户</el-radio-button>
                <el-radio-button value="admin">系统管理员</el-radio-button>
              </el-radio-group>
              <div class="role-hint">
                <el-icon :size="14"><InfoFilled /></el-icon>
                <span v-if="form.role === 'admin'">系统管理员：拥有后台管理、知识库管理等全部权限</span>
                <span v-else>普通用户：使用知识检索、作业指引、智能问答等业务功能</span>
              </div>
            </el-form-item>
            <el-form-item prop="password">
              <el-input
                v-model="form.password"
                type="password"
                placeholder="密码（至少 6 位）"
                :prefix-icon="Lock"
                show-password
                autocomplete="new-password"
              />
            </el-form-item>
            <el-form-item prop="confirm_password">
              <el-input
                v-model="form.confirm_password"
                type="password"
                placeholder="确认密码"
                :prefix-icon="Lock"
                show-password
                autocomplete="new-password"
              />
            </el-form-item>
            <el-form-item>
              <el-button
                type="primary"
                size="large"
                :loading="loading"
                style="width: 100%"
                @click="onRegister"
              >
                注 册
              </el-button>
            </el-form-item>
          </el-form>

          <div class="login-link">
            已有账号？<el-link type="primary" :underline="false" @click="goLogin">立即登录</el-link>
          </div>
        </el-card>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { User, Lock, UserFilled, Check, Tools, OfficeBuilding, InfoFilled } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const auth = useAuthStore()

const formRef = ref<FormInstance>()
const loading = ref(false)

const form = ref({
  username: '',
  password: '',
  confirm_password: '',
  full_name: '',
  department: '',
  role: 'engineer' as 'admin' | 'engineer',
})

// 用户名校验：字母开头，3-20 位字母/数字/下划线
const usernamePattern = /^[A-Za-z][A-Za-z0-9_]{2,19}$/

const validateUsername = (_rule: unknown, value: string, callback: (err?: Error) => void) => {
  if (!value) return callback(new Error('请输入账号'))
  if (!usernamePattern.test(value)) {
    return callback(new Error('账号必须以字母开头，仅含字母/数字/下划线，长度 3-20 位'))
  }
  callback()
}

const validateConfirmPassword = (_rule: unknown, value: string, callback: (err?: Error) => void) => {
  if (!value) return callback(new Error('请再次输入密码'))
  if (value !== form.value.password) return callback(new Error('两次输入的密码不一致'))
  callback()
}

const rules: FormRules = {
  username: [{ validator: validateUsername, trigger: 'blur' }],
  full_name: [{ required: true, message: '请输入姓名', trigger: 'blur' }],
  role: [{ required: true, message: '请选择角色', trigger: 'change' }],
  password: [{ required: true, min: 6, message: '密码至少 6 位', trigger: 'blur' }],
  confirm_password: [{ validator: validateConfirmPassword, trigger: 'blur' }],
}

async function onRegister() {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (!valid) return
    loading.value = true
    try {
      const result = auth.register({
        username: form.value.username.trim(),
        password: form.value.password,
        confirm_password: form.value.confirm_password,
        full_name: form.value.full_name.trim(),
        department: form.value.department.trim(),
        role: form.value.role,
      })
      if (result.success) {
        ElMessage.success('注册成功，正在为您登录…')
        // 自动用新账号登录
        const loginRes = auth.login(form.value.username.trim(), form.value.password)
        if (loginRes.success) {
          router.push('/home')
        } else {
          router.push('/login')
        }
      } else {
        ElMessage.error(result.message || '注册失败')
      }
    } finally {
      loading.value = false
    }
  })
}

function goLogin() {
  router.push('/login')
}
</script>

<style lang="scss" scoped>
.register-page {
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

.register-container {
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

.register-card {
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

.role-radio {
  width: 100%;
  display: flex;

  :deep(.el-radio-button) {
    flex: 1;

    .el-radio-button__inner {
      width: 100%;
      box-sizing: border-box;
    }
  }
}

.role-hint {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-top: 6px;
  font-size: var(--font-size-xs);
  color: var(--text-muted);
  line-height: 1.4;
}

.login-link {
  margin-top: var(--spacing-md);
  text-align: center;
  font-size: var(--font-size-sm);
  color: var(--text-muted);
}

// 响应式
@media (max-width: 900px) {
  .brand-side { display: none; }
  .form-side { flex: 1; padding: 24px; }
  .register-container { max-width: 480px; }
}
</style>