# Re-export all public APIs for backward compatibility.
# Implementation has been split into focused modules under app/infrastructure/fish/.
from app.infrastructure.fish.classifier import classify_fish, classify_fish_top_n
from app.infrastructure.fish.detector import detect_fish
from app.infrastructure.fish.ensemble import verify_detections_with_classifier
from app.infrastructure.fish.estimator import estimate_price, estimate_weight
from app.infrastructure.fish.model_loader import preload_models
from app.infrastructure.fish.preprocessing import preprocess_image

__all__ = [
    "preprocess_image",
    "preload_models",
    "classify_fish",
    "classify_fish_top_n",
    "detect_fish",
    "verify_detections_with_classifier",
    "estimate_weight",
    "estimate_price",
    "detect_reference_object",
    "build_bulk_summary",
    "ReferenceType",
    "ReferenceBoundingBox",
    "ReferenceDetectionResult",
]

from app.infrastructure.fish.reference_detector import (
    BoundingBox as ReferenceBoundingBox,
    ReferenceDetectionResult,
    detect_reference_object,
)
from app.domain.fish.bulk import build_bulk_summary
from app.domain.fish.reference_types import ReferenceType
