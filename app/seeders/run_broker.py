import asyncio

from app.db import connect_db, disconnect_db
from app.seeders.roles_permissions import seed_broker_role_with_permissions


async def main() -> None:
    await connect_db()
    try:
        await seed_broker_role_with_permissions()
        print("Broker role and permissions seeded.")
    finally:
        await disconnect_db()


if __name__ == "__main__":
    asyncio.run(main())
