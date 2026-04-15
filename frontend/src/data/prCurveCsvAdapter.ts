/**
 * Skyline — PR 曲线 CSV 数据适配器
 *
 * 职责：
 *   - 读取 /metrics/pr_curve_plot_data_VisDrone.csv
 *   - 解析各类别 PR 曲线数据 points
 *   - 计算每类 AP（沿 recall 方向积分）
 *   - 计算 all classes 平均 PR 曲线与 mAP@0.5
 */

export interface PrCurvePoint {
  x: number  // recall
  y: number  // precision
}

export interface PrCurveSeries {
  key: string
  label: string
  points: PrCurvePoint[]
  ap: number
}

export interface PrCurveData {
  series: PrCurveSeries[]
  allClassesSeries: PrCurveSeries | null
  mAP50: number
}

// 类别标签映射（中英文对照）
const CLASS_LABELS: Record<string, string> = {
  pedestrian: 'pedestrian',
  people: 'people',
  bicycle: 'bicycle',
  car: 'car',
  van: 'van',
  truck: 'truck',
  tricycle: 'tricycle',
  'awning-tricycle': 'awning-tricycle',
  bus: 'bus',
  motor: 'motor',
}

// 调色板（固定顺序，与组件内一致）
const CLASS_COLORS = [
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

/**
 * 计算单条 PR 曲线的 AP（Average Precision）
 * 使用梯形法则（Trapezoidal Rule）对 recall 方向积分
 * AP = Σ P(r) * Δr（每个区间的 precision × recall 增量）
 */
function computeAP(points: PrCurvePoint[]): number {
  if (points.length < 2) return 0

  let ap = 0
  for (let i = 1; i < points.length; i++) {
    const prev = points[i - 1]
    const curr = points[i]
    const deltaR = curr.x - prev.x
    if (deltaR > 0) {
      // 梯形积分：面积 = (P1 + P2) / 2 * Δr
      const avgPrecision = (prev.y + curr.y) / 2
      ap += avgPrecision * deltaR
    }
  }

  return Math.max(0, Math.min(1, ap))
}

/**
 * 解析 CSV 文本，返回 { recalls[], precisionsByClass{} }
 */
function parseCSV(csvText: string): {
  recalls: number[]
  precisionsByClass: Record<string, number[]>
  classKeys: string[]
} {
  const lines = csvText.trim().split('\n')
  if (lines.length < 2) {
    return { recalls: [], precisionsByClass: {}, classKeys: [] }
  }

  const header = lines[0].split(',')
  const classKeys = header.slice(1).map(col => col.replace('Precision_', ''))

  const recalls: number[] = []
  const precisionsByClass: Record<string, number[]> = {}
  classKeys.forEach(k => { precisionsByClass[k] = [] })

  for (let i = 1; i < lines.length; i++) {
    const values = lines[i].split(',')
    if (values.length < header.length) continue

    const recall = parseFloat(values[0])
    if (isNaN(recall)) continue

    recalls.push(recall)
    classKeys.forEach((k, idx) => {
      const p = parseFloat(values[idx + 1])
      precisionsByClass[k].push(isNaN(p) ? 0 : p)
    })
  }

  return { recalls, precisionsByClass, classKeys }
}

/**
 * 加载 PR 曲线 CSV 数据，解析各类别曲线并计算 AP
 */
export async function loadPrCurveData(): Promise<PrCurveData> {
  const response = await fetch('/metrics/pr_curve_plot_data_VisDrone.csv')
  if (!response.ok) {
    throw new Error(`Failed to load PR curve CSV: ${response.status}`)
  }

  const csvText = await response.text()
  const { recalls, precisionsByClass, classKeys } = parseCSV(csvText)

  if (recalls.length === 0 || classKeys.length === 0) {
    throw new Error('Invalid CSV data: no recall points or class columns found')
  }

  // 构建各类别 series
  const series: PrCurveSeries[] = classKeys.map((key, idx) => {
    const points: PrCurvePoint[] = recalls.map((r, i) => ({
      x: r,
      y: precisionsByClass[key][i],
    }))
    const ap = computeAP(points)
    return {
      key,
      label: CLASS_LABELS[key] ?? key,
      points,
      ap,
    }
  })

  // 计算 all classes 平均曲线
  const numClasses = classKeys.length
  const allPoints: PrCurvePoint[] = recalls.map((r, i) => {
    let sumPrecision = 0
    classKeys.forEach(k => {
      sumPrecision += precisionsByClass[k][i] ?? 0
    })
    return {
      x: r,
      y: sumPrecision / numClasses,
    }
  })

  const mAP50 = computeAP(allPoints)

  const allClassesSeries: PrCurveSeries = {
    key: 'all',
    label: 'all classes',
    points: allPoints,
    ap: mAP50,
  }

  return {
    series,
    allClassesSeries,
    mAP50,
  }
}

/**
 * 获取类别颜色（固定调色板，按顺序循环）
 */
export function getClassColor(index: number): string {
  return CLASS_COLORS[index % CLASS_COLORS.length]
}

/**
 * 获取 all classes 专用颜色
 */
export const ALL_CLASSES_COLOR = '#ffffff'
export const ALL_CLASSES_STROKE_WIDTH = 2.5