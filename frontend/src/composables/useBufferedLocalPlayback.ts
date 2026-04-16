/**
 * useBufferedLocalPlayback.ts — 本地视频双视频时钟延迟对齐方案（修复版）
 *
 * 核心策略：
 * - analysis video（隐藏）：提前播放、抽帧送后端、接收检测结果写入缓冲池
 * - visible video（显示）：用户实际看到的播放画面，固定滞后 analysis video 约 2 秒
 * - 渲染时根据 visible video 当前时刻，从缓冲池中取对应检测结果进行绘制
 *
 * 时间绑定修复（v2）：
 * - 检测结果正确绑定到"发送帧时的 captureTime"（即 analysis video 在那一刻的 currentTime）
 * - 而非"结果返回时 analysis video 的 currentTime"（旧版本的错误做法）
 * - 后端返回 inference_result 时，通过 frame_id 查到对应的 captureTime，再写入缓冲池
 * - visible video 渲染时，用自身 currentTime 去"按 captureTime 索引"的缓冲池中查找最近可用结果
 *
 * 约束：
 * - 仅对 sourceType === 'local_file' 生效
 * - webcam 模式行为完全不变
 * - 不缓存原始图像帧，只存检测结果索引
 * - 不修改后端协议
 */
import { ref, type Ref } from 'vue'
import type { Detection } from '@/types/skyline'

// ── 常量 ─────────────────────────────────────────────────────────────────────

/** visible video 滞后 analysis video 的秒数 */
export const VISIBLE_DELAY_SEC = 2.0

// ── 导出类型 ──────────────────────────────────────────────────────────────────

export type BufferStatus = 'idle' | 'buffering' | 'playing' | 'paused' | 'finished'

export interface UseBufferedLocalPlaybackOptions {
  /** 外部传入的 visible video ref */
  visibleVideoEl: Ref<HTMLVideoElement | null>
  /** 外部传入的 analysis video ref */
  analysisVideoEl: Ref<HTMLVideoElement | null>
  /** 回调：analysis video 需要发送帧时触发 */
  onAnalysisFrame: (data: {
    frame_id: number
    timestamp: number
    image_base64: string
  }) => void
}

export interface UseBufferedLocalPlaybackReturn {
  /** visible video 是否正在播放 */
  isPlaying: Ref<boolean>
  /** 是否已加载视频 */
  hasVideo: Ref<boolean>
  /** 缓冲状态 */
  bufferStatus: Ref<BufferStatus>
  /** 当前可见帧对应的检测结果 */
  visibleDetections: Ref<Detection[]>
  /** 是否使用缓冲播放（local_file 模式） */
  useBufferedMode: Ref<boolean>

  /** 加载本地视频文件 */
  loadFile: (file: File) => void
  /** 开始分析（播放 visible video，启动 analysis video 推流） */
  startAnalysis: () => void
  /** 停止分析 */
  stopAnalysis: () => void
  /** 暂停 */
  pause: () => void
  /** 恢复 */
  resume: () => void
  /** 重置到待机状态 */
  reset: () => void
  /** 接收后端检测结果（修复版：按发送时的 captureTime 绑定，而非结果返回时） */
  pushResult: (frameId: number, detections: Detection[]) => void
}

// ── 实现 ─────────────────────────────────────────────────────────────────────

