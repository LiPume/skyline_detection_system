<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import type { Detection, ServerMessage, InferenceResult } from '@/types/skyline'
import { useWebSocket }      from '@/composables/useWebSocket'
import { useVideoStream }    from '@/composables/useVideoStream'
import { useCanvasRenderer } from '@/composables/useCanvasRenderer'
import { useModelConfig } from '@/composables/useModelConfig'
import { wsStatus as globalWsStatus, isGpuActive } from '@/store/systemStatus'
import { LATENCY_THROTTLE_THRESHOLD_MS, LATENCY_BAR_MAX_MS } from '@/config'
import { saveDetection }     from '@/api/history'

// ── DOM refs ───────────────────────────────────────────────────────────────────
const canvasEl   = ref<HTMLCanvasElement | null>(null)
const videoEl    = ref<HTMLVideoElement | null>(null)
// ALWAYS in DOM — never inside v-if, so the ref is never null
const fileInputEl = ref<HTMLInputElement | null>(null)

// ── Analysis state machine ─────────────────────────────────────────────────────
type AnalysisState = 'standby' | 'ready' | 'analyzing' | 'paused' | 'finished'
const analysisState = ref<AnalysisState>('standby')

const isAnalyzing = computed(() => analysisState.value === 'analyzing')
const isPaused    = computed(() => analysisState.value === 'paused')
const canExecute  = computed(() => analysisState.value === 'ready' || analysisState.value === 'finished')
const isLocked    = computed(() => analysisState.value === 'analyzing' || analysisState.value === 'paused')

// ── Pause dialog state ─────────────────────────────────────────────────────────
const showPauseDialog = ref(false)

// ── Toast notification stack ──────────────────────────────────────────────────
interface Toast { id: number; type: 'error' | 'warn' | 'success'; text: string }
const toasts = ref<Toast[]>([])
let toastSeq = 0
function showToast(text: string, type: Toast['type'] = 'error', ms = 4000) {
  const id = toastSeq++
  toasts.value.push({ id, type, text })
  setTimeout(() => { toasts.value = toasts.value.filter(t => t.id !== id) }, ms)
}

// ── Telemetry ──────────────────────────────────────────────────────────────────
const backendProcessMs    = ref<number | null>(null)   // 后端全流程耗时（不含网络）
const inferenceFps        = ref(0)   // 后端处理 FPS：1000 / backendProcessMs（兼容旧名）

// ── Phase 5: 比赛硬指标（session_ms 口径——后端当前未实现，显示 --）──────────
const sessionMs           = ref<number | null>(null)   // 纯模型 forward 耗时（后端未提供）
const fpsInfer             = computed(() => {
  if (sessionMs.value === null || sessionMs.value <= 0) return null
  return 1000 / sessionMs.value
})

// ── Phase 5: 工程指标 ──────────────────────────────────────────────────────────
const preprocessMs         = ref<number | null>(null)   // 预处理耗时（后端未提供）
const postprocessMs        = ref<number | null>(null)   // 后处理耗时（后端未提供）
const algoProcessMs        = computed<number | null>(() => {
  // 仅当三个子阶段全部可用时才能计算
  if (preprocessMs.value === null || sessionMs.value === null || postprocessMs.value === null) return null
  return preprocessMs.value + sessionMs.value + postprocessMs.value
})
const fpsAlgo              = computed<number | null>(() => {
  if (algoProcessMs.value === null || algoProcessMs.value <= 0) return null
  return 1000 / algoProcessMs.value
})
const fpsBackend           = computed<number | null>(() => {
  if (backendProcessMs.value === null || backendProcessMs.value <= 0) return null
  return 1000 / backendProcessMs.value
})

// ── Phase 5: 系统实时指标 ──────────────────────────────────────────────────────
const frontendSendIntervalMs = ref<number | null>(null) // 前端发送节奏（ms）
const fpsSend               = computed<number | null>(() => {
  if (frontendSendIntervalMs.value === null || frontendSendIntervalMs.value <= 0) return null
  return 1000 / frontendSendIntervalMs.value
})
const resultIntervalMs       = ref<number | null>(null) // 结果返回节奏（ms）
const fpsResult               = computed<number | null>(() => {
  if (resultIntervalMs.value === null || resultIntervalMs.value <= 0) return null
  return 1000 / resultIntervalMs.value
})
const endToEndLatencyMs       = ref<number | null>(null) // 端到端延迟（ms）

// ── Phase 5: 调试指标 ─────────────────────────────────────────────────────────
const frontendEncodeMs     = ref<number | null>(null)    // 前端编码耗时
const frontendRenderMs     = ref<number | null>(null)    // 前端消息处理
const pipelineExtraMs      = computed<number | null>(() => {
  if (endToEndLatencyMs.value === null || backendProcessMs.value === null) return null
  return Math.max(0, endToEndLatencyMs.value - backendProcessMs.value)
})
let lastSendAt    = 0  // 上次发送时间戳
let lastResultAt  = 0  // 上次收到结果时间戳

// ── 格式化辅助 ───────────────────────────────────────────────────────────────
function fmt(v: number | null, decimals = 1): string {
  if (v === null || !isFinite(v)) return '--'
  return v.toFixed(decimals)
}

// ── Detection state & drag ─────────────────────────────────────────────────────
const currentDetections = ref<Detection[]>([])
const isDragging        = ref(false)

// ── Detection statistics ───────────────────────────────────────────────────────
const classCounts     = ref<Record<string, number>>({})
const totalDetections = computed(() =>
  Object.values(classCounts.value).reduce((a, b) => a + b, 0),
)

// Max detections in a single frame (peak)
const maxFrameDetections = ref(0)

function updateMaxDetections(count: number) {
  if (count > maxFrameDetections.value) {
    maxFrameDetections.value = count
  }
}

function resetStats() {
  classCounts.value = {}
  maxFrameDetections.value = 0
  analysisDuration.value = 0
  saveState.value = 'idle'
}

// ── Analysis duration ───────────────────────────────────────────────────────────
const analysisStartTime = ref<number | null>(null)
const analysisDuration  = ref<number>(0)   // seconds

// ── Video name (extracted from loaded file) ────────────────────────────────────
const videoName = ref<string>('unknown')

// ── Save state ────────────────────────────────────────────────────────────────
type SaveState = 'idle' | 'saving' | 'saved' | 'error'
const saveState = ref<SaveState>('idle')

