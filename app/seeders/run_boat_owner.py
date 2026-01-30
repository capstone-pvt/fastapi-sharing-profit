import asyncio

from app.db import connect_db, disconnect_db
from app.seeders.roles_permissions import seed_boat_owner_role_with_permissions


async def main() -> None:
    await connect_db()
    try:
        await seed_boat_owner_role_with_permissions()
        print("Boat Owner role and permissions seeded.")
    finally:
        await disconnect_db()


if __name__ == "__main__":
    asyncio.run(main())
