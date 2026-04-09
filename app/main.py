import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from pathlib import Path

from app.db import connect_db, disconnect_db, get_db
from app.api.v1 import api_router
from app.core.config import get_settings
from app.seeders.roles_permissions import (
    seed_admin_role_with_all_permissions,
    seed_boat_owner_role_with_permissions,
    seed_broker_role_with_permissions,
    seed_fisherman_role_with_permissions,
)
from app.seeders.users import backfill_default_user_role, seed_default_role_users
from app.seeders.companies import seed_default_companies
from app.seeders.licenses import seed_default_licenses
from app.seeders.fish_models import seed_fish_models, seed_fish_species
from app.infrastructure.fish.inference import preload_models

logger = logging.getLogger(__name__)

env_path = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(env_path)

settings = get_settings()

# Track model preload status for health checks
_models_loaded: dict[str, bool] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown logic."""
    global _models_loaded
    # Startup
    await connect_db()
    await seed_broker_role_with_permissions()
    await seed_boat_owner_role_with_permissions()
    await seed_fisherman_role_with_permissions()
    await seed_admin_role_with_all_permissions()
    await backfill_default_user_role()
    _, companies_by_key = await seed_default_companies()
    await seed_default_licenses(companies_by_key)
    await seed_default_role_users()
    await seed_fish_species()
    await seed_fish_models()
    _models_loaded = preload_models()
    logger.info("Application startup complete")
    yield
    # Shutdown
    await disconnect_db()
    logger.info("Application shutdown complete")


app = FastAPI(title="Profit Sharing API (FastAPI)", lifespan=lifespan)

_origins = settings.allowed_origins
_use_wildcard = _origins == ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=not _use_wildcard,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {"status": "ok", "service": "profit-sharing-api"}


@app.get("/health")
async def health_check():
    """Health endpoint that verifies MongoDB connectivity and model status."""
    health: dict = {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "models": _models_loaded,
    }
    # Check MongoDB connectivity
    try:
        db = get_db()
        await db.command("ping")
        health["database"] = "connected"
    except Exception as e:
        health["status"] = "degraded"
        health["database"] = f"error: {str(e)}"

    status_code = 200 if health["status"] == "ok" else 503
    from fastapi.responses import JSONResponse
    return JSONResponse(content=health, status_code=status_code)


app.include_router(api_router)

upload_root = Path(settings.upload_root)
upload_root.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(upload_root)), name="uploads")
