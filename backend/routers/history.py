"""
Skyline — Detection History API Router
REST API endpoints for CRUD operations on detection records.
"""
import os
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from models.history import DetectionRecord


router = APIRouter(prefix="/history", tags=["history"])


# ── Request / Response Schemas ──────────────────────────────────────────────────

class ModelConfig(BaseModel):
    """Model configuration used in a detection session."""
    model_id: str
    display_name: str
    model_type: str
    prompt_classes: list[str] = []
    selected_classes: list[str] = []


class SaveDetectionRequest(BaseModel):
    """Payload for creating a new detection record."""
    video_name: str
    duration: float = Field(ge=0)
    detection_model: ModelConfig
    class_counts: dict = {}
    total_detections: int = 0
    video_path: str | None = None
    thumbnail_path: str | None = None
    extra_data: dict = {}


class DetectionRecordResponse(BaseModel):
    """Response schema for a single detection record."""
    id: int
    created_at: str
    duration: float
    video_name: str
    video_path: str | None
    detection_model: ModelConfig
    class_counts: dict
    total_detections: int
    status: str
    thumbnail_path: str | None
    metadata: dict


class HistoryListResponse(BaseModel):
    """Paginated list of detection records."""
    items: list[DetectionRecordResponse]
    total: int
    page: int
    limit: int


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post("", response_model=DetectionRecordResponse, status_code=201)
async def create_detection_record(
    req: SaveDetectionRequest,
    db: AsyncSession = Depends(get_db),
) -> DetectionRecordResponse:
    """
    Save a new detection record after analysis completes.
    Called automatically by the frontend when a video analysis session ends.
    """
    # Store model config in extra_data for backward compatibility
    extra_data = req.extra_data.copy()
    extra_data["model_config"] = req.detection_model.model_dump()
    
    record = DetectionRecord(
        created_at=datetime.utcnow(),
        duration=req.duration,
        video_name=req.video_name,
        video_path=req.video_path,
        model_name=req.detection_model.display_name,  # Keep model_name for backward compat
        class_counts=req.class_counts,
        total_detections=req.total_detections,
        status="completed",
        thumbnail_path=req.thumbnail_path,
        extra_data=extra_data,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return DetectionRecordResponse(**record.to_dict())


@router.get("", response_model=HistoryListResponse)
async def list_detection_records(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    status: Optional[str] = Query(None, description="Filter by status: completed | failed | cancelled"),
    db: AsyncSession = Depends(get_db),
) -> HistoryListResponse:
    """
    Retrieve a paginated list of detection records, newest first.
    """
    # Build query
    base_query = select(DetectionRecord)
    count_query = select(func.count(DetectionRecord.id))

    if status:
        base_query = base_query.where(DetectionRecord.status == status)
        count_query = count_query.where(DetectionRecord.status == status)

    # Total count
    total = await db.scalar(count_query)

    # Paginated results, ordered by created_at DESC
    offset = (page - 1) * limit
    query = (
        base_query
        .order_by(DetectionRecord.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(query)
    records = result.scalars().all()

    return HistoryListResponse(
        items=[DetectionRecordResponse(**r.to_dict()) for r in records],
        total=total or 0,
        page=page,
        limit=limit,
    )


@router.get("/{record_id}", response_model=DetectionRecordResponse)
async def get_detection_record(
    record_id: int,
    db: AsyncSession = Depends(get_db),
) -> DetectionRecordResponse:
    """Get a single detection record by ID."""
    result = await db.execute(
        select(DetectionRecord).where(DetectionRecord.id == record_id)
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail=f"Record {record_id} not found")
    return DetectionRecordResponse(**record.to_dict())


class UpdateExtraDataRequest(BaseModel):
    """Payload for merging extra_data fields into an existing record."""
    extra_data: dict


@router.patch("/{record_id}/extra-data", response_model=DetectionRecordResponse)
async def patch_detection_record_extra_data(
    record_id: int,
    req: UpdateExtraDataRequest,
    db: AsyncSession = Depends(get_db),
) -> DetectionRecordResponse:
    """
    Merge new fields into extra_data of an existing detection record.

    仅做顶层 key merge，不覆盖已有字段（除请求中显式传入的 key）。
    用于：AI 短报告生成成功后补写回历史记录。
    """
    result = await db.execute(
        select(DetectionRecord).where(DetectionRecord.id == record_id)
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail=f"Record {record_id} not found")

    # 顶层 key merge：请求中传入的字段直接覆盖，对端已有 key 则保留
    merged = dict(record.extra_data or {})
    merged.update(req.extra_data)
    record.extra_data = merged

    await db.commit()
    await db.refresh(record)
    return DetectionRecordResponse(**record.to_dict())


@router.delete("/{record_id}", status_code=204)
async def delete_detection_record(
    record_id: int,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a detection record by ID."""
    result = await db.execute(
        delete(DetectionRecord).where(DetectionRecord.id == record_id)
    )
    await db.commit()
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail=f"Record {record_id} not found")


# ── Download Endpoints ──────────────────────────────────────────────────────────

@router.get("/{record_id}/video")
async def download_video(
    record_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Download the original video file for a detection record.
    Returns the video file or an error if the file path is not available.
    """
    result = await db.execute(
        select(DetectionRecord).where(DetectionRecord.id == record_id)
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail=f"Record {record_id} not found")

    if not record.video_path:
        raise HTTPException(status_code=404, detail="No video path recorded for this analysis")

    video_path = record.video_path
    # Handle both absolute and relative paths
    if not os.path.isabs(video_path):
        # Relative to backend directory
        video_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), video_path)

    if not os.path.exists(video_path):
        raise HTTPException(status_code=404, detail=f"Video file not found: {video_path}")

    return FileResponse(
        path=video_path,
        filename=record.video_name,
        media_type="video/mp4",
    )


@router.get("/{record_id}/data")
async def export_detection_data(
    record_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Export all detection data for a record as a structured JSON file.
    Includes: video info, model info, class counts, and detailed detection data.
    """
    result = await db.execute(
        select(DetectionRecord).where(DetectionRecord.id == record_id)
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail=f"Record {record_id} not found")

    # Build structured export data
    # Try to extract model_config from extra_data
    model_config = None
    if record.extra_data and "model_config" in record.extra_data:
        model_config = record.extra_data["model_config"]
    else:
        model_config = {
            "model_id": record.model_name,
            "display_name": record.model_name,
            "model_type": "unknown",
            "prompt_classes": [],
            "selected_classes": [],
        }
    
    export_data = {
        "record_id": record.id,
        "created_at": record.created_at.isoformat() if record.created_at else None,
        "video_info": {
            "name": record.video_name,
            "path": record.video_path,
            "duration_seconds": record.duration,
        },
        "model_info": model_config,
        "statistics": {
            "total_detections": record.total_detections,
            "class_counts": record.class_counts,
        },
        "metadata": record.extra_data,
    }

    import json
    json_bytes = json.dumps(export_data, indent=2, ensure_ascii=False).encode("utf-8")

    return StreamingResponse(
        iter([json_bytes]),
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="detection_{record_id}_{record.video_name}.json"'
        },
    )
