import type { Router } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { useTabsStore } from '@/stores/tabs'
import {
  addRoutesByMenus,
  asyncRoutes,
  getFirstAccessiblePath,
  isDynamicRoutesLoaded,
} from './index'

const APP_TITLE = import.meta.env.VITE_APP_TITLE || '银铃守护'

/** 无需登录即可访问的静态白名单路由 */
const WHITE_LIST = ['/login', '/403', '/404']

/** 判断某路径是否属于系统已定义的业务路由（用于区分 403 无权限 与 404 不存在） */
function isKnownAsyncPath(targetPath: string): boolean {
  const clean = targetPath.replace(/^\/+|\/+$/g, '')
  if (!clean) return false
  const firstSeg = clean.split('/')[0]
  return asyncRoutes.some((r) => r.path.replace(/^\/+/, '') === firstSeg)
}

/**
 * 路由权限守卫（F3 完整版）
 *
 * 1. 无 token 且非登录页 → /login（携带 redirect）
 * 2. 已登录访问 /login → 跳 /
 * 3. 有 token 但无内存 userInfo（或尚未注入动态路由，如刷新页面 / 首次登录进入）：
 *    await fetchMe() → addRoutesByMenus(menus) → next({ ...to, replace: true })
 * 4. 访问根路径 / → 跳转到当前角色第一个可访问菜单（如 ADMIN→/dashboard，FAMILY→/family）
 * 5. 路由未命中：若属于其他角色的业务路由跳 /403，否则跳 /404
 */
export function setupRouterGuard(router: Router) {
  router.beforeEach(async (to, _from, next) => {
    const userStore = useUserStore()
    const tabsStore = useTabsStore()

    // 1. 未登录
    if (!userStore.token) {
      if (WHITE_LIST.includes(to.path)) {
        next()
        return
      }
      if (to.matched.length === 0) {
        // 未登录直接敲任意地址也先跳登录页
        next({ path: '/login', query: to.fullPath !== '/' ? { redirect: to.fullPath } : {} })
        return
      }
      next({ path: '/login', query: to.fullPath !== '/' ? { redirect: to.fullPath } : {} })
      return
    }

    // 2. 已登录访问 /login → 跳根路径
    if (to.path === '/login') {
      next({ path: '/', replace: true })
      return
    }

    // 3. 有 token 但无 userInfo 或尚未挂载动态路由（刷新页面 / 首次进入）
    if (!userStore.userInfo || !isDynamicRoutesLoaded()) {
      try {
        const info = userStore.userInfo ?? (await userStore.fetchMe())
        addRoutesByMenus(info.menus)
        // 同步当前角色可见的标签页（清理跨账号残留并初始化 affix 标签）
        tabsStore.syncWithMenus(router.getRoutes())
        // 关键：addRoute 后必须 replace 重进一次，否则首次进入会白屏
        next({ ...to, replace: true })
        return
      } catch {
        // token 无效或获取用户信息失败：清本地态并回登录页
        userStore.clearAuth()
        next({ path: '/login', query: to.fullPath !== '/' ? { redirect: to.fullPath } : {} })
        return
      }
    }

    // 4. 根路径 / 重定向到当前角色第一个有权限的菜单
    if (to.path === '/') {
      const home = getFirstAccessiblePath(userStore.menus)
      next({ path: home, replace: true })
      return
    }

    // 5. 动态路由已挂载后：拦截无权限的业务路径（如 family01 手动输入 /system/users）
    // 注意：CatchAllNotFound 在 router/index.ts 里若直接 redirect:'/404'，会在进入守卫前就把 to.path 改写成 /404，
    // 因此 router/index.ts 中 CatchAllNotFound 不做静态 redirect，统一交给此处分流 403 / 404
    if (to.matched.length === 0 || to.name === 'CatchAllNotFound') {
      if (isKnownAsyncPath(to.path)) {
        next({ path: '/403', replace: true })
      } else {
        next({ path: '/404', replace: true })
      }
      return
    }

    // 6. 若路由 meta 声明了细粒度 permission，进一步用 hasPermission 校验
    if (to.meta?.permission && !userStore.hasPermission(to.meta.permission)) {
      next({ path: '/403', replace: true })
      return
    }

    next()
  })

  router.afterEach((to) => {
    document.title = to.meta.title ? `${to.meta.title} - ${APP_TITLE}` : APP_TITLE
  })
}
