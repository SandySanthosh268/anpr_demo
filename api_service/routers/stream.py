from __future__ import annotations

import asyncio
from typing import AsyncGenerator

import cv2
import numpy as np
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from api_service.frame_buffer import frame_buffer

router = APIRouter(tags=["stream"])

# ── Placeholder frame (shown when camera is offline) ──────────────────────────
def _make_placeholder() -> bytes:
    img = np.zeros((360, 640, 3), dtype=np.uint8)
    cv2.putText(img, "Waiting for camera...", (140, 170),
                cv2.FONT_HERSHEY_SIMPLEX, 0.9, (100, 100, 100), 2)
    cv2.putText(img, "Check RTSP_URL in .env", (160, 210),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (70, 70, 70), 1)
    _, buf = cv2.imencode(".jpg", img)
    return buf.tobytes()


_PLACEHOLDER = _make_placeholder()


async def _generate_mjpeg() -> AsyncGenerator[bytes, None]:
    boundary = b"--frame\r\nContent-Type: image/jpeg\r\n\r\n"
    while True:
        jpeg = frame_buffer.get() or _PLACEHOLDER
        yield boundary + jpeg + b"\r\n"
        await asyncio.sleep(1 / 15)   # stream at ~15 fps


@router.get("/stream/video")
async def video_stream():
    """MJPEG stream of the live camera feed with detection overlays."""
    return StreamingResponse(
        _generate_mjpeg(),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={"Cache-Control": "no-cache, no-store"},
    )
