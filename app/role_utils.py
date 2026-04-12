"""Shared role resolution utilities for multi-role support.

All user documents may store roles in one of three formats:
  - ``roles``: list[ObjectId]  (new multi-role format)
  - ``role``:  ObjectId         (legacy single-role)
  - ``roleId``: str             (JWT / serialised payload)
  - ``roleIds``: list[str]      (JWT multi-role payload)

Functions in this module normalise to ``list[str]`` for uniform handling.
"""

from __future__ import annotations

from typing import Any

from app.db import get_db
from app.utils import to_object_id


def get_user_role_ids(user: dict[str, Any]) -> list[str]:
    """Extract role IDs from a user dict, normalised to ``list[str]``.

    Handles all legacy and new formats gracefully.
    """
    # Prefer multi-role fields first
    role_ids = user.get("roleIds")
    if isinstance(role_ids, list) and role_ids:
        return [str(r) for r in role_ids]

    roles = user.get("roles")
    if isinstance(roles, list) and roles:
        out = []
        for r in roles:
            if isinstance(r, dict):
                out.append(str(r.get("id") or r.get("_id", "")))
            else:
                out.append(str(r))
        return [x for x in out if x]

    # Fallback: single role
    role_id = user.get("roleId") or user.get("role")
    if role_id:
        return [str(role_id)]

    return []


async def get_user_role_names(user: dict[str, Any]) -> set[str]:
    """Resolve all role names for a user dict from the DB."""
    role_ids = get_user_role_ids(user)
    if not role_ids:
        return set()

    db = get_db()
    names: set[str] = set()
    for rid in role_ids:
        try:
            role = await db["roles"].find_one({"_id": to_object_id(rid)})
            if role and role.get("name"):
                names.add(role["name"])
        except Exception:
            continue
    return names


async def get_merged_permissions(role_ids: list[str]) -> list[str]:
    """Merge permission names from multiple roles (union, deduplicated)."""
    if not role_ids:
        return []

    db = get_db()
    all_perms: set[str] = set()

    for rid in role_ids:
        try:
            role = await db["roles"].find_one({"_id": to_object_id(rid)})
            if not role:
                continue
            perm_ids = role.get("permissions", [])
            if not perm_ids:
                continue
            perm_oids = [to_object_id(str(p)) for p in perm_ids]
            async for perm in db["permissions"].find(
                {"_id": {"$in": perm_oids}}
            ):
                name = perm.get("name")
                if name:
                    all_perms.add(name)
        except Exception:
            continue

    return sorted(all_perms)
