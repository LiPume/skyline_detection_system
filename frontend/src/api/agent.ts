/**
 * Skyline — Agent API Client
 * REST client for the task-parsing agent endpoint.
 */
import { API_BASE_URL } from '@/config/index'

// ── Types ──────────────────────────────────────────────────────────────────────

export interface ParseTaskResponse {
  intent: string
  recommended_model_id: string
  target_classes: string[]
  report_required: boolean
  reason: string
  confidence: 'high' | 'medium' | 'low'
}

// ── Internal helpers ──────────────────────────────────────────────────────────

async function request<T>(path: string, body: object): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(detail?.detail ?? `HTTP ${res.status}`)
  }
  return res.json() as Promise<T>
}

// ── API functions ─────────────────────────────────────────────────────────────

/** POST /api/agent/parse-task — parse natural-language task → structured recommendation */
export function parseTask(userText: string): Promise<ParseTaskResponse> {
  return request<ParseTaskResponse>('/api/agent/parse-task', { user_text: userText })
}

// ── Short Report ─────────────────────────────────────────────────────────────────

export interface ClassCountItem {
  className: string
  count: number
}

export interface GenerateReportRequest {
  modelId: string
  modelLabel: string
  targetClasses: string[]
  totalDetectionEvents: number
  detectedClassCount: number
  classCounts: ClassCountItem[]
  maxFrameDetections: number
  durationSec: number | null
  summaryText: string
  taskPrompt?: string | null
  taskIntent?: string | null
  concernFocus?: string[]
  sceneEvidence?: SceneEvidence | null
}

export interface SceneEvidence {
  vehicleMix: Record<string, number>
  laneDensityHint: {
    leftRegionCount: number
    centerRegionCount: number
    rightRegionCount: number
  }
  peopleRisk: {
    pedestrianCount: number
    peopleCount: number
    hasPeopleOnRoadSide: boolean
  }
  congestionHint: {
    frameCrowdingHigh: boolean
    rightLaneHeavier: boolean
    leftLaneRelativelyClear: boolean
    suspectedCongestion: boolean
  }
  sceneHint: {
    suspectedHighway: boolean
    reason: string
  }
  confidenceHint: {
    analysisConfidence: 'high' | 'medium' | 'low'
  }
}

export interface GenerateReportResponse {
  reportText: string
}

/** POST /api/agent/generate-report — generate short AI report from detection summary */
export function generateReport(payload: GenerateReportRequest): Promise<GenerateReportResponse> {
  return request<GenerateReportResponse>('/api/agent/generate-report', payload)
}
