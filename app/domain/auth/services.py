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
    company_code = payload.get("companyCode")
    company_name = payload.get("companyName")
    if not email or not password or not first_name or not last_name:
        raise ValueError("Missing required fields")
    return {
        "email": email,
        "password": password,
        "firstName": first_name,
        "lastName": last_name,
        "roleId": role_id,
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
    role_id: str,
    session_id: str | None = None,
    company_id: str | None = None,
    company_approved: bool | None = None,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    user_doc = {
        "email": email,
        "password": hashed_password,
        "firstName": first_name,
        "lastName": last_name,
        "roleId": role_id,
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
    role_id: str,
    role_name: str | None,
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
    user_obj: dict[str, Any] = {
        "id": user_id,
        "email": email,
        "firstName": first_name,
        "lastName": last_name,
        "role": {"id": role_id, "name": role_name},
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
