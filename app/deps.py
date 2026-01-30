from typing import Any, Callable

from fastapi import Depends, HTTPException, Request, status
from jose import JWTError, jwt
from bson import ObjectId

from app.core.config import get_settings
from app.db import get_db
from app.utils import serialize_doc, to_object_id


async def get_current_user(request: Request) -> dict[str, Any]:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    token = auth.replace("Bearer ", "")
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED) from exc

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    session_id = payload.get("sid")

    db = get_db()
    user = await db["users"].find_one({"_id": to_object_id(user_id)})
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    if not session_id or user.get("sessionId") != session_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

    user_data = serialize_doc(user)
    user_data["roleId"] = payload.get("roleId")
    return user_data


def require_roles(*roles: str) -> Callable:
    async def _guard(user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
        if not roles:
            return user
        role_name = None
        role_value = user.get("role")
        if isinstance(role_value, dict):
            role_name = role_value.get("name")
        if not role_name and user.get("roleId"):
            db = get_db()
            role = await db["roles"].find_one({"_id": to_object_id(user["roleId"])})
            role_name = role.get("name") if role else None
        if role_name not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
        return user

    return _guard


def require_permissions(*permissions: str) -> Callable:
    async def _guard(user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
        if not permissions:
            return user
        db = get_db()
        role_id = user.get("roleId") or user.get("role", {}).get("id")
        if not role_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
        role = await db["roles"].find_one({"_id": to_object_id(role_id)})
        role_perms = role.get("permissions", []) if role else []

        permission_names: set[str] = set()
        if role_perms:
            if isinstance(role_perms[0], dict) and "name" in role_perms[0]:
                permission_names = {perm.get("name") for perm in role_perms}
            else:
                has_object_ids = any(
                    isinstance(perm, ObjectId) or ObjectId.is_valid(str(perm))
                    for perm in role_perms
                )
                if has_object_ids:
                    ids = [
                        perm if isinstance(perm, ObjectId) else to_object_id(str(perm))
                        for perm in role_perms
                    ]
                    cursor = db["permissions"].find({"_id": {"$in": ids}})
                    permission_names = {
                        perm.get("name") async for perm in cursor if perm.get("name")
                    }
                else:
                    permission_names = {str(perm) for perm in role_perms}

        if not set(permissions).issubset(permission_names):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
        return user

    return _guard
