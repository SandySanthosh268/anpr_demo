"""Unit tests for OCR cleanup and validation pipeline edge cases."""
from __future__ import annotations

import pytest

from ocr_service.paddle_ocr import PaddleOCRService
from validation_service.plate_validator import PlateValidator


def test_ocr_clean_text_removes_spaces():
    svc = PaddleOCRService.__new__(PaddleOCRService)
    assert PaddleOCRService._clean_text("TN 01 AB 1234") == "TN01AB1234"


def test_ocr_clean_text_uppercase():
    assert PaddleOCRService._clean_text("tn01ab1234") == "TN01AB1234"


def test_validator_normalise_strips_special_chars():
    result = PlateValidator._normalise("TN-01-AB-1234")
    assert result == "TN01AB1234"


def test_validator_normalise_handles_spaces():
    result = PlateValidator._normalise("TN 01 AB 1234")
    assert result == "TN01AB1234"


@pytest.mark.parametrize("raw,expected_pattern", [
    ("TN01AB1234", "standard"),
    ("22BH1234AB", "bh_series"),
    ("GARBAGE123", "unknown"),
])
def test_correct_and_match_patterns(raw, expected_pattern):
    v = PlateValidator(min_confidence=0.5, duplicate_window=10)
    normalised = PlateValidator._normalise(raw)
    _, pattern = v._correct_and_match(normalised)
    assert pattern == expected_pattern


def test_full_pipeline_reject_low_confidence():
    v = PlateValidator(min_confidence=0.8)
    result = v.validate("TN01AB1234", confidence=0.5)
    assert not result.is_valid


def test_full_pipeline_accept_valid():
    v = PlateValidator(min_confidence=0.6)
    result = v.validate("KA05MN1111", confidence=0.95)
    assert result.is_valid
    assert result.plate_number == "KA05MN1111"
    assert result.pattern_type == "standard"
