/**
 * useDelayedDisplay.ts — 本地视频延迟对齐播放 composable
 *
 * 目标：解决"本地视频持续播放，但检测框异步返回，导致框与目标位置有明显延迟/错位"的问题。
 *
 * 核心思路（V2 修复版）：
 * - 不再以"已发送帧数"作为显示推进基准（该方案在后端 LIFO 丢帧 / timeout /
 *   ack mismatch 时会失效，因为返回的 frame_id 序列不连续）
 * - 改为以"最近收到有效结果的 frame_id"为基础推进显示
 * - 查询 target = latestReceivedFrameId - DELAY_WINDOW_FRAMES
 * - lookup 时从 resultBuffer 的已有 key 中找最接近且 <= target 的帧
 *
 * 约束：
 * - 仅对 sourceType === 'local_file' 生效
 * - webcam 模式行为不变
 * - 不缓存原始图像帧
 * - 不重写 Detection 主状态机
 * - 不修改后端协议
 */

import { ref, computed, type Ref } from 'vue'
import type { Detection } from '@/types/skyline'

// ── 常量 ─────────────────────────────────────────────────────────────────────

/** 延迟窗口大小（帧数）。基于约 5 FPS 检测速率，2 秒 ≈ 10 帧 */
export const DELAY_WINDOW_FRAMES = 10

// ── 导出类型 ──────────────────────────────────────────────────────────────────

export type BufferPhase = 'buffering' | 'synced' | 'buffer_low'

export interface UseDelayedDisplayReturn {
  /** 当前应展示的 detections（从缓冲中查询） */
  displayDetections: Ref<Detection[]>
  /** 缓冲状态：buffering / synced / buffer_low */
  bufferPhase: Ref<BufferPhase>
  /** 缓冲池大小（已缓存的 frame_id 数） */
  bufferSize: Ref<number>
  /** 已达到同步状态（缓冲已填满）的标志 */
  isSynced: Ref<boolean>
  /**
   * 接收检测结果（由 WebSocket onMessage 调用）
   * 仅在 local_file 模式生效，webcam 模式直接透传。
   */
  pushResult: (frameId: number, detections: Detection[]) => void
  /**
   * 重置缓冲状态（所有切换点统一调用）。
   * 调用时机：加载新文件、重新开始分析、resetToStandby、停止分析、切换到 webcam。
   */
  reset: () => void
}

// ── 实现 ─────────────────────────────────────────────────────────────────────

