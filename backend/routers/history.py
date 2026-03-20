"""
Skyline — Detection History API Router
REST API endpoints for CRUD operations on detection records.
"""
import os
from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from models.history import DetectionRecord


router = APIRouter(prefix="/history", tags=["history"])


# ── Request / Response Schemas ──────────────────────────────────────────────────

class SaveDetectionRequest(BaseModel):
    """Payload for creating a new detection record."""
    video_name: str = Field(..., description="Original video file name")
    duration: float = Field(..., ge=0, description="Analysis duration in seconds")
    model_name: str = Field(..., description="AI model name, e.g. 'YOLO-World-V2'")
    class_counts: dict = Field(default_factory=dict, description="Class name -> count mapping")
    total_detections: int = Field(default=0, ge=0)
    video_path: Optional[str] = Field(default=None)
    thumbnail_path: Optional[str] = Field(default=None)
    extra_data: dict = Field(default_factory=dict, description="Extra metadata stored as JSON")


class DetectionRecordResponse(BaseModel):
    """Response schema for a single detection record."""
    id: int
    created_at: str
    duration: float
    video_name: str
    video_path: Optional[str]
    model_name: str
    class_counts: dict
    total_detections: int
    status: str
    thumbnail_path: Optional[str]
    metadata: dict


class HistoryListResponse(BaseModel):
    """Paginated list of detection records."""
    items: List[DetectionRecordResponse]
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
    record = DetectionRecord(
        created_at=datetime.utcnow(),
        duration=req.duration,
        video_name=req.video_name,
        video_path=req.video_path,
        model_name=req.model_name,
        class_counts=req.class_counts,
        total_detections=req.total_detections,
        status="completed",
        thumbnail_path=req.thumbnail_path,
        extra_data=req.extra_data,
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
    export_data = {
        "record_id": record.id,
        "created_at": record.created_at.isoformat() if record.created_at else None,
        "video_info": {
            "name": record.video_name,
            "path": record.video_path,
            "duration_seconds": record.duration,
        },
        "model_info": {
            "name": record.model_name,
        },
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
