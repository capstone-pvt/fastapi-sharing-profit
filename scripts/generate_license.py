"""Generate an activation code directly in MongoDB.

Usage:
    PYTHONPATH=. python scripts/generate_license.py
    PYTHONPATH=. python scripts/generate_license.py --plan premium --max-users 100 --days 365
"""

from __future__ import annotations

import argparse
import asyncio
import secrets
import string
from datetime import datetime

from dotenv import load_dotenv
load_dotenv()

from app.db import connect_db, disconnect_db, get_db


def generate_code() -> str:
    chars = string.ascii_uppercase + string.digits
    segment = lambda: "".join(secrets.choice(chars) for _ in range(4))
    return f"{segment()}-{segment()}-{segment()}-{segment()}"


async def main(plan: str, max_users: int, duration_days: int) -> None:
    await connect_db()
    try:
        db = get_db()
        code = generate_code()

        # Ensure uniqueness
        while await db["app_licenses"].find_one({"activationCode": code}):
            code = generate_code()

        now = datetime.utcnow()
        doc = {
            "activationCode": code,
            "status": "pending",
            "companyId": None,
            "companyName": None,
            "activatedAt": None,
            "expiresAt": None,
            "durationDays": duration_days,
            "maxUsers": max_users,
            "plan": plan,
            "createdBy": "script",
            "createdAt": now,
            "updatedAt": now,
        }
        await db["app_licenses"].insert_one(doc)

        print()
        print("=" * 44)
        print(f"  ACTIVATION CODE:  {code}")
        print(f"  Plan:             {plan}")
        print(f"  Max Users:        {max_users}")
        print(f"  Duration:         {duration_days} days")
        print("=" * 44)
        print()
        print("Share this code with your client.")
        print("They enter it on the Activation page after login.")
        print()
    finally:
        await disconnect_db()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate an activation code.")
    parser.add_argument("--plan", default="standard", choices=["trial", "standard", "premium"])
    parser.add_argument("--max-users", type=int, default=50)
    parser.add_argument("--days", type=int, default=365)
    args = parser.parse_args()

    asyncio.run(main(args.plan, args.max_users, args.days))
