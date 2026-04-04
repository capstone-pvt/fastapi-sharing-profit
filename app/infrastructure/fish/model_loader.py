from __future__ import annotations

import gc
import logging
import os

import joblib

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Number of features the weight model must accept.
# Changing this constant requires retraining and redeploying the model file.
WEIGHT_MODEL_EXPECTED_FEATURES = 6

# Confidence threshold below which detector species is verified by classifier
ENSEMBLE_CONFIDENCE_THRESHOLD = 0.6

# Minimum detection confidence to keep (filters noise)
MIN_DETECTION_CONFIDENCE = 0.15

# Padding factor when cropping detections for classifier verification (% of bbox)
CROP_PADDING = 0.1

# ---------------------------------------------------------------------------
# Module-level model cache — intentionally mutable globals for lazy-loading
# ---------------------------------------------------------------------------

_classifier_model = None
_weight_model = None
_price_model = None
_detector_model = None


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

def _load_classifier():
    global _classifier_model
    if _classifier_model is not None:
        return _classifier_model
    settings = get_settings()
    if not settings.classifier_model_path:
        logger.warning("Classifier: CLASSIFIER_MODEL_PATH not configured in environment")
        return None
    try:
        from ultralytics import YOLO

        if not os.path.exists(settings.classifier_model_path):
            logger.error("Classifier: model file not found at: %s", settings.classifier_model_path)
            return None

        _classifier_model = YOLO(settings.classifier_model_path)
        logger.info("Classifier: model loaded from %s", settings.classifier_model_path)
        return _classifier_model
    except Exception as e:
        logger.error("Error loading classifier model: %s", e)
        return None


def _load_weight_model():
    global _weight_model
    if _weight_model is not None:
        return _weight_model
    settings = get_settings()
    if not settings.weight_model_path:
        logger.warning("Weight model: WEIGHT_MODEL_PATH not configured in environment")
        return None
    try:
        if not os.path.exists(settings.weight_model_path):
            logger.error("Weight model: file not found at: %s", settings.weight_model_path)
            return None

        _weight_model = joblib.load(settings.weight_model_path)
        logger.info("Weight model: loaded from %s", settings.weight_model_path)
        return _weight_model
    except Exception as e:
        logger.error("Error loading weight model: %s", e)
        return None


def _load_price_model():
    global _price_model
    if _price_model is not None:
        return _price_model
    settings = get_settings()
    if not settings.price_model_path:
        logger.warning("Price model: PRICE_MODEL_PATH not configured in environment")
        return None
    try:
        if not os.path.exists(settings.price_model_path):
            logger.error("Price model: file not found at: %s", settings.price_model_path)
            return None

        _price_model = joblib.load(settings.price_model_path)
        logger.info("Price model: loaded from %s", settings.price_model_path)
        return _price_model
    except Exception as e:
        logger.error("Error loading price model: %s", e)
        return None


def _load_detector():
    global _detector_model
    if _detector_model is not None:
        return _detector_model
    settings = get_settings()
    if not settings.detector_model_path:
        logger.warning("Detector: DETECTOR_MODEL_PATH not configured in environment")
        return None
    try:
        from ultralytics import YOLO

        if not os.path.exists(settings.detector_model_path):
            logger.error("Detector: model file not found at: %s", settings.detector_model_path)
            return None

        _detector_model = YOLO(settings.detector_model_path)
        logger.info("Detector: model loaded from %s", settings.detector_model_path)
        return _detector_model
    except Exception as e:
        logger.error("Error loading detector model: %s", e)
        return None


# ---------------------------------------------------------------------------
# Preloading
# ---------------------------------------------------------------------------

def preload_models() -> dict[str, bool]:
    """Eagerly load all ML models. Returns a status dict.

    Set PRELOAD_MODELS=false to skip preloading (lazy-load on first request).
    This reduces startup memory on constrained plans like Render starter.
    """
    if os.getenv("PRELOAD_MODELS", "true").lower() == "false":
        logger.info("PRELOAD_MODELS=false -- models will lazy-load on first request")
        return {}

    status: dict[str, bool] = {}
    for name, loader in [
        ("detector", _load_detector),
        ("classifier", _load_classifier),
        ("weight", _load_weight_model),
        ("price", _load_price_model),
    ]:
        try:
            model = loader()
            status[name] = model is not None
            if model is None:
                logger.warning("Preload: %s model returned None", name)
        except Exception as e:
            status[name] = False
            logger.error("Error preloading %s model: %s", name, e)

    gc.collect()
    logger.info("Model preload status: %s", status)
    return status
