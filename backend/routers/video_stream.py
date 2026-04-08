"""
Skyline — WebSocket Video Stream Router
Full-duplex endpoint: /api/ws/video_stream

Features:
- Heartbeat ping/pong mechanism to detect dead connections
- Automatic cleanup on disconnect
- LIFO frame buffer with overflow protection
"""
import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from core.models import ErrorMessage, InferenceResult, StatusMessage, VideoFrame
from core.inference import InferenceScheduler

logger = logging.getLogger(__name__)
router = APIRouter()

# Heartbeat settings
HEARTBEAT_INTERVAL_MS = 15_000  # Send ping every 15 seconds
HEARTBEAT_TIMEOUT_MS = 20_000    # Connection considered dead if no pong in 20 seconds
PING_MESSAGE = "__heartbeat_ping__"
PONG_MESSAGE = "__heartbeat_pong__"


@router.websocket("/ws/video_stream")
async def video_stream_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    client = websocket.client
    logger.info("Client connected: %s", client)

    scheduler = InferenceScheduler()
    heartbeat_task: asyncio.Task | None = None
    last_pong_time: float = 0

    # ── Phase 5+: model cold-load tracking ─────────────────────────────────
    # Tracks which model_ids have already triggered a "model_loading" broadcast
    # to avoid sending duplicate messages when the same model is re-requested.
    # Access is single-threaded (only the scheduler's worker thread writes,
    # only the WS event loop reads).
    _cold_loaded_models: set[str] = set()

    def _cold_load_callback(model_id: str) -> None:
        """
        Called from the inference worker thread via ModelManager callback.
        Schedules a model_loading status message onto the WS event loop.
        Uses run_coroutine_threadsafe (thread-safe) instead of create_task
        to avoid get_running_loop() in the worker thread.
        """
        loop = asyncio.get_running_loop()
        coro = websocket.send_text(
            StatusMessage(phase="model_loading", model_id=model_id).model_dump_json()
        )
        asyncio.run_coroutine_threadsafe(coro, loop)

    # Register the cold-load hook so ModelManager can notify us when a model
    # is first instantiated.  This callback runs inside the worker thread,
    # synchronously before the inference call returns.
    from models.model_manager import set_cold_load_callback
    set_cold_load_callback(_cold_load_callback)

    async def _send_result(result: InferenceResult) -> None:
        """Callback: push inference result back to this client."""
        # ── Phase 5+: emit model_ready if this was a cold-load frame ──────────
        model_id = result.model_id
        if model_id not in _cold_loaded_models:
            _cold_loaded_models.add(model_id)
            try:
                await websocket.send_text(
                    StatusMessage(phase="model_ready", model_id=model_id).model_dump_json()
                )
            except Exception as exc:
                logger.warning("Failed to send model_ready to %s: %s", client, exc)

        try:
            await websocket.send_text(result.model_dump_json())
        except Exception as exc:
            logger.warning("Failed to send result to %s: %s", client, exc)

    async def heartbeat_loop() -> None:
        """Send periodic pings to detect dead connections."""
        nonlocal last_pong_time
        last_pong_time = asyncio.get_event_loop().time()

        while True:
            await asyncio.sleep(HEARTBEAT_INTERVAL_MS / 1000)
            try:
                await websocket.send_text(PING_MESSAGE)
                logger.debug("Sent heartbeat ping to %s", client)
            except Exception:
                logger.debug("Heartbeat failed for %s, connection may be dead", client)
                break

    async def wait_for_pong() -> bool:
        """Wait for pong response with timeout."""
        nonlocal last_pong_time
        try:
            msg = await asyncio.wait_for(
                websocket.receive_text(),
                timeout=HEARTBEAT_TIMEOUT_MS / 1000
            )
            if msg == PONG_MESSAGE:
                last_pong_time = asyncio.get_event_loop().time()
                return True
            # If it's not a pong, it might be a regular message (shouldn't happen normally)
            return False
        except asyncio.TimeoutError:
            logger.warning("Heartbeat timeout for client %s", client)
            return False

    # Start heartbeat task
    heartbeat_task = asyncio.create_task(heartbeat_loop())

    inference_task = asyncio.create_task(scheduler.run(_send_result))

    try:
        while True:
            # Use wait_for with timeout to allow checking heartbeat
            try:
                raw = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=HEARTBEAT_INTERVAL_MS / 1000 * 2
                )
            except asyncio.TimeoutError:
                # No message received, check if connection is still alive
                current_time = asyncio.get_event_loop().time()
                if current_time - last_pong_time > HEARTBEAT_TIMEOUT_MS / 1000:
                    logger.warning("Connection dead for client %s, no response", client)
                    break
                continue

            # Handle heartbeat messages
            if raw == PING_MESSAGE:
                try:
                    await websocket.send_text(PONG_MESSAGE)
                except Exception as exc:
                    logger.warning("Failed to send pong to %s: %s", client, exc)
                continue
            elif raw == PONG_MESSAGE:
                last_pong_time = asyncio.get_event_loop().time()
                continue

            # ── Pydantic v2 validation circuit breaker ────────────────────
            try:
                data = json.loads(raw)
                frame = VideoFrame.model_validate(data)
            except (ValidationError, json.JSONDecodeError, ValueError) as exc:
                err = ErrorMessage(error_code=422, detail=str(exc))
                await websocket.send_text(err.model_dump_json())
                continue

            # ── Push into LIFO scheduler (drops stale frame if AI is busy) ─
            await scheduler.push_frame(frame)

    except WebSocketDisconnect:
        logger.info("Client disconnected: %s", client)
    except Exception as exc:
        logger.error("Unexpected WS error from %s: %s", client, exc)
    finally:
        # ── Circuit breaker: clean up all tasks ────────────────────────────
        scheduler.stop()

        if heartbeat_task:
            heartbeat_task.cancel()
            try:
                await heartbeat_task
            except asyncio.CancelledError:
                pass

        inference_task.cancel()
        try:
            await inference_task
        except asyncio.CancelledError:
            pass

        logger.info("Resources released for client: %s", client)
