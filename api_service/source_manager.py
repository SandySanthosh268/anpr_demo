from __future__ import annotations

import asyncio

from config import get_settings

_STREAM_PREFIXES = ("rtsp://", "rtsps://", "rtmp://", "http://", "https://")


class SourceManager:
    """
    Singleton that holds the currently active video source.

    - RTSP / HTTP streams: auto-start on boot (pipeline_active = True)
    - Local file paths: manual-start (pipeline_active = False until play() is called)
    """

    def __init__(self) -> None:
        s = get_settings()
        self._url: str = s.video_source.strip() if s.video_source.strip() else s.rtsp_url
        self._name: str = s.camera_name
        self._event = asyncio.Event()
        self._pipeline_active: bool = not self._url_is_file(self._url)

    # ── Properties ────────────────────────────────────────────────────────────

    @property
    def url(self) -> str:
        return self._url

    @property
    def name(self) -> str:
        return self._name

    @property
    def is_file_source(self) -> bool:
        return self._url_is_file(self._url)

    @property
    def pipeline_active(self) -> bool:
        return self._pipeline_active

    # ── Control ───────────────────────────────────────────────────────────────

    def play(self) -> None:
        """Start (or resume) processing. For file sources only."""
        self._pipeline_active = True
        self._event.set()  # wakes the idle loop and recreates the capture from start

    def stop(self) -> None:
        """Pause processing. For file sources only."""
        self._pipeline_active = False

    def change(self, url: str, name: str) -> None:
        """Hot-swap to a new source. Files require manual play(); streams auto-start."""
        self._url = url
        self._name = name
        self._pipeline_active = not self._url_is_file(url)
        self._event.set()

    def take_restart(self) -> bool:
        """Returns True once per change/play event, then resets the flag."""
        if self._event.is_set():
            self._event.clear()
            return True
        return False

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _url_is_file(url: str) -> bool:
        return not any(url.lower().startswith(p) for p in _STREAM_PREFIXES)


source_manager = SourceManager()
