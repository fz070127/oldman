import { createApp } from 'vue'
import { ElMessage } from 'element-plus'
import App from './App.vue'
import router from './router'
import pinia from './stores'
import { setupDirectives } from './directives'
import { setUnauthorizedHandler } from './api/request'
import 'element-plus/theme-chalk/base.css'
import '@/styles/index.scss'

const app = createApp(App)

app.use(pinia)
app.use(router)
setupDirectives(app)

// token 失效且刷新失败时：提示并跳登录页（带回跳地址）
setUnauthorizedHandler(async () => {
  const current = router.currentRoute.value
  if (current.path === '/login') return
  ElMessage.error('登录已过期，请重新登录')
  await router.replace({ path: '/login', query: { redirect: current.fullPath } })
})

app.mount('#app')
