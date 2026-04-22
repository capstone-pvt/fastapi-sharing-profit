"""
Role-specific profile completion.

Every user registered as a broker / vessel owner / crew member must complete a
role-specific KYC-style profile before an admin can verify their account.
This module holds validation and payload normalization logic; the actual DB
and HTTP layers live in app.infrastructure.role_profiles and app.api.v1.

Design notes
============
* A single `roleProfile` sub-document lives on the user record so we don't
  need a new collection. Each supported role has its own key:
    roleProfile.broker   -> broker-specific fields
    roleProfile.owner    -> vessel-owner fields
    roleProfile.crew     -> fishing-crew fields (incl. the captain-is-owner
                            variant, which just sets crew.captainIsOwner=True)
  Uploaded documents live under roleProfile.documents (a flat list) so one
  admin review queue can inspect them regardless of role.
* Verification state machine: pending -> verified / rejected. Transitions
  are performed by admins via separate endpoints, not this module.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable

SUPPORTED_ROLES = ("broker", "owner", "crew")

BROKER_TYPES = ("financing", "trader_non_financing", "external_trader")
OWNERSHIP_TYPES = ("individual", "group", "broker_owner")
FISHING_TYPES = ("commercial", "municipal")
FINANCING_TYPES = ("self", "broker_financed")
CREW_TYPES = ("pakura", "tongko")
DOCUMENT_TYPES = (
    "tin_number",
    "mayors_permit",
    "business_permit",
    "barangay_clearance",
    "license",
    "other",
)
VERIFICATION_STATUSES = ("pending", "verified", "expired", "rejected")


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def _as_str(value: Any, field: str, *, required: bool = True) -> str | None:
    if value is None:
        if required:
            raise ValueError(f"{field} is required")
        return None
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a string")
    value = value.strip()
    if required and not value:
        raise ValueError(f"{field} must not be empty")
    return value or None


def _as_int(value: Any, field: str, *, required: bool = True) -> int | None:
    if value is None or value == "":
        if required:
            raise ValueError(f"{field} is required")
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be an integer") from exc


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _as_str_list(value: Any, field: str) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        items = [str(v).strip() for v in value if str(v).strip()]
        return items
    if isinstance(value, str):
        # Accept comma-separated strings as a convenience.
        return [s.strip() for s in value.split(",") if s.strip()]
    raise ValueError(f"{field} must be a list of strings")


def _require_choice(value: Any, field: str, choices: Iterable[str]) -> str:
    normalized = _as_str(value, field)
    if normalized is None:
        raise ValueError(f"{field} is required")
    if normalized not in choices:
        raise ValueError(
            f"{field} must be one of: {', '.join(choices)}"
        )
    return normalized


def validate_broker_profile(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "tradingName": _as_str(payload.get("tradingName"), "tradingName"),
        "brokerType": _require_choice(
            payload.get("brokerType"), "brokerType", BROKER_TYPES
        ),
        "mainLandingCenter": _as_str(
            payload.get("mainLandingCenter"), "mainLandingCenter"
        ),
        "areaOfOperation": _as_str_list(
            payload.get("areaOfOperation"), "areaOfOperation"
        ),
        "yearsOfOperation": _as_int(
            payload.get("yearsOfOperation"), "yearsOfOperation", required=False
        ),
    }


def validate_owner_profile(payload: dict[str, Any]) -> dict[str, Any]:
    ownership_type = _require_choice(
        payload.get("ownershipType"), "ownershipType", OWNERSHIP_TYPES
    )
    financing_type = _require_choice(
        payload.get("financingType"), "financingType", FINANCING_TYPES
    )
    data: dict[str, Any] = {
        "ownershipType": ownership_type,
        "numberOfVesselsOwned": _as_int(
            payload.get("numberOfVesselsOwned"),
            "numberOfVesselsOwned",
            required=False,
        ),
        "primaryLandingCenter": _as_str(
            payload.get("primaryLandingCenter"), "primaryLandingCenter"
        ),
        "areaOfOperation": _as_str_list(
            payload.get("areaOfOperation"), "areaOfOperation"
        ),
        "fishingType": _require_choice(
            payload.get("fishingType"), "fishingType", FISHING_TYPES
        ),
        "activeGearTypes": _as_str_list(
            payload.get("activeGearTypes"), "activeGearTypes"
        ),
        "passiveGearTypes": _as_str_list(
            payload.get("passiveGearTypes"), "passiveGearTypes"
        ),
        "financingType": financing_type,
        "alsoFunctionsAsBroker": _as_bool(
            payload.get("alsoFunctionsAsBroker", False)
        ),
    }
    if financing_type == "broker_financed":
        data["linkedBrokerId"] = _as_str(
            payload.get("linkedBrokerId"), "linkedBrokerId"
        )
    return data


def validate_crew_profile(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "assignedVesselId": _as_str(
            payload.get("assignedVesselId"),
            "assignedVesselId",
            required=False,
        ),
        "crewType": _require_choice(
            payload.get("crewType"), "crewType", CREW_TYPES
        ),
        "skills": _as_str(payload.get("skills"), "skills", required=False),
        "yearsExperience": _as_int(
            payload.get("yearsExperience"),
            "yearsExperience",
            required=False,
        ),
        "licenseNumber": _as_str(
            payload.get("licenseNumber"), "licenseNumber", required=False
        ),
        "captainIsOwner": _as_bool(payload.get("captainIsOwner", False)),
        "boatOwnerId": _as_str(
            payload.get("boatOwnerId"), "boatOwnerId", required=False
        ),
    }


_VALIDATORS = {
    "broker": validate_broker_profile,
    "owner": validate_owner_profile,
    "crew": validate_crew_profile,
}


def validate_role_profile(
    role: str, payload: dict[str, Any]
) -> tuple[str, dict[str, Any]]:
    """Validate a role-profile upsert payload. Returns (role, normalized data).

    `role` must match one of SUPPORTED_ROLES. Unknown fields are silently
    dropped — the normalized payload is always what ends up in Mongo.
    """
    if role not in _VALIDATORS:
        raise ValueError(
            f"Unsupported role '{role}'. Expected one of: {', '.join(SUPPORTED_ROLES)}"
        )
    if not isinstance(payload, dict):
        raise ValueError("Profile payload must be an object")
    data = _VALIDATORS[role](payload)
    return role, data


# ---------------------------------------------------------------------------
# Document helpers
# ---------------------------------------------------------------------------


def validate_document_metadata(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate document metadata posted alongside an upload."""
    doc_type = _require_choice(
        payload.get("type"), "type", DOCUMENT_TYPES
    )
    issue_date = _as_str(
        payload.get("issueDate"), "issueDate", required=False
    )
    expiry_date = _as_str(
        payload.get("expiryDate"), "expiryDate", required=False
    )
    if issue_date and not _looks_like_date(issue_date):
        raise ValueError("issueDate must be YYYY-MM-DD")
    if expiry_date and not _looks_like_date(expiry_date):
        raise ValueError("expiryDate must be YYYY-MM-DD")
    return {
        "type": doc_type,
        "issueDate": issue_date,
        "expiryDate": expiry_date,
    }


