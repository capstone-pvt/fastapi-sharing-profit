from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath


def save_training_upload(file, base_dir: str | Path) -> Path:
    target_dir = Path(base_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    # Use UUID to prevent path traversal via user-controlled filenames
    ext = PurePosixPath(file.filename or "image.jpg").suffix or ".jpg"
    safe_name = f"{int(datetime.now(timezone.utc).timestamp() * 1000)}_{uuid.uuid4().hex}{ext}"
    target = target_dir / safe_name
    with target.open("wb") as buffer:
        buffer.write(file.file.read())
    return target
