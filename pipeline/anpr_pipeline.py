from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncGenerator, Callable, Coroutine, List, Optional

import cv2
import numpy as np
from loguru import logger

from camera_service.rtsp_capture import FrameResult, RTSPCapture
from config import get_settings
from database.crud import create_event, get_camera_by_name
from database.session import AsyncSessionLocal
from detection_service.plate_detector import DetectionResult, PlateDetector
from ocr_service.paddle_ocr import OCRResult, PaddleOCRService
from validation_service.plate_validator import PlateValidator, ValidationResult

settings = get_settings()

# Type alias for WebSocket broadcast callbacks
BroadcastCallback = Callable[[dict], Coroutine]


@dataclass
class PipelineEvent:
    """Represents a fully processed and validated ANPR detection."""

    plate_number: str
    timestamp: datetime
    confidence: float
    ocr_confidence: float
    camera_name: str
    image_path: Optional[str]
    bbox: List[int]
    raw_text: str


class ANPRPipeline:
    """
    End-to-end ANPR pipeline orchestrator.

    Wires together:
      RTSPCapture → PlateDetector → PaddleOCRService → PlateValidator → DB + WebSocket
    """

    def __init__(
        self,
        broadcast_callback: Optional[BroadcastCallback] = None,
    ) -> None:
        self.broadcast_callback = broadcast_callback

        self._camera = RTSPCapture(
            rtsp_url=settings.rtsp_url,
            camera_name=settings.camera_name,
            frame_skip=settings.frame_skip,
            reconnect_delay=settings.reconnect_delay,
            max_reconnect_attempts=settings.max_reconnect_attempts,
        )
        self._detector = PlateDetector(
            model_path=settings.yolo_model_path,
            confidence=settings.yolo_confidence,
            iou=settings.yolo_iou,
            device=settings.detection_device,
        )
        self._ocr = PaddleOCRService(
            lang=settings.ocr_lang,
            confidence_threshold=settings.ocr_confidence_threshold,
        )
        self._validator = PlateValidator(
            min_confidence=settings.plate_confidence_min,
            duplicate_window=settings.duplicate_window_seconds,
        )
        self._running = False

    # ── Public API ─────────────────────────────────────────────────────────────

    async def run(self) -> None:
        """Start the pipeline. Runs until stop() is called."""
        self._running = True
        logger.info("ANPR Pipeline starting for camera: {name}", name=settings.camera_name)

        async for event in self._process_stream():
            if not self._running:
                break
            await self._persist_and_broadcast(event)

        logger.info("ANPR Pipeline stopped.")

    def stop(self) -> None:
        self._running = False
        self._camera.stop()

    @property
    def camera_stats(self):
        return self._camera.stats

    # ── Internal pipeline stages ───────────────────────────────────────────────

    async def _process_stream(self) -> AsyncGenerator[PipelineEvent, None]:
        async for frame_result in self._camera.stream_frames():
            if not self._running:
                break

            for event in self._process_frame(frame_result):
                yield event

    def _process_frame(self, frame_result: FrameResult) -> List[PipelineEvent]:
        """Synchronous processing of a single frame. Returns validated events."""
        events: List[PipelineEvent] = []
        detections: List[DetectionResult] = self._detector.detect(frame_result.frame)

        for detection in detections:
            ocr_result: Optional[OCRResult] = self._ocr.extract(detection.plate_crop)
            if ocr_result is None:
                continue

            validation: ValidationResult = self._validator.validate(
                raw_text=ocr_result.text,
                confidence=detection.confidence,
            )
            if not validation.is_valid:
                logger.debug(
                    "Plate rejected: {raw!r} → {plate!r}",
                    raw=ocr_result.text,
                    plate=validation.plate_number,
                )
                continue

            if self._validator.is_duplicate(validation.plate_number):
                continue

            image_path = self._save_snapshot(
                plate_number=validation.plate_number,
                frame=frame_result.frame,
                bbox=detection.bbox,
                timestamp=frame_result.timestamp,
            )

            events.append(
                PipelineEvent(
                    plate_number=validation.plate_number,
                    timestamp=datetime.fromtimestamp(frame_result.timestamp, tz=timezone.utc),
                    confidence=detection.confidence,
                    ocr_confidence=ocr_result.confidence,
                    camera_name=frame_result.camera_name,
                    image_path=image_path,
                    bbox=detection.bbox,
                    raw_text=ocr_result.raw_text,
                )
            )
            logger.info(
                "Plate detected: {plate} | conf={conf:.2f} | ocr={ocr:.2f} | cam={cam}",
                plate=validation.plate_number,
                conf=detection.confidence,
                ocr=ocr_result.confidence,
                cam=frame_result.camera_name,
            )

        return events

    async def _persist_and_broadcast(self, event: PipelineEvent) -> None:
        async with AsyncSessionLocal() as db:
            try:
                camera = await get_camera_by_name(db, event.camera_name)
                db_event = await create_event(
                    db=db,
                    plate_number=event.plate_number,
                    timestamp=event.timestamp,
                    camera_name=event.camera_name,
                    confidence=event.confidence,
                    ocr_confidence=event.ocr_confidence,
                    image_path=event.image_path,
                    raw_plate_text=event.raw_text,
                    camera_id=camera.id if camera else None,
                )
                await db.commit()
                logger.debug("Event saved: id={id}", id=db_event.id)
            except Exception as exc:
                logger.error("Failed to persist event: {err}", err=exc)
                await db.rollback()
                return

        if self.broadcast_callback:
            payload = {
                "plate": event.plate_number,
                "timestamp": event.timestamp.isoformat(),
                "confidence": round(event.confidence * 100, 1),
                "ocr_confidence": round(event.ocr_confidence * 100, 1),
                "camera": event.camera_name,
                "image_path": event.image_path,
                "bbox": event.bbox,
            }
            try:
                await self.broadcast_callback(payload)
            except Exception as exc:
                logger.warning("Broadcast failed: {err}", err=exc)

    # ── Snapshot helper ────────────────────────────────────────────────────────

    @staticmethod
    def _save_snapshot(
        plate_number: str,
        frame: np.ndarray,
        bbox: List[int],
        timestamp: float,
    ) -> Optional[str]:
        try:
            snapshot_dir = settings.snapshot_dir
            ts_str = datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
            filename = f"{plate_number}_{ts_str}.jpg"
            filepath = snapshot_dir / filename

            # Draw bounding box on a copy for the snapshot
            annotated = frame.copy()
            x1, y1, x2, y2 = bbox
            cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(
                annotated, plate_number, (x1, y1 - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2,
            )
            cv2.imwrite(str(filepath), annotated)
            return str(filepath)
        except Exception as exc:
            logger.warning("Snapshot save failed: {err}", err=exc)
            return None
