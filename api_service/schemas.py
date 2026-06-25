from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


# ─── Camera ───────────────────────────────────────────────────────────────────

class CameraRegisterRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    rtsp_url: str = Field(..., min_length=10)
    location: Optional[str] = Field(default=None, max_length=255)


class CameraResponse(BaseModel):
    id: int
    name: str
    rtsp_url: str
    location: Optional[str]
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ─── ANPR Events ──────────────────────────────────────────────────────────────

class ANPREventResponse(BaseModel):
    id: int
    plate_number: str
    timestamp: datetime
    camera_name: str
    confidence: float
    ocr_confidence: float
    image_path: Optional[str]
    raw_plate_text: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class PaginatedEventsResponse(BaseModel):
    items: List[ANPREventResponse]
    total: int
    page: int
    page_size: int
    pages: int


class EventCountResponse(BaseModel):
    total: int
    camera_name: Optional[str]
    date: Optional[str]


# ─── Analytics ────────────────────────────────────────────────────────────────

class DailyCountItem(BaseModel):
    date: str
    count: int


class HourlyCountItem(BaseModel):
    hour: int
    count: int


class FrequentPlateItem(BaseModel):
    plate_number: str
    count: int
    first_seen: Optional[str]
    last_seen: Optional[str]


class EntryExitResponse(BaseModel):
    plate_number: str
    first_seen: Optional[str]
    last_seen: Optional[str]
    total_visits: int
    duration_seconds: Optional[int]


# ─── WebSocket ────────────────────────────────────────────────────────────────

class WSEvent(BaseModel):
    plate: str
    timestamp: str
    confidence: float
    ocr_confidence: float
    camera: str
    image_path: Optional[str] = None
    bbox: Optional[List[int]] = None


# ─── Health ───────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    version: str
    pipeline_running: bool
    camera_connected: bool
    ws_clients: int
