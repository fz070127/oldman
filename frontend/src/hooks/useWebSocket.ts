/**
 * 全局实时推送（契约 3.12）—— 全局唯一连接
 *
 * - 由 App.vue onMounted 调 setupRealtime() 初始化一次；连接实例是模块级单例，
 *   与路由 / 组件生命周期无关，路由切换不会断开
 * - 登录态驱动：有 token 就连，token 变化（refresh）就用新 token 重连，登出就断开
 * - 心跳：每 30s 发 {type:'PING'}；看门狗发现 60s 内没有收到任何消息（含 PONG）→ 主动重连
 * - 重连：指数退避 1s / 2s / 4s / 8s / 16s，上限 30s；连接成功后拉 /alarms/pending-count 兜底
 * - 线路层由 utils/wsTransport.ts 按 VITE_USE_MOCK 选择：真实 WebSocket 或 mock SSE 桥
 */
import { ref, type Ref } from 'vue'
import type { WsMessage } from '@/types/alarm'
import { WsMessageType } from '@/types/alarm'
import { buildWsUrl, createTransport, type Transport } from '@/utils/wsTransport'

export type WsStatus = 'idle' | 'connecting' | 'open' | 'reconnecting' | 'closed'

export const HEARTBEAT_INTERVAL_MS = 30_000
export const HEARTBEAT_TIMEOUT_MS = 60_000
const WATCHDOG_INTERVAL_MS = 5_000
const BACKOFF_BASE_MS = 1_000
const BACKOFF_MAX_MS = 30_000

type MessageListener = (msg: WsMessage) => void
type OpenListener = (info: { isReconnect: boolean }) => void

class RealtimeClient {
  readonly status: Ref<WsStatus> = ref('idle')
  /** 下一次重连的等待毫秒数（UI 展示用） */
  readonly nextRetryMs: Ref<number> = ref(0)

  private transport: Transport | null = null
  private token = ''
  private retry = 0
  private everOpened = false
  private manualClosed = true
  private lastMessageAt = 0
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null
  private heartbeatTimer: ReturnType<typeof setInterval> | null = null
  private watchdogTimer: ReturnType<typeof setInterval> | null = null
  private readonly messageListeners = new Set<MessageListener>()
  private readonly openListeners = new Set<OpenListener>()

  /** 用指定 token 建立连接；token 未变且连接存活时为 no-op */
  connect(token: string): void {
    if (!token) return
    if (token === this.token && !this.manualClosed && (this.transport || this.reconnectTimer)) return
    this.token = token
    this.manualClosed = false
    this.retry = 0
    this.clearReconnectTimer()
    this.open()
  }

  /** 主动断开（登出时调用），不会触发重连 */
  disconnect(): void {
    this.manualClosed = true
    this.token = ''
    this.everOpened = false
    this.retry = 0
    this.clearReconnectTimer()
    this.teardownTransport()
    this.status.value = 'closed'
  }

  send(msg: Record<string, unknown>): void {
    this.transport?.send(msg)
  }

  subscribe(cb: MessageListener): () => void {
    this.messageListeners.add(cb)
    return () => this.messageListeners.delete(cb)
  }

  onOpen(cb: OpenListener): () => void {
    this.openListeners.add(cb)
    return () => this.openListeners.delete(cb)
  }

  // ---------------- 内部 ----------------

  private open(): void {
    this.teardownTransport()
    this.status.value = this.everOpened ? 'reconnecting' : 'connecting'
    this.transport = createTransport(buildWsUrl(this.token), {
      onOpen: () => this.handleOpen(),
      onMessage: (msg) => this.handleMessage(msg),
      onClose: (reason) => this.handleClose(reason),
    })
  }

  private handleOpen(): void {
    const isReconnect = this.everOpened
    this.everOpened = true
    this.retry = 0
    this.nextRetryMs.value = 0
    this.lastMessageAt = Date.now()
    this.status.value = 'open'
    this.startHeartbeat()
    for (const cb of this.openListeners) {
      try {
        cb({ isReconnect })
      } catch (err) {
        console.error('[ws] open listener error', err)
      }
    }
  }

  private handleMessage(msg: WsMessage): void {
    this.lastMessageAt = Date.now()
    if (!msg || typeof msg !== 'object' || !msg.type) return
    if (msg.type === WsMessageType.PONG) return
    if (msg.type === WsMessageType.PING) {
      this.send({ type: WsMessageType.PONG })
      return
    }
    for (const cb of this.messageListeners) {
      try {
        cb(msg)
      } catch (err) {
        // 单个订阅者异常不能影响其他订阅者，也不能打断连接
        console.error('[ws] subscriber error', err)
      }
    }
  }

  private handleClose(reason: string): void {
    this.stopHeartbeat()
    this.transport = null
    if (this.manualClosed) return
    console.warn(`[ws] disconnected (${reason}), will reconnect`)
    this.scheduleReconnect()
  }

  private scheduleReconnect(): void {
    this.clearReconnectTimer()
    const delay = Math.min(BACKOFF_MAX_MS, BACKOFF_BASE_MS * 2 ** this.retry)
    this.retry += 1
    this.nextRetryMs.value = delay
    this.status.value = 'reconnecting'
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null
      if (!this.manualClosed) this.open()
    }, delay)
  }

  private startHeartbeat(): void {
    this.stopHeartbeat()
    this.heartbeatTimer = setInterval(() => {
      this.send({ type: WsMessageType.PING })
    }, HEARTBEAT_INTERVAL_MS)
    this.watchdogTimer = setInterval(() => {
      if (Date.now() - this.lastMessageAt > HEARTBEAT_TIMEOUT_MS) {
        console.warn('[ws] no message in 60s, force reconnect')
        this.teardownTransport()
        this.scheduleReconnect()
      }
    }, WATCHDOG_INTERVAL_MS)
  }

  private stopHeartbeat(): void {
    if (this.heartbeatTimer) clearInterval(this.heartbeatTimer)
    if (this.watchdogTimer) clearInterval(this.watchdogTimer)
    this.heartbeatTimer = null
    this.watchdogTimer = null
  }

  private teardownTransport(): void {
    this.stopHeartbeat()
    if (this.transport) {
      this.transport.close()
      this.transport = null
    }
  }

  private clearReconnectTimer(): void {
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer)
    this.reconnectTimer = null
  }
}

/** 模块级单例：整个应用只有这一条连接 */
const client = new RealtimeClient()

// 开发期热更新时关掉旧连接，避免 HMR 后出现两条连接
if (import.meta.hot) {
  import.meta.hot.dispose(() => client.disconnect())
}

/** 组件 / store 里使用：拿到全局唯一连接 */
export function useWebSocket() {
  return {
    status: client.status,
    nextRetryMs: client.nextRetryMs,
    connect: (token: string) => client.connect(token),
    disconnect: () => client.disconnect(),
    send: (msg: Record<string, unknown>) => client.send(msg),
    subscribe: (cb: MessageListener) => client.subscribe(cb),
    onOpen: (cb: OpenListener) => client.onOpen(cb),
  }
}
