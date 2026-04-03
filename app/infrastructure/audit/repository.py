"""
Audit logging repository for tracking company assignments and other administrative actions.
"""

from datetime import datetime, timezone
from typing import Any
from bson import ObjectId
from app.db import get_db
from app.utils import serialize_doc


async def create_audit_log(
    action: str,
    entity_type: str,
    entity_id: str | None,
    performed_by: str,
    details: dict[str, Any],
    metadata: dict[str, Any] | None = None
) -> dict[str, Any]:
    """
    Create an audit log entry.

    Args:
        action: The action performed (e.g., "company_assigned", "company_updated")
        entity_type: The type of entity affected (e.g., "user", "company")
        entity_id: The ID of the entity affected
        performed_by: User ID of who performed the action
        details: Additional details about the action
        metadata: Optional metadata (IP address, user agent, etc.)

    Returns:
        The created audit log document
    """
    db = get_db()
    now = datetime.now(timezone.utc)

    audit_doc = {
        "action": action,
        "entityType": entity_type,
        "entityId": entity_id,
        "performedBy": performed_by,
        "performedByObjectId": ObjectId(performed_by) if performed_by else None,
        "details": details,
        "metadata": metadata or {},
        "timestamp": now,
        "createdAt": now,
    }

    result = await db["audit_logs"].insert_one(audit_doc)
    created = await db["audit_logs"].find_one({"_id": result.inserted_id})
    return serialize_doc(created)


async def list_audit_logs(
    query: dict[str, Any] | None = None,
    limit: int = 50,
    offset: int = 0
) -> tuple[list[dict[str, Any]], int]:
    """
    List audit logs with pagination.

    Args:
        query: MongoDB query filter
        limit: Maximum number of results
        offset: Number of results to skip

    Returns:
        Tuple of (results, total_count)
    """
    db = get_db()
    query = query or {}

    # Build aggregation pipeline to include user information
    pipeline = [
        {"$match": query},
        {"$sort": {"timestamp": -1}},
        {"$skip": offset},
        {"$limit": limit},
        {
            "$lookup": {
                "from": "users",
                "localField": "performedByObjectId",
                "foreignField": "_id",
                "as": "performedByUser"
            }
        },
        {
            "$unwind": {
                "path": "$performedByUser",
                "preserveNullAndEmptyArrays": True
            }
        },
        {
            "$project": {
                "_id": 1,
                "action": 1,
                "entityType": 1,
                "entityId": 1,
                "performedBy": 1,
                "details": 1,
                "metadata": 1,
                "timestamp": 1,
                "createdAt": 1,
                "performedByEmail": "$performedByUser.email",
                "performedByName": {
                    "$concat": [
                        "$performedByUser.firstName",
                        " ",
                        "$performedByUser.lastName"
                    ]
                }
            }
        }
    ]

    cursor = db["audit_logs"].aggregate(pipeline)
    results = [serialize_doc(doc) async for doc in cursor]

    total = await db["audit_logs"].count_documents(query)

    return results, total


async def get_audit_log(audit_id: str) -> dict[str, Any] | None:
    """
    Get a single audit log by ID.

    Args:
        audit_id: The audit log ID

    Returns:
        The audit log document or None if not found
    """
    db = get_db()
    try:
        object_id = ObjectId(audit_id)
    except Exception:
        return None

    doc = await db["audit_logs"].find_one({"_id": object_id})
    return serialize_doc(doc) if doc else None


async def get_user_audit_history(
    user_id: str,
    action_filter: str | None = None,
    limit: int = 50,
    offset: int = 0
) -> tuple[list[dict[str, Any]], int]:
    """
    Get audit history for a specific user.

    Args:
        user_id: The user ID
        action_filter: Optional action filter (e.g., "company_assigned")
        limit: Maximum number of results
        offset: Number of results to skip

    Returns:
        Tuple of (results, total_count)
    """
    query: dict[str, Any] = {"entityId": user_id, "entityType": "user"}

    if action_filter:
        query["action"] = action_filter

    return await list_audit_logs(query, limit, offset)


async def get_company_audit_history(
    company_id: str,
    limit: int = 50,
    offset: int = 0
) -> tuple[list[dict[str, Any]], int]:
    """
    Get audit history for a specific company.

    Args:
        company_id: The company ID
        limit: Maximum number of results
        offset: Number of results to skip

    Returns:
        Tuple of (results, total_count)
    """
    query = {"entityId": company_id, "entityType": "company"}
    return await list_audit_logs(query, limit, offset)


async def delete_old_audit_logs(days: int = 90) -> int:
    """
    Delete audit logs older than specified days.

    Args:
        days: Number of days to retain

    Returns:
        Number of deleted documents
    """
    db = get_db()
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

    result = await db["audit_logs"].delete_many({"timestamp": {"$lt": cutoff_date}})
    return result.deleted_count


# Helper function to log company assignments
async def log_company_assignment(
    user_id: str,
    company_id: str,
    company_name: str,
    performed_by_user_id: str,
    old_company_id: str | None = None,
    old_company_name: str | None = None,
    is_bulk: bool = False
) -> dict[str, Any]:
    """
    Log a company assignment action.

    Args:
        user_id: The user ID being assigned
        company_id: The new company ID
        company_name: The new company name
        performed_by_user_id: User ID who performed the action
        old_company_id: Previous company ID (if any)
        old_company_name: Previous company name (if any)
        is_bulk: Whether this is part of a bulk operation

    Returns:
        The created audit log
    """
    details = {
        "newCompanyId": company_id,
        "newCompanyName": company_name,
        "isBulkOperation": is_bulk
    }

    if old_company_id:
        details["oldCompanyId"] = old_company_id
        details["oldCompanyName"] = old_company_name

    return await create_audit_log(
        action="company_assigned",
        entity_type="user",
        entity_id=user_id,
        performed_by=performed_by_user_id,
        details=details
    )


# Import timedelta at the top
from datetime import timedelta
