<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import type { Detection, ServerMessage, InferenceResult, SupportedModel } from '@/types/skyline'
import { SUPPORTED_MODELS } from '@/types/skyline'
import { useWebSocket }      from '@/composables/useWebSocket'
import { useVideoStream }    from '@/composables/useVideoStream'
import { useCanvasRenderer } from '@/composables/useCanvasRenderer'

// ── DOM refs ─────────────────────────────────────────────────────────────────
const canvasEl = ref<HTMLCanvasElement | null>(null)
const videoEl  = ref<HTMLVideoElement | null>(null)

// ── Analysis state machine ────────────────────────────────────────────────────
// standby  → [file loaded]     → ready
// ready    → [EXECUTE clicked] → analyzing
// analyzing→ [video ended]     → finished
//          → [STOP clicked]    → finished
// finished → [EXECUTE clicked] → analyzing  (re-run from start)
//          → [file loaded]     → ready      (new file)
type AnalysisState = 'standby' | 'ready' | 'analyzing' | 'finished'
const analysisState = ref<AnalysisState>('standby')

// Derived convenience booleans
const isAnalyzing = computed(() => analysisState.value === 'analyzing')
const canExecute  = computed(() => analysisState.value === 'ready' || analysisState.value === 'finished')
const isLocked    = computed(() => analysisState.value === 'analyzing') // disables upload/source switch

// ── Telemetry state ───────────────────────────────────────────────────────────
const systemLatency     = ref(0)
const inferenceTime     = ref(0)
const currentDetections = ref<Detection[]>([])
const displayFps        = ref(0)
const errorBanner       = ref('')
const isDragging        = ref(false)

let fpsCount = 0, fpsLast = Date.now()
function tickFps() {
  fpsCount++
  const now = Date.now()
  if (now - fpsLast >= 1000) { displayFps.value = fpsCount; fpsCount = 0; fpsLast = now }
}

// ── AI console state ──────────────────────────────────────────────────────────
const selectedModel = ref<SupportedModel>('YOLO-World-V2')
const promptInput   = ref('car, person, drone')
const targetClasses = computed<string[]>(() =>
  promptInput.value.split(',').map((s) => s.trim()).filter(Boolean),
)

// ── WebSocket ─────────────────────────────────────────────────────────────────
const { status: wsStatus, connect, disconnect, send } = useWebSocket({
  onMessage(msg: ServerMessage) {
    if (msg.message_type === 'inference_result') {
      const r = msg as InferenceResult
      systemLatency.value     = Math.round((Date.now() / 1000 - r.timestamp) * 1000)
      inferenceTime.value     = Math.round(r.inference_time_ms)
      currentDetections.value = r.detections
      tickFps()
    } else if (msg.message_type === 'error') {
      errorBanner.value = msg.detail
      setTimeout(() => { errorBanner.value = '' }, 4000)
    }
  },
})

// ── Video stream composable ───────────────────────────────────────────────────
const { sourceType, isPlaying, hasVideo, loadFile, selectWebcam, startPush, stopPush, release } =
  useVideoStream({
    videoEl,
    systemLatency,
    onFrame({ frame_id, timestamp, image_base64 }) {
      send(JSON.stringify({
        message_type:   'video_frame',
        frame_id,
        timestamp,
        image_base64,
        selected_model: selectedModel.value,
        target_classes: targetClasses.value,
      }))
    },
  })

// ── Canvas renderer ───────────────────────────────────────────────────────────
const { startRendering } = useCanvasRenderer({
  canvasEl,
  videoEl,
  detections: currentDetections,
  isPlaying,
  hasVideo,
})

// ── State machine actions ─────────────────────────────────────────────────────

function startAnalysis() {
  const video = videoEl.value
  if (!video || !hasVideo.value) return

  // If re-running after FINISHED, seek to beginning first
  if (analysisState.value === 'finished') {
    video.currentTime = 0
    currentDetections.value = []
  }

  video.play()
  startPush()
  analysisState.value = 'analyzing'
}

function stopAnalysis() {
  stopPush()
  videoEl.value?.pause()
  analysisState.value = 'finished'
}

