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


# ── Send notification helper (used by other modules) ────────────────

async def send_notification_to_user(
    user_id: str,
    title: str,
    body: str,
    data: dict[str, str] | None = None,
) -> int:
    """Send a push notification to all devices registered to a user.

    Returns the number of devices notified.
    """
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
