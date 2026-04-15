from __future__ import annotations

from app.domain.fish.reference_types import ReferenceType, known_dimension_mm


def pixels_per_cm_from_measurement(
    *, measured_px: float, ref_type: ReferenceType
) -> float:
    """Given the measured pixel length of a reference object's dominant
    dimension, return pixels-per-cm using the known real-world size.
    """
    if measured_px <= 0:
        raise ValueError("measured_px must be > 0")
    known_cm = known_dimension_mm(ref_type) / 10.0  # raises on MANUAL
    return measured_px / known_cm


def bbox_to_cm(
    *,
    bbox_width_px: float,
    bbox_height_px: float,
    pixels_per_cm: float,
) -> tuple[float, float]:
    """Convert a bounding box to (length_cm, width_cm). The longer side is
    treated as the length; the shorter as the width.
    """
    if pixels_per_cm <= 0:
        raise ValueError("pixels_per_cm must be > 0")
    longer = max(bbox_width_px, bbox_height_px)
    shorter = min(bbox_width_px, bbox_height_px)
    return (longer / pixels_per_cm, shorter / pixels_per_cm)
