from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, status
from jose import JWTError, jwt

from app.core.config import get_settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
)
from app.db import get_db
from app.deps import get_current_user
from app.utils import serialize_doc, to_object_id


router = APIRouter(prefix="/auth", tags=["auth"])


def refresh_expiry_date() -> datetime:
    settings = get_settings()
    return datetime.utcnow() + timedelta(days=settings.jwt_refresh_expiration_days)


@router.post("/register")
async def register(payload: dict[str, Any] = Body(...)):
    db = get_db()
    email = payload.get("email")
    password = payload.get("password")
    first_name = payload.get("firstName")
    last_name = payload.get("lastName")
    role_id = payload.get("roleId")

    if not email or not password or not first_name or not last_name:
        raise HTTPException(status_code=400, detail="Missing required fields")

    existing = await db["users"].find_one({"email": email})
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")

    if not role_id:
        default_role = await db["roles"].find_one({"name": "user"})
        if not default_role:
            raise HTTPException(
                status_code=404, detail='Default role "user" not found'
            )
        role_id = str(default_role["_id"])

    hashed = hash_password(password)
    user_doc = {
        "email": email,
        "password": hashed,
        "firstName": first_name,
        "lastName": last_name,
        "role": to_object_id(role_id),
        "createdAt": datetime.utcnow(),
        "updatedAt": datetime.utcnow(),
    }
    result = await db["users"].insert_one(user_doc)
    user_id = str(result.inserted_id)

    access_token = create_access_token(
        {"sub": user_id, "email": email, "roleId": role_id}
    )
    refresh_token = create_refresh_token({"sub": user_id, "email": email})
    await db["users"].update_one(
        {"_id": to_object_id(user_id)},
        {
            "$set": {
                "refreshToken": refresh_token,
                "refreshTokenExpiry": refresh_expiry_date(),
            }
        },
    )

    role = await db["roles"].find_one({"_id": to_object_id(role_id)})
    return {
        "accessToken": access_token,
        "refreshToken": refresh_token,
        "user": {
            "id": user_id,
            "email": email,
            "firstName": first_name,
            "lastName": last_name,
            "role": {"id": role_id, "name": role.get("name") if role else None},
        },
    }


@router.post("/login")
async def login(payload: dict[str, Any] = Body(...)):
    db = get_db()
    email = payload.get("email")
    password = payload.get("password")
    if not email or not password:
        raise HTTPException(status_code=400, detail="Missing credentials")

    user = await db["users"].find_one({"email": email})
    if not user or not verify_password(password, user.get("password", "")):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

    user_id = str(user["_id"])
    role_id = str(user.get("role")) if user.get("role") else ""
    access_token = create_access_token(
        {"sub": user_id, "email": email, "roleId": role_id}
    )
    refresh_token = create_refresh_token({"sub": user_id, "email": email})
    await db["users"].update_one(
        {"_id": user["_id"]},
        {
            "$set": {
                "refreshToken": refresh_token,
                "refreshTokenExpiry": refresh_expiry_date(),
            }
        },
    )

    role = (
        await db["roles"].find_one({"_id": to_object_id(role_id)})
        if role_id
        else None
    )
    return {
        "accessToken": access_token,
        "refreshToken": refresh_token,
        "user": {
            "id": user_id,
            "email": email,
            "firstName": user.get("firstName"),
            "lastName": user.get("lastName"),
            "role": {"id": role_id, "name": role.get("name") if role else None},
        },
    }


@router.post("/refresh")
async def refresh(payload: dict[str, Any] = Body(...)):
    db = get_db()
    refresh_token = payload.get("refreshToken")
    if not refresh_token:
        raise HTTPException(status_code=400, detail="Missing refresh token")

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

    user = await db["users"].find_one({"_id": to_object_id(user_id)})
    if not user or user.get("refreshToken") != refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

    access_token = create_access_token(
        {"sub": user_id, "email": user.get("email"), "roleId": str(user.get("role"))}
    )
    new_refresh_token = create_refresh_token(
        {"sub": user_id, "email": user.get("email")}
    )
    await db["users"].update_one(
        {"_id": user["_id"]},
        {
            "$set": {
                "refreshToken": new_refresh_token,
                "refreshTokenExpiry": refresh_expiry_date(),
            }
        },
    )

    role_id = str(user.get("role")) if user.get("role") else ""
    role = (
        await db["roles"].find_one({"_id": to_object_id(role_id)})
        if role_id
        else None
    )
    return {
        "accessToken": access_token,
        "refreshToken": new_refresh_token,
        "user": {
            "id": user_id,
            "email": user.get("email"),
            "firstName": user.get("firstName"),
            "lastName": user.get("lastName"),
            "role": {"id": role_id, "name": role.get("name") if role else None},
        },
    }


@router.post("/logout")
async def logout(user: dict[str, Any] = Depends(get_current_user)):
    db = get_db()
    await db["users"].update_one(
        {"_id": to_object_id(user["id"])},
        {"$set": {"refreshToken": None, "refreshTokenExpiry": None}},
    )
    return {"status": "ok"}
