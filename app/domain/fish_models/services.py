from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def build_create_model_payload(payload: dict[str, Any]) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    model_payload = dict(payload)
    model_payload["createdAt"] = now
    model_payload["updatedAt"] = now
    return model_payload


def build_update_model_payload(payload: dict[str, Any]) -> dict[str, Any]:
    model_payload = dict(payload)
    model_payload["updatedAt"] = datetime.now(timezone.utc)
    return model_payload


def build_upload_record(
    *,
    model_type: str,
    version: str,
    description: str | None,
    is_active: bool,
    model_path: str,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    return {
        "modelType": model_type,
        "version": version,
        "modelPath": model_path,
        "description": description,
        "isActive": is_active,
        "createdAt": now,
        "updatedAt": now,
    }
