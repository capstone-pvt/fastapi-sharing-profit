from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from bson import ObjectId


def refresh_expiry_date(expiration_days: int) -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=expiration_days)


def _clean_str(value: Any) -> str | None:
    """Return stripped string or None if blank / not a string."""
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None


def _clean_address(payload: dict[str, Any]) -> dict[str, Any] | None:
    """Accept either a flat string or a structured PSGC object."""
    address = payload.get("address")
    if not address:
        return None
    if isinstance(address, str):
        cleaned = address.strip()
        return {"line": cleaned} if cleaned else None
    if isinstance(address, dict):
        region = address.get("region") if isinstance(address.get("region"), dict) else None
        province = address.get("province") if isinstance(address.get("province"), dict) else None
        city = address.get("cityMunicipality") if isinstance(address.get("cityMunicipality"), dict) else None
        barangay = address.get("barangay") if isinstance(address.get("barangay"), dict) else None
        line = _clean_str(address.get("line"))
        if not (region or province or city or barangay or line):
            return None
        return {
            "region": region,
            "province": province,
            "cityMunicipality": city,
            "barangay": barangay,
            "line": line,
        }
    return None


def validate_register_payload(payload: dict[str, Any]) -> dict[str, Any]:
    email = _clean_str(payload.get("email"))
    username = _clean_str(payload.get("username"))
    password = payload.get("password")
    first_name = _clean_str(payload.get("firstName"))
    last_name = _clean_str(payload.get("lastName"))
    role_id = _clean_str(payload.get("roleId"))
    role_ids = payload.get("roleIds")
    role_name = _clean_str(payload.get("roleName"))
    company_code = _clean_str(payload.get("companyCode"))
    company_name = _clean_str(payload.get("companyName"))
    if not password or not first_name or not last_name:
        raise ValueError("Missing required fields")
    if not email and not username:
        raise ValueError("Email or username is required")
    # Normalise to roleIds list
    if role_ids and isinstance(role_ids, list):
        normalised_role_ids = role_ids
    elif role_id:
        normalised_role_ids = [role_id]
    else:
        normalised_role_ids = None
    return {
        "email": email,
        "username": (username.lower() if username else None),
        "password": password,
        "firstName": first_name,
        "lastName": last_name,
        "roleId": role_id,  # backward compat
        "roleIds": normalised_role_ids,
        "roleName": (role_name.lower() if role_name else None),
        "companyCode": company_code,
        "companyName": company_name,
        "birthday": _clean_str(payload.get("birthday")),
        "mobileNumber": _clean_str(payload.get("mobileNumber")),
        "address": _clean_address(payload),
        "validIdBase64": _clean_str(payload.get("validIdBase64")),
        "profilePhotoBase64": _clean_str(payload.get("profilePhotoBase64")),
    }


def validate_login_payload(payload: dict[str, Any]) -> tuple[str, str]:
    # Accept either `email`, `username`, or a generic `identifier` field.
    raw = (
        payload.get("identifier")
        or payload.get("email")
        or payload.get("username")
    )
    password = payload.get("password")
    if not raw or not password:
        raise ValueError("Missing credentials")
    identifier = raw.strip() if isinstance(raw, str) else ""
    if not identifier:
        raise ValueError("Missing credentials")
    return identifier, password


def validate_refresh_payload(payload: dict[str, Any]) -> str:
    refresh_token = payload.get("refreshToken")
    if not refresh_token:
        raise ValueError("Missing refresh token")
    return refresh_token


def build_user_doc(
    email: str | None,
    hashed_password: str,
    first_name: str,
    last_name: str,
    role_ids: list[str] | None = None,
    role_id: str | None = None,
    session_id: str | None = None,
    company_id: str | None = None,
    company_approved: bool | None = None,
    birthday: str | None = None,
    username: str | None = None,
    mobile_number: str | None = None,
    address: dict[str, Any] | None = None,
    valid_id_url: str | None = None,
    profile_photo_url: str | None = None,
    requested_role: str | None = None,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    # Normalise to roleIds list
    if role_ids:
        final_role_ids = role_ids
    elif role_id:
        final_role_ids = [role_id]
    else:
        final_role_ids = []
    user_doc: dict[str, Any] = {
        "email": email,
        "password": hashed_password,
        "firstName": first_name,
        "lastName": last_name,
        "roleIds": final_role_ids,
        "birthday": birthday,
        "createdAt": now,
        "updatedAt": now,
    }
    if username:
        user_doc["username"] = username
    if mobile_number:
        user_doc["mobileNumber"] = mobile_number
    if address:
        user_doc["address"] = address
    if valid_id_url:
        user_doc["validIdUrl"] = valid_id_url
    if profile_photo_url:
        user_doc["profilePhotoUrl"] = profile_photo_url
    if requested_role:
        user_doc["requestedRole"] = requested_role
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
    kyc_completed: bool = False,
    street: str | None = None,
    house_number: str | None = None,
    barangay: str | None = None,
    city: str | None = None,
    province: str | None = None,
    zip_code: str | None = None,
    approval_delegates: list[str] | None = None,
    requested_role: str | None = None,
    username: str | None = None,
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
        "kycCompleted": kyc_completed,
        "street": street,
        "houseNumber": house_number,
        "barangay": barangay,
        "city": city,
        "province": province,
        "zipCode": zip_code,
        "approvalDelegates": [r for r in (approval_delegates or []) if isinstance(r, str)],
    }
    if requested_role:
        user_obj["requestedRole"] = requested_role
    if username:
        user_obj["username"] = username
    if company_id:
        user_obj["companyId"] = company_id
    return {
        "accessToken": access_token,
        "refreshToken": refresh_token,
        "user": user_obj,
    }
