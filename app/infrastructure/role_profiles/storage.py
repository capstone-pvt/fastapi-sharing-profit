"""Filesystem storage for role-profile documents (TIN, Mayor's Permit, etc.).

Mirrors the avatar storage pattern: writes under settings.upload_root and
returns a web-servable path rooted at /uploads/...
"""
from __future__ import annotations

import uuid
from pathlib import Path, PurePosixPath

from app.core.config import get_settings


ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".pdf"}


def save_role_document(
    user_id: str,
    file_bytes: bytes,
    original_name: str,
) -> str:
    """Persist a document and return the web URL (e.g. /uploads/role-docs/...)."""
    settings = get_settings()
    root = Path(settings.upload_root) / "role-docs" / user_id
    root.mkdir(parents=True, exist_ok=True)
    ext = PurePosixPath(original_name).suffix.lower() or ".bin"
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(
            f"Unsupported document type '{ext}'. Allowed: "
            f"{', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )
    safe_name = f"{uuid.uuid4().hex}{ext}"
    target = root / safe_name
    target.write_bytes(file_bytes)
    return f"/uploads/role-docs/{user_id}/{safe_name}"


def delete_role_document(file_url: str) -> None:
    """Best-effort delete for a previously-saved document URL."""
    settings = get_settings()
    prefix = "/uploads/"
    if not file_url.startswith(prefix):
        return
    rel = file_url[len(prefix):]
    target = Path(settings.upload_root) / rel
    try:
        target.unlink(missing_ok=True)
    except OSError:
        # Non-fatal; orphaned files can be cleaned up out-of-band.
        pass
