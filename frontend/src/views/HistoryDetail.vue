<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getHistory, getDataUrl, type HistoryRecord } from '@/api/history'

// ── Route & Navigation ─────────────────────────────────────────────────────────
const route = useRoute()
const router = useRouter()
const recordId = computed(() => Number(route.params.id))

// ── State ──────────────────────────────────────────────────────────────────────
const record = ref<HistoryRecord | null>(null)
const isLoading = ref(true)
const errorMsg = ref('')

// ── Fetch Data ─────────────────────────────────────────────────────────────────
onMounted(async () => {
  try {
    record.value = await getHistory(recordId.value)
  } catch (e: unknown) {
    errorMsg.value = e instanceof Error ? e.message : '加载失败'
  } finally {
    isLoading.value = false
  }
})

// ── Download JSON ──────────────────────────────────────────────────────────────
function downloadData() {
  if (!record.value) return
  const url = getDataUrl(record.value.id)
  const a = document.createElement('a')
  a.href = url
  a.download = `detection_${record.value.id}_${record.value.video_name}.json`
  a.click()
}

// ── Download Video ─────────────────────────────────────────────────────────────
function downloadVideo() {
  if (!record.value?.video_path) return
  const url = getDataUrl(record.value.id).replace('/data', '/video')
  const a = document.createElement('a')
  a.href = url
  a.download = record.value.video_name
  a.click()
}

// ── Back ────────────────────────────────────────────────────────────────────────
function goBack() {
  router.push({ name: 'history' })
}

// ── Helpers ────────────────────────────────────────────────────────────────────
function formatDuration(seconds: number) {
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}

function formatTime(iso: string) {
  return iso.replace('T', '  ').substring(0, 19)
}

