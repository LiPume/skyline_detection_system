"""
Skyline — WebSocket Video Stream Router
Full-duplex endpoint: /api/ws/video_stream
"""
import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from core.models import ErrorMessage, InferenceResult, VideoFrame
from core.inference import InferenceScheduler

logger = logging.getLogger(__name__)
router = APIRouter()


@router.websocket("/ws/video_stream")
async def video_stream_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    client = websocket.client
    logger.info("Client connected: %s", client)

    scheduler = InferenceScheduler()

    async def _send_result(result: InferenceResult) -> None:
        """Callback: push inference result back to this client."""
        try:
            await websocket.send_text(result.model_dump_json())
        except Exception as exc:
            logger.warning("Failed to send result to %s: %s", client, exc)

    inference_task = asyncio.create_task(scheduler.run(_send_result))

    try:
        while True:
            raw = await websocket.receive_text()

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
        # ── Circuit breaker: clean up inference task on any disconnect ─────
        scheduler.stop()
        inference_task.cancel()
        try:
            await inference_task
        except asyncio.CancelledError:
            pass
        logger.info("Resources released for client: %s", client)
