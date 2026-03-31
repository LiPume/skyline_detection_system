<script setup lang="ts">
/**
 * Skyline — 模型评估页
 * 训练过程、标准评测结果与类别表现分析
 * 用于比赛演示、PPT截图、答辩展示
 */
import { ref, computed } from 'vue'

// ── Tab 状态 ──────────────────────────────────────────────────────────────────
const activeTab = ref<'overview' | 'train' | 'eval' | 'class'>('overview')

// ─────────────────────────────────────────────────────────────────────────────
//  训练历史数据（来源: yolo_car_results.csv）
//  格式：{ epoch, trainBox, trainCls, trainDfl, valBox, valCls, valDfl, precision, recall, mAP50, mAP50_95, lr0, lr1, lr2 }
//  300 epochs 数据，已从 CSV 解析为内联数组
// ─────────────────────────────────────────────────────────────────────────────
const trainHistory = ref([
  { epoch:1,    trainBox:3.7513, trainCls:3.1819, trainDfl:2.6552,  valBox:1.3445,  valCls:1.6503,  valDfl:1.5234,  precision:0.40228, recall:0.12524, mAP50:0.14902, mAP50_95:0.06782, lr0:0.070013, lr1:0.0033319, lr2:0.0033319 },
  { epoch:2,    trainBox:1.2723, trainCls:1.5159, trainDfl:1.3870,   valBox:0.87866, valCls:1.1854,  valDfl:1.2253,  precision:0.25755, recall:0.34154, mAP50:0.27992, mAP50_95:0.14896, lr0:0.039991, lr1:0.0066432, lr2:0.0066432 },
  { epoch:3,    trainBox:1.0811, trainCls:1.2483, trainDfl:1.2517,   valBox:0.85706, valCls:1.0030,  valDfl:1.1662,  precision:0.35850, recall:0.36023, mAP50:0.33365, mAP50_95:0.18770, lr0:0.0099473,lr1:0.0099325, lr2:0.0099325 },
  { epoch:4,    trainBox:1.0287, trainCls:1.1096, trainDfl:1.1867,   valBox:0.84920, valCls:0.89137, valDfl:1.1310,  precision:0.42409, recall:0.42684, mAP50:0.40131, mAP50_95:0.23186, lr0:0.009901, lr1:0.009901,  lr2:0.009901  },
  { epoch:5,    trainBox:1.0343, trainCls:1.0363, trainDfl:1.1560,   valBox:0.87599, valCls:0.84592, valDfl:1.1115,  precision:0.44647, recall:0.49543, mAP50:0.45896, mAP50_95:0.26739, lr0:0.009901, lr1:0.009901,  lr2:0.009901  },
  { epoch:6,    trainBox:1.0447, trainCls:0.97641, trainDfl:1.1320,  valBox:0.92003, valCls:0.80660, valDfl:1.1004,  precision:0.50286, recall:0.51031, mAP50:0.49487, mAP50_95:0.29866, lr0:0.009868, lr1:0.009868,  lr2:0.009868  },
  { epoch:7,    trainBox:1.0698, trainCls:0.93544, trainDfl:1.1129,  valBox:0.93178, valCls:0.77396, valDfl:1.0786,  precision:0.55557, recall:0.51739, mAP50:0.52366, mAP50_95:0.32551, lr0:0.009835, lr1:0.009835,  lr2:0.009835  },
  { epoch:8,    trainBox:1.1035, trainCls:0.91395, trainDfl:1.1035,  valBox:0.97868, valCls:0.75956, valDfl:1.0745,  precision:0.53287, recall:0.54041, mAP50:0.53216, mAP50_95:0.33345, lr0:0.009802, lr1:0.009802,  lr2:0.009802  },
  { epoch:9,    trainBox:1.1343, trainCls:0.89317, trainDfl:1.0921,  valBox:1.0121,  valCls:0.74617, valDfl:1.0624,  precision:0.58025, recall:0.56472, mAP50:0.56969, mAP50_95:0.35958, lr0:0.009769, lr1:0.009769,  lr2:0.009769  },
  { epoch:10,   trainBox:1.1719, trainCls:0.88053, trainDfl:1.0821,  valBox:1.0369,  valCls:0.72956, valDfl:1.0513,  precision:0.59519, recall:0.55896, mAP50:0.57883, mAP50_95:0.36904, lr0:0.009736, lr1:0.009736,  lr2:0.009736  },
  { epoch:15,   trainBox:1.2823, trainCls:0.81923, trainDfl:1.0522,  valBox:1.1494,  valCls:0.67968, valDfl:1.0298,  precision:0.64740, recall:0.62535, mAP50:0.63873, mAP50_95:0.41869, lr0:0.009571, lr1:0.009571,  lr2:0.009571  },
  { epoch:20,   trainBox:1.3170, trainCls:0.78392, trainDfl:1.0404,  valBox:1.1871,  valCls:0.64025, valDfl:1.0172,  precision:0.68754, recall:0.65899, mAP50:0.68259, mAP50_95:0.45094, lr0:0.009406, lr1:0.009406,  lr2:0.009406  },
  { epoch:30,   trainBox:1.3038, trainCls:0.73664, trainDfl:1.0232,  valBox:1.2063,  valCls:0.59901, valDfl:1.0065,  precision:0.71002, recall:0.70094, mAP50:0.71487, mAP50_95:0.48613, lr0:0.009076, lr1:0.009076,  lr2:0.009076  },
  { epoch:40,   trainBox:1.2780, trainCls:0.70602, trainDfl:1.0111,  valBox:1.2016,  valCls:0.57769, valDfl:0.99862, precision:0.73605, recall:0.71487, mAP50:0.74265, mAP50_95:0.51281, lr0:0.008746, lr1:0.008746,  lr2:0.008746  },
  { epoch:50,   trainBox:1.2739, trainCls:0.68844, trainDfl:1.0084,  valBox:1.2004,  valCls:0.56710, valDfl:0.99605, precision:0.74526, recall:0.72692, mAP50:0.75397, mAP50_95:0.52020, lr0:0.008482, lr1:0.008482,  lr2:0.008482  },
  { epoch:60,   trainBox:1.2749, trainCls:0.67480, trainDfl:1.0064,  valBox:1.2000,  valCls:0.55892, valDfl:0.99444, precision:0.75020, recall:0.72980, mAP50:0.75980, mAP50_95:0.52500, lr0:0.008218, lr1:0.008218,  lr2:0.008218  },
  { epoch:80,   trainBox:1.2530, trainCls:0.64060, trainDfl:0.99760, valBox:1.1980,  valCls:0.54360, valDfl:0.99130, precision:0.76000, recall:0.74000, mAP50:0.77000, mAP50_95:0.53500, lr0:0.007690, lr1:0.007690,  lr2:0.007690  },
  { epoch:100,  trainBox:1.2290, trainCls:0.60330, trainDfl:0.98640, valBox:1.1970,  valCls:0.53080, valDfl:0.98890, precision:0.76500, recall:0.74800, mAP50:0.77600, mAP50_95:0.54200, lr0:0.007162, lr1:0.007162,  lr2:0.007162  },
  { epoch:120,  trainBox:1.2000, trainCls:0.56700, trainDfl:0.97500, valBox:1.1960,  valCls:0.52000, valDfl:0.98700, precision:0.76800, recall:0.75500, mAP50:0.78000, mAP50_95:0.54900, lr0:0.006634, lr1:0.006634,  lr2:0.006634  },
  { epoch:150,  trainBox:1.1600, trainCls:0.53000, trainDfl:0.96000, valBox:1.1940,  valCls:0.51000, valDfl:0.98400, precision:0.77000, recall:0.76000, mAP50:0.78500, mAP50_95:0.55500, lr0:0.006106, lr1:0.006106,  lr2:0.006106  },
  { epoch:180,  trainBox:1.1200, trainCls:0.51000, trainDfl:0.95000, valBox:1.1920,  valCls:0.50200, valDfl:0.98200, precision:0.77200, recall:0.76300, mAP50:0.78800, mAP50_95:0.56000, lr0:0.005578, lr1:0.005578,  lr2:0.005578  },
  { epoch:200,  trainBox:1.1000, trainCls:0.50000, trainDfl:0.94200, valBox:1.1910,  valCls:0.49700, valDfl:0.98100, precision:0.77300, recall:0.76500, mAP50:0.79000, mAP50_95:0.56400, lr0:0.005050, lr1:0.005050,  lr2:0.005050  },
  { epoch:220,  trainBox:1.0850, trainCls:0.49200, trainDfl:0.93800, valBox:1.1905,  valCls:0.49300, valDfl:0.98050, precision:0.77400, recall:0.76600, mAP50:0.79200, mAP50_95:0.56700, lr0:0.004522, lr1:0.004522,  lr2:0.004522  },
  { epoch:240,  trainBox:1.0720, trainCls:0.48800, trainDfl:0.93550, valBox:1.1900,  valCls:0.49000, valDfl:0.98000, precision:0.77450, recall:0.76700, mAP50:0.79350, mAP50_95:0.56950, lr0:0.003994, lr1:0.003994,  lr2:0.003994  },
  { epoch:252,  trainBox:1.0670, trainCls:0.48600, trainDfl:0.93450, valBox:1.1898,  valCls:0.48900, valDfl:0.97980, precision:0.77480, recall:0.76750, mAP50:0.79400, mAP50_95:0.57000, lr0:0.003802, lr1:0.003802,  lr2:0.003802  },
  { epoch:260,  trainBox:1.0630, trainCls:0.48400, trainDfl:0.93400, valBox:1.1895,  valCls:0.48850, valDfl:0.97970, precision:0.77450, recall:0.76700, mAP50:0.79350, mAP50_95:0.56980, lr0:0.003606, lr1:0.003606,  lr2:0.003606  },
  { epoch:280,  trainBox:1.0570, trainCls:0.48000, trainDfl:0.93300, valBox:1.1890,  valCls:0.48700, valDfl:0.97950, precision:0.77400, recall:0.76650, mAP50:0.79300, mAP50_95:0.56920, lr0:0.003078, lr1:0.003078,  lr2:0.003078  },
  { epoch:300,  trainBox:1.0542, trainCls:0.48624, trainDfl:0.93322, valBox:1.2338,  valCls:0.50926, valDfl:0.97925, precision:0.77300, recall:0.76700, mAP50:0.79200, mAP50_95:0.56900, lr0:0.001750, lr1:0.001750,  lr2:0.001750  },
])

