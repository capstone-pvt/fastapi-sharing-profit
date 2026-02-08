"""
Database migration script to update role names from old to new format.

Old -> New role name mappings:
- 'Broker/Financer', 'Broker/Financier', 'Broker' -> 'broker'
- 'Vessel Owner', 'Boat Owner', 'vesselowner', 'boatowner' -> 'owner'
- 'Fisherman', 'fisherman' -> 'crew'
- 'User', 'user' -> 'user' (no change)
- 'Admin', 'admin' -> 'admin' (no change)
- 'System Admin', 'Superadmin', 'Super Admin', 'Super-Admin' -> 'super'

This script will:
1. Update role names in the roles collection
2. Update requesterRole and approverRole in cash_advances collection
3. Preserve role relationships in users collection (via role ObjectId references)
"""
import asyncio
import re
from app.db import get_db
from app.infrastructure.roles.repository import RoleNames


# Role name mappings
OLD_TO_NEW_ROLES = {
    # Broker variants
    "Broker/Financer": RoleNames.BROKER,
    "Broker/Financier": RoleNames.BROKER,
    "Broker": RoleNames.BROKER,
    "broker": RoleNames.BROKER,
    "financer": RoleNames.BROKER,
    "financier": RoleNames.BROKER,
    "broker/financer": RoleNames.BROKER,
    "broker/financier": RoleNames.BROKER,

    # Owner variants
    "Vessel Owner": RoleNames.OWNER,
    "Boat Owner": RoleNames.OWNER,
    "vesselowner": RoleNames.OWNER,
    "vessel owner": RoleNames.OWNER,
    "boatowner": RoleNames.OWNER,
    "boat owner": RoleNames.OWNER,
    "vessel_owner": RoleNames.OWNER,

    # Crew variants
    "Fisherman": RoleNames.CREW,
    "fisherman": RoleNames.CREW,

    # User (no change)
    "User": RoleNames.USER,
    "user": RoleNames.USER,

    # Admin (no change)
    "Admin": RoleNames.ADMIN,
    "admin": RoleNames.ADMIN,

    # Super admin variants
    "System Admin": RoleNames.SUPER,
    "system admin": RoleNames.SUPER,
    "Superadmin": RoleNames.SUPER,
    "superadmin": RoleNames.SUPER,
    "Super Admin": RoleNames.SUPER,
    "super admin": RoleNames.SUPER,
    "Super-Admin": RoleNames.SUPER,
    "super-admin": RoleNames.SUPER,
}


async def migrate_roles():
    """Update role names in the roles collection."""
    db = get_db()
    roles_updated = 0

    print("=" * 60)
    print("STEP 1: Migrating roles collection")
    print("=" * 60)

    # Get all roles
    roles = await db["roles"].find({}).to_list(None)
    print(f"Found {len(roles)} roles in the database")

    for role in roles:
        old_name = role.get("name", "")
        new_name = OLD_TO_NEW_ROLES.get(old_name)

        if new_name and new_name != old_name:
            # Check if the new role name already exists
            existing = await db["roles"].find_one(
                {"name": {"$regex": f"^{re.escape(new_name)}$", "$options": "i"}}
            )

            if existing and existing["_id"] != role["_id"]:
                # New role name already exists, need to merge
                print(f"  Merging: '{old_name}' -> '{new_name}' (target already exists)")

                # Update all users pointing to old role to point to new role
                await db["users"].update_many(
                    {"role": role["_id"]},
                    {"$set": {"role": existing["_id"]}}
                )

                # Delete the old role
                await db["roles"].delete_one({"_id": role["_id"]})
                roles_updated += 1
            else:
                # Simply rename the role
                print(f"  Renaming: '{old_name}' -> '{new_name}'")
                await db["roles"].update_one(
                    {"_id": role["_id"]},
                    {"$set": {"name": new_name}}
                )
                roles_updated += 1
        else:
            print(f"  Keeping: '{old_name}' (no change needed)")

    print(f"\nRoles updated: {roles_updated}")
    return roles_updated


