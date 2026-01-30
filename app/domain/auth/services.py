from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any


def refresh_expiry_date(expiration_days: int) -> datetime:
    return datetime.utcnow() + timedelta(days=expiration_days)


def validate_register_payload(payload: dict[str, Any]) -> dict[str, str | None]:
    email = payload.get("email")
    password = payload.get("password")
    first_name = payload.get("firstName")
    last_name = payload.get("lastName")
    role_id = payload.get("roleId")
    company_name = payload.get("companyName")
    company_address = payload.get("companyAddress")
    company_phone = payload.get("companyPhone")
    company_tax_id = payload.get("companyTaxId")
    if not email or not password or not first_name or not last_name:
        raise ValueError("Missing required fields")
    return {
        "email": email,
        "password": password,
        "firstName": first_name,
        "lastName": last_name,
        "roleId": role_id,
        "companyName": company_name,
        "companyAddress": company_address,
        "companyPhone": company_phone,
        "companyTaxId": company_tax_id,
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
    company_name: str | None = None,
    company_address: str | None = None,
    company_phone: str | None = None,
    company_tax_id: str | None = None,
) -> dict[str, Any]:
    now = datetime.utcnow()
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
    if company_name:
        user_doc["companyName"] = company_name
    if company_address:
        user_doc["companyAddress"] = company_address
    if company_phone:
        user_doc["companyPhone"] = company_phone
    if company_tax_id:
        user_doc["companyTaxId"] = company_tax_id
    return user_doc


def build_auth_response(
    *,
    user_id: str,
    email: str,
    first_name: str | None,
    last_name: str | None,
    role_id: str,
    role_name: str | None,
    company_name: str | None,
    company_address: str | None,
    company_phone: str | None,
    company_tax_id: str | None,
    permissions: list[str] | None,
    access_token: str,
    refresh_token: str,
) -> dict[str, Any]:
    return {
        "accessToken": access_token,
        "refreshToken": refresh_token,
        "user": {
            "id": user_id,
            "email": email,
            "firstName": first_name,
            "lastName": last_name,
            "role": {"id": role_id, "name": role_name},
            "companyName": company_name,
            "companyAddress": company_address,
            "companyPhone": company_phone,
            "companyTaxId": company_tax_id,
            "permissions": permissions or [],
        },
    }
