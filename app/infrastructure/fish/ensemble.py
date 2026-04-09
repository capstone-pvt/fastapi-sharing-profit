from __future__ import annotations

import logging
from typing import Any

from PIL import Image

from app.infrastructure.fish.classifier import classify_fish
from app.infrastructure.fish.model_loader import (
    ENSEMBLE_CONFIDENCE_THRESHOLD,
    _load_classifier,
)
from app.infrastructure.fish.preprocessing import _crop_detection

logger = logging.getLogger(__name__)

# Ensemble weighting — configurable via environment or constants.
# Detector (YOLO object detection) provides spatial localization; classifier
# (YOLO classification) provides species-level accuracy.  The weights
# reflect the relative reliability of each model's confidence score.
import os

DETECTOR_WEIGHT = float(os.getenv("ENSEMBLE_DETECTOR_WEIGHT", "0.6"))
CLASSIFIER_WEIGHT = float(os.getenv("ENSEMBLE_CLASSIFIER_WEIGHT", "0.4"))
AGREEMENT_BOOST = float(os.getenv("ENSEMBLE_AGREEMENT_BOOST", "1.1"))


def verify_detections_with_classifier(
    pil_image: Image.Image,
    detections: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """For each detection, crop the region and run classifier to verify/improve
    the species prediction. Uses confidence-weighted ensemble when detector
    confidence is below threshold.

    This is the key accuracy improvement: the detector finds WHERE fish are,
    and the classifier (specialized for species) confirms WHAT species they are.
    """
    classifier = _load_classifier()
    if classifier is None:
        return detections

    verified: list[dict[str, Any]] = []
    for det in detections:
        bbox = det.get("boundingBox", {})
        detector_species = det.get("species", "Unknown")
        detector_conf = det.get("confidence", 0.0)

        cropped = _crop_detection(pil_image, bbox)
        if cropped is None:
            # Can't crop — keep detector result as-is
            det["verificationMethod"] = "detector_only"
            verified.append(det)
            continue

        # Classify the cropped region with TTA
        cls_species, cls_conf = classify_fish(cropped, use_tta=True)

        if detector_conf >= ENSEMBLE_CONFIDENCE_THRESHOLD:
            # High detector confidence — trust detector, but record classifier result
            det["classifierSpecies"] = cls_species
            det["classifierConfidence"] = round(cls_conf, 4)
            det["verificationMethod"] = "detector_high_confidence"
            verified.append(det)
        else:
            # Low detector confidence — use classifier if it's more confident
            if cls_conf > detector_conf and cls_species != "Unknown":
                det["species"] = cls_species
                det["confidence"] = round(cls_conf, 4)
                det["classifierSpecies"] = cls_species
                det["classifierConfidence"] = round(cls_conf, 4)
                det["verificationMethod"] = "classifier_override"
                logger.info(
                    "Classifier override for det %s: %s(%.2f) -> %s(%.2f)",
                    det["id"],
                    detector_species,
                    detector_conf,
                    cls_species,
                    cls_conf,
                )
            else:
                # Weighted average of detector and classifier confidence.
                # Detector weight is higher (0.6) because it provides spatial
                # localization (bounding box); classifier (0.4) verifies the
                # species label.  When both models agree, a 10% boost rewards
                # the higher certainty of consensus.
                combined_conf = detector_conf * DETECTOR_WEIGHT + cls_conf * CLASSIFIER_WEIGHT
                if cls_species == detector_species:
                    # Both agree — boost confidence
                    det["confidence"] = round(min(combined_conf * AGREEMENT_BOOST, 1.0), 4)
                    det["verificationMethod"] = "ensemble_agreement"
                else:
                    det["classifierSpecies"] = cls_species
                    det["classifierConfidence"] = round(cls_conf, 4)
                    det["verificationMethod"] = "detector_preferred"

            verified.append(det)

    return verified
