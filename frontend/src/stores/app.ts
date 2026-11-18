import { defineStore } from 'pinia'
import { storage, StorageKeys } from '@/utils/storage'

/** 应用级 UI 状态 */
export const useAppStore = defineStore('app', {
  state: () => ({
    /** 侧边栏是否折叠（持久化） */
    sidebarCollapsed: storage.get(StorageKeys.SIDEBAR_COLLAPSED) === '1',
    /** 未读通知数（F1 占位，后续由 WebSocket / pending-count 驱动） */
    unreadCount: 0,
  }),
  actions: {
    toggleSidebar() {
      this.sidebarCollapsed = !this.sidebarCollapsed
      storage.set(StorageKeys.SIDEBAR_COLLAPSED, this.sidebarCollapsed ? '1' : '0')
    },
    setUnreadCount(n: number) {
      this.unreadCount = n
    },
  },
})
