<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import type { HistoryRecord } from '@/api/history'
import { listHistory, deleteHistory, getVideoUrl, getDataUrl } from '@/api/history'

// ── State ──────────────────────────────────────────────────────────────────────
const router = useRouter()
const records = ref<HistoryRecord[]>([])
const isLoading = ref(true)
const errorMsg  = ref('')

// ── Lifecycle ──────────────────────────────────────────────────────────────────
onMounted(async () => {
  try {
    const res = await listHistory({ limit: 100 })
    records.value = res.items
  } catch (e: unknown) {
    errorMsg.value = e instanceof Error ? e.message : '加载失败'
  } finally {
    isLoading.value = false
  }
})

// ── Refresh ────────────────────────────────────────────────────────────────────
async function refresh() {
  isLoading.value = true
  errorMsg.value = ''
  try {
    const res = await listHistory({ limit: 100 })
    records.value = res.items
  } catch (e: unknown) {
    errorMsg.value = e instanceof Error ? e.message : '加载失败'
  } finally {
    isLoading.value = false
  }
}

// ── Delete ────────────────────────────────────────────────────────────────────
async function onDelete(id: number) {
  try {
    await deleteHistory(id)
    records.value = records.value.filter(r => r.id !== id)
  } catch (e: unknown) {
    errorMsg.value = e instanceof Error ? e.message : '删除失败'
  }
}

// ── Video Preview Modal ────────────────────────────────────────────────────────
const previewVideo = ref<HistoryRecord | null>(null)
const videoUrl = ref('')

function openPreview(record: HistoryRecord) {
  previewVideo.value = record
  videoUrl.value = getVideoUrl(record.id)
}

function closePreview() {
  previewVideo.value = null
  videoUrl.value = ''
}

// ── View Data Detail ───────────────────────────────────────────────────────────
function viewData(record: HistoryRecord) {
  router.push({ name: 'history-detail', params: { id: record.id } })
}

// ── Download Video ─────────────────────────────────────────────────────────────
function downloadVideo(record: HistoryRecord) {
  if (!record.video_path) {
    errorMsg.value = '该记录没有关联的视频文件'
    return
  }
  const url = getVideoUrl(record.id)
  const a = document.createElement('a')
  a.href = url
  a.download = record.video_name
  a.click()
}

// ── Download JSON Data ─────────────────────────────────────────────────────────
function downloadData(record: HistoryRecord) {
  const url = getDataUrl(record.id)
  const a = document.createElement('a')
  a.href = url
  a.download = `detection_${record.id}_${record.video_name}.json`
  a.click()
}

// ── Helpers ────────────────────────────────────────────────────────────────────
const totalCount = computed(() => records.value.length)

const classColorMap: Record<string, string> = {
  car:        'bg-yellow-500/15 text-yellow-400 border-yellow-500/30',
  person:     'bg-red-500/15    text-red-400    border-red-500/30',
  truck:      'bg-orange-500/15 text-orange-400 border-orange-500/30',
  drone:      'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
  motorcycle: 'bg-purple-500/15 text-purple-400 border-purple-500/30',
  bicycle:    'bg-blue-500/15   text-blue-400   border-blue-500/30',
}

function classStyle(cls: string) {
  return classColorMap[cls] ?? 'bg-slate-700/40 text-slate-300 border-slate-600/40'
}

function formatDuration(seconds: number) {
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}

function formatTime(iso: string) {
  return iso.replace('T', '  ').substring(0, 19)
}

function shortModel(name: string) {
  const noChinese = name.replace(/[\u4e00-\u9fa5]+/g, '').replace(/[（(].*?[)）]/g, '').trim()
  return noChinese.replace('YOLO-World-V2', 'WV2').replace('YOLOv8-Base', 'v8n')
}

function shortModelConfig(modelConfig: { display_name?: string; model_id?: string } | null) {
  if (!modelConfig) return '未知'
  const name = modelConfig.display_name || modelConfig.model_id || '未知'
  return shortModel(name)
}

function statusConfig(status: string) {
  if (status === 'completed') return 'bg-emerald-500/10 border-emerald-500/25 text-emerald-400'
  if (status === 'failed')    return 'bg-red-500/10    border-red-500/25    text-red-400'
  return 'bg-slate-700/40     border-slate-600/40 text-slate-400'
}
</script>

