from __future__ import annotations

import threading
from typing import Optional


class FrameBuffer:
    """Thread-safe store for the latest JPEG-encoded annotated frame."""

    def __init__(self) -> None:
        self._jpeg: Optional[bytes] = None
        self._lock = threading.Lock()

    def update(self, jpeg_bytes: bytes) -> None:
        with self._lock:
            self._jpeg = jpeg_bytes

    def get(self) -> Optional[bytes]:
        with self._lock:
            return self._jpeg


# Singleton shared between the pipeline and the stream router
frame_buffer = FrameBuffer()
