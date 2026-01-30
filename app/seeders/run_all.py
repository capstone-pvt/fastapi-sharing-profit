import asyncio

from app.db import connect_db, disconnect_db
from app.seeders.roles_permissions import (
    seed_admin_role_with_all_permissions,
    seed_boat_owner_role_with_permissions,
    seed_broker_role_with_permissions,
    seed_fisherman_role_with_permissions,
)
from app.seeders.users import backfill_default_user_role


async def main() -> None:
    await connect_db()
    try:
        await seed_broker_role_with_permissions()
        await seed_boat_owner_role_with_permissions()
        await seed_fisherman_role_with_permissions()
        await seed_admin_role_with_all_permissions()
        await backfill_default_user_role()
        print(
            "Broker, Boat Owner, Fisherman, and Admin roles/permissions seeded."
        )
    finally:
        await disconnect_db()


if __name__ == "__main__":
    asyncio.run(main())
