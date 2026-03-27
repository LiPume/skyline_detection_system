/**
 * Skyline — History API Client
 * REST client for detection record CRUD operations.
 */
import { API_BASE_URL } from '@/config/index'
import type { ModelConfig } from '@/types/skyline'

// ── Shared types ──────────────────────────────────────────────────────────────

export interface HistoryRecord {
  id: number
  created_at: string      // ISO 8601
  duration: number         // seconds
  video_name: string
  video_path: string | null
  detection_model: ModelConfig
  class_counts: Record<string, number>
  total_detections: number
  status: 'completed' | 'failed' | 'cancelled'
  thumbnail_path: string | null
  metadata: Record<string, unknown>
}

export interface SaveDetectionPayload {
  video_name: string
  duration: number
  detection_model: ModelConfig
  class_counts: Record<string, number>
  total_detections: number
  video_path?: string
  thumbnail_path?: string
  metadata?: Record<string, unknown>
}

export interface HistoryListResponse {
  items: HistoryRecord[]
  total: number
  page: number
  limit: number
}

// ── API functions ─────────────────────────────────────────────────────────────

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
): Promise<T> {
  const opts: RequestInit = {
    method,
    headers: { 'Content-Type': 'application/json' },
  }
  if (body) opts.body = JSON.stringify(body)

  const res = await fetch(`${API_BASE_URL}${path}`, opts)
  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(detail?.detail ?? `HTTP ${res.status}`)
  }
  if (res.status === 204) return undefined as T
  return res.json() as Promise<T>
}

/** POST /api/history — save a new detection record */
export function saveDetection(payload: SaveDetectionPayload): Promise<HistoryRecord> {
  return request<HistoryRecord>('POST', '/api/history', payload)
}

/** GET /api/history — list records with optional pagination */
export function listHistory(params?: {
  page?: number
  limit?: number
  status?: string
}): Promise<HistoryListResponse> {
  const qs = new URLSearchParams()
  if (params?.page)  qs.set('page',   String(params.page))
  if (params?.limit) qs.set('limit',  String(params.limit))
  if (params?.status) qs.set('status', params.status)
  const query = qs.toString()
  return request<HistoryListResponse>(
    'GET',
    `/api/history${query ? `?${query}` : ''}`,
  )
}

/** GET /api/history/:id — fetch a single record */
export function getHistory(id: number): Promise<HistoryRecord> {
  return request<HistoryRecord>('GET', `/api/history/${id}`)
}

/** DELETE /api/history/:id — delete a record */
export function deleteHistory(id: number): Promise<void> {
  return request<void>('DELETE', `/api/history/${id}`)
}

/** GET /api/history/:id/video — download the original video file */
export function getVideoUrl(id: number): string {
  return `${API_BASE_URL}/api/history/${id}/video`
}

/** GET /api/history/:id/data — download detection data as JSON */
export function getDataUrl(id: number): string {
  return `${API_BASE_URL}/api/history/${id}/data`
}
