from __future__ import annotations

import logging
import traceback
from typing import Any

from PIL import Image

from app.core.config import get_settings
from app.infrastructure.fish.model_loader import MIN_DETECTION_CONFIDENCE, _load_detector

logger = logging.getLogger(__name__)


def detect_fish(
    pil_image: Image.Image,
    *,
    confidence: float | None,
    iou: float | None,
) -> list[dict[str, Any]]:
    """Detect fish in the image and return bounding-box annotations.

    Returns an empty list when the detector is unavailable or inference fails.
    Results are sorted by confidence descending.
    """
    detections: list[dict[str, Any]] = []
    detector = _load_detector()
    if detector is None:
        return detections
    try:
        settings = get_settings()
        conf_threshold = confidence if confidence is not None else settings.detector_confidence
        iou_threshold = iou if iou is not None else settings.detector_iou

        # Run detector with augmented inference for better accuracy
        results = detector.predict(
            pil_image,
            verbose=False,
            conf=conf_threshold,
            iou=iou_threshold,
            augment=True,  # Enable built-in YOLO test-time augmentation
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

                # Filter out very low confidence noise
                if conf_value < MIN_DETECTION_CONFIDENCE:
                    continue

                detections.append(
                    {
                        "id": f"det_{idx}",
                        "species": species,
                        "confidence": conf_value,
                        "detectorConfidence": conf_value,
                        "boundingBox": {
                            "x": float(x1),
                            "y": float(y1),
                            "width": float(bbox_width),
                            "height": float(bbox_height),
                        },
                    }
                )

        # Sort by confidence descending (highest confidence first)
        detections.sort(key=lambda d: d["confidence"], reverse=True)

    except Exception as e:
        logger.error("Error in detect_fish prediction: %s", e)
        traceback.print_exc()
        return []
    return detections
