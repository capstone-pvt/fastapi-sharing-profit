from __future__ import annotations

from datetime import datetime
from typing import Any


def build_create_permission_payload(payload: dict[str, Any]) -> dict[str, Any]:
    now = datetime.utcnow()
    perm_payload = dict(payload)
    perm_payload["createdAt"] = now
    perm_payload["updatedAt"] = now
    return perm_payload


def build_update_permission_payload(payload: dict[str, Any]) -> dict[str, Any]:
    perm_payload = dict(payload)
    perm_payload["updatedAt"] = datetime.utcnow()
    return perm_payload
