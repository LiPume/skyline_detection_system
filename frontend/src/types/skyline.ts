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
  timestamp: number          // echoed back from client — used for E2E latency calc
  /**
   * 后端单帧总处理耗时（不含网络传输）。
   * 口径：_blocking_inference() 从入口到返回的完整耗时。
   * 包含 get_detector() + detector.infer() + 结果构造，不含帧在队列中的等待时间。
   *
   * ⚠️ 注意：这 **不是** 纯模型推理时间（session_ms）。
   *   纯推理时间需要后端单独暴露 detector.infer() 内的计时，
   *   当前后端 inference_time_ms 包含 detector 加载等开销。
   */
  inference_time_ms: number
  /**
   * 纯模型 forward 耗时（不含预处理/后处理）。
   *
   * 来源：
   *   - ONNX: session.run() wall-clock 计时
   *   - PT: Ultralytics Results.speed["inference"]
   *
   * 注意：这是前端"纯推理耗时 / 纯推理 FPS"的直接来源，
   *       与 inference_time_ms 是不同概念。
   */
  session_ms: number
  /**
   * 预处理耗时：base64 decode + resize + normalize。
   *
   * 来源：
   *   - ONNX: decode_ms + _preprocess()
   *   - PT: Ultralytics Results.speed["preprocess"] + decode_ms
   */
  preprocess_ms: number
  /**
   * 后处理耗时：NMS + 坐标变换 + 类别过滤。
   *
   * 来源：
   *   - ONNX: _postprocess()
   *   - PT: Ultralytics Results.speed["postprocess"]
   */
  postprocess_ms: number
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
