"""Role-profile endpoints — the role-specific KYC step performed after
registration and before admin verification.

Endpoints:
    GET    /role-profiles/me                       — fetch own profile
    PUT    /role-profiles/me                       — upsert own profile
    POST   /role-profiles/me/documents             — multipart upload
    DELETE /role-profiles/me/documents/{doc_id}    — remove own document
    GET    /role-profiles/{user_id}                — admin view of another user's profile
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import (
    APIRouter,
    Body,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
)

from app.deps import get_current_user, require_permissions
from app.domain.role_profiles.services import (
    DOCUMENT_TYPES,
    append_document,
    build_role_profile_update,
    remove_document,
    validate_document_metadata,
    validate_role_profile,
)
from app.infrastructure.role_profiles.repository import (
    get_user_for_role_profile,
    replace_role_documents,
    update_user_role_profile,
)
from app.infrastructure.role_profiles.storage import (
    delete_role_document,
    save_role_document,
)
from app.utils import serialize_doc


router = APIRouter(prefix="/role-profiles", tags=["role-profiles"])


MAX_DOCUMENT_BYTES = 10 * 1024 * 1024  # 10 MB per document


def _serialize(user: dict[str, Any]) -> dict[str, Any]:
    """Project the bits of the user doc the client actually needs."""
    return {
        "userId": str(user.get("_id") or user.get("id") or ""),
        "roleProfile": user.get("roleProfile") or {
            "broker": None,
            "owner": None,
            "crew": None,
            "documents": [],
        },
        "profileCompleted": bool(user.get("profileCompleted", False)),
        "verificationStatus": user.get("verificationStatus", "pending"),
        "verifiedAt": user.get("verifiedAt"),
        "verifiedBy": user.get("verifiedBy"),
        "rejectedAt": user.get("rejectedAt"),
        "rejectedReason": user.get("rejectedReason"),
    }


@router.get("/me")
async def get_my_role_profile(
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    raw = await get_user_for_role_profile(user["id"])
    if not raw:
        raise HTTPException(status_code=404, detail="User not found")
    return _serialize(serialize_doc(raw))


@router.put("/me")
async def upsert_my_role_profile(
    payload: dict[str, Any] = Body(...),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    role = payload.get("role")
    profile = payload.get("profile") or {}
    if not isinstance(role, str):
        raise HTTPException(status_code=400, detail="role is required")
    try:
        role, normalized = validate_role_profile(role, profile)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    raw = await get_user_for_role_profile(user["id"])
    if not raw:
        raise HTTPException(status_code=404, detail="User not found")

    update = build_role_profile_update(serialize_doc(raw), role, normalized)
    updated = await update_user_role_profile(user["id"], update)
    if not updated:
        raise HTTPException(status_code=500, detail="Failed to update profile")
    return _serialize(updated)


@router.post("/me/documents")
async def upload_my_document(
    file: UploadFile = File(...),
    document_type: str = Form(...),
    issue_date: str | None = Form(None),
    expiry_date: str | None = Form(None),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    # Metadata validation
    try:
        metadata = validate_document_metadata(
            {
                "type": document_type,
                "issueDate": issue_date,
                "expiryDate": expiry_date,
            }
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # Read + size guard
    blob = await file.read()
    if len(blob) == 0:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(blob) > MAX_DOCUMENT_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds {MAX_DOCUMENT_BYTES // (1024 * 1024)} MB limit",
        )

    try:
        url = save_role_document(user["id"], blob, file.filename or "document")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    document = {
        "id": uuid.uuid4().hex,
        "type": metadata["type"],
        "issueDate": metadata["issueDate"],
        "expiryDate": metadata["expiryDate"],
        "fileUrl": url,
        "fileName": file.filename or "document",
        "verificationStatus": "pending",
        "uploadedAt": datetime.now(timezone.utc),
    }

    raw = await get_user_for_role_profile(user["id"])
    if not raw:
        raise HTTPException(status_code=404, detail="User not found")
    docs = append_document(serialize_doc(raw), document)
    updated = await replace_role_documents(user["id"], docs)
    if not updated:
        raise HTTPException(status_code=500, detail="Failed to record document")
    return {"document": document, "profile": _serialize(updated)}


@router.delete("/me/documents/{doc_id}")
async def delete_my_document(
    doc_id: str,
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    raw = await get_user_for_role_profile(user["id"])
    if not raw:
        raise HTTPException(status_code=404, detail="User not found")
    serialized = serialize_doc(raw)
    existing_docs = (serialized.get("roleProfile") or {}).get("documents") or []
    target = next((d for d in existing_docs if d.get("id") == doc_id), None)
    if not target:
        raise HTTPException(status_code=404, detail="Document not found")

    docs = remove_document(serialized, doc_id)
    updated = await replace_role_documents(user["id"], docs)
    if not updated:
        raise HTTPException(status_code=500, detail="Failed to remove document")
    # Best-effort filesystem cleanup.
    if isinstance(target.get("fileUrl"), str):
        delete_role_document(target["fileUrl"])
    return {"profile": _serialize(updated)}


@router.get(
    "/{user_id}",
    dependencies=[Depends(require_permissions("user:read"))],
)
async def get_role_profile_for_admin(user_id: str) -> dict[str, Any]:
    raw = await get_user_for_role_profile(user_id)
    if not raw:
        raise HTTPException(status_code=404, detail="User not found")
    return _serialize(serialize_doc(raw))


@router.get("/meta/document-types")
async def list_document_types() -> dict[str, list[str]]:
    return {"documentTypes": list(DOCUMENT_TYPES)}
