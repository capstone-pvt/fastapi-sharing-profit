import os
from urllib.parse import urlparse
from functools import lru_cache


def _infer_db_name(uri: str) -> str | None:
    try:
        parsed = urlparse(uri)
        if parsed.path and parsed.path != "/":
            return parsed.path.lstrip("/")
    except Exception:
        return None
    return None


class Settings:
    app_name = "profit_sharing_api_fastapi"
    mongodb_uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    database_name = os.getenv("DATABASE_NAME") or _infer_db_name(mongodb_uri) or "profit_sharing_db"
    jwt_secret = os.getenv("JWT_SECRET", "change-me")
    jwt_refresh_secret = os.getenv("JWT_REFRESH_SECRET", "change-me-refresh")
    jwt_expiration = os.getenv("JWT_EXPIRATION", "15m")
    jwt_refresh_expiration = os.getenv("JWT_REFRESH_EXPIRATION", "7d")
    jwt_refresh_expiration_days = int(
        os.getenv("JWT_REFRESH_EXPIRATION_DAYS", "7")
    )
    upload_root = os.getenv("UPLOAD_ROOT", "uploads")
    model_root = os.getenv("MODEL_ROOT", "models")


@lru_cache()
def get_settings() -> Settings:
    return Settings()
