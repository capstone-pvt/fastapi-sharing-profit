"""
Script to add the audit:read permission to the database.
Run this after setting up the audit logging system.
"""

import asyncio
from datetime import datetime
import re
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db import connect_db, disconnect_db, get_db


async def add_audit_permission():
    """Add the audit:read permission to the permissions collection."""
    await connect_db()

    try:
        db = get_db()
        now = datetime.utcnow()

        audit_permission = {
            "name": "audit:read",
            "resource": "audit",
            "action": "read",
            "description": "View audit logs and history",
            "createdAt": now,
            "updatedAt": now,
        }

        result = await db["permissions"].update_one(
            {"name": {"$regex": f"^{re.escape('audit:read')}$", "$options": "i"}},
            {"$setOnInsert": audit_permission},
            upsert=True,
        )

        if result.upserted_id:
            print(f"✓ Created audit:read permission with ID: {result.upserted_id}")
        elif result.matched_count > 0:
            print("✓ audit:read permission already exists")
        else:
            print("✗ Failed to create audit:read permission")

        # Get all admin and super roles and add the permission
        permission_doc = await db["permissions"].find_one(
            {"name": {"$regex": f"^{re.escape('audit:read')}$", "$options": "i"}}
        )

        if permission_doc:
            permission_id = permission_doc["_id"]

            # Update admin and super roles
            admin_roles = await db["roles"].find(
                {"name": {"$regex": "^(admin|super)", "$options": "i"}}
            ).to_list(None)

            for role in admin_roles:
                if permission_id not in role.get("permissions", []):
                    await db["roles"].update_one(
                        {"_id": role["_id"]},
                        {"$addToSet": {"permissions": permission_id}}
                    )
                    print(f"✓ Added audit:read permission to role: {role['name']}")
                else:
                    print(f"✓ Role {role['name']} already has audit:read permission")

    finally:
        await disconnect_db()


if __name__ == "__main__":
    asyncio.run(add_audit_permission())
