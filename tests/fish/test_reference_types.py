import pytest
from app.domain.fish.reference_types import (
    ReferenceType,
    known_dimension_mm,
    is_circular,
)


def test_enum_values_match_api_strings():
    assert ReferenceType.MANUAL.value == "manual"
    assert ReferenceType.COIN_PHP_1.value == "coin_php_1"
    assert ReferenceType.COIN_PHP_5.value == "coin_php_5"
    assert ReferenceType.COIN_PHP_10.value == "coin_php_10"
    assert ReferenceType.ID_CARD.value == "id_card"
    assert ReferenceType.BILL_PHP.value == "bill_php"
    assert ReferenceType.ARUCO_4CM.value == "aruco_4cm"
    assert ReferenceType.ARUCO_10CM.value == "aruco_10cm"


def test_known_dimension_mm_per_type():
    assert known_dimension_mm(ReferenceType.COIN_PHP_1) == 20.0
    assert known_dimension_mm(ReferenceType.COIN_PHP_5) == 25.0
    assert known_dimension_mm(ReferenceType.COIN_PHP_10) == 26.5
    assert known_dimension_mm(ReferenceType.ID_CARD) == 85.6
    assert known_dimension_mm(ReferenceType.BILL_PHP) == 160.0
    assert known_dimension_mm(ReferenceType.ARUCO_4CM) == 40.0
    assert known_dimension_mm(ReferenceType.ARUCO_10CM) == 100.0


def test_known_dimension_mm_manual_raises():
    with pytest.raises(ValueError):
        known_dimension_mm(ReferenceType.MANUAL)


def test_is_circular():
    assert is_circular(ReferenceType.COIN_PHP_1) is True
    assert is_circular(ReferenceType.COIN_PHP_5) is True
    assert is_circular(ReferenceType.COIN_PHP_10) is True
    assert is_circular(ReferenceType.ID_CARD) is False
    assert is_circular(ReferenceType.BILL_PHP) is False
    assert is_circular(ReferenceType.ARUCO_4CM) is False


def test_from_string_unknown_raises():
    with pytest.raises(ValueError):
        ReferenceType("not_a_type")
