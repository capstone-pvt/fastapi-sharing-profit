import re
from datetime import datetime
from typing import Any

from bson import ObjectId
from bson.errors import InvalidId


# Fields that must never be returned to clients
_SENSITIVE_FIELDS = {"password", "refreshToken", "refreshTokenExpiresAt", "sessionId"}


def _encode_value(value: Any) -> Any:
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        # Only apply _id→id renaming if the dict looks like a MongoDB document
        if "_id" in value:
            return serialize_doc(value)
        return {k: _encode_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_encode_value(item) for item in value]
    return value


def serialize_doc(doc: dict[str, Any]) -> dict[str, Any]:
    if not doc:
        return doc
    serialized = {
        key: _encode_value(value)
        for key, value in doc.items()
        if key not in _SENSITIVE_FIELDS
    }
    serialized["id"] = serialized.get("_id", serialized.get("id"))
    serialized.pop("_id", None)
    return serialized


def to_object_id(value: str) -> ObjectId:
    """Convert a string to an ObjectId, raising InvalidId on failure."""
    if not ObjectId.is_valid(value):
        raise InvalidId(f"'{value}' is not a valid ObjectId")
    return ObjectId(value)


def escape_regex(value: str) -> str:
    """Escape a string for safe use in a MongoDB $regex query."""
    return re.escape(value)
