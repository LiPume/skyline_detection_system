"""
Skyline — Pydantic v2 Data Models
Strict schema enforcement for WebSocket message protocol.
Phase 3.1: Added model_id, prompt_classes, selected_classes for model capability driven inference.
"""
from typing import Literal
from pydantic import BaseModel, Field


# ── Upstream: Client → Server ─────────────────────────────────────────────────

class VideoFrame(BaseModel):
    """A single video frame sent from the frontend at ~20 FPS."""
    message_type: Literal["video_frame"]
    timestamp: float
    frame_id: int
    image_base64: str
    
    # ── Phase 3.1: Model capability driven fields ────────────────────────────
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
    """Full inference response sent back per frame."""
    message_type: Literal["inference_result"] = "inference_result"
    frame_id: int
    timestamp: float
    inference_time_ms: float
    detections: list[Detection]


class ErrorMessage(BaseModel):
    """Standard error envelope. Prevents frontend white-screen-of-death."""
    message_type: Literal["error"] = "error"
    error_code: int
    detail: str
