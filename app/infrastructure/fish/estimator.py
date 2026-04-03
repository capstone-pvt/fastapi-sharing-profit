from __future__ import annotations

import logging

import numpy as np

from app.infrastructure.fish.model_loader import (
    WEIGHT_MODEL_EXPECTED_FEATURES,
    _load_price_model,
    _load_weight_model,
)

logger = logging.getLogger(__name__)


def estimate_weight(
    species_index: int,
    width: float,
    height: float,
    scale_reference_cm: float | None,
    length_cm: float | None,
    width_cm: float | None,
) -> float:
    """Estimate fish weight in kg from bounding-box dimensions and species index.

    Falls back to a naive pixel-area heuristic when the model is unavailable
    or the feature vector shape does not match the trained model.
    """
    weight_model = _load_weight_model()
    if weight_model is not None:
        w = float(width)
        h = float(height)
        sr = float(scale_reference_cm or 0)
        lc = float(length_cm or 0)
        wc = float(width_cm or 0)

        # Base features
        base = [species_index, w, h, sr, lc, wc]

        # Engineered features (must match train_regression_models.py)
        area = w * h
        aspect = w / max(h, 1.0) if h > 0 else 1.0
        area_cm = lc * wc

        features = np.array([base + [area, aspect, area_cm]], dtype=float)

        # Validate feature count before predict to produce an actionable error
        # instead of a cryptic sklearn shape mismatch buried in a silent except.
        if features.shape[1] != WEIGHT_MODEL_EXPECTED_FEATURES:
            logger.error(
                "estimate_weight: feature vector has %d columns but "
                "WEIGHT_MODEL_EXPECTED_FEATURES=%d. "
                "The model file is likely stale — retrain with the current "
                "train_regression_models.py and replace weight_model.joblib.",
                features.shape[1],
                WEIGHT_MODEL_EXPECTED_FEATURES,
            )
            return float(width * height) * 0.000001

        try:
            prediction = float(weight_model.predict(features)[0])
            return max(0.0, prediction)
        except Exception as exc:
            logger.exception("estimate_weight: model.predict() failed: %s", exc)

    return float(width * height) * 0.000001


def estimate_price(species_index: int, estimated_weight: float) -> float:
    """Estimate total price for a fish given species and estimated weight.

    Falls back to a flat rate of 8.5 per kg when the model is unavailable.
    """
    price_model = _load_price_model()
    if price_model is not None:
        try:
            price_per_kg = float(
                price_model.predict(
                    np.array([[species_index, estimated_weight]], dtype=float)
                )[0]
            )
            return max(0.0, price_per_kg * estimated_weight)
        except Exception as exc:
            logger.exception("estimate_price: model.predict() failed: %s", exc)
    return estimated_weight * 8.5
