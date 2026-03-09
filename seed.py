import asyncio
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

from app.db import connect_db, disconnect_db
from app.seeders.roles_permissions import (
    seed_admin_role_with_all_permissions,
    seed_boat_owner_role_with_permissions,
    seed_broker_role_with_permissions,
    seed_fisherman_role_with_permissions,
)
from app.seeders.users import backfill_default_user_role, seed_default_role_users
from app.seeders.fish_models import seed_fish_models, seed_fish_species


async def main() -> None:
    await connect_db()
    try:
        await seed_broker_role_with_permissions()
        await seed_boat_owner_role_with_permissions()
        await seed_fisherman_role_with_permissions()
        await seed_admin_role_with_all_permissions()
        await backfill_default_user_role()
        await seed_default_role_users()
        print(
            "Broker, Boat Owner, Fisherman, and Admin roles/permissions seeded."
        )
        await seed_fish_species()
        await seed_fish_models()
        print("Fish species and pre-trained models seeded.")
    finally:
        await disconnect_db()


if __name__ == "__main__":
    asyncio.run(main())
