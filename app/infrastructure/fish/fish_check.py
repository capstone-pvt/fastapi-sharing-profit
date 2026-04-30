"""Server-side guard: does this image actually contain a fish?

Used by `/fish/training-samples` to block non-fish images from poisoning
the training set. Lighter than `/fish/analyze` — runs only the detector
+ a single classifier pass, skips the cm-scaling math.
"""

from __future__ import annotations

import logging
from io import BytesIO

from PIL import Image

from app.core.config import get_settings
from app.infrastructure.fish.classifier import classify_fish
from app.infrastructure.fish.detector import detect_fish
from app.infrastructure.fish.preprocessing import preprocess_image

logger = logging.getLogger(__name__)


# Stricter than /fish/analyze — we're rejecting the upload, not just warning.
# Detector noise can hallucinate boxes on uniform/random images; require both
# a high-confidence detector box AND a confident classifier pick to accept.
_DETECTOR_MIN_CONFIDENCE = 0.50
_FULL_IMAGE_MIN_CONFIDENCE = 0.55
_CLASSIFIER_AGREEMENT_MIN_CONFIDENCE = 0.40


def is_fish_image(image_bytes: bytes) -> tuple[bool, str]:
    """Return (looks_like_fish, reason).

    `reason` is a short string suitable for an HTTP 422 detail. Returns
    (True, "ok") in the happy path so callers can `if ok: ...` cleanly.

    Decision logic:
      1. Detector returns at least one box with conf ≥ 0.50 AND the
         full-image classifier agrees with conf ≥ 0.40 → accept.
      2. Detector returns nothing — fall back to the classifier alone with
         a stricter conf ≥ 0.55. The classifier is forced to pick one of the
         5 trained species, so low confidence is the only "this isn't really
         a fish" signal we have without a dedicated yes/no head.
      3. Otherwise reject.

    Errors (model missing, decode failure on garbage bytes) → conservatively
    allow through; existing routes already accept anything when models are
    absent and we don't want to brick local dev / first-boot.
    """
    try:
        pil = Image.open(BytesIO(image_bytes)).convert("RGB")
    except Exception as exc:
        logger.info("is_fish_image: cannot decode image: %s", exc)
        return False, "Image could not be decoded."

    try:
        prepared = preprocess_image(pil)
    except Exception:
        prepared = pil

    settings = get_settings()
    try:
        detections = detect_fish(
            prepared,
            confidence=settings.detector_confidence,
            iou=settings.detector_iou,
        )
    except Exception as exc:
        logger.info("is_fish_image: detector failed (%s); allowing through", exc)
        return True, "ok"

    # Single classifier pass on the whole image — used by both branches.
    try:
        cls_species, cls_confidence = classify_fish(prepared, use_tta=False)
    except Exception as exc:
        logger.info("is_fish_image: classifier failed (%s); allowing through", exc)
        return True, "ok"

    if detections:
        # Detector found something — accept only if the detector is confident
        # AND the classifier agrees this is a known species (filters out
        # YOLO hallucinations on noise / textures / unrelated objects).
        top_det_conf = max((d.get("confidence", 0.0) for d in detections), default=0.0)
        if (
            top_det_conf >= _DETECTOR_MIN_CONFIDENCE
            and cls_species
            and cls_species != "Unknown"
            and cls_confidence >= _CLASSIFIER_AGREEMENT_MIN_CONFIDENCE
        ):
            return True, "ok"
        # Else fall through to reject — detector probably hallucinated.

    elif (
        cls_species
        and cls_species != "Unknown"
        and cls_confidence >= _FULL_IMAGE_MIN_CONFIDENCE
    ):
        # No detector box but the classifier is highly confident on its own.
        return True, "ok"

    return (
        False,
        "This image doesn't look like a fish. "
        "Please re-capture with a clear, well-lit photo of a single fish.",
    )