export function useDelayedDisplay(): UseDelayedDisplayReturn {
  /**
   * 检测结果缓冲池
   * key: frame_id（后端返回的唯一帧编号）
   * value: 该帧的 detections 数组
   */
  const resultBuffer = ref<Map<number, Detection[]>>(new Map())

  /** 当前应展示的 detections */
  const displayDetections = ref<Detection[]>([])

  /** 缓冲状态 */
  const bufferPhase = ref<BufferPhase>('buffering')

  /** 缓冲是否已填满（稳定阶段） */
  const isSynced = ref(false)

  /**
   * 迄今收到的最大 frame_id。
   * 作为延迟显示的推进基准——不再依赖 sentFrameCount，
   * 因为后端 timeout / ack mismatch 时返回的 frame_id 序列可能稀疏/跳跃。
   */
  let latestReceivedFrameId = -1

  /**
   * 所有收到过的 frame_id 有序集合（升序）。
   * 用于 lookup 时找"最接近且 <= target"的帧，而不是依赖连续 frame_id。
   */
  const receivedFrameIds = ref<number[]>([])

  // ── 工具 ───────────────────────────────────────────────────────────────────

  /**
   * 更新 latestReceivedFrameId 并维护 receivedFrameIds 有序数组。
   */
  function addReceivedFrameId(frameId: number) {
    if (frameId <= latestReceivedFrameId) return
    latestReceivedFrameId = frameId

    const ids = receivedFrameIds.value
    const idx = ids.findIndex(fid => fid > frameId)
    if (idx === -1) {
      ids.push(frameId)
    } else {
      ids.splice(idx, 0, frameId)
    }
  }

  /**
   * 从缓冲池中查找最接近（且 <=）targetFrameId 的可用结果。
   * 补偿机制：当精确帧缺失时，从所有已有 key 中找最近的 <= target 的帧。
   */
  function lookupDisplayDetections(targetFrameId: number): Detection[] {
    const buf = resultBuffer.value
    const ids = receivedFrameIds.value

    if (ids.length === 0) return []

    // 二分查找：从 ids 中找 <= targetFrameId 的最近一帧
    let lo = 0, hi = ids.length - 1, candidate = -1
    while (lo <= hi) {
      const mid = (lo + hi) >> 1
      if (ids[mid] <= targetFrameId) {
        candidate = ids[mid]
        lo = mid + 1
      } else {
        hi = mid - 1
      }
    }

    if (candidate === -1) return []
    return buf.get(candidate) ?? []
  }

  /**
   * 清理缓冲池中"比当前目标帧更旧"的历史结果。
   * 防止内存泄漏和旧数据残留。
   * 注意：同步清理 receivedFrameIds。
   */
  function pruneOldResults(targetFrameId: number) {
    const cutoff = targetFrameId - DELAY_WINDOW_FRAMES * 2
    if (cutoff < 0) return

    const buf = resultBuffer.value
    const ids  = receivedFrameIds.value

    // 同步清理 buf
    for (const fid of buf.keys()) {
      if (fid < cutoff) buf.delete(fid)
    }

    // 同步清理 ids（丢弃 < cutoff 的旧帧号）
    while (ids.length > 0 && ids[0] < cutoff) {
      ids.shift()
    }
  }

  /**
   * 计算当前应展示的目标 frame_id。
   *
   * 规则：
   * - 未同步（buffering）：返回 -1（不展示任何框）
   * - 已同步：以 latestReceivedFrameId 为基准，向回退 DELAY_WINDOW_FRAMES 帧
   *   作为"至少已收到结果"的展示目标
   *
   * 这种方式不依赖发送帧号，即使后端 timeout/lifo 导致返回序列稀疏，
   * 只要有结果回到缓冲，就能正确展示。
   */
  function getTargetFrameId(): number {
    if (!isSynced.value) return -1
    return latestReceivedFrameId - DELAY_WINDOW_FRAMES
  }

  /**
   * 尝试推进 displayDetections（当有新结果进入时调用）。
   *
   * 进入 synced 的条件：
   * 收到至少 DELAY_WINDOW_FRAMES 个有效结果后（latestReceivedFrameId >= DELAY_WINDOW_FRAMES - 1），
   * 且 lookup 能查到非空结果，才真正进入 synced 态。
   *
   * 这样可以防止：
   * - 前 N 帧 timeout 时，buffer.size < 阈值导致无法展示
   * - synced 后空洞导致 continuousCount 跌破阈值导致假性退 buffer
   */
  function tryAdvanceDisplay() {
    if (!isSynced.value) {
      // buffering 阶段：检查是否可进入 synced
      if (latestReceivedFrameId >= DELAY_WINDOW_FRAMES - 1) {
        const target = getTargetFrameId()
        if (target < 0) return
        const dets = lookupDisplayDetections(target)
        if (dets.length > 0) {
          isSynced.value = true
          bufferPhase.value = 'synced'
          displayDetections.value = dets
          pruneOldResults(target)
        } else {
          // 有足够帧号但查不到结果（说明结果全在更后面），继续 buffering
          bufferPhase.value = 'buffering'
        }
      } else {
        bufferPhase.value = 'buffering'
      }
    } else {
      // synced 阶段：正常推进展示帧
      const target = getTargetFrameId()
      if (target < 0) return
      const dets = lookupDisplayDetections(target)
      displayDetections.value = dets

      // synced 后仍可能因密集丢帧导致缓冲枯竭，降至 buffer_low 提示用户
      // 但不再回退 isSynced（避免频繁切换导致闪烁）
      if (resultBuffer.value.size < DELAY_WINDOW_FRAMES) {
        bufferPhase.value = 'buffer_low'
      } else {
        bufferPhase.value = 'synced'
      }
      pruneOldResults(target)
    }
  }

  // ── 核心 API ───────────────────────────────────────────────────────────────

  /**
   * pushResult — 接收后端返回的检测结果。
   * @param frameId 后端返回的 frame_id
   * @param detections 该帧的检测结果
   */
  function pushResult(frameId: number, detections: Detection[]) {
    // 写入缓冲池
    resultBuffer.value.set(frameId, detections)
    addReceivedFrameId(frameId)

    // 每次收到结果都尝试推进显示
    tryAdvanceDisplay()
  }

  /**
   * reset — 重置缓冲状态。
   * 调用时机：加载新文件、重新开始分析、resetToStandby、停止分析、切换到 webcam。
   */
  function reset() {
    resultBuffer.value.clear()
    displayDetections.value = []
    bufferPhase.value = 'buffering'
    isSynced.value = false
    latestReceivedFrameId = -1
    receivedFrameIds.value = []
  }

  const bufferSize = computed(() => resultBuffer.value.size)

  return {
    displayDetections,
    bufferPhase,
    bufferSize,
    isSynced,
    pushResult,
    reset,
  }
}
