from __future__ import annotations

import shutil
from pathlib import Path

from app.core.config import get_settings


def save_model_zip(model_type: str, version: str, upload_file) -> Path:
    settings = get_settings()
    target_dir = (Path(settings.model_root) / "registry" / model_type / version).resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    zip_path = target_dir / "model.zip"
    with zip_path.open("wb") as buffer:
        shutil.copyfileobj(upload_file, buffer)
    return zip_path
