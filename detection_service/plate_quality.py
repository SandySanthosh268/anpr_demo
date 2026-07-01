from __future__ import annotations

from typing import List

import cv2
import numpy as np


def score_crop(
    crop: np.ndarray,
    confidence: float,
    bbox: List[int],
) -> float:
    """
    Quality score for a plate crop. Higher = better candidate for OCR/saving.

    Components:
      - confidence:  YOLO detection score (0–1)
      - sharpness:   Laplacian variance of the grayscale crop — blurry crops
                     score low even after CLAHE enhancement
      - area:        raw bounding-box pixel area — larger = more readable

    Formula: conf * sharpness_norm^0.4 * area_norm^0.3

    Normalisation denominators are soft baselines (not hard caps):
      - sharpness baseline 500  ≈ acceptably sharp plate at medium distance
      - area baseline 5 000 px² ≈ ~70×70 px plate crop
    Values above baseline push the score above 1.0, which is fine — we only
    compare scores against each other, not against a fixed threshold.
    """
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if crop.ndim == 3 else crop
    sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())

    x1, y1, x2, y2 = bbox
    area = float(max((x2 - x1) * (y2 - y1), 1))

    sharpness_norm = (max(sharpness, 1.0) / 500.0) ** 0.4
    area_norm = (area / 5_000.0) ** 0.3

    return confidence * sharpness_norm * area_norm
