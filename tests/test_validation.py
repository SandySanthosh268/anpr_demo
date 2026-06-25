"""Unit tests for the PlateValidator."""
from __future__ import annotations

import time

import pytest

from validation_service.plate_validator import PlateValidator


@pytest.fixture
def validator():
    return PlateValidator(min_confidence=0.6, duplicate_window=5)


# ── Valid Indian plates ────────────────────────────────────────────────────────

@pytest.mark.parametrize("plate", [
    "TN01AB1234",
    "KA05MN1111",
    "MH12XY5678",
    "DL01AB0001",
    "UP80GH9999",
    "GJ15CD3456",
    "RJ14EF7890",
    "AP09GH1234",
])
def test_valid_standard_plates(validator, plate):
    result = validator.validate(plate, confidence=0.9)
    assert result.is_valid, f"Expected {plate!r} to be valid"
    assert result.plate_number == plate


# ── BH series plates ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("plate", [
    "22BH1234AB",
    "23BH5678CD",
])
def test_bh_series_plates(validator, plate):
    result = validator.validate(plate, confidence=0.9)
    assert result.is_valid, f"Expected BH plate {plate!r} to be valid"
    assert result.pattern_type == "bh_series"


# ── Invalid plates ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("plate", [
    "XXXXXX",
    "123456",
    "ABCDEFGH",
    "",
    "ZZ99ZZ9999",  # ZZ is not a valid state code
])
def test_invalid_plates(validator, plate):
    result = validator.validate(plate, confidence=0.9)
    assert not result.is_valid, f"Expected {plate!r} to be invalid"


# ── OCR correction ─────────────────────────────────────────────────────────────

def test_ocr_correction_zero_for_o(validator):
    """O in digit positions should be corrected to 0."""
    result = validator.validate("TN0OAB1234", confidence=0.9)
    # After correction TN00AB1234 should be valid (TN is a valid state code)
    assert result.is_valid
    assert "0" in result.plate_number


def test_ocr_correction_one_for_i(validator):
    """I in digit positions should be corrected to 1."""
    result = validator.validate("TN0IAB1234", confidence=0.9)
    assert result.is_valid


# ── Confidence threshold ───────────────────────────────────────────────────────

def test_low_confidence_rejected(validator):
    result = validator.validate("TN01AB1234", confidence=0.3)
    assert not result.is_valid


def test_boundary_confidence_accepted(validator):
    result = validator.validate("TN01AB1234", confidence=0.6)
    assert result.is_valid


# ── Duplicate suppression ──────────────────────────────────────────────────────

def test_duplicate_suppressed_within_window(validator):
    plate = "KA01AB1234"
    assert not validator.is_duplicate(plate)   # first time → not duplicate
    assert validator.is_duplicate(plate)        # second time within window → duplicate


def test_duplicate_allowed_after_window(validator):
    validator2 = PlateValidator(min_confidence=0.6, duplicate_window=1)
    plate = "KA02CD5678"
    assert not validator2.is_duplicate(plate)
    time.sleep(1.1)
    assert not validator2.is_duplicate(plate)   # window expired → not duplicate anymore
