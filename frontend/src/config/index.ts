/**
 * Skyline — Global configuration
 * All magic numbers and environment-dependent constants live here.
 * Import from this file instead of hardcoding values across the codebase.
 */

// ── Backend server ────────────────────────────────────────────────────────────

export const BACKEND_PORT = Number(
  import.meta.env.VITE_BACKEND_PORT ?? 8000,
)

// REST API base URL (used by fetch / axios)
export const API_BASE_URL = `http://${window.location.hostname}:${BACKEND_PORT}`

// ── WebSocket ────────────────────────────────────────────────────────────────

export const WS_URL = (import.meta.env.VITE_WS_URL as string | undefined) ??
  `ws://${window.location.hostname}:${BACKEND_PORT}/api/ws/video_stream`

export const WS_MAX_RECONNECT_DELAY_MS = 30_000
export const WS_BASE_RECONNECT_DELAY_MS = 1_000

// ── Video / Camera ──────────────────────────────────────────────────────────

export const VIDEO_TARGET_FPS    = 20
export const VIDEO_THROTTLED_FPS = 10
export const VIDEO_JPEG_QUALITY  = 0.7

export const CAMERA_CONSTRAINTS: MediaTrackConstraints = {
  video: { width: { ideal: 1280 }, height: { ideal: 720 }, frameRate: { ideal: 30 } },
  audio: false,
}

// ── Performance thresholds ───────────────────────────────────────────────────

/** Latency above this value triggers automatic FPS throttling. */
export const LATENCY_THROTTLE_THRESHOLD_MS = 200

/** Max value used to scale the latency progress bar. */
export const LATENCY_BAR_MAX_MS = 300

// ── Canvas rendering ─────────────────────────────────────────────────────────

export const CANVAS_FONT_MONO    = '12px "Courier New", Courier, monospace'
export const CANVAS_FONT_OVERLAY = 'bold 13px "Courier New", Courier, monospace'
export const CANVAS_CORNER_SIZE  = 10
export const CANVAS_PANEL_WIDTH   = 160
