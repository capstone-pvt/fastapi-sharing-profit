from datetime import datetime, timedelta, timezone
from typing import Any

from jose import jwt
from passlib.context import CryptContext

from app.core.config import get_settings


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return pwd_context.verify(password, hashed)


def _parse_expiration(value: str) -> timedelta:
    unit = value[-1]
    amount = int(value[:-1])
    if unit == "m":
        return timedelta(minutes=amount)
    if unit == "h":
        return timedelta(hours=amount)
    if unit == "d":
        return timedelta(days=amount)
    return timedelta(minutes=15)


def create_access_token(payload: dict[str, Any]) -> str:
    settings = get_settings()
    expire = datetime.now(timezone.utc) + _parse_expiration(settings.jwt_expiration)
    to_encode = {**payload, "exp": expire}
    return jwt.encode(to_encode, settings.jwt_secret, algorithm="HS256")


def create_refresh_token(payload: dict[str, Any]) -> str:
    settings = get_settings()
    expire = datetime.now(timezone.utc) + _parse_expiration(settings.jwt_refresh_expiration)
    to_encode = {**payload, "exp": expire}
    return jwt.encode(to_encode, settings.jwt_refresh_secret, algorithm="HS256")
