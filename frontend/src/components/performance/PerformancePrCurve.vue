<script setup lang="ts">
/**
 * Skyline — PR 曲线 SVG 组件（YOLO 风格评测图版）
 *
 * 职责：
 *   - 使用原生 SVG 绘制多类别 PR 曲线
 *   - 右侧固定图例显示每类 AP
 *   - all classes 粗线高亮显示
 *   - 深色主题适配，适合截图展示
 *
 * 数据来源：prCurveCsvAdapter.ts
 */
import { ref, onMounted } from 'vue'
import { loadPrCurveData, type PrCurveData } from '@/data/prCurveCsvAdapter'

// ── 调色板（10 个类别，固定配色） ──────────────────────────────────────────
const CURVE_COLORS = [
  '#60a5fa', // blue
  '#34d399', // emerald
  '#f472b6', // pink
  '#fbbf24', // amber
  '#a78bfa', // violet
  '#22d3ee', // cyan
  '#fb923c', // orange
  '#94a3b8', // slate
  '#f87171', // red
  '#86efac', // light emerald
]

// ── all classes 专用颜色（更醒目的白色系） ─────────────────────────────────
const ALL_CLASSES_COLOR = '#ffffff'
const ALL_CLASSES_STROKE_WIDTH = 2.5
const CLASS_STROKE_WIDTH = 1.2

// ── SVG 布局参数（更大主图区域，右侧固定图例） ───────────────────────────
const SVG_W = 840
const SVG_H = 480
const PAD_LEFT = 65
const PAD_RIGHT = 160  // 右侧图例区域，更宽裕
const PAD_TOP = 25
const PAD_BOTTOM = 55

const CHART_W = SVG_W - PAD_LEFT - PAD_RIGHT
const CHART_H = SVG_H - PAD_TOP - PAD_BOTTOM

// ── 状态 ──────────────────────────────────────────────────────────────────
const prData = ref<PrCurveData | null>(null)
const loading = ref(true)
const loadError = ref<string | null>(null)

// ── 数据加载 ─────────────────────────────────────────────────────────────
onMounted(async () => {
  try {
    const data = await loadPrCurveData()
    prData.value = data
  } catch (e) {
    loadError.value = e instanceof Error ? e.message : 'Unknown error'
  } finally {
    loading.value = false
  }
})

// ── 坐标映射 ─────────────────────────────────────────────────────────────
function mapX(recall: number): number {
  return PAD_LEFT + recall * CHART_W
}

function mapY(precision: number): number {
  return PAD_TOP + (1 - precision) * CHART_H
}

// ── 路径生成（平滑曲线） ──────────────────────────────────────────────────
function buildPath(points: { x: number; y: number }[]): string {
  if (points.length < 2) return ''
  const mapped = points.map(p => ({ x: mapX(p.x), y: mapY(p.y) }))

  let d = `M ${mapped[0].x.toFixed(2)},${mapped[0].y.toFixed(2)}`
  for (let i = 1; i < mapped.length; i++) {
    d += ` L ${mapped[i].x.toFixed(2)},${mapped[i].y.toFixed(2)}`
  }
  return d
}

// ── 网格线 & 刻度（0.0 - 1.0，步长 0.2） ─────────────────────────────────
const gridLines = Array.from({ length: 6 }, (_, i) => {
  const v = i / 5
  const y = PAD_TOP + (1 - v) * CHART_H
  return { y: y.toFixed(2), label: v.toFixed(1) }
})

const xLabels = Array.from({ length: 6 }, (_, i) => {
  const v = i / 5
  const x = PAD_LEFT + v * CHART_W
  return { x: x.toFixed(2), label: v.toFixed(1) }
})

// ── 图例项数据 ───────────────────────────────────────────────────────────
interface LegendItem {
  key: string
  label: string
  ap: number
  color: string
  isAllClasses: boolean
}

function getLegendItems(data: PrCurveData): LegendItem[] {
  const items: LegendItem[] = data.series.map((s, idx) => ({
    key: s.key,
    label: s.label,
    ap: s.ap,
    color: CURVE_COLORS[idx % CURVE_COLORS.length],
    isAllClasses: false
  }))

  if (data.allClassesSeries) {
    items.push({
      key: data.allClassesSeries.key,
      label: data.allClassesSeries.label,
      ap: data.mAP50,
      color: ALL_CLASSES_COLOR,
      isAllClasses: true
    })
  }

  return items
}

