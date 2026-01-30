from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Body, Depends, HTTPException, status
from jose import JWTError, jwt

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
    get_role_by_id,
    get_role_by_name,
    get_user_by_email,
    get_user_by_id,
    revoke_refresh_token,
    update_session,
    update_refresh_token,
)
from app.infrastructure.roles.repository import get_role_permissions_names


router = APIRouter(prefix="/auth", tags=["auth"])


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
    role_id = fields["roleId"]
    company_name = fields.get("companyName")
    company_address = fields.get("companyAddress")
    company_phone = fields.get("companyPhone")
    company_tax_id = fields.get("companyTaxId")

    existing = await get_user_by_email(email)
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")

    if not role_id:
        default_role = await get_role_by_name("user")
        if not default_role:
            raise HTTPException(
                status_code=404, detail='Default role "user" not found'
            )
        role_id = str(default_role["_id"])

    hashed = hash_password(password)
    session_id = uuid4().hex
    user_doc = build_user_doc(
        email=email,
        hashed_password=hashed,
        first_name=first_name,
        last_name=last_name,
        role_id=role_id,
        session_id=session_id,
        company_name=company_name,
        company_address=company_address,
        company_phone=company_phone,
        company_tax_id=company_tax_id,
    )
    user_id = await create_user(user_doc)

    access_token = create_access_token(
        {"sub": user_id, "email": email, "roleId": role_id, "sid": session_id}
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

    role = await get_role_by_id(role_id)
    permissions = await get_role_permissions_names(role_id)
    return build_auth_response(
        user_id=user_id,
        email=email,
        first_name=first_name,
        last_name=last_name,
        role_id=role_id,
        role_name=role.get("name") if role else None,
        company_name=company_name,
        company_address=company_address,
        company_phone=company_phone,
        company_tax_id=company_tax_id,
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
    role_id = str(user.get("role")) if user.get("role") else ""
    session_id = uuid4().hex
    access_token = create_access_token(
        {"sub": user_id, "email": email, "roleId": role_id, "sid": session_id}
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

    role = await get_role_by_id(role_id) if role_id else None
    permissions = await get_role_permissions_names(role_id) if role_id else []
    return build_auth_response(
        user_id=user_id,
        email=email,
        first_name=user.get("firstName"),
        last_name=user.get("lastName"),
        role_id=role_id,
        role_name=role.get("name") if role else None,
        company_name=user.get("companyName"),
        company_address=user.get("companyAddress"),
        company_phone=user.get("companyPhone"),
        company_tax_id=user.get("companyTaxId"),
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

    access_token = create_access_token(
        {
            "sub": user_id,
            "email": user.get("email"),
            "roleId": str(user.get("role")),
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

    role_id = str(user.get("role")) if user.get("role") else ""
    role = await get_role_by_id(role_id) if role_id else None
    permissions = await get_role_permissions_names(role_id) if role_id else []
    return build_auth_response(
        user_id=user_id,
        email=user.get("email"),
        first_name=user.get("firstName"),
        last_name=user.get("lastName"),
        role_id=role_id,
        role_name=role.get("name") if role else None,
        company_name=user.get("companyName"),
        company_address=user.get("companyAddress"),
        company_phone=user.get("companyPhone"),
        company_tax_id=user.get("companyTaxId"),
        permissions=permissions,
        access_token=access_token,
        refresh_token=new_refresh_token,
    )


@router.post("/logout")
async def logout(user: dict[str, Any] = Depends(get_current_user)):
    await revoke_refresh_token(user["id"])
    return {"status": "ok"}
