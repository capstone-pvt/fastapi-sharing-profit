from datetime import datetime
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from bson.errors import InvalidId

from app.db import get_db
from app.deps import get_current_user, require_permissions
from app.infrastructure.roles.repository import get_role
from app.utils import serialize_doc, to_object_id


router = APIRouter(prefix="/companies", tags=["companies"])

SUPER_ROLE_NAMES = {"super", "superadmin", "super admin", "super-admin"}
ADMIN_ROLE_NAMES = {"admin", "system admin"}


async def _get_role_name(user: dict[str, Any]) -> str:
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


async def _get_role_flags(user: dict[str, Any]) -> tuple[bool, bool]:
    role_name = (await _get_role_name(user)).strip().lower()
    is_super = role_name in SUPER_ROLE_NAMES
    is_company_admin = role_name in ADMIN_ROLE_NAMES
    return is_super, is_company_admin


def _company_id_value(data: dict[str, Any]) -> str | None:
    company_id = data.get("companyId")
    return str(company_id) if company_id else None


@router.get("", dependencies=[Depends(require_permissions("companies:read"))])
async def list_companies(
    limit: int = Query(200, ge=1, le=500),
    offset: int = Query(0, ge=0),
    search: str | None = Query(None),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    db = get_db()
    query: dict[str, Any] = {}
    is_super, is_company_admin = await _get_role_flags(user)
    if is_company_admin and not is_super:
        company_id = _company_id_value(user)
        if not company_id:
            return {"results": [], "total": 0, "limit": limit, "offset": offset}
        try:
            query["_id"] = to_object_id(company_id)
        except InvalidId:
            return {"results": [], "total": 0, "limit": limit, "offset": offset}
    if search:
        query["companyName"] = {"$regex": search, "$options": "i"}
    cursor = (
        db["companies"]
        .find(query)
        .sort("companyName", 1)
        .skip(offset)
        .limit(limit)
    )
    results = [serialize_doc(doc) async for doc in cursor]
    total = await db["companies"].count_documents(query)
    return {"results": results, "total": total, "limit": limit, "offset": offset}


@router.post("", dependencies=[Depends(require_permissions("companies:create"))])
async def create_company(
    payload: dict[str, Any] = Body(...),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    is_super, is_company_admin = await _get_role_flags(user)
    if is_company_admin and not is_super:
        raise HTTPException(status_code=403, detail="Forbidden")
    name = (payload.get("companyName") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="companyName is required")
    now = datetime.utcnow()
    db = get_db()
    existing = await db["companies"].find_one(
        {"companyName": {"$regex": f"^{name}$", "$options": "i"}}
    )
    if existing:
        await db["companies"].update_one(
            {"_id": existing["_id"]},
            {
                "$set": {
                    "companyName": name,
                    "companyCode": payload.get("companyCode"),
                    "companyAddress": payload.get("companyAddress"),
                    "companyPhone": payload.get("companyPhone"),
                    "companyTaxId": payload.get("companyTaxId"),
                    "updatedAt": now,
                }
            },
        )
        doc = await db["companies"].find_one({"_id": existing["_id"]})
        return serialize_doc(doc)

    doc = {
        "companyName": name,
        "companyCode": payload.get("companyCode"),
        "companyAddress": payload.get("companyAddress"),
        "companyPhone": payload.get("companyPhone"),
        "companyTaxId": payload.get("companyTaxId"),
        "createdAt": now,
        "updatedAt": now,
    }
    result = await db["companies"].insert_one(doc)
    created = await db["companies"].find_one({"_id": result.inserted_id})
    return serialize_doc(created)


@router.patch("/{company_id}", dependencies=[Depends(require_permissions("companies:update"))])
async def update_company(
    company_id: str,
    payload: dict[str, Any] = Body(...),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    db = get_db()
    is_super, is_company_admin = await _get_role_flags(user)
    try:
        object_id = to_object_id(company_id)
    except InvalidId:
        raise HTTPException(status_code=404, detail="Company not found")
    if is_company_admin and not is_super:
        user_company_id = _company_id_value(user)
        if not user_company_id or user_company_id != str(object_id):
            raise HTTPException(status_code=403, detail="Forbidden")
    payload["updatedAt"] = datetime.utcnow()
    await db["companies"].update_one({"_id": object_id}, {"$set": payload})
    doc = await db["companies"].find_one({"_id": object_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Company not found")
    return serialize_doc(doc)


@router.delete(
    "/{company_id}", dependencies=[Depends(require_permissions("companies:delete"))]
)
async def delete_company(
    company_id: str, user: dict[str, Any] = Depends(get_current_user)
) -> dict[str, Any]:
    db = get_db()
    is_super, is_company_admin = await _get_role_flags(user)
    try:
        object_id = to_object_id(company_id)
    except InvalidId:
        raise HTTPException(status_code=404, detail="Company not found")
    if is_company_admin and not is_super:
        user_company_id = _company_id_value(user)
        if not user_company_id or user_company_id != str(object_id):
            raise HTTPException(status_code=403, detail="Forbidden")
    result = await db["companies"].delete_one({"_id": object_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Company not found")
    return {"status": "deleted"}
