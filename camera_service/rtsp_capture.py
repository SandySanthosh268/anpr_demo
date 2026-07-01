from __future__ import annotations

import asyncio
import os
import threading
import time
from dataclasses import dataclass, field
from typing import AsyncGenerator, Optional

import cv2
import numpy as np
from loguru import logger

from config import get_settings

settings = get_settings()

_STREAM_PREFIXES = ("rtsp://", "rtsps://", "rtmp://", "http://", "https://")


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
    Async video source ingestion.

    RTSP/RTMP/HTTP streams:
      A background drain thread reads every incoming frame and keeps only the
      latest in a shared buffer.  The pipeline always receives the most current
      view of the scene — stale queued frames are silently dropped.

    Local video files:
      Every frame is yielded in sequence so no detections are missed.

    Both sources reconnect automatically on failure.
    """

    def __init__(
        self,
        rtsp_url: str,
        camera_name: str,
        reconnect_delay: int = 5,
        max_reconnect_attempts: int = 10,
    ) -> None:
        self.rtsp_url = rtsp_url
        self.camera_name = camera_name
        self.reconnect_delay = reconnect_delay
        self.max_reconnect_attempts = max_reconnect_attempts
        self.is_file = not any(rtsp_url.lower().startswith(p) for p in _STREAM_PREFIXES)

        self._cap: Optional[cv2.VideoCapture] = None
        self._stats = CameraStats()
        self._running = False

        # Latest-frame buffer used by the RTSP drain thread
        self._latest_frame: Optional[np.ndarray] = None
        self._latest_ts: float = 0.0
        self._frame_lock = threading.Lock()
        self._new_frame = threading.Event()
        self._drain_thread: Optional[threading.Thread] = None

    @property
    def stats(self) -> CameraStats:
        return self._stats

    # ── Public API ─────────────────────────────────────────────────────────────

    async def stream_frames(self) -> AsyncGenerator[FrameResult, None]:
        self._running = True
        reconnect_attempts = 0

        while self._running:
            connected = await self._connect()
            if not connected:
                if self.is_file:
                    logger.error("File source not found: {path}", path=self.rtsp_url)
                    break
                reconnect_attempts += 1
                if reconnect_attempts > self.max_reconnect_attempts:
                    logger.error(
                        "Camera {name}: exceeded max reconnect attempts.",
                        name=self.camera_name,
                    )
                    break
                logger.warning(
                    "Camera {name}: reconnect {attempt}/{max} in {delay}s",
                    name=self.camera_name,
                    attempt=reconnect_attempts,
                    max=self.max_reconnect_attempts,
                    delay=self.reconnect_delay,
                )
                await asyncio.sleep(self.reconnect_delay)
                continue

            reconnect_attempts = 0
            self._stats.is_connected = True
            src_type = "file" if self.is_file else "stream"
            logger.info("Camera {name}: {t} connected.", name=self.camera_name, t=src_type)

            async for frame_result in self._read_frames():
                if not self._running:
                    break
                yield frame_result

            self._stats.is_connected = False

            if self.is_file:
                logger.info("File {name}: reached end of file.", name=self.camera_name)
                break
            else:
                if self._running:
                    logger.warning(
                        "Camera {name}: stream lost, reconnecting…",
                        name=self.camera_name,
                    )
                    self._stop_drain_thread()
                    self._release()
                    await asyncio.sleep(self.reconnect_delay)

    def stop(self) -> None:
        self._running = False
        self._stop_drain_thread()
        self._release()
        logger.info("Camera {name}: stopped.", name=self.camera_name)

    # ── Connection ─────────────────────────────────────────────────────────────

    async def _connect(self) -> bool:
        try:
            self._stop_drain_thread()
            self._release()
            loop = asyncio.get_event_loop()
            cap = await loop.run_in_executor(None, self._open_capture)
            if cap is None or not cap.isOpened():
                return False
            self._cap = cap
            self._stats.reconnect_count += 1

            if not self.is_file:
                # Start background thread that drains RTSP as fast as possible
                self._latest_frame = None
                self._new_frame.clear()
                self._drain_thread = threading.Thread(
                    target=self._drain_rtsp, daemon=True, name=f"drain-{self.camera_name}"
                )
                self._drain_thread.start()

            return True
        except Exception as exc:
            logger.error("Camera {name}: connect error: {err}", name=self.camera_name, err=exc)
            return False

    def _open_capture(self) -> Optional[cv2.VideoCapture]:
        if self.is_file:
            cap = cv2.VideoCapture(self.rtsp_url)
        else:
            os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp|buffer_size;2097152"
            cap = cv2.VideoCapture(self.rtsp_url, cv2.CAP_FFMPEG)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)   # smallest possible: keep pipeline lag low
            cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 10_000)
            cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, 10_000)
        return cap if cap.isOpened() else None

    # ── Frame reading ──────────────────────────────────────────────────────────

    async def _read_frames(self) -> AsyncGenerator[FrameResult, None]:
        if self.is_file:
            async for fr in self._read_file_frames():
                yield fr
        else:
            async for fr in self._read_latest_frame():
                yield fr

    async def _read_latest_frame(self) -> AsyncGenerator[FrameResult, None]:
        """
        RTSP: yield the latest frame from the drain thread's buffer.

        The drain thread runs at full camera FPS in the background.  We wake up
        here whenever a new frame arrives and always deliver the freshest image
        to the pipeline — intermediate frames that arrived while the pipeline was
        busy with detection/OCR are silently discarded.
        """
        loop = asyncio.get_event_loop()

        while self._running:
            # Block (off the event loop) until the drain thread signals a new frame
            got = await loop.run_in_executor(
                None, lambda: self._new_frame.wait(timeout=2.0)
            )
            if not got:
                # 2-second timeout — stream is likely dead
                logger.warning("Camera {name}: no frame for 2s, assuming stream lost.", name=self.camera_name)
                break

            with self._frame_lock:
                frame = self._latest_frame
                ts = self._latest_ts
                self._new_frame.clear()   # consumed — wait for next new frame

            if frame is None:
                break

            self._stats.processed_frames += 1
            yield FrameResult(
                frame=frame,
                frame_number=self._stats.total_frames,
                timestamp=ts,
                camera_name=self.camera_name,
            )
            await asyncio.sleep(0)  # yield control back to event loop

    async def _read_file_frames(self) -> AsyncGenerator[FrameResult, None]:
        """
        File: yield every Nth frame (controlled by FRAME_SKIP in .env).
        All frames are read from disk so total_frames stays accurate,
        but only every Nth is sent to the detection pipeline.
        """
        loop = asyncio.get_event_loop()

        while self._running and self._cap is not None:
            ret, frame = await loop.run_in_executor(None, self._cap.read)
            if not ret or frame is None:
                break

            self._stats.total_frames += 1
            ts = time.time()
            self._stats.last_frame_time = ts

            if self._stats.total_frames % settings.frame_skip != 0:
                await asyncio.sleep(0)
                continue

            self._stats.processed_frames += 1
            yield FrameResult(
                frame=self._preprocess(frame),
                frame_number=self._stats.total_frames,
                timestamp=ts,
                camera_name=self.camera_name,
            )
            await asyncio.sleep(0)

    # ── Drain thread (RTSP only) ───────────────────────────────────────────────

    def _drain_rtsp(self) -> None:
        """
        Runs in a daemon thread.  Reads from the RTSP stream as fast as the
        camera produces frames and stores only the latest in _latest_frame.
        Old frames are overwritten — we never queue them.
        """
        logger.debug("Drain thread started for {name}.", name=self.camera_name)
        while self._running and self._cap is not None:
            ret, frame = self._cap.read()
            if not ret or frame is None:
                logger.debug("Drain thread: stream ended for {name}.", name=self.camera_name)
                break

            self._stats.total_frames += 1
            ts = time.time()
            self._stats.last_frame_time = ts

            processed = self._preprocess(frame)
            with self._frame_lock:
                self._latest_frame = processed
                self._latest_ts = ts
            self._new_frame.set()  # wake up _read_latest_frame

        # Signal the async generator that no more frames are coming
        self._new_frame.set()
        logger.debug("Drain thread finished for {name}.", name=self.camera_name)

    def _stop_drain_thread(self) -> None:
        if self._drain_thread is not None and self._drain_thread.is_alive():
            # _running=False and cap release will cause the thread to exit naturally
            self._drain_thread.join(timeout=3.0)
        self._drain_thread = None

    # ── Helpers ────────────────────────────────────────────────────────────────

    @staticmethod
    def _preprocess(frame: np.ndarray) -> np.ndarray:
        h, w = frame.shape[:2]
        if w > 1280:
            scale = 1280 / w
            frame = cv2.resize(frame, (1280, int(h * scale)), interpolation=cv2.INTER_AREA)
        return frame

    def _release(self) -> None:
        if self._cap is not None:
            try:
                self._cap.release()
            except Exception:
                pass
            self._cap = None
