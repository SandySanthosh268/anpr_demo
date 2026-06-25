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

from api_service.frame_buffer import frame_buffer
from api_service.source_manager import source_manager
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
            rtsp_url=source_manager.url,
            camera_name=source_manager.name,
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
        """Start the pipeline. Runs until stop() is called, hot-swaps source on change."""
        self._running = True
        logger.info("ANPR Pipeline starting: {url}", url=source_manager.url)

        while self._running:
            # File source: idle (no capture) until user presses Play
            if source_manager.is_file_source and not source_manager.pipeline_active:
                await asyncio.sleep(0.2)
                if source_manager.take_restart():
                    # Source was changed while paused — reinit camera for new source
                    self._camera.stop()
                    self._camera = self._make_camera()
                continue

            # Play pressed (or RTSP auto-start): recreate camera so file starts from frame 0
            if source_manager.take_restart():
                self._camera.stop()
                self._camera = self._make_camera()
                logger.info("Source active: {url}", url=source_manager.url)

            async for event in self._process_stream():
                if not self._running:
                    break
                if source_manager.take_restart():
                    self._camera.stop()
                    self._camera = self._make_camera()
                    logger.info("Source switched to: {url}", url=source_manager.url)
                    break
                # File source stopped mid-stream by user — break out to idle loop
                if source_manager.is_file_source and not source_manager.pipeline_active:
                    self._camera.stop()
                    self._camera = self._make_camera()
                    logger.info("File source stopped by user.")
                    break
                await self._persist_and_broadcast(event)
            else:
                # Loop completed without a break → file reached end naturally
                if self._running and source_manager.is_file_source and source_manager.pipeline_active:
                    source_manager.stop()
                    logger.info("File '{name}' playback finished.", name=source_manager.name)

        logger.info("ANPR Pipeline stopped.")

    def _make_camera(self) -> RTSPCapture:
        return RTSPCapture(
            rtsp_url=source_manager.url,
            camera_name=source_manager.name,
            frame_skip=settings.frame_skip,
            reconnect_delay=settings.reconnect_delay,
            max_reconnect_attempts=settings.max_reconnect_attempts,
        )

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

        # Run OCR on every detection first so we can overlay text on the stream
        ocr_map: dict[int, Optional[OCRResult]] = {}
        for i, detection in enumerate(detections):
            ocr_result: Optional[OCRResult] = self._ocr.extract(detection.plate_crop)
            ocr_map[i] = ocr_result
            if ocr_result:
                logger.debug(
                    "OCR raw={raw!r} conf={conf:.2f} yolo={yconf:.2f}",
                    raw=ocr_result.text, conf=ocr_result.confidence,
                    yconf=detection.confidence,
                )
            else:
                logger.debug("OCR returned None for detection conf={c:.2f}", c=detection.confidence)

        # Push annotated frame (bounding boxes + OCR text) to live stream
        self._push_to_stream(frame_result.frame, detections, ocr_map)

        for i, detection in enumerate(detections):
            ocr_result = ocr_map[i]
            if ocr_result is None:
                continue

            validation: ValidationResult = self._validator.validate(
                raw_text=ocr_result.text,
                confidence=detection.confidence,
            )
            if not validation.is_valid:
                logger.info(
                    "Plate rejected: raw={raw!r} → {plate!r} | yolo={yc:.2f} | ocr={oc:.2f} | pattern={p}",
                    raw=ocr_result.text,
                    plate=validation.plate_number,
                    yc=detection.confidence,
                    oc=ocr_result.confidence,
                    p=validation.pattern_type,
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

    # ── Live stream helper ─────────────────────────────────────────────────────

    @staticmethod
    def _push_to_stream(
        frame: np.ndarray,
        detections: List[DetectionResult],
        ocr_map: dict | None = None,
    ) -> None:
        """Annotate frame with detection boxes + OCR text and push to the buffer."""
        try:
            annotated = frame.copy()
            for i, det in enumerate(detections):
                x1, y1, x2, y2 = det.bbox
                ocr = (ocr_map or {}).get(i)

                # Box colour: green if OCR found text, yellow if not
                color = (0, 230, 118) if ocr else (0, 200, 255)
                cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)

                # Top label: OCR text + YOLO conf
                ocr_text = ocr.text if ocr else "?"
                label = f"{ocr_text}  {det.confidence:.0%}"

                # Dark background behind text for readability
                (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.65, 2)
                ty = max(y1 - 10, th + 4)
                cv2.rectangle(annotated, (x1, ty - th - 4), (x1 + tw + 4, ty + 2), (0, 0, 0), -1)
                cv2.putText(
                    annotated, label, (x1 + 2, ty),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.65, color, 2,
                )

            ok, buf = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 80])
            if ok:
                frame_buffer.update(buf.tobytes())
        except Exception:
            pass  # never crash the pipeline over a stream update

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
