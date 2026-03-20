"""
Skyline — Detection History Database Models
SQLAlchemy 2.0 async models for persisting detection analysis records.
"""
from datetime import datetime
from typing import List, Optional

from sqlalchemy import String, Float, Integer, Text, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class DetectionRecord(Base):
    """
    Persisted record of a video analysis session.

    Attributes:
        id: Primary key (auto-increment)
        created_at: UTC timestamp when the record was created
        duration: Analysis duration in seconds
        video_name: Original video file name (without path)
        video_path: Full path to the stored video file (optional)
        model_name: AI model used (e.g., 'YOLO-World-V2')
        class_counts: JSON dict of class name -> detection count
        total_detections: Total number of objects detected
        status: 'completed' | 'failed' | 'cancelled'
        thumbnail_path: Optional path to a generated thumbnail
        metadata: Extra JSON metadata (e.g., video resolution, FPS)
    """
    __tablename__ = "detection_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    duration: Mapped[float] = mapped_column(Float, nullable=False)
    video_name: Mapped[str] = mapped_column(String(255), nullable=False)
    video_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    class_counts: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    total_detections: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    status: Mapped[str] = mapped_column(String(20), nullable=False, default="completed")
    thumbnail_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    extra_data: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "duration": self.duration,
            "video_name": self.video_name,
            "video_path": self.video_path,
            "model_name": self.model_name,
            "class_counts": self.class_counts,
            "total_detections": self.total_detections,
            "status": self.status,
            "thumbnail_path": self.thumbnail_path,
            "metadata": self.extra_data,
        }
