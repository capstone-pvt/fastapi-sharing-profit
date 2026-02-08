import asyncio

from app.db import connect_db, disconnect_db
from app.seeders.roles_permissions import (
    seed_admin_role_with_all_permissions,
    seed_boat_owner_role_with_permissions,
    seed_broker_role_with_permissions,
    seed_fisherman_role_with_permissions,
)
from app.seeders.users import backfill_default_user_role, seed_default_role_users
from app.seeders.companies import seed_default_company_and_assign_to_users


async def main() -> None:
    await connect_db()
    try:
        await seed_broker_role_with_permissions()
        await seed_boat_owner_role_with_permissions()
        await seed_fisherman_role_with_permissions()
        await seed_admin_role_with_all_permissions()
        await backfill_default_user_role()
        await seed_default_role_users()
        company_created, users_updated = await seed_default_company_and_assign_to_users()
        print(
            "Broker, Boat Owner, Fisherman, and Admin roles/permissions seeded."
        )
        print(
            f"Default company: {'created' if company_created else 'already exists'}; "
            f"users assigned: {users_updated}."
        )
    finally:
        await disconnect_db()


if __name__ == "__main__":
    asyncio.run(main())