export function useBufferedLocalPlayback(
  options: UseBufferedLocalPlaybackOptions,
): UseBufferedLocalPlaybackReturn {
  const { visibleVideoEl, analysisVideoEl, onAnalysisFrame } = options

  // 状态
  const isPlaying    = ref(false)
  const hasVideo     = ref(false)
  const bufferStatus = ref<BufferStatus>('idle')
  const useBufferedMode = ref(false)

  /**
   * 结果缓冲池：key = captureTime（发送帧时 analysis video 的 currentTime，秒，保留3位小数）
   *             value = 检测结果数组
   *
   * 正确绑定点说明：
   * - captureTime 是"analysis video 截取这一帧时"的 currentTime
   * - 结果返回时，visible video 大约在 captureTime - VISIBLE_DELAY_SEC 附近
   * - visible video 渲染时，用自身 currentTime 去这个池子里找 <= captureTime 的最近结果
   */
  const resultBuffer = ref<Map<number, Detection[]>>(new Map())

  /**
   * frame_id → captureTime 元数据表（修复版核心）
   * 在 captureAndSendAnalysisFrame() 发送帧时记录，pushResult() 按 frame_id 查绑定时间。
   */
  const frameMetaMap = ref<Map<number, number>>(new Map())

  // 当前 visible video 对应的检测结果
  const visibleDetections = ref<Detection[]>([])

  // 内部状态
  let currentBlobUrl: string | null = null
  let analysisPushTimerId: ReturnType<typeof setTimeout> | null = null
  let frameId = 0

  // Dedicated offscreen canvas for frame extraction
  const offscreen = document.createElement('canvas')
  const offCtx    = offscreen.getContext('2d')!

  // ── 限频日志 ───────────────────────────────────────────────────────────────

  const lastLogTime: Record<string, number> = {}
  const LOG_INTERVAL_MS = 2000

  function bufLog(tag: string, msg: string) {
    const now = performance.now()
    if (!lastLogTime[tag] || now - lastLogTime[tag] >= LOG_INTERVAL_MS) {
      console.log(`[BUF] [${tag}] ${msg}`)
      lastLogTime[tag] = now
    }
  }

  // ── 工具函数 ───────────────────────────────────────────────────────────────

  /**
   * 根据 visible video 的当前时间查找对应的检测结果。
   * 策略：找到 resultBuffer 中 <= visibleTime 的最大 captureTime（即最近一帧已送出的结果）。
   * 若 buffer 中没有任何 <= visibleTime 的条目，说明结果还未返回，回退到最近一条。
   */
  function lookupDetectionsForTime(visibleTime: number): Detection[] {
    const buf = resultBuffer.value
    if (buf.size === 0) return []

    let bestTime = -1

    for (const t of buf.keys()) {
      if (t <= visibleTime && t > bestTime) {
        bestTime = t
      }
    }

    // 严格模式：没找到任何 <= visibleTime 的结果时，尝试回退到最近一帧
    if (bestTime < 0) {
      let closestTime = -1
      for (const t of buf.keys()) {
        if (t > closestTime) {
          closestTime = t
        }
      }
      if (closestTime >= 0) {
        bestTime = closestTime
      }
    }

    const dets = bestTime >= 0 ? (buf.get(bestTime) ?? []) : []

    bufLog('match', `visibleTime=${visibleTime.toFixed(3)} matchedCaptureTime=${bestTime >= 0 ? bestTime.toFixed(3) : 'none'} dets=${dets.length}`)

    return dets
  }

  /** 清理过期的缓冲数据 */
  function pruneBuffer() {
    const av = analysisVideoEl.value
    if (!av) return

    const currentTime = av.currentTime
    // visible video 最大不会超过 currentTime - VISIBLE_DELAY_SEC
    // 保留 analysis video 当前时间前 10 秒的缓冲（给网络抖动留余地）
    const cutoff = currentTime - 10

    for (const t of resultBuffer.value.keys()) {
      if (t < cutoff) resultBuffer.value.delete(t)
    }

    // frameMetaMap 只保留最近 300 个
    if (frameMetaMap.value.size > 300) {
      const entries = Array.from(frameMetaMap.value.entries())
        .sort((a, b) => a[0] - b[0]) // 按 frameId 排序（从小到大）
      const keep = entries.slice(-200)
      frameMetaMap.value.clear()
      for (const [k, v] of keep) frameMetaMap.value.set(k, v)
    }
  }

  /** 更新 visibleDetections */
  function updateVisibleDetections() {
    const vv = visibleVideoEl.value
    if (!vv) return
    visibleDetections.value = lookupDetectionsForTime(vv.currentTime)
  }

  // ── analysis video 推流逻辑 ─────────────────────────────────────────────────

  function captureAndSendAnalysisFrame() {
    const video = analysisVideoEl.value
    if (!video || video.readyState < HTMLMediaElement.HAVE_CURRENT_DATA) return
    if (video.videoWidth === 0 || video.videoHeight === 0) return
    if (video.paused || video.ended) return

    offscreen.width  = video.videoWidth
    offscreen.height = video.videoHeight
    offCtx.drawImage(video, 0, 0)

    const imageBase64 = offscreen.toDataURL('image/jpeg', 0.85)
    const currentFrameId = frameId++
    const timestamp = Date.now() / 1000

    // 关键修复：记录这一帧的 captureTime（发送时 analysis video 的 currentTime）
    // 这是检测结果真正对应的时间轴索引，而非结果返回时的时间
    const captureTime = Math.round(video.currentTime * 1000) / 1000
    frameMetaMap.value.set(currentFrameId, captureTime)

    bufLog('sent', `id=${currentFrameId} captureTime=${captureTime.toFixed(3)}`)

    onAnalysisFrame({
      frame_id: currentFrameId,
      timestamp,
      image_base64: imageBase64,
    })

    // 定期清理
    if (frameMetaMap.value.size > 250) {
      pruneBuffer()
    }
  }

  function startAnalysisPush() {
    if (analysisPushTimerId !== null) return
    frameId = 0

    function tick() {
      analysisPushTimerId = null
      captureAndSendAnalysisFrame()
      // 约 5 FPS 发帧（200ms 间隔）
      analysisPushTimerId = setTimeout(tick, 200) as unknown as ReturnType<typeof setTimeout>
    }

    tick()
  }

  function stopAnalysisPush() {
    if (analysisPushTimerId !== null) {
      clearTimeout(analysisPushTimerId as unknown as ReturnType<typeof setTimeout>)
      analysisPushTimerId = null
    }
  }

  // ── visible video 同步 ──────────────────────────────────────────────────────

  /** 让 visible video 同步到 analysis video 减去延迟后的位置 */
  function syncVisibleToAnalysis() {
    const av = analysisVideoEl.value
    const vv = visibleVideoEl.value
    if (!av || !vv || !hasVideo.value) return
    if (av.paused || av.ended) return

    const targetTime = Math.max(0, av.currentTime - VISIBLE_DELAY_SEC)

    // 如果 visible video 落后太多（超过 1 秒），强制同步
    if (Math.abs(vv.currentTime - targetTime) > 1.0) {
      vv.currentTime = targetTime
    }
  }

  // ── visible video 事件监听 ──────────────────────────────────────────────────

  function setupVisibleVideoEvents() {
    const vv = visibleVideoEl.value
    if (!vv) return

    vv.onended = () => {
      stopAnalysisPush()
      analysisVideoEl.value?.pause()
      isPlaying.value = false
      bufferStatus.value = 'finished'
      updateVisibleDetections()
    }

    vv.ontimeupdate = () => {
      updateVisibleDetections()
      if (isPlaying.value) {
        syncVisibleToAnalysis()
      }
    }
  }

  // ── 公共 API ───────────────────────────────────────────────────────────────

  function loadFile(file: File) {
    reset()

    currentBlobUrl = URL.createObjectURL(file)
    useBufferedMode.value = true

    const av = analysisVideoEl.value
    const vv = visibleVideoEl.value
    if (!av || !vv) return

    av.muted = true
    av.loop = false
    av.src = currentBlobUrl
    av.load()

    vv.muted = true
    vv.loop = false
    vv.src = currentBlobUrl
    vv.load()

    setupVisibleVideoEvents()

    av.addEventListener('loadeddata', () => {
      hasVideo.value = true
    }, { once: true })
  }

  function startAnalysis() {
    const av = analysisVideoEl.value
    const vv = visibleVideoEl.value
    if (!av || !vv || !hasVideo.value) return

    bufferStatus.value = 'buffering'
    isPlaying.value = true
    frameId = 0
    resultBuffer.value.clear()
    frameMetaMap.value.clear()
    visibleDetections.value = []

    av.currentTime = 0
    av.play()

    const onAvPlay = () => {
      av.removeEventListener('play', onAvPlay)
      vv.currentTime = Math.max(0, av.currentTime - VISIBLE_DELAY_SEC)
      vv.play()
      startAnalysisPush()
      bufferStatus.value = 'playing'
    }
    av.addEventListener('play', onAvPlay)

    if (!av.paused) {
      av.removeEventListener('play', onAvPlay)
      vv.currentTime = Math.max(0, av.currentTime - VISIBLE_DELAY_SEC)
      vv.play()
      startAnalysisPush()
      bufferStatus.value = 'playing'
    }
  }

  function stopAnalysis() {
    stopAnalysisPush()

    analysisVideoEl.value?.pause()
    visibleVideoEl.value?.pause()

    isPlaying.value = false
    bufferStatus.value = 'finished'

    updateVisibleDetections()
  }

  function pause() {
    analysisVideoEl.value?.pause()
    visibleVideoEl.value?.pause()
    stopAnalysisPush()
    isPlaying.value = false
    bufferStatus.value = 'paused'
  }

  function resume() {
    const av = analysisVideoEl.value
    const vv = visibleVideoEl.value
    if (!av || !vv) return

    bufferStatus.value = 'buffering'
    isPlaying.value = true

    av.play()
    vv.play()
    startAnalysisPush()
    bufferStatus.value = 'playing'
  }

  function reset() {
    stopAnalysisPush()

    if (analysisVideoEl.value) {
      analysisVideoEl.value.pause()
      analysisVideoEl.value.src = ''
    }
    if (visibleVideoEl.value) {
      visibleVideoEl.value.pause()
      visibleVideoEl.value.src = ''
    }

    if (currentBlobUrl) {
      URL.revokeObjectURL(currentBlobUrl)
      currentBlobUrl = null
    }

    isPlaying.value = false
    hasVideo.value = false
    bufferStatus.value = 'idle'
    useBufferedMode.value = false
    resultBuffer.value.clear()
    frameMetaMap.value.clear()
    visibleDetections.value = []
    frameId = 0
  }

  /**
   * 接收后端返回的检测结果（修复版）。
   *
   * 关键修复：不再用"结果返回时 analysisVideo.currentTime"作为 key。
   * 而是：
   *   1. 通过 frameId 在 frameMetaMap 中查找这一帧的 captureTime
   *   2. 用 captureTime 作为 key 写入 resultBuffer
   *
   * 这样 resultBuffer 的时间轴与 visible video 的时间轴完全对齐（都相对于视频开头），
   * visible video 渲染时用自身 currentTime 查找缓冲池即可得到精确匹配。
   */
  function pushResult(frameId: number, detections: Detection[]) {
    // 从发送时记录的元数据中找到 captureTime
    const captureTime = frameMetaMap.value.get(frameId)

    if (captureTime === undefined) {
      bufLog('warn', `pushResult: frameId=${frameId} not found in frameMetaMap, skipping`)
      return
    }

    // 用 captureTime（发送帧时的分析时间）作为索引，而非返回时的当前时间
    resultBuffer.value.set(captureTime, detections)

    bufLog('result', `id=${frameId} boundCaptureTime=${captureTime.toFixed(3)} dets=${detections.length}`)

    // 立即更新 visibleDetections（让框能及时显示）
    updateVisibleDetections()

    // 定期清理
    if (resultBuffer.value.size > 300) {
      pruneBuffer()
    }
  }

  return {
    isPlaying,
    hasVideo,
    bufferStatus,
    visibleDetections,
    useBufferedMode,
    loadFile,
    startAnalysis,
    stopAnalysis,
    pause,
    resume,
    reset,
    pushResult,
  }
}
