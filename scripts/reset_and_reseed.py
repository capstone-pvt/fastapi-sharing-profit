"""Reset production database and re-seed with fresh data.

Usage:
    cd profit_sharing_api_fastapi
    PYTHONPATH=. python scripts/reset_and_reseed.py

WARNING: This drops ALL collections and recreates them from scratch.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from dotenv import load_dotenv

# Load .env before any app imports
_project_root = Path(__file__).resolve().parents[1]
load_dotenv(_project_root / ".env")

from app.db import connect_db, disconnect_db, get_db  # noqa: E402
from app.seeders.roles_permissions import (  # noqa: E402
    seed_admin_role_with_all_permissions,
    seed_boat_owner_role_with_permissions,
    seed_broker_role_with_permissions,
    seed_fisherman_role_with_permissions,
)
from app.seeders.users import (  # noqa: E402
    backfill_default_user_role,
    seed_default_role_users,
)
from app.seeders.companies import seed_default_companies  # noqa: E402
from app.seeders.fish_models import seed_fish_models, seed_fish_species  # noqa: E402


# All known collections in the database
COLLECTIONS_TO_DROP = [
    # System
    "permissions",
    "roles",
    "users",
    "companies",
    "audit_logs",
    # Domain
    "vessels",
    "vessel_owners",
    "boats",
    "fishermen",
    "crew",
    "trips",
    "catches",
    "fish_sales",
    "expenses",
    "cash_advances",
    "profit_shares",
    "profit_sharing_policies",
    "forecasts",
    # AI / Training
    "fish_species",
    "fish_models",
    "fish_analysis",
    "fish_training_samples",
    # Licenses
    "licenses",
]


async def reset_and_reseed() -> None:
    await connect_db()
    db = get_db()

    # 1. Drop all collections
    print("=" * 50)
    print("  DROPPING ALL COLLECTIONS")
    print("=" * 50)
    existing = await db.list_collection_names()
    for name in COLLECTIONS_TO_DROP:
        if name in existing:
            await db[name].drop()
            print(f"  Dropped: {name}")
        else:
            print(f"  Skipped (not found): {name}")

    # Drop any remaining collections not in the list
    remaining = await db.list_collection_names()
    for name in remaining:
        if not name.startswith("system."):
            await db[name].drop()
            print(f"  Dropped (extra): {name}")

    print()
    print("=" * 50)
    print("  RE-SEEDING DATABASE")
    print("=" * 50)

    # 2. Seed roles & permissions
    print("\n[1/6] Seeding permissions & roles...")
    await seed_broker_role_with_permissions()
    await seed_boat_owner_role_with_permissions()
    await seed_fisherman_role_with_permissions()
    await seed_admin_role_with_all_permissions()
    print("  Done - broker, owner, crew, admin, super roles created")

    # 3. Backfill default role
    print("\n[2/6] Backfilling default user role...")
    await backfill_default_user_role()
    print("  Done")

    # 4. Seed companies
    print("\n[3/6] Seeding companies...")
    created_count, _ = await seed_default_companies()
    print(f"  Done - {created_count} companies created")

    # 5. Seed users
    print("\n[4/6] Seeding default users...")
    user_count = await seed_default_role_users()
    print(f"  Done - {user_count} users created/updated")

    # 6. Seed fish species
    print("\n[5/6] Seeding fish species...")
    await seed_fish_species()
    print("  Done")

    # 7. Seed fish models
    print("\n[6/6] Seeding fish models...")
    await seed_fish_models()
    print("  Done")

    print()
    print("=" * 50)
    print("  RESET COMPLETE")
    print("=" * 50)
    print()
    print("Default users:")
    print("  super@demo.com    / P@ssw0rd123  (Super Admin)")
    print("  admin@demo.com    / P@ssw0rd123  (Admin - Blue Ocean Co)")
    print("  broker@demo.com   / P@ssw0rd123  (Broker - Blue Ocean Co)")
    print("  owner@demo.com    / P@ssw0rd123  (Owner - Blue Ocean Co)")
    print("  crew@demo.com     / P@ssw0rd123  (Crew - Blue Ocean Co)")
    print()

    await disconnect_db()


if __name__ == "__main__":
    asyncio.run(reset_and_reseed())
