from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def build_create_species_payload(payload: dict[str, Any]) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    species_payload = dict(payload)
    species_payload["createdAt"] = now
    species_payload["updatedAt"] = now
    return species_payload


def build_update_species_payload(payload: dict[str, Any]) -> dict[str, Any]:
    species_payload = dict(payload)
    species_payload["updatedAt"] = datetime.now(timezone.utc)
    return species_payload
