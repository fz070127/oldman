import { defineStore } from 'pinia'
import { storage, StorageKeys } from '@/utils/storage'

/** 应用级 UI 状态（未读告警数已迁移到 stores/alarm.ts 的 pendingCount） */
export const useAppStore = defineStore('app', {
  state: () => ({
    /** 侧边栏是否折叠（持久化） */
    sidebarCollapsed: storage.get(StorageKeys.SIDEBAR_COLLAPSED) === '1',
  }),
  actions: {
    toggleSidebar() {
      this.sidebarCollapsed = !this.sidebarCollapsed
      storage.set(StorageKeys.SIDEBAR_COLLAPSED, this.sidebarCollapsed ? '1' : '0')
    },
  },
})
