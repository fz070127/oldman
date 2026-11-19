/**
 * Mock 实时通道（浏览器侧）—— 只在 VITE_USE_MOCK=true 时被 wsTransport.ts 选中
 *
 * 为什么不是 EventTarget：
 * mock 的 emit 发生在 vite-plugin-mock 的 Node 进程里，浏览器拿不到那份内存总线。
 * 这里订阅 SSE 端点 GET /api/v1/mock/ws，由 Node 侧把每条消息推下来（见 src/mock/index.ts）。
 *
 * 与原生 WebSocket Transport 行为对齐：
 * - SSE 出错时**主动关闭**，不用 EventSource 自带的重连，
 *   把重连交还给 useWebSocket 的指数退避（1s/2s/4s/8s…≤30s），两种通道表现一致
 * - SSE 是单向的，客户端发 PING 时本地回一条 PONG，让心跳看门狗逻辑保持统一
 */
import type { WsMessage } from '@/types/alarm'
import type { TransportFactory } from './wsTransport'

const SSE_URL = `${(import.meta.env.VITE_API_BASE || '/api/v1').replace(/\/$/, '')}/mock/ws`

export const createMockTransport: TransportFactory = (_url, handlers) => {
  let source: EventSource | null = new EventSource(SSE_URL)
  let closed = false

  source.onopen = () => handlers.onOpen()
  source.onmessage = (evt) => {
    try {
      handlers.onMessage(JSON.parse(evt.data) as WsMessage)
    } catch (err) {
      console.error('[mock-ws] bad message', evt.data, err)
    }
  }
  source.onerror = () => {
    if (closed) return
    closed = true
    source?.close()
    source = null
    handlers.onClose('sse error')
  }

  return {
    send(msg) {
      if (closed || msg.type !== 'PING') return
      setTimeout(() => {
        if (closed) return
        handlers.onMessage({ type: 'PONG', ts: new Date().toISOString(), data: null })
      }, 20)
    },
    close() {
      closed = true
      source?.close()
      source = null
    },
  }
}
