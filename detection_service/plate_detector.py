from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import cv2
import numpy as np
from loguru import logger

from config import get_settings

settings = get_settings()

# Absolute path so it resolves regardless of working directory
_BYTETRACK_CFG = str(Path(__file__).parent.parent / "bytetrack_plate.yaml")


@dataclass
class DetectionResult:
    bbox: List[int]               # [x1, y1, x2, y2] in pixels
    confidence: float             # 0–1 YOLO detection score
    plate_crop: np.ndarray        # enhanced plate crop (BGR)
    track_id: int = 0             # assigned by ByteTrack inside detect()
    vehicle_type: str = "unknown" # filled by pipeline after vehicle detection


class PlateDetector:
    """
    YOLOv8 plate detector with integrated ByteTrack tracking.

    Calls model.track(persist=True) so track_id is stable across frames —
    the same physical plate keeps the same ID even if confidence fluctuates.
    ByteTrack handles occlusion and brief disappearances internally.
    """

    MODEL_FALLBACK_URL = "yolov8n.pt"

    def __init__(
        self,
        model_path: Optional[str] = None,
        confidence: float = 0.5,
        iou: float = 0.45,
        device: str = "cpu",
    ) -> None:
        self.confidence = confidence
        self.iou = iou
        self.device = device
        self._model = None
        self._model_path = model_path or settings.yolo_model_path
        self._load_model()

    # ── Public API ─────────────────────────────────────────────────────────────

    def detect(self, frame: np.ndarray) -> List[DetectionResult]:
        """Detect plates and return stable ByteTrack IDs in one call."""
        if self._model is None:
            return []

        try:
            results = self._model.track(
                source=frame,
                conf=self.confidence,
                iou=self.iou,
                device=self.device,
                tracker=_BYTETRACK_CFG,
                persist=True,   # keep Kalman state between frames
                verbose=False,
            )
        except Exception as exc:
            logger.error("YOLO track error: {err}", err=exc)
            return []

        if not results or results[0].boxes is None:
            return []

        boxes = results[0].boxes
        ids = boxes.id          # Tensor[N] or None on first frame / no confirmed tracks
        h, w = frame.shape[:2]
        detections: List[DetectionResult] = []

        for i in range(len(boxes)):
            conf = float(boxes.conf[i])
            x1, y1, x2, y2 = map(int, boxes.xyxy[i].tolist())
            track_id = int(ids[i].item()) if ids is not None else 0

            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(w, x2), min(h, y2)
            if x2 <= x1 or y2 <= y1:
                continue

            crop = frame[y1:y2, x1:x2]
            if crop.size == 0:
                continue

            detections.append(DetectionResult(
                bbox=[x1, y1, x2, y2],
                confidence=conf,
                plate_crop=self._enhance_crop(crop),
                track_id=track_id,
            ))

        logger.debug("PlateDetector: {n} plate(s) | IDs: {ids}",
                     n=len(detections), ids=[d.track_id for d in detections])
        return detections

    def reset_tracker(self) -> None:
        """Reset ByteTrack state — call when video source changes."""
        try:
            if (self._model is not None
                    and hasattr(self._model, "predictor")
                    and self._model.predictor is not None
                    and hasattr(self._model.predictor, "trackers")
                    and self._model.predictor.trackers):
                self._model.predictor.trackers[0].reset()
                logger.info("ByteTrack state reset.")
        except Exception as exc:
            logger.warning("ByteTrack reset failed: {err}", err=exc)

    # ── Internal ───────────────────────────────────────────────────────────────

    def _load_model(self) -> None:
        try:
            from ultralytics import YOLO

            model_path = Path(self._model_path)
            if not model_path.exists():
                logger.warning(
                    "Custom model not found at {path}, falling back to {fb}",
                    path=model_path,
                    fb=self.MODEL_FALLBACK_URL,
                )
                model_path = Path(self.MODEL_FALLBACK_URL)

            self._model = YOLO(str(model_path))
            logger.info("PlateDetector loaded: {path}", path=model_path)
        except ImportError:
            logger.error("ultralytics not installed. PlateDetector disabled.")
        except Exception as exc:
            logger.error("Failed to load YOLO model: {err}", err=exc)

    @staticmethod
    def _enhance_crop(crop: np.ndarray) -> np.ndarray:
        h, w = crop.shape[:2]
        if w < 200:
            scale = 200 / w
            crop = cv2.resize(crop, (int(w * scale), int(h * scale)),
                              interpolation=cv2.INTER_CUBIC)
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        gray = clahe.apply(gray)
        denoised = cv2.fastNlMeansDenoising(gray, h=10)
        return cv2.cvtColor(denoised, cv2.COLOR_GRAY2BGR)
