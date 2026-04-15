/**
 * Skyline — YOLO 训练结果 CSV 适配器
 *
 * 职责：
 *   - fetch('/metrics/yolo_final_results.csv')
 *   - 解析 CSV
 *   - 转换为页面需要的 trainingHistory 数据结构
 *   - 计算真实 summaryMetrics 的部分字段
 *   - 计算 trainingSummary
 *
 * 本文件仅负责处理 CSV，不涉及其他数据源。
 */

import type { PerformanceReport } from './performanceReport.mock'

/** CSV 原始列名到页面字段名的映射 */
const COLUMN_MAP: Record<string, keyof PerformanceReport['trainingHistory'][number]> = {
  'epoch':               'epoch',
  'train/box_loss':      'trainBox',
  'train/cls_loss':      'trainCls',
  'train/dfl_loss':      'trainDfl',
  'val/box_loss':        'valBox',
  'val/cls_loss':        'valCls',
  'val/dfl_loss':        'valDfl',
  'metrics/precision(B)': 'precision',
  'metrics/recall(B)':    'recall',
  'metrics/mAP50(B)':     'mAP50',
  'metrics/mAP50-95(B)':  'mAP50_95',
  'lr/pg0':              'lr0',
  'lr/pg1':              'lr1',
  'lr/pg2':              'lr2',
}

/** 解析 CSV 文本，返回表头和行数据 */
function parseCsv(text: string): { headers: string[]; rows: string[][] } {
  const lines = text.trim().split('\n')
  // 处理 header 行：可能有前导空格
  const headers = parseCSVLine(lines[0])
  const rows = lines.slice(1).map(line => parseCSVLine(line))
  return { headers, rows }
}

/** 解析单行 CSV（逗号分隔，值可能带引号） */
function parseCSVLine(line: string): string[] {
  const result: string[] = []
  let current = ''
  let inQuotes = false

  for (let i = 0; i < line.length; i++) {
    const ch = line[i]
    if (ch === '"') {
      inQuotes = !inQuotes
    } else if (ch === ',' && !inQuotes) {
      result.push(current.trim())
      current = ''
    } else {
      current += ch
    }
  }
  result.push(current.trim())
  return result
}

/**
 * 将 CSV 原始行转换为 trainingHistory 条目
 * @param headers  表头数组
 * @param row      数据行
 */
function mapRowToHistoryEntry(
  headers: string[],
  row: string[]
): PerformanceReport['trainingHistory'][number] {
  const entry: Record<string, number> = { epoch: 0 }

  for (let i = 0; i < headers.length; i++) {
    const colName = headers[i].trim()
    const mappedKey = COLUMN_MAP[colName]
    if (mappedKey) {
      entry[mappedKey] = parseFloat(row[i])
    }
  }

  return entry as PerformanceReport['trainingHistory'][number]
}

/**
 * 计算 trainingSummary
 * bestEpoch: 取 mAP50_95 最大的 epoch，若并列取较大 epoch
 */
function computeTrainingSummary(history: PerformanceReport['trainingHistory']): PerformanceReport['trainingSummary'] {
  if (!history.length) {
    return {
      bestEpoch: 0,
      finalMap50: 0,
      finalMap50_95: 0,
      finalPrecision: 0,
      finalRecall: 0,
    }
  }

  // 找 mAP50_95 最大的 epoch（并列时取较大 epoch）
  let bestEpoch = history[0].epoch
  let bestMap5095 = history[0].mAP50_95

  for (const row of history) {
    if (row.mAP50_95 > bestMap5095 || (row.mAP50_95 === bestMap5095 && row.epoch > bestEpoch)) {
      bestEpoch = row.epoch
      bestMap5095 = row.mAP50_95
    }
  }

  // 取最后一个 epoch 的指标作为 final
  const last = history[history.length - 1]

  return {
    bestEpoch,
    finalMap50: last.mAP50,
    finalMap50_95: last.mAP50_95,
    finalPrecision: last.precision,
    finalRecall: last.recall,
  }
}

/**
 * 计算 summaryMetrics 中需要替换的 4 个字段
 * 取 CSV 最后一个 epoch 的指标值
 */
function computeSummaryMetricsFromHistory(
  history: PerformanceReport['trainingHistory']
): Pick<PerformanceReport['summaryMetrics'], 'map50' | 'map50_95' | 'precision' | 'recall'> {
  if (!history.length) {
    return { map50: 0, map50_95: 0, precision: 0, recall: 0 }
  }
  const last = history[history.length - 1]
  return {
    map50: last.mAP50,
    map50_95: last.mAP50_95,
    precision: last.precision,
    recall: last.recall,
  }
}

/**
 * 从 yolo_final_results.csv 加载并解析数据
 * 失败时抛出异常，由调用方 catch 处理
 */
export async function loadPerformanceCsvData(): Promise<{
  summaryMetrics: Pick<PerformanceReport['summaryMetrics'], 'map50' | 'map50_95' | 'precision' | 'recall'>
  trainingHistory: PerformanceReport['trainingHistory']
  trainingSummary: PerformanceReport['trainingSummary']
}> {
  const response = await fetch('/metrics/yolo_final_results.csv')
  if (!response.ok) {
    throw new Error(`CSV fetch failed: ${response.status}`)
  }

  const text = await response.text()
  const { headers, rows } = parseCsv(text)

  if (rows.length === 0) {
    throw new Error('CSV has no data rows')
  }

  const trainingHistory = rows.map(row => mapRowToHistoryEntry(headers, row))
  const summaryMetrics = computeSummaryMetricsFromHistory(trainingHistory)
  const trainingSummary = computeTrainingSummary(trainingHistory)

  return { summaryMetrics, trainingHistory, trainingSummary }
}
