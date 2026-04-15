import pytest

from app.infrastructure.fish.calibration import (
    pixels_per_cm_from_measurement,
    bbox_to_cm,
)
from app.domain.fish.reference_types import ReferenceType


def test_pixels_per_cm_basic():
    result = pixels_per_cm_from_measurement(
        measured_px=100.0, ref_type=ReferenceType.COIN_PHP_5
    )
    assert result == pytest.approx(40.0, rel=1e-6)


def test_pixels_per_cm_card():
    result = pixels_per_cm_from_measurement(
        measured_px=856.0, ref_type=ReferenceType.ID_CARD
    )
    assert result == pytest.approx(100.0, rel=1e-6)


def test_pixels_per_cm_rejects_manual():
    with pytest.raises(ValueError):
        pixels_per_cm_from_measurement(
            measured_px=100.0, ref_type=ReferenceType.MANUAL
        )


def test_pixels_per_cm_rejects_zero():
    with pytest.raises(ValueError):
        pixels_per_cm_from_measurement(
            measured_px=0.0, ref_type=ReferenceType.COIN_PHP_5
        )


def test_bbox_to_cm():
    length_cm, width_cm = bbox_to_cm(
        bbox_width_px=120.0, bbox_height_px=40.0, pixels_per_cm=40.0
    )
    assert length_cm == pytest.approx(3.0)
    assert width_cm == pytest.approx(1.0)


def test_bbox_to_cm_uses_longer_as_length():
    length_cm, width_cm = bbox_to_cm(
        bbox_width_px=40.0, bbox_height_px=120.0, pixels_per_cm=40.0
    )
    assert length_cm == pytest.approx(3.0)
    assert width_cm == pytest.approx(1.0)


def test_bbox_to_cm_rejects_invalid_scale():
    with pytest.raises(ValueError):
        bbox_to_cm(bbox_width_px=100.0, bbox_height_px=50.0, pixels_per_cm=0.0)
