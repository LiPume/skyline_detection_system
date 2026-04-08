/**
 * Skyline — WebSocket composable
 *
 * Features:
 * - Exponential backoff auto-reconnect (1s → 2s → 4s → … → 30s max)
 * - Reactive connection status
 * - Typed message dispatch via onMessage callback
 * - Heartbeat ping/pong to detect dead connections
 * - Visibility-aware reconnect: suppressed while page is hidden,
 *   controlled single reconnect when page becomes visible again
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
  /** Resolved when ws is OPEN, or immediately if already connected.
   *  Useful after a visibility-change reconnect to know when it's safe to resume. */
  waitForConnected: () => Promise<void>
}

export function useWebSocket({ onMessage, onSendFailure }: UseWebSocketOptions): UseWebSocketReturn {
  const status = ref<WsStatus>('disconnected')
  const sendFailCount = ref(0)

  let ws: WebSocket | null = null
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null
  let reconnectDelay = WS_BASE_RECONNECT_DELAY_MS
  let manualDisconnect = false
  let heartbeatTimer: ReturnType<typeof setInterval> | null = null
  let heartbeatTimeoutTimer: ReturnType<typeof setTimeout> | null = null
  let lastPongTime = 0

  // ── Visibility-aware reconnect guard ───────────────────────────────────────
  // Set to true while we are mid-reconnect triggered by a visibility change.
  // Prevents multiple simultaneous reconnect attempts.
  let isRecovering = false

  // Promise resolve held while waiting for OPEN after a reconnect.
  // Allows callers (e.g. Detection.vue) to await connection.
  let pendingConnectedResolve: (() => void) | null = null

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
    // Block duplicate connect at both OPEN and CONNECTING
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

      // Resolve any pending waitForConnected call
      if (pendingConnectedResolve) {
        pendingConnectedResolve()
        pendingConnectedResolve = null
      }
    }

    ws.onmessage = (event: MessageEvent<string>) => {
      const data = event.data

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

      // Clear pending connected promise so callers don't hang forever
      if (pendingConnectedResolve) {
        pendingConnectedResolve()
        pendingConnectedResolve = null
      }

      // Visibility-aware: do NOT schedule reconnect while page is hidden.
      // The visibility handler will take care of reconnecting when the page returns.
      if (!manualDisconnect && document.visibilityState !== 'hidden') {
        scheduleReconnect()
      }
    }

    ws.onerror = () => {
      // onerror is always followed by onclose — nothing extra needed
    }
  }

  function scheduleReconnect() {
    // Visibility guard: never blind-reconnect while hidden.
    // This fires for background-tab heartbeat timeouts, etc.
    if (document.visibilityState === 'hidden') {
      return
    }

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
    if (pendingConnectedResolve) {
      pendingConnectedResolve()
      pendingConnectedResolve = null
    }
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

  /** Resolved when ws is OPEN, or immediately if already connected. */
  function waitForConnected(): Promise<void> {
    if (status.value === 'connected' && ws?.readyState === WebSocket.OPEN) {
      return Promise.resolve()
    }
    return new Promise<void>(resolve => {
      pendingConnectedResolve = resolve
    })
  }

  // ── Visibility change handler ───────────────────────────────────────────────
  // NOTE: Detection.vue also listens to visibilitychange for its own
  // wasAnalyzingBeforeHidden state. The WS handler below ONLY manages
  // the connection layer; it does NOT stop/start analysis.
  function handleVisibilityChange() {
    if (document.visibilityState === 'hidden') {
      console.log('[VIS] hidden')
      // Do NOT disconnect here — let the socket stay alive if it can.
      // The onclose handler will refuse to scheduleReconnect while hidden.
      return
    }

    // visible
    console.log('[VIS] visible')

    // Check WS health
    if (ws && ws.readyState === WebSocket.OPEN) {
      console.log('[VIS] ws healthy')
      return
    }
    console.log('[VIS] ws unhealthy')

    // Prevent double-reconnect if a recovery is already in flight
    if (isRecovering) {
      return
    }

    console.log('[VIS] reconnect requested')
    isRecovering = true

    forceReconnect()

    // Clear the flag after a generous window (the onopen handler also clears it
    // via pendingConnectedResolve, but this is a safety net in case connect()
    // gets blocked by the duplicate guard and never fires onopen).
    setTimeout(() => {
      isRecovering = false
    }, 10_000)
  }

  document.addEventListener('visibilitychange', handleVisibilityChange)

  onUnmounted(() => {
    document.removeEventListener('visibilitychange', handleVisibilityChange)
    disconnect()
  })

  return { status, sendFailCount, connect, disconnect, send, forceReconnect, waitForConnected }
}
