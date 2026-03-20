/**
 * Skyline — Canvas Renderer composable (Phase 4: State Machine)
 *
 * Rendering modes driven by two booleans:
 *
 *   hasVideo=false → STANDBY screen (grid + scan line animation)
 *   hasVideo=true,  isPlaying=false → static frame (READY / FINISHED)
 *   hasVideo=true,  isPlaying=true  → live frame + BBox overlays (ANALYZING)
 *
 * This means:
 *   - In READY:    first frame is visible, no BBoxes (detections is empty)
 *   - In FINISHED: last frame frozen, last BBoxes remain visible
 *   - In ANALYZING: 60 FPS live render with detection overlays
 */
import { onUnmounted } from 'vue'
import type { Ref } from 'vue'
import type { Detection } from '@/types/skyline'
import { CLASS_COLORS, DEFAULT_DETECTION_COLOR } from '@/types/skyline'
import {
  CANVAS_FONT_MONO,
  CANVAS_FONT_OVERLAY,
  CANVAS_CORNER_SIZE,
  CANVAS_PANEL_WIDTH,
} from '@/config'

interface UseCanvasRendererOptions {
  canvasEl:   Ref<HTMLCanvasElement | null>
  videoEl:    Ref<HTMLVideoElement | null>
  detections: Ref<Detection[]>
  isPlaying:  Ref<boolean>   // true → ANALYZING (draw BBoxes)
  hasVideo:   Ref<boolean>   // true → some source loaded (draw frame vs standby)
}

