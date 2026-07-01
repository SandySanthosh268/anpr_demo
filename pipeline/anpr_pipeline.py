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
from detection_service.best_plate_store import BestPlateStore
from detection_service.plate_detector import DetectionResult, PlateDetector
from detection_service.plate_quality import score_crop
from detection_service.vehicle_detector import VehicleDetector
from detection_service.vehicle_tracker import VehicleTracker
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
    track_id: int = 0
    vehicle_type: str = "unknown"
    best_plate_path: Optional[str] = None


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
        self._tracker = VehicleTracker(
            iou_threshold=0.35,
            max_miss_frames=30,
        )
        self._vehicle_detector = VehicleDetector(
            confidence=0.30,
            device=settings.detection_device,
        )
        self._best_store = BestPlateStore(
            save_dir=settings.snapshot_dir / "best_plates",
        )
        # Stable label per track: once a track gets a valid read, this text
        # is shown for every subsequent frame even if OCR gives a noisy result.
        self._track_labels: dict[int, str] = {}
        self._running = False

        # Per-session crop folder: snapshots/plate_crops/session_YYYYMMDD_HHMMSS/
        if settings.cropped_plate:
            session_ts = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
            self._crop_dir: Optional[Path] = (
                settings.snapshot_dir / "plate_crops" / f"session_{session_ts}"
            )
            self._crop_dir.mkdir(parents=True, exist_ok=True)
            logger.info("Plate crops will be saved to: {d}", d=self._crop_dir)
        else:
            self._crop_dir = None

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

        # ── Save raw plate crops for testing / debugging ───────────────────────
        if self._crop_dir is not None and detections:
            self._save_plate_crops(detections, frame_result.timestamp, self._crop_dir)

        # ── Tracking: assign persistent track_id per plate bbox ────────────────
        track_ids, finalized_ids = self._tracker.update(
            [d.bbox for d in detections]
        )
        for i, det in enumerate(detections):
            det.track_id = track_ids[i]

        if finalized_ids:
            logger.debug("Tracks finalized this frame: {ids}", ids=finalized_ids)

        # ── Vehicle type: associate each plate with car/truck/bus/motorcycle ───
        vtype_map = self._vehicle_detector.get_vehicle_type(
            frame_result.frame,
            [d.bbox for d in detections],
        )
        for i, det in enumerate(detections):
            det.vehicle_type = vtype_map.get(i, "unknown")

        # ── Score crops + update best-plate store ─────────────────────────────
        for i, detection in enumerate(detections):
            q = score_crop(detection.plate_crop, detection.confidence, detection.bbox)
            self._best_store.update(
                track_id=detection.track_id,
                crop=detection.plate_crop,
                score=q,
                conf=detection.confidence,
                vehicle_type=detection.vehicle_type,
                bbox=detection.bbox,
                timestamp=frame_result.timestamp,
            )
            logger.debug(
                "Quality score={q:.3f} track={tid} type={vtype}",
                q=q,
                tid=detection.track_id,
                vtype=detection.vehicle_type,
            )

        # ── Release memory for tracks that left the frame ──────────────────────
        for tid in finalized_ids:
            entry = self._best_store.pop(tid)
            if entry:
                logger.debug(
                    "Track {tid} finalized — best score was {s:.3f} ({vtype})",
                    tid=tid,
                    s=entry.best_score,
                    vtype=entry.vehicle_type,
                )
            self._track_labels.pop(tid, None)

        # ── OCR + Validate: run both before drawing on stream ─────────────────
        ocr_map: dict[int, Optional[OCRResult]] = {}
        validation_map: dict[int, Optional[ValidationResult]] = {}

        for i, detection in enumerate(detections):
            ocr_result: Optional[OCRResult] = self._ocr.extract(detection.plate_crop)
            ocr_map[i] = ocr_result

            if ocr_result:
                validation = self._validator.validate(
                    raw_text=ocr_result.text,
                    confidence=detection.confidence,
                )
                validation_map[i] = validation
                logger.debug(
                    "OCR raw={raw!r} → {plate!r} valid={v} | "
                    "ocr={oc:.2f} yolo={yc:.2f} track={tid}",
                    raw=ocr_result.text,
                    plate=validation.plate_number,
                    v=validation.is_valid,
                    oc=ocr_result.confidence,
                    yc=detection.confidence,
                    tid=detection.track_id,
                )
            else:
                validation_map[i] = None
                logger.debug(
                    "OCR returned None | conf={c:.2f} track={tid}",
                    c=detection.confidence,
                    tid=detection.track_id,
                )

        # ── Lock in any newly validated plate text per track ──────────────────
        for i, det in enumerate(detections):
            val = validation_map.get(i)
            if val is not None and val.is_valid:
                self._track_labels[det.track_id] = val.plate_number

        # ── Push annotated frame — stable label wins over per-frame OCR ───────
        self._push_to_stream(
            frame_result.frame,
            detections,
            ocr_map,
            validation_map=validation_map,
            track_labels=self._track_labels,
            active_tracks=self._tracker.active_count,
        )

        # ── Broadcast currently active confirmed plates to frontend ────────────
        # This fires on every frame so the right panel always reflects what is
        # currently on screen, regardless of the duplicate-suppression window.
        if self._track_labels:
            active_payload = {
                "type": "tracks_update",
                "tracks": [
                    {
                        "track_id": tid,
                        "plate":    plate,
                        "camera":   frame_result.camera_name,
                        "timestamp": frame_result.timestamp,
                    }
                    for tid, plate in self._track_labels.items()
                ],
            }
            asyncio.ensure_future(self._safe_broadcast(active_payload))

        # ── Emit events for valid, non-duplicate detections ───────────────────
        for i, detection in enumerate(detections):
            ocr_result = ocr_map[i]
            if ocr_result is None:
                continue

            validation = validation_map[i]
            if validation is None or not validation.is_valid:
                if validation is not None:
                    logger.info(
                        "Plate rejected: raw={raw!r} → {plate!r} | yolo={yc:.2f} | "
                        "ocr={oc:.2f} | pattern={p} | track={tid}",
                        raw=ocr_result.text,
                        plate=validation.plate_number,
                        yc=detection.confidence,
                        oc=ocr_result.confidence,
                        p=validation.pattern_type,
                        tid=detection.track_id,
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

            # Save the best-quality crop seen for this track so far
            best_plate_path = self._best_store.save_best_crop(
                track_id=detection.track_id,
                plate_number=validation.plate_number,
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
                    track_id=detection.track_id,
                    vehicle_type=detection.vehicle_type,
                    best_plate_path=best_plate_path,
                )
            )
            logger.info(
                "Plate detected: {plate} | track={tid} | type={vtype} | "
                "conf={conf:.2f} | ocr={ocr:.2f} | cam={cam}",
                plate=validation.plate_number,
                tid=detection.track_id,
                vtype=detection.vehicle_type,
                conf=detection.confidence,
                ocr=ocr_result.confidence,
                cam=frame_result.camera_name,
            )

        return events

    async def _safe_broadcast(self, payload: dict) -> None:
        """Fire-and-forget broadcast — never raises."""
        if self.broadcast_callback:
            try:
                await self.broadcast_callback(payload)
            except Exception:
                pass

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
                    track_id=event.track_id or None,
                    vehicle_type=event.vehicle_type if event.vehicle_type != "unknown" else None,
                    best_plate_path=event.best_plate_path,
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
                "track_id": event.track_id,
                "vehicle_type": event.vehicle_type,
                "best_plate_path": event.best_plate_path,
            }
            try:
                await self.broadcast_callback(payload)
            except Exception as exc:
                logger.warning("Broadcast failed: {err}", err=exc)

    # ── Live stream helper ─────────────────────────────────────────────────────

    # BGR colours keyed by vehicle type
    _VEHICLE_COLORS = {
        "car":        (0, 230, 118),   # green
        "truck":      (0, 120, 255),   # blue
        "bus":        (0, 165, 255),   # orange
        "motorcycle": (255, 0, 200),   # magenta
        "unknown":    (0, 200, 255),   # yellow
    }

    @staticmethod
    def _push_to_stream(
        frame: np.ndarray,
        detections: List[DetectionResult],
        ocr_map: dict | None = None,
        validation_map: dict | None = None,
        track_labels: dict | None = None,
        active_tracks: int = 0,
    ) -> None:
        """Annotate frame with stable plate text, track ID, vehicle type."""
        try:
            annotated = frame.copy()

            for i, det in enumerate(detections):
                x1, y1, x2, y2 = det.bbox
                ocr = (ocr_map or {}).get(i)
                val = (validation_map or {}).get(i)
                cached = (track_labels or {}).get(det.track_id)

                if cached:
                    # Locked-in text from a previous good read — never flickers
                    display_text = cached
                    color = (0, 230, 118)   # green: confirmed
                elif val is not None and val.is_valid:
                    # First valid read this frame
                    display_text = val.plate_number
                    color = (0, 230, 118)   # green: confirmed
                elif ocr is not None:
                    # OCR read something but validation rejected it
                    display_text = ocr.text
                    color = (0, 200, 255)   # yellow: unconfirmed
                else:
                    # No OCR result at all
                    display_text = "?"
                    color = (160, 160, 160) # grey: no read

                cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)

                vtype = det.vehicle_type if det.vehicle_type != "unknown" else ""
                label = f"[{det.track_id}]{(' ' + vtype) if vtype else ''}  {display_text}  {det.confidence:.0%}"

                (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.60, 2)
                ty = max(y1 - 10, th + 4)
                cv2.rectangle(
                    annotated, (x1, ty - th - 4), (x1 + tw + 4, ty + 2), (0, 0, 0), -1
                )
                cv2.putText(
                    annotated, label, (x1 + 2, ty),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.60, color, 2,
                )

            overlay = f"Active Tracks: {active_tracks}"
            cv2.putText(
                annotated, overlay, (10, annotated.shape[0] - 12),
                cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 0), 2,
            )

            ok, buf = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 80])
            if ok:
                frame_buffer.update(buf.tobytes())
        except Exception:
            pass  # never crash the pipeline over a stream update

    # ── Plate crop saver (testing / debugging) ────────────────────────────────

    @staticmethod
    def _save_plate_crops(detections: List[DetectionResult], timestamp: float, crop_dir: Path) -> None:
        ts = datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime("%Y%m%d_%H%M%S_%f")[:-3]
        for det in detections:
            try:
                fname = f"{ts}_t{det.track_id}_c{det.confidence:.2f}.jpg"
                cv2.imwrite(str(crop_dir / fname), det.plate_crop)
            except Exception:
                pass

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
