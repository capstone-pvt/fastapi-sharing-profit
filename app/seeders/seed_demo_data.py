"""
Demo data seeder for the Profit Sharing system.
Seeds roles, company, and user accounts only.

Usage:
    python -m app.seeders.seed_demo_data
"""
import asyncio
from datetime import datetime, timezone

from app.db import connect_db, disconnect_db, get_db
from app.core.security import hash_password
from app.seeders.roles_permissions import (
    seed_broker_role_with_permissions,
    seed_boat_owner_role_with_permissions,
    seed_fisherman_role_with_permissions,
    seed_admin_role_with_all_permissions,
)


DEMO_PASSWORD = "P@ssw0rd123"


async def seed_demo_data():
    await connect_db()
    db = get_db()
    now = datetime.now(timezone.utc)

    print("Seeding roles and permissions...")
    await seed_broker_role_with_permissions()
    await seed_boat_owner_role_with_permissions()
    await seed_fisherman_role_with_permissions()
    await seed_admin_role_with_all_permissions()

    # ─── Lookup role IDs ───
    roles = {}
    async for r in db["roles"].find():
        roles[r["name"]] = r["_id"]

    # ─── Company ───
    print("Seeding company...")
    company = await db["companies"].find_one({"companyName": "Demo Fishing Co"})
    if not company:
        result = await db["companies"].insert_one({
            "companyName": "Demo Fishing Co",
            "companyCode": "DFC001",
            "companyAddress": "",
            "companyPhone": "",
            "companyTaxId": "",
            "createdAt": now,
            "updatedAt": now,
        })
        company_id = result.inserted_id
    else:
        company_id = company["_id"]

    # ─── Users ───
    print("Seeding users...")
    users_data = [
        {"email": "super@demo.com", "firstName": "Super", "lastName": "Admin",
         "role": "admin"},
        {"email": "admin@demo.com", "firstName": "Admin", "lastName": "User",
         "role": "admin"},
    ]
    user_ids = {}
    for u in users_data:
        existing = await db["users"].find_one({"email": u["email"]})
        if existing:
            user_ids[u["email"]] = existing["_id"]
            continue
        result = await db["users"].insert_one({
            "email": u["email"],
            "password": hash_password(DEMO_PASSWORD),
            "firstName": u["firstName"],
            "lastName": u["lastName"],
            "role": roles.get(u["role"]),
            "companyId": company_id,
            "companyApproved": True,
            "isActive": True,
            "createdAt": now,
            "updatedAt": now,
        })
        user_ids[u["email"]] = result.inserted_id
    print(f"  {len(user_ids)} users ready")

    print()
    print("=" * 50)
    print("DEMO DATA SEEDED SUCCESSFULLY!")
    print("=" * 50)
    print()
    print(f"Login credentials (all use password: {DEMO_PASSWORD}):")
    print("  Super:   super@demo.com")
    print("  Admin:   admin@demo.com")
    print()

    await disconnect_db()


if __name__ == "__main__":
    asyncio.run(seed_demo_data())