// ── File upload handlers ──────────────────────────────────────────────────────

function onFileChange(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (!file) return
  loadFile(file)
  currentDetections.value = []
  analysisState.value = 'ready'
}

function onDrop(e: DragEvent) {
  isDragging.value = false
  const file = e.dataTransfer?.files[0]
  if (file && file.type.startsWith('video/')) {
    loadFile(file)
    currentDetections.value = []
    analysisState.value = 'ready'
  }
}

// ── Webcam handler ────────────────────────────────────────────────────────────

async function onSelectWebcam() {
  await selectWebcam()      // auto-plays + auto-pushes in composable
  currentDetections.value = []
  analysisState.value = 'analyzing'
}

// ── Lifecycle ─────────────────────────────────────────────────────────────────

onMounted(() => {
  connect()
  startRendering()

  // Canvas size follows viewport container
  const observer = new ResizeObserver(() => {
    const canvas    = canvasEl.value
    const container = canvas?.parentElement
    if (!canvas || !container) return
    canvas.width  = container.clientWidth
    canvas.height = container.clientHeight
  })
  if (canvasEl.value?.parentElement) observer.observe(canvasEl.value.parentElement)

  // video.ended → FINISHED state (for local file mode)
  const video = videoEl.value
  if (video) {
    video.addEventListener('ended', () => {
      stopPush()
      analysisState.value = 'finished'
    })
  }
})

// ── Status helpers ────────────────────────────────────────────────────────────

const wsStatusLabel = computed(() => ({
  connected:    'ONLINE',
  connecting:   'SYNCING...',
  disconnected: 'OFFLINE',
}[wsStatus.value]))

const wsStatusClass = computed(() => ({
  connected:    'status--online',
  connecting:   'status--syncing',
  disconnected: 'status--offline',
}[wsStatus.value]))

const stateLabel = computed(() => ({
  standby:   'STANDBY',
  ready:     'ARMED',
  analyzing: 'ANALYZING',
  finished:  'COMPLETE',
}[analysisState.value]))

const stateClass = computed(() => ({
  standby:   'state--standby',
  ready:     'state--ready',
  analyzing: 'state--analyzing',
  finished:  'state--finished',
}[analysisState.value]))

const latencyClass = computed(() =>
  systemLatency.value > 200 ? 'metric--warn' : 'metric--ok',
)
</script>

