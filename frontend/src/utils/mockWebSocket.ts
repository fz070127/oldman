/**
 * Mock WebSocket 客户端（浏览器侧）
 *
 * 与真实 WebSocket 保持同一套 subscribe / connect / close 接口，
 * F6 切真实 WS 时只需换实现，订阅代码不动。
 *
 * 为什么不是 EventTarget：
 * mock 的 emit 发生在 vite-plugin-mock 的 Node 进程里，浏览器拿不到那份内存总线。
 * 这里改成订阅 SSE 端点 GET /api/v1/mock/ws，由 Node 侧把每条消息推下来。
 *
 * 契约 3.12 的断线重连（1s/2s/4s/8s，上限 30s）由 EventSource 自动重连兜底；
 * 重连后前端仍应主动拉一次 /alarms/pending-count 补数（F6 负责）。
 */
import type { WsMessage } from '@/types/alarm'

export interface MockWebSocketLike {
  /** 订阅消息，返回取消订阅函数（可重复调用） */
  subscribe<T = unknown>(cb: (msg: WsMessage<T>) => void): () => void
  /** 建立连接 */
  connect(): void
  /** 断开连接 */
  close(): void
  /** 当前是否已连上 */
  readonly connected: boolean
}

const SSE_URL = '/api/v1/mock/ws'

export function createMockWebSocket(): MockWebSocketLike {
  const listeners = new Set<(msg: WsMessage<never>) => void>()
  let source: EventSource | null = null
  let connected = false

  const dispatch = (msg: WsMessage) => {
    for (const cb of listeners) {
      try {
        cb(msg as WsMessage<never>)
      } catch (err) {
        // 单个订阅者抛错不能影响其他订阅者
        console.error('[mock-ws] subscriber error', err)
      }
    }
  }

  return {
    subscribe<T = unknown>(cb: (msg: WsMessage<T>) => void) {
      listeners.add(cb as (msg: WsMessage<never>) => void)
      return () => {
        listeners.delete(cb as (msg: WsMessage<never>) => void)
      }
    },

    connect() {
      if (source) return
      source = new EventSource(SSE_URL)
      source.onopen = () => {
        connected = true
      }
      source.onmessage = (evt) => {
        try {
          dispatch(JSON.parse(evt.data) as WsMessage)
        } catch (err) {
          console.error('[mock-ws] bad message', evt.data, err)
        }
      }
      source.onerror = () => {
        connected = false
        // EventSource 默认会自己按浏览器的节奏重连，这里不主动 close
      }
    },

    close() {
      source?.close()
      source = null
      connected = false
    },

    get connected() {
      return connected
    },
  }
}