import 'vue-router'
import type { Component } from 'vue'

// 扩展路由 meta 类型
declare module 'vue-router' {
  interface RouteMeta {
    /** 页面标题（菜单名 / 面包屑 / 标签页 / document.title） */
    title?: string
    /** 菜单图标（Element Plus 图标组件） */
    icon?: Component
    /** 是否在侧边栏隐藏 */
    hidden?: boolean
    /** 标签页是否固定（不可关闭） */
    affix?: boolean
  }
}

export {}
