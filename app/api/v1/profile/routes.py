from typing import Any

from fastapi import APIRouter, Body, Depends, File, HTTPException, UploadFile

from app.core.security import hash_password, verify_password
from app.deps import get_current_user
from app.domain.profile.services import (
    build_profile_update_payload,
    validate_password_change,
    validate_profile_update,
)
from app.infrastructure.profile.repository import (
    get_profile,
    update_avatar,
    update_password,
    update_profile,
)
from app.infrastructure.roles.repository import get_role_permissions_names
from app.infrastructure.auth.repository import get_company_by_id, get_role_by_id
from app.infrastructure.profile.storage import save_profile_avatar


router = APIRouter(prefix="/profile", tags=["profile"])


async def _enrich_with_company(profile: dict[str, Any]) -> None:
    """Attach company fields (including themeColor) to the profile dict."""
    company_id = str(profile["companyId"]) if profile.get("companyId") else None
    if not company_id:
        return
    company = await get_company_by_id(company_id)
    if company:
        profile["companyName"] = company.get("companyName")
        profile["companyAddress"] = company.get("companyAddress")
        profile["companyPhone"] = company.get("companyPhone")
        profile["companyTaxId"] = company.get("companyTaxId")
        profile["companyThemeColor"] = company.get("themeColor")
        profile["companyCode"] = company.get("companyCode")


def _get_role_id(profile: dict[str, Any]) -> str | None:
    role_id = profile.get("roleId")
    if role_id:
        return role_id
    role_value = profile.get("role")
    if isinstance(role_value, dict):
        return role_value.get("id")
    if isinstance(role_value, str):
        return role_value
    return None


@router.get("")
async def fetch_profile(user: dict[str, Any] = Depends(get_current_user)):
    profile = await get_profile(user["id"])
    if not profile:
        raise HTTPException(status_code=404, detail="User not found")
    role_id = _get_role_id(profile)
    role = await get_role_by_id(role_id) if role_id else None
    if role_id:
        profile["role"] = {"id": role_id, "name": role.get("name") if role else None}
    profile["permissions"] = (
        await get_role_permissions_names(role_id) if role_id else []
    )
    await _enrich_with_company(profile)
    return profile


@router.patch("")
async def patch_profile(
    payload: dict[str, Any] = Body(...),
    user: dict[str, Any] = Depends(get_current_user),
):
    try:
        validate_profile_update(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    update_payload = build_profile_update_payload(payload)
    profile = await update_profile(user["id"], update_payload)
    if not profile:
        raise HTTPException(status_code=404, detail="User not found")
    role_id = _get_role_id(profile)
    role = await get_role_by_id(role_id) if role_id else None
    if role_id:
        profile["role"] = {"id": role_id, "name": role.get("name") if role else None}
    profile["permissions"] = (
        await get_role_permissions_names(role_id) if role_id else []
    )
    await _enrich_with_company(profile)
    return profile


_ALLOWED_AVATAR_TYPES = {"image/jpeg", "image/png", "image/webp"}


@router.post("/avatar")
async def upload_avatar(
    image: UploadFile = File(...),
    user: dict[str, Any] = Depends(get_current_user),
):
    if not image:
        raise HTTPException(status_code=400, detail="Image file is required")
    if image.content_type not in _ALLOWED_AVATAR_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid image type. Allowed: {', '.join(_ALLOWED_AVATAR_TYPES)}",
        )
    image_bytes = await image.read()
    image_name = image.filename or f"avatar_{user['id']}.jpg"
    image_url = save_profile_avatar(image_bytes, image_name)
    profile = await update_avatar(user["id"], image_url)
    if not profile:
        raise HTTPException(status_code=404, detail="User not found")
    role_id = _get_role_id(profile)
    role = await get_role_by_id(role_id) if role_id else None
    if role_id:
        profile["role"] = {"id": role_id, "name": role.get("name") if role else None}
    profile["permissions"] = (
        await get_role_permissions_names(role_id) if role_id else []
    )
    await _enrich_with_company(profile)
    return profile


@router.post("/change-password")
async def change_password(
    payload: dict[str, Any] = Body(...),
    user: dict[str, Any] = Depends(get_current_user),
):
    try:
        current_password, new_password = validate_password_change(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    stored = await get_profile(user["id"])
    if not stored or not stored.get("password"):
        raise HTTPException(status_code=404, detail="User not found")
    if not verify_password(current_password, stored.get("password", "")):
        raise HTTPException(status_code=401, detail="Current password is incorrect")

    await update_password(user["id"], hash_password(new_password))
    return {"status": "ok"}
