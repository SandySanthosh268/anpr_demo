from __future__ import annotations

from collections import Counter
from typing import Optional

from loguru import logger


class PlateVoter:
    """
    Majority-vote plate text selector per track.

    For each track_id, collects validated OCR reads across frames.
    Once `min_votes` agree on the same plate text → the track is LOCKED.
    After locking:
      · OCR is skipped for that track (no more PaddleOCR calls)
      · The locked text is used for display and event emission
      · One detection event fires, never repeated for the same track

    If OCR results are noisy and no single plate reaches `min_votes` within
    `max_attempts` tries, the most-voted candidate is force-locked.
    """

    def __init__(self, min_votes: int = 3, max_attempts: int = 10) -> None:
        self.min_votes = min_votes
        self.max_attempts = max_attempts
        # track_id → Counter of plate text votes
        self._votes: dict[int, Counter] = {}
        # track_id → locked plate text (set once, never changes)
        self._locked: dict[int, str] = {}
        # track_id → total OCR attempts (including failed validates)
        self._attempts: dict[int, int] = {}

    # ── Public API ─────────────────────────────────────────────────────────────

    def vote(self, track_id: int, plate: str) -> Optional[str]:
        """
        Submit a validated plate read for track_id.
        Returns the locked plate string when consensus is reached, else None.
        If already locked, returns the locked plate immediately.
        """
        if track_id in self._locked:
            return self._locked[track_id]

        counter = self._votes.setdefault(track_id, Counter())
        counter[plate] += 1
        self._attempts[track_id] = self._attempts.get(track_id, 0) + 1

        winner, top_count = counter.most_common(1)[0]
        total = self._attempts[track_id]

        if top_count >= self.min_votes:
            self._lock(track_id, winner, reason=f"{top_count}/{self.min_votes} votes")
            return winner

        if total >= self.max_attempts:
            self._lock(track_id, winner, reason=f"force-lock after {total} attempts")
            return winner

        return None

    def count_attempt(self, track_id: int) -> None:
        """Record an OCR attempt that didn't yield a valid plate (e.g. OCR returned None)."""
        self._attempts[track_id] = self._attempts.get(track_id, 0) + 1
        # Force-lock on max_attempts even with no valid reads so track doesn't burn CPU forever
        if self._attempts[track_id] >= self.max_attempts and track_id not in self._locked:
            counter = self._votes.get(track_id)
            if counter:
                winner, _ = counter.most_common(1)[0]
                self._lock(track_id, winner, reason="force-lock (mostly invalid OCR)")

    def is_locked(self, track_id: int) -> bool:
        return track_id in self._locked

    def get_locked(self, track_id: int) -> Optional[str]:
        return self._locked.get(track_id)

    def top_candidate(self, track_id: int) -> Optional[str]:
        """Best candidate so far (for interim display while voting)."""
        counter = self._votes.get(track_id)
        if not counter:
            return None
        return counter.most_common(1)[0][0]

    def vote_progress(self, track_id: int) -> tuple[int, int]:
        """Returns (top_vote_count, min_votes_needed) for display."""
        counter = self._votes.get(track_id)
        if not counter:
            return 0, self.min_votes
        return counter.most_common(1)[0][1], self.min_votes

    def finalize(self, track_id: int) -> None:
        """Remove all state for a track that has left the frame."""
        self._votes.pop(track_id, None)
        self._locked.pop(track_id, None)
        self._attempts.pop(track_id, None)

    def reset(self) -> None:
        """Clear all state (on source change / restart)."""
        self._votes.clear()
        self._locked.clear()
        self._attempts.clear()

    # ── Internal ───────────────────────────────────────────────────────────────

    def _lock(self, track_id: int, plate: str, reason: str) -> None:
        self._locked[track_id] = plate
        logger.info("Voter locked track={tid} → {plate!r} ({reason})",
                    tid=track_id, plate=plate, reason=reason)
