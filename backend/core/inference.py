"""
Skyline — Inference Scheduler (Refactored: Unified Runtime Architecture)

Changes from Phase 3.1:
  - inference.py no longer imports PT-specific modules
  - Calls get_detector(model_id) which dispatches to PTDetector or ONNXDetector internally
  - ModelManager reads RUNTIME_CONFIG[model_id].runtime_type to choose the factory
  - _blocking_inference sends unified args to detector.infer():
      open_vocab  → infer(image_base64, prompt_classes=[...], selected_classes=[])
      closed_set  → infer(image_base64, prompt_classes=[], selected_classes=[...])
    Post-inference class filtering is now handled INSIDE BaseDetector.infer().
  - Adding TensorRT / OpenVINO requires zero changes here

Error handling:
  - ValueError: base64 decode failure or unknown model name → empty detections
  - RuntimeError: CUDA OOM or PyTorch errors → empty detections + specific log
  - Exception (catch-all): any other model failure → empty detections + error log
"""

import asyncio
import logging
import time as _time
from typing import Callable, Coroutine, Optional

from starlette.concurrency import run_in_threadpool

from core.models import InferenceResult, VideoFrame
from models.model_manager import DetectorResult, get_detector
from models.registry import get_model_capabilities

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "YOLO-World-V2"


# ── Inference function (runs in thread pool) ──────────────────────────────────

def _blocking_inference(frame: VideoFrame) -> InferenceResult:
    """
    CPU/GPU-bound inference — runs in a thread pool (keeps asyncio event loop free).

    This function is completely runtime-agnostic. It does NOT know whether the
    detector uses PT or ONNX. It simply:
      1. Resolves model_id (with legacy fallback)
      2. Validates model exists in registry
      3. Determines which class list to send based on model_type
      4. Calls detector.infer() — all runtime logic is encapsulated inside the detector
      5. Wraps result in InferenceResult

    open_vocab models:    infer(image_base64, prompt_classes=[...], selected_classes=[])
    closed_set models:     infer(image_base64, prompt_classes=[], selected_classes=[...])
    """
    t0 = _time.perf_counter()

    # ── 1. Resolve model_id (with legacy selected_model fallback) ─────────────
    selected_model = frame.model_id or frame.selected_model or DEFAULT_MODEL

    # ── 2. Validate model is registered ───────────────────────────────────────
    caps = get_model_capabilities(selected_model)
    if caps is None:
        logger.warning("[frame %d] Unknown model '%s', falling back to %s",
                       frame.frame_id, selected_model, DEFAULT_MODEL)
        selected_model = DEFAULT_MODEL
        caps = get_model_capabilities(selected_model)

    # ── 3. Build unified call args based on model_type ────────────────────────
    if caps.model_type == "open_vocab":
        # Open vocabulary: use prompt_classes (or legacy target_classes), no selected_classes
        raw_prompts = frame.prompt_classes or frame.target_classes or []
        prompt_classes: list[str] = []
        for c in raw_prompts:
            prompt_classes.extend(x.strip().lower() for x in c.split(",") if x.strip())
        if not prompt_classes:
            prompt_classes = ["object"]
        selected_classes: list[str] = []

        logger.info(
            "[frame %d] open_vocab → model=%s prompt_classes=%s",
            frame.frame_id, selected_model, prompt_classes
        )

    else:
        # Closed set: ignore prompt_classes, use selected_classes for filtering
        # The detector handles post-inference filtering internally.
        prompt_classes = []
        selected_classes = list(frame.selected_classes)

        logger.info(
            "[frame %d] closed_set → model=%s selected_classes=%s",
            frame.frame_id, selected_model, selected_classes
        )

    # ── 4. Dispatch to unified detector interface ───────────────────────────────
    detector_result = None  # type: ignore

    try:
        # get_detector() returns PTDetector or ONNXDetector based on RUNTIME_CONFIG.
        # inference.py has NO knowledge of the runtime type.
        detector = get_detector(selected_model)

        # detector.infer() returns DetectorResult(detections, session_ms, preprocess_ms, postprocess_ms)
        detector_result = detector.infer(
            image_base64=frame.image_base64,
            prompt_classes=prompt_classes,
            selected_classes=selected_classes,
        )

        logger.info(
            "[frame %d] %s → %d detection(s)",
            frame.frame_id, selected_model, len(detector_result.detections)
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

    # Default to empty result if detector failed
    if detector_result is None:
        detector_result = DetectorResult(detections=[], session_ms=None, preprocess_ms=None, postprocess_ms=None)

    elapsed_ms = (_time.perf_counter() - t0) * 1000

    return InferenceResult(
        frame_id=frame.frame_id,
        timestamp=frame.timestamp,
        inference_time_ms=round(elapsed_ms, 3),
        session_ms=round(detector_result.session_ms, 3) if detector_result.session_ms is not None else None,
        preprocess_ms=round(detector_result.preprocess_ms, 3) if detector_result.preprocess_ms is not None else None,
        postprocess_ms=round(detector_result.postprocess_ms, 3) if detector_result.postprocess_ms is not None else None,
        model_id=selected_model,
        detections=detector_result.detections,
    )


# ── LIFO Scheduler (unchanged) ────────────────────────────────────────────────

class InferenceScheduler:
    """
    LIFO single-frame-buffer scheduler with overflow protection.

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
        self._dropped_frames = 0  # Track dropped frames for monitoring

    async def push_frame(self, frame: VideoFrame) -> None:
        async with self._lock:
            # Track if we're about to drop a frame (overwriting _latest_frame)
            if self._latest_frame is not None:
                self._dropped_frames += 1
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
