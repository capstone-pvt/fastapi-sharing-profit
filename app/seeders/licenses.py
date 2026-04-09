"""Seeder for default app_licenses.

Pre-activates the demo company so the seeded users (admin/broker/owner/crew)
can sign in and use the app immediately without going through the activation
flow.

Each entry binds an activation code to one of the seeded companies (looked up
by company_key). The license is created in `active` state with `activatedAt`
set to now and `expiresAt` set 1 year out.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from app.db import get_db


# Pre-defined activation codes per company. These are intentionally
# human-friendly so anyone running the seeder can copy them into the in-app
# Settings → Activation page if they ever need to re-bind a license.
DEFAULT_LICENSES = [
    {
        "company_key": "company_a",  # Demo Fishing Co
        "activationCode": "DEMO-FISH-CO00-0001",
        "plan": "premium",
        "maxUsers": 100,
        "durationDays": 365,
    },
]


async def seed_default_licenses(
    companies_by_key: dict[str, dict[str, Any]],
) -> int:
    """Create activation codes pre-bound to seeded companies.

    Args:
        companies_by_key: Mapping returned by ``seed_default_companies()`` —
            keyed by the company's seeder ``key`` ("company_a", etc.) so the
            license can be bound to the correct company without re-querying.

    Returns:
        Number of licenses created or refreshed.
    """
    db = get_db()
    now = datetime.now(timezone.utc)
    count = 0

    for spec in DEFAULT_LICENSES:
        company = companies_by_key.get(spec["company_key"])
        if not company:
            continue

        company_id = company["_id"]
        company_name = company.get("companyName")
        code = spec["activationCode"].strip().upper()
        plan = spec.get("plan", "standard")
        duration_days = int(spec.get("durationDays", 365))
        max_users = int(spec.get("maxUsers", 20))
        expires_at = now + timedelta(days=duration_days)

        active_doc = {
            "activationCode": code,
            "status": "active",
            "companyId": company_id,
            "companyName": company_name,
            "activatedAt": now,
            "expiresAt": expires_at,
            "durationDays": duration_days,
            "maxUsers": max_users,
            "plan": plan,
            "createdBy": "seeder",
            "updatedAt": now,
        }

        # Upsert by activation code so re-running the seeder is idempotent.
        result = await db["app_licenses"].update_one(
            {"activationCode": code},
            {
                "$set": active_doc,
                "$setOnInsert": {"createdAt": now},
            },
            upsert=True,
        )
        if result.upserted_id is not None or result.modified_count > 0:
            count += 1

        # Defensive: clear any other "active" license bound to the same
        # company so /licenses/status returns the seeded one (it sorts by
        # expiresAt desc and the seeded one is the freshest).
        await db["app_licenses"].update_many(
            {
                "companyId": company_id,
                "status": "active",
                "activationCode": {"$ne": code},
            },
            {"$set": {"status": "revoked", "updatedAt": now}},
        )

    return count
