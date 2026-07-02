import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import 'element-plus/dist/index.css'
import 'nprogress/nprogress.css'
import zhCn from 'element-plus/dist/locale/zh-cn.mjs'

// 触发 ECharts 按需注册（执行后 echarts 全局可用）
import './components/Charts'

import App from './App.vue'
import router from './router'
import { useThemeStore } from './stores/theme'
import { useAuthStore } from './stores/auth'
import './styles/main.scss'

const app = createApp(App)

// 注册所有 Element Plus 图标
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component as any)
}

app.use(createPinia())
app.use(router)
app.use(ElementPlus, { locale: zhCn })

// 初始化主题（在 mount 前，避免闪烁）
const themeStore = useThemeStore()
themeStore.init()

// 恢复登录状态（处理刷新）
const authStore = useAuthStore()
authStore.restore()

// U.3.6 NProgress 顶部进度条（路由切换时显示）
import NProgress from 'nprogress'
NProgress.configure({ showSpinner: false, trickleSpeed: 200, minimum: 0.3 })
router.beforeEach((_to, _from, next) => {
  NProgress.start()
  next()
})
router.afterEach(() => {
  NProgress.done()
})

// 全局错误捕获
app.config.errorHandler = (err, _instance, info) => {
  console.error('[Global Error]', err, info)
  // 避免循环：只 import 一次 ElMessage
  // （实际生产环境会发到 Sentry 等监控）
}

app.mount('#app')
