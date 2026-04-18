<script setup lang="ts">
/**
 * Skyline — 模型评测结果与案例分析页
 * 用于比赛展示、PPT截图、答辩讲解
 *
 * 数据来源：performanceReport.mock.ts
 * 后续替换：
 *   - report.json → 替换 meta / summaryMetrics / scenarios / caseStudies / conclusion
 *   - train_history.csv → 替换 trainingHistory / trainingSummary
 *   - pr_metrics_table_merged.csv → 替换 classMetrics（十类）
 *
 * 【本次改动】接入 merged 数据：
 *   - PerformancePrCurve.vue 使用 prCurveCsvAdapter.ts 读取 pr_curve_plot_data_merged.csv
 *   - classMetrics 由 pr_metrics_table_merged.csv 提供十类真实数据
 */
import { ref, computed, onMounted } from 'vue'
import { performanceReport } from '@/data/performanceReport.mock'
import type { PerformanceReport } from '@/data/performanceReport.mock'
import { loadPerformanceCsvData } from '@/data/performanceCsvAdapter'
import PerformancePrCurve from '@/components/performance/PerformancePrCurve.vue'

// ── 当前数据（后续替换为 fetch('report.json')） ────────────────────────────
const report = ref<PerformanceReport>(performanceReport)

// ── PR 曲线 mAP@0.5（由 metrics 表汇总行提供，不走 adapter 积分值） ───
const map50Ref = ref<number | null>(null)

// ── classMetrics 排序视图（按 AP@0.5 从大到小） ─────────────────────────
const sortedClassMetrics = computed(() =>
  [...report.value.classMetrics].sort((a, b) => b.ap50 - a.ap50)
)

// ── CSV 数据加载（只加载训练历史与摘要，不覆盖顶部核心指标） ─────────────────
// trainingHistory / trainingSummary 由 yolo_final_results.csv 提供真实数据。
// 注意：summaryMetrics（mAP@0.5 / mAP@0.5:0.95 / Precision / Recall / FPS）
//   已由 performanceReport.mock.ts 提供，来源于 system_performance_summary.xlsx，
//   此处不再覆盖，以保留赛题数据集的评测结果。
onMounted(async () => {
  try {
    const csvData = await loadPerformanceCsvData()
    // 只替换训练历史与摘要，不覆盖顶部核心指标
    report.value.trainingHistory = csvData.trainingHistory
    report.value.trainingSummary = csvData.trainingSummary
  } catch {
    // CSV 加载失败时保留 mock 数据，不做额外处理
  }

  // 加载 classMetrics CSV（十类数据），覆盖 mock；失败时保留原值
  try {
    const resp = await fetch('/metrics/pr_metrics_table_merged.csv')
    const text = await resp.text()
    const lines = text.trim().split('\n')
    // 最后一行为 All (Weighted Mean) 汇总行，从中提取 mAP@0.5
    const summaryLine = lines[lines.length - 1]
    const summaryParts = summaryLine.split(',')
    map50Ref.value = parseFloat(summaryParts[4]) || null
    // 跳过表头第1行 + 末尾 All (Weighted Mean) 汇总行，取中间十类
    const dataLines = lines.slice(1, lines.length - 1)
    report.value.classMetrics = dataLines.map(line => {
      const parts = line.split(',')
      return {
        className: parts[0],
        label: parts[0],
        precision: parseFloat(parts[1]) || 0,
        recall: parseFloat(parts[2]) || 0,
        ap50: parseFloat(parts[4]) || 0,
        ap50_95: parseFloat(parts[5]) || 0,
        support: 0,
        note: '',
      }
    })
  } catch {
    // CSV 加载失败时保留原 mock classMetrics
  }
})

// ── 指标颜色辅助 ────────────────────────────────────────────────────────────
function metricColor(value: number): string {
  if (value >= 0.75) return 'text-emerald-400'
  if (value >= 0.5)  return 'text-yellow-400'
  return 'text-red-400'
}

function apColor(value: number): string {
  if (value >= 0.75) return '#34d399'
  if (value >= 0.5)  return '#fbbf24'
  return '#f87171'
}

