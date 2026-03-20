"""
Skyline — Pydantic v2 Data Models
Strict schema enforcement for WebSocket message protocol.
Phase 2: Added selected_model and target_classes to VideoFrame.
"""
from typing import Literal, List, Tuple
from pydantic import BaseModel, Field


# ── Upstream: Client → Server ─────────────────────────────────────────────────

class VideoFrame(BaseModel):
    """A single video frame sent from the frontend at ~20 FPS."""
    message_type: Literal["video_frame"]
    timestamp: float = Field(..., description="Client send timestamp (epoch seconds)")
    frame_id: int    = Field(..., ge=0, description="Monotonically increasing frame counter")
    image_base64: str = Field(..., min_length=10, description="JPEG Base64 with data URI prefix")
    # ── Phase 2: AI engine control fields ─────────────────────────────────
    selected_model: str = Field(
        default="YOLO-World-V2",
        description="Model name to use for inference (must match ModelManager registry)",
    )
    target_classes: List[str] = Field(
        default_factory=list,
        description="Open-vocabulary target class names parsed from the user's prompt",
    )


# ── Downstream: Server → Client ───────────────────────────────────────────────

class Detection(BaseModel):
    """A single object detection result."""
    class_name: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    bbox: Tuple[int, int, int, int]  # [x_min, y_min, width, height] in natural resolution


class InferenceResult(BaseModel):
    """Full inference response sent back per frame."""
    message_type: Literal["inference_result"] = "inference_result"
    frame_id: int
    timestamp: float           # Original client timestamp — echoed back for latency calc
    inference_time_ms: float   # Pure model inference duration
    detections: List[Detection]


class ErrorMessage(BaseModel):
    """Standard error envelope. Prevents frontend white-screen-of-death."""
    message_type: Literal["error"] = "error"
    error_code: int
    detail: str
