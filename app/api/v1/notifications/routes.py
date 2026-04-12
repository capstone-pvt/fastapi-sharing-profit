"""Push notification endpoints.

Handles FCM device token registration and provides a utility for sending
notifications to specific users or roles within a company.

Collection: ``device_tokens``

Document schema::

    {
        "userId": str,
        "fcmToken": str,
        "platform": "android" | "ios",
        "companyId": ObjectId | null,
        "updatedAt": datetime,
    }
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Body, Depends

from app.db import get_db
from app.deps import get_current_user
from app.utils import serialize_doc, to_object_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/notifications", tags=["notifications"])

COLLECTION = "device_tokens"


# ── Device registration ─────────────────────────────────────────────

@router.post("/register-device")
async def register_device(
    payload: dict[str, Any] = Body(...),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Register or update an FCM token for the authenticated user's device."""
    db = get_db()
    fcm_token = (payload.get("fcmToken") or "").strip()
    platform = (payload.get("platform") or "android").strip()

    if not fcm_token:
        return {"status": "ignored", "reason": "empty token"}

    user_id = str(user.get("_id") or user.get("id") or "")
    company_id = user.get("companyId")
    now = datetime.now(timezone.utc)

    # Upsert by fcmToken (a single device can only belong to one user)
    await db[COLLECTION].update_one(
        {"fcmToken": fcm_token},
        {
            "$set": {
                "userId": user_id,
                "fcmToken": fcm_token,
                "platform": platform,
                "companyId": company_id,
                "updatedAt": now,
            },
            "$setOnInsert": {"createdAt": now},
        },
        upsert=True,
    )

    return {"status": "registered"}


# ── In-app notification storage ────────────────────────────────────

NOTIF_COLLECTION = "notifications"


@router.get("")
async def list_notifications(
    user: dict[str, Any] = Depends(get_current_user),
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    """List in-app notifications for the current user (newest first)."""
    db = get_db()
    user_id = str(user.get("_id") or user.get("id") or "")
    query = {"userId": user_id}
    cursor = (
        db[NOTIF_COLLECTION]
        .find(query)
        .sort("createdAt", -1)
        .skip(offset)
        .limit(limit)
    )
    results = [serialize_doc(doc) async for doc in cursor]
    total = await db[NOTIF_COLLECTION].count_documents(query)
    unread = await db[NOTIF_COLLECTION].count_documents(
        {**query, "isRead": False}
    )
    return {
        "results": results,
        "total": total,
        "unread": unread,
        "limit": limit,
        "offset": offset,
    }


@router.get("/unread-count")
async def unread_count(
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, int]:
    """Get the unread notification count for the current user."""
    db = get_db()
    user_id = str(user.get("_id") or user.get("id") or "")
    count = await db[NOTIF_COLLECTION].count_documents(
        {"userId": user_id, "isRead": False}
    )
    return {"unread": count}


@router.patch("/{notification_id}/read")
async def mark_as_read(
    notification_id: str,
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Mark a single notification as read."""
    db = get_db()
    user_id = str(user.get("_id") or user.get("id") or "")
    result = await db[NOTIF_COLLECTION].update_one(
        {"_id": to_object_id(notification_id), "userId": user_id},
        {"$set": {"isRead": True, "readAt": datetime.now(timezone.utc)}},
    )
    if result.matched_count == 0:
        return {"status": "not_found"}
    return {"status": "read"}


@router.patch("/read-all")
async def mark_all_read(
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Mark all notifications as read for the current user."""
    db = get_db()
    user_id = str(user.get("_id") or user.get("id") or "")
    result = await db[NOTIF_COLLECTION].update_many(
        {"userId": user_id, "isRead": False},
        {"$set": {"isRead": True, "readAt": datetime.now(timezone.utc)}},
    )
    return {"status": "ok", "marked": result.modified_count}


async def store_notification(
    user_id: str,
    title: str,
    body: str,
    category: str = "general",
    data: dict[str, str] | None = None,
) -> str:
    """Store an in-app notification and return its ID."""
    db = get_db()
    now = datetime.now(timezone.utc)
    doc = {
        "userId": user_id,
        "title": title,
        "body": body,
        "category": category,
        "data": data or {},
        "isRead": False,
        "createdAt": now,
    }
    result = await db[NOTIF_COLLECTION].insert_one(doc)
    return str(result.inserted_id)


# ── Send notification helper (used by other modules) ────────────────

async def send_notification_to_user(
    user_id: str,
    title: str,
    body: str,
    data: dict[str, str] | None = None,
    category: str = "general",
) -> int:
    """Send a push notification and store in-app notification.

    Returns the number of devices notified.
    """
    # Always store in-app notification (even if no FCM tokens)
    try:
        await store_notification(user_id, title, body, category, data)
    except Exception as e:
        logger.warning("Failed to store in-app notification: %s", e)

    db = get_db()
    tokens_cursor = db[COLLECTION].find({"userId": user_id})
    tokens = [doc.get("fcmToken") async for doc in tokens_cursor if doc.get("fcmToken")]

    if not tokens:
        return 0

    sent = 0
    for token in tokens:
        try:
            await _send_fcm_message(token, title, body, data)
            sent += 1
        except Exception as e:
            logger.warning("FCM send failed for token %s: %s", token[:20], e)
            # Remove invalid tokens
            if "not registered" in str(e).lower() or "invalid" in str(e).lower():
                await db[COLLECTION].delete_one({"fcmToken": token})

    return sent


async def send_notification_to_company_role(
    company_id: str | Any,
    role_name: str,
    title: str,
    body: str,
    data: dict[str, str] | None = None,
    exclude_user_id: str | None = None,
) -> int:
    """Send a push notification to all users of a specific role in a company.

    Returns the total number of devices notified.
    """
    db = get_db()

    # Find users with the given role in the company
    role = await db["roles"].find_one({"name": role_name})
    if not role:
        return 0

    role_id = role["_id"]
    user_query: dict[str, Any] = {"role": role_id}

    # Company scoping
    if company_id:
        try:
            oid = to_object_id(str(company_id))
            user_query["companyId"] = {"$in": [oid, str(oid)]}
        except Exception:
            user_query["companyId"] = str(company_id)

    users_cursor = db["users"].find(user_query, {"_id": 1})
    user_ids = [str(u["_id"]) async for u in users_cursor]

    if exclude_user_id:
        user_ids = [uid for uid in user_ids if uid != exclude_user_id]

    sent = 0
    for uid in user_ids:
        sent += await send_notification_to_user(uid, title, body, data)

    return sent


# ── FCM sender ──────────────────────────────────────────────────────

async def _send_fcm_message(
    token: str,
    title: str,
    body: str,
    data: dict[str, str] | None = None,
) -> None:
    """Send a single FCM message using the Firebase Admin SDK or HTTP v1 API.

    Falls back to a no-op if Firebase Admin is not configured (e.g. no
    service account key).  This allows the app to run without FCM in
    development.
    """
    try:
        import firebase_admin  # type: ignore
        from firebase_admin import messaging  # type: ignore

        # Initialize Firebase Admin if not already done
        if not firebase_admin._apps:
            try:
                firebase_admin.initialize_app()
            except Exception:
                logger.info("Firebase Admin not configured — notifications disabled")
                return

        message = messaging.Message(
            notification=messaging.Notification(title=title, body=body),
            data=data or {},
            token=token,
        )
        messaging.send(message)
    except ImportError:
        logger.info("firebase-admin not installed — push notifications disabled")
    except Exception as e:
        logger.warning("FCM send error: %s", e)
        raise