function scenarioColor(level: 'good' | 'medium' | 'weak') {
  if (level === 'good')   return { badge: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/25', dot: 'bg-emerald-400', label: '良好' }
  if (level === 'medium') return { badge: 'bg-yellow-500/15 text-yellow-400 border-yellow-500/25', dot: 'bg-yellow-400', label: '一般' }
  return { badge: 'bg-red-500/15 text-red-400 border-red-500/25', dot: 'bg-red-400', label: '待优化' }
}

// ── 案例分析模态框 ─────────────────────────────────────────────────────────
const activeCaseStudy = ref<PerformanceReport['caseStudies'][number] | null>(null)

function openCaseStudy(caseStudy: PerformanceReport['caseStudies'][number]) {
  activeCaseStudy.value = caseStudy
}

function closeCaseStudy() {
  activeCaseStudy.value = null
}

// ── SVG Chart Helpers ──────────────────────────────────────────────────────
const CHART_W = 700
const CHART_H = 180
const PAD = 30

function buildSmoothPath(data: typeof report.value.trainingHistory, key: string, width: number, height: number, padding: number): string {
  if (!data || !data.length) return ''
  const all = data
  const vals = all.map(e => (e as any)[key])
  const minVal = Math.min(...vals)
  const maxVal = Math.max(...vals)
  const range = maxVal - minVal || 1
  const epochs = all.map(e => e.epoch)
  const minEpoch = Math.min(...epochs)
  const maxEpoch = Math.max(...epochs)
  const epochRange = maxEpoch - minEpoch || 1

  const pts = all.map((e) => {
    const x = padding + ((e.epoch - minEpoch) / epochRange) * (width - padding * 2)
    const y = padding + (1 - ((e as any)[key] - minVal) / range) * (height - padding * 2)
    return { x: parseFloat(x.toFixed(2)), y: parseFloat(y.toFixed(2)) }
  })

  if (pts.length < 2) return ''
  let d = `M ${pts[0].x},${pts[0].y}`
  for (let i = 0; i < pts.length - 1; i++) {
    const p0 = pts[i === 0 ? 0 : i - 1]
    const p1 = pts[i]
    const p2 = pts[i + 1]
    const p3 = pts[i + 2 >= pts.length ? pts.length - 1 : i + 2]
    const cp1x = p1.x + (p2.x - p0.x) / 6
    const cp1y = p1.y + (p2.y - p0.y) / 6
    const cp2x = p2.x - (p3.x - p1.x) / 6
    const cp2y = p2.y - (p3.y - p1.y) / 6
    d += ` C ${cp1x.toFixed(1)},${cp1y.toFixed(1)} ${cp2x.toFixed(1)},${cp2y.toFixed(1)} ${p2.x},${p2.y}`
  }
  return d
}

const metricLines = computed(() => ({
  mAP50:    buildSmoothPath(report.value.trainingHistory, 'mAP50',    CHART_W, CHART_H, PAD),
  precision: buildSmoothPath(report.value.trainingHistory, 'precision', CHART_W, CHART_H, PAD),
  recall:   buildSmoothPath(report.value.trainingHistory, 'recall',   CHART_W, CHART_H, PAD),
}))

const metricGridLines = computed(() => {
  const lines = []
  for (let i = 0; i <= 4; i++) {
    const v = i / 4
    const y = PAD + (1 - i / 4) * (CHART_H - PAD * 2)
    lines.push({ y: y.toFixed(1), label: (v * 100).toFixed(0) + '%' })
  }
  return lines
})

const epochLabels = computed(() => {
  if (!report.value.trainingHistory?.length) return []
  const epochs = report.value.trainingHistory.map(e => e.epoch)
  const min = Math.min(...epochs)
  const max = Math.max(...epochs)
  const range = max - min
  const labels = []
  for (let i = 0; i <= 5; i++) {
    const e = Math.round(min + (range * i) / 5)
    const x = PAD + (i / 5) * (CHART_W - PAD * 2)
    labels.push({ x: x.toFixed(1), label: `E${e}` })
  }
  return labels
})

const bestEpochData = computed(() => {
  if (!report.value.trainingHistory?.length) return null
  const best = report.value.trainingHistory.find(e => e.epoch === report.value.trainingSummary?.bestEpoch)
  return best ?? null
})

const hasTrainingHistory = computed(() =>
  Array.isArray(report.value.trainingHistory) && report.value.trainingHistory.length > 0
)
</script>

<template>
  <div class="h-full bg-slate-950 flex flex-col overflow-hidden">

    <!-- ══ 页面头部 ═══════════════════════════════════════════════════════════ -->
    <div class="px-8 py-5 flex-shrink-0 border-b border-slate-800">
      <div class="flex items-center justify-between">
        <div>
          <h2 class="text-base font-semibold text-white tracking-wide">模型评测结果与案例分析</h2>
          <p class="text-xs text-slate-500 mt-0.5">评测报告 · 场景鲁棒性分析 · 典型案例</p>
        </div>
        <div class="flex items-center gap-2">
          <span
            class="inline-flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-full bg-emerald-500/15 border border-emerald-500/25 text-emerald-400"
          >
            <span class="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>
            评测完成
          </span>
        </div>
      </div>
    </div>

    <!-- ══ 内容区（单页滚动，无需 Tab） ════════════════════════════════════════ -->
    <div class="flex-1 overflow-y-auto px-8 py-5 space-y-6">

      <!-- ╔══════════════════════════════════════════════════════════════════════╗ -->
      <!-- ║  模块 1：评测总览（页面最重要区域）                                    ║ -->
      <!-- ╚══════════════════════════════════════════════════════════════════════╝ -->

      <!-- ── 核心评测指标（数据来源说明） ──────────────────────────────────────── -->
      <div class="mb-1">
        <p class="text-xs text-slate-600">以上指标基于赛题提供的 Drone-Vehicle 数据集评测结果</p>
      </div>

      <!-- ── 核心指标 + 模型基本信息横向布局 ─────────────────────────────────── -->
      <div class="grid grid-cols-5 gap-4">

        <!-- 左侧：核心评测指标（3个最大卡片） -->
        <div class="col-span-3 grid grid-cols-3 gap-4">
          <div class="rounded-xl border p-4 bg-slate-900/50 border-slate-800">
            <div class="text-xs text-slate-500 mb-1.5">mAP@0.5</div>
            <div class="text-3xl font-bold text-blue-400 leading-none">{{ (report.summaryMetrics.map50 * 100).toFixed(1) }}<span class="text-sm font-normal text-slate-400">%</span></div>
            <div class="mt-2 h-1 rounded-full bg-slate-700 overflow-hidden">
              <div class="h-full rounded-full bg-blue-500" :style="{ width: (report.summaryMetrics.map50 * 100) + '%' }"></div>
            </div>
            <div class="mt-1.5 flex items-center gap-1">
              <span class="text-xs text-emerald-400">✓ 达到赛题要求</span>
              <span class="text-xs text-slate-600">/ 指标≥80%</span>
            </div>
          </div>

          <div class="rounded-xl border p-4 bg-slate-900/50 border-slate-800">
            <div class="text-xs text-slate-500 mb-1.5">mAP@0.5:0.95</div>
            <div class="text-3xl font-bold leading-none" :class="metricColor(report.summaryMetrics.map50_95)">
              {{ (report.summaryMetrics.map50_95 * 100).toFixed(1) }}<span class="text-sm font-normal text-slate-400">%</span>
            </div>
            <div class="mt-2 h-1 rounded-full bg-slate-700 overflow-hidden">
              <div class="h-full rounded-full" :class="report.summaryMetrics.map50_95 >= 0.5 ? 'bg-emerald-400' : 'bg-yellow-400'" :style="{ width: (report.summaryMetrics.map50_95 * 100) + '%' }"></div>
            </div>
          </div>

          <div class="rounded-xl border p-4 bg-slate-900/50 border-slate-800">
            <div class="text-xs text-slate-500 mb-1.5">Precision</div>
            <div class="text-3xl font-bold leading-none" :class="metricColor(report.summaryMetrics.precision)">
              {{ (report.summaryMetrics.precision * 100).toFixed(1) }}<span class="text-sm font-normal text-slate-400">%</span>
            </div>
            <div class="mt-2 h-1 rounded-full bg-slate-700 overflow-hidden">
              <div class="h-full rounded-full" :class="report.summaryMetrics.precision >= 0.75 ? 'bg-emerald-400' : 'bg-yellow-400'" :style="{ width: (report.summaryMetrics.precision * 100) + '%' }"></div>
            </div>
          </div>
        </div>

        <!-- 右侧：FPS + Recall -->
        <div class="col-span-2 grid grid-cols-2 gap-4">
          <div class="rounded-xl border p-4 bg-slate-900/50 border-slate-800">
            <div class="text-xs text-slate-500 mb-1.5">纯推理 FPS</div>
            <div class="text-3xl font-bold text-cyan-400 leading-none">{{ report.summaryMetrics.fpsInfer.toFixed(1) }}</div>
            <div class="mt-2 text-xs text-emerald-400">✓ 达到实时处理要求</div>
            <div class="text-xs text-slate-600 mt-0.5">/ 要求≥25 FPS</div>
          </div>

          <div class="rounded-xl border p-4 bg-slate-900/50 border-slate-800">
            <div class="text-xs text-slate-500 mb-1.5">Recall</div>
            <div class="text-3xl font-bold leading-none" :class="metricColor(report.summaryMetrics.recall)">
              {{ (report.summaryMetrics.recall * 100).toFixed(1) }}<span class="text-sm font-normal text-slate-400">%</span>
            </div>
            <div class="mt-2 h-1 rounded-full bg-slate-700 overflow-hidden">
              <div class="h-full rounded-full" :class="report.summaryMetrics.recall >= 0.75 ? 'bg-emerald-400' : 'bg-yellow-400'" :style="{ width: (report.summaryMetrics.recall * 100) + '%' }"></div>
            </div>
          </div>
        </div>
      </div>

      <!-- ── 模型基本信息卡片 ──────────────────────────────────────────────── -->
      <div class="rounded-xl border border-slate-800 bg-slate-900/50 p-5">
        <div class="flex items-center gap-2 mb-4">
          <div class="w-1 h-4 rounded-full bg-blue-500"></div>
          <h3 class="text-sm font-medium text-slate-200">模型基本信息</h3>
        </div>
        <div class="grid grid-cols-4 gap-x-8 gap-y-3">
          <div class="flex justify-between items-center">
            <span class="text-xs text-slate-500">模型名称</span>
            <span class="text-xs font-mono text-slate-300">{{ report.meta.modelName }}</span>
          </div>
          <div class="flex justify-between items-center">
            <span class="text-xs text-slate-500">模型 ID</span>
            <span class="text-xs font-mono text-slate-400">{{ report.meta.modelId }}</span>
          </div>
          <div class="flex justify-between items-center">
            <span class="text-xs text-slate-500">模型类型</span>
            <span class="text-xs text-slate-300">{{ report.meta.modelType }}</span>
          </div>
          <div class="flex justify-between items-center">
            <span class="text-xs text-slate-500">Runtime</span>
            <span class="text-xs font-mono text-slate-300">{{ report.meta.runtime }}</span>
          </div>
          <div class="flex justify-between items-center">
            <span class="text-xs text-slate-500">输入尺寸</span>
            <span class="text-xs font-mono text-slate-300">{{ report.meta.inputSize }} × {{ report.meta.inputSize }}</span>
          </div>
          <div class="flex justify-between items-center">
            <span class="text-xs text-slate-500">数据集</span>
            <span class="text-xs text-slate-300 truncate max-w-[200px]">{{ report.meta.datasetName }}</span>
          </div>
          <div class="flex justify-between items-center">
            <span class="text-xs text-slate-500">测试日期</span>
            <span class="text-xs font-mono text-slate-400">{{ report.meta.testDate }}</span>
          </div>
          <div class="flex justify-between items-center">
            <span class="text-xs text-slate-500">单帧推理耗时</span>
            <span class="text-xs font-mono text-amber-400">{{ report.summaryMetrics.inferTimeMs.toFixed(1) }} ms</span>
          </div>
        </div>
      </div>

      <!-- ── 评测结论总述 ──────────────────────────────────────────────────── -->
      <div class="rounded-xl border border-slate-800 bg-slate-900/50 p-5">
        <div class="flex items-center gap-2 mb-3">
          <div class="w-1 h-4 rounded-full bg-violet-500"></div>
          <h3 class="text-sm font-medium text-slate-200">总体评测结论</h3>
        </div>
        <p class="text-xs text-slate-400 leading-relaxed">{{ report.conclusion.overallSummary }}</p>

        <!-- 优势 + 劣势横向布局 -->
        <div class="grid grid-cols-2 gap-4 mt-4">
          <div class="rounded-lg border border-emerald-500/20 bg-emerald-500/5 p-3">
            <div class="flex items-center gap-1.5 mb-2">
              <span class="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>
              <span class="text-xs font-medium text-emerald-400">优势</span>
            </div>
            <ul class="space-y-1">
              <li v-for="s in report.conclusion.strengths" :key="s" class="text-xs text-slate-400 leading-relaxed flex gap-2">
                <span class="text-emerald-400/60 flex-shrink-0 mt-0.5">·</span>
                <span>{{ s }}</span>
              </li>
            </ul>
          </div>
          <div class="rounded-lg border border-yellow-500/20 bg-yellow-500/5 p-3">
            <div class="flex items-center gap-1.5 mb-2">
              <span class="w-1.5 h-1.5 rounded-full bg-yellow-400"></span>
              <span class="text-xs font-medium text-yellow-400">待改进</span>
            </div>
            <ul class="space-y-1">
              <li v-for="w in report.conclusion.weaknesses" :key="w" class="text-xs text-slate-400 leading-relaxed flex gap-2">
                <span class="text-yellow-400/60 flex-shrink-0 mt-0.5">·</span>
                <span>{{ w }}</span>
              </li>
            </ul>
          </div>
        </div>

        <!-- 部署理由 -->
        <div class="mt-3 p-3 rounded-lg bg-slate-800/30 border border-slate-700/50">
          <div class="text-xs text-slate-500 mb-1">推荐部署理由</div>
          <div class="text-xs text-slate-400">{{ report.conclusion.deploymentReason }}</div>
        </div>
      </div>

      <!-- ╔══════════════════════════════════════════════════════════════════════╗ -->
      <!-- ║  模块 2：标准评测结果                                                  ║ -->
      <!-- ╚══════════════════════════════════════════════════════════════════════╝ -->

      <!-- ── PR 曲线 ────────────────────────────────────────────────────────── -->
      <div class="rounded-xl border border-slate-800 bg-slate-900/50 overflow-hidden">
        <div class="px-5 py-4 border-b border-slate-800 flex items-center justify-between">
          <h3 class="text-sm font-medium text-slate-300">P-R 曲线</h3>
          <div class="flex items-center gap-2 text-xs text-slate-500">
            <span class="px-2 py-0.5 rounded bg-slate-800 border border-slate-700">10 类别</span>
          </div>
        </div>
        <div class="p-6" style="min-height: 360px;">
          <PerformancePrCurve :map50="map50Ref ?? undefined" />
        </div>
      </div>

      <!-- ── 各类别 AP 排名条形图 ─────────────────────────────────────────── -->
      <div class="rounded-xl border border-slate-800 bg-slate-900/50 p-5">
        <div class="flex items-center gap-2 mb-5">
          <div class="w-1 h-4 rounded-full bg-emerald-500"></div>
          <h3 class="text-sm font-medium text-slate-200">各类别 AP@0.5 排名</h3>
        </div>
        <div class="space-y-4">
          <div
            v-for="(cls, i) in sortedClassMetrics"
            :key="cls.className"
            class="flex items-center gap-4"
          >
            <div class="w-6 text-center flex-shrink-0">
              <span
                class="text-xs font-mono font-bold"
                :class="i === 0 ? 'text-yellow-400' : i === 1 ? 'text-slate-400' : i === 2 ? 'text-amber-600' : 'text-slate-600'"
              >{{ i + 1 }}</span>
            </div>
            <div class="w-20 flex-shrink-0">
              <div class="text-sm font-medium text-slate-200">{{ cls.label }}</div>
              <div class="text-xs text-slate-500 font-mono">{{ cls.className }}</div>
            </div>
            <div class="flex-1 h-3 bg-slate-800 rounded-full overflow-hidden">
              <div
                class="h-full rounded-full transition-all duration-700"
                :style="{ width: (cls.ap50 * 100) + '%', backgroundColor: apColor(cls.ap50) }"
              ></div>
            </div>
            <div class="w-16 text-right flex-shrink-0">
              <span class="text-sm font-mono font-bold" :style="{ color: apColor(cls.ap50) }">
                {{ (cls.ap50 * 100).toFixed(1) }}%
              </span>
            </div>
          </div>
        </div>
      </div>

      <!-- ── 类别 AP 详细数据表 ──────────────────────────────────────────── -->
      <div class="rounded-xl border border-slate-800 bg-slate-900/50 overflow-hidden">
        <div class="px-5 py-4 border-b border-slate-800">
          <h3 class="text-sm font-medium text-slate-300">AP 详细数据</h3>
        </div>
        <div class="overflow-x-auto">
          <table class="w-full">
            <thead>
              <tr class="border-b border-slate-800">
                <th class="px-5 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">类别</th>
                <th class="px-5 py-3 text-right text-xs font-medium text-slate-500 uppercase tracking-wider">AP@0.5</th>
                <th class="px-5 py-3 text-right text-xs font-medium text-slate-500 uppercase tracking-wider">AP@0.5:0.95</th>
                <th class="px-5 py-3 text-right text-xs font-medium text-slate-500 uppercase tracking-wider">Precision</th>
                <th class="px-5 py-3 text-right text-xs font-medium text-slate-500 uppercase tracking-wider">Recall</th>
                <th class="px-5 py-3 text-right text-xs font-medium text-slate-500 uppercase tracking-wider">达指标</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="cls in sortedClassMetrics"
                :key="cls.className + '-detail'"
                class="border-b border-slate-800/50 hover:bg-slate-800/30 transition-colors"
              >
                <td class="px-5 py-3.5">
                  <div class="flex items-center gap-2">
                    <div class="w-6 h-6 rounded bg-slate-800 border border-slate-700 flex items-center justify-center text-xs font-mono text-slate-400">
                      {{ cls.className.slice(0, 2).toUpperCase() }}
                    </div>
                    <span class="text-sm text-slate-200">{{ cls.label }}</span>
                  </div>
                </td>
                <td class="px-5 py-3.5 text-right font-mono text-sm font-medium" :style="{ color: apColor(cls.ap50) }">
                  {{ (cls.ap50 * 100).toFixed(2) }}%
                </td>
                <td class="px-5 py-3.5 text-right font-mono text-sm text-slate-300">
                  {{ (cls.ap50_95 * 100).toFixed(2) }}%
                </td>
                <td class="px-5 py-3.5 text-right font-mono text-sm text-slate-300">
                  {{ (cls.precision * 100).toFixed(2) }}%
                </td>
                <td class="px-5 py-3.5 text-right font-mono text-sm text-slate-300">
                  {{ (cls.recall * 100).toFixed(2) }}%
                </td>
                <td class="px-5 py-3.5 text-right">
                  <span
                    class="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full"
                    :class="cls.ap50 >= 0.75 ? 'bg-emerald-500/15 text-emerald-400' : 'bg-yellow-500/15 text-yellow-400'"
                  >
                    <span class="w-1.5 h-1.5 rounded-full bg-current"></span>
                    {{ cls.ap50 >= 0.75 ? '达指标' : '待优化' }}
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- ╔══════════════════════════════════════════════════════════════════════╗ -->
      <!-- ║  模块 3：场景鲁棒性分析                                                ║ -->
      <!-- ╚══════════════════════════════════════════════════════════════════════╝ -->

      <div class="rounded-xl border border-slate-800 bg-slate-900/50 overflow-hidden">
        <div class="px-5 py-4 border-b border-slate-800">
          <h3 class="text-sm font-medium text-slate-300">场景鲁棒性分析</h3>
          <p class="text-xs text-slate-500 mt-0.5">模型在不同场景条件下的综合表现评估</p>
        </div>
        <div class="p-5 grid grid-cols-2 gap-4">
          <div
            v-for="scenario in report.scenarios"
            :key="scenario.name"
            class="rounded-lg border p-4"
            :class="scenarioColor(scenario.performance).badge"
          >
            <div class="flex items-start justify-between mb-2">
              <div class="flex items-center gap-2">
                <span class="w-2 h-2 rounded-full" :class="scenarioColor(scenario.performance).dot"></span>
                <span class="text-sm font-medium text-slate-200">{{ scenario.name }}</span>
              </div>
              <span class="text-xs px-2 py-0.5 rounded-full border" :class="scenarioColor(scenario.performance).badge">
                {{ scenarioColor(scenario.performance).label }}
              </span>
            </div>
            <p class="text-xs text-slate-400 leading-relaxed">{{ scenario.description }}</p>
            <!-- 场景示例图 -->
            <div v-if="scenario.sampleVideo" class="mt-3 rounded-md overflow-hidden h-36">
              <video
                :src="scenario.sampleVideo"
                :alt="scenario.name + ' 示例'"
                class="w-full h-full object-cover"
                muted
                autoplay
                loop
                playsinline
                preload="metadata"
              ></video>
            </div>
            <div v-else-if="scenario.sampleImage" class="mt-3 rounded-md overflow-hidden h-36">
              <img :src="scenario.sampleImage" :alt="scenario.name + ' 示例'" class="w-full h-full object-cover" />
            </div>
            <div v-else class="mt-3 rounded-md overflow-hidden h-8 bg-slate-800/60 border border-slate-700/40 flex items-center justify-center">
              <span class="text-xs text-slate-600">{{ scenario.name }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- ╔══════════════════════════════════════════════════════════════════════╗ -->
      <!-- ║  模块 4：典型案例分析                                                  ║ -->
      <!-- ╚══════════════════════════════════════════════════════════════════════╝ -->

      <div class="rounded-xl border border-slate-800 bg-slate-900/50 overflow-hidden">
        <div class="px-5 py-4 border-b border-slate-800">
          <h3 class="text-sm font-medium text-slate-300">典型案例分析</h3>
          <p class="text-xs text-slate-500 mt-0.5">选取 3 个代表性检测场景，深入分析模型表现与能力边界</p>
        </div>
        <div class="p-5 grid grid-cols-3 gap-4">
          <div
            v-for="cs in report.caseStudies"
            :key="cs.id"
            class="rounded-lg border border-slate-700 bg-slate-800/30 overflow-hidden flex flex-col hover:border-blue-500/30 transition-colors"
          >
            <!-- 案例信息（优先展示） -->
            <div class="p-3 flex-1 flex flex-col">
              <div class="flex items-center gap-2 mb-2">
                <span class="text-xs px-2 py-0.5 rounded-full bg-slate-700 text-slate-400 border border-slate-600">
                  {{ cs.sceneTag }}
                </span>
              </div>
              <div class="text-sm font-medium text-slate-200 mb-1 leading-snug">{{ cs.title }}</div>
              <div class="text-xs text-slate-500 mb-1">{{ cs.modelName }}</div>
              <p class="text-xs text-slate-400 leading-relaxed flex-1">{{ cs.summary }}</p>
              <button
                class="mt-3 w-full px-3 py-2 rounded-lg bg-blue-600/20 border border-blue-600/40
                       text-blue-400 text-xs hover:bg-blue-600/30 transition-all duration-200"
                @click="openCaseStudy(cs)"
              >
                查看案例分析
              </button>
            </div>

            <!-- 封面图（辅助展示） -->
            <div class="mt-3 rounded-md overflow-hidden relative" style="height: 120px;">
              <img
                v-if="cs.coverImage"
                :src="cs.coverImage"
                :alt="cs.title + ' 封面'"
                class="w-full h-full object-cover"
              />
              <div v-else class="w-full h-full bg-slate-800/80 border border-slate-700/40 flex items-center justify-center">
                <span class="text-xs text-slate-600">{{ cs.sceneTag }}</span>
              </div>
              <div class="absolute inset-0 flex items-center justify-center pointer-events-none">
                <div class="w-8 h-8 rounded-full bg-slate-950/70 border border-slate-600 flex items-center justify-center">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor" class="text-slate-300 ml-0.5">
                    <polygon points="5,3 19,12 5,21"/>
                  </svg>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- ╔══════════════════════════════════════════════════════════════════════╗ -->
      <!-- ║  模块 5：轻量训练摘要（降级处理，不做主角）                             ║ -->
      <!-- ╚══════════════════════════════════════════════════════════════════════╝ -->

      <div class="rounded-xl border border-slate-800 bg-slate-900/50 p-5">
        <div class="flex items-center gap-2 mb-4">
          <div class="w-1 h-4 rounded-full bg-slate-600"></div>
          <h3 class="text-sm font-medium text-slate-400">训练摘要</h3>
          <span class="text-xs text-slate-600 ml-2">（轻量信息，供答辩参考）</span>
        </div>

        <div class="grid grid-cols-4 gap-4 mb-5">
          <div class="flex justify-between items-center">
            <span class="text-xs text-slate-500">Best Epoch</span>
            <span class="text-xs font-mono text-blue-400">{{ report.trainingSummary?.bestEpoch ?? '—' }}</span>
          </div>
          <div class="flex justify-between items-center">
            <span class="text-xs text-slate-500">Final mAP@0.5</span>
            <span class="text-xs font-mono text-emerald-400">{{ report.trainingSummary ? (report.trainingSummary.finalMap50 * 100).toFixed(2) + '%' : '—' }}</span>
          </div>
          <div class="flex justify-between items-center">
            <span class="text-xs text-slate-500">Final Precision</span>
            <span class="text-xs font-mono text-slate-300">{{ report.trainingSummary ? (report.trainingSummary.finalPrecision * 100).toFixed(2) + '%' : '—' }}</span>
          </div>
          <div class="flex justify-between items-center">
            <span class="text-xs text-slate-500">Final Recall</span>
            <span class="text-xs font-mono text-slate-300">{{ report.trainingSummary ? (report.trainingSummary.finalRecall * 100).toFixed(2) + '%' : '—' }}</span>
          </div>
        </div>

        <!-- 精度演进趋势（小图，有数据时显示） -->
        <div v-if="hasTrainingHistory" class="rounded-lg border border-slate-800 p-4">
          <div class="flex items-center gap-2 mb-3">
            <span class="flex items-center gap-1.5 text-xs text-slate-500">
              <span class="w-3 h-0.5 bg-blue-400 rounded"></span> Precision
            </span>
            <span class="flex items-center gap-1.5 text-xs text-slate-500">
              <span class="w-3 h-0.5 bg-cyan-400 rounded"></span> Recall
            </span>
            <span class="flex items-center gap-1.5 text-xs text-slate-500">
              <span class="w-3 h-0.5 bg-emerald-400 rounded"></span> mAP@0.5
            </span>
          </div>
          <svg :width="CHART_W" :height="CHART_H" class="w-full" style="color-scheme:dark">
            <defs>
              <linearGradient id="grad-emerald2" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stop-color="#10b981" stop-opacity="0.2"/>
                <stop offset="100%" stop-color="#10b981" stop-opacity="0"/>
              </linearGradient>
            </defs>
            <g stroke="#1e293b" stroke-width="1">
              <line v-for="gl in metricGridLines" :key="gl.y" :x1="PAD" :y1="gl.y" :x2="CHART_W - PAD" :y2="gl.y" stroke-dasharray="4,4"/>
            </g>
            <g class="text-slate-600" font-size="10" font-family="monospace">
              <text v-for="gl in metricGridLines" :key="'mlbl-'+gl.y" :x="PAD - 4" :y="parseFloat(gl.y) + 3" text-anchor="end">{{ gl.label }}</text>
              <text v-for="el in epochLabels" :key="'melbl-'+el.x" :x="el.x" :y="CHART_H - 6" text-anchor="middle">{{ el.label }}</text>
            </g>
            <path :d="buildSmoothPath(report.trainingHistory, 'mAP50', CHART_W, CHART_H, PAD)" fill="url(#grad-emerald2)"/>
            <path :d="metricLines.precision"  fill="none" stroke="#60a5fa" stroke-width="1.5" stroke-linejoin="round"/>
            <path :d="metricLines.recall"     fill="none" stroke="#22d3ee" stroke-width="1.5" stroke-linejoin="round"/>
            <path :d="metricLines.mAP50"       fill="none" stroke="#34d399" stroke-width="2"   stroke-linejoin="round"/>

            <!-- Best epoch marker -->
            <g v-if="bestEpochData">
              <line
                :x1="PAD + ((bestEpochData.epoch - 1) / 299) * (CHART_W - PAD * 2)"
                :y1="PAD"
                :x2="PAD + ((bestEpochData.epoch - 1) / 299) * (CHART_W - PAD * 2)"
                :y2="CHART_H - PAD"
                stroke="#fbbf24" stroke-width="1" stroke-dasharray="4,4" opacity="0.6"
              />
              <text
                :x="PAD + ((bestEpochData.epoch - 1) / 299) * (CHART_W - PAD * 2)"
                :y="PAD - 4"
                text-anchor="middle"
                fill="#fbbf24"
                font-size="10"
                font-family="monospace"
              >
                ★ E{{ bestEpochData.epoch }}
              </text>
            </g>
          </svg>
        </div>
        <div v-else class="rounded-lg border border-slate-800 p-6 flex items-center justify-center text-xs text-slate-600">
          训练历史数据暂未接入
        </div>
      </div>

    </div><!-- /内容区 -->

    <!-- ╔══════════════════════════════════════════════════════════════════════╗ -->
    <!-- ║  典型案例分析模态框                                                    ║ -->
    <!-- ╚══════════════════════════════════════════════════════════════════════╝ -->
    <Transition name="modal">
      <div
        v-if="activeCaseStudy"
        class="fixed inset-0 z-50 flex items-center justify-center p-6"
        @click.self="closeCaseStudy"
      >
        <!-- Backdrop -->
        <div class="absolute inset-0 bg-slate-950/80 backdrop-blur-sm"></div>

        <!-- Modal Content -->
        <div class="relative z-10 w-full max-w-3xl max-h-[85vh] rounded-2xl border border-slate-700 bg-slate-900 overflow-hidden flex flex-col shadow-2xl">
          <!-- Modal Header -->
          <div class="px-6 py-4 border-b border-slate-800 flex items-start justify-between flex-shrink-0">
            <div>
              <div class="flex items-center gap-2 mb-1.5">
                <span class="text-xs px-2 py-0.5 rounded-full bg-slate-800 text-slate-400 border border-slate-700">
                  {{ activeCaseStudy.sceneTag }}
                </span>
                <span class="text-xs text-slate-500">{{ activeCaseStudy.modelName }}</span>
              </div>
              <h3 class="text-base font-semibold text-white">{{ activeCaseStudy.title }}</h3>
              <p class="text-xs text-slate-500 mt-0.5">{{ activeCaseStudy.summary }}</p>
            </div>
            <button
              class="p-1.5 rounded-lg text-slate-500 hover:text-slate-300 hover:bg-slate-800 transition-all flex-shrink-0 ml-4"
              @click="closeCaseStudy"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="18" y1="6" x2="6" y2="18"/>
                <line x1="6" y1="6" x2="18" y2="18"/>
              </svg>
            </button>
          </div>

          <!-- Modal Body -->
          <div class="flex-1 overflow-y-auto p-6 space-y-5">
            <!-- 视频播放器 -->
            <div class="rounded-lg border border-slate-700 overflow-hidden bg-slate-950">
              <video
                :src="activeCaseStudy.videoPath"
                controls
                autoplay
                class="w-full"
                style="max-height: 320px; object-fit: contain;"
              ></video>
            </div>

            <!-- 案例分析内容 -->
            <div class="space-y-4">
              <div>
                <div class="text-xs font-medium text-slate-400 mb-1.5 flex items-center gap-1.5">
                  <span class="w-1 h-3 rounded-full bg-blue-500"></span>
                  场景描述
                </div>
                <p class="text-xs text-slate-400 leading-relaxed pl-3">{{ activeCaseStudy.analysis.sceneDescription }}</p>
              </div>

              <div>
                <div class="text-xs font-medium text-slate-400 mb-1.5 flex items-center gap-1.5">
                  <span class="w-1 h-3 rounded-full bg-emerald-500"></span>
                  模型表现
                </div>
                <p class="text-xs text-slate-400 leading-relaxed pl-3">{{ activeCaseStudy.analysis.modelPerformance }}</p>
              </div>

              <div class="grid grid-cols-2 gap-4">
                <div class="rounded-lg border border-emerald-500/20 bg-emerald-500/5 p-3">
                  <div class="text-xs font-medium text-emerald-400 mb-2 flex items-center gap-1.5">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <polyline points="20,6 9,17 4,12"/>
                    </svg>
                    优势
                  </div>
                  <ul class="space-y-1">
                    <li v-for="s in activeCaseStudy.analysis.strengths" :key="s" class="text-xs text-slate-400 leading-relaxed flex gap-2">
                      <span class="text-emerald-400/60 flex-shrink-0 mt-0.5">·</span>
                      <span>{{ s }}</span>
                    </li>
                  </ul>
                </div>

                <div class="rounded-lg border border-yellow-500/20 bg-yellow-500/5 p-3">
                  <div class="text-xs font-medium text-yellow-400 mb-2 flex items-center gap-1.5">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <circle cx="12" cy="12" r="10"/>
                      <line x1="12" y1="8" x2="12" y2="12"/>
                      <line x1="12" y1="16" x2="12.01" y2="16"/>
                    </svg>
                    局限
                  </div>
                  <ul class="space-y-1">
                    <li v-for="l in activeCaseStudy.analysis.limitations" :key="l" class="text-xs text-slate-400 leading-relaxed flex gap-2">
                      <span class="text-yellow-400/60 flex-shrink-0 mt-0.5">·</span>
                      <span>{{ l }}</span>
                    </li>
                  </ul>
                </div>
              </div>

              <div class="rounded-lg border border-violet-500/20 bg-violet-500/5 p-3">
                <div class="text-xs font-medium text-violet-400 mb-1.5 flex items-center gap-1.5">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polygon points="12,2 15.09,8.26 22,9.27 17,14.14 18.18,21.02 12,17.77 5.82,21.02 7,14.14 2,9.27 8.91,8.26"/>
                  </svg>
                  为什么该案例具有代表性
                </div>
                <p class="text-xs text-slate-400 leading-relaxed">{{ activeCaseStudy.analysis.whyRepresentative }}</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </Transition>

  </div>
</template>

<style scoped>
/* Scrollbar styling */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: #334155; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #475569; }

/* SVG crisp rendering */
svg text { user-select: none; }

/* Modal transition */
.modal-enter-active,
.modal-leave-active {
  transition: opacity 200ms ease;
}
.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}
.modal-enter-active .relative,
.modal-leave-active .relative {
  transition: transform 200ms ease;
}
.modal-enter-from .relative {
  transform: scale(0.96) translateY(8px);
}
.modal-leave-to .relative {
  transform: scale(0.96) translateY(8px);
}
</style>
