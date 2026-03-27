/**
 * Skyline — Model API Client
 * REST client for model discovery and capabilities.
 */
import { API_BASE_URL } from '@/config/index'
import type { ModelCapabilities, ModelListResponse } from '@/types/skyline'

async function request<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`)
  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(detail?.detail ?? `HTTP ${res.status}`)
  }
  return res.json() as Promise<T>
}

/** GET /api/models — list all available models */
export function listModels(): Promise<ModelListResponse> {
  return request<ModelListResponse>('/api/models')
}

/** GET /api/models/:id/capabilities — get full capabilities for a specific model */
export function getModelCapabilities(modelId: string): Promise<ModelCapabilities> {
  return request<ModelCapabilities>(`/api/models/${encodeURIComponent(modelId)}/capabilities`)
}
