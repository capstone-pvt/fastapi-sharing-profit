from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def validate_profile_update(payload: dict[str, Any]) -> None:
    if not payload:
        raise ValueError("No profile fields provided")
    allowed = {
        "firstName",
        "lastName",
        "email",
        "companyName",
        "companyAddress",
        "companyPhone",
        "companyTaxId",
        "street",
        "houseNumber",
        "barangay",
        "city",
        "province",
        "zipCode",
        "kycCompleted",
    }
    if not any(field in payload for field in allowed):
        raise ValueError("No updatable fields provided")


def build_profile_update_payload(payload: dict[str, Any]) -> dict[str, Any]:
    update_payload = {}
    for field in (
        "firstName",
        "lastName",
        "email",
        "companyName",
        "companyAddress",
        "companyPhone",
        "companyTaxId",
        "street",
        "houseNumber",
        "barangay",
        "city",
        "province",
        "zipCode",
        "kycCompleted",
    ):
        if field in payload and payload[field] is not None:
            update_payload[field] = payload[field]
    update_payload["updatedAt"] = datetime.now(timezone.utc)
    return update_payload


def validate_password_change(payload: dict[str, Any]) -> tuple[str, str]:
    current_password = payload.get("currentPassword")
    new_password = payload.get("newPassword")
    if not current_password or not new_password:
        raise ValueError("Current and new passwords are required")
    if len(new_password) < 6:
        raise ValueError("New password must be at least 6 characters")
    return current_password, new_password
