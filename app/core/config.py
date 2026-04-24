import os
from pathlib import Path
from urllib.parse import urlparse
from functools import lru_cache
from dotenv import load_dotenv

# Project root directory (profit_sharing_api_fastapi/)
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Load .env before any os.getenv() calls
load_dotenv(BASE_DIR / ".env")

# Weak default values that must never reach production
_INSECURE_JWT_DEFAULTS = {"", "change-me", "change-me-refresh"}
_JWT_MIN_LENGTH = 32


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


def _parse_cors_origins(raw: str) -> list[str]:
    """Parse a comma-separated list of allowed origins from env."""
    return [o.strip() for o in raw.split(",") if o.strip()]


class Settings:
    app_name = "profit_sharing_api_fastapi"
    mongodb_uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    database_name = os.getenv("DATABASE_NAME") or _infer_db_name(mongodb_uri) or "smart_catch"
    jwt_secret = os.getenv("JWT_SECRET", "")
    jwt_refresh_secret = os.getenv("JWT_REFRESH_SECRET", "")
    jwt_expiration = os.getenv("JWT_EXPIRATION", "15m")
    jwt_refresh_expiration = os.getenv("JWT_REFRESH_EXPIRATION", "7d")
    jwt_refresh_expiration_days = int(
        os.getenv("JWT_REFRESH_EXPIRATION_DAYS", "7")
    )
    # CORS: comma-separated list of allowed origins.
    # Use "*" only for fully public, non-credentialed APIs.
    # Example: ALLOWED_ORIGINS=https://app.example.com,https://admin.example.com
    allowed_origins: list[str] = _parse_cors_origins(
        os.getenv("ALLOWED_ORIGINS", "http://localhost:3000")
    )
    upload_root = _resolve_path("UPLOAD_ROOT", "uploads")
    model_root = _resolve_path("MODEL_ROOT", "app/models")
    classifier_model_path = _resolve_path("CLASSIFIER_MODEL_PATH", "app/models/classifier/best.pt")
    weight_model_path = _resolve_path("WEIGHT_MODEL_PATH", "app/models/weight/weight_model.joblib")
    price_model_path = _resolve_path("PRICE_MODEL_PATH", "app/models/price/price_model.joblib")
    detector_model_path = _resolve_path("DETECTOR_MODEL_PATH", "app/models/detector/best.pt")
    detector_confidence = float(os.getenv("DETECTOR_CONFIDENCE", "0.25"))
    detector_iou = float(os.getenv("DETECTOR_IOU", "0.45"))
    # Minimum classifier confidence to accept a species prediction.
    # Below this threshold the image is rejected as "no fish detected".
    # Raise this value (e.g. 0.5) to be stricter; lower it to be more permissive.
    classifier_min_confidence = float(os.getenv("CLASSIFIER_MIN_CONFIDENCE", "0.40"))
    size_small_max_kg = float(os.getenv("SIZE_SMALL_MAX_KG", "0.5"))
    size_medium_max_kg = float(os.getenv("SIZE_MEDIUM_MAX_KG", "1.5"))
    openweather_api_key = os.getenv("OPENWEATHER_API_KEY", "")
    storage_backend = os.getenv("STORAGE_BACKEND", "local")
    cloudinary_url = os.getenv("CLOUDINARY_URL", "")
    # When false, skip seeding fish species, fish models, and demo transactions
    # at startup. Auth data (roles, permissions, users, companies, licenses)
    # still seeds so the app remains usable.
    seed_on_startup = os.getenv("SEED_ON_STARTUP", "true").lower() in (
        "1", "true", "yes", "on",
    )


def _validate_settings(s: Settings) -> None:
    """Fail fast at startup if critical configuration is missing or insecure."""
    errors: list[str] = []
    if s.jwt_secret in _INSECURE_JWT_DEFAULTS or len(s.jwt_secret) < _JWT_MIN_LENGTH:
        errors.append(
            f"JWT_SECRET must be set to a random string of at least {_JWT_MIN_LENGTH} characters. "
            "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
        )
    if s.jwt_refresh_secret in _INSECURE_JWT_DEFAULTS or len(s.jwt_refresh_secret) < _JWT_MIN_LENGTH:
        errors.append(
            f"JWT_REFRESH_SECRET must be set to a random string of at least {_JWT_MIN_LENGTH} characters."
        )
    if errors:
        raise RuntimeError(
            "Application cannot start due to insecure configuration:\n"
            + "\n".join(f"  - {e}" for e in errors)
        )


@lru_cache()
def get_settings() -> Settings:
    s = Settings()
    _validate_settings(s)
    return s