// ── 样式常量 ─────────────────────────────────────────────────────────────
const LEGEND_ROW_HEIGHT = 26
const LEGEND_FONT_SIZE = 12
</script>

<template>
  <div class="w-full">
    <!-- 加载状态 -->
    <div v-if="loading" class="flex items-center justify-center" style="height: 400px;">
      <div class="flex items-center gap-2 text-slate-500 text-xs">
        <svg class="animate-spin w-4 h-4" viewBox="0 0 24 24" fill="none">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
        </svg>
        正在加载 P-R 曲线数据…
      </div>
    </div>

    <!-- 加载失败 -->
    <div v-else-if="loadError" class="flex items-center justify-center" style="height: 400px;">
      <div class="text-center">
        <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" class="mx-auto mb-2 text-slate-600">
          <circle cx="12" cy="12" r="10"/>
          <line x1="12" y1="8" x2="12" y2="12"/>
          <line x1="12" y1="16" x2="12.01" y2="16"/>
        </svg>
        <p class="text-xs text-slate-500">P-R 曲线加载失败</p>
        <p class="text-xs text-slate-600 mt-1">{{ loadError }}</p>
      </div>
    </div>

    <!-- SVG 图表 -->
    <div v-else-if="prData" class="w-full">
      <svg
        :width="SVG_W"
        :height="SVG_H"
        :viewBox="`0 0 ${SVG_W} ${SVG_H}`"
        class="block"
        style="color-scheme: dark; background: #0a0f1a;"
      >
        <defs>
          <clipPath id="chart-area">
            <rect :x="PAD_LEFT" :y="PAD_TOP" :width="CHART_W" :height="CHART_H"/>
          </clipPath>
        </defs>

        <!-- 图表背景 -->
        <rect :x="PAD_LEFT" :y="PAD_TOP" :width="CHART_W" :height="CHART_H" fill="#111827" rx="3"/>

        <!-- 水平网格线（更细的灰色虚线） -->
        <g stroke="#1e293b" stroke-width="0.8">
          <line
            v-for="gl in gridLines"
            :key="gl.y"
            :x1="PAD_LEFT"
            :y1="gl.y"
            :x2="PAD_LEFT + CHART_W"
            :y2="gl.y"
          />
        </g>

        <!-- 垂直网格线 -->
        <g stroke="#1e293b" stroke-width="0.8" stroke-dasharray="3,3">
          <line
            v-for="xl in xLabels"
            :key="xl.x"
            :x1="xl.x"
            :y1="PAD_TOP"
            :x2="xl.x"
            :y2="PAD_TOP + CHART_H"
          />
        </g>

        <!-- 坐标轴边框 -->
        <g stroke="#475569" stroke-width="1.5">
          <!-- Y 轴 -->
          <line :x1="PAD_LEFT" :y1="PAD_TOP" :x2="PAD_LEFT" :y2="PAD_TOP + CHART_H"/>
          <!-- X 轴 -->
          <line :x1="PAD_LEFT" :y1="PAD_TOP + CHART_H" :x2="PAD_LEFT + CHART_W" :y2="PAD_TOP + CHART_H"/>
        </g>

        <!-- Y 轴刻度标签 -->
        <g :font-size="11" font-family="'SF Mono', 'Consolas', monospace" text-anchor="end">
          <text
            v-for="gl in gridLines"
            :key="'yl-' + gl.y"
            :x="PAD_LEFT - 10"
            :y="parseFloat(gl.y) + 4"
            fill="#94a3b8"
          >{{ gl.label }}</text>
        </g>

        <!-- X 轴刻度标签 -->
        <g :font-size="11" font-family="'SF Mono', 'Consolas', monospace" text-anchor="middle">
          <text
            v-for="xl in xLabels"
            :key="'xl-' + xl.x"
            :x="xl.x"
            :y="PAD_TOP + CHART_H + 22"
            fill="#94a3b8"
          >{{ xl.label }}</text>
        </g>

        <!-- X 轴标题 -->
        <text
          :x="PAD_LEFT + CHART_W / 2"
          :y="SVG_H - 10"
          text-anchor="middle"
          fill="#cbd5e1"
          font-size="14"
          font-weight="500"
          font-family="'SF Mono', 'Consolas', monospace"
        >Recall</text>

        <!-- Y 轴标题 -->
        <text
          :x="16"
          :y="PAD_TOP + CHART_H / 2"
          text-anchor="middle"
          fill="#cbd5e1"
          font-size="14"
          font-weight="500"
          font-family="'SF Mono', 'Consolas', monospace"
          :transform="`rotate(-90, 16, ${PAD_TOP + CHART_H / 2})`"
        >Precision</text>

        <!-- PR 曲线（各类别，裁剪到图表区域） -->
        <g clip-path="url(#chart-area)">
          <path
            v-for="(series, idx) in prData.series"
            :key="series.key"
            :d="buildPath(series.points)"
            fill="none"
            :stroke="CURVE_COLORS[idx % CURVE_COLORS.length]"
            :stroke-width="CLASS_STROKE_WIDTH"
            stroke-linejoin="round"
            stroke-linecap="round"
          />
        </g>

        <!-- all classes 粗线（最上层，不裁剪保证完整显示） -->
        <path
          v-if="prData.allClassesSeries"
          :d="buildPath(prData.allClassesSeries.points)"
          fill="none"
          :stroke="ALL_CLASSES_COLOR"
          :stroke-width="ALL_CLASSES_STROKE_WIDTH"
          stroke-linejoin="round"
          stroke-linecap="round"
        />

        <!-- 图表边框 -->
        <rect
          :x="PAD_LEFT"
          :y="PAD_TOP"
          :width="CHART_W"
          :height="CHART_H"
          fill="none"
          stroke="#334155"
          stroke-width="1"
          rx="3"
        />

        <!-- 右侧图例区域 -->
        <g :transform="`translate(${PAD_LEFT + CHART_W + 18}, ${PAD_TOP + 8})`">
          <!-- 图例标题 -->
          <text
            x="0"
            y="0"
            fill="#e2e8f0"
            font-size="13"
            font-weight="600"
            font-family="'SF Mono', 'Consolas', monospace"
          >Classes</text>

          <!-- 图例分隔线 -->
          <line x1="0" y1="10" x2="130" y2="10" stroke="#334155" stroke-width="1"/>

          <!-- 图例项 -->
          <g v-for="(item, idx) in getLegendItems(prData)" :key="item.key">
            <!-- 图例线条 -->
            <line
              x1="0"
              :y1="28 + idx * LEGEND_ROW_HEIGHT"
              :x2="22"
              :y2="28 + idx * LEGEND_ROW_HEIGHT"
              :stroke="item.color"
              :stroke-width="item.isAllClasses ? 3 : 2"
              stroke-linecap="round"
            />
            <!-- 完整标签：类别名 + AP 值 -->
            <text
              x="30"
              :y="28 + idx * LEGEND_ROW_HEIGHT"
              :fill="item.isAllClasses ? '#ffffff' : '#e2e8f0'"
              :font-size="LEGEND_FONT_SIZE"
              font-family="'SF Mono', 'Consolas', monospace"
              :font-weight="item.isAllClasses ? '700' : '400'"
            >{{ item.label + ' ' + item.ap.toFixed(3) }}</text>
          </g>

          <!-- mAP@0.5 高亮标注 -->
          <g v-if="prData.allClassesSeries">
            <!-- 分隔线 -->
            <line
              x1="0"
              :y1="28 + prData.series.length * LEGEND_ROW_HEIGHT + 10"
              x2="130"
              :y2="28 + prData.series.length * LEGEND_ROW_HEIGHT + 10"
              stroke="#475569"
              stroke-width="1"
            />
            <!-- mAP 值（白色粗体突出） -->
            <text
              x="0"
              :y="28 + prData.series.length * LEGEND_ROW_HEIGHT + 28"
              fill="#ffffff"
              :font-size="LEGEND_FONT_SIZE + 2"
              font-weight="700"
              font-family="'SF Mono', 'Consolas', monospace"
            >mAP@0.5: {{ prData.mAP50.toFixed(3) }}</text>
          </g>
        </g>
      </svg>
    </div>
  </div>
</template>

<style scoped>
/* 确保 SVG 在深色背景下清晰可读 */
svg {
  filter: drop-shadow(0 0 20px rgba(0, 0, 0, 0.3));
}
</style>