<template>
  <div class="skyline-shell">

    <!-- ── Top bar ────────────────────────────────────────────────────────── -->
    <header class="topbar">
      <span class="topbar__logo">&#9651; SKYLINE</span>
      <span class="topbar__sub">INTELLIGENT VISUAL ANALYSIS SYSTEM v1.0</span>

      <!-- State pill -->
      <span class="state-pill" :class="stateClass">{{ stateLabel }}</span>

      <!-- WS reconnect banner -->
      <transition name="banner">
        <div v-if="wsStatus !== 'connected'" class="topbar__banner topbar__banner--warn">
          &#9888; WebSocket {{ wsStatusLabel }} — Auto-reconnecting…
        </div>
      </transition>
      <!-- Error banner -->
      <transition name="banner">
        <div v-if="errorBanner" class="topbar__banner topbar__banner--error">
          &#10005; {{ errorBanner }}
        </div>
      </transition>
    </header>

    <!-- ── Main layout ──────────────────────────────────────────────────────── -->
    <main class="workspace">

      <!-- ── LEFT: Control panel ─────────────────────────────────────────── -->
      <aside class="ctrl-panel">

        <!-- SYSTEM STATUS -->
        <section class="ctrl-section">
          <h3 class="section-title">SYSTEM STATUS</h3>
          <div class="status-row">
            <span class="status-dot" :class="wsStatusClass"></span>
            <span class="status-label">WebSocket</span>
            <span class="status-value" :class="wsStatusClass">{{ wsStatusLabel }}</span>
          </div>
          <div class="status-row">
            <span class="status-dot" :class="isAnalyzing ? 'status--online' : 'status--offline'"></span>
            <span class="status-label">GPU Inference</span>
            <span class="status-value" :class="isAnalyzing ? 'status--online' : 'status--offline'">
              {{ isAnalyzing ? 'ACTIVE' : 'IDLE' }}
            </span>
          </div>
        </section>

        <!-- VIDEO SOURCE -->
        <section class="ctrl-section">
          <h3 class="section-title">VIDEO SOURCE</h3>
          <div class="source-tabs">
            <button
              class="source-tab"
              :class="{ 'source-tab--active': sourceType === 'local_file' }"
              :disabled="isLocked"
            >
              <span class="tab-icon">&#9654;</span> LOCAL FILE
            </button>
            <button
              class="source-tab"
              :class="{ 'source-tab--active': sourceType === 'webcam' }"
              :disabled="isLocked"
              @click="onSelectWebcam"
            >
              <span class="tab-icon">&#9679;</span> LIVE CAM
            </button>
          </div>

          <!-- Drop zone — hidden during analysis -->
          <div
            v-if="sourceType === 'local_file' && !isLocked"
            class="drop-zone"
            :class="{ 'drop-zone--over': isDragging, 'drop-zone--loaded': hasVideo }"
            @dragover.prevent="isDragging = true"
            @dragleave="isDragging = false"
            @drop.prevent="onDrop"
            @click="($refs.fileInput as HTMLInputElement).click()"
          >
            <input ref="fileInput" type="file" accept="video/*" class="hidden" @change="onFileChange" />
            <div class="drop-zone__icon">{{ hasVideo ? '&#10003;' : '&#8645;' }}</div>
            <div class="drop-zone__text">
              {{ hasVideo ? 'MEDIA LOADED — Click to replace' : 'DROP VIDEO FILE HERE' }}
            </div>
            <div class="drop-zone__sub">MP4 / MOV / AVI</div>
          </div>

          <!-- Locked hint during analysis -->
          <div v-else-if="sourceType === 'local_file' && isLocked" class="locked-hint">
            <span>&#128274; Source locked during analysis</span>
          </div>

          <!-- Webcam hint -->
          <div v-else-if="sourceType === 'webcam'" class="webcam-hint">
            <div class="webcam-hint__dot"></div>
            <span>Live feed active</span>
          </div>
        </section>

        <!-- AI ANALYSIS CONSOLE -->
        <section class="ctrl-section">
          <h3 class="section-title">AI ANALYSIS CONSOLE</h3>

          <!-- Model selector -->
          <div class="ai-field">
            <label class="ai-label">MODEL</label>
            <div class="ai-select-wrap">
              <select v-model="selectedModel" class="ai-select" :disabled="isLocked">
                <option v-for="m in SUPPORTED_MODELS" :key="m" :value="m">{{ m }}</option>
              </select>
              <span class="ai-select-arrow">&#9660;</span>
            </div>
          </div>

          <!-- Prompt textarea -->
          <div class="ai-field">
            <label class="ai-label">TARGET CLASSES</label>
            <textarea
              v-model="promptInput"
              class="ai-prompt"
              :disabled="isLocked"
              placeholder="car, person, drone, backpack..."
              rows="3"
              spellcheck="false"
            ></textarea>
          </div>

          <!-- Parsed class chips -->
          <div class="ai-chips" v-if="targetClasses.length > 0">
            <span v-for="cls in targetClasses" :key="cls" class="ai-chip">{{ cls }}</span>
          </div>
          <div class="ai-empty" v-else>&#9888; No targets defined</div>

          <div class="ai-count">
            <span class="ai-count__num">{{ targetClasses.length }}</span>
            <span class="ai-count__label">ACTIVE TARGET{{ targetClasses.length !== 1 ? 'S' : '' }}</span>
          </div>

          <!-- ── EXECUTE ANALYSIS button ────────────────────────────────── -->
          <button
            v-if="!isAnalyzing"
            class="btn-execute"
            :class="{ 'btn-execute--armed': canExecute, 'btn-execute--disabled': !canExecute }"
            :disabled="!canExecute"
            @click="startAnalysis"
          >
            <span class="btn-execute__icon">&#9654;</span>
            {{ analysisState === 'finished' ? '[ RE-RUN ANALYSIS ]' : '[ EXECUTE ANALYSIS ]' }}
          </button>

          <!-- ── STOP button ───────────────────────────────────────────── -->
          <button
            v-if="isAnalyzing"
            class="btn-stop"
            @click="stopAnalysis"
          >
            <span class="btn-stop__icon">&#9632;</span>
            [ STOP ANALYSIS ]
          </button>
        </section>

        <!-- PERFORMANCE -->
        <section class="ctrl-section">
          <h3 class="section-title">PERFORMANCE</h3>
          <div class="metric-block">
            <div class="metric-label">END-TO-END LATENCY</div>
            <div class="metric-value" :class="latencyClass">
              {{ isAnalyzing ? systemLatency : '—' }}<span class="metric-unit">ms</span>
            </div>
            <div class="metric-bar">
              <div class="metric-bar__fill" :class="latencyClass"
                   :style="{ width: `${Math.min((systemLatency / 300) * 100, 100)}%` }"></div>
            </div>
          </div>
          <div class="metric-block">
            <div class="metric-label">BACKEND INFERENCE</div>
            <div class="metric-value metric--cyan">
              {{ isAnalyzing ? inferenceTime : '—' }}<span class="metric-unit">ms</span>
            </div>
          </div>
          <div class="metric-block">
            <div class="metric-label">THROUGHPUT</div>
            <div class="metric-value metric--ok">
              {{ isAnalyzing ? displayFps : '—' }}<span class="metric-unit">FPS</span>
            </div>
            <div v-if="systemLatency > 200 && isAnalyzing" class="throttle-badge">
              &#9660; THROTTLED 10 FPS
            </div>
          </div>
        </section>

        <!-- NETWORK -->
        <section class="ctrl-section">
          <h3 class="section-title">NETWORK</h3>
          <div class="ws-url">{{ wsStatus === 'connected' ? 'WS CONNECTED' : 'WS OFFLINE' }}</div>
          <div class="ctrl-actions">
            <button class="btn btn--danger"  @click="disconnect" :disabled="wsStatus === 'disconnected'">DISCONNECT</button>
            <button class="btn btn--primary" @click="connect"    :disabled="wsStatus === 'connected'">RECONNECT</button>
          </div>
        </section>

      </aside>

      <!-- ── RIGHT: Canvas viewport ───────────────────────────────────────── -->
      <section class="viewport">
        <!-- Hidden video: source for frame capture -->
        <video ref="videoEl" class="hidden-video" muted playsinline preload="auto"></video>

        <!-- Main canvas: 60 FPS render via RAF -->
        <canvas ref="canvasEl" class="main-canvas"></canvas>

        <!-- READY overlay: video loaded, awaiting command -->
        <transition name="fade">
          <div v-if="analysisState === 'ready'" class="viewport-overlay viewport-overlay--ready">
            <div class="overlay-content">
              <div class="overlay-icon">&#9671;</div>
              <div class="overlay-title">SYSTEM ARMED</div>
              <div class="overlay-sub">Configure targets and click EXECUTE ANALYSIS</div>
            </div>
          </div>
        </transition>

        <!-- FINISHED overlay: analysis complete -->
        <transition name="fade">
          <div v-if="analysisState === 'finished'" class="viewport-overlay viewport-overlay--finished">
            <div class="overlay-content">
              <div class="overlay-icon">&#10003;</div>
              <div class="overlay-title">ANALYSIS COMPLETE</div>
              <div class="overlay-sub">
                {{ currentDetections.length }} target{{ currentDetections.length !== 1 ? 's' : '' }} in final frame
              </div>
            </div>
          </div>
        </transition>

        <!-- Detection count badge (top-right, ANALYZING only) -->
        <div v-if="isAnalyzing && currentDetections.length > 0" class="det-badge">
          {{ currentDetections.length }} TARGET{{ currentDetections.length !== 1 ? 'S' : '' }}
        </div>
      </section>

    </main>
  </div>
