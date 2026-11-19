/**
 * 告警全局状态 + 实时消息分发（契约 3.12）
 *
 * ALARM_NEW    → ① 未读（待处理）数 +1 ② 横幅入队 ③ 提示音 ④ 标题闪烁 ⑤ 通知已挂载的页面（列表插顶）
 * ALARM_UPDATE → 通知页面更新对应行 + 防抖拉 pending-count 校准
 * DEVICE_STATUS→ 离线 / 故障时 toast
 */
import { defineStore } from 'pinia'
import { watch } from 'vue'
import { ElMessage } from 'element-plus'
import { getAlarmPendingCount } from '@/api/alarm'
import { useWebSocket } from '@/hooks/useWebSocket'
import { useUserStore } from '@/stores/user'
import {
  WsMessageType,
  type WsAlarmNewPayload,
  type WsAlarmUpdatePayload,
  type WsMessage,
} from '@/types/alarm'
import { installAlarmSoundUnlock, playAlarmSound } from '@/utils/alarmSound'
import { storage, StorageKeys } from '@/utils/storage'
import { startTitleFlash } from '@/utils/titleFlasher'

/** DEVICE_STATUS 负载（契约 3.12） */
export interface WsDeviceStatusPayload {
  deviceId: string
  deviceNo: string
  status: number
  lastHeartbeat: string | null
}

export type AlarmBusEvent =
  | { type: 'new'; payload: WsAlarmNewPayload; ts: string }
  | { type: 'update'; payload: WsAlarmUpdatePayload; ts: string }

type AlarmBusListener = (evt: AlarmBusEvent) => void

/** 页面级订阅者（列表页挂载时订阅，卸载时退订）—— 不放进 state，避免被 pinia 响应式代理 */
const busListeners = new Set<AlarmBusListener>()

const BANNER_QUEUE_LIMIT = 20

export const useAlarmStore = defineStore('alarm', {
  state: () => ({
    /** 当前用户待处理告警数（导航栏未读角标）；以 /alarms/pending-count 为准，WS 增量 +1 */
    pendingCount: 0,
    /** 横幅队列：一次只展示 queue[0] */
    bannerQueue: [] as WsAlarmNewPayload[],
    /** 提示音静音（持久化 localStorage） */
    muted: storage.get(StorageKeys.ALARM_MUTED) === '1',
  }),

  getters: {
    currentBanner: (state): WsAlarmNewPayload | null => state.bannerQueue[0] ?? null,
  },

  actions: {
    toggleMuted() {
      this.muted = !this.muted
      storage.set(StorageKeys.ALARM_MUTED, this.muted ? '1' : '0')
    },

    async syncPendingCount() {
      try {
        const res = await getAlarmPendingCount()
        this.pendingCount = Number(res?.count ?? 0)
      } catch {
        // 兜底接口失败不影响主流程
      }
    },

    /** 防抖校准：短时间多条 ALARM_UPDATE 只拉一次 */
    syncPendingCountDebounced() {
      if (syncTimer) clearTimeout(syncTimer)
      syncTimer = setTimeout(() => {
        syncTimer = null
        this.syncPendingCount()
      }, 500)
    },

    dismissBanner(alarmId?: string) {
      if (!alarmId) {
        this.bannerQueue.shift()
        return
      }
      const idx = this.bannerQueue.findIndex((b) => b.alarmId === alarmId)
      if (idx >= 0) this.bannerQueue.splice(idx, 1)
    },

    clearBanners() {
      this.bannerQueue = []
    },

    onAlarmEvent(cb: AlarmBusListener): () => void {
      busListeners.add(cb)
      return () => busListeners.delete(cb)
    },

    handleWsMessage(msg: WsMessage) {
      switch (msg.type) {
        case WsMessageType.ALARM_NEW: {
          const payload = msg.data as WsAlarmNewPayload
          if (!payload?.alarmId) return
          this.pendingCount += 1
          if (!this.bannerQueue.some((b) => b.alarmId === payload.alarmId)) {
            this.bannerQueue.push(payload)
            if (this.bannerQueue.length > BANNER_QUEUE_LIMIT) {
              // 队列过长时丢掉最旧的未展示项（保留正在展示的 queue[0]）
              this.bannerQueue.splice(1, 1)
            }
          }
          if (!this.muted) playAlarmSound()
          startTitleFlash(`新告警 ${payload.elderName} ${payload.roomNo}`)
          emitBus({ type: 'new', payload, ts: msg.ts })
          break
        }
        case WsMessageType.ALARM_UPDATE: {
          const payload = msg.data as WsAlarmUpdatePayload
          if (!payload?.alarmId) return
          emitBus({ type: 'update', payload, ts: msg.ts })
          this.syncPendingCountDebounced()
          break
        }
        case WsMessageType.DEVICE_STATUS: {
          const payload = msg.data as WsDeviceStatusPayload
          if (payload && (payload.status === 2 || payload.status === 3)) {
            ElMessage.warning(`设备 ${payload.deviceNo} ${payload.status === 2 ? '已离线' : '故障'}`)
          }
          break
        }
        default:
          break
      }
    },
  },
})

let syncTimer: ReturnType<typeof setTimeout> | null = null

function emitBus(evt: AlarmBusEvent) {
  for (const cb of busListeners) {
    try {
      cb(evt)
    } catch (err) {
      console.error('[alarm-bus] listener error', err)
    }
  }
}

let realtimeInstalled = false

/**
 * 在 App.vue onMounted 里调用一次：建立全局唯一的实时连接并绑定分发。
 * 重复调用是 no-op（防止 HMR / 误用导致多条连接）。
 */
export function setupRealtime(): void {
  if (realtimeInstalled) return
  realtimeInstalled = true

  installAlarmSoundUnlock()

  const ws = useWebSocket()
  const userStore = useUserStore()
  const alarmStore = useAlarmStore()

  ws.subscribe((msg) => alarmStore.handleWsMessage(msg))
  // 首次连上 & 每次重连成功后都拉一次 pending-count 兜底（断线期间可能漏消息）
  ws.onOpen(() => alarmStore.syncPendingCount())

  watch(
    () => userStore.token,
    (token) => {
      if (token) {
        ws.connect(token)
      } else {
        ws.disconnect()
        alarmStore.pendingCount = 0
        alarmStore.clearBanners()
      }
    },
    { immediate: true },
  )
}
