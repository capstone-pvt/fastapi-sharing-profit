from __future__ import annotations

from pathlib import Path

from app.core.config import get_settings


def save_upload(image_bytes: bytes, file_name: str) -> str:
    settings = get_settings()
    root = Path(settings.upload_root) / "fish"
    root.mkdir(parents=True, exist_ok=True)
    target = root / file_name
    target.write_bytes(image_bytes)
    return f"/uploads/fish/{file_name}"
