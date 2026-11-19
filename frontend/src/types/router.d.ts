import 'vue-router'
import type { Component } from 'vue'

// 扩展路由 meta 类型
declare module 'vue-router' {
  interface RouteMeta {
    /** 页面标题（菜单名 / 面包屑 / 标签页 / document.title） */
    title?: string
    /** 菜单图标（Element Plus 图标组件） */
    icon?: Component
    /** 菜单权限标识（与 /auth/me 返回的 menus 对应） */
    menuKey?: string
    /** 路由访问细粒度权限码（可选，如 'system:read'） */
    permission?: string
    /** 是否在侧边栏隐藏 */
    hidden?: boolean
    /** 标签页是否固定（不可关闭） */
    affix?: boolean
    /** 是否以 100vw×100vh 独立沉浸式全屏展示（隐藏侧边栏/顶栏/标签栏） */
    fullscreen?: boolean
  }
}

export {}
