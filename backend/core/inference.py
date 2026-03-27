"""
Skyline — Inference Scheduler (Phase 3.1: Model Capability Driven Inference)

Changes from Phase 3:
  - Now uses model_id from VideoFrame to select the correct model
  - Differentiates between open_vocab (YOLO-World) and closed_set (YOLOv8) models
  - open_vocab models: use prompt_classes as detection targets
  - closed_set models: use selected_classes for post-inference filtering
  - Added model capability validation and error handling
"""
import asyncio
import logging
import time as _time
from typing import Callable, Coroutine, Optional

from starlette.concurrency import run_in_threadpool

from core.models import InferenceResult, VideoFrame
from models.model_manager import get_model
from models.registry import get_model_capabilities, filter_supported_classes

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "YOLO-World-V2"


# ── Inference function (runs in thread pool) ──────────────────────────────────

def _blocking_inference(frame: VideoFrame) -> InferenceResult:
    """
    CPU/GPU-bound inference — runs in a thread pool (keeps asyncio event loop free).

    Model type handling:
      - open_vocab (YOLO-World): uses prompt_classes as detection targets
      - closed_set (YOLOv8): ignores prompt_classes, uses selected_classes for filtering

    Error handling:
      - ValueError: base64 decode failure or unknown model name → empty detections
      - RuntimeError: CUDA OOM or PyTorch errors → empty detections + specific log
      - Exception (catch-all): any other model failure → empty detections + error log
    """
    t0 = _time.perf_counter()

    # Resolve model_id with fallback for legacy selected_model field
    selected_model = frame.model_id or frame.selected_model or DEFAULT_MODEL
    
    # Get model capabilities to determine how to handle classes
    caps = get_model_capabilities(selected_model)
    if caps is None:
        logger.warning("[frame %d] Unknown model '%s', falling back to %s", 
                      frame.frame_id, selected_model, DEFAULT_MODEL)
        selected_model = DEFAULT_MODEL
        caps = get_model_capabilities(selected_model)

    # Determine which classes to use based on model type
    if caps.model_type == "open_vocab":
        # Open vocabulary model: use prompt_classes (or legacy target_classes)
        target_classes = frame.prompt_classes or frame.target_classes
        if not target_classes:
            target_classes = ["object"]  # Ultimate fallback for open vocab
        # Clean and normalize
        clean_classes: list[str] = []
        for c in target_classes:
            clean_classes.extend([x.strip().lower() for x in c.split(",") if x.strip()])
        if not clean_classes:
            clean_classes = ["object"]
        selected_classes_filter: list[str] = []  # No filtering for open vocab
    else:
        # Closed set model: ignore prompt_classes, use selected_classes for filtering
        clean_classes = []  # Not used for closed set
        # Filter selected_classes to only those supported by the model
        selected_classes_filter = filter_supported_classes(
            selected_model, 
            frame.selected_classes
        )
        logger.info(
            "[frame %d] Model '%s' (closed_set): selected_classes=%s → filtered=%s",
            frame.frame_id, selected_model, frame.selected_classes, selected_classes_filter
        )

    logger.info(
        "[frame %d] Inference request: model=%s (type=%s), prompt=%s, filter=%s",
        frame.frame_id, selected_model, caps.model_type, clean_classes, selected_classes_filter
    )

    detections = []
    try:
        model = get_model(selected_model)
        
        # For open_vocab models, pass clean_classes to infer()
        # For closed_set models, pass empty list (filtering is done post-inference)
        model_target_classes = clean_classes if caps.model_type == "open_vocab" else []
        
        detections = model.infer(frame.image_base64, model_target_classes)
        
        # Post-inference filtering for closed_set models
        if caps.model_type == "closed_set" and selected_classes_filter:
            original_count = len(detections)
            filter_set = {c.lower() for c in selected_classes_filter}
            detections = [
                d for d in detections 
                if d.class_name.lower() in filter_set
            ]
            logger.info(
                "[frame %d] Closed-set filter: %d → %d detections",
                frame.frame_id, original_count, len(detections)
            )

    except ValueError as exc:
        # Bad model name OR base64 decode failure
        logger.warning("[frame %d] Input error: %s", frame.frame_id, exc)

    except RuntimeError as exc:
        # CUDA OOM, cuDNN errors, PyTorch internal errors
        if "out of memory" in str(exc).lower():
            logger.error(
                "[frame %d] CUDA Out of Memory — consider reducing resolution or FPS. %s",
                frame.frame_id, exc,
            )
        else:
            logger.error("[frame %d] RuntimeError during inference: %s", frame.frame_id, exc)

    except Exception as exc:
        logger.error(
            "[frame %d] Unexpected inference error (%s): %s",
            frame.frame_id, type(exc).__name__, exc,
        )

    elapsed_ms = (_time.perf_counter() - t0) * 1000
    return InferenceResult(
        frame_id=frame.frame_id,
        timestamp=frame.timestamp,
        inference_time_ms=round(elapsed_ms, 3),
        detections=detections,
    )


# ── LIFO Scheduler (unchanged) ────────────────────────────────────────────────

class InferenceScheduler:
    """
    LIFO single-frame-buffer scheduler.

    When a new frame arrives while the AI thread is busy:
      - the queued frame is overwritten by the new one (stale frame dropped)
      - dashboard always shows the current moment, never accumulates lag

    Thread-safety: asyncio.Lock guards the _latest_frame slot.
    """

    def __init__(self) -> None:
        self._latest_frame: Optional[VideoFrame] = None
        self._lock = asyncio.Lock()
        self._has_frame = asyncio.Event()
        self._running = False

    async def push_frame(self, frame: VideoFrame) -> None:
        async with self._lock:
            self._latest_frame = frame
            self._has_frame.set()

    async def _pop_frame(self) -> VideoFrame:
        await self._has_frame.wait()
        async with self._lock:
            frame = self._latest_frame
            self._latest_frame = None
            self._has_frame.clear()
        return frame  # type: ignore[return-value]

    async def run(
        self,
        result_callback: Callable[[InferenceResult], Coroutine],
    ) -> None:
        self._running = True
        logger.info("InferenceScheduler started.")
        try:
            while self._running:
                frame = await self._pop_frame()
                if not self._running:
                    break
                try:
                    result = await run_in_threadpool(_blocking_inference, frame)
                    await result_callback(result)
                except Exception as exc:
                    logger.error("Scheduler loop error on frame %d: %s", frame.frame_id, exc)
        except asyncio.CancelledError:
            logger.info("InferenceScheduler loop cancelled.")
        finally:
            logger.info("InferenceScheduler stopped.")

    def stop(self) -> None:
        self._running = False
        self._has_frame.set()  # unblock any pending _pop_frame wait
