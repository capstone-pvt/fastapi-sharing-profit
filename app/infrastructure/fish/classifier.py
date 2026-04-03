from __future__ import annotations

import logging
import traceback
from typing import Any

from PIL import Image, ImageOps

from app.infrastructure.fish.model_loader import _load_classifier

logger = logging.getLogger(__name__)


def _classify_single(classifier, pil_image: Image.Image) -> dict[str, float]:
    """Run classifier on a single image, return {species: confidence} map."""
    results = classifier.predict(pil_image, verbose=False)
    if not results:
        return {}
    result = results[0]
    if not (hasattr(result, "names") and hasattr(result, "probs")):
        return {}
    probs = result.probs.data.cpu().numpy()
    names = result.names
    return {names.get(i, f"class_{i}"): float(probs[i]) for i in range(len(probs))}


def classify_fish(pil_image: Image.Image, *, use_tta: bool = True) -> tuple[str, float]:
    """Classify fish species with optional Test-Time Augmentation.

    TTA runs inference on original + horizontally flipped image and averages
    the probability distributions. This improves robustness to fish orientation.
    """
    classifier = _load_classifier()
    if classifier is None:
        return "Unknown", 0.0
    try:
        probs_original = _classify_single(classifier, pil_image)
        if not probs_original:
            return "Unknown", 0.0

        if use_tta:
            # Horizontal flip (fish can face either direction)
            flipped = ImageOps.mirror(pil_image)
            probs_flipped = _classify_single(classifier, flipped)

            # Average probabilities across augmentations
            all_species = set(probs_original) | set(probs_flipped)
            probs_avg = {
                sp: (probs_original.get(sp, 0.0) + probs_flipped.get(sp, 0.0)) / 2.0
                for sp in all_species
            }
        else:
            probs_avg = probs_original

        best_species = max(probs_avg, key=probs_avg.get)
        best_conf = probs_avg[best_species]
        return best_species, best_conf

    except Exception as e:
        logger.error("Error in classify_fish prediction: %s", e)
        traceback.print_exc()
        return "Unknown", 0.0


def classify_fish_top_n(
    pil_image: Image.Image, *, n: int = 3, use_tta: bool = True
) -> list[dict[str, Any]]:
    """Return top-N species predictions with confidence scores."""
    classifier = _load_classifier()
    if classifier is None:
        return [{"species": "Unknown", "confidence": 0.0}]
    try:
        probs_original = _classify_single(classifier, pil_image)
        if not probs_original:
            return [{"species": "Unknown", "confidence": 0.0}]

        if use_tta:
            flipped = ImageOps.mirror(pil_image)
            probs_flipped = _classify_single(classifier, flipped)
            all_species = set(probs_original) | set(probs_flipped)
            probs_avg = {
                sp: (probs_original.get(sp, 0.0) + probs_flipped.get(sp, 0.0)) / 2.0
                for sp in all_species
            }
        else:
            probs_avg = probs_original

        sorted_preds = sorted(probs_avg.items(), key=lambda x: x[1], reverse=True)[:n]
        return [{"species": sp, "confidence": round(conf, 4)} for sp, conf in sorted_preds]
    except Exception:
        logger.exception("Error in classify_fish_top_n")
        return [{"species": "Unknown", "confidence": 0.0}]
