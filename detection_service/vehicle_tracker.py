from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple


@dataclass
class _Track:
    track_id: int
    bbox: List[int]       # [x1, y1, x2, y2]
    frames_missing: int = 0
    total_frames: int = 1


class VehicleTracker:
    """
    Lightweight IoU-based multi-object tracker.

    Assigns a persistent track_id to each plate detection and carries it across
    frames. No external library — pure Python + simple IoU math.

    Lifecycle:
      - New detection with no IoU match above threshold → new track_id assigned.
      - Matched detection → track_id re-used, frames_missing reset to 0.
      - Track unseen for > max_miss_frames → marked finalized and removed.
    """

    def __init__(
        self,
        iou_threshold: float = 0.35,
        max_miss_frames: int = 30,
    ) -> None:
        self.iou_threshold = iou_threshold
        self.max_miss_frames = max_miss_frames
        self._tracks: Dict[int, _Track] = {}
        self._next_id: int = 1

    # ── Public API ─────────────────────────────────────────────────────────────

    def update(
        self, bboxes: List[List[int]]
    ) -> Tuple[List[int], List[int]]:
        """
        Match new detections to existing tracks for one frame.

        Args:
            bboxes: list of [x1, y1, x2, y2] plate bounding boxes this frame.

        Returns:
            track_ids   — parallel list of IDs for each input bbox.
            finalized   — IDs of tracks that just expired (unseen too long).
        """
        # Age every track by one frame before matching
        for track in self._tracks.values():
            track.frames_missing += 1

        assigned_tids: set[int] = set()
        track_ids: List[int] = []

        for bbox in bboxes:
            best_iou = 0.0
            best_tid = None

            for tid, track in self._tracks.items():
                if tid in assigned_tids:
                    continue
                iou = _iou(bbox, track.bbox)
                if iou > best_iou:
                    best_iou = iou
                    best_tid = tid

            if best_iou >= self.iou_threshold and best_tid is not None:
                track = self._tracks[best_tid]
                track.bbox = bbox
                track.frames_missing = 0
                track.total_frames += 1
                assigned_tids.add(best_tid)
                track_ids.append(best_tid)
            else:
                new_tid = self._next_id
                self._next_id += 1
                self._tracks[new_tid] = _Track(track_id=new_tid, bbox=bbox)
                track_ids.append(new_tid)

        # Expire tracks that have been missing too long
        finalized = [
            tid
            for tid, t in self._tracks.items()
            if t.frames_missing > self.max_miss_frames
        ]
        for tid in finalized:
            del self._tracks[tid]

        return track_ids, finalized

    @property
    def active_count(self) -> int:
        return len(self._tracks)


# ── Module-level helper (no numpy needed) ─────────────────────────────────────

def _iou(a: List[int], b: List[int]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b

    ix1 = max(ax1, bx1)
    iy1 = max(ay1, by1)
    ix2 = min(ax2, bx2)
    iy2 = min(ay2, by2)

    inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
    if inter == 0:
        return 0.0

    area_a = (ax2 - ax1) * (ay2 - ay1)
    area_b = (bx2 - bx1) * (by2 - by1)
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0
