import os
from pathlib import Path
from urllib.parse import urlparse
from functools import lru_cache

# Project root directory (profit_sharing_api_fastapi/)
BASE_DIR = Path(__file__).resolve().parent.parent.parent


def _resolve_path(env_var: str, default_relative: str) -> str:
    """Resolve a path from env var. If relative, resolve against BASE_DIR."""
    raw = os.getenv(env_var, default_relative)
    if not raw:
        return ""
    p = Path(raw)
    if p.is_absolute():
        return str(p)
    return str(BASE_DIR / p)


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
    upload_root = _resolve_path("UPLOAD_ROOT", "uploads")
    model_root = _resolve_path("MODEL_ROOT", "app/models")
    classifier_model_path = _resolve_path("CLASSIFIER_MODEL_PATH", "app/models/classifier/best.pt")
    weight_model_path = _resolve_path("WEIGHT_MODEL_PATH", "app/models/weight/weight_model.joblib")
    price_model_path = _resolve_path("PRICE_MODEL_PATH", "app/models/price/price_model.joblib")
    detector_model_path = _resolve_path("DETECTOR_MODEL_PATH", "app/models/detector/best.pt")
    detector_confidence = float(os.getenv("DETECTOR_CONFIDENCE", "0.25"))
    detector_iou = float(os.getenv("DETECTOR_IOU", "0.45"))
    size_small_max_kg = float(os.getenv("SIZE_SMALL_MAX_KG", "0.5"))
    size_medium_max_kg = float(os.getenv("SIZE_MEDIUM_MAX_KG", "1.5"))
    openweather_api_key = os.getenv("OPENWEATHER_API_KEY", "")


@lru_cache()
def get_settings() -> Settings:
    return Settings()
