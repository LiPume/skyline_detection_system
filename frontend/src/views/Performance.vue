<script setup lang="ts">
/**
 * Skyline — Performance Analysis Page
 * Model performance metrics, P-R curves, and analytics dashboard.
 * Import video detection data and visualize model performance.
 */
import { ref, computed } from 'vue'

// ── State ──────────────────────────────────────────────────────────────────────

// Import state
const isDragging = ref(false)
const importedFiles = ref<{ name: string; type: string; size: number }[]>([])
const isImporting = ref(false)

// Active tab
const activeTab = ref<'overview' | 'pr-curves' | 'class-analysis' | 'reports'>('overview')

// Mock data - will be replaced with real imported data
const performanceMetrics = ref({
  mAP50: 0.782,
  mAP50_95: 0.584,
  precision: 0.845,
  recall: 0.718,
  fps: 25.3,
  inferenceTime: 38.7,
})

const classMetrics = ref([
  { name: 'person', ap50: 0.89, precision: 0.92, recall: 0.85, count: 1247 },
  { name: 'car', ap50: 0.85, precision: 0.88, recall: 0.82, count: 892 },
  { name: 'truck', ap50: 0.78, precision: 0.81, recall: 0.76, count: 234 },
  { name: 'bicycle', ap50: 0.72, precision: 0.79, recall: 0.68, count: 156 },
  { name: 'motorcycle', ap50: 0.69, precision: 0.75, recall: 0.64, count: 98 },
  { name: 'drone', ap50: 0.65, precision: 0.71, recall: 0.58, count: 23 },
])

const testReports = ref([
  { id: 1, name: 'Daytime Urban Test', date: '2026-03-15', score: 82.5 },
  { id: 2, name: 'Night Surveillance', date: '2026-03-14', score: 71.3 },
  { id: 3, name: 'Rainy Weather Test', date: '2026-03-12', score: 68.9 },
  { id: 4, name: 'Dense Crowds', date: '2026-03-10', score: 75.6 },
])

// ── Computed ──────────────────────────────────────────────────────────────────

const overallScore = computed(() => {
  return (performanceMetrics.value.mAP50 * 100).toFixed(1)
})

// ── File Import ───────────────────────────────────────────────────────────────

function onDragOver(e: DragEvent) {
  e.preventDefault()
  isDragging.value = true
}

function onDragLeave() {
  isDragging.value = false
}

function onDrop(e: DragEvent) {
  e.preventDefault()
  isDragging.value = false
  const files = e.dataTransfer?.files
  if (files) handleFiles(files)
}

function onFileSelect(e: Event) {
  const input = e.target as HTMLInputElement
  if (input.files) handleFiles(input.files)
}

