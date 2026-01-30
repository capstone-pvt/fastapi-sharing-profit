from __future__ import annotations

from datetime import datetime
from typing import Any, Callable


def build_user_query(search: str | None) -> dict[str, Any]:
    query: dict[str, Any] = {}
    if search:
        query["email"] = {"$regex": search, "$options": "i"}
    return query


def validate_user_payload(payload: dict[str, Any], required: list[str]) -> None:
    if any(not payload.get(field) for field in required):
        raise ValueError("Missing required fields")


def build_create_user_payload(
    payload: dict[str, Any], *, hash_password: Callable[[str], str]
) -> dict[str, Any]:
    now = datetime.utcnow()
    user_payload = dict(payload)
    user_payload["password"] = hash_password(user_payload["password"])
    user_payload["createdAt"] = now
    user_payload["updatedAt"] = now
    return user_payload


def build_update_user_payload(
    payload: dict[str, Any], *, hash_password: Callable[[str], str]
) -> dict[str, Any]:
    update_payload = dict(payload)
    if "password" in update_payload:
        update_payload["password"] = hash_password(update_payload["password"])
    update_payload["updatedAt"] = datetime.utcnow()
    return update_payload
