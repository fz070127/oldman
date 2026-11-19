/**
 * 实时通道 Transport 层（只负责“线”，不负责心跳 / 重连 / 分发）
 *
 * 契约 3.12：ws(s)://<host>/api/v1/ws?token=<accessToken>
 *
 * - VITE_USE_MOCK=false → createNativeTransport：浏览器原生 WebSocket，直连 M7
 * - VITE_USE_MOCK=true  → createMockTransport：SSE 桥（src/mock/index.ts），
 *                         消息结构与真实 WS 完全一致
 *
 * 心跳、指数退避重连、pending-count 兜底等逻辑都在 hooks/useWebSocket.ts 里，
 * 对两种 Transport 一视同仁 —— M7 上线时只改 .env 的 VITE_USE_MOCK，不改业务代码。
 */
import type { WsMessage } from '@/types/alarm'
import { createMockTransport } from './mockWebSocket'

export interface TransportHandlers {
  onOpen: () => void
  onMessage: (msg: WsMessage) => void
  /** 连接断开（含握手失败）。主动 close() 不会触发 */
  onClose: (reason: string) => void
}

export interface Transport {
  send: (msg: Record<string, unknown>) => void
  /** 主动关闭（不触发 onClose） */
  close: () => void
}

export type TransportFactory = (url: string, handlers: TransportHandlers) => Transport

export const USE_MOCK_TRANSPORT = import.meta.env.VITE_USE_MOCK === 'true'

/** 组装契约 3.12 的连接地址（兼容 VITE_API_BASE 为相对路径或绝对 http(s) 地址） */
export function buildWsUrl(token: string): string {
  const base = (import.meta.env.VITE_API_BASE || '/api/v1').replace(/\/$/, '')
  const query = `token=${encodeURIComponent(token)}`
  if (/^https?:\/\//i.test(base)) {
    return `${base.replace(/^http/i, 'ws')}/ws?${query}`
  }
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${proto}//${window.location.host}${base}/ws?${query}`
}

/** 原生 WebSocket（M7 上线后使用） */
export const createNativeTransport: TransportFactory = (url, handlers) => {
  const ws = new WebSocket(url)
  let closedByUser = false

  ws.onopen = () => handlers.onOpen()
  ws.onmessage = (evt) => {
    try {
      handlers.onMessage(JSON.parse(String(evt.data)) as WsMessage)
    } catch (err) {
      console.error('[ws] bad message', evt.data, err)
    }
  }
  // onerror 之后浏览器一定会再触发 onclose，统一在 onclose 里处理
  ws.onerror = () => undefined
  ws.onclose = (evt) => {
    if (closedByUser) return
    // 4401 token 无效 / 4408 心跳超时（契约 3.12）
    handlers.onClose(`code=${evt.code}${evt.reason ? ` reason=${evt.reason}` : ''}`)
  }

  return {
    send(msg) {
      if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(msg))
    },
    close() {
      closedByUser = true
      try {
        ws.close(1000, 'client close')
      } catch {
        /* ignore */
      }
    },
  }
}

/** 按环境选择 Transport */
export const createTransport: TransportFactory = USE_MOCK_TRANSPORT
  ? createMockTransport
  : createNativeTransport
