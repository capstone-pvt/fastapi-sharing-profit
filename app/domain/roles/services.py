from __future__ import annotations

from datetime import datetime
from typing import Any


def build_create_role_payload(payload: dict[str, Any]) -> dict[str, Any]:
    now = datetime.utcnow()
    role_payload = dict(payload)
    role_payload["permissions"] = role_payload.get("permissions", [])
    role_payload["createdAt"] = now
    role_payload["updatedAt"] = now
    return role_payload


def build_update_role_payload(payload: dict[str, Any]) -> dict[str, Any]:
    role_payload = dict(payload)
    role_payload["updatedAt"] = datetime.utcnow()
    return role_payload
