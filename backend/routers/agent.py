"""
Skyline — Agent API Router
POST /api/agent/parse-task
"""
import logging
from pydantic import BaseModel, Field

from fastapi import APIRouter, HTTPException

from services.agent_service import parse_detection_task

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/agent", tags=["agent"])


# ── Schemas ────────────────────────────────────────────────────────────────────

class ParseTaskRequest(BaseModel):
    user_text: str = Field(..., min_length=1, max_length=1000)


class ParseTaskResponse(BaseModel):
    intent: str
    recommended_model_id: str
    target_classes: list[str]
    report_required: bool
    reason: str
    confidence: str


# ── Endpoint ────────────────────────────────────────────────────────────────────

@router.post("/parse-task", response_model=ParseTaskResponse)
async def parse_task(req: ParseTaskRequest):
    """
    Parse a natural-language detection task and return a structured recommendation.

    This endpoint only performs task understanding and plan recommendation.
    It does NOT start any real detection or modify system state.
    """
    try:
        result = parse_detection_task(req.user_text)
        return ParseTaskResponse(**result)
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except RuntimeError as exc:
        logger.error("[agent] parse_task failed: %s", exc)
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("[agent] Unexpected error in parse_task: %s", exc)
        raise HTTPException(status_code=500, detail="内部错误，请稍后重试") from exc
