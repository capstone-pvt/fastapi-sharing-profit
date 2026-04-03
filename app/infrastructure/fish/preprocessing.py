from __future__ import annotations

import logging

from PIL import Image, ImageEnhance, ImageOps

from app.infrastructure.fish.model_loader import CROP_PADDING

logger = logging.getLogger(__name__)


def preprocess_image(pil_image: Image.Image) -> Image.Image:
    """Preprocess image for improved model accuracy.

    - Auto-orient using EXIF data (handles phone camera rotations)
    - Enhance sharpness and contrast for clearer features
    - Ensure RGB mode
    """
    img = ImageOps.exif_transpose(pil_image)
    if img is None:
        img = pil_image
    img = img.convert("RGB")

    # Mild sharpness boost helps models pick up fin/scale details
    img = ImageEnhance.Sharpness(img).enhance(1.3)
    # Mild contrast boost helps in low-light underwater/market photos
    img = ImageEnhance.Contrast(img).enhance(1.1)

    return img


def _crop_detection(pil_image: Image.Image, bbox: dict) -> Image.Image | None:
    """Crop a detection region from the image with padding for classifier input."""
    img_w, img_h = pil_image.size
    x = float(bbox.get("x", 0))
    y = float(bbox.get("y", 0))
    w = float(bbox.get("width", 0))
    h = float(bbox.get("height", 0))

    if w <= 0 or h <= 0:
        return None

    # Add padding around the bounding box
    pad_x = w * CROP_PADDING
    pad_y = h * CROP_PADDING
    x1 = max(0, x - pad_x)
    y1 = max(0, y - pad_y)
    x2 = min(img_w, x + w + pad_x)
    y2 = min(img_h, y + h + pad_y)

    cropped = pil_image.crop((x1, y1, x2, y2))
    # Ensure minimum size for classifier
    if cropped.width < 32 or cropped.height < 32:
        return None
    return cropped