<template>
  <div class="h-full bg-slate-950 flex flex-col overflow-hidden">

    <!-- Page header -->
    <div class="px-8 py-6 flex-shrink-0 border-b border-slate-800">
      <div class="flex items-center justify-between">
        <div>
          <h2 class="text-lg font-semibold text-white">历史记录库</h2>
          <p class="text-sm text-slate-500 mt-0.5">
            过往分析任务的完整档案
            <template v-if="!isLoading">· {{ totalCount }} 条记录</template>
          </p>
        </div>
        <button
          class="flex items-center gap-2 px-4 py-2 rounded-lg bg-slate-800 border border-slate-700
                 text-slate-400 text-sm hover:border-blue-600 hover:text-blue-400 transition-all"
          :disabled="isLoading"
          @click="refresh"
        >
          <svg
            width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
            :class="isLoading ? 'animate-spin' : ''"
          >
            <path d="M23 4v6h-6"/><path d="M1 20v-6h6"/>
            <path d="M3.51 9a9 9 0 0114.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0020.49 15"/>
          </svg>
          刷新
        </button>
      </div>
    </div>

    <!-- Error banner -->
    <div
      v-if="errorMsg"
      class="mx-8 mt-4 px-4 py-3 rounded-lg bg-red-950/70 border border-red-700/60 text-red-300 text-sm"
    >
      {{ errorMsg }}
      <button class="ml-4 underline hover:no-underline" @click="errorMsg = ''">关闭</button>
    </div>

    <!-- Table area -->
    <div class="flex-1 overflow-auto px-8 py-5">

      <!-- Loading skeleton -->
      <div v-if="isLoading" class="space-y-3">
        <div v-for="i in 5" :key="i" class="h-16 rounded-xl bg-slate-900/60 animate-pulse"></div>
      </div>

      <!-- Table (only when not loading) -->
      <template v-else>

        <!-- Table header -->
        <div class="rounded-xl border border-slate-800 overflow-hidden bg-slate-900/50">
          <div class="grid grid-cols-[56px_1fr_120px_180px_100px_100px_180px] gap-0
                      px-5 py-3 border-b border-slate-800 bg-slate-900">
            <div class="text-xs font-medium text-slate-500 tracking-wider uppercase">#</div>
            <div class="text-xs font-medium text-slate-500 tracking-wider uppercase">任务信息</div>
            <div class="text-xs font-medium text-slate-500 tracking-wider uppercase">模型</div>
            <div class="text-xs font-medium text-slate-500 tracking-wider uppercase">检测类别</div>
            <div class="text-xs font-medium text-slate-500 tracking-wider uppercase">目标数</div>
            <div class="text-xs font-medium text-slate-500 tracking-wider uppercase">状态</div>
            <div class="text-xs font-medium text-slate-500 tracking-wider uppercase text-right">操作</div>
          </div>

          <!-- Rows -->
          <div
            v-for="(rec, index) in records"
            :key="rec.id"
            class="grid grid-cols-[56px_1fr_120px_180px_100px_100px_180px] gap-0
                   px-5 py-4 items-center transition-colors hover:bg-slate-800/40"
            :class="index < records.length - 1 ? 'border-b border-slate-800/60' : ''"
          >
            <!-- Index -->
            <div class="flex items-center">
              <div class="w-10 h-8 rounded-md bg-slate-800 border border-slate-700 flex items-center justify-center
                          text-slate-600 text-xs font-mono">
                {{ rec.id.toString().padStart(2, '0') }}
              </div>
            </div>

            <!-- Task info -->
            <div>
              <div class="text-sm text-slate-200 font-medium">分析任务 #{{ rec.id.toString().padStart(4, '0') }}</div>
              <div class="text-xs text-slate-500 mt-0.5 font-mono">
                {{ formatTime(rec.created_at) }}
                <span class="ml-2 text-slate-600">时长 {{ formatDuration(rec.duration) }}</span>
              </div>
            </div>

            <!-- Model -->
            <div>
              <span class="text-xs px-2 py-0.5 rounded-md bg-blue-500/10 border border-blue-500/20 text-blue-400 font-mono">
                {{ shortModelConfig(rec.detection_model) }}
              </span>
            </div>

            <!-- Classes -->
            <div class="flex flex-wrap gap-1">
              <span
                v-for="cls in Object.keys(rec.class_counts)"
                :key="cls"
                class="text-xs px-2 py-0.5 rounded-full border font-mono"
                :class="classStyle(cls)"
              >
                {{ cls }}
                <span class="opacity-60">×{{ rec.class_counts[cls] }}</span>
              </span>
            </div>

            <!-- Detection count -->
            <div class="text-sm font-bold font-mono text-slate-200">
              {{ rec.total_detections }}
              <span class="text-xs text-slate-600 font-normal">个</span>
            </div>

            <!-- Status -->
            <div>
              <span
                class="inline-flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full border"
                :class="statusConfig(rec.status)"
              >
                <span class="w-1.5 h-1.5 rounded-full bg-current"></span>
                {{ rec.status === 'completed' ? '已完成' : rec.status }}
              </span>
            </div>

            <!-- Actions -->
            <div class="flex items-center justify-end gap-1.5">
              <!-- View data button -->
              <button
                class="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium
                       bg-slate-800 border border-slate-700 text-slate-300
                       hover:border-blue-600 hover:text-blue-400 transition-all duration-150"
                title="查看数据详情"
                @click="viewData(rec)"
              >
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/>
                  <polyline points="14,2 14,8 20,8"/>
                  <line x1="16" y1="13" x2="8" y2="13"/>
                  <line x1="16" y1="17" x2="8" y2="17"/>
                  <polyline points="10,9 9,9 8,9"/>
                </svg>
                数据
              </button>

              <!-- Download JSON button -->
              <button
                class="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium
                       bg-slate-800 border border-slate-700 text-slate-300
                       hover:border-purple-600 hover:text-purple-400 transition-all duration-150"
                title="下载JSON数据"
                @click="downloadData(rec)"
              >
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/>
                  <polyline points="7,10 12,15 17,10"/>
                  <line x1="12" y1="15" x2="12" y2="3"/>
                </svg>
                JSON
              </button>

              <!-- Download video button -->
              <button
                v-if="rec.video_path"
                class="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium
                       bg-slate-800 border border-slate-700 text-slate-300
                       hover:border-emerald-600 hover:text-emerald-400 transition-all duration-150"
                title="下载视频"
                @click="downloadVideo(rec)"
              >
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <polygon points="5,3 19,12 5,21 5,3"/>
                </svg>
                视频
              </button>

              <!-- Preview button -->
              <button
                v-if="rec.video_path"
                class="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium
                       bg-slate-800 border border-slate-700 text-slate-300
                       hover:border-cyan-600 hover:text-cyan-400 transition-all duration-150"
                title="在线预览"
                @click="openPreview(rec)"
              >
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <rect x="2" y="3" width="20" height="14" rx="2" ry="2"/>
                  <line x1="8" y1="21" x2="16" y2="21"/>
                  <line x1="12" y1="17" x2="12" y2="21"/>
                </svg>
                播放
              </button>

              <!-- Delete button -->
              <button
                class="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium
                       bg-slate-800 border border-slate-700 text-slate-300
                       hover:border-red-600 hover:text-red-400 transition-all duration-150"
                @click="onDelete(rec.id)"
              >
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <polyline points="3,6 5,6 21,6"/>
                  <path d="M19 6l-1 14H6L5 6"/>
                  <path d="M10 11v6M14 11v6"/>
                  <path d="M9 6V4h6v2"/>
                </svg>
                删除
              </button>
            </div>
          </div>
        </div>

        <!-- Empty state -->
        <div
          v-if="records.length === 0 && !errorMsg"
          class="flex flex-col items-center justify-center py-20 text-slate-600"
        >
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1">
            <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/>
            <polyline points="14,2 14,8 20,8"/>
          </svg>
          <p class="mt-3 text-sm">暂无历史记录</p>
          <p class="text-xs text-slate-700 mt-1">完成一次视频分析后，记录将自动保存到这里</p>
        </div>

      </template>
    </div>

    <!-- Video Preview Modal -->
    <Teleport to="body">
      <Transition name="modal">
        <div
          v-if="previewVideo"
          class="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm"
          @click.self="closePreview"
        >
          <div class="relative w-full max-w-4xl mx-4 bg-slate-900 rounded-2xl border border-slate-700 shadow-2xl overflow-hidden">
            <!-- Modal header -->
            <div class="flex items-center justify-between px-5 py-4 border-b border-slate-800">
              <div>
                <h3 class="text-white font-medium">{{ previewVideo.video_name }}</h3>
                <p class="text-xs text-slate-500 mt-0.5">
                  分析任务 #{{ previewVideo.id.toString().padStart(4, '0') }} · {{ formatDuration(previewVideo.duration) }}
                </p>
              </div>
              <button
                class="p-2 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white transition-colors"
                @click="closePreview"
              >
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <line x1="18" y1="6" x2="6" y2="18"/>
                  <line x1="6" y1="6" x2="18" y2="18"/>
                </svg>
              </button>
            </div>

            <!-- Video player -->
            <div class="aspect-video bg-black flex items-center justify-center">
              <video
                :src="videoUrl"
                controls
                autoplay
                class="w-full h-full object-contain"
              >
                您的浏览器不支持视频播放
              </video>
            </div>

            <!-- Modal footer with stats -->
            <div class="px-5 py-4 border-t border-slate-800 flex items-center justify-between">
              <div class="flex items-center gap-4">
                <span class="text-xs text-slate-500">
                  检测目标: <span class="text-slate-300">{{ previewVideo.total_detections }} 个</span>
                </span>
                <span class="text-xs text-slate-500">
                  模型: <span class="text-blue-400">{{ shortModelConfig(previewVideo.detection_model) }}</span>
                </span>
              </div>
              <button
                class="flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium
                       bg-emerald-600/20 border border-emerald-600/40 text-emerald-400
                       hover:bg-emerald-600/30 transition-all"
                @click="downloadVideo(previewVideo)"
              >
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/>
                  <polyline points="7,10 12,15 17,10"/>
                  <line x1="12" y1="15" x2="12" y2="3"/>
                </svg>
                下载视频
              </button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>

  </div>
</template>

<style scoped>
/* Modal animation */
.modal-enter-active,
.modal-leave-active {
  transition: all 0.25s ease;
}
.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}
.modal-enter-from > div,
.modal-leave-to > div {
  transform: scale(0.95);
}
</style>