</template>

<style scoped>
/* ── Design tokens ──────────────────────────────────────────────────────── */
:root {
  --bg-deep:     #07091a;
  --bg-panel:    #0d1225;
  --bg-section:  #111827;
  --border:      rgba(0, 255, 136, 0.15);
  --neon-green:  #00ff88;
  --neon-cyan:   #00ccff;
  --neon-red:    #ff3366;
  --neon-yellow: #ffcc00;
  --text-primary:#e2e8f0;
  --text-dim:    #64748b;
  --text-accent: #4dffc3;
}

/* ── Shell ──────────────────────────────────────────────────────────────── */
.skyline-shell {
  display: flex;
  flex-direction: column;
  height: 100vh; width: 100vw;
  background: var(--bg-deep, #07091a);
  color: var(--text-primary, #e2e8f0);
  font-family: 'Courier New', Courier, monospace;
  overflow: hidden;
}

/* ── Top bar ────────────────────────────────────────────────────────────── */
.topbar {
  position: relative;
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 0 24px;
  height: 48px;
  background: #080b18;
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
  z-index: 10;
}
.topbar__logo {
  font-size: 16px; font-weight: 700; letter-spacing: 4px;
  color: var(--neon-green); text-shadow: 0 0 16px rgba(0,255,136,0.6);
}
.topbar__sub { font-size: 10px; letter-spacing: 2px; color: var(--text-dim); }

/* State pill */
.state-pill {
  margin-left: auto;
  font-size: 9px; letter-spacing: 3px; padding: 3px 10px;
  border-radius: 2px; border: 1px solid;
}
.state--standby  { color: var(--text-dim);    border-color: rgba(100,116,139,0.4); }
.state--ready    { color: var(--neon-green);  border-color: var(--neon-green);  box-shadow: 0 0 8px rgba(0,255,136,0.3); animation: pill-pulse 2s infinite; }
.state--analyzing{ color: var(--neon-red);    border-color: var(--neon-red);    box-shadow: 0 0 8px rgba(255,51,102,0.4); }
.state--finished { color: var(--neon-cyan);   border-color: var(--neon-cyan);   box-shadow: 0 0 8px rgba(0,204,255,0.3); }

@keyframes pill-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.55; }
}