async function autoSave() {
  if (totalDetections.value === 0) return  // Skip empty sessions
  saveState.value = 'saving'
  try {
    await saveDetection({
      video_name: videoName.value,
      duration: analysisDuration.value,
      detection_model: buildModelConfig(),
      class_counts: { ...classCounts.value },
      total_detections: totalDetections.value,
    })
    saveState.value = 'saved'
    showToast('分析记录已保存到历史记录库', 'success', 3000)
  } catch (e: unknown) {
    saveState.value = 'error'
    showToast('保存失败：' + (e instanceof Error ? e.message : '未知错误'), 'error', 5000)
  }
}

// ── Model Config (Phase 3.1) ─────────────────────────────────────────────────
const {
  modelList,
  selectedModelId,
  currentCapabilities,
  isLoading: modelLoading,
  fetchError: modelError,
  promptInput,
  targetClasses,
  selectedClasses,
  isOpenVocabModel,
  isClosedSetModel,
  selectModel,
  toggleClass,
  selectAllClasses,
  clearAllClasses,
  appendChip,
  buildModelConfig,
  initialize: initModelConfig,
} = useModelConfig()

// ── AI console state ───────────────────────────────────────────────────────────

const QUICK_CHIPS_LOCAL = [
  { label: '汽车',   en: 'car' },
  { label: '行人',   en: 'person' },
  { label: '无人机', en: 'drone' },
  { label: '卡车',   en: 'truck' },
  { label: '摩托车', en: 'motorcycle' },
  { label: '船只',   en: 'boat' },
  { label: '背包',   en: 'backpack' },
]

// ── WebSocket ──────────────────────────────────────────────────────────────────
const { status: wsStatus, connect, disconnect, send } = useWebSocket({
  onMessage(msg: ServerMessage) {
    if (msg.message_type === 'inference_result') {
      // ── Phase 5: 收到推理结果，计算结果返回节奏 ─────────────────────────
      const resultNow = performance.now()
      if (lastResultAt > 0) {
        resultIntervalMs.value = resultNow - lastResultAt
      }
      lastResultAt = resultNow

      const r = msg as InferenceResult

      // ── 工程指标 ────────────────────────────────────────────────────────
      backendProcessMs.value  = r.inference_time_ms
      inferenceFps.value      = r.inference_time_ms > 0
        ? Math.round(1000 / r.inference_time_ms * 10) / 10 : 0

      // ── 比赛硬指标（Phase 5: 后端已实现，直接读取）──────────────────────
      sessionMs.value     = r.session_ms ?? null
      preprocessMs.value  = r.preprocess_ms ?? null
      postprocessMs.value = r.postprocess_ms ?? null

      // ── 系统实时指标 ────────────────────────────────────────────────────
      endToEndLatencyMs.value = (Date.now() / 1000 - r.timestamp) * 1000

      // ── 检测结果写入 ────────────────────────────────────────────────────
      currentDetections.value = r.detections
      updateMaxDetections(r.detections.length)
      for (const d of r.detections) {
        classCounts.value[d.class_name] = (classCounts.value[d.class_name] ?? 0) + 1
      }

      // ── 调试指标：前端消息处理耗时 ─────────────────────────────────────
      frontendRenderMs.value = performance.now() - resultNow

    } else if (msg.message_type === 'error') {
      showToast(msg.detail, 'error')
    }
  },
  onSendFailure() {
    showToast('推流中断：WebSocket 未连接，帧已丢弃', 'warn', 3000)
  },
})

// Sync to global store → MainLayout header indicators
watch(wsStatus,    v => { globalWsStatus.value = v }, { immediate: true })
watch(isAnalyzing, v => { isGpuActive.value    = v }, { immediate: true })

// ── Video stream ───────────────────────────────────────────────────────────────
const selectedClassesArray = computed<string[]>(() => Array.from(selectedClasses.value))

const { sourceType, isPlaying, hasVideo, loadFile, selectWebcam, startPush, stopPush } =
  useVideoStream({
    videoEl,
    systemLatency: endToEndLatencyMs,
    modelId: selectedModelId,
    promptClasses: targetClasses,
    selectedClasses: selectedClassesArray,
    // ── Phase 5: 发送节奏测速 ───────────────────────────────────────────────
    onFrame({ frame_id, timestamp, image_base64, model_id, prompt_classes, selected_classes }) {
      const sendNow = performance.now()
      if (lastSendAt > 0) {
        frontendSendIntervalMs.value = sendNow - lastSendAt
      }
      lastSendAt = sendNow

      send(JSON.stringify({
        message_type:   'video_frame',
        frame_id,
        timestamp,
        image_base64,
        model_id,
        prompt_classes,
        selected_classes,
        // Legacy fields for backward compatibility
        selected_model: model_id,
        target_classes: prompt_classes,
      }))
    },
    // ── Phase 5: 编码耗时测速 ──────────────────────────────────────────────
    onEncode(encodeMs) {
      frontendEncodeMs.value = encodeMs
    },
  })

// ── Canvas renderer ────────────────────────────────────────────────────────────
const { startRendering } = useCanvasRenderer({
  canvasEl,
  videoEl,
  detections: currentDetections,
  isPlaying,
  hasVideo,
})

// ── State machine actions ──────────────────────────────────────────────────────

function startAnalysis() {
  if (!hasVideo.value) return
  if (wsStatus.value !== 'connected') {
    showToast('WebSocket 未连接，请等待重连后重试', 'warn')
    return
  }
  
  // Phase 3.1: Model-specific validation
  if (isOpenVocabModel.value) {
    // Open vocab model requires at least one target class
    if (targetClasses.value.length === 0) {
      showToast('请先填写至少一个检测目标', 'warn')
      return
    }
  } else if (isClosedSetModel.value) {
    // Closed-set model requires at least one selected class
    if (selectedClasses.value.size === 0) {
      showToast('请先选择至少一个要显示的类别', 'warn')
      return
    }
  }
  
  const video = videoEl.value!
  if (analysisState.value === 'finished') {
    video.currentTime = 0
    currentDetections.value = []
    resetStats()
  }
  // Reset stats before new analysis
  resetStats()
  analysisStartTime.value = Date.now()
  video.play()
  startPush()
  analysisState.value = 'analyzing'
}

function stopAnalysis() {
  stopPush()
  videoEl.value?.pause()
  // Record duration
  if (analysisStartTime.value !== null) {
    analysisDuration.value = (Date.now() - analysisStartTime.value) / 1000
    analysisStartTime.value = null
  }
  analysisState.value = 'finished'
  autoSave()
}

