from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from bson import ObjectId


def refresh_expiry_date(expiration_days: int) -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=expiration_days)


def validate_register_payload(payload: dict[str, Any]) -> dict[str, str | None]:
    email = payload.get("email")
    password = payload.get("password")
    first_name = payload.get("firstName")
    last_name = payload.get("lastName")
    role_id = payload.get("roleId")
    role_ids = payload.get("roleIds")
    company_code = payload.get("companyCode")
    company_name = payload.get("companyName")
    if not email or not password or not first_name or not last_name:
        raise ValueError("Missing required fields")
    # Normalise to roleIds list
    if role_ids and isinstance(role_ids, list):
        normalised_role_ids = role_ids
    elif role_id:
        normalised_role_ids = [role_id]
    else:
        normalised_role_ids = None
    return {
        "email": email,
        "password": password,
        "firstName": first_name,
        "lastName": last_name,
        "roleId": role_id,  # backward compat
        "roleIds": normalised_role_ids,
        "companyCode": (company_code or "").strip() or None,
        "companyName": (company_name or "").strip() or None,
    }


def validate_login_payload(payload: dict[str, Any]) -> tuple[str, str]:
    email = payload.get("email")
    password = payload.get("password")
    if not email or not password:
        raise ValueError("Missing credentials")
    return email, password


def validate_refresh_payload(payload: dict[str, Any]) -> str:
    refresh_token = payload.get("refreshToken")
    if not refresh_token:
        raise ValueError("Missing refresh token")
    return refresh_token


def build_user_doc(
    email: str,
    hashed_password: str,
    first_name: str,
    last_name: str,
    role_ids: list[str] | None = None,
    role_id: str | None = None,
    session_id: str | None = None,
    company_id: str | None = None,
    company_approved: bool | None = None,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    # Normalise to roleIds list
    if role_ids:
        final_role_ids = role_ids
    elif role_id:
        final_role_ids = [role_id]
    else:
        final_role_ids = []
    user_doc = {
        "email": email,
        "password": hashed_password,
        "firstName": first_name,
        "lastName": last_name,
        "roleIds": final_role_ids,
        "createdAt": now,
        "updatedAt": now,
    }
    if session_id:
        user_doc["sessionId"] = session_id
    if company_id:
        user_doc["companyId"] = ObjectId(company_id) if ObjectId.is_valid(company_id) else company_id
        user_doc["companyApproved"] = company_approved if company_approved is not None else False
    return user_doc


def build_auth_response(
    *,
    user_id: str,
    email: str,
    first_name: str | None,
    last_name: str | None,
    role_ids: list[str] | None = None,
    role_names: list[str] | None = None,
    role_id: str | None = None,
    role_name: str | None = None,
    company_id: str | None = None,
    company_approved: bool = True,
    company_name: str | None = None,
    company_address: str | None = None,
    company_phone: str | None = None,
    company_tax_id: str | None = None,
    company_theme_color: str | None = None,
    company_code: str | None = None,
    permissions: list[str] | None = None,
    access_token: str = "",
    refresh_token: str = "",
) -> dict[str, Any]:
    # Build roles array
    r_ids = role_ids or ([role_id] if role_id else [])
    r_names = role_names or ([role_name] if role_name else [])
    roles_array = []
    for i, rid in enumerate(r_ids):
        name = r_names[i] if i < len(r_names) else None
        roles_array.append({"id": rid, "name": name})

    user_obj: dict[str, Any] = {
        "id": user_id,
        "email": email,
        "firstName": first_name,
        "lastName": last_name,
        # Multi-role
        "roles": roles_array,
        # Backward compat — first role
        "role": roles_array[0] if roles_array else {"id": None, "name": None},
        "companyApproved": company_approved,
        "companyName": company_name,
        "companyAddress": company_address,
        "companyPhone": company_phone,
        "companyTaxId": company_tax_id,
        "companyThemeColor": company_theme_color,
        "companyCode": company_code,
        "permissions": permissions or [],
    }
    if company_id:
        user_obj["companyId"] = company_id
    return {
        "accessToken": access_token,
        "refreshToken": refresh_token,
        "user": user_obj,
    }
