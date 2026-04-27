"""
Audit log API endpoints.
Allows administrators to view audit logs for company assignments and other actions.
"""

from datetime import datetime
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from app.deps import get_current_user, require_permissions
from app.role_utils import get_user_role_names
from app.infrastructure.audit.repository import (
    list_audit_logs,
    get_audit_log,
    get_user_audit_history,
    get_company_audit_history
)


router = APIRouter(prefix="/audit-logs", tags=["audit"])

# Government regulators get cross-company read-only access to audit logs —
# the trail is the regulator's primary tool for tracking transactions and
# was flagged as "Very Important" in the gov-admin feedback brief.
AUDIT_READER_ROLE_NAMES = {"super", "admin", "government"}


async def _can_read_audit(user: dict[str, Any]) -> bool:
    raw_names = await get_user_role_names(user)
    # Lowercase to match `AUDIT_READER_ROLE_NAMES` regardless of how the
    # role names are persisted (mixed-case `Government` in some seed sets,
    # canonical `government` in others).
    names = {str(n).strip().lower() for n in raw_names}
    return bool(names & AUDIT_READER_ROLE_NAMES)


@router.get("", dependencies=[Depends(require_permissions("audit:read"))])
async def list_audit(
    request: Request,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    action: str | None = Query(None),
    entity_type: str | None = Query(None),
    entity_id: str | None = Query(None),
    performed_by: str | None = Query(
        None, description="User id of the actor"
    ),
    actor_search: str | None = Query(
        None, description="Substring match against actor name/email"
    ),
    start_date: str | None = Query(
        None, description="ISO date (yyyy-mm-dd) — inclusive lower bound"
    ),
    end_date: str | None = Query(
        None, description="ISO date (yyyy-mm-dd) — inclusive upper bound"
    ),
    user: dict[str, Any] = Depends(get_current_user),
):
    """
    List audit logs with filtering options.
    Admins, super admins, and government regulators can read.
    """
    if not await _can_read_audit(user):
        raise HTTPException(status_code=403, detail="Audit access required")

    query: dict[str, Any] = {}

    if action:
        query["action"] = action

    if entity_type:
        query["entityType"] = entity_type

    if entity_id:
        query["entityId"] = entity_id

    if performed_by:
        query["performedBy"] = performed_by

    if actor_search:
        # Case-insensitive substring match against either name or email.
        # Mongo treats $regex on the same key with $or as expected.
        pattern = {"$regex": actor_search, "$options": "i"}
        query["$or"] = [
            {"performedByName": pattern},
            {"performedByEmail": pattern},
        ]

    # Inclusive date range. Filter on `timestamp` since that's the action
    # time; createdAt is the row write-time and can drift slightly.
    date_filter: dict[str, Any] = {}
    if start_date:
        try:
            datetime.strptime(start_date, "%Y-%m-%d")
            date_filter["$gte"] = f"{start_date}T00:00:00"
        except ValueError:
            raise HTTPException(
                status_code=400, detail="start_date must be yyyy-mm-dd"
            )
    if end_date:
        try:
            datetime.strptime(end_date, "%Y-%m-%d")
            date_filter["$lte"] = f"{end_date}T23:59:59.999"
        except ValueError:
            raise HTTPException(
                status_code=400, detail="end_date must be yyyy-mm-dd"
            )
    if date_filter:
        query["timestamp"] = date_filter

    results, total = await list_audit_logs(query, limit=limit, offset=offset)
    return {"results": results, "total": total, "limit": limit, "offset": offset}


@router.get("/{audit_id}", dependencies=[Depends(require_permissions("audit:read"))])
async def get_audit(
    audit_id: str,
    user: dict[str, Any] = Depends(get_current_user)
):
    """
    Get a single audit log by ID.
    Only admins and super admins can access audit logs.
    """
    if not await _can_read_audit(user):
        raise HTTPException(status_code=403, detail="Audit access required")

    doc = await get_audit_log(audit_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Audit log not found")

    return doc


@router.get("/user/{user_id}", dependencies=[Depends(require_permissions("audit:read"))])
async def get_user_audit(
    user_id: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    action: str | None = Query(None),
    user: dict[str, Any] = Depends(get_current_user),
):
    """
    Get audit history for a specific user.
    Only admins and super admins can access audit logs.
    """
    if not await _can_read_audit(user):
        raise HTTPException(status_code=403, detail="Audit access required")

    results, total = await get_user_audit_history(
        user_id,
        action_filter=action,
        limit=limit,
        offset=offset
    )

    return {"results": results, "total": total, "limit": limit, "offset": offset}


@router.get("/company/{company_id}", dependencies=[Depends(require_permissions("audit:read"))])
async def get_company_audit(
    company_id: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: dict[str, Any] = Depends(get_current_user),
):
    """
    Get audit history for a specific company.
    Only admins and super admins can access audit logs.
    """
    if not await _can_read_audit(user):
        raise HTTPException(status_code=403, detail="Audit access required")

    results, total = await get_company_audit_history(
        company_id,
        limit=limit,
        offset=offset
    )

    return {"results": results, "total": total, "limit": limit, "offset": offset}