export function useCanvasRenderer({
  canvasEl,
  videoEl,
  detections,
  isPlaying,
  hasVideo,
}: UseCanvasRendererOptions) {
  let rafId:  number | null = null
  let scanY = 0

  // ── Standby screen ─────────────────────────────────────────────────────────

  function drawStandby(ctx: CanvasRenderingContext2D, w: number, h: number, ts: number) {
    ctx.fillStyle = '#0a0e1a'
    ctx.fillRect(0, 0, w, h)

    // Grid
    ctx.strokeStyle = 'rgba(0, 255, 136, 0.08)'
    ctx.lineWidth = 1
    const step = 40
    for (let x = 0; x <= w; x += step) {
      ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, h); ctx.stroke()
    }
    for (let y = 0; y <= h; y += step) {
      ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(w, y); ctx.stroke()
    }

    // Animated scan line
    scanY = (scanY + 1.5) % h
    const grad = ctx.createLinearGradient(0, scanY - 20, 0, scanY + 4)
    grad.addColorStop(0,   'rgba(0, 255, 136, 0)')
    grad.addColorStop(0.7, 'rgba(0, 255, 136, 0.12)')
    grad.addColorStop(1,   'rgba(0, 255, 136, 0.25)')
    ctx.fillStyle = grad
    ctx.fillRect(0, scanY - 20, w, 24)

    // Corner brackets
    ctx.strokeStyle = 'rgba(0, 255, 136, 0.3)'
    ctx.lineWidth = 1.5
    const m = 20
    const corners: [number, number, number, number][] = [
      [m, m, m, m], [w - m, m, -m, m],
      [m, h - m, m, -m], [w - m, h - m, -m, -m],
    ]
    corners.forEach(([x, y, dx, dy]) => {
      ctx.beginPath()
      ctx.moveTo(x + dx, y); ctx.lineTo(x, y); ctx.lineTo(x, y + dy)
      ctx.stroke()
    })

    // Pulsing center text
    const pulse = 0.6 + 0.4 * Math.sin(ts / 800)
    ctx.globalAlpha = pulse
    ctx.fillStyle = '#00ff88'
    ctx.font = 'bold 20px "Courier New", Courier, monospace'
    ctx.textAlign = 'center'
    ctx.fillText('[ SYSTEM STANDBY ]', w / 2, h / 2 - 16)
    ctx.globalAlpha = pulse * 0.7
    ctx.font = '13px "Courier New", Courier, monospace'
    ctx.fillStyle = '#4dffc3'
    ctx.fillText('PLEASE UPLOAD MEDIA OR CONNECT WEBCAM', w / 2, h / 2 + 12)
    ctx.globalAlpha = 1
    ctx.textAlign = 'left'
  }

  // ── BBox drawing ────────────────────────────────────────────────────────────

  function drawDetection(
    ctx: CanvasRenderingContext2D,
    det: Detection,
    scaleX: number,
    scaleY: number,
  ) {
    const [nx, ny, nw, nh] = det.bbox
    const x = Math.round(nx * scaleX)
    const y = Math.round(ny * scaleY)
    const w = Math.round(nw * scaleX)
    const h = Math.round(nh * scaleY)

    const color = CLASS_COLORS[det.class_name] ?? DEFAULT_DETECTION_COLOR
    const label = `${det.class_name} ${(det.confidence * 100).toFixed(0)}%`

    // Semi-transparent fill
    ctx.fillStyle = hexToRgba(color, 0.12)
    ctx.fillRect(x, y, w, h)

    // Border
    ctx.strokeStyle = color
    ctx.lineWidth = 2
    ctx.strokeRect(x, y, w, h)

    // Corner ticks
    drawCornerTicks(ctx, x, y, w, h, color)

    // Label chip with dark background
    ctx.font = CANVAS_FONT_MONO
    const textW = ctx.measureText(label).width + 10
    const chipH = 18
    const chipY = y - chipH - 1 < 0 ? y + 2 : y - chipH - 1

    ctx.fillStyle = 'rgba(0, 0, 0, 0.75)'
    ctx.fillRect(x, chipY, textW, chipH)
    ctx.strokeStyle = color
    ctx.lineWidth = 1
    ctx.strokeRect(x, chipY, textW, chipH)
    ctx.fillStyle = '#ffffff'
    ctx.fillText(label, x + 5, chipY + 13)
  }

  function drawCornerTicks(
    ctx: CanvasRenderingContext2D,
    x: number, y: number, w: number, h: number,
    color: string,
  ) {
    ctx.strokeStyle = color
    ctx.lineWidth = 2.5
    const c = CANVAS_CORNER_SIZE
    const cs: [number, number, number, number][] = [
      [x, y, c, c], [x + w, y, -c, c],
      [x, y + h, c, -c], [x + w, y + h, -c, -c],
    ]
    cs.forEach(([cx, cy, dx, dy]) => {
      ctx.beginPath()
      ctx.moveTo(cx + dx, cy); ctx.lineTo(cx, cy); ctx.lineTo(cx, cy + dy)
      ctx.stroke()
    })
  }

  // ── Detection summary overlay ───────────────────────────────────────────────

  function drawSummaryOverlay(ctx: CanvasRenderingContext2D, dets: Detection[]) {
    if (dets.length === 0) return
    const counts: Record<string, number> = {}
    dets.forEach((d) => { counts[d.class_name] = (counts[d.class_name] ?? 0) + 1 })

    const lines   = Object.entries(counts).map(([cls, n]) => `${cls.toUpperCase()}: ${n}`)
    const padding = 8
    const lineH   = 18
    const panelW  = CANVAS_PANEL_WIDTH
    const panelH  = lines.length * lineH + padding * 2

    ctx.fillStyle = 'rgba(0, 0, 0, 0.65)'
    ctx.fillRect(12, 12, panelW, panelH)
    ctx.strokeStyle = 'rgba(0, 255, 136, 0.5)'
    ctx.lineWidth = 1
    ctx.strokeRect(12, 12, panelW, panelH)

    ctx.font = CANVAS_FONT_OVERLAY
    lines.forEach((line, i) => {
      const cls = Object.keys(counts)[i]
      ctx.fillStyle = CLASS_COLORS[cls] ?? DEFAULT_DETECTION_COLOR
      ctx.fillText(line, 12 + padding, 12 + padding + 13 + i * lineH)
    })
  }

  // ── Main render loop ────────────────────────────────────────────────────────

  function renderFrame(ts: number) {
    rafId = requestAnimationFrame(renderFrame)

    const canvas = canvasEl.value
    if (!canvas) return
    const ctx = canvas.getContext('2d')!
    const w = canvas.width
    const h = canvas.height

    const video = videoEl.value

    // ── STANDBY: no video source loaded ────────────────────────────────────
    if (!hasVideo.value || !video || video.readyState < HTMLMediaElement.HAVE_CURRENT_DATA) {
      drawStandby(ctx, w, h, ts)
      return
    }

    // ── READY / ANALYZING / FINISHED: draw current video frame ─────────────
    ctx.clearRect(0, 0, w, h)
    ctx.drawImage(video, 0, 0, w, h)

    // BBoxes: render in ANALYZING (live) and FINISHED (frozen last frame)
    // In READY, detections is always empty so nothing is drawn regardless
    if (detections.value.length > 0) {
      const scaleX = w / (video.videoWidth || w)
      const scaleY = h / (video.videoHeight || h)
      detections.value.forEach((det) => drawDetection(ctx, det, scaleX, scaleY))
      drawSummaryOverlay(ctx, detections.value)
    }

    // Subtle "REC" indicator while actively streaming
    if (isPlaying.value) {
      ctx.fillStyle = '#ff3366'
      ctx.beginPath()
      ctx.arc(w - 18, 18, 5, 0, Math.PI * 2)
      ctx.fill()
      ctx.fillStyle = 'rgba(255,255,255,0.85)'
      ctx.font = '10px "Courier New", Courier, monospace'
      ctx.textAlign = 'right'
      ctx.fillText('REC', w - 26, 22)
      ctx.textAlign = 'left'
    }
  }

  function startRendering() {
    if (rafId !== null) return
    rafId = requestAnimationFrame(renderFrame)
  }

  function stopRendering() {
    if (rafId !== null) {
      cancelAnimationFrame(rafId)
      rafId = null
    }
  }

  onUnmounted(stopRendering)

  return { startRendering, stopRendering }
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function hexToRgba(hex: string, alpha: number): string {
  const r = parseInt(hex.slice(1, 3), 16)
  const g = parseInt(hex.slice(3, 5), 16)
  const b = parseInt(hex.slice(5, 7), 16)
  return `rgba(${r}, ${g}, ${b}, ${alpha})`
}
