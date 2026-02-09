"""
Bulk company assignment endpoint for users.
This can be integrated into the main users routes file.
"""

from typing import Any
from fastapi import Body, Depends, HTTPException
from app.deps import get_current_user, require_permissions
from app.infrastructure.users.repository import (
    get_user as repo_get_user,
    update_user as repo_update_user,
)
from app.db import get_db
from app.utils import to_object_id


async def _get_role_name(user: dict[str, Any]) -> str:
    from app.infrastructure.roles.repository import get_role
    role_value = user.get("role")
    if isinstance(role_value, dict):
        role_name = role_value.get("name")
        if role_name:
            return str(role_name)
        role_value = role_value.get("id")
    if not role_value:
        role_value = user.get("roleId")
    if not role_value:
        return ""
    role = await get_role(str(role_value))
    return str(role.get("name") or "") if role else ""


async def _get_role_flags(user: dict[str, Any]) -> tuple[str, bool, bool]:
    # Canonical role names: super | admin | broker | owner | crew | user
    SUPER_ROLE_NAMES = {"super"}
    ADMIN_ROLE_NAMES = {"admin"}
    role_name = (await _get_role_name(user)).strip().lower()
    is_super = role_name in SUPER_ROLE_NAMES
    is_company_admin = role_name in ADMIN_ROLE_NAMES
    return role_name, is_super, is_company_admin


# This function should be added to the users router
async def bulk_assign_company(
    payload: dict[str, Any] = Body(...),
    user: dict[str, Any] = Depends(get_current_user),
):
    """
    Bulk assign a company to multiple users.
    Only super admins can use this endpoint.

    Payload:
    {
        "userIds": ["user_id_1", "user_id_2", ...],
        "companyId": "company_id"
    }

    Returns:
    {
        "status": "completed",
        "totalRequested": 5,
        "successCount": 4,
        "failedCount": 1,
        "updatedUsers": [...],
        "failedUsers": [...],
        "companyAssigned": {"id": "...", "name": "..."}
    }
    """
    _, is_super, is_company_admin = await _get_role_flags(user)

    # Only super admins can bulk assign companies
    if not is_super:
        raise HTTPException(
            status_code=403,
            detail="Only super admins can perform bulk company assignments"
        )

    user_ids = payload.get("userIds", [])
    company_id = payload.get("companyId")

    # Validate input
    if not user_ids or not isinstance(user_ids, list):
        raise HTTPException(status_code=400, detail="userIds must be a non-empty array")

    if not company_id:
        raise HTTPException(status_code=400, detail="companyId is required")

    # Validate company exists
    db = get_db()
    try:
        company_object_id = to_object_id(company_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid companyId format")

    company = await db["companies"].find_one({"_id": company_object_id})
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    # Update users
    success_count = 0
    failed_users = []
    updated_users = []

    for user_id in user_ids:
        try:
            target_user = await repo_get_user(user_id)
            if not target_user:
                failed_users.append({"userId": user_id, "reason": "User not found"})
                continue

            # Prepare update payload with company information
            update_payload = {
                "companyId": company_object_id,
                "companyName": company.get("companyName"),
                "companyAddress": company.get("companyAddress"),
                "companyPhone": company.get("companyPhone"),
                "companyTaxId": company.get("companyTaxId"),
            }

            doc = await repo_update_user(user_id, update_payload)
            if doc:
                success_count += 1
                updated_users.append({
                    "userId": user_id,
                    "email": doc.get("email"),
                    "companyName": doc.get("companyName")
                })
            else:
                failed_users.append({"userId": user_id, "reason": "Update failed"})
        except Exception as e:
            failed_users.append({"userId": user_id, "reason": str(e)})

    return {
        "status": "completed",
        "totalRequested": len(user_ids),
        "successCount": success_count,
        "failedCount": len(failed_users),
        "updatedUsers": updated_users,
        "failedUsers": failed_users,
        "companyAssigned": {
            "id": company_id,
            "name": company.get("companyName")
        }
    }


# To integrate this into routes.py, add this line to the router:
# @router.post("/bulk-assign-company", dependencies=[Depends(require_permissions("user:update"))])
# And then add the bulk_assign_company function
