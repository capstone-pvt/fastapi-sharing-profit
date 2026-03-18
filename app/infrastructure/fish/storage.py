from __future__ import annotations

import uuid
from pathlib import Path

from app.core.config import get_settings


def save_upload(image_bytes: bytes, file_name: str) -> str:
    settings = get_settings()
    if settings.storage_backend == "cloudinary":
        return _save_to_cloudinary(image_bytes, file_name)
    return _save_to_local(image_bytes, file_name)


def _save_to_local(image_bytes: bytes, file_name: str) -> str:
    settings = get_settings()
    root = Path(settings.upload_root) / "fish"
    root.mkdir(parents=True, exist_ok=True)
    ext = Path(file_name).suffix or ".jpg"
    unique_name = f"{uuid.uuid4().hex}{ext}"
    target = root / unique_name
    target.write_bytes(image_bytes)
    return f"/uploads/fish/{unique_name}"


def _save_to_cloudinary(image_bytes: bytes, file_name: str) -> str:
    import cloudinary
    import cloudinary.uploader

    settings = get_settings()
    if settings.cloudinary_url:
        cloudinary.config(cloudinary_url=settings.cloudinary_url)
    ext = Path(file_name).suffix or ".jpg"
    public_id = f"fish/{uuid.uuid4().hex}"
    result = cloudinary.uploader.upload(
        image_bytes,
        public_id=public_id,
        resource_type="image",
        format=ext.lstrip("."),
    )
    return result["secure_url"]
