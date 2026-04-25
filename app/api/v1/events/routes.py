"""Server-Sent Events stream for real-time dashboard updates.

The web app opens one long-lived ``GET /api/events/stream`` connection per
tab. We watch MongoDB change streams on the collections the mobile app's
offline queue drains into, then emit small SSE events such as

    event: change
    data: {"collection":"catches","operationType":"insert"}

so the frontend can target which React Query keys to invalidate. Heartbeats
keep the connection alive through proxies. Multi-tenant scoping uses the
authenticated user's ``companyId``.

Auth note: ``EventSource`` cannot set custom headers, so this endpoint also
accepts the JWT via the ``token`` query parameter.

Graceful degradation: change streams require a MongoDB replica set. If the
local Mongo is a standalone, the watcher tasks will fail fast and the stream
just sends heartbeats — the frontend's existing 30s polling is the safety
net, so this is purely additive.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, AsyncIterator

from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from jose import JWTError, jwt

from app.core.config import get_settings
from app.db import get_db
from app.utils import serialize_doc, to_object_id


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/events", tags=["events"])


# Collections the mobile app pushes to (and the web should reflect).
WATCHED_COLLECTIONS = (
    "catches",
    "fish_sales",
    "cash_advances",
    "profit_shares",
    "fish_training_samples",
    "trips",
    "fish_analysis",
)

# Heartbeat cadence — under most reverse-proxy idle timeouts (60-90s).
HEARTBEAT_INTERVAL_SECONDS = 25.0


async def _resolve_user_from_token(token: str) -> dict[str, Any]:
    """Decode the JWT and load the user. Mirrors :func:`get_current_user` but
    lets us authenticate from a query string instead of a header (which
    ``EventSource`` cannot send)."""
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED) from exc

    user_id = payload.get("sub")
    session_id = payload.get("sid")
    if not user_id or not session_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

    db = get_db()
    doc = await db["users"].find_one({"_id": to_object_id(user_id)})
    if not doc or doc.get("sessionId") != session_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    return serialize_doc(doc)


async def _watch_collection(
    collection: str,
    queue: asyncio.Queue[dict[str, Any]],
    company_oid: Any | None,
) -> None:
    """Run ``collection.watch()`` and push change events into ``queue``.
    On failure (e.g. standalone Mongo without change streams) it logs and
    exits — the stream survives via heartbeats."""
    db = get_db()
    pipeline: list[dict[str, Any]] = []
    if company_oid is not None:
        # Match writes scoped to the caller's company. fullDocument is
        # populated on insert and via updateLookup for updates/replaces;
        # delete events expose only documentKey so we always emit those.
        pipeline.append(
            {
                "$match": {
                    "$or": [
                        {"fullDocument.companyId": company_oid},
                        {"fullDocument.companyId": str(company_oid)},
                        {"operationType": "delete"},
                    ]
                }
            }
        )

    try:
        async with db[collection].watch(
            pipeline, full_document="updateLookup"
        ) as stream:
            async for change in stream:
                await queue.put(
                    {
                        "collection": collection,
                        "operationType": change.get("operationType"),
                    }
                )
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        # Most likely "The $changeStream stage is only supported on replica
        # sets" against a standalone local Mongo. Don't crash the whole
        # stream — just back off this collection.
        logger.warning(
            "events: change stream for '%s' unavailable (%s); skipping.",
            collection,
            exc,
        )


async def _event_generator(
    request: Request, company_oid: Any | None
) -> AsyncIterator[bytes]:
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    watchers: list[asyncio.Task[None]] = []

    for coll in WATCHED_COLLECTIONS:
        watchers.append(
            asyncio.create_task(_watch_collection(coll, queue, company_oid))
        )

    try:
        # Tell the client we're ready (frontend can start invalidating fresh).
        yield b"event: ready\ndata: {}\n\n"

        while True:
            if await request.is_disconnected():
                break

            try:
                evt = await asyncio.wait_for(
                    queue.get(), timeout=HEARTBEAT_INTERVAL_SECONDS
                )
            except asyncio.TimeoutError:
                # SSE comment line — keeps proxies/load balancers from
                # idling the connection out without becoming a real event.
                yield b": heartbeat\n\n"
                continue

            payload = json.dumps(evt, separators=(",", ":"))
            yield f"event: change\ndata: {payload}\n\n".encode("utf-8")
    finally:
        for task in watchers:
            task.cancel()
        # Don't await: cancellation is enough; awaiting could block shutdown.


@router.get("/stream")
async def stream(
    request: Request,
    token: str = Query(..., description="JWT access token"),
):
    """Long-lived Server-Sent Events stream of write events visible to the
    authenticated user's company. Use ``EventSource('/api/events/stream?token=…')``
    on the frontend.
    """
    user = await _resolve_user_from_token(token)
    raw_company = user.get("companyId")
    company_oid: Any | None = None
    if raw_company:
        try:
            company_oid = to_object_id(str(raw_company))
        except Exception:
            company_oid = raw_company

    return StreamingResponse(
        _event_generator(request, company_oid),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            # Disable buffering on common reverse proxies (nginx, render).
            "X-Accel-Buffering": "no",
        },
    )
