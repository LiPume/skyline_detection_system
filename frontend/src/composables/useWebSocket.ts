/**
 * Skyline — WebSocket composable
 *
 * Features:
 * - Exponential backoff auto-reconnect (1s → 2s → 4s → … → 30s max)
 * - Reactive connection status
 * - Typed message dispatch via onMessage callback
 */
import { ref, onUnmounted } from 'vue'
import type { Ref } from 'vue'
import type { ServerMessage, WsStatus } from '@/types/skyline'
import {
  WS_URL,
  WS_MAX_RECONNECT_DELAY_MS,
  WS_BASE_RECONNECT_DELAY_MS,
} from '@/config'

interface UseWebSocketOptions {
  onMessage: (msg: ServerMessage) => void
  /** Called whenever a frame message is dropped because the socket is not open. */
  onSendFailure?: () => void
}

interface UseWebSocketReturn {
  status: Ref<WsStatus>
  /** Number of frames dropped because the socket was not ready. */
  sendFailCount: Ref<number>
  connect: () => void
  disconnect: () => void
  send: (data: string) => boolean
}

export function useWebSocket({ onMessage, onSendFailure }: UseWebSocketOptions): UseWebSocketReturn {
  const status = ref<WsStatus>('disconnected')
  const sendFailCount = ref(0)

  let ws: WebSocket | null = null
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null
  let reconnectDelay = WS_BASE_RECONNECT_DELAY_MS
  let manualDisconnect = false

  function clearReconnectTimer() {
    if (reconnectTimer !== null) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
  }

  function connect() {
    manualDisconnect = false
    clearReconnectTimer()

    if (ws && ws.readyState === WebSocket.OPEN) return

    status.value = 'connecting'
    ws = new WebSocket(WS_URL)

    ws.onopen = () => {
      status.value = 'connected'
      reconnectDelay = WS_BASE_RECONNECT_DELAY_MS // reset backoff on success
    }

    ws.onmessage = (event: MessageEvent<string>) => {
      try {
        const parsed = JSON.parse(event.data) as ServerMessage
        onMessage(parsed)
      } catch {
        // silently drop malformed messages
      }
    }

    ws.onclose = () => {
      status.value = 'disconnected'
      ws = null
      if (!manualDisconnect) {
        scheduleReconnect()
      }
    }

    ws.onerror = () => {
      // onerror is always followed by onclose — nothing extra needed
    }
  }

  function scheduleReconnect() {
    clearReconnectTimer()
    reconnectTimer = setTimeout(() => {
      reconnectDelay = Math.min(reconnectDelay * 2, WS_MAX_RECONNECT_DELAY_MS)
      connect()
    }, reconnectDelay)
  }

  function disconnect() {
    manualDisconnect = true
    clearReconnectTimer()
    ws?.close()
    ws = null
    status.value = 'disconnected'
  }

  /** Returns true if the message was queued for send. */
  function send(data: string): boolean {
    if (ws?.readyState === WebSocket.OPEN) {
      ws.send(data)
      return true
    }
    sendFailCount.value++
    onSendFailure?.()
    return false
  }

  onUnmounted(disconnect)

  return { status, sendFailCount, connect, disconnect, send }
}
