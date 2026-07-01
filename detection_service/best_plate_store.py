from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import cv2
import numpy as np
from loguru import logger


@dataclass
class _Entry:
    best_crop:    np.ndarray     # enhanced plate crop at highest quality seen
    best_score:   float          # quality score at time of best crop
    best_conf:    float          # YOLO confidence at time of best crop
    vehicle_type: str
    first_seen:   float          # UNIX timestamp of first detection
    best_bbox:    List[int]      # bbox [x1,y1,x2,y2] at time of best crop


class BestPlateStore:
    """
    Tracks the highest-quality plate crop seen for each active track_id.

    For every frame, call update() with the current crop + score.
    When the pipeline detects a valid plate event, call save_best_crop()
    to persist the best crop so far to disk.
    When a track is finalized (vehicle left frame), call pop() to release memory.

    Thread-safety: not needed — called from a single synchronous pipeline frame loop.
    """

    def __init__(self, save_dir: Path) -> None:
        self._store: Dict[int, _Entry] = {}
        self._save_dir = Path(save_dir)
        self._save_dir.mkdir(parents=True, exist_ok=True)

    # ── Public API ─────────────────────────────────────────────────────────────

    def update(
        self,
        track_id: int,
        crop: np.ndarray,
        score: float,
        conf: float,
        vehicle_type: str,
        bbox: List[int],
        timestamp: float,
    ) -> None:
        """
        Update the stored entry for track_id if the new score beats the current best.
        Creates a new entry if track_id is unseen.
        """
        entry = self._store.get(track_id)
        if entry is None:
            self._store[track_id] = _Entry(
                best_crop=crop.copy(),
                best_score=score,
                best_conf=conf,
                vehicle_type=vehicle_type,
                first_seen=timestamp,
                best_bbox=list(bbox),
            )
        elif score > entry.best_score:
            entry.best_crop = crop.copy()
            entry.best_score = score
            entry.best_conf = conf
            entry.vehicle_type = vehicle_type
            entry.best_bbox = list(bbox)

    def save_best_crop(self, track_id: int, plate_number: str) -> Optional[str]:
        """
        Write the best crop for track_id to disk.
        Filename: best_plates/TRK{id:04d}_{plate_number}.jpg
        Returns the file path, or None if no entry exists for this track.
        """
        entry = self._store.get(track_id)
        if entry is None:
            return None

        filename = f"TRK{track_id:04d}_{plate_number}.jpg"
        filepath = self._save_dir / filename
        try:
            cv2.imwrite(str(filepath), entry.best_crop)
            logger.debug(
                "Best plate saved: track={tid} plate={p} score={s:.3f} path={fp}",
                tid=track_id,
                p=plate_number,
                s=entry.best_score,
                fp=filepath,
            )
            return str(filepath)
        except Exception as exc:
            logger.warning("Failed to save best plate crop: {err}", err=exc)
            return None

    def pop(self, track_id: int) -> Optional[_Entry]:
        """Remove and return the entry for a finalized track (frees memory)."""
        return self._store.pop(track_id, None)

    def get_best_score(self, track_id: int) -> float:
        """Return current best score for a track, or 0.0 if unseen."""
        entry = self._store.get(track_id)
        return entry.best_score if entry else 0.0

    @property
    def active_count(self) -> int:
        return len(self._store)
