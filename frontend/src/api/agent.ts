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
