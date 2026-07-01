from __future__ import annotations

import asyncio
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
from detection_service.plate_voter import PlateVoter
from detection_service.vehicle_detector import VehicleDetector
from ocr_service.paddle_ocr import OCRResult, PaddleOCRService
from validation_service.plate_validator import PlateValidator, ValidationResult

settings = get_settings()

BroadcastCallback = Callable[[dict], Coroutine]


@dataclass
class PipelineEvent:
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
    ByteTrack + voting + finalization ANPR pipeline.

    Flow per vehicle:
      1. Vehicle enters frame → ByteTrack assigns a stable track_id.
      2. Each frame: quality-gated OCR runs on the plate crop. Valid reads
         are accumulated by PlateVoter. Stream shows best candidate.
      3. Vehicle leaves frame → track_id disappears → FINALIZATION:
         - Definitive OCR runs on the sharpest crop ever seen (BestPlateStore).
         - One event fires to DB + WebSocket. Never fires twice for same track.
         - Fallback: voted top candidate if best-crop OCR fails.

    Colors on stream:
      Grey  = no OCR yet (plate too small/blurry)
      Amber = candidate found (1+ votes, not yet confirmed)
      Green = confirmed (min_votes reached)
    """

    def __init__(self, broadcast_callback: Optional[BroadcastCallback] = None) -> None:
        self.broadcast_callback = broadcast_callback

        self._camera = self._make_camera()
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
        self._vehicle_detector = VehicleDetector(
            confidence=0.30,
            device=settings.detection_device,
        )
        self._best_store = BestPlateStore(
            save_dir=settings.snapshot_dir / "best_plates",
        )
        self._voter = PlateVoter(
            min_votes=settings.plate_min_votes,
            max_attempts=99,  # no force-lock — definitive answer comes from best-crop OCR
        )

        # Per-track state — all cleared on source change via _reset_tracking_state()
        self._track_labels: dict[int, str] = {}           # best candidate per track (for stream display)
        self._locked_track_ids: set[int] = set()          # tracks that reached min_votes (green)
        self._prev_track_ids: set[int] = set()            # track IDs seen in the previous frame
        self._vehicle_type_cache: dict[int, str] = {}     # vehicle type, detected once per track
        self._event_fired: set[int] = set()               # tracks whose finalization event already fired
        self._track_trails: dict[int, list] = {}          # track_id → list of (cx, cy) centroids

        self._running = False

        # Per-session crop folder
        if settings.cropped_plate:
            session_ts = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
            self._crop_dir: Optional[Path] = (
                settings.snapshot_dir / "plate_crops" / f"session_{session_ts}"
            )
            self._crop_dir.mkdir(parents=True, exist_ok=True)
            logger.info("Plate crops → {d}", d=self._crop_dir)
        else:
            self._crop_dir = None

    # ── Public API ─────────────────────────────────────────────────────────────

    async def run(self) -> None:
        self._running = True
        logger.info("ANPR Pipeline starting: {url}", url=source_manager.url)

        while self._running:
            # File source: idle until user presses Play in the dashboard
            if source_manager.is_file_source and not source_manager.pipeline_active:
                await asyncio.sleep(0.2)
                if source_manager.take_restart():
                    self._camera.stop()
                    self._camera = self._make_camera()
                continue

            if source_manager.take_restart():
                self._camera.stop()
                self._camera = self._make_camera()
                self._reset_tracking_state()
                logger.info("Source active: {url}", url=source_manager.url)

            async for event in self._process_stream():
                if not self._running:
                    break
                if source_manager.take_restart():
                    self._camera.stop()
                    self._camera = self._make_camera()
                    self._reset_tracking_state()
                    logger.info("Source switched to: {url}", url=source_manager.url)
                    break
                if source_manager.is_file_source and not source_manager.pipeline_active:
                    self._camera.stop()
                    self._camera = self._make_camera()
                    logger.info("File source stopped.")
                    break
                await self._persist_and_broadcast(event)
            else:
                if self._running and source_manager.is_file_source and source_manager.pipeline_active:
                    source_manager.stop()
                    logger.info("File '{name}' playback finished.", name=source_manager.name)

        logger.info("ANPR Pipeline stopped.")

    def stop(self) -> None:
        self._running = False
        self._camera.stop()

    @property
    def camera_stats(self):
        return self._camera.stats

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _make_camera(self) -> RTSPCapture:
        return RTSPCapture(
            rtsp_url=source_manager.url,
            camera_name=source_manager.name,
            reconnect_delay=settings.reconnect_delay,
            max_reconnect_attempts=settings.max_reconnect_attempts,
        )

    def _reset_tracking_state(self) -> None:
        """Clear all per-track state on source change or restart."""
        self._detector.reset_tracker()
        self._track_labels.clear()
        self._locked_track_ids.clear()
        self._prev_track_ids.clear()
        self._vehicle_type_cache.clear()
        self._event_fired.clear()
        self._voter.reset()
        self._track_trails.clear()

    def _cleanup_track(self, tid: int) -> None:
        """Remove all state for a track that has been finalized."""
        self._voter.finalize(tid)
        self._track_labels.pop(tid, None)
        self._locked_track_ids.discard(tid)
        self._vehicle_type_cache.pop(tid, None)
        self._track_trails.pop(tid, None)

    # ── Stream processing ──────────────────────────────────────────────────────

    async def _process_stream(self) -> AsyncGenerator[PipelineEvent, None]:
        async for frame_result in self._camera.stream_frames():
            if not self._running:
                break
            for event in self._process_frame(frame_result):
                yield event

    def _process_frame(self, frame_result: FrameResult) -> List[PipelineEvent]:
        events: List[PipelineEvent] = []

        # ── 1. Detect + ByteTrack ─────────────────────────────────────────────
        # model.track(persist=True) keeps the tracker state between calls.
        # track_id is stable across frames for the same physical plate.
        detections: List[DetectionResult] = self._detector.detect(frame_result.frame)

        # ── 2. Save raw crops (debug / training data) ─────────────────────────
        if self._crop_dir is not None and detections:
            self._save_plate_crops(detections, frame_result.timestamp, self._crop_dir)

        # ── 3. Vehicle type — detected once per track_id, result cached ────────
        new_idxs = [i for i, d in enumerate(detections)
                    if d.track_id not in self._vehicle_type_cache]
        if new_idxs:
            vtype_map = self._vehicle_detector.get_vehicle_type(
                frame_result.frame, [detections[i].bbox for i in new_idxs]
            )
            for j, i in enumerate(new_idxs):
                tid = detections[i].track_id
                self._vehicle_type_cache[tid] = vtype_map.get(j, "unknown")
        for det in detections:
            det.vehicle_type = self._vehicle_type_cache.get(det.track_id, "unknown")

        # ── 4. Quality score + best-plate store ───────────────────────────────
        # Compute quality once per detection; reuse in step 6 (OCR gating).
        quality: dict[int, float] = {}
        for i, det in enumerate(detections):
            q = score_crop(det.plate_crop, det.confidence, det.bbox)
            quality[i] = q
            self._best_store.update(
                track_id=det.track_id,
                crop=det.plate_crop,
                score=q,
                conf=det.confidence,
                vehicle_type=det.vehicle_type,
                bbox=det.bbox,
                timestamp=frame_result.timestamp,
            )

        # ── 4b. Update movement trails (centroid history per track) ──────────────
        _TRAIL_MAX = 60   # keep last N positions (~2s at 30 FPS)
        for det in detections:
            if det.track_id <= 0:
                continue
            x1, y1, x2, y2 = det.bbox
            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
            trail = self._track_trails.setdefault(det.track_id, [])
            trail.append((cx, cy))
            if len(trail) > _TRAIL_MAX:
                del trail[0]

        # ── 5. FINALIZATION — vehicle completely crossed the frame ─────────────
        #
        # A track_id disappears when ByteTrack drops it (vehicle left frame,
        # or exceeded track_buffer frames without a match after leaving).
        # This is the ONE point where we commit a plate to the database.
        #
        # Strategy:
        #   a) Run definitive OCR on the sharpest crop the vehicle ever showed.
        #   b) Validate. If valid → fire event.
        #   c) Fallback: use voter's top candidate if OCR fails.
        current_ids = {d.track_id for d in detections if d.track_id > 0}
        finalized_ids = self._prev_track_ids - current_ids

        # New track IDs that weren't present last frame — ByteTrack may reuse old IDs,
        # so wipe any stale label/vote state before accumulating fresh data.
        new_track_ids = current_ids - self._prev_track_ids
        for tid in new_track_ids:
            self._track_labels.pop(tid, None)
            self._locked_track_ids.discard(tid)
            self._voter.finalize(tid)
            self._vehicle_type_cache.pop(tid, None)
            self._track_trails.pop(tid, None)

        self._prev_track_ids = current_ids

        for tid in finalized_ids:
            if tid in self._event_fired:
                self._cleanup_track(tid)
                continue

            entry = self._best_store.pop(tid)   # releases memory

            plate_final: Optional[str] = None
            ocr_conf_final = 0.0

            if entry is not None:
                ocr_final = self._ocr.extract(entry.best_crop)
                if ocr_final:
                    val_final = self._validator.validate(ocr_final.text, entry.best_conf)
                    if val_final.is_valid:
                        plate_final = val_final.plate_number
                        ocr_conf_final = ocr_final.confidence

            # Fallback to voted candidate when best-crop OCR can't confirm
            if not plate_final:
                plate_final = (
                    self._voter.top_candidate(tid)
                    or self._track_labels.get(tid)
                )

            if plate_final and not self._validator.is_duplicate(plate_final):
                self._event_fired.add(tid)

                # Save the best-quality crop image to disk
                best_plate_path: Optional[str] = None
                if entry is not None:
                    try:
                        fdir = settings.snapshot_dir / "best_plates"
                        fdir.mkdir(parents=True, exist_ok=True)
                        fpath = fdir / f"TRK{tid:04d}_{plate_final}.jpg"
                        cv2.imwrite(str(fpath), entry.best_crop)
                        best_plate_path = str(fpath)
                    except Exception as exc:
                        logger.warning("Best crop save failed: {err}", err=exc)

                ts = entry.first_seen if entry else frame_result.timestamp
                bbox = entry.best_bbox if entry else [0, 0, 0, 0]
                vtype = entry.vehicle_type if entry else "unknown"
                image_path = self._save_snapshot(plate_final, frame_result.frame, bbox, ts)

                events.append(PipelineEvent(
                    plate_number=plate_final,
                    timestamp=datetime.fromtimestamp(ts, tz=timezone.utc),
                    confidence=entry.best_conf if entry else 0.0,
                    ocr_confidence=ocr_conf_final,
                    camera_name=frame_result.camera_name,
                    image_path=image_path,
                    bbox=bbox,
                    raw_text=plate_final,
                    track_id=tid,
                    vehicle_type=vtype,
                    best_plate_path=best_plate_path,
                ))
                logger.info(
                    "FINALIZED track={tid} plate={plate!r} type={vtype}",
                    tid=tid, plate=plate_final, vtype=vtype,
                )
            else:
                reason = "duplicate" if plate_final else "no plate identified"
                logger.debug("Finalized track={tid} — {reason}", tid=tid, reason=reason)

            self._cleanup_track(tid)

        # ── 6. Quality-gated OCR + voting — for stream display only ──────────
        # OCR is skipped when the crop is too blurry or small (quality threshold).
        # Valid reads vote per track. Voter locks when min_votes agree.
        # Stream display: amber = candidate, green = confirmed (locked).
        ocr_map: dict[int, Optional[OCRResult]] = {}
        validation_map: dict[int, Optional[ValidationResult]] = {}

        for i, det in enumerate(detections):
            tid = det.track_id

            if quality[i] < settings.plate_min_ocr_quality:
                ocr_map[i] = None
                validation_map[i] = None
                continue

            ocr_result = self._ocr.extract(det.plate_crop)
            ocr_map[i] = ocr_result

            if ocr_result is None:
                validation_map[i] = None
                self._voter.count_attempt(tid)
                continue

            val = self._validator.validate(raw_text=ocr_result.text, confidence=det.confidence)
            validation_map[i] = val

            if val.is_valid:
                locked = self._voter.vote(tid, val.plate_number)
                if locked:
                    self._locked_track_ids.add(tid)
                logger.debug("Vote: {plate!r} q={q:.3f} track={tid}",
                             plate=val.plate_number, q=quality[i], tid=tid)
            else:
                self._voter.count_attempt(tid)
                logger.debug("Invalid: {raw!r} track={tid}", raw=ocr_result.text, tid=tid)

        # ── 7. Update display labels ──────────────────────────────────────────
        for det in detections:
            candidate = self._voter.top_candidate(det.track_id)
            if candidate:
                self._track_labels[det.track_id] = candidate

        # ── 8. Push annotated frame to MJPEG stream ───────────────────────────
        self._push_to_stream(
            frame_result.frame,
            detections,
            ocr_map,
            validation_map=validation_map,
            track_labels=self._track_labels,
            locked_track_ids=self._locked_track_ids,
            track_trails=self._track_trails,
            active_tracks=len(current_ids),
        )

        # ── 9. Broadcast active tracks to frontend ────────────────────────────
        if self._track_labels:
            asyncio.ensure_future(self._safe_broadcast({
                "type": "tracks_update",
                "tracks": [
                    {"track_id": tid, "plate": plate,
                     "camera": frame_result.camera_name,
                     "timestamp": frame_result.timestamp}
                    for tid, plate in self._track_labels.items()
                ],
            }))

        return events

    # ── Async helpers ──────────────────────────────────────────────────────────

    async def _safe_broadcast(self, payload: dict) -> None:
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
            try:
                await self.broadcast_callback({
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
                })
            except Exception as exc:
                logger.warning("Broadcast failed: {err}", err=exc)

    # ── Stream annotation ──────────────────────────────────────────────────────

    _VEHICLE_COLORS = {
        "car":        (0, 230, 118),
        "truck":      (0, 120, 255),
        "bus":        (0, 165, 255),
        "motorcycle": (255, 0, 200),
        "unknown":    (0, 200, 255),
    }

    @staticmethod
    def _push_to_stream(
        frame: np.ndarray,
        detections: List[DetectionResult],
        ocr_map: dict,
        validation_map: dict | None = None,
        track_labels: dict | None = None,
        locked_track_ids: set | None = None,
        track_trails: dict | None = None,
        active_tracks: int = 0,
    ) -> None:
        try:
            annotated = frame.copy()

            # ── Draw movement trails ──────────────────────────────────────────
            for tid, trail in (track_trails or {}).items():
                if len(trail) < 2:
                    continue
                for j in range(1, len(trail)):
                    alpha = j / len(trail)
                    thickness = max(1, int(alpha * 3))
                    brightness = int(80 + alpha * 175)
                    cv2.line(annotated, trail[j - 1], trail[j],
                             (brightness, brightness, 0), thickness)
                if trail:
                    # Filled dot at trail head
                    cv2.circle(annotated, trail[-1], 5, (0, 255, 255), -1)
                    # Track ID printed next to the trail head dot
                    tid_label = f"#{tid}"
                    (tw, th), _ = cv2.getTextSize(
                        tid_label, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 2)
                    tx, ty = trail[-1][0] + 8, trail[-1][1] + th // 2
                    cv2.rectangle(annotated,
                                  (tx - 2, ty - th - 2), (tx + tw + 2, ty + 2),
                                  (0, 0, 0), -1)
                    cv2.putText(annotated, tid_label, (tx, ty),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 255), 2)

            # ── Draw detection boxes + labels ─────────────────────────────────
            for i, det in enumerate(detections):
                x1, y1, x2, y2 = det.bbox
                ocr = (ocr_map or {}).get(i)
                cached = (track_labels or {}).get(det.track_id)
                is_locked = det.track_id in (locked_track_ids or set())

                if cached:
                    display_text = cached
                    color = (0, 230, 118) if is_locked else (0, 165, 255)
                elif ocr is not None:
                    display_text = ocr.text
                    color = (0, 200, 255)
                else:
                    display_text = "?"
                    color = (160, 160, 160)

                cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)

                # Large track ID drawn inside the bbox (top-left corner)
                tid_str = str(det.track_id)
                cv2.putText(annotated, tid_str, (x1 + 4, y1 + 22),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 0, 0), 4)
                cv2.putText(annotated, tid_str, (x1 + 4, y1 + 22),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.75, color, 2)

                # Info label above the bbox: vehicle type  plate  confidence
                vtype = det.vehicle_type if det.vehicle_type != "unknown" else ""
                label = (f"{(' ' + vtype) if vtype else ''}  "
                         f"{display_text}  {det.confidence:.0%}").strip()

                (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 2)
                ty = max(y1 - 8, th + 4)
                cv2.rectangle(annotated, (x1, ty - th - 4), (x1 + tw + 4, ty + 2),
                              (0, 0, 0), -1)
                cv2.putText(annotated, label, (x1 + 2, ty),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)

            cv2.putText(annotated, f"Active Tracks: {active_tracks}",
                        (10, annotated.shape[0] - 12),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 0), 2)

            ok, buf = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 80])
            if ok:
                frame_buffer.update(buf.tobytes())
        except Exception:
            pass

    # ── Snapshot helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _save_plate_crops(
        detections: List[DetectionResult], timestamp: float, crop_dir: Path
    ) -> None:
        ts = datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime("%Y%m%d_%H%M%S_%f")[:-3]
        for det in detections:
            try:
                fname = f"{ts}_t{det.track_id}_c{det.confidence:.2f}.jpg"
                cv2.imwrite(str(crop_dir / fname), det.plate_crop)
            except Exception:
                pass

    @staticmethod
    def _save_snapshot(
        plate_number: str,
        frame: np.ndarray,
        bbox: List[int],
        timestamp: float,
    ) -> Optional[str]:
        try:
            ts_str = datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
            filename = f"{plate_number}_{ts_str}.jpg"
            filepath = settings.snapshot_dir / filename
            annotated = frame.copy()
            x1, y1, x2, y2 = bbox
            cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(annotated, plate_number, (x1, y1 - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
            cv2.imwrite(str(filepath), annotated)
            return str(filepath)
        except Exception as exc:
            logger.warning("Snapshot save failed: {err}", err=exc)
            return None
