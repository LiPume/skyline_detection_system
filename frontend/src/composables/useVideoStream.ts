/**
 * Skyline — Video Stream composable (Phase 4: State Machine)
 *
 * Responsibilities split into clear stages:
 *   loadFile()     → READY:     load video, draw first frame, do NOT play, do NOT push
 *   startPush()    → ANALYZING: begin frame capture + WebSocket streaming
 *   stopPush()     → pause streaming (video stays paused at last frame)
 *   selectWebcam() → ANALYZING immediately (live feed has no "ready" stage)
 *   release()      → STANDBY:   tear down all media resources
 *
 * Key differences from Phase 1:
 *   - selectFile() removed; replaced by loadFile() which does NOT auto-play
 *   - hasVideo ref: true once video has data (drives canvas standby vs. frame display)
 *   - video.loop removed from file mode (we need the 'ended' event for state machine)
 * 
 * Phase 3.1: Updated to support model capability driven frame data
 */
import { ref, computed, onUnmounted } from 'vue'
import type { Ref } from 'vue'
import type { VideoSourceType } from '@/types/skyline'
import {
  VIDEO_TARGET_FPS,
  VIDEO_THROTTLED_FPS,
  VIDEO_JPEG_QUALITY,
  CAMERA_CONSTRAINTS,
} from '@/config'

interface UseVideoStreamOptions {
  videoEl: Ref<HTMLVideoElement | null>
  systemLatency: Ref<number>
  // Phase 3.1: Model-related refs for dynamic configuration
  modelId: Ref<string>
  promptClasses: Ref<string[]>
  selectedClasses: Ref<string[]>
  onFrame: (frameData: { 
    frame_id: number
    timestamp: number
    image_base64: string
    model_id: string
    prompt_classes: string[]
    selected_classes: string[]
  }) => void
  // [临时测速] 编码完成回调，传入编码耗时(ms)
  onEncode?: (encodeMs: number) => void
}

interface UseVideoStreamReturn {
  sourceType: Ref<VideoSourceType>
  isPlaying: Ref<boolean>   // true only while frames are being pushed (ANALYZING)
  hasVideo:  Ref<boolean>   // true once a source is loaded (READY / ANALYZING / FINISHED)
  loadFile:     (file: File) => void
  selectWebcam: () => Promise<void>
  startPush:    () => void
  stopPush:     () => void
  release:      () => void
  resetVideo:   () => void  // Reset to standby state (stops push, releases resources)
  /** 背压 ACK：收到 inference_result 时调用，告知该帧已完成，允许发下一帧 */
  ackFrame: (frameId: number) => void
  /** 诊断：pending 是否为 true */
  pending:        Ref<boolean>
  /** 诊断：当前等待的 frame_id（-1 表示无 pending） */
  pendingFrameId: Ref<number>
  /** 诊断：pending 已持续多少 ms */
  pendingAgeMs:   Ref<number>
  /** 渲染门控用：最近一次发送的 frame_id（发送前已自增，故为 frameId - 1） */
  latestSentFrameId: Ref<number>
}

