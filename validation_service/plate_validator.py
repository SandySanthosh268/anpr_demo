from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

from loguru import logger

from config import get_settings

settings = get_settings()

# ─── Indian plate patterns ────────────────────────────────────────────────────
#
# Standard:    SS DD LL NNNN   e.g. TN01AB1234
# BH Series:   YY BH NNNN LL  e.g. 22BH1234AB
# Temporary:   TEMP-NN-NN-NNNN
#
_STANDARD = re.compile(
    r"^([A-Z]{2})(\d{2})([A-Z]{1,3})(\d{4})$"
)
_BH_SERIES = re.compile(
    r"^(\d{2})(BH)(\d{4})([A-Z]{1,2})$"
)
_TEMPORARY = re.compile(
    r"^TEMP[-]?\d{2}[-]?\d{2}[-]?\d{4}$"
)

# Valid Indian state/UT codes
_STATE_CODES = frozenset(
    "AN AP AR AS BH CG CH DD DL DN GA GJ HP HR JH JK JL KA KL LA LD MH ML MN "
    "MP MZ NL OD PB PY RJ SK TN TR TS UK UP WB".split()
)


# ─── OCR correction rules ─────────────────────────────────────────────────────
#
# These substitutions fix common OCR confusions for specific positions.
# Applied before pattern matching.
#
_OCR_CORRECTIONS: Dict[str, str] = {
    "O": "0",   # digit position  → prefer zero
    "I": "1",   # digit position  → prefer one
    "Z": "2",
    "S": "5",
    "B": "8",
    "G": "6",
    "T": "7",
}
# For letter positions: digits that look like letters
_DIGIT_TO_LETTER: Dict[str, list] = {
    "0": ["O", "D", "Q"],   # D is very common in Indian series (TN07DD2233)
    "1": ["I", "L"],
    "8": ["B"],
    "6": ["G"],
    "5": ["S"],
}


@dataclass
class ValidationResult:
    is_valid: bool
    plate_number: str          # corrected, normalised plate
    raw_text: str              # as-is from OCR
    confidence: float
    pattern_type: str = "unknown"  # standard | bh_series | temporary


class PlateValidator:
    """
    Validates and corrects Indian vehicle registration numbers.

    Key responsibilities:
    - Apply positional OCR correction (O↔0, I↔1, …)
    - Match against standard / BH-series / temporary patterns
    - Suppress duplicate detections within a configurable time window
    - Filter by minimum confidence threshold
    """

    def __init__(
        self,
        min_confidence: float = 0.6,
        duplicate_window: int = 30,
    ) -> None:
        self.min_confidence = min_confidence
        self.duplicate_window = duplicate_window
        # plate → last_seen_timestamp
        self._seen: Dict[str, float] = {}

    # ── Public API ─────────────────────────────────────────────────────────────

    def validate(self, raw_text: str, confidence: float) -> ValidationResult:
        if confidence < self.min_confidence:
            return ValidationResult(
                is_valid=False,
                plate_number=raw_text.upper(),
                raw_text=raw_text,
                confidence=confidence,
            )

        normalised = self._normalise(raw_text)
        corrected, pattern = self._correct_and_match(normalised)

        is_valid = pattern != "unknown"
        if is_valid:
            is_valid = self._validate_state_code(corrected)

        result = ValidationResult(
            is_valid=is_valid,
            plate_number=corrected,
            raw_text=raw_text,
            confidence=confidence,
            pattern_type=pattern,
        )
        logger.debug(
            "Validation: {raw!r} → {plate!r} valid={v} pattern={p}",
            raw=raw_text,
            plate=corrected,
            v=is_valid,
            p=pattern,
        )
        return result

    def is_duplicate(self, plate_number: str) -> bool:
        """True if the same plate was seen within the duplicate window."""
        now = time.monotonic()
        last = self._seen.get(plate_number)
        if last is not None and (now - last) < self.duplicate_window:
            logger.debug("Duplicate suppressed: {plate}", plate=plate_number)
            return True
        self._seen[plate_number] = now
        self._evict_stale()
        return False

    # ── Internal helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _normalise(text: str) -> str:
        return re.sub(r"[^A-Z0-9]", "", text.upper())

    def _correct_and_match(self, text: str) -> Tuple[str, str]:
        # Try the text as-is, then with 1 or 2 leading characters stripped.
        # This handles OCR noise at the start (e.g. logo/emblem read as 'P').
        for strip in (0, 1, 2):
            candidate_text = text[strip:] if strip else text
            for attempt in self._correction_candidates(candidate_text):
                if _STANDARD.match(attempt):
                    return attempt, "standard"
                if _BH_SERIES.match(attempt):
                    return attempt, "bh_series"
                if _TEMPORARY.match(attempt):
                    return attempt, "temporary"
        return text, "unknown"

    @staticmethod
    def _correction_candidates(text: str) -> list[str]:
        """
        Generate corrected variants for a standard Indian plate SS DD LL NNNN.

        Positional rules (10-char plate):
          0,1   → letters (state code)
          2,3   → digits  (RTO number)
          4-6   → letters (series)  ← '0' commonly means 'D' or 'O' here
          6-9   → digits  (number)

        Applies multi-position corrections so that e.g. '00' → 'DD' is found
        in a single candidate rather than needing two separate passes.
        """
        import itertools

        candidates = [text]
        if len(text) < 8:
            return candidates

        chars = list(text)

        # Build per-position option lists for the series letter block (positions 4-6).
        # Each position yields a list of possible characters.
        series_positions = list(range(4, min(7, len(chars))))
        series_options: list[list[str]] = []
        for i in series_positions:
            ch = chars[i]
            opts = _DIGIT_TO_LETTER.get(ch, [ch])  # possible letter replacements
            series_options.append([ch] + [l for l in opts if l != ch])

        # Cartesian product of all series-position options → multi-char corrections
        for combo in itertools.product(*series_options):
            c = chars[:]
            for i, ch in zip(series_positions, combo):
                c[i] = ch
            candidate = "".join(c)
            if candidate not in candidates:
                candidates.append(candidate)

        # Positions 0,1: state-code letters — fix digits that look like letters
        for i in (0, 1):
            if i < len(chars) and chars[i] in _DIGIT_TO_LETTER:
                for letter in _DIGIT_TO_LETTER[chars[i]]:
                    c = chars[:]
                    c[i] = letter
                    if "".join(c) not in candidates:
                        candidates.append("".join(c))

        # Positions 2,3: RTO digit positions — fix letters that look like digits
        for i in (2, 3):
            if i < len(chars) and chars[i] in _OCR_CORRECTIONS:
                c = chars[:]
                c[i] = _OCR_CORRECTIONS[chars[i]]
                if "".join(c) not in candidates:
                    candidates.append("".join(c))

        # Last 4 positions: number digits — fix letters that look like digits
        for i in range(max(0, len(chars) - 4), len(chars)):
            if chars[i] in _OCR_CORRECTIONS:
                c = chars[:]
                c[i] = _OCR_CORRECTIONS[chars[i]]
                if "".join(c) not in candidates:
                    candidates.append("".join(c))

        return candidates

    @staticmethod
    def _validate_state_code(plate: str) -> bool:
        m = _STANDARD.match(plate)
        if m:
            return m.group(1) in _STATE_CODES
        # BH series has no state code
        return _BH_SERIES.match(plate) is not None or _TEMPORARY.match(plate) is not None

    def _evict_stale(self) -> None:
        now = time.monotonic()
        stale = [k for k, v in self._seen.items() if now - v > self.duplicate_window * 2]
        for k in stale:
            del self._seen[k]