async def migrate_cash_advances():
    """Update requesterRole and approverRole in cash_advances collection."""
    db = get_db()
    advances_updated = 0

    print("\n" + "=" * 60)
    print("STEP 2: Migrating cash_advances collection")
    print("=" * 60)

    # Get all cash advances
    advances = await db["cash_advances"].find({}).to_list(None)
    print(f"Found {len(advances)} cash advances in the database")

    for advance in advances:
        updates = {}

        # Update requesterRole if needed
        requester_role = advance.get("requesterRole", "")
        if requester_role:
            new_requester_role = OLD_TO_NEW_ROLES.get(requester_role)
            if new_requester_role and new_requester_role != requester_role:
                updates["requesterRole"] = new_requester_role
                print(f"  Advance {advance['_id']}: requesterRole '{requester_role}' -> '{new_requester_role}'")

        # Update approverRole if needed
        approver_role = advance.get("approverRole", "")
        if approver_role:
            new_approver_role = OLD_TO_NEW_ROLES.get(approver_role)
            if new_approver_role and new_approver_role != approver_role:
                updates["approverRole"] = new_approver_role
                print(f"  Advance {advance['_id']}: approverRole '{approver_role}' -> '{new_approver_role}'")

        # Apply updates if any
        if updates:
            await db["cash_advances"].update_one(
                {"_id": advance["_id"]},
                {"$set": updates}
            )
            advances_updated += 1

    print(f"\nCash advances updated: {advances_updated}")
    return advances_updated


async def verify_migration():
    """Verify the migration was successful."""
    db = get_db()

    print("\n" + "=" * 60)
    print("STEP 3: Verification")
    print("=" * 60)

    # Check roles
    roles = await db["roles"].find({}).to_list(None)
    print(f"\nRoles in database after migration:")
    for role in roles:
        print(f"  - {role['name']}")

    # Check for any remaining old role names
    old_role_names = [k for k in OLD_TO_NEW_ROLES.keys() if k != OLD_TO_NEW_ROLES[k]]
    remaining_old_roles = await db["roles"].find(
        {"name": {"$in": old_role_names}}
    ).to_list(None)

    if remaining_old_roles:
        print("\n⚠️  WARNING: Found remaining old role names:")
        for role in remaining_old_roles:
            print(f"  - {role['name']}")
    else:
        print("\n✓ All role names have been migrated successfully")

    # Check cash advances
    advances_with_old_roles = await db["cash_advances"].find({
        "$or": [
            {"requesterRole": {"$in": ["vessel_owner", "fisherman"]}},
            {"approverRole": {"$in": ["vessel_owner", "fisherman"]}}
        ]
    }).to_list(None)

    if advances_with_old_roles:
        print(f"\n⚠️  WARNING: Found {len(advances_with_old_roles)} cash advances with old role names")
    else:
        print("✓ All cash advance role fields have been migrated")

    # Count users by role
    print(f"\nUsers by role:")
    for role in roles:
        user_count = await db["users"].count_documents({"role": role["_id"]})
        print(f"  - {role['name']}: {user_count} users")


async def main():
    """Run the migration."""
    print("\n" + "=" * 60)
    print("ROLE MIGRATION SCRIPT")
    print("=" * 60)
    print("\nThis script will update role names in the database.")
    print("Make sure you have a backup before proceeding!")

    response = input("\nContinue with migration? (yes/no): ")
    if response.lower() != "yes":
        print("Migration cancelled.")
        return

    try:
        # Run migrations
        roles_updated = await migrate_roles()
        advances_updated = await migrate_cash_advances()

        # Verify
        await verify_migration()

        print("\n" + "=" * 60)
        print("MIGRATION COMPLETED")
        print("=" * 60)
        print(f"Roles updated: {roles_updated}")
        print(f"Cash advances updated: {advances_updated}")

    except Exception as e:
        print(f"\n❌ ERROR during migration: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