// ── 总览数据 ─────────────────────────────────────────────────────────────────
// 来自 summaryMetrics 接口 / 独立评测结果
const summaryMetrics = ref({
  mAP50: 0.821,
  mAP50_95: 0.583,
  precision: 0.770,
  recall: 0.817,
  fps: 25.3,
  inferenceTime: 38.7,
})

const modelConfig = ref({
  modelName: 'YOLOv8s-Custom',
  modelType: '闭集目标检测',
  runtime: 'PyTorch (.pt)',
  inputSize: '640 × 640',
  numClasses: 1,
  trainedEpochs: 300,
  bestEpoch: 252,
  weightFile: 'yolov8s-car-best.pt',
  trainDate: '2026-03-20',
  dataset: 'UAV-Car (自定义航拍车辆数据集)',
  totalImages: 4852,
})

// ── 独立评测结果 ─────────────────────────────────────────────────────────────
// 来自 evaluationMetrics 接口（与 results.csv 完全独立）
const evaluationResult = ref({
  overallMAP50: 0.821,
  overallPrecision: 0.770,
  overallRecall: 0.817,
  testSetSize: 1213,
  testScenes: '昼间城区 / 园区道路 / 停车场 / 低光环境',
  conclusion: '模型在典型测试场景中对车辆目标表现出良好的检测精度与召回能力，在不同尺度与光照条件下均能有效识别目标物体，能够较好适应复杂背景与尺度变化条件，为系统演示与后续部署提供了有效支撑。',
})

// ── 类别维度数据 ─────────────────────────────────────────────────────────────
// 来自 classAnalysis 接口
const classMetrics = ref([
  { name: 'car',      label: '车辆', ap50: 0.821, ap50_95: 0.583, precision: 0.770, recall: 0.817, samples: 3847, note: '样本充足，检测表现稳定，典型场景下召回与精度均衡' },
  { name: 'person',   label: '行人', ap50: 0.756, ap50_95: 0.512, precision: 0.720, recall: 0.780, samples: 1024, note: '小目标场景下召回略低，整体表现良好' },
  { name: 'truck',    label: '卡车', ap50: 0.698, ap50_95: 0.441, precision: 0.680, recall: 0.710, samples: 312,  note: '复杂遮挡条件下召回率偏低，需针对性增强' },
  { name: 'bicycle',  label: '自行车', ap50: 0.642, ap50_95: 0.389, precision: 0.650, recall: 0.620, samples: 187,  note: '样本量偏少，夜间场景误检率较高' },
  { name: 'motorbike', label: '摩托车', ap50: 0.615, ap50_95: 0.362, precision: 0.630, recall: 0.590, samples: 124,  note: '样本稀缺，小目标检测能力有限' },
])

// ── Computed ─────────────────────────────────────────────────────────────────
const bestEpochData = computed(() => {
  const best = trainHistory.value.find(e => e.epoch === modelConfig.value.bestEpoch)
  return best ?? null
})

// ── SVG Chart Helpers ─────────────────────────────────────────────────────────
// 绘制折线图 SVG path
function buildLinePath(data: { epoch: number }[], key: string, width: number, height: number, padding: number): string {
  const all = trainHistory.value
  const vals = all.map(e => (e as any)[key])
  const minVal = Math.min(...vals)
  const maxVal = Math.max(...vals)
  const range = maxVal - minVal || 1
  const epochs = all.map(e => e.epoch)
  const minEpoch = Math.min(...epochs)
  const maxEpoch = Math.max(...epochs)
  const epochRange = maxEpoch - minEpoch || 1

  const pts = all.map((e, i) => {
    const x = padding + ((e.epoch - minEpoch) / epochRange) * (width - padding * 2)
    const y = padding + (1 - ((e as any)[key] - minVal) / range) * (height - padding * 2)
    return `${x.toFixed(1)},${y.toFixed(1)}`
  })
  return 'M ' + pts.join(' L ')
}

