import secrets
import string
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Body, Depends, HTTPException, status
from jose import JWTError, jwt

from app.db import get_db

from app.core.config import get_settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
)
from app.deps import get_current_user
from app.domain.auth.services import (
    build_auth_response,
    build_user_doc,
    refresh_expiry_date,
    validate_login_payload,
    validate_refresh_payload,
    validate_register_payload,
)
from app.infrastructure.auth.repository import (
    create_user,
    get_company_by_code,
    get_company_by_id,
    get_role_by_id,
    get_role_by_name,
    get_user_by_email,
    get_user_by_id,
    revoke_refresh_token,
    update_session,
    update_refresh_token,
)
from app.role_utils import get_user_role_ids, get_merged_permissions


router = APIRouter(prefix="/auth", tags=["auth"])


def _generate_company_code() -> str:
    """Generate a short alphanumeric company code like ``AB12CD``."""
    chars = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(chars) for _ in range(6))


async def _resolve_roles(role_ids: list[str]) -> tuple[list[str], list[str], list[str]]:
    """Resolve role IDs to (ids, names, merged_permissions)."""
    names = []
    for rid in role_ids:
        role = await get_role_by_id(rid) if rid else None
        names.append(role.get("name") if role else None)
    permissions = await get_merged_permissions(role_ids)
    return role_ids, names, permissions


