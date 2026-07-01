from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ────────────────────────────────────────────
    app_name: str = "ANPR System"
    app_env: str = "production"
    debug: bool = False
    secret_key: str = "change_me_in_production"

    # ── Database ───────────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://anpr_user:anpr_pass@localhost:5432/anpr_db"
    database_pool_size: int = 10
    database_max_overflow: int = 20

    # ── Camera ─────────────────────────────────────────────────
    rtsp_url: str = "rtsp://admin:password@192.168.1.100:554/stream1"
    video_source: str = ""  # If set, used instead of rtsp_url at startup (local file path)
    camera_name: str = "Gate1"
    frame_skip: int = Field(default=5, ge=1, le=30)
    reconnect_delay: int = Field(default=5, ge=1)
    max_reconnect_attempts: int = Field(default=10, ge=1)

    # ── Detection ──────────────────────────────────────────────
    yolo_model_path: str = "models/yolov8_license_plate.pt"
    yolo_confidence: float = Field(default=0.5, ge=0.1, le=1.0)
    yolo_iou: float = Field(default=0.45, ge=0.1, le=1.0)
    detection_device: str = "cpu"

    # ── OCR ────────────────────────────────────────────────────
    ocr_confidence_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    ocr_lang: str = "en"

    # ── Validation ─────────────────────────────────────────────
    plate_confidence_min: float = Field(default=0.6, ge=0.0, le=1.0)
    duplicate_window_seconds: int = Field(default=30, ge=1)

    # ── Snapshots ──────────────────────────────────────────────
    snapshot_dir: Path = Path("snapshots")
    snapshot_retention_days: int = Field(default=30, ge=1)
    cropped_plate: bool = False  # true → save every detected plate crop to snapshots/plate_crops/

    # ── API ────────────────────────────────────────────────────
    api_host: str = "0.0.0.0"
    api_port: int = Field(default=8000, ge=1024, le=65535)
    api_workers: int = Field(default=4, ge=1)
    cors_origins: List[str] = ["http://localhost:3000", "http://localhost:80"]

    # ── WebSocket ──────────────────────────────────────────────
    ws_heartbeat_interval: int = Field(default=30, ge=5)

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors(cls, v: str | List[str]) -> List[str]:
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return [origin.strip() for origin in v.split(",")]
        return v

    @field_validator("snapshot_dir", mode="before")
    @classmethod
    def ensure_snapshot_dir(cls, v: str | Path) -> Path:
        path = Path(v)
        path.mkdir(parents=True, exist_ok=True)
        return path


@lru_cache
def get_settings() -> Settings:
    return Settings()
