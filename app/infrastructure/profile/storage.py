from __future__ import annotations

import uuid
from pathlib import Path, PurePosixPath

from app.core.config import get_settings


def save_profile_avatar(image_bytes: bytes, file_name: str) -> str:
    settings = get_settings()
    root = Path(settings.upload_root) / "profiles"
    root.mkdir(parents=True, exist_ok=True)
    # Use UUID to prevent path traversal via user-controlled filenames
    ext = PurePosixPath(file_name).suffix or ".jpg"
    safe_name = f"{uuid.uuid4().hex}{ext}"
    target = root / safe_name
    target.write_bytes(image_bytes)
    return f"/uploads/profiles/{safe_name}"
