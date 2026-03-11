from __future__ import annotations

from typing import Any

import joblib
import numpy as np

from app.core.config import get_settings

_classifier_model = None
_weight_model = None
_price_model = None
_detector_model = None


def _load_classifier():
    global _classifier_model
    if _classifier_model is not None:
        return _classifier_model
    settings = get_settings()
    if not settings.classifier_model_path:
        print("WARNING: CLASSIFIER_MODEL_PATH not configured in environment")
        return None
    try:
        from ultralytics import YOLO
        import os

        if not os.path.exists(settings.classifier_model_path):
            print(f"ERROR: Classifier model file not found at: {settings.classifier_model_path}")
            return None

        _classifier_model = YOLO(settings.classifier_model_path)
        print(f"SUCCESS: Classifier model loaded from {settings.classifier_model_path}")
        return _classifier_model
    except Exception as e:
        print(f"ERROR loading classifier model: {str(e)}")
        return None


def _load_weight_model():
    global _weight_model
    if _weight_model is not None:
        return _weight_model
    settings = get_settings()
    if not settings.weight_model_path:
        print("WARNING: WEIGHT_MODEL_PATH not configured in environment")
        return None
    try:
        import os

        if not os.path.exists(settings.weight_model_path):
            print(f"ERROR: Weight model file not found at: {settings.weight_model_path}")
            return None

        _weight_model = joblib.load(settings.weight_model_path)
        print(f"SUCCESS: Weight model loaded from {settings.weight_model_path}")
        return _weight_model
    except Exception as e:
        print(f"ERROR loading weight model: {str(e)}")
        return None


def _load_price_model():
    global _price_model
    if _price_model is not None:
        return _price_model
    settings = get_settings()
    if not settings.price_model_path:
        print("WARNING: PRICE_MODEL_PATH not configured in environment")
        return None
    try:
        import os

        if not os.path.exists(settings.price_model_path):
            print(f"ERROR: Price model file not found at: {settings.price_model_path}")
            return None

        _price_model = joblib.load(settings.price_model_path)
        print(f"SUCCESS: Price model loaded from {settings.price_model_path}")
        return _price_model
    except Exception as e:
        print(f"ERROR loading price model: {str(e)}")
        return None


def _load_detector():
    global _detector_model
    if _detector_model is not None:
        return _detector_model
    settings = get_settings()
    if not settings.detector_model_path:
        print("WARNING: DETECTOR_MODEL_PATH not configured in environment")
        return None
    try:
        from ultralytics import YOLO
        import os

        if not os.path.exists(settings.detector_model_path):
            print(f"ERROR: Detector model file not found at: {settings.detector_model_path}")
            return None

        _detector_model = YOLO(settings.detector_model_path)
        print(f"SUCCESS: Detector model loaded from {settings.detector_model_path}")
        return _detector_model
    except Exception as e:
        print(f"ERROR loading detector model: {str(e)}")
        return None


def detect_fish(
    pil_image,
    *,
    confidence: float | None,
    iou: float | None,
) -> list[dict[str, Any]]:
    detections: list[dict[str, Any]] = []
    detector = _load_detector()
    if detector is None:
        return detections
    try:
        settings = get_settings()
        results = detector.predict(
            pil_image,
            verbose=False,
            conf=confidence if confidence is not None else settings.detector_confidence,
            iou=iou if iou is not None else settings.detector_iou,
        )
        if results:
            result = results[0]
            names = result.names if hasattr(result, "names") else {}
            for idx, box in enumerate(result.boxes):
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                conf_value = float(box.conf[0]) if box.conf is not None else 0.0
                cls_idx = int(box.cls[0]) if box.cls is not None else 0
                species = names.get(cls_idx, "Unknown")
                bbox_width = max(0.0, x2 - x1)
                bbox_height = max(0.0, y2 - y1)
                detections.append(
                    {
                        "id": f"det_{idx}",
                        "species": species,
                        "confidence": conf_value,
                        "boundingBox": {
                            "x": float(x1),
                            "y": float(y1),
                            "width": float(bbox_width),
                            "height": float(bbox_height),
                        },
                    }
                )
    except Exception as e:
        import traceback
        print(f"ERROR in detect_fish prediction: {e}")
        traceback.print_exc()
        return []
    return detections


def classify_fish(pil_image) -> tuple[str, float]:
    classifier = _load_classifier()
    if classifier is None:
        return "Unknown", 0.0
    try:
        results = classifier.predict(pil_image, verbose=False)
        if results:
            result = results[0]
            if hasattr(result, "names") and hasattr(result, "probs"):
                top_idx = int(result.probs.top1)
                species = result.names.get(top_idx, "Unknown")
                confidence = float(result.probs.top1conf)
                return species, confidence
    except Exception as e:
        import traceback
        print(f"ERROR in classify_fish prediction: {e}")
        traceback.print_exc()
        return "Unknown", 0.0
    return "Unknown", 0.0


def estimate_weight(
    species_index: int,
    width: float,
    height: float,
    scale_reference_cm: float | None,
    length_cm: float | None,
    width_cm: float | None,
) -> float:
    weight_model = _load_weight_model()
    if weight_model is not None:
        features = np.array(
            [
                [
                    species_index,
                    float(width),
                    float(height),
                    float(scale_reference_cm or 0),
                    float(length_cm or 0),
                    float(width_cm or 0),
                ]
            ],
            dtype=float,
        )
        try:
            return float(weight_model.predict(features)[0])
        except Exception:
            pass
    return float(width * height) * 0.000001


def preload_models() -> dict[str, bool]:
    """Eagerly load all ML models. Returns a status dict."""
    status = {}
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
                print(f"WARNING: {name} model returned None")
        except Exception as e:
            status[name] = False
            print(f"ERROR preloading {name} model: {e}")
    print(f"Model preload status: {status}")
    return status


def estimate_price(species_index: int, estimated_weight: float) -> float:
    price_model = _load_price_model()
    if price_model is not None:
        try:
            price_per_kg = float(
                price_model.predict(
                    np.array([[species_index, estimated_weight]], dtype=float)
                )[0]
            )
            return price_per_kg * estimated_weight
        except Exception:
            pass
    return estimated_weight * 8.5
