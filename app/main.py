from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from pathlib import Path

from app.db import connect_db, disconnect_db
from app.api.v1 import api_router
from app.core.config import get_settings
from app.seeders.roles_permissions import (
    seed_admin_role_with_all_permissions,
    seed_boat_owner_role_with_permissions,
    seed_broker_role_with_permissions,
    seed_fisherman_role_with_permissions,
)
from app.seeders.users import backfill_default_user_role, seed_default_role_users


load_dotenv()

app = FastAPI(title="Profit Sharing API (FastAPI)")


@app.on_event("startup")
async def startup_event() -> None:
    await connect_db()
    await seed_broker_role_with_permissions()
    await seed_boat_owner_role_with_permissions()
    await seed_fisherman_role_with_permissions()
    await seed_admin_role_with_all_permissions()
    await backfill_default_user_role()
    await seed_default_role_users()


@app.on_event("shutdown")
async def shutdown_event() -> None:
    await disconnect_db()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def health():
    return {"status": "ok"}


app.include_router(api_router)

settings = get_settings()
upload_root = Path(settings.upload_root)
upload_root.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(upload_root)), name="uploads")
