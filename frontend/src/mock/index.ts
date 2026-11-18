/**
 * Mock 实时消息总线（EventTarget 实现）+ SSE 桥
 *
 * 为什么不能只用 EventTarget：
 * vite-plugin-mock 用 bundle-require 在 **Vite 的 Node 进程**里加载本文件，
 * 浏览器侧 import 到的是另一份实例，两边 globalThis 不共享。
 * 所以 Node 里 emit 的消息，浏览器订阅者永远收不到。
 *
 * 方案：
 * - 总线本身用 EventTarget，Node 侧 emit/subscribe 行为不变（契约 3.12 消息结构原样）
 * - 额外挂一个 `/api/v1/mock/ws` 的 SSE 端点：浏览器 EventSource 订阅它，
 *   每次 emit 由 Node 进程把消息真正推下去
 *
 * 用法（F6）：
 *   const ws = createMockWebSocket()   // VITE_USE_MOCK=true 时用这个
 *   const off = ws.subscribe((msg) => { ... })
 *   ws.connect()
 *
 * 客户端实现见 src/utils/mockWebSocket.ts。
 */
import type { MockMethod } from 'vite-plugin-mock'
import type { ServerResponse } from 'node:http'
import type { WsMessage } from '@/types/alarm'

export type MockWsCallback<T = unknown> = (msg: WsMessage<T>) => void

const WS_EVENT_NAME = 'mock-ws-message'

const GLOBAL_WS_KEY = '__SILVER_BELL_MOCK_WS__'
const GLOBAL_SSE_KEY = '__SILVER_BELL_MOCK_SSE__'

/** 已连接的 SSE 客户端 */
interface SseHub {
  clients: Set<ServerResponse>
}

class MockWsBus {
  private target: EventTarget

  constructor() {
    this.target = new EventTarget()
  }

  /** 订阅模拟 WebSocket 消息，返回取消订阅函数 */
  subscribe<T = unknown>(cb: MockWsCallback<T>): () => void {
    const handler = (evt: Event) => {
      const customEvt = evt as CustomEvent<WsMessage<T>>
      cb(customEvt.detail)
    }
    this.target.addEventListener(WS_EVENT_NAME, handler)
    return () => {
      this.target.removeEventListener(WS_EVENT_NAME, handler)
    }
  }

  /** 广播一条模拟 WebSocket 消息：本进程订阅者 + 所有 SSE 客户端 */
  emit<T = unknown>(msg: WsMessage<T>): void {
    // Node 18+ 与现代浏览器均原生支持 CustomEvent + EventTarget
    this.target.dispatchEvent(new CustomEvent<WsMessage<T>>(WS_EVENT_NAME, { detail: msg }))
    pushToSseClients(msg)
  }
}

function getGlobal<T>(key: string, factory: () => T): T {
  const g = globalThis as unknown as Record<string, T | undefined>
  if (!g[key]) g[key] = factory()
  return g[key] as T
}

export const mockWs = getGlobal<MockWsBus>(GLOBAL_WS_KEY, () => new MockWsBus())

const sseHub = getGlobal<SseHub>(GLOBAL_SSE_KEY, () => ({ clients: new Set<ServerResponse>() }))

/** 把消息写进每一条 SSE 连接；写失败的连接直接摘掉 */
function pushToSseClients(msg: WsMessage): void {
  const payload = `data: ${JSON.stringify(msg)}\n\n`
  for (const res of sseHub.clients) {
    try {
      res.write(payload)
    } catch {
      sseHub.clients.delete(res)
    }
  }
}

/**
 * GET /api/v1/mock/ws —— SSE 端点，把 mockWs.emit 的消息推给浏览器
 *
 * 用 rawResponse 接管响应体，避免 vite-plugin-mock 走 JSON 序列化。
 * 连接建立后先补一条 PONG 作为握手确认，客户端据此判断通道可用。
 */
export const mockWsSse: MockMethod = {
  url: '/api/v1/mock/ws',
  method: 'get',
  rawResponse: (_req, res) => {
    res.writeHead(200, {
      'Content-Type': 'text/event-stream; charset=utf-8',
      'Cache-Control': 'no-cache, no-transform',
      Connection: 'keep-alive',
      // 关掉 nginx 等中间层的缓冲，否则事件会被攒着一起发
      'X-Accel-Buffering': 'no',
    })
    res.write(': connected\n\n')
    sseHub.clients.add(res)

    // 25 秒心跳：防止浏览器/代理把空闲连接掐掉
    const heartbeat = setInterval(() => {
      try {
        res.write(': ping\n\n')
      } catch {
        cleanup()
      }
    }, 25000)

    const cleanup = () => {
      clearInterval(heartbeat)
      sseHub.clients.delete(res)
    }
    res.on('close', cleanup)
    res.on('error', cleanup)
  },
}

// vite-plugin-mock 扫描 src/mock/*.ts 时读取 default 导出
export default [mockWsSse] as MockMethod[]