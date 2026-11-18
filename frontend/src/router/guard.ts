import type { Router } from 'vue-router'
import { useUserStore } from '@/stores/user'

const APP_TITLE = import.meta.env.VITE_APP_TITLE || '银铃守护'

/** 无需登录即可访问的路由 */
const WHITE_LIST = ['/login', '/404']

/**
 * 路由守卫
 * F1 阶段只做：无 token 跳登录；已登录访问登录页跳首页；设置页面标题
 */
export function setupRouterGuard(router: Router) {
  router.beforeEach((to) => {
    const userStore = useUserStore()

    if (!userStore.token) {
      if (WHITE_LIST.includes(to.path)) return true
      return { path: '/login', query: to.fullPath !== '/' ? { redirect: to.fullPath } : {} }
    }

    if (to.path === '/login') return { path: '/' }
    return true
  })

  router.afterEach((to) => {
    document.title = to.meta.title ? `${to.meta.title} - ${APP_TITLE}` : APP_TITLE
  })
}
