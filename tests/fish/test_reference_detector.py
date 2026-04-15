import pytest

from app.domain.fish.reference_types import ReferenceType
from app.infrastructure.fish.reference_detector import (
    detect_reference_object,
    ReferenceDetectionResult,
)
from tests.fish.helpers.synthetic_images import (
    make_coin_image,
    make_noise_image,
)


def test_detect_coin_php_5_synthetic():
    img = make_coin_image(canvas=(800, 600), diameter_px=100)
    result = detect_reference_object(img, ReferenceType.COIN_PHP_5)
    assert isinstance(result, ReferenceDetectionResult)
    assert result.status == "detected"
    assert 38.0 <= result.pixels_per_cm <= 42.0
    assert result.bounding_box is not None
    assert result.confidence > 0.0


def test_detect_coin_missing_returns_not_found():
    img = make_noise_image(canvas=(800, 600), seed=7)
    result = detect_reference_object(img, ReferenceType.COIN_PHP_5)
    assert result.status == "not_found"
    assert result.pixels_per_cm is None


def test_detect_coin_php_10_larger_diameter_scales():
    img = make_coin_image(canvas=(800, 600), diameter_px=100)
    result = detect_reference_object(img, ReferenceType.COIN_PHP_10)
    assert result.status == "detected"
    assert 35.5 <= result.pixels_per_cm <= 40.0


from tests.fish.helpers.synthetic_images import make_card_image, make_bill_image


def test_detect_id_card_synthetic():
    img = make_card_image(canvas=(1200, 800), card_long_px=600)
    result = detect_reference_object(img, ReferenceType.ID_CARD)
    assert result.status == "detected"
    assert 66.0 <= result.pixels_per_cm <= 75.0


def test_detect_bill_php_synthetic():
    img = make_bill_image(canvas=(1600, 900), bill_long_px=800)
    result = detect_reference_object(img, ReferenceType.BILL_PHP)
    assert result.status == "detected"
    assert 47.0 <= result.pixels_per_cm <= 53.0


def test_detect_card_missing_returns_not_found():
    img = make_noise_image(seed=11)
    result = detect_reference_object(img, ReferenceType.ID_CARD)
    assert result.status == "not_found"


from tests.fish.helpers.synthetic_images import make_aruco_image


def test_detect_aruco_4cm():
    img = make_aruco_image(canvas=(800, 600), side_px=200)
    result = detect_reference_object(img, ReferenceType.ARUCO_4CM)
    assert result.status == "detected"
    assert 49.0 <= result.pixels_per_cm <= 51.0
    assert result.confidence >= 0.95


def test_detect_aruco_10cm():
    img = make_aruco_image(canvas=(1200, 800), side_px=500)
    result = detect_reference_object(img, ReferenceType.ARUCO_10CM)
    assert result.status == "detected"
    assert 49.0 <= result.pixels_per_cm <= 51.0


def test_detect_aruco_missing():
    img = make_noise_image(seed=13)
    result = detect_reference_object(img, ReferenceType.ARUCO_4CM)
    assert result.status == "not_found"


from app.infrastructure.fish.reference_detector import BoundingBox


def test_tap_to_mark_coin():
    img = make_noise_image(seed=1)
    bbox = BoundingBox(x=10, y=20, width=100, height=100)
    result = detect_reference_object(
        img, ReferenceType.COIN_PHP_5, supplied_bbox=bbox
    )
    assert result.status == "client_supplied"
    assert result.pixels_per_cm == pytest.approx(40.0)
    assert result.bounding_box == bbox
    assert result.confidence == 1.0


def test_tap_to_mark_id_card_uses_long_side():
    img = make_noise_image(seed=2)
    bbox = BoundingBox(x=0, y=0, width=856, height=540)
    result = detect_reference_object(
        img, ReferenceType.ID_CARD, supplied_bbox=bbox
    )
    assert result.status == "client_supplied"
    assert result.pixels_per_cm == pytest.approx(100.0)


def test_tap_to_mark_manual_ignores_bbox():
    img = make_noise_image(seed=3)
    bbox = BoundingBox(x=0, y=0, width=100, height=100)
    result = detect_reference_object(
        img, ReferenceType.MANUAL, supplied_bbox=bbox
    )
    assert result.status == "manual"
    assert result.pixels_per_cm is None
