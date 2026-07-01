from __future__ import annotations

from typing import Dict, List

import numpy as np
from loguru import logger


# COCO class IDs that represent vehicles we care about
_VEHICLE_CLASSES: Dict[int, str] = {
    2: "car",
    3: "motorcycle",
    5: "bus",
    7: "truck",
}


class VehicleDetector:
    """
    Detects vehicle type (car / truck / bus / motorcycle) using YOLOv8n
    pretrained on COCO (~6 MB, auto-downloaded by ultralytics on first use).

    For each plate bounding box, finds the vehicle box whose area contains
    the plate centroid and returns that vehicle's class label.
    """

    _COCO_MODEL = "yolov8n.pt"

    def __init__(self, confidence: float = 0.30, device: str = "cpu") -> None:
        self.confidence = confidence
        self.device = device
        self._model = None
        self._load_model()

    # ── Public API ─────────────────────────────────────────────────────────────

    def get_vehicle_type(
        self,
        frame: np.ndarray,
        plate_bboxes: List[List[int]],
    ) -> Dict[int, str]:
        """
        Run vehicle detection and associate each plate with a vehicle type.

        Args:
            frame:        BGR frame (same frame used for plate detection).
            plate_bboxes: list of [x1, y1, x2, y2] plate boxes.

        Returns:
            Dict of {plate_index → vehicle_type_string}.
            Plates with no containing vehicle box are absent from the dict.
        """
        if self._model is None or not plate_bboxes:
            return {}

        try:
            results = self._model.predict(
                source=frame,
                conf=self.confidence,
                classes=list(_VEHICLE_CLASSES.keys()),
                device=self.device,
                verbose=False,
            )
        except Exception as exc:
            logger.warning("VehicleDetector inference error: {err}", err=exc)
            return {}

        # Collect (bbox, vehicle_type) for all detected vehicles
        vehicle_boxes: List[tuple[List[int], str]] = []
        for result in results:
            if result.boxes is None:
                continue
            for box in result.boxes:
                cls_id = int(box.cls[0])
                vtype = _VEHICLE_CLASSES.get(cls_id)
                if vtype is None:
                    continue
                x1, y1, x2, y2 = (int(v) for v in box.xyxy[0].tolist())
                vehicle_boxes.append(([x1, y1, x2, y2], vtype))

        # For each plate centroid, find the first vehicle box that contains it
        plate_to_type: Dict[int, str] = {}
        for i, pbbox in enumerate(plate_bboxes):
            cx = (pbbox[0] + pbbox[2]) // 2
            cy = (pbbox[1] + pbbox[3]) // 2
            for vbbox, vtype in vehicle_boxes:
                if vbbox[0] <= cx <= vbbox[2] and vbbox[1] <= cy <= vbbox[3]:
                    plate_to_type[i] = vtype
                    break

        return plate_to_type

    # ── Internal ───────────────────────────────────────────────────────────────

    def _load_model(self) -> None:
        try:
            from ultralytics import YOLO

            self._model = YOLO(self._COCO_MODEL)
            logger.info("VehicleDetector loaded COCO model: {m}", m=self._COCO_MODEL)
        except ImportError:
            logger.error("ultralytics not installed — VehicleDetector disabled.")
        except Exception as exc:
            logger.error("VehicleDetector model load failed: {err}", err=exc)