@router.post("/register")
async def register(payload: dict[str, Any] = Body(...)):
    try:
        fields = validate_register_payload(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    email = fields["email"]
    password = fields["password"]
    first_name = fields["firstName"]
    last_name = fields["lastName"]
    role_ids = fields.get("roleIds") or []
    role_id = fields.get("roleId")
    company_code = fields.get("companyCode")
    company_name = fields.get("companyName")

    existing = await get_user_by_email(email)
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")

    db = get_db()
    company_id: str | None = None

    if company_name:
        # Admin registration — create a new company
        admin_role = await get_role_by_name("admin")
        if not admin_role:
            raise HTTPException(
                status_code=404, detail='Role "admin" not found'
            )
        role_ids = [str(admin_role["_id"])]

        # Generate a unique company code
        new_code = _generate_company_code()
        while await db["companies"].find_one(
            {"companyCode": {"$regex": f"^{new_code}$", "$options": "i"}}
        ):
            new_code = _generate_company_code()

        now = datetime.now(timezone.utc)
        company_doc = {
            "companyName": company_name,
            "companyCode": new_code,
            "companyAddress": None,
            "companyPhone": None,
            "companyTaxId": None,
            "createdAt": now,
            "updatedAt": now,
        }
        result = await db["companies"].insert_one(company_doc)
        company_id = str(result.inserted_id)
    elif company_code:
        # User registration — join existing company
        company = await get_company_by_code(company_code)
        if not company:
            raise HTTPException(
                status_code=400, detail="Company code not found"
            )
        company_id = str(company["_id"])

        # Enforce max 20 users per company
        max_users = 20
        license_doc = await db["app_licenses"].find_one(
            {"companyId": company["_id"], "status": "active"},
            sort=[("expiresAt", -1)],
        )
        if license_doc:
            license_max = license_doc.get("maxUsers", 20)
            if 0 < license_max < max_users:
                max_users = license_max

        current_count = await db["users"].count_documents(
            {"companyId": {"$in": [company["_id"], str(company["_id"])]}}
        )
        if current_count >= max_users:
            raise HTTPException(
                status_code=403,
                detail=f"Company has reached the maximum number of users ({max_users})",
            )

    # Normalise role_ids
    if not role_ids:
        if role_id:
            role_ids = [role_id]
        else:
            # Default role: "crew" when joining a company, "user" otherwise
            default_role_name = "crew" if company_code else "user"
            default_role = await get_role_by_name(default_role_name)
            if not default_role:
                # Fallback to "user" if "crew" doesn't exist
                default_role = await get_role_by_name("user")
            if not default_role:
                raise HTTPException(
                    status_code=404, detail=f'Default role "{default_role_name}" not found'
                )
            role_ids = [str(default_role["_id"])]

    hashed = hash_password(password)
    session_id = uuid4().hex
    is_company_creator = bool(company_name)
    user_doc = build_user_doc(
        email=email,
        hashed_password=hashed,
        first_name=first_name,
        last_name=last_name,
        role_ids=role_ids,
        session_id=session_id,
        company_id=company_id,
        company_approved=True if is_company_creator else None,
    )
    user_id = await create_user(user_doc)

    access_token = create_access_token(
        {"sub": user_id, "email": email, "roleIds": role_ids, "sid": session_id}
    )
    refresh_token = create_refresh_token(
        {"sub": user_id, "email": email, "sid": session_id}
    )
    settings = get_settings()
    await update_session(
        user_id,
        refresh_token,
        refresh_expiry_date(settings.jwt_refresh_expiration_days),
        session_id,
    )

    r_ids, r_names, permissions = await _resolve_roles(role_ids)
    company = await get_company_by_id(company_id) if company_id else None
    company_approved = True if is_company_creator else (False if company_id else True)
    return build_auth_response(
        user_id=user_id,
        email=email,
        first_name=first_name,
        last_name=last_name,
        role_ids=r_ids,
        role_names=r_names,
        company_id=company_id,
        company_approved=company_approved,
        company_name=company.get("companyName") if company else None,
        company_address=company.get("companyAddress") if company else None,
        company_phone=company.get("companyPhone") if company else None,
        company_tax_id=company.get("companyTaxId") if company else None,
        company_theme_color=company.get("themeColor") if company else None,
        company_code=company.get("companyCode") if company else None,
        permissions=permissions,
        access_token=access_token,
        refresh_token=refresh_token,
    )


@router.post("/login")
async def login(payload: dict[str, Any] = Body(...)):
    try:
        email, password = validate_login_payload(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    user = await get_user_by_email(email)
    if not user or not verify_password(password, user.get("password", "")):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

    user_id = str(user["_id"])
    # Multi-role: extract role IDs from user doc
    role_ids = get_user_role_ids(user)
    session_id = uuid4().hex
    access_token = create_access_token(
        {"sub": user_id, "email": email, "roleIds": role_ids, "sid": session_id}
    )
    refresh_token = create_refresh_token(
        {"sub": user_id, "email": email, "sid": session_id}
    )
    settings = get_settings()
    await update_session(
        user_id,
        refresh_token,
        refresh_expiry_date(settings.jwt_refresh_expiration_days),
        session_id,
    )

    r_ids, r_names, permissions = await _resolve_roles(role_ids)
    company_id = str(user["companyId"]) if user.get("companyId") else None
    company = (
        await get_company_by_id(company_id) if company_id else None
    )
    company_approved = user.get("companyApproved", True)
    return build_auth_response(
        user_id=user_id,
        email=email,
        first_name=user.get("firstName"),
        last_name=user.get("lastName"),
        role_ids=r_ids,
        role_names=r_names,
        company_id=company_id,
        company_approved=company_approved,
        company_name=company.get("companyName") if company else user.get("companyName"),
        company_address=company.get("companyAddress") if company else user.get("companyAddress"),
        company_phone=company.get("companyPhone") if company else user.get("companyPhone"),
        company_tax_id=company.get("companyTaxId") if company else user.get("companyTaxId"),
        company_theme_color=company.get("themeColor") if company else None,
        company_code=company.get("companyCode") if company else None,
        permissions=permissions,
        access_token=access_token,
        refresh_token=refresh_token,
    )


@router.post("/refresh")
async def refresh(payload: dict[str, Any] = Body(...)):
    try:
        refresh_token = validate_refresh_payload(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    settings = get_settings()
    try:
        refresh_payload = jwt.decode(
            refresh_token, settings.jwt_refresh_secret, algorithms=["HS256"]
        )
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED) from exc

    user_id = refresh_payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

    user = await get_user_by_id(user_id)
    if not user or user.get("refreshToken") != refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

    session_id = user.get("sessionId")
    if not session_id or refresh_payload.get("sid") != session_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

    # Multi-role
    role_ids = get_user_role_ids(user)
    access_token = create_access_token(
        {
            "sub": user_id,
            "email": user.get("email"),
            "roleIds": role_ids,
            "sid": session_id,
        }
    )
    new_refresh_token = create_refresh_token(
        {"sub": user_id, "email": user.get("email"), "sid": session_id}
    )
    await update_refresh_token(
        user_id,
        new_refresh_token,
        refresh_expiry_date(settings.jwt_refresh_expiration_days),
    )

    r_ids, r_names, permissions = await _resolve_roles(role_ids)
    company_id = str(user["companyId"]) if user.get("companyId") else None
    company = (
        await get_company_by_id(company_id) if company_id else None
    )
    company_approved = user.get("companyApproved", True)
    return build_auth_response(
        user_id=user_id,
        email=user.get("email"),
        first_name=user.get("firstName"),
        last_name=user.get("lastName"),
        role_ids=r_ids,
        role_names=r_names,
        company_id=company_id,
        company_approved=company_approved,
        company_name=company.get("companyName") if company else user.get("companyName"),
        company_address=company.get("companyAddress") if company else user.get("companyAddress"),
        company_phone=company.get("companyPhone") if company else user.get("companyPhone"),
        company_tax_id=company.get("companyTaxId") if company else user.get("companyTaxId"),
        company_theme_color=company.get("themeColor") if company else None,
        company_code=company.get("companyCode") if company else None,
        permissions=permissions,
        access_token=access_token,
        refresh_token=new_refresh_token,
    )


@router.post("/logout")
async def logout(user: dict[str, Any] = Depends(get_current_user)):
    await revoke_refresh_token(user["id"])
    return {"status": "ok"}
