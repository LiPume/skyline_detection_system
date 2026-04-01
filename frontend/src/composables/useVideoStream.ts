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
import { ref, onUnmounted } from 'vue'
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

  // Dedicated offscreen canvas for frame extraction
  const offscreen = document.createElement('canvas')
  const offCtx    = offscreen.getContext('2d')!

  // ── Frame capture ──────────────────────────────────────────────────────────

  function captureAndSend() {
    const video = videoEl.value
    if (!video || video.readyState < HTMLMediaElement.HAVE_CURRENT_DATA) return
    if (video.videoWidth === 0 || video.videoHeight === 0) return

    // [临时测速] 开始编码计时
    const encodeStart = performance.now()

    offscreen.width  = video.videoWidth
    offscreen.height = video.videoHeight
    offCtx.drawImage(video, 0, 0)

    const imageBase64 = offscreen.toDataURL('image/jpeg', VIDEO_JPEG_QUALITY)

    // [临时测速] 编码完成，记录耗时
    const encodeMs = performance.now() - encodeStart
    onEncode?.(encodeMs)

    onFrame({
      frame_id:     frameId++,
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

    function tick() {
      captureAndSend()
      const fps = systemLatency.value > 200 ? VIDEO_THROTTLED_FPS : VIDEO_TARGET_FPS
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
  }

  // ── Source management ──────────────────────────────────────────────────────

  /** Full teardown — releases all media resources and resets to STANDBY. */
  function release() {
    stopPush()

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
      video.load()   // resets internal state to EMPTY
    }

    hasVideo.value = false
  }

  /**
   * Load a local video file WITHOUT playing.
   * Transitions to READY state — canvas will display the first frame.
   * The 'ended' event is NOT suppressed (loop = false) so the state machine
   * can detect when playback finishes.
   */
  function loadFile(file: File) {
    release()
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
    release()
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

  return { sourceType, isPlaying, hasVideo, loadFile, selectWebcam, startPush, stopPush, release }
}
