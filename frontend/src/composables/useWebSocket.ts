/**
 * Skyline — WebSocket composable
 *
 * Features:
 * - Exponential backoff auto-reconnect (1s → 2s → 4s → … → 30s max)
 * - Reactive connection status
 * - Typed message dispatch via onMessage callback
 * - Heartbeat ping/pong to detect dead connections
 */
import { ref, onUnmounted } from 'vue'
import type { Ref } from 'vue'
import type { ServerMessage, WsStatus } from '@/types/skyline'
import {
  WS_URL,
  WS_MAX_RECONNECT_DELAY_MS,
  WS_BASE_RECONNECT_DELAY_MS,
} from '@/config'

// Heartbeat settings (must match backend)
const HEARTBEAT_INTERVAL_MS = 15_000
const HEARTBEAT_TIMEOUT_MS = 20_000
const PING_MESSAGE = "__heartbeat_ping__"
const PONG_MESSAGE = "__heartbeat_pong__"

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
  /** Force reconnect - useful when page becomes visible again */
  forceReconnect: () => void
}

export function useWebSocket({ onMessage, onSendFailure }: UseWebSocketOptions): UseWebSocketReturn {
  const status = ref<WsStatus>('disconnected')
  const sendFailCount = ref(0)

  let ws: WebSocket | null = null
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null
  let reconnectDelay = WS_BASE_RECONNECT_DELAY_MS
  let manualDisconnect = false
  let heartbeatTimer: ReturnType<typeof setTimeout> | null = null
  let heartbeatTimeoutTimer: ReturnType<typeof setTimeout> | null = null
  let lastPongTime = 0

  function clearReconnectTimer() {
    if (reconnectTimer !== null) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
  }

  function clearHeartbeatTimers() {
    if (heartbeatTimer !== null) {
      clearInterval(heartbeatTimer)
      heartbeatTimer = null
    }
    if (heartbeatTimeoutTimer !== null) {
      clearTimeout(heartbeatTimeoutTimer)
      heartbeatTimeoutTimer = null
    }
  }

  function startHeartbeat() {
    clearHeartbeatTimers()
    lastPongTime = Date.now()

    heartbeatTimer = setInterval(() => {
      if (ws?.readyState === WebSocket.OPEN) {
        ws.send(PING_MESSAGE)

        // Set timeout for pong response
        heartbeatTimeoutTimer = setTimeout(() => {
          const timeSincePong = Date.now() - lastPongTime
          if (timeSincePong > HEARTBEAT_TIMEOUT_MS) {
            console.warn('[WS] Heartbeat timeout, reconnecting...')
            ws?.close()
          }
        }, HEARTBEAT_TIMEOUT_MS)
      }
    }, HEARTBEAT_INTERVAL_MS)
  }

  function handlePong() {
    lastPongTime = Date.now()
    if (heartbeatTimeoutTimer !== null) {
      clearTimeout(heartbeatTimeoutTimer)
      heartbeatTimeoutTimer = null
    }
  }

  function connect() {
    console.log('[WS] connect requested')
    if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
      console.log('[WS] duplicate connect blocked')
      return
    }

    manualDisconnect = false
    clearReconnectTimer()
    clearHeartbeatTimers()

    status.value = 'connecting'
    ws = new WebSocket(WS_URL)

    ws.onopen = () => {
      console.log('[WS] open')
      status.value = 'connected'
      reconnectDelay = WS_BASE_RECONNECT_DELAY_MS
      startHeartbeat()
    }

    ws.onmessage = (event: MessageEvent<string>) => {
      const data = event.data

      // Handle heartbeat messages
      if (data === PONG_MESSAGE) {
        handlePong()
        return
      }
      if (data === PING_MESSAGE) {
        ws?.send(PONG_MESSAGE)
        return
      }

      try {
        const parsed = JSON.parse(data) as ServerMessage
        onMessage(parsed)
      } catch {
        // silently drop malformed messages
      }
    }

    ws.onclose = () => {
      console.log('[WS] close')
      status.value = 'disconnected'
      clearHeartbeatTimers()
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
    clearHeartbeatTimers()
    ws?.close()
    ws = null
    status.value = 'disconnected'
  }

  function forceReconnect() {
    manualDisconnect = false
    clearReconnectTimer()
    clearHeartbeatTimers()
    ws?.close()
    ws = null
    status.value = 'disconnected'
    reconnectDelay = WS_BASE_RECONNECT_DELAY_MS
    connect()
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

  // Handle visibility change to reconnect if page was hidden
  function handleVisibilityChange() {
    if (document.visibilityState === 'visible' && status.value === 'disconnected' && !manualDisconnect) {
      console.log('[WS] Page became visible, attempting reconnect...')
      forceReconnect()
    }
  }

  document.addEventListener('visibilitychange', handleVisibilityChange)

  onUnmounted(() => {
    document.removeEventListener('visibilitychange', handleVisibilityChange)
    disconnect()
  })

  return { status, sendFailCount, connect, disconnect, send, forceReconnect }
}
