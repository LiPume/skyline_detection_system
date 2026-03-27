// Skyline — Shared TypeScript type definitions
// Single source of truth for WebSocket protocol types and model capabilities

// ════════════════════════════════════════════════════════════════════════════════
// MODEL CAPABILITIES (Phase 3.1)
// ════════════════════════════════════════════════════════════════════════════════

export type ModelType = 'open_vocab' | 'closed_set'

export interface ModelCapabilities {
  model_id: string
  display_name: string
  model_type: ModelType
  supports_prompt: boolean
  prompt_editable: boolean
  supported_classes: string[]
  class_filter_enabled: boolean
  description: string
}

export interface ModelListItem {
  model_id: string
  display_name: string
  model_type: ModelType
  description: string
}

export interface ModelListResponse {
  models: ModelListItem[]
}

export interface ModelConfig {
  model_id: string
  display_name: string
  model_type: ModelType
  prompt_classes: string[]
  selected_classes: string[]
}

// ════════════════════════════════════════════════════════════════════════════════
// WEBSOCKET MESSAGE TYPES (Phase 3.1)
// ════════════════════════════════════════════════════════════════════════════════

// ── Upstream: Client → Server ──────────────────────────────────────────────────

export interface VideoFrame {
  message_type: 'video_frame'
  timestamp: number        // epoch seconds, used for E2E latency calculation
  frame_id: number         // monotonically increasing
  image_base64: string     // "data:image/jpeg;base64,..."
  // Phase 3.1: Model capability driven fields
  model_id: string         // model identifier (canonical, e.g. "YOLO-World-V2")
  prompt_classes: string[] // for open_vocab models: custom detection targets
  selected_classes: string[] // for closed_set models: filter which classes to display
  // Legacy fields for backward compatibility
  selected_model?: string
  target_classes?: string[]
}

// ── AI Engine ─────────────────────────────────────────────────────────────────

export const SUPPORTED_MODELS = ['YOLO-World-V2', 'YOLOv8-Base'] as const
export type SupportedModel = typeof SUPPORTED_MODELS[number]

// ── Downstream: Server → Client ────────────────────────────────────────────────

export interface Detection {
  class_name: string
  confidence: number                        // 0.0 – 1.0
  bbox: [number, number, number, number]    // [x_min, y_min, width, height] natural-res pixels
}

export interface InferenceResult {
  message_type: 'inference_result'
  frame_id: number
  timestamp: number          // echoed back from client — used for latency calc
  inference_time_ms: number  // pure model inference duration on backend
  detections: Detection[]
}

export interface ErrorMessage {
  message_type: 'error'
  error_code: number
  detail: string
}

export type ServerMessage = InferenceResult | ErrorMessage

// ── UI State ──────────────────────────────────────────────────────────────────

export type WsStatus = 'connecting' | 'connected' | 'disconnected'
export type VideoSourceType = 'webcam' | 'local_file'

// BBox color palette keyed by class name
export const CLASS_COLORS: Record<string, string> = {
  person: '#ff3366',
  car: '#ffcc00',
  truck: '#ff6600',
  bus: '#00ccff',
  bicycle: '#cc44ff',
  motorcycle: '#ff00cc',
  drone: '#00ff88',
  boat: '#0088ff',
  van: '#ff8800',
  pedestrian: '#ff3366',
}
export const DEFAULT_DETECTION_COLOR = '#00ff88'
