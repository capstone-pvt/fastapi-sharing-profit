from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable


def build_user_query(
    search: str | None = None,
    pending: bool | None = None,
) -> dict[str, Any]:
    query: dict[str, Any] = {}
    if search:
        query["email"] = {"$regex": search, "$options": "i"}
    if pending is True:
        query["companyApproved"] = False
    return query


def validate_user_payload(payload: dict[str, Any], required: list[str]) -> None:
    if any(not payload.get(field) for field in required):
        raise ValueError("Missing required fields")


def build_create_user_payload(
    payload: dict[str, Any], *, hash_password: Callable[[str], str]
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    user_payload = dict(payload)
    user_payload["password"] = hash_password(user_payload["password"])
    user_payload["createdAt"] = now
    user_payload["updatedAt"] = now
    return user_payload


def build_update_user_payload(
    payload: dict[str, Any], *, hash_password: Callable[[str], str]
) -> dict[str, Any]:
    update_payload = dict(payload)
    # Only update password when a non-empty new password is provided (never overwrite with empty)
    raw_password = update_payload.pop("password", None)
    if raw_password is not None and str(raw_password).strip():
        update_payload["password"] = hash_password(raw_password)
    update_payload["updatedAt"] = datetime.now(timezone.utc)
    return update_payload
