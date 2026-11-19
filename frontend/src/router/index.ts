import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { markRaw } from 'vue'
import {
  Bell,
  DataBoard,
  House,
  Monitor,
  Odometer,
  Setting,
  User,
  Warning,
} from '@element-plus/icons-vue'
import DefaultLayout from '@/layouts/DefaultLayout.vue'
import { setupRouterGuard } from './guard'

/** 业务占位页（F3 阶段各业务路由统一先挂载此页，F4~F8 逐步替换为真实业务页） */
const Placeholder = () => import('@/views/placeholder/index.vue')

/**
 * 动态业务路由（按 /auth/me 返回的 menus 过滤后，通过 router.addRoute('Layout', route) 注入）
 * 每个路由 meta 包含 { title, icon, menuKey, permission? }
 */
export const asyncRoutes: RouteRecordRaw[] = [
  {
    path: 'dashboard',
    name: 'Dashboard',
    component: Placeholder,
    meta: { title: '工作台', icon: markRaw(Odometer), menuKey: 'dashboard', affix: true },
  },
  {
    path: 'elder',
    name: 'Elder',
    alias: ['elder/list'],
    component: () => import('@/views/elder/list.vue'),
    meta: { title: '老人档案', icon: markRaw(User), menuKey: 'elder', permission: 'elder:read' },
  },
  {
    path: 'elder/detail/:id',
    name: 'ElderDetail',
    component: () => import('@/views/elder/detail.vue'),
    meta: { title: '老人详情', menuKey: 'elder', permission: 'elder:read', hidden: true },
  },
  {
    path: 'device',
    name: 'Device',
    alias: ['device/list'],
    component: () => import('@/views/device/list.vue'),
    meta: { title: '设备管理', icon: markRaw(Monitor), menuKey: 'device', permission: 'device:read' },
  },
  {
    path: 'device/detail/:id',
    name: 'DeviceDetail',
    component: () => import('@/views/device/detail.vue'),
    meta: { title: '设备详情', menuKey: 'device', permission: 'device:read', hidden: true },
  },
  {
    path: 'event',
    name: 'Event',
    alias: ['event/list'],
    component: () => import('@/views/event/list.vue'),
    meta: { title: '事件中心', icon: markRaw(Warning), menuKey: 'event', permission: 'event:read' },
  },
  {
    path: 'event/detail/:id',
    name: 'EventDetail',
    component: () => import('@/views/event/detail.vue'),
    meta: { title: '事件详情', menuKey: 'event', permission: 'event:read', hidden: true },
  },
  {
    path: 'alarm',
    name: 'Alarm',
    alias: ['alarm/list'],
    component: () => import('@/views/alarm/list.vue'),
    meta: { title: '告警中心', icon: markRaw(Bell), menuKey: 'alarm', permission: 'alarm:read' },
  },
  {
    path: 'screen',
    name: 'Screen',
    component: Placeholder,
    meta: { title: '社区大屏', icon: markRaw(DataBoard), menuKey: 'screen' },
  },
  {
    path: 'system',
    name: 'System',
    redirect: '/system/users',
    meta: { title: '系统管理', icon: markRaw(Setting), menuKey: 'system', permission: 'system:read' },
    children: [
      {
        path: 'users',
        name: 'SystemUsers',
        component: Placeholder,
        meta: { title: '用户管理', menuKey: 'system', permission: 'system:read' },
      },
      {
        path: 'roles',
        name: 'SystemRoles',
        component: Placeholder,
        meta: { title: '角色管理', menuKey: 'system', permission: 'system:read' },
      },
      {
        path: 'communities',
        name: 'SystemCommunities',
        component: Placeholder,
        meta: { title: '社区管理', menuKey: 'system', permission: 'system:read' },
      },
    ],
  },
  {
    path: 'family',
    name: 'Family',
    component: Placeholder,
    meta: { title: '我的家人', icon: markRaw(House), menuKey: 'family', permission: 'family:read' },
  },
]

/** 静态公共路由（无需权限过滤，始终存在） */
export const constantRoutes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/login/index.vue'),
    meta: { title: '登录', hidden: true },
  },
  {
    path: '/403',
    name: 'Forbidden',
    component: () => import('@/views/error/403.vue'),
    meta: { title: '无访问权限', hidden: true },
  },
  {
    path: '/404',
    name: 'NotFound',
    component: () => import('@/views/error/404.vue'),
    meta: { title: '页面不存在', hidden: true },
  },
  {
    path: '/',
    name: 'Layout',
    component: DefaultLayout,
    children: [],
  },
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: constantRoutes,
  scrollBehavior: () => ({ top: 0 }),
})

// ---------------- 动态路由注册与清理 ----------------

const CATCH_ALL_NAME = 'CatchAllNotFound'

/** 记录本次会话已动态挂载的顶层路由 name，登出或切换账号时逐一卸载 */
const registeredRouteNames = new Set<string | symbol>()
let dynamicRoutesLoaded = false

/** 当前会话是否已完成动态路由注入 */
export function isDynamicRoutesLoaded(): boolean {
  return dynamicRoutesLoaded
}

/** 获取当前已注入的第一个可访问菜单路径（用作 / 的默认落地页） */
export function getFirstAccessiblePath(menus: string[]): string {
  const matched = asyncRoutes.find((r) => r.meta?.menuKey && menus.includes(r.meta.menuKey))
  if (!matched) return '/403'
  return `/${matched.path.replace(/^\//, '')}`
}

/** 清理已动态添加的全部业务路由与兜底 404 路由（登出 / 切换账号时调用） */
export function resetDynamicRoutes(): void {
  for (const name of registeredRouteNames) {
    if (router.hasRoute(name)) {
      router.removeRoute(name)
    }
  }
  registeredRouteNames.clear()
  if (router.hasRoute(CATCH_ALL_NAME)) {
    router.removeRoute(CATCH_ALL_NAME)
  }
  dynamicRoutesLoaded = false
}

/**
 * 根据 /auth/me 返回的 menus 过滤 asyncRoutes，并挂载到具名父路由 'Layout' 下
 * 注意：挂载前会先清理上一次残留的动态路由，防止切换账号后菜单串权
 */
export function addRoutesByMenus(menus: string[]): RouteRecordRaw[] {
  resetDynamicRoutes()

  const menuSet = new Set(menus)
  const allowed = asyncRoutes.filter((route) => route.meta?.menuKey && menuSet.has(route.meta.menuKey))

  for (const route of allowed) {
    router.addRoute('Layout', route)
    if (route.name) {
      registeredRouteNames.add(route.name)
    }
  }

  // 动态路由挂载完成后，再注册通配符兜底路由（不设静态 redirect，交给 guard 区分 403 与 404）
  router.addRoute({
    path: '/:pathMatch(.*)*',
    name: CATCH_ALL_NAME,
    component: () => import('@/views/error/404.vue'),
    meta: { hidden: true },
  })

  dynamicRoutesLoaded = true
  return allowed
}

setupRouterGuard(router)

export default router
