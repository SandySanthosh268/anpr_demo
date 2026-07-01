from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import cv2
import numpy as np
from loguru import logger

from config import get_settings

settings = get_settings()


@dataclass
class DetectionResult:
    bbox: List[int]               # [x1, y1, x2, y2] in pixels
    confidence: float             # 0–1 float
    plate_crop: np.ndarray        # Cropped plate image (BGR)
    track_id: int = 0             # assigned by VehicleTracker in pipeline
    vehicle_type: str = "unknown" # assigned by VehicleDetector in pipeline


class PlateDetector:
    """
    YOLOv8-based license plate detector.

    Falls back to a YOLOv8n general-object model (pretrained on COCO) when the
    custom plate model is not found, using class 0 (person) as a stand-in only
    during development. In production, replace with a model trained on Indian
    license plates (class 0 → license_plate).
    """

    MODEL_FALLBACK_URL = "yolov8n.pt"  # downloaded automatically by ultralytics

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
        """Return a list of detected plate regions from the given BGR frame."""
        if self._model is None:
            return []

        try:
            results = self._model.predict(
                source=frame,
                conf=self.confidence,
                iou=self.iou,
                device=self.device,
                verbose=False,
            )
        except Exception as exc:
            logger.error("YOLO inference error: {err}", err=exc)
            return []

        detections: List[DetectionResult] = []
        for result in results:
            if result.boxes is None:
                continue
            for box in result.boxes:
                x1, y1, x2, y2 = (int(v) for v in box.xyxy[0].tolist())
                conf = float(box.conf[0])

                # Clip to frame bounds
                h, w = frame.shape[:2]
                x1, y1 = max(0, x1), max(0, y1)
                x2, y2 = min(w, x2), min(h, y2)

                if x2 <= x1 or y2 <= y1:
                    continue

                crop = frame[y1:y2, x1:x2]
                if crop.size == 0:
                    continue

                crop = self._enhance_crop(crop)
                detections.append(
                    DetectionResult(bbox=[x1, y1, x2, y2], confidence=conf, plate_crop=crop)
                )

        logger.debug(
            "PlateDetector: {n} plate(s) detected.",
            n=len(detections),
        )
        return detections

    # ── Internal helpers ───────────────────────────────────────────────────────

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
            logger.info("PlateDetector loaded model: {path}", path=model_path)
        except ImportError:
            logger.error("ultralytics package not installed. PlateDetector disabled.")
        except Exception as exc:
            logger.error("Failed to load YOLO model: {err}", err=exc)

    @staticmethod
    def _enhance_crop(crop: np.ndarray) -> np.ndarray:
        """Apply contrast enhancement and denoising to improve OCR accuracy."""
        # Upscale small crops
        h, w = crop.shape[:2]
        if w < 200:
            scale = 200 / w
            crop = cv2.resize(crop, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_CUBIC)

        # Convert to grayscale, apply CLAHE, convert back to BGR for PaddleOCR
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        gray = clahe.apply(gray)
        denoised = cv2.fastNlMeansDenoising(gray, h=10)
        return cv2.cvtColor(denoised, cv2.COLOR_GRAY2BGR)
