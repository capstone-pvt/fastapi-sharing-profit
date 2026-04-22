from typing import Any, Callable

from fastapi import Depends, HTTPException, Request, status
from jose import JWTError, jwt

from app.core.cache import AsyncTtlCache
from app.core.config import get_settings
from app.db import get_db
from app.role_utils import get_user_role_ids, get_user_role_names, get_merged_permissions
from app.utils import serialize_doc, to_object_id


# Cache authenticated user lookups for 30s keyed by (user_id, session_id).
# Session rotation on login/logout invalidates stale entries naturally — a
# stolen/rotated session will miss the cache key after the next login.
_user_cache = AsyncTtlCache(ttl_seconds=30.0)


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
    if not session_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

    async def _load_user() -> dict[str, Any] | None:
        db = get_db()
        doc = await db["users"].find_one({"_id": to_object_id(user_id)})
        if not doc or doc.get("sessionId") != session_id:
            return None
        return doc

    user = await _user_cache.get_or_set((user_id, session_id), _load_user)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

    user_data = serialize_doc(user)
    # Multi-role: prefer roleIds (list) from JWT, fallback to roleId (single)
    jwt_role_ids = payload.get("roleIds")
    if isinstance(jwt_role_ids, list) and jwt_role_ids:
        user_data["roleIds"] = jwt_role_ids
    else:
        single = payload.get("roleId")
        if single:
            user_data["roleIds"] = [single]
        else:
            user_data["roleIds"] = get_user_role_ids(user_data)
    # Keep backward compat
    user_data["roleId"] = user_data["roleIds"][0] if user_data["roleIds"] else None
    return user_data


def require_roles(*roles: str) -> Callable:
    async def _guard(user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
        if not roles:
            return user
        user_roles = await get_user_role_names(user)
        # Super always passes any role guard.
        if "super" in user_roles:
            return user
        if not user_roles.intersection(set(roles)):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
        return user

    return _guard


def require_permissions(*permissions: str) -> Callable:
    async def _guard(user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
        if not permissions:
            return user
        # Super always has every permission.
        user_roles = await get_user_role_names(user)
        if "super" in user_roles:
            return user
        role_ids = get_user_role_ids(user)
        if not role_ids:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
        # Merge permissions from ALL roles
        perm_names = set(await get_merged_permissions(role_ids))
        if not set(permissions).issubset(perm_names):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
        return user

    return _guard