// ── Pause / Resume ─────────────────────────────────────────────────────────────

function pauseAnalysis() {
  if (analysisState.value !== 'analyzing') return
  stopPush()
  videoEl.value?.pause()
  analysisState.value = 'paused'
  showPauseDialog.value = true
}

function resumeAnalysis() {
  showPauseDialog.value = false
  if (analysisStartTime.value === null) {
    analysisStartTime.value = Date.now()
  }
  videoEl.value?.play()
  startPush()
  analysisState.value = 'analyzing'
}

function saveAndFinish() {
  showPauseDialog.value = false
  stopPush()
  videoEl.value?.pause()
  if (analysisStartTime.value !== null) {
    analysisDuration.value = (Date.now() - analysisStartTime.value) / 1000
    analysisStartTime.value = null
  }
  analysisState.value = 'finished'
  autoSave()
}

// ── Keyboard handler ───────────────────────────────────────────────────────────

function handleKeydown(e: KeyboardEvent) {
  if (e.code === 'Space') {
    if (analysisState.value === 'analyzing') {
      e.preventDefault()
      pauseAnalysis()
    } else if (analysisState.value === 'paused') {
      e.preventDefault()
      if (showPauseDialog.value) {
        resumeAnalysis()
      }
    }
  }
}

// ── File upload handlers ───────────────────────────────────────────────────────

function triggerFilePicker() {
  // fileInputEl is always in DOM (not inside v-if) so this is always safe
  fileInputEl.value?.click()
}

function onFileChange(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (!file) return
  ;(e.target as HTMLInputElement).value = ''
  videoName.value = file.name
  loadFile(file)
  currentDetections.value = []
  analysisState.value = 'ready'
}

function onDrop(e: DragEvent) {
  isDragging.value = false
  const file = e.dataTransfer?.files[0]
  if (!file) return
  if (!file.type.startsWith('video/')) {
    showToast('仅支持视频文件（MP4 / MOV / AVI）', 'warn')
    return
  }
  videoName.value = file.name
  loadFile(file)
  currentDetections.value = []
  analysisState.value = 'ready'
}

async function onSelectWebcam() {
  try {
    videoName.value = 'Webcam-' + new Date().toISOString().slice(0, 10)
    await selectWebcam()
    currentDetections.value = []
    analysisState.value = 'analyzing'
  } catch {
    showToast('无法访问摄像头，请检查浏览器权限', 'error')
  }
}

// ── Lifecycle ──────────────────────────────────────────────────────────────────

onMounted(async () => {
  // Phase 3.1: Initialize model configuration
  await initModelConfig()
  
  connect()
  startRendering()

  // Set canvas size immediately (don't wait for ResizeObserver's first callback)
  const canvas    = canvasEl.value
  const container = canvas?.parentElement
  if (canvas && container) {
    canvas.width  = container.clientWidth
    canvas.height = container.clientHeight
  }

  // Keep canvas sized to its container on viewport resize
  const observer = new ResizeObserver(() => {
    const c  = canvasEl.value
    const ct = c?.parentElement
    if (!c || !ct) return
    c.width  = ct.clientWidth
    c.height = ct.clientHeight
  })
  if (canvasEl.value?.parentElement) observer.observe(canvasEl.value.parentElement)

  // video.ended → FINISHED (local file mode)
  videoEl.value?.addEventListener('ended', () => {
    stopPush()
    if (analysisStartTime.value !== null) {
      analysisDuration.value = (Date.now() - analysisStartTime.value) / 1000
      analysisStartTime.value = null
    }
    analysisState.value = 'finished'
    autoSave()
  })

  // Keyboard handler for spacebar pause
  window.addEventListener('keydown', handleKeydown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeydown)
})

// ── Derived display helpers ────────────────────────────────────────────────────

const latencyOk = computed(() => endToEndLatencyMs.value !== null && endToEndLatencyMs.value <= LATENCY_THROTTLE_THRESHOLD_MS)

const stateInfo = computed(() => ({
  standby:   { label: 'STANDBY',   color: 'text-slate-500',   bg: 'bg-slate-500/10  border-slate-600/40' },
  ready:     { label: 'ARMED',     color: 'text-emerald-400', bg: 'bg-emerald-500/10 border-emerald-500/40' },
  analyzing: { label: 'ANALYZING', color: 'text-blue-400',    bg: 'bg-blue-500/10   border-blue-500/40' },
  paused:    { label: 'PAUSED',   color: 'text-amber-400',   bg: 'bg-amber-500/10  border-amber-500/40' },
  finished:  { label: 'COMPLETE', color: 'text-cyan-400',    bg: 'bg-cyan-500/10  border-cyan-500/40' },
}[analysisState.value]))
</script>

