from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.db import get_db
from app.deps import get_current_user
from app.utils import serialize_doc


router = APIRouter(prefix="/fish", tags=["fish"])


@router.post("/analyze")
async def analyze_fish(
    image: UploadFile = File(...),
    user: dict[str, Any] = Depends(get_current_user),
):
    if not image:
        raise HTTPException(status_code=400, detail="Image file is required")
    analysis = {
        "userId": user["id"],
        "createdAt": datetime.utcnow(),
        "detections": [],
        "message": "ML pipeline not implemented in FastAPI yet",
    }
    db = get_db()
    result = await db["fish_analyses"].insert_one(analysis)
    stored = await db["fish_analyses"].find_one({"_id": result.inserted_id})
    return serialize_doc(stored)


@router.get("/analytics")
async def analytics(user: dict[str, Any] = Depends(get_current_user)):
    db = get_db()
    total = await db["fish_analyses"].count_documents({})
    mine = await db["fish_analyses"].count_documents({"userId": user["id"]})
    return {"totalAnalyses": total, "userAnalyses": mine}


@router.get("/analysis-history")
async def analysis_history(user: dict[str, Any] = Depends(get_current_user)):
    db = get_db()
    cursor = db["fish_analyses"].find({"userId": user["id"]}).sort("createdAt", -1)
    results = [serialize_doc(doc) async for doc in cursor]
    return results
