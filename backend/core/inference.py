"""
Skyline — Inference Scheduler (Phase 3: Live YOLO Pipeline)

Changes from Phase 2:
  - _blocking_inference now catches broad Exception (not just ValueError) to handle
    CUDA OOM, OpenCV decode errors, and unexpected model failures gracefully
  - CUDA OOM triggers a specific warning to aid GPU memory debugging
  - All other logic (LIFO scheduler, run_in_threadpool, circuit breaker) unchanged
"""
import asyncio
import logging
import time as _time
from typing import Callable, Coroutine, Optional

from starlette.concurrency import run_in_threadpool

from core.models import InferenceResult, VideoFrame
from models.model_manager import get_model

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "YOLO-World-V2"


# ── Inference function (runs in thread pool) ──────────────────────────────────

def _blocking_inference(frame: VideoFrame) -> InferenceResult:
    """
    CPU/GPU-bound inference — runs in a thread pool (keeps asyncio event loop free).

    Error handling:
      - ValueError:       base64 decode failure or unknown model name → empty detections
      - RuntimeError:     CUDA OOM or PyTorch errors → empty detections + specific log
      - Exception (catch-all): any other model failure → empty detections + error log
    """
    t0 = _time.perf_counter()

    selected_model = frame.selected_model or DEFAULT_MODEL
    target_classes = [c.strip() for c in frame.target_classes if c.strip()]

    logger.info(
        "收到模型 %s 的请求，目标: %s (frame_id=%d)",
        selected_model,
        target_classes,
        frame.frame_id,
    )

    detections = []
    try:
        model = get_model(selected_model)
        detections = model.infer(frame.image_base64, target_classes)

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
