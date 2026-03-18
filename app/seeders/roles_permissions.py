from __future__ import annotations

from app.infrastructure.permissions.repository import ensure_default_permissions
from app.infrastructure.roles.repository import ensure_default_roles, RoleNames


async def seed_broker_role_with_permissions() -> None:
    permission_ids = await ensure_default_permissions()
    broker_permissions = [
        permission_ids.get("boats:create"),
        permission_ids.get("boats:read"),
        permission_ids.get("boats:update"),
        permission_ids.get("boats:delete"),
        permission_ids.get("vessels:create"),
        permission_ids.get("vessels:read"),
        permission_ids.get("vessels:update"),
        permission_ids.get("vessels:delete"),
        permission_ids.get("vessel-owners:create"),
        permission_ids.get("vessel-owners:read"),
        permission_ids.get("vessel-owners:update"),
        permission_ids.get("vessel-owners:delete"),
        permission_ids.get("trips:create"),
        permission_ids.get("trips:read"),
        permission_ids.get("trips:update"),
        permission_ids.get("trips:delete"),
        permission_ids.get("fish-sales:create"),
        permission_ids.get("fish-sales:read"),
        permission_ids.get("fish-sales:update"),
        permission_ids.get("fish-sales:delete"),
        permission_ids.get("expenses:create"),
        permission_ids.get("expenses:read"),
        permission_ids.get("expenses:update"),
        permission_ids.get("expenses:delete"),
        permission_ids.get("cash-advances:read"),
        permission_ids.get("cash-advances:update"),
        permission_ids.get("cash-advances:approve"),
        permission_ids.get("cash-advances:decline"),
        permission_ids.get("training-samples:create"),
        permission_ids.get("training-samples:read"),
        permission_ids.get("forecasts:read"),
        permission_ids.get("forecasts:create"),
        permission_ids.get("forecasts:update"),
        permission_ids.get("forecasts:delete"),
        permission_ids.get("user:read"),
        permission_ids.get("catches:create"),
        permission_ids.get("catches:read"),
        permission_ids.get("catches:update"),
        permission_ids.get("catches:delete"),
        permission_ids.get("fish:analyze"),
        permission_ids.get("fish:diagnostic"),
        permission_ids.get("fish:analytics"),
        permission_ids.get("fish:history"),
    ]
    await ensure_default_roles(
        {
            RoleNames.BROKER: [pid for pid in broker_permissions if pid],
        }
    )


async def seed_boat_owner_role_with_permissions() -> None:
    permission_ids = await ensure_default_permissions()
    boat_owner_permissions = [
        permission_ids.get("boats:create"),
        permission_ids.get("boats:read"),
        permission_ids.get("boats:update"),
        permission_ids.get("boats:delete"),
        permission_ids.get("fishermen:create"),
        permission_ids.get("fishermen:read"),
        permission_ids.get("fishermen:update"),
        permission_ids.get("fishermen:delete"),
        permission_ids.get("catches:create"),
        permission_ids.get("catches:read"),
        permission_ids.get("catches:update"),
        permission_ids.get("catches:delete"),
        permission_ids.get("profit-sharing-policies:create"),
        permission_ids.get("profit-sharing-policies:read"),
        permission_ids.get("profit-sharing-policies:update"),
        permission_ids.get("profit-sharing-policies:delete"),
        permission_ids.get("profit-shares:generate"),
        permission_ids.get("profit-shares:read"),
        permission_ids.get("cash-advances:create"),
        permission_ids.get("cash-advances:read"),
        permission_ids.get("cash-advances:approve"),
        permission_ids.get("cash-advances:decline"),
        permission_ids.get("cash-advances:update"),
        permission_ids.get("forecasts:read"),
        permission_ids.get("training-samples:read"),
        permission_ids.get("fish:analyze"),
        permission_ids.get("fish:analytics"),
        permission_ids.get("fish:history"),
    ]
    await ensure_default_roles(
        {
            RoleNames.OWNER: [pid for pid in boat_owner_permissions if pid],
        }
    )


async def seed_fisherman_role_with_permissions() -> None:
    permission_ids = await ensure_default_permissions()
    fisherman_permissions = [
        permission_ids.get("profit-shares:read"),
        permission_ids.get("cash-advances:create"),
        permission_ids.get("cash-advances:read"),
        permission_ids.get("catches:read"),
        permission_ids.get("fish-sales:read"),
        permission_ids.get("fish:analyze"),
        permission_ids.get("fish:history"),
    ]
    await ensure_default_roles(
        {
            RoleNames.CREW: [pid for pid in fisherman_permissions if pid],
        }
    )


async def seed_admin_role_with_all_permissions() -> None:
    permission_ids = await ensure_default_permissions()
    all_permissions = [pid for pid in permission_ids.values() if pid]
    await ensure_default_roles(
        {
            RoleNames.ADMIN: all_permissions,
            RoleNames.SUPER: all_permissions,
        }
    )
