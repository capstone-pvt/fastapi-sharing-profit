from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal

import cv2
import numpy as np
from PIL import Image

from app.domain.fish.reference_types import (
    ReferenceType,
    is_circular,
    known_dimension_mm,
)
from app.infrastructure.fish.calibration import (
    pixels_per_cm_from_measurement,
)

logger = logging.getLogger(__name__)

_CARD_ASPECT_MIN, _CARD_ASPECT_MAX = 1.43, 1.74
_BILL_ASPECT_MIN, _BILL_ASPECT_MAX = 2.18, 2.67

DetectionStatus = Literal["detected", "not_found", "manual", "client_supplied"]


@dataclass(frozen=True)
class BoundingBox:
    x: float
    y: float
    width: float
    height: float

    def as_dict(self) -> dict:
        return {"x": self.x, "y": self.y, "width": self.width, "height": self.height}


@dataclass(frozen=True)
class ReferenceDetectionResult:
    status: DetectionStatus
    type: ReferenceType
    pixels_per_cm: float | None
    bounding_box: BoundingBox | None
    confidence: float

    def as_dict(self) -> dict:
        d: dict = {
            "status": self.status,
            "type": self.type.value,
            "pixelsPerCm": self.pixels_per_cm,
            "confidence": self.confidence,
        }
        if self.bounding_box is not None:
            d["boundingBox"] = self.bounding_box.as_dict()
        return d


def _pil_to_bgr(img: Image.Image) -> np.ndarray:
    rgb = np.array(img.convert("RGB"))
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)


_MIN_CIRCLE_CONTRAST = 10.0  # inner-vs-ring mean brightness diff; rejects noise FPs


def _circle_contrast(gray: np.ndarray, cx: float, cy: float, r: float) -> float:
    """Mean absolute brightness difference between the circle interior and the
    surrounding ring (0.7r–1.3r). High for real coins, near-zero for noise."""
    h, w = gray.shape
    mask_inner = np.zeros((h, w), dtype=np.uint8)
    mask_outer = np.zeros((h, w), dtype=np.uint8)
    cv2.circle(mask_inner, (int(cx), int(cy)), max(1, int(r * 0.7)), 255, -1)
    cv2.circle(mask_outer, (int(cx), int(cy)), max(1, int(r * 1.3)), 255, -1)
    mask_ring = cv2.subtract(mask_outer, mask_inner)
    inner_vals = gray[mask_inner > 0]
    ring_vals = gray[mask_ring > 0]
    if len(inner_vals) == 0 or len(ring_vals) == 0:
        return 0.0
    return float(abs(np.mean(inner_vals) - np.mean(ring_vals)))


