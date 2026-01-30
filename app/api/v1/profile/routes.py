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
from app.infrastructure.profile.storage import save_profile_avatar


router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("")
async def fetch_profile(user: dict[str, Any] = Depends(get_current_user)):
    profile = await get_profile(user["id"])
    if not profile:
        raise HTTPException(status_code=404, detail="User not found")
    role_id = profile.get("roleId") or profile.get("role", {}).get("id")
    profile["permissions"] = (
        await get_role_permissions_names(role_id) if role_id else []
    )
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
    role_id = profile.get("roleId") or profile.get("role", {}).get("id")
    profile["permissions"] = (
        await get_role_permissions_names(role_id) if role_id else []
    )
    return profile


@router.post("/avatar")
async def upload_avatar(
    image: UploadFile = File(...),
    user: dict[str, Any] = Depends(get_current_user),
):
    if not image:
        raise HTTPException(status_code=400, detail="Image file is required")
    image_bytes = image.file.read()
    image_name = image.filename or f"avatar_{user['id']}.jpg"
    image_url = save_profile_avatar(image_bytes, image_name)
    profile = await update_avatar(user["id"], image_url)
    if not profile:
        raise HTTPException(status_code=404, detail="User not found")
    role_id = profile.get("roleId") or profile.get("role", {}).get("id")
    profile["permissions"] = (
        await get_role_permissions_names(role_id) if role_id else []
    )
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
