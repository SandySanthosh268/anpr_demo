from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base


class Camera(Base):
    __tablename__ = "cameras"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    rtsp_url: Mapped[str] = mapped_column(Text, nullable=False)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    events: Mapped[list[ANPREvent]] = relationship("ANPREvent", back_populates="camera_ref")

    def __repr__(self) -> str:
        return f"<Camera name={self.name} active={self.is_active}>"


class ANPREvent(Base):
    __tablename__ = "anpr_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plate_number: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    camera_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    camera_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("cameras.id", ondelete="SET NULL"), nullable=True
    )
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    ocr_confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    image_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_plate_text: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    camera_ref: Mapped[Camera | None] = relationship("Camera", back_populates="events")

    __table_args__ = (
        Index("ix_anpr_events_plate_timestamp", "plate_number", "timestamp"),
        Index("ix_anpr_events_camera_timestamp", "camera_name", "timestamp"),
    )

    def __repr__(self) -> str:
        return f"<ANPREvent plate={self.plate_number} ts={self.timestamp}>"