export function useVideoStream({
  videoEl,
  systemLatency,
  modelId,
  promptClasses,
  selectedClasses,
  onFrame,
  onEncode,
}: UseVideoStreamOptions): UseVideoStreamReturn {
  const sourceType = ref<VideoSourceType>('local_file')
  const isPlaying  = ref(false)
  const hasVideo   = ref(false)

  let frameId        = 0
  let pushTimerId: ReturnType<typeof setTimeout> | null = null
  let currentBlobUrl: string | null = null
  let webcamStream:   MediaStream  | null = null

  // ── 背压机制：最多 1 帧 in-flight ─────────────────────────────────────────
  // pending：当前是否有帧正在等待 inference_result
  // pendingFrameId：正在等待的那帧的 frame_id（用于日志和 ACK 对齐）
  let pending        = false
  let pendingFrameId = -1
  let pendingTimerId: ReturnType<typeof setTimeout> | null = null
  let pendingSetAt   = 0   // pending 置 true 时的 performance.now()，用于计算 pendingAgeMs
  // 用于限频日志：上一次打印各 tag 日志的时间戳（毫秒），每个 tag 独立计数
  const lastLogTime: Record<string, number> = {}
  const LOG_INTERVAL_MS = 3000  // 相同日志至少间隔 3s，避免刷屏

  /**
   * 限频日志辅助。
   * tag: 日志标签（与 lastLogTime[key] 一一对应），msg: 日志正文。
   * 仅当距上次打印同 tag 超过 LOG_INTERVAL_MS 时才输出。
   */
  function pushLog(tag: string, msg: string) {
    const now = performance.now()
    if (!lastLogTime[tag] || now - lastLogTime[tag] >= LOG_INTERVAL_MS) {
      console.log(`[PUSH] [${tag}] ${msg}`)
      lastLogTime[tag] = now
    }
  }

  /** 计算当前 pending 已持续多少 ms（0 表示当前无 pending） */
  function getPendingAgeMs(): number {
    return pending ? performance.now() - pendingSetAt : 0
  }

  /**
   * 释放 pending 状态，允许发送下一帧。
   * 由 Detection.vue 在收到 inference_result 时调用。
   *
   * 策略说明：
   * - 按 frame_id 精确对齐：只对匹配的那帧 ACK（防止乱序结果误释放 pending）。
   * - 若当前 pending 为 false 或 frame_id 不匹配，则忽略（防止串台）。
   * - 降级保护：若 pending 已超时（age >= PENDING_TIMEOUT_MS），且收到的结果帧号
   *   大于 pendingFrameId（说明中间丢了帧），允许强制释放 pending 一次，防止长视频
   *   跑久后因一帧之差永久卡死。
   */
  function ackFrame(frameId: number) {
    if (!pending) {
      pushLog('ack-ignored', `id=${frameId} but not pending`)
      return
    }
    if (pendingFrameId !== frameId) {
      const age = getPendingAgeMs()
      if (age >= PENDING_TIMEOUT_MS && frameId > pendingFrameId) {
        const lost = frameId - pendingFrameId
        pushLog('ack-degraded', `id=${frameId} > pendingId=${pendingFrameId} lost=${lost} force-clear`)
        _clearPending('degraded-ack')
        triggerTickIfPlaying()
      } else {
        pushLog('ack-mismatch', `id=${frameId} != pendingId=${pendingFrameId} age=${Math.round(age)}ms`)
      }
      return
    }
    _clearPending('ack')
    pushLog('frame ack', `id=${frameId} age=${Math.round(getPendingAgeMs())}ms`)
    triggerTickIfPlaying()
  }

  /**
   * 内部统一清理 pending 状态。
   * reason: 清理来源标识，用于日志记录。
   */
  function _clearPending(reason: string) {
    pending        = false
    pendingFrameId = -1
    if (pendingTimerId !== null) {
      clearTimeout(pendingTimerId)
      pendingTimerId = null
    }
    pushLog('pending cleared', `reason=${reason} age=${Math.round(getPendingAgeMs())}ms`)
  }

  function clearPending() {
    _clearPending('explicit')
  }

  // Adaptive FPS control state
  let consecutiveHighLatency = 0
  let currentFpsLevel = 0  // 0=normal, 1=throttled
  const HIGH_LATENCY_THRESHOLD = 250  // ms - start throttling earlier
  const RECOVERY_THRESHOLD = 3  // consecutive low-latency frames to recover
  const LOW_LATENCY_RECOVERY = 180  // ms - latency to consider "recovered"
  const PENDING_TIMEOUT_MS  = 1800  // pending 帧超时兜底（ms）

  // Dedicated offscreen canvas for frame extraction
  const offscreen = document.createElement('canvas')
  const offCtx    = offscreen.getContext('2d')!

  /**
   * 若正在播放且未在调度下一帧，则立即调度一次 tick（用于 pending 释放后立即续传）。
   * 不会重置现有调度；只作为"补火"使用。
   */
  function triggerTickIfPlaying() {
    if (!isPlaying.value || pushTimerId !== null) return
    pushTimerId = setTimeout(tick, 0) as unknown as ReturnType<typeof setTimeout>
  }

  /**
   * 背压超时兜底：防止后端异常导致 pending 永久不释放。
   * 仅打印一次限频 warning（LOG_INTERVAL_MS 控制）。
   */
  function onPendingTimeout() {
    const fid = pendingFrameId
    pushLog('frame timeout', `id=${fid} age=${Math.round(getPendingAgeMs())}ms`)
    _clearPending('timeout')
    // timeout 后仍然触发下一帧（防止发送死锁）
    triggerTickIfPlaying()
  }

  // ── Frame capture ──────────────────────────────────────────────────────────

  function captureAndSend() {
    const video = videoEl.value
    if (!video || video.readyState < HTMLMediaElement.HAVE_CURRENT_DATA) return
    if (video.videoWidth === 0 || video.videoHeight === 0) return

    // ── 背压 A：检查 pending，不堆积 ─────────────────────────────────────
    if (pending) {
      pushLog('skip send', 'pending')
      return
    }

    // [临时测速] 开始编码计时
    const encodeStart = performance.now()

    offscreen.width  = video.videoWidth
    offscreen.height = video.videoHeight
    offCtx.drawImage(video, 0, 0)

    const imageBase64 = offscreen.toDataURL('image/jpeg', VIDEO_JPEG_QUALITY)

    // [临时测速] 编码完成，记录耗时
    const encodeMs = performance.now() - encodeStart
    onEncode?.(encodeMs)

    const currentFrameId = frameId++
    // ── 背压 B：发帧后立即置 pending 并启动超时计时 ──────────────────────
    pending        = true
    pendingFrameId = currentFrameId
    pendingSetAt   = performance.now()
    pendingTimerId = setTimeout(onPendingTimeout, PENDING_TIMEOUT_MS) as unknown as ReturnType<typeof setTimeout>

    pushLog('frame sent', `id=${currentFrameId} age=0ms`)

    onFrame({
      frame_id:     currentFrameId,
      timestamp:    Date.now() / 1000,
      image_base64: imageBase64,
      // Phase 3.1: Include model-related fields for dynamic configuration
      model_id: modelId.value,
      prompt_classes: promptClasses.value,
      selected_classes: selectedClasses.value,
    })
  }

  // ── Push loop ──────────────────────────────────────────────────────────────

  function startPush() {
    if (pushTimerId !== null) return
    isPlaying.value = true
    consecutiveHighLatency = 0
    currentFpsLevel = 0

    function tick() {
      pushTimerId = null  // 清掉自身引用（在 captureAndSend 内部已判断过 pending）
      captureAndSend()

      // Adaptive FPS: smart throttling based on latency trends
      const latency = systemLatency.value ?? 0

      if (currentFpsLevel === 0 && latency > HIGH_LATENCY_THRESHOLD) {
        // Transitioning to throttled mode
        currentFpsLevel = 1
        consecutiveHighLatency = 1
      } else if (currentFpsLevel === 1 && latency > HIGH_LATENCY_THRESHOLD) {
        consecutiveHighLatency++
      } else if (currentFpsLevel === 1 && latency < LOW_LATENCY_RECOVERY) {
        consecutiveHighLatency--
        if (consecutiveHighLatency <= -RECOVERY_THRESHOLD) {
          // Recover to normal mode
          currentFpsLevel = 0
          consecutiveHighLatency = 0
        }
      } else {
        consecutiveHighLatency = 0
      }

      const fps = currentFpsLevel === 1 ? VIDEO_THROTTLED_FPS : VIDEO_TARGET_FPS
      pushTimerId = setTimeout(tick, 1000 / fps) as unknown as ReturnType<typeof setTimeout>
    }
    tick()
  }

  function stopPush() {
    if (pushTimerId !== null) {
      clearTimeout(pushTimerId as unknown as ReturnType<typeof setTimeout>)
      pushTimerId = null
    }
    isPlaying.value = false
    clearPending()
    pendingSetAt = 0
  }

  // ── Source management ──────────────────────────────────────────────────────

  /**
   * Reset to standby state - stops push, releases resources, shows drop zone.
   * Unlike release(), this resets frame counter and keeps the video element intact.
   */
  function resetVideo() {
    stopPush()
    clearPending()
    consecutiveHighLatency = 0
    currentFpsLevel = 0

    webcamStream?.getTracks().forEach((t) => t.stop())
    webcamStream = null

    if (currentBlobUrl) {
      URL.revokeObjectURL(currentBlobUrl)
      currentBlobUrl = null
    }

    const video = videoEl.value
    if (video) {
      video.pause()
      video.srcObject = null
      video.src = ''
      video.load()
    }

    frameId = 0
    hasVideo.value = false
  }

  /** Full teardown — releases all media resources and resets to STANDBY. */
  function release() {
    resetVideo()
  }

  /**
   * Load a local video file WITHOUT playing.
   * Transitions to READY state — canvas will display the first frame.
   * The 'ended' event is NOT suppressed (loop = false) so the state machine
   * can detect when playback finishes.
   */
  function loadFile(file: File) {
    resetVideo()
    sourceType.value = 'local_file'

    currentBlobUrl = URL.createObjectURL(file)
    const video = videoEl.value
    if (!video) return

    video.muted = true
    video.loop  = false   // we need 'ended' event for FINISHED state
    video.src   = currentBlobUrl
    video.load()

    // Mark hasVideo once the first frame is decoded and drawable
    video.addEventListener('loadeddata', () => { hasVideo.value = true }, { once: true })
  }

  /**
   * Connect a webcam and start streaming immediately (no READY stage for live feeds).
   */
  async function selectWebcam() {
    resetVideo()
    sourceType.value = 'webcam'

    const stream = await navigator.mediaDevices.getUserMedia(CAMERA_CONSTRAINTS)
    webcamStream = stream

    const video = videoEl.value
    if (!video) return
    video.srcObject = stream
    video.muted = true
    await video.play()
    hasVideo.value = true
    startPush()
  }

  onUnmounted(release)

  // 诊断状态（用于 Detection.vue 调试面板）
  const pendingRef        = computed<boolean>(() => pending)
  const pendingFrameIdRef = computed<number>(() => pendingFrameId)
  const pendingAgeMsRef   = computed<number>(() => getPendingAgeMs())

  // 渲染门控用：最近一次发送的 frame_id（frameId 发出前已自增，故为 frameId - 1）
  const latestSentFrameIdRef = computed<number>(() => frameId > 0 ? frameId - 1 : -1)

  return {
    sourceType, isPlaying, hasVideo,
    loadFile, selectWebcam, startPush, stopPush, release, resetVideo, ackFrame,
    // 诊断导出
    pending:        pendingRef,
    pendingFrameId: pendingFrameIdRef,
    pendingAgeMs:   pendingAgeMsRef,
    // 渲染门控用
    latestSentFrameId: latestSentFrameIdRef,
  }
}