def _detect_coin(img: Image.Image, ref_type: ReferenceType) -> ReferenceDetectionResult:
    bgr = _pil_to_bgr(img)
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    gray = cv2.medianBlur(gray, 5)
    h, w = gray.shape
    circles = cv2.HoughCircles(
        gray, cv2.HOUGH_GRADIENT, dp=1.2,
        minDist=max(w // 4, 10),
        param1=100, param2=30,
        minRadius=max(w // 40, 5),
        maxRadius=max(w // 4, 10),
    )
    if circles is None or len(circles[0]) == 0:
        return ReferenceDetectionResult(
            status="not_found", type=ref_type,
            pixels_per_cm=None, bounding_box=None, confidence=0.0,
        )
    # Filter candidates by contrast quality to reject noise false positives
    best = None
    best_contrast = 0.0
    for candidate in circles[0]:
        cx, cy, r = candidate
        contrast = _circle_contrast(gray, cx, cy, r)
        if contrast >= _MIN_CIRCLE_CONTRAST and contrast > best_contrast:
            best = candidate
            best_contrast = contrast
    if best is None:
        return ReferenceDetectionResult(
            status="not_found", type=ref_type,
            pixels_per_cm=None, bounding_box=None, confidence=0.0,
        )
    cx, cy, r = best
    diameter_px = float(2 * r)
    pix_per_cm = pixels_per_cm_from_measurement(
        measured_px=diameter_px, ref_type=ref_type
    )
    bbox = BoundingBox(
        x=float(cx - r), y=float(cy - r),
        width=diameter_px, height=diameter_px,
    )
    confidence = min(1.0, 0.5 + 0.1 * len(circles[0]))
    return ReferenceDetectionResult(
        status="detected", type=ref_type,
        pixels_per_cm=pix_per_cm, bounding_box=bbox, confidence=confidence,
    )


def _detect_rect_reference(
    img: Image.Image, ref_type: ReferenceType,
    aspect_min: float, aspect_max: float,
) -> ReferenceDetectionResult:
    bgr = _pil_to_bgr(img)
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(gray, 50, 150)
    contours, _ = cv2.findContours(
        edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )
    img_area = gray.shape[0] * gray.shape[1]

    best: tuple[float, tuple[float, float], tuple[float, float, float, float]] | None = None

    for contour in contours:
        peri = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, 0.02 * peri, True)
        if len(approx) != 4:
            continue
        rect = cv2.minAreaRect(contour)
        (rw, rh) = rect[1]
        if rw <= 0 or rh <= 0:
            continue
        area = rw * rh
        if area < 0.01 * img_area or area > 0.30 * img_area:
            continue
        long_px = max(rw, rh)
        short_px = min(rw, rh)
        aspect = long_px / short_px
        if not (aspect_min <= aspect <= aspect_max):
            continue
        box_pts = cv2.boxPoints(rect)
        xs = [p[0] for p in box_pts]
        ys = [p[1] for p in box_pts]
        bbox = (min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))
        centre = (aspect_min + aspect_max) / 2
        score = 1.0 - abs(aspect - centre) / centre
        if best is None or score > best[0]:
            best = (score, (long_px, short_px), bbox)

    if best is None:
        return ReferenceDetectionResult(
            status="not_found", type=ref_type,
            pixels_per_cm=None, bounding_box=None, confidence=0.0,
        )
    score, (long_px, _short_px), (bx, by, bw, bh) = best
    pix_per_cm = pixels_per_cm_from_measurement(
        measured_px=float(long_px), ref_type=ref_type
    )
    return ReferenceDetectionResult(
        status="detected", type=ref_type,
        pixels_per_cm=pix_per_cm,
        bounding_box=BoundingBox(x=float(bx), y=float(by), width=float(bw), height=float(bh)),
        confidence=max(0.5, min(1.0, score)),
    )


_ARUCO_DICT = None


def _get_aruco_detector():
    global _ARUCO_DICT
    if _ARUCO_DICT is None:
        _ARUCO_DICT = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    params = cv2.aruco.DetectorParameters()
    return cv2.aruco.ArucoDetector(_ARUCO_DICT, params)


def _detect_aruco(img: Image.Image, ref_type: ReferenceType) -> ReferenceDetectionResult:
    bgr = _pil_to_bgr(img)
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    detector = _get_aruco_detector()
    corners, ids, _ = detector.detectMarkers(gray)
    if ids is None or len(corners) == 0:
        return ReferenceDetectionResult(
            status="not_found", type=ref_type,
            pixels_per_cm=None, bounding_box=None, confidence=0.0,
        )
    quad = corners[0][0]
    sides = [
        float(np.linalg.norm(quad[(i + 1) % 4] - quad[i])) for i in range(4)
    ]
    side_px = float(sum(sides) / 4.0)
    pix_per_cm = pixels_per_cm_from_measurement(
        measured_px=side_px, ref_type=ref_type
    )
    xs = quad[:, 0]
    ys = quad[:, 1]
    bbox = BoundingBox(
        x=float(xs.min()), y=float(ys.min()),
        width=float(xs.max() - xs.min()),
        height=float(ys.max() - ys.min()),
    )
    return ReferenceDetectionResult(
        status="detected", type=ref_type,
        pixels_per_cm=pix_per_cm, bounding_box=bbox, confidence=0.99,
    )


def _from_supplied_bbox(
    bbox: BoundingBox, ref_type: ReferenceType,
) -> ReferenceDetectionResult:
    long_px = max(bbox.width, bbox.height)
    pix_per_cm = pixels_per_cm_from_measurement(
        measured_px=long_px, ref_type=ref_type
    )
    return ReferenceDetectionResult(
        status="client_supplied", type=ref_type,
        pixels_per_cm=pix_per_cm, bounding_box=bbox, confidence=1.0,
    )


def detect_reference_object(
    img: Image.Image,
    ref_type: ReferenceType,
    supplied_bbox: BoundingBox | None = None,
) -> ReferenceDetectionResult:
    """Dispatch reference detection by type."""
    if ref_type == ReferenceType.MANUAL:
        return ReferenceDetectionResult(
            status="manual", type=ref_type,
            pixels_per_cm=None, bounding_box=None, confidence=1.0,
        )
    if supplied_bbox is not None:
        return _from_supplied_bbox(supplied_bbox, ref_type)
    if is_circular(ref_type):
        return _detect_coin(img, ref_type)
    if ref_type == ReferenceType.ID_CARD:
        return _detect_rect_reference(
            img, ref_type, _CARD_ASPECT_MIN, _CARD_ASPECT_MAX
        )
    if ref_type == ReferenceType.BILL_PHP:
        return _detect_rect_reference(
            img, ref_type, _BILL_ASPECT_MIN, _BILL_ASPECT_MAX
        )
    if ref_type in (ReferenceType.ARUCO_4CM, ReferenceType.ARUCO_10CM):
        return _detect_aruco(img, ref_type)
    raise NotImplementedError(f"detection for {ref_type.value} not yet implemented")
