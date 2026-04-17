"""
Skyline — Agent API Router
POST /api/agent/parse-task
"""
import logging
from pydantic import BaseModel, Field

from fastapi import APIRouter, HTTPException

from services.agent_service import parse_detection_task, generate_short_report

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


class ClassCountItem(BaseModel):
    className: str
    count: int


class GenerateReportRequest(BaseModel):
    modelId: str = Field(..., min_length=1)
    modelLabel: str = Field(..., min_length=1)
    targetClasses: list[str] = Field(default_factory=list)
    totalDetectionEvents: int = Field(ge=0)
    detectedClassCount: int = Field(ge=0)
    classCounts: list[ClassCountItem] = Field(default_factory=list)
    maxFrameDetections: int = Field(ge=0)
    durationSec: float | None = Field(default=None)
    summaryText: str = Field(default="")
    # ── 新增：任务上下文 ─────────────────────────────────────────────────────────
    taskPrompt: str | None = Field(default=None)
    taskIntent: str | None = Field(default=None)
    concernFocus: list[str] = Field(default_factory=list)
    # ── 新增：结构化场景证据（由前端启发式计算传入） ───────────────────────────
    sceneEvidence: dict | None = Field(default=None)


class GenerateReportResponse(BaseModel):
    reportText: str


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


@router.post("/generate-report", response_model=GenerateReportResponse)
async def generate_report(req: GenerateReportRequest):
    """
    Generate a short AI report based on structured detection summary.

    This endpoint is triggered manually by the user after detection completes.
    It takes structured summary data (not raw per-frame detections) and returns
    a concise Chinese-language report.
    """
    try:
        report_text = generate_short_report(
            model_id=req.modelId,
            model_label=req.modelLabel,
            target_classes=req.targetClasses,
            total_detection_events=req.totalDetectionEvents,
            detected_class_count=req.detectedClassCount,
            class_counts=[item.model_dump() for item in req.classCounts],
            max_frame_detections=req.maxFrameDetections,
            duration_sec=req.durationSec,
            summary_text=req.summaryText,
            task_prompt=req.taskPrompt,
            task_intent=req.taskIntent,
            concern_focus=req.concernFocus,
            scene_evidence=req.sceneEvidence,
        )
        return GenerateReportResponse(reportText=report_text)
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except RuntimeError as exc:
        logger.error("[agent] generate_report failed: %s", exc)
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("[agent] Unexpected error in generate_report: %s", exc)
        raise HTTPException(status_code=500, detail="内部错误，请稍后重试") from exc