function formatDate(iso: string) {
  const d = new Date(iso)
  return d.toLocaleDateString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

// ── Class Colors ────────────────────────────────────────────────────────────────
const classColorMap: Record<string, { bg: string; text: string; border: string; bar: string }> = {
  car:        { bg: 'bg-yellow-500/15', text: 'text-yellow-400', border: 'border-yellow-500/30', bar: 'bg-yellow-500' },
  person:     { bg: 'bg-red-500/15',    text: 'text-red-400',    border: 'border-red-500/30',    bar: 'bg-red-500' },
  truck:      { bg: 'bg-orange-500/15', text: 'text-orange-400', border: 'border-orange-500/30', bar: 'bg-orange-500' },
  drone:      { bg: 'bg-emerald-500/15', text: 'text-emerald-400', border: 'border-emerald-500/30', bar: 'bg-emerald-500' },
  motorcycle: { bg: 'bg-purple-500/15', text: 'text-purple-400', border: 'border-purple-500/30', bar: 'bg-purple-500' },
  bicycle:    { bg: 'bg-blue-500/15',   text: 'text-blue-400',   border: 'border-blue-500/30',   bar: 'bg-blue-500' },
}

function getClassStyle(cls: string) {
  return classColorMap[cls] ?? { bg: 'bg-slate-700/40', text: 'text-slate-300', border: 'border-slate-600/40', bar: 'bg-slate-500' }
}

// ── Class Statistics ────────────────────────────────────────────────────────────
const sortedClasses = computed(() => {
  if (!record.value?.class_counts) return []
  return Object.entries(record.value.class_counts)
    .sort(([, a], [, b]) => (b as number) - (a as number))
})

const maxCount = computed(() => {
  const counts = Object.values(record.value?.class_counts ?? {})
  return Math.max(...counts as number[], 1)
})
</script>

<template>
  <div class="h-full bg-slate-950 flex flex-col overflow-hidden">

    <!-- Page header -->
    <div class="px-8 py-6 flex-shrink-0 border-b border-slate-800">
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-4">
          <button
            class="p-2 rounded-lg bg-slate-800 border border-slate-700 text-slate-400
                   hover:text-white hover:border-slate-600 transition-all"
            @click="goBack"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M19 12H5M12 19l-7-7 7-7"/>
            </svg>
          </button>
          <div>
            <h2 class="text-lg font-semibold text-white">数据详情</h2>
            <p class="text-sm text-slate-500 mt-0.5">
              分析任务 #{{ record?.id?.toString().padStart(4, '0') ?? '----' }}
            </p>
          </div>
        </div>

        <!-- Action buttons -->
        <div class="flex items-center gap-2">
          <button
            class="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium
                   bg-purple-600/20 border border-purple-600/40 text-purple-400
                   hover:bg-purple-600/30 transition-all"
            @click="downloadData"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/>
              <polyline points="7,10 12,15 17,10"/>
              <line x1="12" y1="15" x2="12" y2="3"/>
            </svg>
            下载 JSON
          </button>

          <button
            v-if="record?.video_path"
            class="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium
                   bg-emerald-600/20 border border-emerald-600/40 text-emerald-400
                   hover:bg-emerald-600/30 transition-all"
            @click="downloadVideo"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/>
              <polyline points="7,10 12,15 17,10"/>
              <line x1="12" y1="15" x2="12" y2="3"/>
            </svg>
            下载视频
          </button>
        </div>
      </div>
    </div>

    <!-- Error banner -->
    <div
      v-if="errorMsg"
      class="mx-8 mt-4 px-4 py-3 rounded-lg bg-red-950/70 border border-red-700/60 text-red-300 text-sm"
    >
      {{ errorMsg }}
    </div>

    <!-- Loading state -->
    <div v-if="isLoading" class="flex-1 flex items-center justify-center">
      <div class="flex flex-col items-center gap-4">
        <div class="w-10 h-10 border-2 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
        <p class="text-slate-500">加载中...</p>
      </div>
    </div>

    <!-- Content -->
    <div v-else-if="record" class="flex-1 overflow-y-auto px-8 py-6 space-y-6">

      <!-- Overview Cards -->
      <div class="grid grid-cols-4 gap-4">
        <!-- Video Info -->
        <div class="bg-slate-900 rounded-xl border border-slate-800 p-5">
          <div class="flex items-center gap-3 mb-3">
            <div class="p-2 rounded-lg bg-blue-500/15">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="text-blue-400">
                <polygon points="5,3 19,12 5,21 5,3"/>
              </svg>
            </div>
            <span class="text-xs text-slate-500 uppercase tracking-wider">视频信息</span>
          </div>
          <p class="text-white font-medium text-sm truncate" :title="record.video_name">{{ record.video_name }}</p>
          <p class="text-slate-400 text-xs mt-1">
            时长 {{ formatDuration(record.duration) }}
          </p>
        </div>

        <!-- Model Info -->
        <div class="bg-slate-900 rounded-xl border border-slate-800 p-5">
          <div class="flex items-center gap-3 mb-3">
            <div class="p-2 rounded-lg bg-purple-500/15">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="text-purple-400">
                <rect x="2" y="3" width="20" height="14" rx="2" ry="2"/>
                <line x1="8" y1="21" x2="16" y2="21"/>
                <line x1="12" y1="17" x2="12" y2="21"/>
              </svg>
            </div>
            <span class="text-xs text-slate-500 uppercase tracking-wider">分析模型</span>
          </div>
          <p class="text-white font-medium text-sm">{{ record.model_name }}</p>
        </div>

        <!-- Total Detections -->
        <div class="bg-slate-900 rounded-xl border border-slate-800 p-5">
          <div class="flex items-center gap-3 mb-3">
            <div class="p-2 rounded-lg bg-emerald-500/15">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="text-emerald-400">
                <circle cx="12" cy="12" r="10"/>
                <circle cx="12" cy="12" r="3"/>
              </svg>
            </div>
            <span class="text-xs text-slate-500 uppercase tracking-wider">总检测数</span>
          </div>
          <p class="text-white font-bold text-2xl font-mono">{{ record.total_detections }}</p>
          <p class="text-slate-400 text-xs mt-1">个目标对象</p>
        </div>

        <!-- Time -->
        <div class="bg-slate-900 rounded-xl border border-slate-800 p-5">
          <div class="flex items-center gap-3 mb-3">
            <div class="p-2 rounded-lg bg-amber-500/15">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="text-amber-400">
                <circle cx="12" cy="12" r="10"/>
                <polyline points="12,6 12,12 16,14"/>
              </svg>
            </div>
            <span class="text-xs text-slate-500 uppercase tracking-wider">分析时间</span>
          </div>
          <p class="text-white font-medium text-sm">{{ formatDate(record.created_at) }}</p>
        </div>
      </div>

      <!-- Detection Classes Chart -->
      <div class="bg-slate-900 rounded-xl border border-slate-800 p-5">
        <h3 class="text-white font-semibold mb-4">检测类别统计</h3>
        <div class="space-y-3">
          <div
            v-for="[cls, count] in sortedClasses"
            :key="cls"
            class="flex items-center gap-4"
          >
            <span
              class="px-3 py-1 rounded-lg border text-sm font-mono min-w-[100px] text-center"
              :class="[getClassStyle(cls as string).bg, getClassStyle(cls as string).text, getClassStyle(cls as string).border]"
            >
              {{ cls }}
            </span>
            <div class="flex-1 h-8 bg-slate-800 rounded-lg overflow-hidden relative">
              <div
                class="h-full rounded-lg transition-all duration-500"
                :class="getClassStyle(cls as string).bar"
                :style="{ width: `${((count as number) / maxCount) * 100}%` }"
              ></div>
            </div>
            <span class="text-white font-mono font-bold min-w-[60px] text-right">
              {{ count }}
              <span class="text-slate-500 font-normal text-xs ml-1">次</span>
            </span>
          </div>

          <div v-if="sortedClasses.length === 0" class="text-center py-8 text-slate-500">
            暂无检测数据
          </div>
        </div>
      </div>

      <!-- JSON Data Preview -->
      <div class="bg-slate-900 rounded-xl border border-slate-800 p-5">
        <div class="flex items-center justify-between mb-4">
          <h3 class="text-white font-semibold">JSON 数据预览</h3>
          <button
            class="flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium
                   bg-slate-800 border border-slate-700 text-slate-400
                   hover:border-purple-600 hover:text-purple-400 transition-all"
            @click="downloadData"
          >
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/>
              <polyline points="7,10 12,15 17,10"/>
              <line x1="12" y1="15" x2="12" y2="3"/>
            </svg>
            下载完整 JSON
          </button>
        </div>

        <div class="bg-slate-950 rounded-lg p-4 font-mono text-xs overflow-x-auto max-h-80 overflow-y-auto">
          <pre class="text-slate-400 whitespace-pre-wrap">{{ JSON.stringify({
  record_id: record.id,
  created_at: record.created_at,
  video_info: {
    name: record.video_name,
    path: record.video_path,
    duration_seconds: record.duration,
  },
  model_info: {
    name: record.model_name,
  },
  statistics: {
    total_detections: record.total_detections,
    class_counts: record.class_counts,
  },
  metadata: record.metadata,
}, null, 2) }}</pre>
        </div>
      </div>

      <!-- Data Structure Explanation -->
      <div class="bg-slate-900 rounded-xl border border-slate-800 p-5">
        <h3 class="text-white font-semibold mb-4">数据结构说明</h3>
        <div class="grid grid-cols-2 gap-4 text-sm">
          <div class="space-y-3">
            <div class="bg-slate-800/50 rounded-lg p-3">
              <div class="text-blue-400 font-mono">record_id</div>
              <div class="text-slate-500 text-xs mt-1">记录唯一标识符</div>
            </div>
            <div class="bg-slate-800/50 rounded-lg p-3">
              <div class="text-blue-400 font-mono">created_at</div>
              <div class="text-slate-500 text-xs mt-1">记录创建时间（ISO 8601格式）</div>
            </div>
            <div class="bg-slate-800/50 rounded-lg p-3">
              <div class="text-emerald-400 font-mono">video_info</div>
              <div class="text-slate-500 text-xs mt-1">视频文件信息（名称、路径、时长）</div>
            </div>
            <div class="bg-slate-800/50 rounded-lg p-3">
              <div class="text-purple-400 font-mono">model_info</div>
              <div class="text-slate-500 text-xs mt-1">使用的AI模型名称</div>
            </div>
          </div>
          <div class="space-y-3">
            <div class="bg-slate-800/50 rounded-lg p-3">
              <div class="text-amber-400 font-mono">statistics</div>
              <div class="text-slate-500 text-xs mt-1">统计信息：总检测数和各类别检测次数</div>
            </div>
            <div class="bg-slate-800/50 rounded-lg p-3">
              <div class="text-cyan-400 font-mono">class_counts</div>
              <div class="text-slate-500 text-xs mt-1">对象类别到检测次数的映射</div>
            </div>
            <div class="bg-slate-800/50 rounded-lg p-3">
              <div class="text-pink-400 font-mono">metadata</div>
              <div class="text-slate-500 text-xs mt-1">额外元数据（视频分辨率、FPS等）</div>
            </div>
          </div>
        </div>
      </div>

    </div>

    <!-- Empty state -->
    <div v-else class="flex-1 flex items-center justify-center">
      <div class="text-center text-slate-500">
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1" class="mx-auto">
          <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/>
          <polyline points="14,2 14,8 20,8"/>
        </svg>
        <p class="mt-3">记录不存在</p>
        <button
          class="mt-4 px-4 py-2 rounded-lg bg-slate-800 border border-slate-700 text-slate-400
                 hover:text-white hover:border-slate-600 transition-all"
          @click="goBack"
        >
          返回列表
        </button>
      </div>
    </div>

  </div>
</template>
