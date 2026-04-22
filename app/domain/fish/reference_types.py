from __future__ import annotations

from enum import Enum


class ReferenceType(str, Enum):
    MANUAL = "manual"
    COIN_PHP_1 = "coin_php_1"
    COIN_PHP_5 = "coin_php_5"
    COIN_PHP_10 = "coin_php_10"
    COIN_PHP_20 = "coin_php_20"
    ID_CARD = "id_card"
    BILL_PHP = "bill_php"
    ARUCO_4CM = "aruco_4cm"
    ARUCO_10CM = "aruco_10cm"


# Dominant real-world dimension in millimetres.
# Coins: diameter. Card/bill: long side. Marker: side length.
_KNOWN_DIMENSION_MM: dict[ReferenceType, float] = {
    ReferenceType.COIN_PHP_1: 20.0,
    ReferenceType.COIN_PHP_5: 25.0,
    ReferenceType.COIN_PHP_10: 26.5,
    ReferenceType.COIN_PHP_20: 30.0,
    ReferenceType.ID_CARD: 85.6,
    ReferenceType.BILL_PHP: 160.0,
    ReferenceType.ARUCO_4CM: 40.0,
    ReferenceType.ARUCO_10CM: 100.0,
}


def known_dimension_mm(ref_type: ReferenceType) -> float:
    if ref_type == ReferenceType.MANUAL:
        raise ValueError("manual reference has no known dimension")
    return _KNOWN_DIMENSION_MM[ref_type]


_CIRCULAR_TYPES = {
    ReferenceType.COIN_PHP_1,
    ReferenceType.COIN_PHP_5,
    ReferenceType.COIN_PHP_10,
    ReferenceType.COIN_PHP_20,
}


def is_circular(ref_type: ReferenceType) -> bool:
    return ref_type in _CIRCULAR_TYPES
