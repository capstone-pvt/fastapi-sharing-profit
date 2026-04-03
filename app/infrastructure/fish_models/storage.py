from __future__ import annotations

import re
import shutil
from pathlib import Path

from fastapi import HTTPException

from app.core.config import get_settings

# Only allow safe path segment characters: letters, digits, dots, hyphens, underscores
_SAFE_PATH_SEGMENT = re.compile(r"^[\w.\-]+$")


def _assert_safe_segment(value: str, field: str) -> None:
    """Raise 400 if the value could escape the model root directory."""
    if not _SAFE_PATH_SEGMENT.match(value):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid characters in {field}. Only letters, digits, dots, hyphens, and underscores are allowed.",
        )


def save_model_zip(model_type: str, version: str, upload_file) -> Path:
    _assert_safe_segment(model_type, "modelType")
    _assert_safe_segment(version, "version")

    settings = get_settings()
    model_root = Path(settings.model_root).resolve()
    target_dir = (model_root / "registry" / model_type / version).resolve()

    # Guard against path traversal even after resolve()
    if not str(target_dir).startswith(str(model_root)):
        raise HTTPException(status_code=400, detail="Invalid model type or version")

    target_dir.mkdir(parents=True, exist_ok=True)
    zip_path = target_dir / "model.zip"
    with zip_path.open("wb") as buffer:
        shutil.copyfileobj(upload_file, buffer)
    return zip_path
