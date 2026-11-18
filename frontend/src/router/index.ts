import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { markRaw } from 'vue'
import { Odometer, User, Monitor, Warning, Bell, Setting } from '@element-plus/icons-vue'
import DefaultLayout from '@/layouts/DefaultLayout.vue'
import { setupRouterGuard } from './guard'

/** 业务占位页（F1 阶段所有业务路由均指向此页） */
const Placeholder = () => import('@/views/placeholder/index.vue')

/**
 * DefaultLayout 下的一级路由占位。侧边栏菜单由此生成（meta.hidden 的不显示）
 * 注：F3 阶段将改为按 /auth/me 的 menus 动态 addRoute('Layout', ...)
 */
export const layoutChildren: RouteRecordRaw[] = [
  {
    path: 'dashboard',
    name: 'Dashboard',
    component: Placeholder,
    meta: { title: '工作台', icon: markRaw(Odometer), affix: true },
  },
  {
    path: 'elder',
    name: 'Elder',
    component: Placeholder,
    meta: { title: '老人档案', icon: markRaw(User) },
  },
  {
    path: 'device',
    name: 'Device',
    component: Placeholder,
    meta: { title: '设备管理', icon: markRaw(Monitor) },
  },
  {
    path: 'event',
    name: 'Event',
    component: Placeholder,
    meta: { title: '事件中心', icon: markRaw(Warning) },
  },
  {
    path: 'alarm',
    name: 'Alarm',
    component: Placeholder,
    meta: { title: '告警处置', icon: markRaw(Bell) },
  },
  {
    // 二级菜单示例
    path: 'system',
    name: 'System',
    redirect: '/system/users',
    meta: { title: '系统管理', icon: markRaw(Setting) },
    children: [
      { path: 'users', name: 'SystemUsers', component: Placeholder, meta: { title: '用户管理' } },
      { path: 'roles', name: 'SystemRoles', component: Placeholder, meta: { title: '角色管理' } },
      { path: 'communities', name: 'SystemCommunities', component: Placeholder, meta: { title: '社区管理' } },
    ],
  },
]

export const constantRoutes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/login/index.vue'),
    meta: { title: '登录', hidden: true },
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
    redirect: '/dashboard',
    children: layoutChildren,
  },
  { path: '/:pathMatch(.*)*', redirect: '/404', meta: { hidden: true } },
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: constantRoutes,
  scrollBehavior: () => ({ top: 0 }),
})

setupRouterGuard(router)

export default router