/* Banners */
.topbar__banner {
  position: absolute; bottom: -28px; left: 0; right: 0;
  height: 28px; display: flex; align-items: center;
  padding: 0 16px; font-size: 11px; letter-spacing: 1px; z-index: 9;
}
.topbar__banner--warn  { background: rgba(255,170,0,0.15); border-bottom: 2px solid #ffaa00; color: #ffaa00; }
.topbar__banner--error { background: rgba(255,51,102,0.15); border-bottom: 2px solid var(--neon-red); color: var(--neon-red); }

/* ── Workspace ──────────────────────────────────────────────────────────── */
.workspace { display: flex; flex: 1; overflow: hidden; }

/* ── Control panel ──────────────────────────────────────────────────────── */
.ctrl-panel {
  width: 240px; flex-shrink: 0;
  background: var(--bg-panel);
  border-right: 1px solid var(--border);
  overflow-y: auto; padding: 8px 0;
  scrollbar-width: thin;
  scrollbar-color: rgba(0,255,136,0.2) transparent;
}
.ctrl-section { padding: 14px 16px; border-bottom: 1px solid rgba(255,255,255,0.05); }
.section-title { font-size: 9px; letter-spacing: 3px; color: var(--text-dim); margin: 0 0 12px; }

/* Status */
.status-row { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.status-dot  { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.status-label { flex: 1; font-size: 11px; color: var(--text-dim); }
.status-value { font-size: 10px; font-weight: 700; letter-spacing: 1px; }
.status--online  { color: var(--neon-green); background: var(--neon-green); box-shadow: 0 0 6px rgba(0,255,136,0.8); }
.status--syncing { color: var(--neon-yellow); background: var(--neon-yellow); box-shadow: 0 0 6px rgba(255,204,0,0.8); }
.status--offline { color: var(--neon-red); background: var(--neon-red); box-shadow: 0 0 6px rgba(255,51,102,0.8); }
.status-value.status--online,
.status-value.status--syncing,
.status-value.status--offline { background: none; box-shadow: none; }

/* Source tabs */
.source-tabs { display: flex; gap: 6px; margin-bottom: 12px; }
.source-tab {
  flex: 1; padding: 7px 4px;
  background: var(--bg-section); border: 1px solid rgba(255,255,255,0.08); border-radius: 4px;
  color: var(--text-dim); font-family: 'Courier New', Courier, monospace;
  font-size: 9px; letter-spacing: 1px; cursor: pointer; transition: all 0.2s;
  display: flex; flex-direction: column; align-items: center; gap: 4px;
}
.source-tab:hover:not(:disabled) { border-color: var(--border); color: var(--text-primary); }
.source-tab:disabled { opacity: 0.4; cursor: not-allowed; }
.source-tab--active { border-color: var(--neon-green) !important; color: var(--neon-green) !important; box-shadow: 0 0 8px rgba(0,255,136,0.2) inset; }
.tab-icon { font-size: 14px; }

/* Drop zone */
.drop-zone {
  border: 1px dashed rgba(0,255,136,0.3); border-radius: 6px;
  padding: 16px 10px; text-align: center; cursor: pointer; transition: all 0.2s;
  background: rgba(0,255,136,0.02);
}
.drop-zone:hover, .drop-zone--over { border-color: var(--neon-green); background: rgba(0,255,136,0.05); }
.drop-zone--loaded { border-color: rgba(0,255,136,0.6); border-style: solid; }
.drop-zone__icon  { font-size: 24px; color: var(--neon-green); margin-bottom: 6px; }
.drop-zone__text  { font-size: 10px; letter-spacing: 1px; color: var(--text-primary); margin-bottom: 4px; }
.drop-zone__sub   { font-size: 9px; color: var(--text-dim); }

/* Locked hint */
.locked-hint {
  font-size: 10px; color: var(--neon-yellow); letter-spacing: 0.5px;
  padding: 8px 4px; opacity: 0.7;
}

/* Webcam hint */
.webcam-hint { display: flex; align-items: center; gap: 8px; font-size: 11px; color: var(--neon-green); padding: 10px 4px; }
.webcam-hint__dot { width: 8px; height: 8px; border-radius: 50%; background: var(--neon-red); box-shadow: 0 0 6px rgba(255,51,102,0.9); animation: blink 1s infinite; }
@keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0.2; } }

/* ── AI Console ─────────────────────────────────────────────────────────── */
.ai-field { margin-bottom: 10px; }
.ai-label { display: block; font-size: 9px; letter-spacing: 2px; color: var(--text-dim); margin-bottom: 5px; }

.ai-select-wrap { position: relative; }
.ai-select {
  width: 100%; padding: 7px 28px 7px 10px;
  background: #0a0f1e; border: 1px solid rgba(0,204,255,0.35); border-radius: 4px;
  color: var(--neon-cyan); font-family: 'Courier New', Courier, monospace;
  font-size: 11px; cursor: pointer; appearance: none; outline: none; transition: all 0.2s;
}
.ai-select:hover:not(:disabled), .ai-select:focus:not(:disabled) { border-color: var(--neon-cyan); box-shadow: 0 0 8px rgba(0,204,255,0.2); }
.ai-select:disabled { opacity: 0.4; cursor: not-allowed; }
.ai-select option  { background: #0d1225; color: #e2e8f0; }
.ai-select-arrow   { position: absolute; right: 9px; top: 50%; transform: translateY(-50%); font-size: 9px; color: var(--neon-cyan); pointer-events: none; }

.ai-prompt {
  width: 100%; padding: 8px 10px;
  background: #0a0f1e; border: 1px solid rgba(0,255,136,0.25); border-radius: 4px;
  color: var(--neon-green); font-family: 'Courier New', Courier, monospace;
  font-size: 11px; line-height: 1.5; resize: vertical; outline: none; box-sizing: border-box; transition: all 0.2s;
}
.ai-prompt::placeholder { color: rgba(0,255,136,0.25); font-style: italic; }
.ai-prompt:focus:not(:disabled) { border-color: var(--neon-green); box-shadow: 0 0 8px rgba(0,255,136,0.15); }
.ai-prompt:disabled { opacity: 0.4; cursor: not-allowed; }

.ai-chips { display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 8px; }
.ai-chip  { padding: 2px 7px; background: rgba(0,255,136,0.08); border: 1px solid rgba(0,255,136,0.35); border-radius: 3px; color: var(--neon-green); font-size: 9px; }
.ai-empty { font-size: 9px; color: rgba(255,51,102,0.7); margin-bottom: 8px; }
.ai-count { display: flex; align-items: baseline; gap: 6px; margin-top: 6px; margin-bottom: 14px; }
.ai-count__num   { font-size: 22px; font-weight: 700; color: var(--neon-cyan); text-shadow: 0 0 10px rgba(0,204,255,0.5); line-height: 1; }
.ai-count__label { font-size: 9px; letter-spacing: 2px; color: var(--text-dim); }

/* EXECUTE ANALYSIS button */
.btn-execute {
  width: 100%; padding: 13px 8px;
  border-radius: 4px; border: 1px solid;
  font-family: 'Courier New', Courier, monospace;
  font-size: 10px; letter-spacing: 2px; cursor: pointer;
  display: flex; align-items: center; justify-content: center; gap: 8px;
  transition: all 0.25s;
}
.btn-execute--armed {
  background: linear-gradient(135deg, rgba(0,255,136,0.12), rgba(0,204,255,0.06));
  border-color: var(--neon-green); color: var(--neon-green);
  box-shadow: 0 0 18px rgba(0,255,136,0.2), inset 0 0 12px rgba(0,255,136,0.05);
  animation: execute-glow 2s ease-in-out infinite;
}
.btn-execute--armed:hover {
  background: linear-gradient(135deg, rgba(0,255,136,0.22), rgba(0,204,255,0.12));
  box-shadow: 0 0 28px rgba(0,255,136,0.4), inset 0 0 18px rgba(0,255,136,0.1);
  transform: translateY(-1px);
}
.btn-execute--disabled {
  background: rgba(255,255,255,0.03); border-color: rgba(255,255,255,0.1); color: rgba(255,255,255,0.2);
  cursor: not-allowed;
}
.btn-execute__icon { font-size: 14px; }

@keyframes execute-glow {
  0%, 100% { box-shadow: 0 0 18px rgba(0,255,136,0.2), inset 0 0 12px rgba(0,255,136,0.05); }
  50%       { box-shadow: 0 0 30px rgba(0,255,136,0.4), inset 0 0 18px rgba(0,255,136,0.1); }
}

/* STOP button */
.btn-stop {
  width: 100%; padding: 13px 8px;
  background: rgba(255,51,102,0.1); border: 1px solid var(--neon-red); border-radius: 4px;
  color: var(--neon-red); font-family: 'Courier New', Courier, monospace;
  font-size: 10px; letter-spacing: 2px; cursor: pointer;
  display: flex; align-items: center; justify-content: center; gap: 8px;
  box-shadow: 0 0 12px rgba(255,51,102,0.15);
  transition: all 0.2s;
}
.btn-stop:hover { background: rgba(255,51,102,0.2); box-shadow: 0 0 22px rgba(255,51,102,0.35); }
.btn-stop__icon { font-size: 13px; }

/* Metrics */
.metric-block { margin-bottom: 14px; }
.metric-label { font-size: 9px; letter-spacing: 2px; color: var(--text-dim); margin-bottom: 4px; }
.metric-value { font-size: 26px; font-weight: 700; line-height: 1; margin-bottom: 6px; }
.metric-unit  { font-size: 11px; margin-left: 3px; font-weight: 400; opacity: 0.7; }
.metric--ok   { color: var(--neon-green); text-shadow: 0 0 12px rgba(0,255,136,0.5); }
.metric--warn { color: var(--neon-red);   text-shadow: 0 0 12px rgba(255,51,102,0.5); }
.metric--cyan { color: var(--neon-cyan);  text-shadow: 0 0 12px rgba(0,204,255,0.5); }
.metric-bar   { height: 3px; background: rgba(255,255,255,0.06); border-radius: 2px; overflow: hidden; }
.metric-bar__fill { height: 100%; border-radius: 2px; transition: width 0.4s ease; }
.metric-bar__fill.metric--ok   { background: var(--neon-green); }
.metric-bar__fill.metric--warn { background: var(--neon-red); }
.throttle-badge { margin-top: 4px; font-size: 9px; color: var(--neon-yellow); letter-spacing: 1px; }

/* Network */
.ws-url { font-size: 10px; color: var(--text-accent); letter-spacing: 1px; margin-bottom: 10px; }
.ctrl-actions { display: flex; gap: 6px; }
.btn { flex: 1; padding: 7px 4px; border-radius: 4px; font-family: 'Courier New', Courier, monospace; font-size: 9px; letter-spacing: 1px; cursor: pointer; border: 1px solid; transition: all 0.2s; }
.btn:disabled { opacity: 0.35; cursor: not-allowed; }
.btn--primary { background: rgba(0,255,136,0.08); border-color: var(--neon-green); color: var(--neon-green); }
.btn--primary:hover:not(:disabled) { background: rgba(0,255,136,0.18); box-shadow: 0 0 8px rgba(0,255,136,0.3); }
.btn--danger  { background: rgba(255,51,102,0.08); border-color: var(--neon-red); color: var(--neon-red); }
.btn--danger:hover:not(:disabled)  { background: rgba(255,51,102,0.18); }

/* ── Viewport ────────────────────────────────────────────────────────────── */
.viewport { flex: 1; position: relative; background: #07091a; overflow: hidden; }

.hidden-video { position: absolute; width: 1px; height: 1px; opacity: 0; pointer-events: none; }
.main-canvas  { display: block; width: 100%; height: 100%; }

/* Canvas overlays */
.viewport-overlay {
  position: absolute; inset: 0;
  display: flex; align-items: flex-end; justify-content: flex-start;
  padding: 20px 24px;
  pointer-events: none;
}
.viewport-overlay--ready    { background: transparent; }
.viewport-overlay--finished { background: transparent; }

.overlay-content {
  display: flex; align-items: center; gap: 12px;
  background: rgba(0,0,0,0.7); border: 1px solid;
  border-radius: 4px; padding: 10px 16px;
  backdrop-filter: blur(2px);
}
.viewport-overlay--ready    .overlay-content { border-color: rgba(0,255,136,0.4); }
.viewport-overlay--finished .overlay-content { border-color: rgba(0,204,255,0.4); }

.overlay-icon {
  font-size: 18px;
}
.viewport-overlay--ready    .overlay-icon { color: var(--neon-green); }
.viewport-overlay--finished .overlay-icon { color: var(--neon-cyan); }

.overlay-title {
  font-size: 11px; font-weight: 700; letter-spacing: 3px;
}
.viewport-overlay--ready    .overlay-title { color: var(--neon-green); }
.viewport-overlay--finished .overlay-title { color: var(--neon-cyan); }

.overlay-sub {
  font-size: 10px; color: var(--text-dim); letter-spacing: 1px; margin-left: 2px;
}

/* Detection badge */
.det-badge {
  position: absolute; top: 14px; right: 16px;
  background: rgba(0,0,0,0.7); border: 1px solid var(--neon-green); color: var(--neon-green);
  font-size: 10px; letter-spacing: 2px; padding: 4px 10px; border-radius: 2px;
  box-shadow: 0 0 10px rgba(0,255,136,0.2);
}

/* ── Utility ─────────────────────────────────────────────────────────────── */
.hidden { display: none; }

/* ── Transitions ─────────────────────────────────────────────────────────── */
.banner-enter-active, .banner-leave-active { transition: opacity 0.3s, transform 0.3s; }
.banner-enter-from, .banner-leave-to { opacity: 0; transform: translateY(-6px); }
.fade-enter-active, .fade-leave-active { transition: opacity 0.4s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
