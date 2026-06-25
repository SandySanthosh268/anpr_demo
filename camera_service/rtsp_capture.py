from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import AsyncGenerator, Optional

import cv2
import numpy as np
from loguru import logger

from config import get_settings

settings = get_settings()


@dataclass
class FrameResult:
    frame: np.ndarray
    frame_number: int
    timestamp: float
    camera_name: str


@dataclass
class CameraStats:
    total_frames: int = 0
    processed_frames: int = 0
    reconnect_count: int = 0
    last_frame_time: float = field(default_factory=time.time)
    is_connected: bool = False


class RTSPCapture:
    """
    Async RTSP stream ingestion with automatic reconnection.

    Yields every Nth frame (controlled by frame_skip) so the detection
    pipeline does not receive more frames than it can process.
    """

    def __init__(
        self,
        rtsp_url: str,
        camera_name: str,
        frame_skip: int = 5,
        reconnect_delay: int = 5,
        max_reconnect_attempts: int = 10,
    ) -> None:
        self.rtsp_url = rtsp_url
        self.camera_name = camera_name
        self.frame_skip = frame_skip
        self.reconnect_delay = reconnect_delay
        self.max_reconnect_attempts = max_reconnect_attempts

        self._cap: Optional[cv2.VideoCapture] = None
        self._stats = CameraStats()
        self._running = False

    # ── Public API ────────────────────────────────────────────────────────────

    @property
    def stats(self) -> CameraStats:
        return self._stats

    async def stream_frames(self) -> AsyncGenerator[FrameResult, None]:
        """Yields processed frames continuously until stopped."""
        self._running = True
        reconnect_attempts = 0

        while self._running:
            connected = await self._connect()
            if not connected:
                reconnect_attempts += 1
                if reconnect_attempts > self.max_reconnect_attempts:
                    logger.error(
                        "Camera {name} exceeded max reconnect attempts ({max}). Stopping.",
                        name=self.camera_name,
                        max=self.max_reconnect_attempts,
                    )
                    break
                logger.warning(
                    "Camera {name}: reconnect attempt {attempt}/{max} in {delay}s",
                    name=self.camera_name,
                    attempt=reconnect_attempts,
                    max=self.max_reconnect_attempts,
                    delay=self.reconnect_delay,
                )
                await asyncio.sleep(self.reconnect_delay)
                continue

            reconnect_attempts = 0
            self._stats.is_connected = True
            logger.info("Camera {name}: stream connected.", name=self.camera_name)

            async for frame_result in self._read_frames():
                if not self._running:
                    break
                yield frame_result

            self._stats.is_connected = False
            if self._running:
                logger.warning(
                    "Camera {name}: stream lost, reconnecting...",
                    name=self.camera_name,
                )
                self._release()
                await asyncio.sleep(self.reconnect_delay)

    def stop(self) -> None:
        self._running = False
        self._release()
        logger.info("Camera {name}: capture stopped.", name=self.camera_name)

    # ── Internal helpers ──────────────────────────────────────────────────────

    async def _connect(self) -> bool:
        try:
            self._release()
            loop = asyncio.get_event_loop()
            cap = await loop.run_in_executor(None, self._open_capture)
            if cap is None or not cap.isOpened():
                return False
            self._cap = cap
            self._stats.reconnect_count += 1
            return True
        except Exception as exc:
            logger.error("Camera {name}: connection error: {err}", name=self.camera_name, err=exc)
            return False

    def _open_capture(self) -> Optional[cv2.VideoCapture]:
        cap = cv2.VideoCapture(self.rtsp_url, cv2.CAP_FFMPEG)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 10_000)
        cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, 10_000)
        if not cap.isOpened():
            return None
        return cap

    async def _read_frames(self) -> AsyncGenerator[FrameResult, None]:
        frame_count = 0
        loop = asyncio.get_event_loop()

        while self._running and self._cap is not None:
            ret, frame = await loop.run_in_executor(None, self._cap.read)
            if not ret or frame is None:
                logger.warning("Camera {name}: frame read failed.", name=self.camera_name)
                break

            self._stats.total_frames += 1
            self._stats.last_frame_time = time.time()
            frame_count += 1

            if frame_count % self.frame_skip != 0:
                continue

            self._stats.processed_frames += 1
            preprocessed = self._preprocess(frame)
            yield FrameResult(
                frame=preprocessed,
                frame_number=self._stats.total_frames,
                timestamp=self._stats.last_frame_time,
                camera_name=self.camera_name,
            )

            # Yield control to the event loop between frames
            await asyncio.sleep(0)

    @staticmethod
    def _preprocess(frame: np.ndarray) -> np.ndarray:
        """Light preprocessing: resize to a standard width for consistent detection."""
        h, w = frame.shape[:2]
        target_width = 1280
        if w > target_width:
            scale = target_width / w
            frame = cv2.resize(frame, (target_width, int(h * scale)), interpolation=cv2.INTER_AREA)
        return frame

    def _release(self) -> None:
        if self._cap is not None:
            try:
                self._cap.release()
            except Exception:
                pass
            self._cap = None

    def __repr__(self) -> str:
        return (
            f"RTSPCapture(camera={self.camera_name!r}, "
            f"connected={self._stats.is_connected}, "
            f"frames_processed={self._stats.processed_frames})"
        )
