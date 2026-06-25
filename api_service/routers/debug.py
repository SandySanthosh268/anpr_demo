from __future__ import annotations

import io

import cv2
import numpy as np
from fastapi import APIRouter, UploadFile, File
from fastapi.responses import JSONResponse

from ocr_service.paddle_ocr import PaddleOCRService
from validation_service.plate_validator import PlateValidator

router = APIRouter(prefix="/debug", tags=["debug"])

_ocr = PaddleOCRService(confidence_threshold=0.0)   # no threshold — show everything
_validator = PlateValidator(min_confidence=0.0)


@router.post("/ocr")
async def test_ocr(file: UploadFile = File(...)):
    """Upload a plate crop image and see raw OCR output + validation result."""
    data = await file.read()
    arr = np.frombuffer(data, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        return JSONResponse({"error": "Could not decode image"}, status_code=400)

    result = _ocr.extract(img)
    if result is None:
        return {"ocr": None, "message": "PaddleOCR returned no text"}

    validation = _validator.validate(result.text, confidence=1.0)
    return {
        "raw_text": result.raw_text,
        "cleaned_text": result.text,
        "ocr_confidence": round(result.confidence, 3),
        "validation": {
            "is_valid": validation.is_valid,
            "plate_number": validation.plate_number,
            "pattern_type": validation.pattern_type,
        },
    }