<template>
  <div class="relative flex h-full bg-slate-950 overflow-hidden">

    <!-- ── Always-in-DOM file input (NEVER inside v-if) ──────────────────────── -->
    <!-- Keeping this outside all conditional blocks ensures the ref stays valid  -->
    <!-- even after a video is loaded and the drop-zone overlay is hidden.        -->
    <input
      ref="fileInputEl"
      type="file"
      accept="video/*"
      class="hidden"
      @change="onFileChange"
    />

    <!-- ── Toast stack ───────────────────────────────────────────────────────── -->
    <div class="absolute top-4 left-1/2 -translate-x-1/2 z-50 flex flex-col gap-2 pointer-events-none"
         style="min-width:320px; max-width:520px;">
      <TransitionGroup name="toast">
          <div
          v-for="t in toasts"
          :key="t.id"
          class="flex items-center gap-2.5 px-4 py-2.5 rounded-xl border text-sm
                 backdrop-blur shadow-xl pointer-events-auto"
          :class="t.type === 'error'
            ? 'bg-red-950/90 border-red-700/70 text-red-300'
            : t.type === 'warn'
              ? 'bg-amber-950/90 border-amber-700/70 text-amber-300'
              : 'bg-emerald-950/90 border-emerald-700/70 text-emerald-300'"
        >
          <span class="text-base flex-shrink-0">{{ t.type === 'error' ? '✕' : t.type === 'warn' ? '⚠' : '✓' }}</span>
          {{ t.text }}
        </div>
      </TransitionGroup>
    </div>

    <!-- ── LEFT: Visual stage ────────────────────────────────────────────────── -->
    <div class="flex-1 relative flex flex-col overflow-hidden min-w-0">

      <!-- Hidden video element — source for frame capture only -->
      <video
        ref="videoEl"
        class="absolute w-px h-px opacity-0 pointer-events-none"
        muted playsinline preload="auto"
      ></video>

      <!-- Canvas viewport -->
      <div class="flex-1 relative bg-slate-950">
        <canvas ref="canvasEl" class="w-full h-full block"></canvas>

        <!-- Drop zone (standby only, not locked) -->
        <!-- .self on dragleave prevents child-element hover from resetting isDragging -->
        <Transition name="fade">
          <div
            v-if="!hasVideo && !isLocked"
            class="absolute inset-0 flex items-center justify-center cursor-pointer transition-colors duration-200"
            :class="isDragging ? 'bg-blue-950/50' : ''"
            @dragover.prevent="isDragging = true"
            @dragleave.self="isDragging = false"
            @drop.prevent="onDrop"
            @click="triggerFilePicker"
          >
            <div class="flex flex-col items-center gap-4 text-center select-none pointer-events-none">
              <div
                class="w-28 h-28 rounded-2xl border-2 border-dashed flex items-center justify-center
                       transition-all duration-200"
                :class="isDragging
                  ? 'border-blue-400 bg-blue-500/15 text-blue-400 scale-105'
                  : 'border-slate-600 bg-slate-900/60 text-slate-500'"
              >
                <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                  <path stroke-linecap="round" stroke-linejoin="round"
                        d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5"/>
                </svg>
              </div>
              <div>
                <p class="text-slate-200 text-base font-medium">拖拽视频文件至此处</p>
                <p class="text-slate-500 text-sm mt-1">或点击选择文件 · MP4 / MOV / AVI</p>
              </div>
            </div>
          </div>
        </Transition>

        <!-- WS offline warning (during analysis attempt) -->
        <Transition name="fade">
          <div
            v-if="wsStatus !== 'connected' && isAnalyzing"
            class="absolute top-4 left-1/2 -translate-x-1/2 pointer-events-none"
          >
            <div class="flex items-center gap-2 px-3 py-1.5 rounded-lg
                        bg-amber-950/85 border border-amber-700/60 backdrop-blur">
              <span class="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse"></span>
              <span class="text-amber-300 text-xs font-medium">WebSocket 重连中，推流已暂停</span>
            </div>
          </div>
        </Transition>

        <!-- PAUSED overlay -->
        <Transition name="fade">
          <div v-if="analysisState === 'paused'"
               class="absolute bottom-5 left-5 pointer-events-none">
            <div class="flex items-center gap-3 px-4 py-2.5 rounded-xl
                        bg-slate-950/85 border border-amber-500/30 backdrop-blur">
              <div class="w-2 h-2 rounded-full bg-amber-400
                          shadow-[0_0_6px_rgba(251,191,36,0.8)]"></div>
              <span class="text-amber-400 text-sm font-medium tracking-wide">ANALYSIS PAUSED</span>
              <span class="text-slate-500 text-xs">· 按空格继续</span>
            </div>
          </div>
        </Transition>

        <!-- READY overlay -->
        <Transition name="fade">
          <div v-if="analysisState === 'ready'"
               class="absolute bottom-5 left-5 pointer-events-none">
            <div class="flex items-center gap-3 px-4 py-2.5 rounded-xl
                        bg-slate-950/85 border border-emerald-500/30 backdrop-blur">
              <div class="w-2 h-2 rounded-full bg-emerald-400
                          shadow-[0_0_6px_rgba(52,211,153,0.8)] animate-pulse"></div>
              <span class="text-emerald-400 text-sm font-medium tracking-wide">SYSTEM ARMED</span>
              <span class="text-slate-500 text-xs">· 配置目标后点击启动</span>
            </div>
          </div>
        </Transition>

        <!-- FINISHED overlay -->
        <Transition name="fade">
          <div v-if="analysisState === 'finished'"
               class="absolute bottom-5 left-5 pointer-events-none">
            <div class="flex items-center gap-3 px-4 py-2.5 rounded-xl
                        bg-slate-950/85 border border-cyan-500/30 backdrop-blur">
              <span class="text-cyan-400 text-lg leading-none">{{ saveState === 'saved' ? '✓' : '✓' }}</span>
              <div>
                <div class="text-cyan-400 text-sm font-medium tracking-wide">ANALYSIS COMPLETE</div>
                <div class="text-slate-500 text-xs mt-0.5">
                  末帧检测到 {{ currentDetections.length }} 个目标
                  <span v-if="maxFrameDetections > 0" class="ml-1">· 最大帧检测数 {{ maxFrameDetections }}</span>
                  <span v-if="totalDetections > 0" class="ml-1">· 累计 {{ totalDetections }} 次检测</span>
                </div>
                <div v-if="saveState === 'saving'" class="text-slate-600 text-xs mt-0.5 animate-pulse">
                  正在保存到历史记录库...
                </div>
                <div v-else-if="saveState === 'saved'" class="text-emerald-500 text-xs mt-0.5">
                  已保存到历史记录库
                </div>
                <div v-else-if="saveState === 'error'" class="text-red-500 text-xs mt-0.5">
                  保存失败
                </div>
              </div>
            </div>
          </div>
        </Transition>

        <!-- Detection count badge (top-right, analyzing only) -->
        <Transition name="fade">
          <div
            v-if="isAnalyzing && currentDetections.length > 0"
            class="absolute top-4 right-4 px-3 py-1.5 rounded-lg
                   bg-slate-950/85 border border-blue-500/40 backdrop-blur
                   text-blue-400 text-xs font-mono font-medium tracking-wider"
          >
            {{ currentDetections.length }} TARGET{{ currentDetections.length !== 1 ? 'S' : '' }}
          </div>
        </Transition>

        <!-- State pill (top-left) -->
        <div class="absolute top-4 left-4">
          <span
            class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md border
                   text-xs font-mono font-medium tracking-widest"
            :class="[stateInfo.color, stateInfo.bg]"
          >
            <span v-if="isAnalyzing" class="w-1.5 h-1.5 rounded-full bg-current animate-pulse"></span>
            {{ stateInfo.label }}
          </span>
        </div>
      </div>
    </div>

    <!-- ── RIGHT: AI Console ──────────────────────────────────────────────────── -->
    <aside class="w-80 flex-shrink-0 flex flex-col bg-slate-900 border-l border-slate-800">

      <!-- Console header -->
      <div class="px-5 py-4 border-b border-slate-800 flex-shrink-0">
        <h2 class="text-sm font-semibold text-white tracking-wide">AI 分析控制台</h2>
        <p class="text-xs text-slate-500 mt-0.5">配置模型与检测目标</p>
      </div>

      <div class="flex-1 overflow-y-auto px-5 py-4 space-y-5">

        <!-- Video source -->
        <div>
          <label class="block text-xs font-medium text-slate-400 tracking-wider uppercase mb-2">视频来源</label>
          <div class="grid grid-cols-2 gap-2">
            <button
              class="flex items-center justify-center gap-2 py-2 rounded-lg border
                     text-xs font-medium transition-all duration-150"
              :class="sourceType === 'local_file'
                ? 'bg-blue-600/20 border-blue-500/50 text-blue-400'
                : 'bg-slate-800 border-slate-700 text-slate-400 hover:border-slate-600 hover:text-slate-300'"
              :disabled="isLocked"
              @click="triggerFilePicker"
            >
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/>
                <polyline points="14,2 14,8 20,8"/>
              </svg>
              本地文件
            </button>
            <button
              class="flex items-center justify-center gap-2 py-2 rounded-lg border
                     text-xs font-medium transition-all duration-150"
              :class="sourceType === 'webcam'
                ? 'bg-blue-600/20 border-blue-500/50 text-blue-400'
                : 'bg-slate-800 border-slate-700 text-slate-400 hover:border-slate-600 hover:text-slate-300'"
              :disabled="isLocked"
              @click="onSelectWebcam"
            >
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="3"/>
                <path d="M12 1v4M12 19v4M4.22 4.22l2.83 2.83M16.95 16.95l2.83 2.83M1 12h4M19 12h4M4.22 19.78l2.83-2.83M16.95 7.05l2.83-2.83"/>
              </svg>
              实时摄像
            </button>
          </div>
          <!-- Loaded file indicator -->
          <div v-if="hasVideo && sourceType === 'local_file'"
               class="mt-2 flex items-center justify-between px-2.5 py-1.5 rounded-lg
                      bg-emerald-500/8 border border-emerald-500/20">
            <span class="text-emerald-400 text-xs">✓ 视频已就绪</span>
            <button
              class="text-xs text-slate-500 hover:text-slate-300 transition-colors"
              :disabled="isLocked"
              @click="triggerFilePicker"
            >更换</button>
          </div>
        </div>

        <!-- Model Info Banner (Phase 3.1) -->
        <div v-if="currentCapabilities" class="mb-4 p-3 rounded-lg border" :class="isOpenVocabModel ? 'bg-blue-500/10 border-blue-500/30' : 'bg-amber-500/10 border-amber-500/30'">
          <div class="flex items-start justify-between gap-2">
            <div>
              <div class="flex items-center gap-2">
                <span class="text-sm font-medium text-white">{{ currentCapabilities.display_name }}</span>
                <span class="px-1.5 py-0.5 rounded text-xs" :class="isOpenVocabModel ? 'bg-blue-500/20 text-blue-400' : 'bg-amber-500/20 text-amber-400'">
                  {{ isOpenVocabModel ? '开放词汇' : '固定类别' }}
                </span>
              </div>
              <p class="text-xs text-slate-400 mt-1">{{ currentCapabilities.description }}</p>
            </div>
            <div v-if="modelLoading" class="flex-shrink-0">
              <svg class="w-4 h-4 text-blue-400 animate-spin" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
              </svg>
            </div>
          </div>
        </div>

        <!-- Model selector -->
        <div>
          <label class="block text-xs font-medium text-slate-400 tracking-wider uppercase mb-2">推理模型</label>
          <div class="relative">
            <select
              :value="selectedModelId"
              :disabled="isLocked"
              class="w-full appearance-none bg-slate-800 border border-slate-700 rounded-lg
                     px-3 py-2.5 text-sm text-slate-200 cursor-pointer outline-none
                     focus:border-blue-500 focus:ring-1 focus:ring-blue-500/30
                     disabled:opacity-40 disabled:cursor-not-allowed transition-all"
              @change="(e) => selectModel((e.target as HTMLSelectElement).value)"
            >
              <option v-for="m in modelList" :key="m.model_id" :value="m.model_id" class="bg-slate-900">
                {{ m.display_name }}
              </option>
            </select>
            <svg class="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none text-slate-500"
                 width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="6,9 12,15 18,9"/>
            </svg>
          </div>
          <div v-if="modelError" class="mt-1.5 text-xs text-red-400">{{ modelError }}</div>
        </div>

        <!-- Phase 3.1: Dynamic Configuration Based on Model Type -->
        
        <!-- Open Vocabulary Model: Prompt Input -->
        <div v-if="isOpenVocabModel">
          <!-- Quick chips for open-vocab -->
          <div class="mb-3">
            <label class="block text-xs font-medium text-slate-400 tracking-wider uppercase mb-2">快捷类别</label>
            <div class="flex flex-wrap gap-1.5">
              <button
                v-for="chip in QUICK_CHIPS_LOCAL"
                :key="chip.en"
                class="px-2.5 py-1 rounded-full border text-xs transition-all duration-150"
                :class="isLocked
                  ? 'border-slate-700 text-slate-600 cursor-not-allowed opacity-50'
                  : targetClasses.includes(chip.en)
                    ? 'border-blue-500/50 bg-blue-500/10 text-blue-400'
                    : 'border-slate-600 text-slate-300 hover:border-blue-500 hover:text-blue-400 hover:bg-blue-500/10 cursor-pointer'"
                :disabled="isLocked"
                @click="appendChip(chip.en)"
              >{{ chip.label }}</button>
            </div>
          </div>

          <!-- Prompt input for open-vocab -->
          <div>
            <label class="block text-xs font-medium text-slate-400 tracking-wider uppercase mb-2">检测目标 Prompt</label>
            <textarea
              v-model="promptInput"
              :disabled="isLocked"
              placeholder="car, person, drone, backpack..."
              rows="3"
              spellcheck="false"
              class="w-full bg-slate-800 border border-slate-700 rounded-lg
                     px-3 py-2.5 text-sm text-slate-200 resize-none outline-none
                     placeholder:text-slate-600 font-mono
                     focus:border-blue-500 focus:ring-1 focus:ring-blue-500/30
                     disabled:opacity-40 disabled:cursor-not-allowed transition-all"
            ></textarea>
            <!-- Parsed class chips -->
            <div v-if="targetClasses.length > 0" class="flex flex-wrap gap-1 mt-2">
              <span
                v-for="cls in targetClasses" :key="cls"
                class="inline-flex items-center px-2 py-0.5 rounded-md
                       bg-blue-500/10 border border-blue-500/30 text-blue-400 text-xs font-mono"
              >{{ cls }}</span>
            </div>
            <div v-else class="mt-1.5 text-xs text-amber-500/70">⚠ 尚未定义检测目标</div>
          </div>
        </div>

        <!-- Closed Set Model: Class Filter -->
        <div v-else-if="isClosedSetModel">
          <div class="mb-3 p-3 rounded-lg bg-amber-500/5 border border-amber-500/20">
            <div class="flex items-center gap-2 text-amber-400 text-xs">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="10"/>
                <line x1="12" y1="8" x2="12" y2="12"/>
                <line x1="12" y1="16" x2="12.01" y2="16"/>
              </svg>
              <span>该模型为固定类别检测，仅支持预设类别</span>
            </div>
          </div>

          <!-- Class selection controls -->
          <div class="flex items-center justify-between mb-2">
            <label class="text-xs font-medium text-slate-400 tracking-wider uppercase">
              支持类别 ({{ currentCapabilities?.supported_classes?.length ?? 0 }})
            </label>
            <div class="flex gap-2">
              <button
                class="text-xs text-blue-400 hover:text-blue-300 transition-colors"
                :disabled="isLocked"
                @click="selectAllClasses"
              >全选</button>
              <button
                class="text-xs text-slate-500 hover:text-slate-400 transition-colors"
                :disabled="isLocked"
                @click="clearAllClasses"
              >清空</button>
            </div>
          </div>

          <!-- Supported classes grid -->
          <div class="max-h-48 overflow-y-auto border border-slate-700 rounded-lg p-2 bg-slate-800/50">
            <div class="grid grid-cols-2 gap-1">
              <button
                v-for="cls in currentCapabilities?.supported_classes"
                :key="cls"
                class="text-left px-2 py-1.5 rounded text-xs transition-all duration-150 truncate"
                :class="[
                  isLocked
                    ? 'cursor-not-allowed opacity-50'
                    : 'cursor-pointer',
                  selectedClasses.has(cls)
                    ? 'bg-blue-500/20 border border-blue-500/40 text-blue-400'
                    : 'bg-slate-700/50 border border-transparent text-slate-400 hover:bg-slate-700 hover:text-slate-300'
                ]"
                :disabled="isLocked"
                @click="toggleClass(cls)"
              >
                <span class="flex items-center gap-1.5">
                  <span
                    class="w-3 h-3 rounded flex-shrink-0 flex items-center justify-center border text-[8px]"
                    :class="selectedClasses.has(cls) ? 'bg-blue-500 border-blue-500 text-white' : 'border-slate-600'"
                  >
                    <span v-if="selectedClasses.has(cls)">✓</span>
                  </span>
                  {{ cls }}
                </span>
              </button>
            </div>
          </div>

          <!-- Selected classes summary -->
          <div v-if="selectedClasses.size > 0" class="mt-2 flex flex-wrap gap-1">
            <span
              v-for="cls in Array.from(selectedClasses).slice(0, 5)"
              :key="cls"
              class="inline-flex items-center px-2 py-0.5 rounded-md
                     bg-blue-500/10 border border-blue-500/30 text-blue-400 text-xs"
            >{{ cls }}</span>
            <span
              v-if="selectedClasses.size > 5"
              class="inline-flex items-center px-2 py-0.5 rounded-md
                     bg-slate-700 text-slate-400 text-xs"
            >+{{ selectedClasses.size - 5 }}</span>
          </div>
          <div v-else class="mt-2 text-xs text-amber-500/70">⚠ 请选择要显示的类别</div>
        </div>

        <!-- Loading / Error state -->
        <div v-else-if="modelLoading" class="flex items-center justify-center py-8">
          <svg class="w-6 h-6 text-blue-400 animate-spin" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
          </svg>
        </div>

        <!-- CTA buttons -->
        <div class="pt-1 space-y-2">
          <button
            v-if="!isAnalyzing && !isPaused"
            class="w-full py-3 rounded-xl text-sm font-semibold tracking-wide
                   flex items-center justify-center gap-2.5 transition-all duration-200"
            :class="canExecute
              ? 'bg-gradient-to-r from-blue-600 to-blue-500 text-white shadow-lg shadow-blue-500/25 hover:from-blue-500 hover:to-blue-400 active:scale-[0.98]'
              : 'bg-slate-800 border border-slate-700 text-slate-500 cursor-not-allowed'"
            :disabled="!canExecute"
            @click="startAnalysis"
          >
            {{ analysisState === 'finished' ? '重新启动分析' : '启动实时分析' }}
          </button>

          <!-- Pause & Resume buttons -->
          <div v-if="isAnalyzing || isPaused" class="grid grid-cols-2 gap-2">
            <button
              v-if="isAnalyzing"
              class="flex items-center justify-center gap-2 py-3 rounded-xl text-sm font-semibold tracking-wide
                     bg-amber-600/20 border border-amber-600/40 text-amber-400
                     hover:bg-amber-600/30 transition-all duration-200 active:scale-[0.98]"
              @click="pauseAnalysis"
            >
              <svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor">
                <rect x="6" y="4" width="4" height="16" rx="1"/>
                <rect x="14" y="4" width="4" height="16" rx="1"/>
              </svg>
              暂停 (空格)
            </button>
            <button
              v-if="isPaused"
              class="flex items-center justify-center gap-2 py-3 rounded-xl text-sm font-semibold tracking-wide
                     bg-emerald-600/20 border border-emerald-600/40 text-emerald-400
                     hover:bg-emerald-600/30 transition-all duration-200 active:scale-[0.98]"
              @click="resumeAnalysis"
            >
              <svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor">
                <polygon points="5,3 19,12 5,21"/>
              </svg>
              继续播放
            </button>
            <button
              class="flex items-center justify-center gap-2 py-3 rounded-xl text-sm font-semibold tracking-wide
                     bg-red-950/60 border border-red-700/60 text-red-400
                     hover:bg-red-900/60 hover:border-red-600 transition-all duration-200 active:scale-[0.98]"
              @click="stopAnalysis"
            >
              <svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor">
                <rect x="4" y="4" width="16" height="16" rx="2"/>
              </svg>
              停止分析
            </button>
          </div>
        </div>

        <div class="border-t border-slate-800"></div>

        <!-- ══════════════════════════════════════════════════════════════════════════ -->
        <!-- Phase 5: 性能监控（三层结构）                                            -->
        <!-- ══════════════════════════════════════════════════════════════════════════ -->

        <!-- ── 第1层：主指标卡 ───────────────────────────────────────────────────── -->
        <div>
          <label class="block text-xs font-medium text-slate-400 tracking-wider uppercase mb-3">性能监控</label>

          <!-- 端到端延迟（带进度条） -->
          <div class="bg-slate-800/60 rounded-lg p-3 border border-slate-700/50 mb-2">
            <div class="flex items-center justify-between mb-1.5">
              <span class="text-xs text-slate-500">端到端延迟</span>
              <span class="text-lg font-bold font-mono tabular-nums"
                    :class="latencyOk ? 'text-emerald-400' : 'text-red-400'">
                {{ isAnalyzing ? fmt(endToEndLatencyMs) : '—' }}
                <span class="text-xs font-normal opacity-70 ml-0.5">ms</span>
              </span>
            </div>
            <div class="h-1.5 rounded-full bg-slate-700 overflow-hidden">
              <div
                class="h-full rounded-full transition-all duration-500"
                :class="latencyOk ? 'bg-emerald-400' : 'bg-red-400'"
                :style="{ width: isAnalyzing ? `${Math.min(((endToEndLatencyMs ?? 0) / LATENCY_BAR_MAX_MS) * 100, 100)}%` : '0%' }"
              ></div>
            </div>
          </div>

          <!-- 主指标四卡片 -->
          <div class="grid grid-cols-4 gap-2 mb-3">

            <!-- 后端处理耗时 -->
            <div class="bg-slate-800/60 rounded-lg p-3 border border-slate-700/50">
              <div class="text-xs text-slate-500 mb-1">后端处理耗时</div>
              <div class="text-lg font-bold font-mono tabular-nums text-blue-400">
                {{ isAnalyzing ? fmt(backendProcessMs) : '—' }}
                <span class="text-xs font-normal opacity-70 ml-0.5">ms</span>
              </div>
            </div>

            <!-- 后端处理 FPS -->
            <div class="bg-slate-800/60 rounded-lg p-3 border border-slate-700/50">
              <div class="text-xs text-slate-500 mb-1">后端处理 FPS</div>
              <div class="text-lg font-bold font-mono tabular-nums text-emerald-400">
                {{ isAnalyzing ? fmt(fpsBackend) : '—' }}
                <span class="text-xs font-normal opacity-70 ml-0.5">FPS</span>
              </div>
            </div>

            <!-- 纯推理耗时 -->
            <div class="bg-slate-800/60 rounded-lg p-3 border border-slate-700/50">
              <div class="text-xs text-slate-500 mb-1">纯推理耗时</div>
              <div class="text-lg font-bold font-mono tabular-nums text-purple-400">
                {{ isAnalyzing ? fmt(sessionMs) : '—' }}
                <span class="text-xs font-normal opacity-70 ml-0.5">ms</span>
              </div>
            </div>

            <!-- 纯推理 FPS -->
            <div class="bg-slate-800/60 rounded-lg p-3 border border-slate-700/50">
              <div class="text-xs text-slate-500 mb-1">纯推理 FPS</div>
              <div class="text-lg font-bold font-mono tabular-nums text-purple-400">
                {{ isAnalyzing ? fmt(fpsInfer) : '—' }}
                <span class="text-xs font-normal opacity-70 ml-0.5">FPS</span>
              </div>
            </div>
          </div>
        </div>

        <!-- ── 第2层：工程 / 实时指标明细 ─────────────────────────────────────── -->
        <div>
          <label class="block text-xs font-medium text-slate-400 tracking-wider uppercase mb-2">工程 &amp; 实时指标</label>
          <div class="rounded-lg border border-slate-700/50 bg-slate-800/40 p-3 space-y-2 text-xs">

            <!-- 工程指标子组 -->
            <div class="text-slate-500 uppercase tracking-wider text-[10px] mb-1">工程指标</div>
            <div class="grid grid-cols-2 gap-x-4 gap-y-1.5">

              <!-- 算法全流程耗时 -->
              <div class="flex items-center justify-between">
                <span class="text-slate-500">算法全流程耗时</span>
                <span class="font-mono tabular-nums text-blue-300">
                  {{ isAnalyzing ? fmt(algoProcessMs) : '—' }} ms
                </span>
              </div>

              <!-- 算法全流程 FPS -->
              <div class="flex items-center justify-between">
                <span class="text-slate-500">算法全流程 FPS</span>
                <span class="font-mono tabular-nums text-blue-300">
                  {{ isAnalyzing ? fmt(fpsAlgo) : '—' }} FPS
                </span>
              </div>

            </div>

            <div class="border-t border-slate-700/40 pt-2"></div>

            <!-- 系统实时指标子组 -->
            <div class="text-slate-500 uppercase tracking-wider text-[10px] mb-1">系统实时指标</div>
            <div class="grid grid-cols-2 gap-x-4 gap-y-1.5">

              <!-- 发送节奏 -->
              <div class="flex items-center justify-between">
                <span class="text-slate-500">发送节奏</span>
                <span class="font-mono tabular-nums text-slate-300">
                  {{ isAnalyzing ? fmt(frontendSendIntervalMs) : '—' }} ms
                </span>
              </div>

              <!-- 发送节奏 FPS -->
              <div class="flex items-center justify-between">
                <span class="text-slate-500">发送节奏 FPS</span>
                <span class="font-mono tabular-nums text-slate-300">
                  {{ isAnalyzing ? fmt(fpsSend) : '—' }} FPS
                </span>
              </div>

              <!-- 结果返回节奏 -->
              <div class="flex items-center justify-between">
                <span class="text-slate-500">结果返回节奏</span>
                <span class="font-mono tabular-nums text-emerald-300">
                  {{ isAnalyzing ? fmt(resultIntervalMs) : '—' }} ms
                </span>
              </div>

              <!-- 结果返回 FPS -->
              <div class="flex items-center justify-between">
                <span class="text-slate-500">结果返回 FPS</span>
                <span class="font-mono tabular-nums text-emerald-300">
                  {{ isAnalyzing ? fmt(fpsResult) : '—' }} FPS
                </span>
              </div>

            </div>
          </div>
        </div>

        <!-- ── 第3层：调试诊断区 ───────────────────────────────────────────────── -->
        <div>
          <label class="block text-xs font-medium text-amber-400/80 tracking-wider uppercase mb-2">链路诊断</label>
          <div class="rounded-lg border border-amber-700/40 bg-amber-950/15 p-3 space-y-1.5 text-xs">

            <!-- 前端编码耗时 -->
            <div class="flex items-center justify-between">
              <span class="text-slate-500">前端编码耗时</span>
              <span class="font-mono tabular-nums text-amber-300">
                {{ isAnalyzing ? fmt(frontendEncodeMs) : '—' }} ms
              </span>
            </div>

            <!-- 前端消息处理 -->
            <div class="flex items-center justify-between">
              <span class="text-slate-500">前端消息处理</span>
              <span class="font-mono tabular-nums text-amber-300">
                {{ isAnalyzing ? fmt(frontendRenderMs) : '—' }} ms
              </span>
            </div>

            <!-- 链路额外开销 -->
            <div class="flex items-center justify-between pt-1 border-t border-amber-700/30">
              <span class="text-slate-500">链路额外开销</span>
              <span class="font-mono tabular-nums text-red-400">
                {{ isAnalyzing ? fmt(pipelineExtraMs) : '—' }} ms
              </span>
            </div>

            <!-- 提示文字 -->
            <div class="text-amber-600/60 text-[10px] leading-relaxed pt-1">
              额外开销不含后端推理，含网络传输、队列等待、前端处理等
            </div>

          </div>
        </div>

        <!-- Network controls -->
        <div>
          <label class="block text-xs font-medium text-slate-400 tracking-wider uppercase mb-2">网络控制</label>
          <div class="flex gap-2">
            <button
              class="flex-1 py-2 rounded-lg border text-xs font-medium transition-all
                     border-slate-700 text-slate-400 bg-slate-800
                     hover:border-red-700/70 hover:text-red-400
                     disabled:opacity-35 disabled:cursor-not-allowed"
              :disabled="wsStatus === 'disconnected'"
              @click="disconnect"
            >断开</button>
            <button
              class="flex-1 py-2 rounded-lg border text-xs font-medium transition-all
                     border-slate-700 text-slate-400 bg-slate-800
                     hover:border-blue-600 hover:text-blue-400
                     disabled:opacity-35 disabled:cursor-not-allowed"
              :disabled="wsStatus === 'connected'"
              @click="connect"
            >重连</button>
          </div>
        </div>

      </div>
    </aside>

    <!-- ── Pause Dialog Modal ──────────────────────────────────────────────────── -->
    <Teleport to="body">
      <Transition name="modal">
        <div
          v-if="showPauseDialog"
          class="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm"
          @click.self="resumeAnalysis"
        >
          <div class="relative w-full max-w-md mx-4 bg-slate-900 rounded-2xl border border-slate-700 shadow-2xl overflow-hidden">
            <!-- Modal header -->
            <div class="flex items-center justify-between px-6 py-5 border-b border-slate-800">
              <div class="flex items-center gap-3">
                <div class="p-2 rounded-lg bg-amber-500/15">
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="text-amber-400">
                    <circle cx="12" cy="12" r="10"/>
                    <polyline points="12,6 12,12 16,14"/>
                  </svg>
                </div>
                <div>
                  <h3 class="text-white font-semibold text-lg">分析已暂停</h3>
                  <p class="text-slate-500 text-sm">当前进度已保存</p>
                </div>
              </div>
            </div>

            <!-- Stats summary -->
            <div class="px-6 py-4 border-b border-slate-800">
              <div class="grid grid-cols-3 gap-4 text-center">
                <div>
                  <div class="text-2xl font-bold font-mono text-blue-400">{{ totalDetections }}</div>
                  <div class="text-xs text-slate-500 mt-1">累计检测次数</div>
                </div>
                <div>
                  <div class="text-2xl font-bold font-mono text-emerald-400">{{ maxFrameDetections }}</div>
                  <div class="text-xs text-slate-500 mt-1">最大帧检测数</div>
                </div>
                <div>
                  <div class="text-2xl font-bold font-mono text-amber-400">{{ currentDetections.length }}</div>
                  <div class="text-xs text-slate-500 mt-1">当前帧目标</div>
                </div>
              </div>
            </div>

            <!-- Action buttons -->
            <div class="px-6 py-5 space-y-3">
              <button
                class="w-full py-3 rounded-xl text-sm font-semibold tracking-wide
                       flex items-center justify-center gap-2.5
                       bg-emerald-600 border border-emerald-500 text-white
                       hover:bg-emerald-500 transition-all duration-200 active:scale-[0.98]"
                @click="resumeAnalysis"
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                  <polygon points="5,3 19,12 5,21"/>
                </svg>
                继续播放
              </button>

              <button
                class="w-full py-3 rounded-xl text-sm font-semibold tracking-wide
                       flex items-center justify-center gap-2.5
                       bg-blue-600/20 border border-blue-600/40 text-blue-400
                       hover:bg-blue-600/30 transition-all duration-200 active:scale-[0.98]"
                @click="saveAndFinish"
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M19 21H5a2 2 0 01-2-2V5a2 2 0 012-2h11l5 5v11a2 2 0 01-2 2z"/>
                  <polyline points="17,21 17,13 7,13 7,21"/>
                  <polyline points="7,3 7,8 15,8"/>
                </svg>
                保存到历史记录库
              </button>

              <p class="text-center text-xs text-slate-600 mt-2">
                按 <kbd class="px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 font-mono">空格</kbd> 可快速继续播放
              </p>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>

  </div>
</template>

<style scoped>
/* Toast stack animation */
.toast-enter-active  { transition: all 0.25s ease; }
.toast-leave-active  { transition: all 0.2s ease; }
.toast-enter-from    { opacity: 0; transform: translateY(-12px) scale(0.95); }
.toast-leave-to      { opacity: 0; transform: translateY(-8px) scale(0.95); }
.toast-move          { transition: transform 0.2s ease; }

.fade-enter-active, .fade-leave-active { transition: opacity 0.3s ease; }
.fade-enter-from, .fade-leave-to       { opacity: 0; }
</style>