async function handleFiles(files: FileList) {
  isImporting.value = true
  for (const file of files) {
    importedFiles.value.push({
      name: file.name,
      type: file.type || 'unknown',
      size: file.size,
    })
  }
  // TODO: Process files and extract detection data
  setTimeout(() => {
    isImporting.value = false
  }, 1000)
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

function removeFile(index: number) {
  importedFiles.value.splice(index, 1)
}

// ── Export Report ─────────────────────────────────────────────────────────────

function exportReport() {
  const report = {
    generated_at: new Date().toISOString(),
    metrics: performanceMetrics.value,
    class_metrics: classMetrics.value,
    reports: testReports.value,
  }
  const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `performance_report_${Date.now()}.json`
  a.click()
  URL.revokeObjectURL(url)
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function metricColor(value: number): string {
  if (value >= 0.75) return 'text-emerald-400'
  if (value >= 0.5) return 'text-yellow-400'
  return 'text-red-400'
}

function metricBg(value: number): string {
  if (value >= 0.75) return 'bg-emerald-500/10 border-emerald-500/25'
  if (value >= 0.5) return 'bg-yellow-500/10 border-yellow-500/25'
  return 'bg-red-500/10 border-red-500/25'
}

function scoreColor(score: number): string {
  if (score >= 80) return 'text-emerald-400'
  if (score >= 60) return 'text-yellow-400'
  return 'text-red-400'
}
</script>

<template>
  <div class="h-full bg-slate-950 flex flex-col overflow-hidden">

    <!-- Page header -->
    <div class="px-8 py-6 flex-shrink-0 border-b border-slate-800">
      <div class="flex items-center justify-between">
        <div>
          <h2 class="text-lg font-semibold text-white">性能分析</h2>
          <p class="text-sm text-slate-500 mt-0.5">
            模型评估指标 · P-R 曲线 · 检测报告
          </p>
        </div>
        <div class="flex items-center gap-3">
          <button
            class="flex items-center gap-2 px-4 py-2 rounded-lg bg-slate-800 border border-slate-700
                   text-slate-400 text-sm hover:border-blue-600 hover:text-blue-400 transition-all"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/>
              <polyline points="17,8 12,3 7,8"/>
              <line x1="12" y1="3" x2="12" y2="15"/>
            </svg>
            导出报告
          </button>
          <button
            class="flex items-center gap-2 px-4 py-2 rounded-lg bg-blue-600/20 border border-blue-600/40
                   text-blue-400 text-sm hover:bg-blue-600/30 transition-all"
            @click="exportReport"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/>
              <polyline points="14,2 14,8 20,8"/>
            </svg>
            生成报告
          </button>
        </div>
      </div>
    </div>

    <!-- Tab navigation -->
    <div class="px-8 pt-4 flex-shrink-0">
      <nav class="flex gap-1 bg-slate-900/50 p-1 rounded-xl w-fit">
        <button
          v-for="tab in [
            { id: 'overview', label: '总览' },
            { id: 'pr-curves', label: 'P-R 曲线' },
            { id: 'class-analysis', label: '类别分析' },
            { id: 'reports', label: '测试报告' },
          ]"
          :key="tab.id"
          class="px-4 py-2 rounded-lg text-sm font-medium transition-all"
          :class="activeTab === tab.id
            ? 'bg-blue-600 text-white shadow-lg shadow-blue-600/25'
            : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'"
          @click="activeTab = tab.id as typeof activeTab"
        >
          {{ tab.label }}
        </button>
      </nav>
    </div>

    <!-- Content area -->
    <div class="flex-1 overflow-auto px-8 py-5">

      <!-- ── Overview Tab ──────────────────────────────────────────────────── -->
      <template v-if="activeTab === 'overview'">
        <div class="grid grid-cols-12 gap-5">

          <!-- Overall Score (large card) -->
          <div class="col-span-4 row-span-2 rounded-2xl bg-gradient-to-br from-blue-600/20 to-indigo-600/20
                      border border-blue-500/25 p-6 flex flex-col items-center justify-center">
            <div class="text-slate-400 text-sm mb-2">综合评分</div>
            <div class="text-7xl font-bold text-white tracking-tight">{{ overallScore }}</div>
            <div class="text-2xl text-blue-400 mt-1">mAP@0.5</div>
            <div class="mt-6 flex items-center gap-2 text-sm">
              <span class="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
              <span class="text-slate-400">满足 ≥75% 指标要求</span>
            </div>
          </div>

          <!-- Key Metrics -->
          <div class="col-span-8 grid grid-cols-2 gap-4">
            <!-- Precision -->
            <div class="rounded-xl border p-5" :class="metricBg(performanceMetrics.precision)">
              <div class="text-slate-400 text-xs mb-1">Precision（精度）</div>
              <div class="text-3xl font-bold" :class="metricColor(performanceMetrics.precision)">
                {{ (performanceMetrics.precision * 100).toFixed(1) }}%
              </div>
              <div class="mt-3 h-1.5 bg-slate-700 rounded-full overflow-hidden">
                <div
                  class="h-full rounded-full transition-all"
                  :class="performanceMetrics.precision >= 0.75 ? 'bg-emerald-400' : 'bg-yellow-400'"
                  :style="{ width: `${performanceMetrics.precision * 100}%` }"
                ></div>
              </div>
            </div>

            <!-- Recall -->
            <div class="rounded-xl border p-5" :class="metricBg(performanceMetrics.recall)">
              <div class="text-slate-400 text-xs mb-1">Recall（召回率）</div>
              <div class="text-3xl font-bold" :class="metricColor(performanceMetrics.recall)">
                {{ (performanceMetrics.recall * 100).toFixed(1) }}%
              </div>
              <div class="mt-3 h-1.5 bg-slate-700 rounded-full overflow-hidden">
                <div
                  class="h-full rounded-full transition-all"
                  :class="performanceMetrics.recall >= 0.75 ? 'bg-emerald-400' : 'bg-yellow-400'"
                  :style="{ width: `${performanceMetrics.recall * 100}%` }"
                ></div>
              </div>
            </div>

            <!-- FPS -->
            <div class="rounded-xl border p-5 bg-slate-900/50 border-slate-700/50">
              <div class="text-slate-400 text-xs mb-1">处理速度</div>
              <div class="text-3xl font-bold text-cyan-400">
                {{ performanceMetrics.fps.toFixed(1) }}
                <span class="text-base text-slate-400 font-normal">FPS</span>
              </div>
              <div class="mt-2 text-xs text-slate-500">≥25 FPS 要求 ✓</div>
            </div>

            <!-- Inference Time -->
            <div class="rounded-xl border p-5 bg-slate-900/50 border-slate-700/50">
              <div class="text-slate-400 text-xs mb-1">推理延迟</div>
              <div class="text-3xl font-bold text-amber-400">
                {{ performanceMetrics.inferenceTime.toFixed(1) }}
                <span class="text-base text-slate-400 font-normal">ms</span>
              </div>
              <div class="mt-2 text-xs text-slate-500">单帧推理时间</div>
            </div>
          </div>

          <!-- mAP50-95 -->
          <div class="col-span-4 rounded-xl border bg-slate-900/50 border-slate-700/50 p-5">
            <div class="text-slate-400 text-xs mb-1">mAP@0.5:0.95</div>
            <div class="text-2xl font-bold" :class="metricColor(performanceMetrics.mAP50_95)">
              {{ (performanceMetrics.mAP50_95 * 100).toFixed(1) }}%
            </div>
          </div>

          <!-- Class Count -->
          <div class="col-span-4 rounded-xl border bg-slate-900/50 border-slate-700/50 p-5">
            <div class="text-slate-400 text-xs mb-1">检测类别数</div>
            <div class="text-2xl font-bold text-purple-400">{{ classMetrics.length }}</div>
          </div>

          <!-- Total Detections -->
          <div class="col-span-4 rounded-xl border bg-slate-900/50 border-slate-700/50 p-5">
            <div class="text-slate-400 text-xs mb-1">总检测数</div>
            <div class="text-2xl font-bold text-orange-400">
              {{ classMetrics.reduce((sum, c) => sum + c.count, 0).toLocaleString() }}
            </div>
          </div>

        </div>

        <!-- Quick Class Metrics -->
        <div class="mt-6 rounded-xl border border-slate-800 bg-slate-900/50 overflow-hidden">
          <div class="px-5 py-4 border-b border-slate-800">
            <h3 class="text-sm font-medium text-slate-300">各类别 AP@0.5</h3>
          </div>
          <div class="p-5 grid grid-cols-3 gap-4">
            <div
              v-for="cls in classMetrics"
              :key="cls.name"
              class="flex items-center justify-between p-3 rounded-lg bg-slate-800/50"
            >
              <div class="flex items-center gap-3">
                <div class="w-10 h-10 rounded-lg bg-slate-700 flex items-center justify-center text-sm font-bold text-slate-300">
                  {{ cls.name.slice(0, 2).toUpperCase() }}
                </div>
                <div>
                  <div class="text-sm font-medium text-slate-200">{{ cls.name }}</div>
                  <div class="text-xs text-slate-500">{{ cls.count.toLocaleString() }} 个目标</div>
                </div>
              </div>
              <div class="text-lg font-bold" :class="metricColor(cls.ap50)">
                {{ (cls.ap50 * 100).toFixed(0) }}
              </div>
            </div>
          </div>
        </div>
      </template>

      <!-- ── P-R Curves Tab ────────────────────────────────────────────────── -->
      <template v-if="activeTab === 'pr-curves'">
        <div class="grid grid-cols-12 gap-5">

          <!-- Main P-R Curve Chart -->
          <div class="col-span-8 rounded-2xl border border-slate-800 bg-slate-900/50 overflow-hidden">
            <div class="px-5 py-4 border-b border-slate-800 flex items-center justify-between">
              <h3 class="text-sm font-medium text-slate-300">P-R 曲线（所有类别）</h3>
              <div class="flex items-center gap-4 text-xs text-slate-500">
                <span class="flex items-center gap-1.5">
                  <span class="w-3 h-0.5 bg-blue-400 rounded"></span> person
                </span>
                <span class="flex items-center gap-1.5">
                  <span class="w-3 h-0.5 bg-yellow-400 rounded"></span> car
                </span>
                <span class="flex items-center gap-1.5">
                  <span class="w-3 h-0.5 bg-emerald-400 rounded"></span> truck
                </span>
              </div>
            </div>
            <div class="p-6 h-80 flex items-center justify-center text-slate-600">
              <!-- Placeholder for P-R curve chart -->
              <div class="text-center">
                <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1" class="mx-auto mb-3 opacity-40">
                  <line x1="18" y1="20" x2="18" y2="10"/>
                  <line x1="12" y1="20" x2="12" y2="4"/>
                  <line x1="6" y1="20" x2="6" y2="14"/>
                  <line x1="2" y1="20" x2="22" y2="20"/>
                </svg>
                <p class="text-sm">P-R 曲线图表区域</p>
                <p class="text-xs text-slate-600 mt-1">导入检测数据后自动生成</p>
              </div>
            </div>
          </div>

          <!-- Class Selector -->
          <div class="col-span-4 rounded-2xl border border-slate-800 bg-slate-900/50 overflow-hidden">
            <div class="px-5 py-4 border-b border-slate-800">
              <h3 class="text-sm font-medium text-slate-300">选择类别</h3>
            </div>
            <div class="p-4 space-y-2">
              <button
                v-for="cls in classMetrics"
                :key="cls.name"
                class="w-full flex items-center justify-between p-3 rounded-lg
                       bg-slate-800/50 hover:bg-slate-800 transition-colors text-left"
              >
                <div class="flex items-center gap-3">
                  <div
                    class="w-3 h-3 rounded-sm"
                    :style="{ backgroundColor: ['#60a5fa', '#fbbf24', '#34d399', '#a78bfa', '#f97316', '#06b6d4'][classMetrics.indexOf(cls) % 6] }"
                  ></div>
                  <span class="text-sm text-slate-300">{{ cls.name }}</span>
                </div>
                <span class="text-sm font-mono" :class="metricColor(cls.ap50)">
                  {{ (cls.ap50 * 100).toFixed(1) }}%
                </span>
              </button>
            </div>
          </div>

          <!-- AP Summary Table -->
          <div class="col-span-12 rounded-2xl border border-slate-800 bg-slate-900/50 overflow-hidden">
            <div class="px-5 py-4 border-b border-slate-800">
              <h3 class="text-sm font-medium text-slate-300">AP 详细数据</h3>
            </div>
            <table class="w-full">
              <thead>
                <tr class="border-b border-slate-800">
                  <th class="px-5 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">类别</th>
                  <th class="px-5 py-3 text-right text-xs font-medium text-slate-500 uppercase tracking-wider">AP@0.5</th>
                  <th class="px-5 py-3 text-right text-xs font-medium text-slate-500 uppercase tracking-wider">Precision</th>
                  <th class="px-5 py-3 text-right text-xs font-medium text-slate-500 uppercase tracking-wider">Recall</th>
                  <th class="px-5 py-3 text-right text-xs font-medium text-slate-500 uppercase tracking-wider">检测数</th>
                  <th class="px-5 py-3 text-right text-xs font-medium text-slate-500 uppercase tracking-wider">满足阈值</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="cls in classMetrics"
                  :key="cls.name"
                  class="border-b border-slate-800/50 hover:bg-slate-800/30"
                >
                  <td class="px-5 py-4 text-sm text-slate-300">{{ cls.name }}</td>
                  <td class="px-5 py-4 text-right font-mono text-sm" :class="metricColor(cls.ap50)">
                    {{ (cls.ap50 * 100).toFixed(2) }}%
                  </td>
                  <td class="px-5 py-4 text-right font-mono text-sm text-slate-300">
                    {{ (cls.precision * 100).toFixed(2) }}%
                  </td>
                  <td class="px-5 py-4 text-right font-mono text-sm text-slate-300">
                    {{ (cls.recall * 100).toFixed(2) }}%
                  </td>
                  <td class="px-5 py-4 text-right font-mono text-sm text-slate-400">
                    {{ cls.count.toLocaleString() }}
                  </td>
                  <td class="px-5 py-4 text-right">
                    <span
                      class="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full"
                      :class="cls.ap50 >= 0.75 ? 'bg-emerald-500/15 text-emerald-400' : 'bg-yellow-500/15 text-yellow-400'"
                    >
                      <span class="w-1.5 h-1.5 rounded-full bg-current"></span>
                      {{ cls.ap50 >= 0.75 ? '达标' : '待优化' }}
                    </span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

        </div>
      </template>

      <!-- ── Class Analysis Tab ─────────────────────────────────────────────── -->
      <template v-if="activeTab === 'class-analysis'">
        <div class="grid grid-cols-12 gap-5">

          <!-- Confidence Distribution -->
          <div class="col-span-6 rounded-2xl border border-slate-800 bg-slate-900/50 overflow-hidden">
            <div class="px-5 py-4 border-b border-slate-800">
              <h3 class="text-sm font-medium text-slate-300">置信度分布</h3>
            </div>
            <div class="p-6 h-64 flex items-center justify-center text-slate-600">
              <div class="text-center">
                <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1" class="mx-auto mb-3 opacity-40">
                  <rect x="3" y="12" width="4" height="8" rx="1"/>
                  <rect x="10" y="8" width="4" height="12" rx="1"/>
                  <rect x="17" y="4" width="4" height="16" rx="1"/>
                </svg>
                <p class="text-sm">置信度直方图</p>
              </div>
            </div>
          </div>

          <!-- Detection Timeline -->
          <div class="col-span-6 rounded-2xl border border-slate-800 bg-slate-900/50 overflow-hidden">
            <div class="px-5 py-4 border-b border-slate-800">
              <h3 class="text-sm font-medium text-slate-300">检测数量时序</h3>
            </div>
            <div class="p-6 h-64 flex items-center justify-center text-slate-600">
              <div class="text-center">
                <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1" class="mx-auto mb-3 opacity-40">
                  <polyline points="22,12 18,12 15,21 9,3 6,12 2,12"/>
                </svg>
                <p class="text-sm">检测时序图</p>
              </div>
            </div>
          </div>

          <!-- Object Size Distribution -->
          <div class="col-span-6 rounded-2xl border border-slate-800 bg-slate-900/50 overflow-hidden">
            <div class="px-5 py-4 border-b border-slate-800">
              <h3 class="text-sm font-medium text-slate-300">目标尺度分布</h3>
            </div>
            <div class="p-6 h-64 flex items-center justify-center text-slate-600">
              <div class="text-center">
                <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1" class="mx-auto mb-3 opacity-40">
                  <circle cx="12" cy="12" r="10"/>
                  <circle cx="12" cy="12" r="6"/>
                  <circle cx="12" cy="12" r="2"/>
                </svg>
                <p class="text-sm">尺度热力图</p>
              </div>
            </div>
          </div>

          <!-- Spatial Distribution -->
          <div class="col-span-6 rounded-2xl border border-slate-800 bg-slate-900/50 overflow-hidden">
            <div class="px-5 py-4 border-b border-slate-800">
              <h3 class="text-sm font-medium text-slate-300">空间分布热力图</h3>
            </div>
            <div class="p-6 h-64 flex items-center justify-center text-slate-600">
              <div class="text-center">
                <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1" class="mx-auto mb-3 opacity-40">
                  <rect x="3" y="3" width="18" height="18" rx="2"/>
                  <line x1="3" y1="9" x2="21" y2="9"/>
                  <line x1="3" y1="15" x2="21" y2="15"/>
                  <line x1="9" y1="3" x2="9" y2="21"/>
                  <line x1="15" y1="3" x2="15" y2="21"/>
                </svg>
                <p class="text-sm">空间分布图</p>
              </div>
            </div>
          </div>

        </div>
      </template>

      <!-- ── Reports Tab ────────────────────────────────────────────────────── -->
      <template v-if="activeTab === 'reports'">
        <div class="grid grid-cols-12 gap-5">

          <!-- Data Import Zone -->
          <div class="col-span-5 rounded-2xl border-2 border-dashed overflow-hidden transition-all"
               :class="isDragging
                 ? 'border-blue-500 bg-blue-500/5'
                 : 'border-slate-700 bg-slate-900/30 hover:border-slate-600'"
               @dragover="onDragOver"
               @dragleave="onDragLeave"
               @drop="onDrop"
          >
            <div class="p-8 flex flex-col items-center justify-center text-center">
              <div
                class="w-16 h-16 rounded-2xl bg-slate-800 flex items-center justify-center mb-4
                       transition-colors"
                :class="isDragging ? 'bg-blue-600/20' : ''"
              >
                <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"
                     :class="isDragging ? 'text-blue-400' : 'text-slate-500'">
                  <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/>
                  <polyline points="17,8 12,3 7,8"/>
                  <line x1="12" y1="3" x2="12" y2="15"/>
                </svg>
              </div>
              <h4 class="text-sm font-medium text-slate-300 mb-1">拖放文件到此处</h4>
              <p class="text-xs text-slate-500 mb-4">或点击下方按钮选择文件</p>
              <label class="px-4 py-2 rounded-lg bg-blue-600/20 border border-blue-600/40
                           text-blue-400 text-sm cursor-pointer hover:bg-blue-600/30 transition-colors">
                选择文件
                <input type="file" class="hidden" multiple accept=".json,.csv,.xlsx" @change="onFileSelect">
              </label>
              <p class="text-xs text-slate-600 mt-3">支持 JSON / CSV / Excel 格式</p>
            </div>
          </div>

          <!-- Imported Files List -->
          <div class="col-span-7 rounded-2xl border border-slate-800 bg-slate-900/50 overflow-hidden">
            <div class="px-5 py-4 border-b border-slate-800 flex items-center justify-between">
              <h3 class="text-sm font-medium text-slate-300">已导入文件</h3>
              <span class="text-xs text-slate-500">{{ importedFiles.length }} 个文件</span>
            </div>
            <div class="p-4">
              <div v-if="importedFiles.length === 0" class="text-center py-8 text-slate-600">
                <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1" class="mx-auto mb-2 opacity-40">
                  <path d="M13 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V9z"/>
                  <polyline points="13,2 13,9 20,9"/>
                </svg>
                <p class="text-xs">暂无导入文件</p>
              </div>
              <div v-else class="space-y-2">
                <div
                  v-for="(file, index) in importedFiles"
                  :key="index"
                  class="flex items-center justify-between p-3 rounded-lg bg-slate-800/50"
                >
                  <div class="flex items-center gap-3">
                    <div class="w-8 h-8 rounded-lg bg-slate-700 flex items-center justify-center">
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="text-slate-400">
                        <path d="M13 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V9z"/>
                        <polyline points="13,2 13,9 20,9"/>
                      </svg>
                    </div>
                    <div>
                      <div class="text-sm text-slate-300">{{ file.name }}</div>
                      <div class="text-xs text-slate-500">{{ formatFileSize(file.size) }}</div>
                    </div>
                  </div>
                  <button
                    class="p-1.5 rounded-lg hover:bg-slate-700 text-slate-500 hover:text-red-400 transition-colors"
                    @click="removeFile(index)"
                  >
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <line x1="18" y1="6" x2="6" y2="18"/>
                      <line x1="6" y1="6" x2="18" y2="18"/>
                    </svg>
                  </button>
                </div>
              </div>
            </div>
          </div>

          <!-- Test Reports List -->
          <div class="col-span-12 rounded-2xl border border-slate-800 bg-slate-900/50 overflow-hidden">
            <div class="px-5 py-4 border-b border-slate-800 flex items-center justify-between">
              <h3 class="text-sm font-medium text-slate-300">测试报告列表</h3>
              <button class="text-xs text-blue-400 hover:text-blue-300 transition-colors">
                + 新建报告
              </button>
            </div>
            <table class="w-full">
              <thead>
                <tr class="border-b border-slate-800">
                  <th class="px-5 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">测试名称</th>
                  <th class="px-5 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">测试日期</th>
                  <th class="px-5 py-3 text-right text-xs font-medium text-slate-500 uppercase tracking-wider">评分</th>
                  <th class="px-5 py-3 text-right text-xs font-medium text-slate-500 uppercase tracking-wider">状态</th>
                  <th class="px-5 py-3 text-right text-xs font-medium text-slate-500 uppercase tracking-wider">操作</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="report in testReports"
                  :key="report.id"
                  class="border-b border-slate-800/50 hover:bg-slate-800/30"
                >
                  <td class="px-5 py-4 text-sm text-slate-300">{{ report.name }}</td>
                  <td class="px-5 py-4 text-sm text-slate-500 font-mono">{{ report.date }}</td>
                  <td class="px-5 py-4 text-right font-mono text-lg font-bold" :class="scoreColor(report.score)">
                    {{ report.score.toFixed(1) }}
                  </td>
                  <td class="px-5 py-4 text-right">
                    <span
                      class="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full"
                      :class="report.score >= 75 ? 'bg-emerald-500/15 text-emerald-400' : 'bg-yellow-500/15 text-yellow-400'"
                    >
                      <span class="w-1.5 h-1.5 rounded-full bg-current"></span>
                      {{ report.score >= 75 ? '达标' : '待优化' }}
                    </span>
                  </td>
                  <td class="px-5 py-4 text-right">
                    <button class="text-xs text-blue-400 hover:text-blue-300 mr-3">查看</button>
                    <button class="text-xs text-slate-500 hover:text-slate-300">导出</button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

        </div>
      </template>

    </div>
  </div>
</template>

<style scoped>
/* Smooth transitions for metric bars */
.transition-all {
  transition-property: all;
  transition-timing-function: cubic-bezier(0.4, 0, 0.2, 1);
  transition-duration: 300ms;
}
</style>
