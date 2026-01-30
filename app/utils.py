from datetime import datetime
from typing import Any

from bson import ObjectId


def _encode_value(value: Any) -> Any:
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return serialize_doc(value)
    if isinstance(value, list):
        return [_encode_value(item) for item in value]
    return value


def serialize_doc(doc: dict[str, Any]) -> dict[str, Any]:
    if not doc:
        return doc
    serialized = {key: _encode_value(value) for key, value in doc.items()}
    serialized["id"] = serialized.get("_id", serialized.get("id"))
    serialized.pop("_id", None)
    return serialized


def to_object_id(value: str) -> ObjectId:
    return ObjectId(value)
