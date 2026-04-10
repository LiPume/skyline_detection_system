<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getHistory, getDataUrl, type HistoryRecord } from '@/api/history'
import type { ExtraData } from '@/types/skyline'

// ── Route & Navigation ─────────────────────────────────────────────────────────
const route = useRoute()
const router = useRouter()
const recordId = computed(() => Number(route.params.id))

// ── State ──────────────────────────────────────────────────────────────────────
const record = ref<HistoryRecord | null>(null)
const isLoading = ref(true)
const errorMsg = ref('')
const jsonCollapsed = ref(false)

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
function formatDuration(seconds: number): string {
  if (!seconds || seconds <= 0) return '--:--'
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}

function formatDate(iso: string): string {
  if (!iso) return '—'
  const d = new Date(iso)
  return d.toLocaleDateString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

// ── Class Colors (shared with History.vue palette) ──────────────────────────────
const classColorMap: Record<string, { bg: string; text: string; border: string; bar: string }> = {
  car:        { bg: 'bg-yellow-500/15', text: 'text-yellow-400', border: 'border-yellow-500/30', bar: 'bg-yellow-500' },
  person:     { bg: 'bg-red-500/15',    text: 'text-red-400',    border: 'border-red-500/30',    bar: 'bg-red-500' },
  truck:      { bg: 'bg-orange-500/15', text: 'text-orange-400', border: 'border-orange-500/30', bar: 'bg-orange-500' },
  drone:      { bg: 'bg-emerald-500/15', text: 'text-emerald-400', border: 'border-emerald-500/30', bar: 'bg-emerald-500' },
  motorcycle: { bg: 'bg-purple-500/15', text: 'text-purple-400', border: 'border-purple-500/30', bar: 'bg-purple-500' },
  bicycle:    { bg: 'bg-blue-500/15',   text: 'text-blue-400',   border: 'border-blue-500/30',   bar: 'bg-blue-500' },
  bus:        { bg: 'bg-cyan-500/15',   text: 'text-cyan-400',   border: 'border-cyan-500/30',    bar: 'bg-cyan-500' },
  van:        { bg: 'bg-amber-500/15',  text: 'text-amber-400',  border: 'border-amber-500/30',   bar: 'bg-amber-500' },
  boat:       { bg: 'bg-sky-500/15',    text: 'text-sky-400',    border: 'border-sky-500/30',     bar: 'bg-sky-500' },
  pedestrian: { bg: 'bg-pink-500/15',   text: 'text-pink-400',   border: 'border-pink-500/30',    bar: 'bg-pink-500' },
}

function getClassStyle(cls: string) {
  return classColorMap[cls] ?? { bg: 'bg-slate-700/40', text: 'text-slate-300', border: 'border-slate-600/40', bar: 'bg-slate-500' }
}

// ── Derived Computations ───────────────────────────────────────────────────────

/**
 * 口径说明：
 * 当前所有 "检测数" 均为检测事件累计次数，即逐帧检测框的数量，
 * 不是去重后的独立目标数量。派生指标口径均以此为前提。
 */

// 1. 主导类别（次数最大的类别）
const dominantClass = computed<string | null>(() => {
  const counts = record.value?.class_counts
  if (!counts || Object.keys(counts).length === 0) return null
  const entries = Object.entries(counts).sort(([, a], [, b]) => (b as number) - (a as number))
  return entries[0]?.[0] ?? null
})

// 2. 主导类别次数
const dominantClassCount = computed<number>(() => {
  const cls = dominantClass.value
  if (!cls || !record.value?.class_counts) return 0
  return record.value.class_counts[cls] ?? 0
})

// 3. 主导类别占总检测次数比例（0-1）
const dominantClassShare = computed<number>(() => {
  const total = record.value?.total_detections
  if (!total || total === 0) return 0
  return dominantClassCount.value / total
})

// 4. 实际检测到的类别数量（去零）
const detectedClassCount = computed<number>(() => {
  const counts = record.value?.class_counts
  if (!counts) return 0
  return Object.values(counts).filter(v => (v as number) > 0).length
})

// 5. 配置的类别数量（取决于检测模式）
const configuredClassCount = computed<number>(() => {
  const model = record.value?.detection_model
  if (!model) return 0
  if (model.model_type === 'open_vocab') {
    return model.prompt_classes?.length ?? 0
  }
  return model.selected_classes?.length ?? 0
})

// 6. 平均每秒检测事件数（检测事件频率）
// 注意：不是目标密度，是事件频率口径
const detectionEventsPerSecond = computed<number>(() => {
  const total = record.value?.total_detections
  const duration = record.value?.duration
  if (!total || !duration || duration <= 0) return 0
  return total / duration
})

// 7. 检测模式标签映射
const modelModeLabel = computed<string>(() => {
  const type = record.value?.detection_model?.model_type
  if (type === 'open_vocab') return '开放词汇检测'
  if (type === 'closed_set') return '固定类别检测'
  return '未知模式'
})

// 8. 排序后的类别列表（含次数、占比）
const sortedClasses = computed(() => {
  const counts = record.value?.class_counts
  const total = record.value?.total_detections
  if (!counts || Object.keys(counts).length === 0) return []
  return Object.entries(counts)
    .map(([cls, count]) => ({
      cls,
      count: count as number,
      // 该类别占总检测次数的比例（口径：检测事件次数占比，非独立目标占比）
      share: total && total > 0 ? ((count as number) / total) : 0,
    }))
    .sort((a, b) => b.count - a.count)
})

// 9. 最大次数（用于条形图宽度归一化）
const maxCount = computed<number>(() => {
  const counts = record.value?.class_counts
  if (!counts) return 1
  const values = Object.values(counts) as number[]
  return Math.max(...values, 1)
})

// 10. 任务结论摘要（自然语言）
const taskSummary = computed<string>(() => {
  const r = record.value
  if (!r) return ''
  const modelName = r.detection_model?.display_name || r.detection_model?.model_id || '未知模型'
  const mode = modelModeLabel.value
  const dur = formatDuration(r.duration)
  const total = r.total_detections ?? 0
  const dc = dominantClass.value
  const dcc = detectedClassCount.value
  const ccc = configuredClassCount.value
  const freq = detectionEventsPerSecond.value > 0
    ? `${detectionEventsPerSecond.value.toFixed(2)} 次/秒`
    : '—'

  let parts: string[] = []
  parts.push(`使用 ${modelName} 模型进行${mode}`)
  parts.push(`对视频 "${r.video_name}" 完成了分析`)
  parts.push(`视频时长 ${dur}，共累计 ${total} 次检测事件`)
  if (dc) parts.push(`其中「${dc}」出现最多（${dominantClassCount.value} 次，占 ${(dominantClassShare.value * 100).toFixed(1)}%）`)
  parts.push(`本次任务配置了 ${ccc} 个类别目标，实际检测到 ${dcc} 个类别`)
  parts.push(`平均检测事件频率为 ${freq}`)
  return parts.join('，') + '。'
})

// 11. 配置类别列表（用于展示 prompt_classes 或 selected_classes）
const activeClassList = computed<string[]>(() => {
  const model = record.value?.detection_model
  if (!model) return []
  if (model.model_type === 'open_vocab') return model.prompt_classes ?? []
  return model.selected_classes ?? []
})

// 12. 状态配置样式
const statusConfig = computed(() => {
  const s = record.value?.status
  if (s === 'completed') return { cls: 'bg-emerald-500/10 border-emerald-500/25 text-emerald-400', label: '已完成' }
  if (s === 'failed') return { cls: 'bg-red-500/10 border-red-500/25 text-red-400', label: '失败' }
  if (s === 'cancelled') return { cls: 'bg-amber-500/10 border-amber-500/25 text-amber-400', label: '已取消' }
  return { cls: 'bg-slate-700/40 border-slate-600/40 text-slate-400', label: s ?? '未知' }
})

// 13. 当前配置模式标签
const modeTagConfig = computed(() => {
  const type = record.value?.detection_model?.model_type
  if (type === 'open_vocab') return { cls: 'bg-violet-500/15 border-violet-500/30 text-violet-400', label: '开放词汇' }
  if (type === 'closed_set') return { cls: 'bg-blue-500/15 border-blue-500/30 text-blue-400', label: '固定类别' }
  return { cls: 'bg-slate-700/40 border-slate-600/40 text-slate-400', label: '未知' }
})

// 14. extra_data 解析（来自 Detection 页保存的 AI 短报告与检测摘要）
const extraData = computed<ExtraData | null>(() => {
  const meta = record.value?.metadata
  if (!meta || typeof meta !== 'object') return null
  return meta as unknown as ExtraData
})

// 15. AI 短报告是否存在
const hasShortReport = computed<boolean>(() => {
  const text = extraData.value?.short_report
  return typeof text === 'string' && text.length > 0
})

// 16. AI 短报告文本
const shortReportText = computed<string>(() => {
  return extraData.value?.short_report ?? ''
})

// 17. detection_summary 是否存在
const hasDetectionSummary = computed<boolean>(() => {
  return extraData.value?.detection_summary != null
})
</script>

<template>
  <div class="h-full bg-slate-950 flex flex-col overflow-hidden">

    <!-- ══════════════════════════════════════════════════════════════════ -->
    <!-- 顶部操作栏                                                     -->
    <!-- ══════════════════════════════════════════════════════════════════ -->
    <div class="px-8 py-5 flex-shrink-0 border-b border-slate-800">
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
            <h2 class="text-lg font-semibold text-white">分析任务档案</h2>
            <p class="text-sm text-slate-500 mt-0.5">
              任务 #{{ record?.id?.toString().padStart(4, '0') ?? '----' }}
            </p>
          </div>
        </div>

        <!-- 操作按钮 -->
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

    <!-- 错误提示 -->
    <div
      v-if="errorMsg"
      class="mx-8 mt-4 px-4 py-3 rounded-lg bg-red-950/70 border border-red-700/60 text-red-300 text-sm"
    >
      {{ errorMsg }}
    </div>

    <!-- ══════════════════════════════════════════════════════════════════ -->
    <!-- 加载状态                                                     -->
    <!-- ══════════════════════════════════════════════════════════════════ -->
    <div v-if="isLoading" class="flex-1 flex items-center justify-center">
      <div class="flex flex-col items-center gap-4">
        <div class="w-10 h-10 border-2 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
        <p class="text-slate-500">加载中...</p>
      </div>
    </div>

    <!-- ══════════════════════════════════════════════════════════════════ -->
    <!-- 主内容区                                                     -->
    <!-- ══════════════════════════════════════════════════════════════════ -->
    <div v-else-if="record" class="flex-1 overflow-y-auto px-8 py-6 space-y-5">

      <!-- ──────────────────────────────────────────────────────────────── -->
      <!-- 第一屏：任务摘要卡片组                                        -->
      <!-- ──────────────────────────────────────────────────────────────── -->
      <div class="grid grid-cols-2 lg:grid-cols-4 gap-4">

        <!-- 视频信息 -->
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
          <p v-if="record.status" class="mt-2">
            <span
              class="inline-flex items-center gap-1.5 text-xs px-2 py-0.5 rounded-full border"
              :class="statusConfig.cls"
            >
              <span class="w-1.5 h-1.5 rounded-full bg-current"></span>
              {{ statusConfig.label }}
            </span>
          </p>
        </div>

        <!-- 模型信息 -->
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
          <p class="text-white font-medium text-sm">
            {{ record.detection_model?.display_name || record.detection_model?.model_id || '—' }}
          </p>
          <p class="text-slate-400 text-xs mt-1">{{ modelModeLabel }}</p>
          <p v-if="record.detection_model?.model_type" class="mt-2">
            <span
              class="inline-flex items-center text-xs px-2 py-0.5 rounded-full border"
              :class="modeTagConfig.cls"
            >
              {{ modeTagConfig.label }}
            </span>
          </p>
        </div>

        <!-- 总检测事件数 -->
        <div class="bg-slate-900 rounded-xl border border-slate-800 p-5">
          <div class="flex items-center gap-3 mb-3">
            <div class="p-2 rounded-lg bg-emerald-500/15">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="text-emerald-400">
                <circle cx="12" cy="12" r="10"/>
                <circle cx="12" cy="12" r="3"/>
              </svg>
            </div>
            <span class="text-xs text-slate-500 uppercase tracking-wider">总检测事件</span>
          </div>
          <p class="text-white font-bold text-2xl font-mono">{{ record.total_detections?.toLocaleString() ?? 0 }}</p>
          <p class="text-slate-400 text-xs mt-1">
            <span v-if="detectedClassCount > 0">覆盖 {{ detectedClassCount }} 个类别</span>
            <span v-else>暂无检测数据</span>
          </p>
        </div>

        <!-- 分析时间 -->
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
          <p v-if="record.video_path" class="text-slate-500 text-xs mt-1">含视频文件</p>
        </div>

      </div>

      <!-- ──────────────────────────────────────────────────────────────── -->
      <!-- 派生指标卡片行（更细粒度的数据洞察）                        -->
      <!-- ──────────────────────────────────────────────────────────────── -->
      <div class="grid grid-cols-2 lg:grid-cols-3 gap-4">

        <!-- 主导类别 -->
        <div v-if="dominantClass" class="bg-slate-900 rounded-xl border border-slate-800 p-5">
          <div class="flex items-center gap-3 mb-3">
            <div class="p-2 rounded-lg bg-rose-500/15">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="text-rose-400">
                <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/>
              </svg>
            </div>
            <span class="text-xs text-slate-500 uppercase tracking-wider">主导类别</span>
          </div>
          <p class="text-white font-semibold text-lg" :class="getClassStyle(dominantClass).text">
            {{ dominantClass }}
          </p>
          <p class="text-slate-400 text-xs mt-1">
            {{ dominantClassCount }} 次 · 占比 {{ (dominantClassShare * 100).toFixed(1) }}%
          </p>
        </div>

        <!-- 检测事件频率 -->
        <div class="bg-slate-900 rounded-xl border border-slate-800 p-5">
          <div class="flex items-center gap-3 mb-3">
            <div class="p-2 rounded-lg bg-cyan-500/15">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="text-cyan-400">
                <polyline points="22,12 18,12 15,21 9,3 6,12 2,12"/>
              </svg>
            </div>
            <span class="text-xs text-slate-500 uppercase tracking-wider">检测事件频率</span>
          </div>
          <p class="text-white font-semibold text-lg">
            {{ detectionEventsPerSecond > 0 ? detectionEventsPerSecond.toFixed(2) : '—' }}
            <span class="text-slate-400 text-sm font-normal">次/秒</span>
          </p>
          <p class="text-slate-400 text-xs mt-1">平均每秒累计检测事件数</p>
        </div>

        <!-- 类别覆盖率 -->
        <div class="bg-slate-900 rounded-xl border border-slate-800 p-5">
          <div class="flex items-center gap-3 mb-3">
            <div class="p-2 rounded-lg bg-indigo-500/15">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="text-indigo-400">
                <line x1="18" y1="20" x2="18" y2="10"/>
                <line x1="12" y1="20" x2="12" y2="4"/>
                <line x1="6" y1="20" x2="6" y2="14"/>
              </svg>
            </div>
            <span class="text-xs text-slate-500 uppercase tracking-wider">类别覆盖</span>
          </div>
          <p class="text-white font-semibold text-lg">
            {{ detectedClassCount }}
            <span class="text-slate-400 text-sm font-normal">/ {{ configuredClassCount }}</span>
          </p>
          <p class="text-slate-400 text-xs mt-1">
            实际检测到 / 配置类别数
          </p>
        </div>

      </div>

      <!-- ──────────────────────────────────────────────────────────────── -->
      <!-- AI 智能总结（仅当 extra_data 存在时展示）                         -->
      <!-- ──────────────────────────────────────────────────────────────── -->
      <div
        v-if="hasShortReport"
        class="bg-gradient-to-br from-slate-900 to-slate-900/80 rounded-xl border border-blue-500/25 p-5"
      >
        <div class="flex items-center gap-3 mb-4">
          <div class="p-2 rounded-lg bg-blue-500/15">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="text-blue-400">
              <path d="M12 2a10 10 0 100 20 10 10 0 000-20z"/>
              <path d="M12 6v6l4 2"/>
            </svg>
          </div>
          <div>
            <h3 class="text-white font-semibold text-sm">AI 智能总结</h3>
            <p class="text-slate-500 text-xs mt-0.5">由 AI 生成的检测分析报告</p>
          </div>
        </div>
        <div
          class="text-slate-300 text-sm leading-relaxed bg-blue-500/5 border border-blue-500/20 rounded-lg px-4 py-3"
        >
          {{ shortReportText }}
        </div>
      </div>

      <!-- ──────────────────────────────────────────────────────────────── -->
      <!-- 第二屏：本次任务结论摘要                                      -->
      <!-- ──────────────────────────────────────────────────────────────── -->
      <div class="bg-slate-900 rounded-xl border border-cyan-500/20 p-5">
        <div class="flex items-center gap-3 mb-4">
          <div class="p-2 rounded-lg bg-cyan-500/15">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="text-cyan-400">
              <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/>
              <polyline points="14,2 14,8 20,8"/>
              <line x1="16" y1="13" x2="8" y2="13"/>
              <line x1="16" y1="17" x2="8" y2="17"/>
              <polyline points="10,9 9,9 8,9"/>
            </svg>
          </div>
          <div>
            <h3 class="text-white font-semibold text-sm">本次任务结论</h3>
            <p class="text-slate-500 text-xs mt-0.5">基于当前归档数据的分析摘要</p>
          </div>
        </div>
        <p class="text-slate-300 text-sm leading-relaxed">{{ taskSummary }}</p>
      </div>

      <!-- ──────────────────────────────────────────────────────────────── -->
      <!-- 第三屏：类别统计                                            -->
      <!-- ──────────────────────────────────────────────────────────────── -->
      <div class="bg-slate-900 rounded-xl border border-slate-800 p-5">
        <div class="flex items-center justify-between mb-4">
          <div>
            <h3 class="text-white font-semibold">检测类别统计</h3>
            <p class="text-slate-500 text-xs mt-0.5">按检测事件次数降序排列</p>
          </div>
        </div>

        <div class="space-y-3">
          <div
            v-for="item in sortedClasses"
            :key="item.cls"
            class="flex items-center gap-4"
          >
            <span
              class="px-3 py-1 rounded-lg border text-sm font-mono min-w-[100px] text-center shrink-0"
              :class="[getClassStyle(item.cls).bg, getClassStyle(item.cls).text, getClassStyle(item.cls).border]"
            >
              {{ item.cls }}
            </span>
            <div class="flex-1 h-8 bg-slate-800 rounded-lg overflow-hidden relative">
              <div
                class="h-full rounded-lg transition-all duration-500"
                :class="getClassStyle(item.cls).bar"
                :style="{ width: `${(item.count / maxCount) * 100}%` }"
              ></div>
            </div>
            <span class="text-white font-mono font-bold min-w-[60px] text-right shrink-0">
              {{ item.count.toLocaleString() }}
              <span class="text-slate-500 font-normal text-xs ml-0.5">次</span>
            </span>
            <span class="text-slate-500 font-mono text-xs min-w-[52px] text-right shrink-0">
              {{ (item.share * 100).toFixed(1) }}%
            </span>
          </div>

          <div v-if="sortedClasses.length === 0" class="text-center py-8 text-slate-500">
            暂无检测数据
          </div>
        </div>

        <!-- 统计口径说明（重要） -->
        <div class="mt-4 pt-4 border-t border-slate-800">
          <p class="text-slate-600 text-xs flex items-start gap-2">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="shrink-0 mt-0.5 text-amber-600">
              <circle cx="12" cy="12" r="10"/>
              <line x1="12" y1="8" x2="12" y2="12"/>
              <line x1="12" y1="16" x2="12.01" y2="16"/>
            </svg>
            <span>
              <strong class="text-amber-600/80 font-medium">统计口径说明：</strong>
              以上"检测事件次数"为逐帧检测框累计次数，不代表视频中出现的独立目标数量。
              同一目标在连续多帧中被重复检测时，每帧均会计入。
            </span>
          </p>
        </div>
      </div>

      <!-- ──────────────────────────────────────────────────────────────── -->
      <!-- 第四屏：模型配置信息卡                                       -->
      <!-- ──────────────────────────────────────────────────────────────── -->
      <div class="bg-slate-900 rounded-xl border border-slate-800 p-5">
        <div class="flex items-center gap-3 mb-4">
          <div class="p-2 rounded-lg bg-violet-500/15">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="text-violet-400">
              <circle cx="12" cy="12" r="3"/>
              <path d="M19.07 4.93a10 10 0 010 14.14M4.93 4.93a10 10 0 000 14.14"/>
            </svg>
          </div>
          <div>
            <h3 class="text-white font-semibold text-sm">任务配置详情</h3>
            <p class="text-slate-500 text-xs mt-0.5">本次分析使用的模型与参数</p>
          </div>
        </div>

        <div class="grid grid-cols-2 gap-x-8 gap-y-3 text-sm">
          <!-- model_id -->
          <div class="flex gap-3">
            <span class="text-slate-500 min-w-[80px]">模型 ID</span>
            <span class="text-slate-200 font-mono text-xs break-all">
              {{ record.detection_model?.model_id || '—' }}
            </span>
          </div>
          <!-- display_name -->
          <div class="flex gap-3">
            <span class="text-slate-500 min-w-[80px]">显示名称</span>
            <span class="text-slate-200 font-mono text-xs break-all">
              {{ record.detection_model?.display_name || '—' }}
            </span>
          </div>
          <!-- model_type -->
          <div class="flex gap-3">
            <span class="text-slate-500 min-w-[80px]">检测模式</span>
            <span class="text-slate-200 text-xs">
              {{ modelModeLabel }}
            </span>
          </div>
          <!-- configured class count -->
          <div class="flex gap-3">
            <span class="text-slate-500 min-w-[80px]">配置类别</span>
            <span class="text-slate-200 text-xs">{{ configuredClassCount }} 个</span>
          </div>
        </div>

        <!-- 类别列表（根据模式显示对应字段） -->
        <div v-if="activeClassList.length > 0" class="mt-4 pt-4 border-t border-slate-800">
          <p class="text-slate-500 text-xs mb-2">
            {{ record.detection_model?.model_type === 'open_vocab' ? '自定义检测词表（prompt_classes）' : '固定类别筛选列表（selected_classes）' }}
          </p>
          <div class="flex flex-wrap gap-2">
            <span
              v-for="cls in activeClassList"
              :key="cls"
              class="px-3 py-1 rounded-lg border text-sm font-mono"
              :class="[getClassStyle(cls).bg, getClassStyle(cls).text, getClassStyle(cls).border]"
            >
              {{ cls }}
            </span>
          </div>
        </div>

        <div v-else class="mt-4 pt-4 border-t border-slate-800">
          <p class="text-slate-600 text-xs italic">暂无可展示的类别配置</p>
        </div>

        <!-- metadata.model_config 额外信息 -->
        <div v-if="record.metadata?.model_config" class="mt-4 pt-4 border-t border-slate-800">
          <p class="text-slate-500 text-xs mb-2">模型完整配置</p>
          <pre class="text-slate-400 font-mono text-xs bg-slate-950 rounded-lg p-3 overflow-x-auto">{{ JSON.stringify(record.metadata.model_config, null, 2) }}</pre>
        </div>
      </div>

      <!-- ──────────────────────────────────────────────────────────────── -->
      <!-- 第五屏：原始 JSON（折叠展示，作为次级参考）                -->
      <!-- ──────────────────────────────────────────────────────────────── -->
      <div class="bg-slate-900 rounded-xl border border-slate-800">
        <button
          class="w-full flex items-center justify-between px-5 py-4 hover:bg-slate-800/40 transition-colors"
          @click="jsonCollapsed = !jsonCollapsed"
        >
          <div class="flex items-center gap-3">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="text-slate-500">
              <polyline points="16,18 22,12 16,6"/>
              <polyline points="8,6 2,12 8,18"/>
            </svg>
            <h3 class="text-white font-semibold text-sm">原始归档数据</h3>
            <span class="text-slate-600 text-xs">(开发者参考)</span>
          </div>
          <div class="flex items-center gap-3">
            <button
              class="flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium
                     bg-slate-800 border border-slate-700 text-slate-400
                     hover:border-purple-600 hover:text-purple-400 transition-all"
              @click.stop="downloadData"
            >
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/>
                <polyline points="7,10 12,15 17,10"/>
                <line x1="12" y1="15" x2="12" y2="3"/>
              </svg>
              完整 JSON
            </button>
            <svg
              width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
              class="text-slate-500 transition-transform duration-200"
              :class="jsonCollapsed ? '' : 'rotate-180'"
            >
              <polyline points="6,9 12,15 18,9"/>
            </svg>
          </div>
        </button>

        <Transition name="collapse">
          <div v-show="!jsonCollapsed" class="px-5 pb-5">
            <div class="bg-slate-950 rounded-lg p-4 font-mono text-xs overflow-x-auto max-h-80 overflow-y-auto">
              <pre class="text-slate-400 whitespace-pre-wrap">{{ JSON.stringify({
  record_id: record.id,
  created_at: record.created_at,
  video_info: {
    name: record.video_name,
    path: record.video_path,
    duration_seconds: record.duration,
  },
  model_info: record.detection_model,
  statistics: {
    total_detections: record.total_detections,
    class_counts: record.class_counts,
  },
  metadata: record.metadata,
}, null, 2) }}</pre>
            </div>
          </div>
        </Transition>
      </div>

    </div>

    <!-- ══════════════════════════════════════════════════════════════════ -->
    <!-- 空状态                                                       -->
    <!-- ══════════════════════════════════════════════════════════════════ -->
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

<style scoped>
.collapse-enter-active,
.collapse-leave-active {
  transition: all 0.25s ease;
  overflow: hidden;
}
.collapse-enter-from,
.collapse-leave-to {
  max-height: 0;
  opacity: 0;
}
.collapse-enter-to,
.collapse-leave-from {
  max-height: 600px;
  opacity: 1;
}
</style>
