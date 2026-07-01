from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
from loguru import logger

from config import get_settings

settings = get_settings()


@dataclass
class OCRResult:
    text: str
    confidence: float
    raw_text: str


class PaddleOCRService:
    """
    Wrapper around PaddleOCR for license plate text extraction.

    Lazy-initialised so the heavy PaddlePaddle framework is loaded only when
    first needed, keeping the API startup fast.
    """

    def __init__(
        self,
        lang: str = "en",
        confidence_threshold: float = 0.7,
    ) -> None:
        self.lang = lang
        self.confidence_threshold = confidence_threshold
        self._ocr = None

    # ── Public API ─────────────────────────────────────────────────────────────

    # Minimum crop dimensions PaddleOCR can handle without segfaulting
    _MIN_W = 20
    _MIN_H = 10

    def extract(self, plate_image: np.ndarray) -> Optional[OCRResult]:
        """
        Run OCR on a cropped plate image.

        Returns None if no text was found or confidence is below threshold.
        """
        if self._ocr is None:
            self._init_ocr()
        if self._ocr is None:
            return None

        # Guard: reject crops that are too small — PaddleOCR segfaults on tiny inputs
        if plate_image is None or plate_image.size == 0:
            return None
        h, w = plate_image.shape[:2]
        if w < self._MIN_W or h < self._MIN_H:
            logger.debug("Crop too small ({w}x{h}), skipping OCR", w=w, h=h)
            return None

        # Ensure C-contiguous memory layout — misaligned arrays can crash Paddle
        img = np.ascontiguousarray(plate_image)

        try:
            result = self._ocr.ocr(img, cls=True)
        except Exception as exc:
            logger.error("PaddleOCR inference error: {err}", err=exc)
            return None

        if not result or not result[0]:
            return None

        # Aggregate all text boxes: pick the one with highest confidence or join
        texts = []
        confidences = []
        for line in result[0]:
            if line is None:
                continue
            bbox, (text, conf) = line
            texts.append(text)
            confidences.append(conf)

        if not texts:
            return None

        raw_text = " ".join(texts)
        avg_confidence = sum(confidences) / len(confidences)

        if avg_confidence < self.confidence_threshold:
            logger.debug(
                "OCR confidence {conf:.2f} below threshold {thr:.2f}",
                conf=avg_confidence,
                thr=self.confidence_threshold,
            )
            return None

        cleaned = self._clean_text(raw_text)
        logger.debug("OCR result: {text!r} (conf={conf:.2f})", text=cleaned, conf=avg_confidence)
        return OCRResult(text=cleaned, confidence=avg_confidence, raw_text=raw_text)

    # ── Internal helpers ───────────────────────────────────────────────────────

    def _init_ocr(self) -> None:
        try:
            from paddleocr import PaddleOCR  # type: ignore[import]

            self._ocr = PaddleOCR(
                use_angle_cls=True,
                lang=self.lang,
                use_gpu=False,
                show_log=False,
                enable_mkldnn=False,  # MKL threading causes SIGSEGV on Linux
                cpu_threads=1,        # single-threaded avoids race conditions
            )
            logger.info("PaddleOCR initialised (lang={lang}).", lang=self.lang)
        except ImportError:
            logger.error("paddleocr package not installed. OCR service disabled.")
        except Exception as exc:
            logger.error("Failed to initialise PaddleOCR: {err}", err=exc)

    @staticmethod
    def _clean_text(text: str) -> str:
        """
        Remove spaces and normalise to uppercase.

        PaddleOCR sometimes inserts spaces between characters of a compact plate.
        """
        return text.upper().replace(" ", "").strip()
