"""
Skyline — Pydantic v2 Data Models
Strict schema enforcement for WebSocket message protocol.
Phase 3.1: Added model_id, prompt_classes, selected_classes for model capability driven inference.
Phase 5: Added session_ms / preprocess_ms / postprocess_ms to InferenceResult.
"""
from typing import Literal
from pydantic import BaseModel


# ── Upstream: Client → Server ─────────────────────────────────────────────────

class VideoFrame(BaseModel):
    """A single video frame sent from the frontend at ~20 FPS."""
    message_type: Literal["video_frame"]
    timestamp: float
    frame_id: int
    image_base64: str
    
    # ── Phase 3.1: Model capability driven fields ───────────────────────────
    model_id: str = "YOLO-World-V2"
    prompt_classes: list[str] = []
    selected_classes: list[str] = []
    
    # Legacy field alias for backward compatibility
    selected_model: str | None = None
    target_classes: list[str] = []


# ── Downstream: Server → Client ───────────────────────────────────────────────

class Detection(BaseModel):
    """A single object detection result."""
    class_name: str
    confidence: float
    bbox: tuple[int, int, int, int]


class InferenceResult(BaseModel):
    """
    Full inference response sent back per frame.

    Timing fields:
      session_ms:
        Pure model forward time (e.g. ONNX session.run()).
        None if unavailable (PT models — ultralytics does not expose internal timing).
      preprocess_ms:
        Input preprocessing time. For ONNX: _preprocess() (resize/letterbox/normalize).
        Also includes base64 decode. None if unavailable.
      postprocess_ms:
        Output postprocessing time. For ONNX: NMS + coordinate transform.
        None if unavailable.
      inference_time_ms:
        Total backend per-frame processing time (from _blocking_inference entry to return).
        Includes decode, inference, postprocess, and detector acquisition overhead —
        but NOT queue wait time. Always present.
      model_id:
        Canonical model identifier used for this frame. Used by the WS router to
        emit model_ready status messages on cold-load completion.
    """
    message_type: Literal["inference_result"] = "inference_result"
    frame_id: int
    timestamp: float
    inference_time_ms: float
    session_ms:     float | None = None   # 纯推理耗时（PT 不可用 → None）
    preprocess_ms: float | None = None   # 预处理耗时（PT 不可用 → None）
    postprocess_ms: float | None = None  # 后处理耗时（PT 不可用 → None）
    model_id: str = "YOLO-World-V2"       # 模型标识符（用于冷加载状态通知）
    detections: list[Detection]


class ErrorMessage(BaseModel):
    """Standard error envelope. Prevents frontend white-screen-of-death."""
    message_type: Literal["error"] = "error"
    error_code: int
    detail: str


class StatusMessage(BaseModel):
    """
    Lightweight server → client status notification (no progress, no percentage).

    Currently used for the model cold-load lifecycle:
      phase="model_loading"  — first cold load has started (model_id is loading)
      phase="model_ready"    — cold load completed (model_id is now cached)
    """
    message_type: Literal["status"] = "status"
    phase: Literal["model_loading", "model_ready"]
    model_id: str