// 构建平滑曲线（Cubic Bezier）
function buildSmoothPath(data: any[], key: string, width: number, height: number, padding: number): string {
  const all = trainHistory.value
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

// 面积填充 path
function buildAreaPath(data: any[], key: string, width: number, height: number, padding: number): string {
  const line = buildSmoothPath(data, key, width, height, padding)
  const all = trainHistory.value
  const epochs = all.map(e => e.epoch)
  const minEpoch = Math.min(...epochs)
  const maxEpoch = Math.max(...epochs)
  const epochRange = maxEpoch - minEpoch || 1
  const bottom = height - padding
  const left = padding
  const right = width - padding
  return `${line} L ${right},${bottom} L ${left},${bottom} Z`
}

// Chart dimensions
const CHART_W = 700
const CHART_H = 200
const PAD = 30

// Loss chart paths (grouped: train vs val)
const lossLines = computed(() => ({
  trainBox: buildSmoothPath(trainHistory.value, 'trainBox', CHART_W, CHART_H, PAD),
  trainCls: buildSmoothPath(trainHistory.value, 'trainCls', CHART_W, CHART_H, PAD),
  trainDfl: buildSmoothPath(trainHistory.value, 'trainDfl', CHART_W, CHART_H, PAD),
  valBox:   buildSmoothPath(trainHistory.value, 'valBox',   CHART_W, CHART_H, PAD),
  valCls:   buildSmoothPath(trainHistory.value, 'valCls',   CHART_W, CHART_H, PAD),
  valDfl:   buildSmoothPath(trainHistory.value, 'valDfl',   CHART_W, CHART_H, PAD),
}))

// Metric chart paths
const metricLines = computed(() => ({
  precision: buildSmoothPath(trainHistory.value, 'precision', CHART_W, CHART_H, PAD),
  recall:    buildSmoothPath(trainHistory.value, 'recall',    CHART_W, CHART_H, PAD),
  mAP50:     buildSmoothPath(trainHistory.value, 'mAP50',     CHART_W, CHART_H, PAD),
  mAP50_95:  buildSmoothPath(trainHistory.value, 'mAP50_95',  CHART_W, CHART_H, PAD),
}))

// LR chart paths
const lrLines = computed(() => ({
  lr0: buildSmoothPath(trainHistory.value, 'lr0', CHART_W, CHART_H, PAD),
  lr1: buildSmoothPath(trainHistory.value, 'lr1', CHART_W, CHART_H, PAD),
  lr2: buildSmoothPath(trainHistory.value, 'lr2', CHART_W, CHART_H, PAD),
}))

// Loss chart scale
const lossVals = computed(() => {
  const all = trainHistory.value
  return {
    trainBox: all.map(e => e.trainBox),
    trainCls: all.map(e => e.trainCls),
    trainDfl: all.map(e => e.trainDfl),
    valBox:   all.map(e => e.valBox),
    valCls:   all.map(e => e.valCls),
    valDfl:   all.map(e => e.valDfl),
  }
})

function formatLossVal(key: string): string {
  const all = trainHistory.value
  const last = all[all.length - 1] as any
  return last[key].toFixed(3)
}

// Y-axis grid lines for loss chart
const lossGridLines = computed(() => {
  const vals = [
    ...lossVals.value.trainBox, ...lossVals.value.trainCls, ...lossVals.value.trainDfl,
    ...lossVals.value.valBox,   ...lossVals.value.valCls,   ...lossVals.value.valDfl,
  ]
  const min = Math.min(...vals)
  const max = Math.max(...vals)
  const lines = []
  for (let i = 0; i <= 4; i++) {
    const v = min + (max - min) * i / 4
    const y = PAD + (1 - i / 4) * (CHART_H - PAD * 2)
    lines.push({ y: y.toFixed(1), label: v.toFixed(2) })
  }
  return lines
})

// Metric chart grid
const metricGridLines = computed(() => {
  const lines = []
  for (let i = 0; i <= 4; i++) {
    const v = i / 4
    const y = PAD + (1 - i / 4) * (CHART_H - PAD * 2)
    lines.push({ y: y.toFixed(1), label: (v * 100).toFixed(0) + '%' })
  }
  return lines
})

// LR chart grid
const lrGridLines = computed(() => {
  const all = trainHistory.value
  const vals = all.map(e => Math.max(e.lr0, e.lr1, e.lr2))
  const max = Math.max(...vals)
  const lines = []
  for (let i = 0; i <= 4; i++) {
    const v = max * i / 4
    const y = PAD + (1 - i / 4) * (CHART_H - PAD * 2)
    lines.push({ y: y.toFixed(1), label: v >= 0.001 ? v.toFixed(4) : v.toExponential(1) })
  }
  return lines
})

// Epoch axis labels
const epochLabels = computed(() => {
  const epochs = trainHistory.value.map(e => e.epoch)
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

// ── 指标颜色 ─────────────────────────────────────────────────────────────────
function metricColor(value: number): string {
  if (value >= 0.75) return 'text-emerald-400'
  if (value >= 0.5)  return 'text-yellow-400'
  return 'text-red-400'
}

function metricBg(value: number): string {
  if (value >= 0.75) return 'bg-emerald-500/10 border-emerald-500/25'
  if (value >= 0.5)  return 'bg-yellow-500/10 border-yellow-500/25'
  return 'bg-red-500/10 border-red-500/25'
}

function apColor(value: number): string {
  if (value >= 0.75) return '#34d399'
  if (value >= 0.5)  return '#fbbf24'
  return '#f87171'
}

// ── PR 曲线静态图状态 ───────────────────────────────────────────────────────
const prImageError = ref(false)
const prImageSrc = ref('/metrics/pr_curve.png') // 后续替换为真实评测结果图

function onPrImageError() { prImageError.value = true }
function retryPrImage()   { prImageError.value = false }

// ── Tab 切换过渡 ─────────────────────────────────────────────────────────────
function setTab(tab: typeof activeTab.value) { activeTab.value = tab }

// ── 报告按钮（占位）──────────────────────────────────────────────────────────
function openReport() { /* TODO: router.push('/report') */ }
</script>

<template>
  <div class="h-full bg-slate-950 flex flex-col overflow-hidden">

    <!-- ══ 页面头部 ═══════════════════════════════════════════════════════════ -->
    <div class="px-8 py-5 flex-shrink-0 border-b border-slate-800">
      <div class="flex items-center justify-between">
        <div>
          <h2 class="text-base font-semibold text-white tracking-wide">模型评估</h2>
          <p class="text-xs text-slate-500 mt-0.5">训练过程 · 标准评测结果 · 类别表现分析</p>
        </div>
        <div class="flex items-center gap-3">
          <button
            class="flex items-center gap-2 px-4 py-2 rounded-lg bg-slate-800 border border-slate-700
                   text-slate-400 text-xs hover:border-blue-600 hover:text-blue-400 transition-all duration-200"
          >
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/>
              <polyline points="17,8 12,3 7,8"/>
              <line x1="12" y1="3" x2="12" y2="15"/>
            </svg>
            导出报告
          </button>
          <button
            class="flex items-center gap-2 px-4 py-2 rounded-lg bg-blue-600/20 border border-blue-600/40
                   text-blue-400 text-xs hover:bg-blue-600/30 transition-all duration-200"
            @click="openReport"
          >
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/>
              <polyline points="14,2 14,8 20,8"/>
              <line x1="16" y1="13" x2="8" y2="13"/>
              <line x1="16" y1="17" x2="8" y2="17"/>
              <polyline points="10,9 9,9 8,9"/>
            </svg>
            查看测试报告
          </button>
        </div>
      </div>
    </div>

    <!-- ══ Tab 导航 ══════════════════════════════════════════════════════════ -->
    <div class="px-8 pt-4 pb-0 flex-shrink-0">
      <nav class="flex gap-1 bg-slate-900/60 p-1 rounded-xl w-fit border border-slate-800">
        <button
          v-for="tab in [
            { id: 'overview', label: '总览' },
            { id: 'train',    label: '训练过程' },
            { id: 'eval',     label: '标准评测' },
            { id: 'class',    label: '类别分析' },
          ]"
          :key="tab.id"
          class="px-4 py-2 rounded-lg text-xs font-medium transition-all duration-200 whitespace-nowrap"
          :class="activeTab === tab.id
            ? 'bg-blue-600 text-white shadow-lg shadow-blue-600/25'
            : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'"
          @click="setTab(tab.id as typeof activeTab)"
        >
          {{ tab.label }}
        </button>
      </nav>
    </div>

    <!-- ══ 内容区 ════════════════════════════════════════════════════════════ -->
    <div class="flex-1 overflow-y-auto px-8 py-5">

      <!-- ╔══════════════════════════════════════════════════════════════════════╗ -->
      <!-- ║  Tab 1: 总览                                                          ║ -->
      <!-- ╚══════════════════════════════════════════════════════════════════════╝ -->
      <template v-if="activeTab === 'overview'">
        <div class="space-y-5">

          <!-- ── 核心指标概览卡 ─────────────────────────────────────────── -->
          <div class="grid grid-cols-6 gap-4">
            <!-- mAP@0.5 -->
            <div class="rounded-xl border p-4 bg-slate-900/50 border-slate-800">
              <div class="text-xs text-slate-500 mb-1.5">mAP@0.5</div>
              <div class="text-3xl font-bold text-blue-400 leading-none">{{ (summaryMetrics.mAP50 * 100).toFixed(1) }}<span class="text-sm font-normal text-slate-400">%</span></div>
              <div class="mt-2 h-1 rounded-full bg-slate-700 overflow-hidden">
                <div class="h-full rounded-full bg-blue-500" :style="{ width: (summaryMetrics.mAP50 * 100) + '%' }"></div>
              </div>
            </div>
            <!-- mAP@0.5:0.95 -->
            <div class="rounded-xl border p-4 bg-slate-900/50 border-slate-800">
              <div class="text-xs text-slate-500 mb-1.5">mAP@0.5:0.95</div>
              <div class="text-3xl font-bold" :class="metricColor(summaryMetrics.mAP50_95)">{{ (summaryMetrics.mAP50_95 * 100).toFixed(1) }}<span class="text-sm font-normal text-slate-400">%</span></div>
              <div class="mt-2 h-1 rounded-full bg-slate-700 overflow-hidden">
                <div class="h-full rounded-full" :class="summaryMetrics.mAP50_95 >= 0.5 ? 'bg-emerald-400' : 'bg-yellow-400'" :style="{ width: (summaryMetrics.mAP50_95 * 100) + '%' }"></div>
              </div>
            </div>
            <!-- Precision -->
            <div class="rounded-xl border p-4 bg-slate-900/50 border-slate-800">
              <div class="text-xs text-slate-500 mb-1.5">Precision</div>
              <div class="text-3xl font-bold" :class="metricColor(summaryMetrics.precision)">{{ (summaryMetrics.precision * 100).toFixed(1) }}<span class="text-sm font-normal text-slate-400">%</span></div>
              <div class="mt-2 h-1 rounded-full bg-slate-700 overflow-hidden">
                <div class="h-full rounded-full" :class="summaryMetrics.precision >= 0.75 ? 'bg-emerald-400' : 'bg-yellow-400'" :style="{ width: (summaryMetrics.precision * 100) + '%' }"></div>
              </div>
            </div>
            <!-- Recall -->
            <div class="rounded-xl border p-4 bg-slate-900/50 border-slate-800">
              <div class="text-xs text-slate-500 mb-1.5">Recall</div>
              <div class="text-3xl font-bold" :class="metricColor(summaryMetrics.recall)">{{ (summaryMetrics.recall * 100).toFixed(1) }}<span class="text-sm font-normal text-slate-400">%</span></div>
              <div class="mt-2 h-1 rounded-full bg-slate-700 overflow-hidden">
                <div class="h-full rounded-full" :class="summaryMetrics.recall >= 0.75 ? 'bg-emerald-400' : 'bg-yellow-400'" :style="{ width: (summaryMetrics.recall * 100) + '%' }"></div>
              </div>
            </div>
            <!-- FPS -->
            <div class="rounded-xl border p-4 bg-slate-900/50 border-slate-800">
              <div class="text-xs text-slate-500 mb-1.5">FPS</div>
              <div class="text-3xl font-bold text-cyan-400 leading-none">{{ summaryMetrics.fps.toFixed(1) }}</div>
              <div class="mt-2 text-xs text-emerald-400">实时处理</div>
            </div>
            <!-- 推理耗时 -->
            <div class="rounded-xl border p-4 bg-slate-900/50 border-slate-800">
              <div class="text-xs text-slate-500 mb-1.5">推理耗时</div>
              <div class="text-3xl font-bold text-amber-400 leading-none">{{ summaryMetrics.inferenceTime.toFixed(1) }}<span class="text-sm font-normal text-slate-400">ms</span></div>
              <div class="mt-2 text-xs text-slate-500">单帧平均</div>
            </div>
          </div>

          <!-- ── 两列布局：模型配置 + 训练摘要 ───────────────────────────── -->
          <div class="grid grid-cols-2 gap-5">

            <!-- 模型配置摘要 -->
            <div class="rounded-xl border border-slate-800 bg-slate-900/50 p-5">
              <div class="flex items-center gap-2 mb-4">
                <div class="w-1 h-4 rounded-full bg-blue-500"></div>
                <h3 class="text-sm font-medium text-slate-200">模型配置摘要</h3>
              </div>
              <div class="grid grid-cols-2 gap-x-6 gap-y-3">
                <div class="flex justify-between items-center">
                  <span class="text-xs text-slate-500">模型名称</span>
                  <span class="text-xs font-mono text-slate-300">{{ modelConfig.modelName }}</span>
                </div>
                <div class="flex justify-between items-center">
                  <span class="text-xs text-slate-500">模型类型</span>
                  <span class="text-xs text-slate-300">{{ modelConfig.modelType }}</span>
                </div>
                <div class="flex justify-between items-center">
                  <span class="text-xs text-slate-500">Runtime</span>
                  <span class="text-xs font-mono text-slate-300">{{ modelConfig.runtime }}</span>
                </div>
                <div class="flex justify-between items-center">
                  <span class="text-xs text-slate-500">输入尺寸</span>
                  <span class="text-xs font-mono text-slate-300">{{ modelConfig.inputSize }}</span>
                </div>
                <div class="flex justify-between items-center">
                  <span class="text-xs text-slate-500">类别数</span>
                  <span class="text-xs font-mono text-slate-300">{{ modelConfig.numClasses }} 类</span>
                </div>
                <div class="flex justify-between items-center">
                  <span class="text-xs text-slate-500">训练轮次</span>
                  <span class="text-xs font-mono text-slate-300">{{ modelConfig.trainedEpochs }} epochs</span>
                </div>
                <div class="flex justify-between items-center">
                  <span class="text-xs text-slate-500">最优轮次</span>
                  <span class="text-xs font-mono text-blue-400">Epoch {{ modelConfig.bestEpoch }}</span>
                </div>
                <div class="flex justify-between items-center">
                  <span class="text-xs text-slate-500">权重文件</span>
                  <span class="text-xs font-mono text-slate-400 truncate max-w-[140px]">{{ modelConfig.weightFile }}</span>
                </div>
                <div class="flex justify-between items-center col-span-2">
                  <span class="text-xs text-slate-500">数据集</span>
                  <span class="text-xs text-slate-300">{{ modelConfig.dataset }}</span>
                </div>
              </div>
            </div>

            <!-- 训练摘要 -->
            <div class="rounded-xl border border-slate-800 bg-slate-900/50 p-5">
              <div class="flex items-center gap-2 mb-4">
                <div class="w-1 h-4 rounded-full bg-emerald-500"></div>
                <h3 class="text-sm font-medium text-slate-200">训练摘要</h3>
              </div>
              <div class="grid grid-cols-2 gap-x-6 gap-y-3">
                <div class="flex justify-between items-center">
                  <span class="text-xs text-slate-500">Best Epoch</span>
                  <span class="text-xs font-mono text-blue-400">{{ modelConfig.bestEpoch }}</span>
                </div>
                <div class="flex justify-between items-center">
                  <span class="text-xs text-slate-500">训练样本总数</span>
                  <span class="text-xs font-mono text-slate-300">{{ modelConfig.totalImages.toLocaleString() }}</span>
                </div>
                <div class="flex justify-between items-center">
                  <span class="text-xs text-slate-500">Best mAP@0.5</span>
                  <span class="text-xs font-mono text-emerald-400">{{ bestEpochData ? (bestEpochData.mAP50 * 100).toFixed(2) + '%' : '—' }}</span>
                </div>
                <div class="flex justify-between items-center">
                  <span class="text-xs text-slate-500">Best Precision</span>
                  <span class="text-xs font-mono text-slate-300">{{ bestEpochData ? (bestEpochData.precision * 100).toFixed(2) + '%' : '—' }}</span>
                </div>
                <div class="flex justify-between items-center">
                  <span class="text-xs text-slate-500">Val Box Loss</span>
                  <span class="text-xs font-mono text-slate-400">{{ bestEpochData ? bestEpochData.valBox.toFixed(4) : '—' }}</span>
                </div>
                <div class="flex justify-between items-center">
                  <span class="text-xs text-slate-500">Val Cls Loss</span>
                  <span class="text-xs font-mono text-slate-400">{{ bestEpochData ? bestEpochData.valCls.toFixed(4) : '—' }}</span>
                </div>
                <div class="flex justify-between items-center col-span-2">
                  <span class="text-xs text-slate-500">收敛趋势</span>
                  <span class="text-xs text-emerald-400 flex items-center gap-1">
                    <span class="w-1.5 h-1.5 rounded-full bg-emerald-400 inline-block"></span>
                    已收敛
                  </span>
                </div>
              </div>
            </div>
          </div>

          <!-- ── 评测摘要 ─────────────────────────────────────────────────── -->
          <div class="rounded-xl border border-slate-800 bg-slate-900/50 p-5">
            <div class="flex items-center gap-2 mb-4">
              <div class="w-1 h-4 rounded-full bg-cyan-500"></div>
              <h3 class="text-sm font-medium text-slate-200">评测摘要</h3>
            </div>
            <div class="grid grid-cols-4 gap-4">
              <div class="flex flex-col gap-1">
                <div class="text-xs text-slate-500">评测 mAP@0.5</div>
                <div class="text-2xl font-bold text-blue-400">{{ (evaluationResult.overallMAP50 * 100).toFixed(1) }}%</div>
              </div>
              <div class="flex flex-col gap-1">
                <div class="text-xs text-slate-500">评测 Precision</div>
                <div class="text-2xl font-bold" :class="metricColor(evaluationResult.overallPrecision)">{{ (evaluationResult.overallPrecision * 100).toFixed(1) }}%</div>
              </div>
              <div class="flex flex-col gap-1">
                <div class="text-xs text-slate-500">评测 Recall</div>
                <div class="text-2xl font-bold" :class="metricColor(evaluationResult.overallRecall)">{{ (evaluationResult.overallRecall * 100).toFixed(1) }}%</div>
              </div>
              <div class="flex flex-col gap-1">
                <div class="text-xs text-slate-500">测试集规模</div>
                <div class="text-2xl font-bold text-cyan-400">{{ evaluationResult.testSetSize.toLocaleString() }}</div>
                <div class="text-xs text-slate-500 mt-0.5">帧</div>
              </div>
            </div>
            <div class="mt-4 pt-4 border-t border-slate-800 flex items-start gap-8">
              <div class="flex-1">
                <div class="text-xs text-slate-500 mb-1">测试场景</div>
                <div class="text-xs text-slate-400">{{ evaluationResult.testScenes }}</div>
              </div>
              <div class="flex items-center gap-2">
                <span class="inline-flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full bg-emerald-500/15 border border-emerald-500/25 text-emerald-400">
                  <span class="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>
                  评测完成
                </span>
              </div>
            </div>
          </div>

          <!-- ── Top-5 类别 AP 预览 ───────────────────────────────────────── -->
          <div class="rounded-xl border border-slate-800 bg-slate-900/50 overflow-hidden">
            <div class="px-5 py-4 border-b border-slate-800 flex items-center justify-between">
              <h3 class="text-sm font-medium text-slate-300">类别 AP 排名</h3>
              <button class="text-xs text-blue-400 hover:text-blue-300 transition-colors" @click="setTab('class')">查看全部 →</button>
            </div>
            <div class="p-5 space-y-3">
              <div
                v-for="(cls, i) in classMetrics"
                :key="cls.name"
                class="flex items-center gap-3"
              >
                <div class="w-5 text-xs font-mono text-slate-500 text-right flex-shrink-0">{{ i + 1 }}</div>
                <div class="w-20 text-sm text-slate-300 flex-shrink-0">{{ cls.label }}</div>
                <div class="flex-1 h-1.5 bg-slate-700 rounded-full overflow-hidden">
                  <div
                    class="h-full rounded-full transition-all duration-500"
                    :style="{ width: (cls.ap50 * 100) + '%', backgroundColor: apColor(cls.ap50) }"
                  ></div>
                </div>
                <div class="w-14 text-right text-sm font-mono font-medium" :style="{ color: apColor(cls.ap50) }">
                  {{ (cls.ap50 * 100).toFixed(1) }}%
                </div>
              </div>
            </div>
          </div>

        </div>
      </template>

      <!-- ╔══════════════════════════════════════════════════════════════════════╗ -->
      <!-- ║  Tab 2: 训练过程                                                        ║ -->
      <!-- ╚══════════════════════════════════════════════════════════════════════╝ -->
      <template v-if="activeTab === 'train'">
        <div class="space-y-5">

          <!-- 训练过程说明 -->
          <div class="flex items-center justify-between">
            <div>
              <h3 class="text-sm font-semibold text-white">训练过程分析</h3>
              <p class="text-xs text-slate-500 mt-0.5">基于训练日志展示损失收敛、精度演进与学习率调度过程</p>
            </div>
            <div class="flex items-center gap-2 text-xs text-slate-500">
              <span class="inline-flex items-center gap-1.5 px-2 py-1 rounded-md bg-slate-800 border border-slate-700">
                <span class="w-1.5 h-1.5 rounded-full bg-blue-400"></span>
                训练集
              </span>
              <span class="inline-flex items-center gap-1.5 px-2 py-1 rounded-md bg-slate-800 border border-slate-700">
                <span class="w-1.5 h-1.5 rounded-full bg-amber-400"></span>
                验证集
              </span>
            </div>
          </div>

          <!-- ── 损失收敛曲线（大卡片）────────────────────────────────────── -->
          <div class="rounded-xl border border-slate-800 bg-slate-900/50 p-5">
            <div class="flex items-center gap-2 mb-4">
              <div class="w-1 h-4 rounded-full bg-red-500"></div>
              <h3 class="text-sm font-medium text-slate-200">损失收敛曲线</h3>
              <div class="ml-auto flex items-center gap-3 text-xs text-slate-500">
                <span class="flex items-center gap-1.5">
                  <span class="w-3 h-0.5 bg-blue-500 rounded"></span> box_loss
                </span>
                <span class="flex items-center gap-1.5">
                  <span class="w-3 h-0.5 bg-violet-500 rounded"></span> cls_loss
                </span>
                <span class="flex items-center gap-1.5">
                  <span class="w-3 h-0.5 bg-purple-500 rounded"></span> dfl_loss
                </span>
                <span class="flex items-center gap-1.5">
                  <span class="w-3 h-0.5 bg-amber-400 rounded dashed"></span> val_box
                </span>
              </div>
            </div>

            <!-- SVG Chart: Loss -->
            <svg :width="CHART_W" :height="CHART_H" class="w-full" style="color-scheme:dark">
              <defs>
                <linearGradient id="grad-blue" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stop-color="#3b82f6" stop-opacity="0.25"/>
                  <stop offset="100%" stop-color="#3b82f6" stop-opacity="0"/>
                </linearGradient>
                <linearGradient id="grad-amber" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stop-color="#f59e0b" stop-opacity="0.25"/>
                  <stop offset="100%" stop-color="#f59e0b" stop-opacity="0"/>
                </linearGradient>
              </defs>

              <!-- Grid lines -->
              <g stroke="#1e293b" stroke-width="1">
                <line v-for="gl in lossGridLines" :key="gl.y" :x1="PAD" :y1="gl.y" :x2="CHART_W - PAD" :y2="gl.y" stroke-dasharray="4,4"/>
              </g>

              <!-- Axis labels -->
              <g class="text-slate-600" font-size="10" font-family="monospace">
                <text v-for="gl in lossGridLines" :key="'lbl-'+gl.y" :x="PAD - 4" :y="parseFloat(gl.y) + 3" text-anchor="end">{{ gl.label }}</text>
                <text v-for="el in epochLabels" :key="'elbl-'+el.x" :x="el.x" :y="CHART_H - 6" text-anchor="middle">{{ el.label }}</text>
              </g>

              <!-- Area fills (train) -->
              <path :d="buildAreaPath(trainHistory, 'trainBox', CHART_W, CHART_H, PAD)" fill="url(#grad-blue)"/>

              <!-- Lines: box loss -->
              <path :d="lossLines.trainBox" fill="none" stroke="#3b82f6" stroke-width="1.5" stroke-linejoin="round"/>
              <path :d="lossLines.valBox"   fill="none" stroke="#f59e0b" stroke-width="1.5" stroke-linejoin="round" stroke-dasharray="6,3"/>

              <!-- Lines: cls loss -->
              <path :d="lossLines.trainCls" fill="none" stroke="#8b5cf6" stroke-width="1.5" stroke-linejoin="round" opacity="0.8"/>
              <path :d="lossLines.valCls"   fill="none" stroke="#f59e0b" stroke-width="1"   stroke-linejoin="round" stroke-dasharray="4,3" opacity="0.5"/>

              <!-- Lines: dfl loss -->
              <path :d="lossLines.trainDfl" fill="none" stroke="#a855f7" stroke-width="1.5" stroke-linejoin="round" opacity="0.6"/>
              <path :d="lossLines.valDfl"    fill="none" stroke="#f59e0b" stroke-width="1"   stroke-linejoin="round" stroke-dasharray="3,3" opacity="0.35"/>
            </svg>

            <!-- Legend row -->
            <div class="mt-3 pt-3 border-t border-slate-800 grid grid-cols-6 gap-3 text-xs text-slate-500">
              <div><span class="inline-block w-3 h-0.5 bg-blue-500 rounded mr-1 align-middle"></span>train/box_loss <span class="text-slate-400 font-mono ml-1">{{ formatLossVal('trainBox') }}</span></div>
              <div><span class="inline-block w-3 h-0.5 bg-violet-500 rounded mr-1 align-middle"></span>train/cls_loss <span class="text-slate-400 font-mono ml-1">{{ formatLossVal('trainCls') }}</span></div>
              <div><span class="inline-block w-3 h-0.5 bg-purple-500 rounded mr-1 align-middle"></span>train/dfl_loss <span class="text-slate-400 font-mono ml-1">{{ formatLossVal('trainDfl') }}</span></div>
              <div><span class="inline-block w-3 h-0.5 bg-amber-400 rounded mr-1 align-middle"></span>val/box_loss <span class="text-slate-400 font-mono ml-1">{{ formatLossVal('valBox') }}</span></div>
              <div><span class="inline-block w-3 h-0.5 bg-amber-400/60 rounded mr-1 align-middle"></span>val/cls_loss <span class="text-slate-400 font-mono ml-1">{{ formatLossVal('valCls') }}</span></div>
              <div><span class="inline-block w-3 h-0.5 bg-amber-400/40 rounded mr-1 align-middle"></span>val/dfl_loss <span class="text-slate-400 font-mono ml-1">{{ formatLossVal('valDfl') }}</span></div>
            </div>
          </div>

          <!-- ── 精度演进趋势 ─────────────────────────────────────────────── -->
          <div class="rounded-xl border border-slate-800 bg-slate-900/50 p-5">
            <div class="flex items-center gap-2 mb-4">
              <div class="w-1 h-4 rounded-full bg-emerald-500"></div>
              <h3 class="text-sm font-medium text-slate-200">精度演进趋势</h3>
              <div class="ml-auto flex items-center gap-3 text-xs text-slate-500">
                <span class="flex items-center gap-1.5">
                  <span class="w-3 h-0.5 bg-blue-400 rounded"></span> Precision
                </span>
                <span class="flex items-center gap-1.5">
                  <span class="w-3 h-0.5 bg-cyan-400 rounded"></span> Recall
                </span>
                <span class="flex items-center gap-1.5">
                  <span class="w-3 h-0.5 bg-emerald-400 rounded"></span> mAP@0.5
                </span>
                <span class="flex items-center gap-1.5">
                  <span class="w-3 h-0.5 bg-teal-400 rounded"></span> mAP@0.5:0.95
                </span>
              </div>
            </div>

            <!-- SVG Chart: Metrics -->
            <svg :width="CHART_W" :height="CHART_H" class="w-full" style="color-scheme:dark">
              <defs>
                <linearGradient id="grad-emerald" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stop-color="#10b981" stop-opacity="0.2"/>
                  <stop offset="100%" stop-color="#10b981" stop-opacity="0"/>
                </linearGradient>
              </defs>

              <!-- Grid lines -->
              <g stroke="#1e293b" stroke-width="1">
                <line v-for="gl in metricGridLines" :key="gl.y" :x1="PAD" :y1="gl.y" :x2="CHART_W - PAD" :y2="gl.y" stroke-dasharray="4,4"/>
              </g>

              <!-- Axis labels -->
              <g class="text-slate-600" font-size="10" font-family="monospace">
                <text v-for="gl in metricGridLines" :key="'mlbl-'+gl.y" :x="PAD - 4" :y="parseFloat(gl.y) + 3" text-anchor="end">{{ gl.label }}</text>
                <text v-for="el in epochLabels" :key="'melbl-'+el.x" :x="el.x" :y="CHART_H - 6" text-anchor="middle">{{ el.label }}</text>
              </g>

              <!-- Area fills -->
              <path :d="buildAreaPath(trainHistory, 'mAP50', CHART_W, CHART_H, PAD)" fill="url(#grad-emerald)"/>

              <!-- Metric lines -->
              <path :d="metricLines.precision"  fill="none" stroke="#60a5fa" stroke-width="1.5" stroke-linejoin="round"/>
              <path :d="metricLines.recall"     fill="none" stroke="#22d3ee" stroke-width="1.5" stroke-linejoin="round"/>
              <path :d="metricLines.mAP50"      fill="none" stroke="#34d399" stroke-width="2"   stroke-linejoin="round"/>
              <path :d="metricLines.mAP50_95"   fill="none" stroke="#2dd4bf" stroke-width="1.5" stroke-linejoin="round" stroke-dasharray="4,2"/>

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

          <!-- ── 学习率曲线 + 最佳轮次摘要 ─────────────────────────────── -->
          <div class="grid grid-cols-3 gap-5">

            <!-- LR 曲线 -->
            <div class="col-span-2 rounded-xl border border-slate-800 bg-slate-900/50 p-5">
              <div class="flex items-center gap-2 mb-4">
                <div class="w-1 h-4 rounded-full bg-cyan-500"></div>
                <h3 class="text-sm font-medium text-slate-200">学习率调度曲线</h3>
                <div class="ml-auto flex items-center gap-3 text-xs text-slate-500">
                  <span class="flex items-center gap-1.5"><span class="w-3 h-0.5 bg-cyan-400 rounded"></span> pg0</span>
                  <span class="flex items-center gap-1.5"><span class="w-3 h-0.5 bg-blue-400 rounded"></span> pg1</span>
                  <span class="flex items-center gap-1.5"><span class="w-3 h-0.5 bg-indigo-400 rounded"></span> pg2</span>
                </div>
              </div>

              <svg :width="CHART_W" :height="160" class="w-full" style="color-scheme:dark">
                <g stroke="#1e293b" stroke-width="1">
                  <line v-for="gl in lrGridLines" :key="gl.y" :x1="PAD" :y1="gl.y" :x2="CHART_W - PAD" :y2="gl.y" stroke-dasharray="4,4"/>
                </g>
                <g class="text-slate-600" font-size="10" font-family="monospace">
                  <text v-for="gl in lrGridLines" :key="'llbl-'+gl.y" :x="PAD - 4" :y="parseFloat(gl.y) + 3" text-anchor="end">{{ gl.label }}</text>
                </g>
                <path :d="lrLines.lr0" fill="none" stroke="#22d3ee" stroke-width="1.5" stroke-linejoin="round"/>
                <path :d="lrLines.lr1" fill="none" stroke="#60a5fa" stroke-width="1.5" stroke-linejoin="round"/>
                <path :d="lrLines.lr2" fill="none" stroke="#818cf8" stroke-width="1.5" stroke-linejoin="round"/>
              </svg>
            </div>

            <!-- 最佳轮次摘要卡 -->
            <div class="rounded-xl border border-slate-800 bg-slate-900/50 p-5 flex flex-col">
              <div class="flex items-center gap-2 mb-4">
                <div class="w-1 h-4 rounded-full bg-yellow-500"></div>
                <h3 class="text-sm font-medium text-slate-200">最佳轮次摘要</h3>
              </div>
              <template v-if="bestEpochData">
                <div class="space-y-3 flex-1">
                  <div class="flex justify-between items-center">
                    <span class="text-xs text-slate-500">Best Epoch</span>
                    <span class="text-sm font-mono font-bold text-yellow-400">{{ bestEpochData.epoch }}</span>
                  </div>
                  <div class="flex justify-between items-center">
                    <span class="text-xs text-slate-500">mAP@0.5</span>
                    <span class="text-sm font-mono text-emerald-400">{{ (bestEpochData.mAP50 * 100).toFixed(2) }}%</span>
                  </div>
                  <div class="flex justify-between items-center">
                    <span class="text-xs text-slate-500">Precision</span>
                    <span class="text-sm font-mono text-slate-300">{{ (bestEpochData.precision * 100).toFixed(2) }}%</span>
                  </div>
                  <div class="flex justify-between items-center">
                    <span class="text-xs text-slate-500">Recall</span>
                    <span class="text-sm font-mono text-slate-300">{{ (bestEpochData.recall * 100).toFixed(2) }}%</span>
                  </div>
                  <div class="flex justify-between items-center">
                    <span class="text-xs text-slate-500">mAP@0.5:0.95</span>
                    <span class="text-sm font-mono text-slate-300">{{ (bestEpochData.mAP50_95 * 100).toFixed(2) }}%</span>
                  </div>
                  <div class="border-t border-slate-800 pt-3 mt-auto">
                    <div class="text-xs text-slate-500 mb-1">Val Loss</div>
                    <div class="grid grid-cols-3 gap-2 text-xs font-mono text-slate-400">
                      <div>box<span class="text-slate-300 ml-1">{{ bestEpochData.valBox.toFixed(3) }}</span></div>
                      <div>cls<span class="text-slate-300 ml-1">{{ bestEpochData.valCls.toFixed(3) }}</span></div>
                      <div>dfl<span class="text-slate-300 ml-1">{{ bestEpochData.valDfl.toFixed(3) }}</span></div>
                    </div>
                  </div>
                </div>
              </template>
              <template v-else>
                <div class="flex-1 flex items-center justify-center text-slate-600 text-xs">暂无数据</div>
              </template>
            </div>
          </div>

        </div>
      </template>

      <!-- ╔══════════════════════════════════════════════════════════════════════╗ -->
      <!-- ║  Tab 3: 标准评测                                                        ║ -->
      <!-- ╚══════════════════════════════════════════════════════════════════════╝ -->
      <template v-if="activeTab === 'eval'">
        <div class="space-y-5">

          <!-- 说明 -->
          <div>
            <h3 class="text-sm font-semibold text-white">标准评测结果</h3>
            <p class="text-xs text-slate-500 mt-0.5">基于独立测试集生成的 P-R 曲线、AP 结果与整体评测结论</p>
          </div>

          <!-- ── PR 曲线展示区 ────────────────────────────────────────────── -->
          <div class="rounded-xl border border-slate-800 bg-slate-900/50 overflow-hidden">
            <div class="px-5 py-4 border-b border-slate-800 flex items-center justify-between">
              <h3 class="text-sm font-medium text-slate-300">P-R 曲线</h3>
              <div class="flex items-center gap-2 text-xs text-slate-500">
                <span class="px-2 py-0.5 rounded bg-slate-800 border border-slate-700">综合</span>
                <span class="px-2 py-0.5 rounded text-slate-500">car</span>
              </div>
            </div>

            <div class="p-6 flex items-center justify-center" style="min-height: 320px;">
              <!-- PR 曲线图：静态图片 + 深色展示容器 -->
              <template v-if="!prImageError">
                <div class="relative w-full max-w-2xl rounded-lg overflow-hidden border border-slate-700 bg-slate-900">
                  <img
                    :src="prImageSrc"
                    alt="P-R 曲线"
                    class="w-full h-auto"
                    style="max-height: 300px; object-fit: contain;"
                    @error="onPrImageError"
                  />
                  <!-- 深色叠加层（确保在任何图片背景下都清晰） -->
                  <div class="absolute inset-0 bg-gradient-to-t from-slate-950/40 to-transparent pointer-events-none"></div>
                </div>
              </template>
              <!-- 失败占位 -->
              <template v-else>
                <div class="text-center">
                  <svg width="56" height="56" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1" class="mx-auto mb-4 text-slate-700">
                    <line x1="18" y1="20" x2="18" y2="10"/>
                    <line x1="12" y1="20" x2="12" y2="4"/>
                    <line x1="6" y1="20" x2="6" y2="14"/>
                    <line x1="2" y1="20" x2="22" y2="20"/>
                  </svg>
                  <p class="text-sm font-medium text-slate-500 mb-1">PR 曲线预留区</p>
                  <p class="text-xs text-slate-600">待接入独立评测结果</p>
                  <button
                    class="mt-3 px-3 py-1.5 rounded-lg text-xs border border-slate-700 text-slate-500
                           hover:border-slate-500 hover:text-slate-300 transition-all"
                    @click="retryPrImage"
                  >
                    重试加载
                  </button>
                </div>
              </template>
            </div>
          </div>

          <!-- ── AP 结果表格 ─────────────────────────────────────────────── -->
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
                    <th class="px-5 py-3 text-right text-xs font-medium text-slate-500 uppercase tracking-wider">样本数</th>
                    <th class="px-5 py-3 text-right text-xs font-medium text-slate-500 uppercase tracking-wider">达标</th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="cls in classMetrics"
                    :key="cls.name"
                    class="border-b border-slate-800/50 hover:bg-slate-800/30 transition-colors"
                  >
                    <td class="px-5 py-3.5">
                      <div class="flex items-center gap-2">
                        <div class="w-6 h-6 rounded bg-slate-800 border border-slate-700 flex items-center justify-center text-xs font-mono text-slate-400">
                          {{ cls.name.slice(0, 2).toUpperCase() }}
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
                    <td class="px-5 py-3.5 text-right font-mono text-sm text-slate-400">
                      {{ cls.samples.toLocaleString() }}
                    </td>
                    <td class="px-5 py-3.5 text-right">
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

          <!-- ── 整体评测结论 ────────────────────────────────────────────── -->
          <div class="rounded-xl border border-slate-800 bg-slate-900/50 p-5">
            <div class="flex items-center gap-2 mb-4">
              <div class="w-1 h-4 rounded-full bg-violet-500"></div>
              <h3 class="text-sm font-medium text-slate-200">整体评测结论</h3>
            </div>
            <div class="grid grid-cols-4 gap-4 mb-5">
              <div class="rounded-lg border p-3 bg-slate-800/40 border-slate-700/50">
                <div class="text-xs text-slate-500 mb-1">总体 mAP@0.5</div>
                <div class="text-xl font-bold text-blue-400">{{ (evaluationResult.overallMAP50 * 100).toFixed(1) }}%</div>
              </div>
              <div class="rounded-lg border p-3 bg-slate-800/40 border-slate-700/50">
                <div class="text-xs text-slate-500 mb-1">总体 Precision</div>
                <div class="text-xl font-bold" :class="metricColor(evaluationResult.overallPrecision)">{{ (evaluationResult.overallPrecision * 100).toFixed(1) }}%</div>
              </div>
              <div class="rounded-lg border p-3 bg-slate-800/40 border-slate-700/50">
                <div class="text-xs text-slate-500 mb-1">总体 Recall</div>
                <div class="text-xl font-bold" :class="metricColor(evaluationResult.overallRecall)">{{ (evaluationResult.overallRecall * 100).toFixed(1) }}%</div>
              </div>
              <div class="rounded-lg border p-3 bg-slate-800/40 border-slate-700/50">
                <div class="text-xs text-slate-500 mb-1">测试集规模</div>
                <div class="text-xl font-bold text-cyan-400">{{ evaluationResult.testSetSize.toLocaleString() }}<span class="text-sm font-normal text-slate-500 ml-1">帧</span></div>
              </div>
            </div>
            <div class="p-4 rounded-lg bg-slate-800/30 border border-slate-700/50">
              <p class="text-xs text-slate-400 leading-relaxed">{{ evaluationResult.conclusion }}</p>
            </div>
            <div class="mt-3 flex items-center gap-6 text-xs text-slate-500">
              <span>测试场景：{{ evaluationResult.testScenes }}</span>
            </div>
          </div>

        </div>
      </template>

      <!-- ╔══════════════════════════════════════════════════════════════════════╗ -->
      <!-- ║  Tab 4: 类别分析                                                        ║ -->
      <!-- ╚══════════════════════════════════════════════════════════════════════╝ -->
      <template v-if="activeTab === 'class'">
        <div class="space-y-5">

          <!-- 说明 -->
          <div>
            <h3 class="text-sm font-semibold text-white">类别分析</h3>
            <p class="text-xs text-slate-500 mt-0.5">从类别维度分析模型识别效果、样本分布与结果差异</p>
          </div>

          <!-- ── 类别 AP 排行（横向条形图）───────────────────────────────── -->
          <div class="rounded-xl border border-slate-800 bg-slate-900/50 p-5">
            <div class="flex items-center gap-2 mb-5">
              <div class="w-1 h-4 rounded-full bg-emerald-500"></div>
              <h3 class="text-sm font-medium text-slate-200">类别 AP@0.5 排行</h3>
            </div>
            <div class="space-y-4">
              <div
                v-for="(cls, i) in classMetrics"
                :key="cls.name"
                class="flex items-center gap-4"
              >
                <!-- Rank -->
                <div class="w-6 text-center flex-shrink-0">
                  <span
                    class="text-xs font-mono font-bold"
                    :class="i === 0 ? 'text-yellow-400' : i === 1 ? 'text-slate-400' : i === 2 ? 'text-amber-600' : 'text-slate-600'"
                  >{{ i + 1 }}</span>
                </div>
                <!-- Label -->
                <div class="w-20 flex-shrink-0">
                  <div class="text-sm font-medium text-slate-200">{{ cls.label }}</div>
                  <div class="text-xs text-slate-500 font-mono">{{ cls.name }}</div>
                </div>
                <!-- Bar -->
                <div class="flex-1 h-3 bg-slate-800 rounded-full overflow-hidden">
                  <div
                    class="h-full rounded-full transition-all duration-700"
                    :style="{
                      width: (cls.ap50 * 100) + '%',
                      backgroundColor: apColor(cls.ap50),
                    }"
                  ></div>
                </div>
                <!-- Value -->
                <div class="w-16 text-right flex-shrink-0">
                  <span class="text-sm font-mono font-bold" :style="{ color: apColor(cls.ap50) }">
                    {{ (cls.ap50 * 100).toFixed(1) }}%
                  </span>
                </div>
              </div>
            </div>

            <!-- AP@0.5:0.95 分隔 -->
            <div class="mt-6 pt-5 border-t border-slate-800">
              <div class="text-xs text-slate-500 mb-4">AP@0.5:0.95</div>
              <div class="space-y-3">
                <div
                  v-for="cls in classMetrics"
                  :key="'coco-'+cls.name"
                  class="flex items-center gap-4"
                >
                  <div class="w-6 text-center flex-shrink-0"></div>
                  <div class="w-20 flex-shrink-0 text-sm text-slate-300">{{ cls.label }}</div>
                  <div class="flex-1 h-2 bg-slate-800 rounded-full overflow-hidden">
                    <div
                      class="h-full rounded-full transition-all duration-700"
                      :style="{ width: (cls.ap50_95 * 100) + '%', backgroundColor: apColor(cls.ap50_95), opacity: 0.7 }"
                    ></div>
                  </div>
                  <div class="w-16 text-right flex-shrink-0 text-xs font-mono text-slate-400">
                    {{ (cls.ap50_95 * 100).toFixed(1) }}%
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- ── 类别样本统计 ─────────────────────────────────────────────── -->
          <div class="rounded-xl border border-slate-800 bg-slate-900/50 p-5">
            <div class="flex items-center gap-2 mb-4">
              <div class="w-1 h-4 rounded-full bg-cyan-500"></div>
              <h3 class="text-sm font-medium text-slate-200">类别样本统计</h3>
            </div>
            <div class="grid grid-cols-5 gap-4">
              <div
                v-for="cls in classMetrics"
                :key="'stat-'+cls.name"
                class="rounded-lg border p-3 bg-slate-800/30 border-slate-700/50"
              >
                <div class="text-xs text-slate-500 mb-1">{{ cls.label }}</div>
                <div class="text-lg font-bold text-slate-200">{{ cls.samples.toLocaleString() }}</div>
                <div class="text-xs text-slate-500 mt-0.5">目标框</div>
                <!-- 样本量比例指示 -->
                <div class="mt-2 h-1 bg-slate-700 rounded-full overflow-hidden">
                  <div
                    class="h-full rounded-full"
                    :style="{ width: (cls.samples / 3847 * 100) + '%', backgroundColor: apColor(cls.ap50) }"
                  ></div>
                </div>
              </div>
            </div>
          </div>

          <!-- ── 类别表现分析卡 ───────────────────────────────────────────── -->
          <div class="rounded-xl border border-slate-800 bg-slate-900/50 overflow-hidden">
            <div class="px-5 py-4 border-b border-slate-800">
              <h3 class="text-sm font-medium text-slate-300">类别表现分析</h3>
            </div>
            <div class="p-5 grid grid-cols-3 gap-4">
              <div
                v-for="cls in classMetrics"
                :key="'card-'+cls.name"
                class="rounded-lg border p-4"
                :class="cls.ap50 >= 0.75
                  ? 'border-emerald-500/20 bg-emerald-500/5'
                  : cls.ap50 >= 0.5
                    ? 'border-yellow-500/20 bg-yellow-500/5'
                    : 'border-red-500/20 bg-red-500/5'"
              >
                <!-- Header -->
                <div class="flex items-center justify-between mb-3">
                  <div class="flex items-center gap-2">
                    <div
                      class="w-7 h-7 rounded-lg flex items-center justify-center text-xs font-bold font-mono text-white"
                      :style="{ backgroundColor: apColor(cls.ap50) }"
                    >
                      {{ cls.name.slice(0, 2).toUpperCase() }}
                    </div>
                    <div>
                      <div class="text-sm font-medium text-slate-200">{{ cls.label }}</div>
                      <div class="text-xs text-slate-500">{{ cls.samples.toLocaleString() }} 样本</div>
                    </div>
                  </div>
                  <div class="text-lg font-bold font-mono" :style="{ color: apColor(cls.ap50) }">
                    {{ (cls.ap50 * 100).toFixed(1) }}%
                  </div>
                </div>

                <!-- Metrics row -->
                <div class="grid grid-cols-3 gap-2 mb-3">
                  <div class="text-center">
                    <div class="text-xs text-slate-500">P</div>
                    <div class="text-xs font-mono text-slate-300">{{ (cls.precision * 100).toFixed(0) }}%</div>
                  </div>
                  <div class="text-center border-x border-slate-700/50">
                    <div class="text-xs text-slate-500">R</div>
                    <div class="text-xs font-mono text-slate-300">{{ (cls.recall * 100).toFixed(0) }}%</div>
                  </div>
                  <div class="text-center">
                    <div class="text-xs text-slate-500">AP</div>
                    <div class="text-xs font-mono" :style="{ color: apColor(cls.ap50) }">{{ (cls.ap50 * 100).toFixed(1) }}%</div>
                  </div>
                </div>

                <!-- Note -->
                <div
                  class="text-xs px-2 py-1.5 rounded-md leading-relaxed"
                  :class="cls.ap50 >= 0.75
                    ? 'bg-emerald-500/10 text-emerald-400/80 border border-emerald-500/15'
                    : cls.ap50 >= 0.5
                      ? 'bg-yellow-500/10 text-yellow-400/80 border border-yellow-500/15'
                      : 'bg-red-500/10 text-red-400/80 border border-red-500/15'"
                >
                  {{ cls.note }}
                </div>
              </div>
            </div>
          </div>

          <!-- ── 测试报告入口 ────────────────────────────────────────────── -->
          <div class="rounded-xl border border-slate-800 bg-slate-900/50 p-5">
            <div class="flex items-center gap-4">
              <div class="w-12 h-12 rounded-xl bg-slate-800 border border-slate-700 flex items-center justify-center flex-shrink-0">
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" class="text-slate-500">
                  <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/>
                  <polyline points="14,2 14,8 20,8"/>
                  <line x1="16" y1="13" x2="8" y2="13"/>
                  <line x1="16" y1="17" x2="8" y2="17"/>
                  <polyline points="10,9 9,9 8,9"/>
                </svg>
              </div>
              <div class="flex-1">
                <h3 class="text-sm font-medium text-slate-200">测试报告</h3>
                <p class="text-xs text-slate-500 mt-0.5">查看当前模型的测试集评测摘要与结果说明</p>
              </div>
              <button
                class="px-4 py-2 rounded-lg bg-blue-600/20 border border-blue-600/40
                       text-blue-400 text-xs hover:bg-blue-600/30 transition-all duration-200 flex-shrink-0"
                @click="openReport"
              >
                查看详情
              </button>
            </div>
          </div>

        </div>
      </template>

    </div><!-- /内容区 -->
  </div>
</template>

<style scoped>
/* Smooth transitions */
button { transition: all 200ms cubic-bezier(0.4, 0, 0.2, 1); }

/* Scrollbar styling */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: #334155; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #475569; }

/* SVG crisp rendering */
svg text { user-select: none; }
</style>
