from __future__ import annotations

from datetime import datetime
from pathlib import Path


def save_training_upload(file, base_dir: str | Path) -> Path:
    target_dir = Path(base_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{int(datetime.utcnow().timestamp() * 1000)}_{file.filename}"
    with target.open("wb") as buffer:
        buffer.write(file.file.read())
    return target
