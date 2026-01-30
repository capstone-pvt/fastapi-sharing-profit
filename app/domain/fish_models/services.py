from __future__ import annotations

from datetime import datetime
from typing import Any


def build_create_model_payload(payload: dict[str, Any]) -> dict[str, Any]:
    now = datetime.utcnow()
    model_payload = dict(payload)
    model_payload["createdAt"] = now
    model_payload["updatedAt"] = now
    return model_payload


def build_update_model_payload(payload: dict[str, Any]) -> dict[str, Any]:
    model_payload = dict(payload)
    model_payload["updatedAt"] = datetime.utcnow()
    return model_payload


def build_upload_record(
    *,
    model_type: str,
    version: str,
    description: str | None,
    is_active: bool,
    model_path: str,
) -> dict[str, Any]:
    now = datetime.utcnow()
    return {
        "modelType": model_type,
        "version": version,
        "modelPath": model_path,
        "description": description,
        "isActive": is_active,
        "createdAt": now,
        "updatedAt": now,
    }