def _looks_like_date(value: str) -> bool:
    if len(value) != 10:
        return False
    try:
        datetime.strptime(value, "%Y-%m-%d")
        return True
    except ValueError:
        return False


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------


def build_role_profile_update(
    user: dict[str, Any],
    role: str,
    profile: dict[str, Any],
) -> dict[str, Any]:
    """Return the Mongo `$set` payload that upserts the role sub-document."""
    now = datetime.now(timezone.utc)
    existing = user.get("roleProfile") or {}
    if not isinstance(existing, dict):
        existing = {}
    existing[role] = profile
    existing.setdefault("documents", [])
    return {
        "roleProfile": existing,
        "profileCompleted": True,
        "verificationStatus": user.get("verificationStatus") or "pending",
        "updatedAt": now,
    }


def append_document(
    user: dict[str, Any],
    document: dict[str, Any],
) -> list[dict[str, Any]]:
    """Return the updated documents list with `document` appended."""
    existing = user.get("roleProfile") or {}
    documents = list(existing.get("documents") or [])
    documents.append(document)
    return documents


def remove_document(
    user: dict[str, Any],
    document_id: str,
) -> list[dict[str, Any]]:
    existing = user.get("roleProfile") or {}
    documents = list(existing.get("documents") or [])
    return [d for d in documents if d.get("id") != document_id]


# ---------------------------------------------------------------------------
# Verification state transitions
# ---------------------------------------------------------------------------


def build_verify_payload(admin_user_id: str) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    return {
        "verificationStatus": "verified",
        "verifiedAt": now,
        "verifiedBy": admin_user_id,
        "companyApproved": True,
        "rejectedAt": None,
        "rejectedBy": None,
        "rejectedReason": None,
        "updatedAt": now,
    }


def build_reject_payload(admin_user_id: str, reason: str | None) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    return {
        "verificationStatus": "rejected",
        "rejectedAt": now,
        "rejectedBy": admin_user_id,
        "rejectedReason": reason,
        "verifiedAt": None,
        "verifiedBy": None,
        "companyApproved": False,
        "updatedAt": now,
    }
