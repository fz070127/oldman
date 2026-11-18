import { defineStore } from 'pinia'
import type { RouteLocationNormalized, RouteMeta } from 'vue-router'

export interface TabItem {
  path: string
  fullPath: string
  name?: string
  title: string
  affix: boolean
}

/** 多标签页状态 */
export const useTabsStore = defineStore('tabs', {
  state: () => ({
    tabs: [] as TabItem[],
  }),
  actions: {
    /** 初始化固定标签（如工作台），保证其始终在最左侧 */
    initAffixTabs(routes: Array<{ path: string; name?: string | symbol; meta: RouteMeta }>) {
      routes
        .filter((r) => r.meta.affix && r.meta.title)
        .forEach((r) => {
          if (this.tabs.some((t) => t.path === r.path)) return
          this.tabs.unshift({
            path: r.path,
            fullPath: r.path,
            name: r.name as string | undefined,
            title: r.meta.title as string,
            affix: true,
          })
        })
    },
    addTab(route: RouteLocationNormalized) {
      if (!route.meta.title || route.meta.hidden) return
      const exist = this.tabs.find((t) => t.path === route.path)
      if (exist) {
        exist.fullPath = route.fullPath
        return
      }
      this.tabs.push({
        path: route.path,
        fullPath: route.fullPath,
        name: route.name as string | undefined,
        title: route.meta.title,
        affix: !!route.meta.affix,
      })
    },
    /** 关闭指定标签，返回关闭后应激活的标签（若关闭的不是当前页则返回 null） */
    closeTab(path: string, activePath: string): TabItem | null {
      const idx = this.tabs.findIndex((t) => t.path === path)
      if (idx < 0 || this.tabs[idx].affix) return null
      this.tabs.splice(idx, 1)
      if (path !== activePath) return null
      return this.tabs[idx] || this.tabs[idx - 1] || null
    },
    closeOthers(path: string) {
      this.tabs = this.tabs.filter((t) => t.affix || t.path === path)
    },
    closeAll() {
      this.tabs = this.tabs.filter((t) => t.affix)
    },
  },
})
