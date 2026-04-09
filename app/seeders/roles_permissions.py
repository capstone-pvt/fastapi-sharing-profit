from __future__ import annotations

from app.infrastructure.permissions.repository import ensure_default_permissions
from app.infrastructure.roles.repository import ensure_default_roles, RoleNames


async def seed_broker_role_with_permissions() -> None:
    """Broker (Financer & Encoder) — per strict RBAC spec.

    CAN: encode fish sales, record expenses, manage cash advances (as
    financer), view vessels/trips/crew (read only), AI analysis, forecasts.

    CANNOT: create/modify vessels, vessel-owners, boats, trips, fishermen,
    profit-sharing policies, generate profit shares, delete sales/expenses.
    """
    permission_ids = await ensure_default_permissions()
    broker_permissions = [
        # Read-only access to operational entities (assigned by owner)
        permission_ids.get("vessels:read"),
        permission_ids.get("vessel-owners:read"),
        permission_ids.get("boats:read"),
        permission_ids.get("trips:read"),
        permission_ids.get("fishermen:read"),
        permission_ids.get("catches:read"),
        # Fish sales — encode (create + update), no delete (correction workflow)
        permission_ids.get("fish-sales:create"),
        permission_ids.get("fish-sales:read"),
        permission_ids.get("fish-sales:update"),
        # Expenses — encode (create + update), no delete
        permission_ids.get("expenses:create"),
        permission_ids.get("expenses:read"),
        permission_ids.get("expenses:update"),
        # Cash advances — full management (broker is financer)
        permission_ids.get("cash-advances:create"),
        permission_ids.get("cash-advances:read"),
        permission_ids.get("cash-advances:update"),
        permission_ids.get("cash-advances:approve"),
        permission_ids.get("cash-advances:decline"),
        # Profit shares — view only (cannot generate/finalize)
        permission_ids.get("profit-shares:read"),
        # Policies — view only (cannot modify)
        permission_ids.get("profit-sharing-policies:read"),
        # Forecasts — view + create (for trip planning)
        permission_ids.get("forecasts:read"),
        permission_ids.get("forecasts:create"),
        # AI / Training
        permission_ids.get("fish:analyze"),
        permission_ids.get("fish:diagnostic"),
        permission_ids.get("fish:analytics"),
        permission_ids.get("fish:history"),
        permission_ids.get("training-samples:create"),
        permission_ids.get("training-samples:read"),
        # Users — read (for crew attribution in sales)
        permission_ids.get("user:read"),
    ]
    await ensure_default_roles(
        {
            RoleNames.BROKER: [pid for pid in broker_permissions if pid],
        }
    )


async def seed_boat_owner_role_with_permissions() -> None:
    """Boat Owner (Trip Owner & Decision Maker) — per strict RBAC spec.

    CAN: register/manage vessels, boats, vessel-owners, trips, crew,
    catches, expenses, profit policies, generate/finalize profit shares,
    approve cash advances, view forecasts/reports.

    CANNOT: directly encode fish sales (broker job), delete broker
    submissions (correction workflow), manage users/companies (admin job).
    """
    permission_ids = await ensure_default_permissions()
    boat_owner_permissions = [
        # Vessel & boat management — full CRUD
        permission_ids.get("vessels:create"),
        permission_ids.get("vessels:read"),
        permission_ids.get("vessels:update"),
        permission_ids.get("vessels:delete"),
        permission_ids.get("vessel-owners:create"),
        permission_ids.get("vessel-owners:read"),
        permission_ids.get("vessel-owners:update"),
        permission_ids.get("vessel-owners:delete"),
        permission_ids.get("boats:create"),
        permission_ids.get("boats:read"),
        permission_ids.get("boats:update"),
        permission_ids.get("boats:delete"),
        # Crew management — full CRUD
        permission_ids.get("fishermen:create"),
        permission_ids.get("fishermen:read"),
        permission_ids.get("fishermen:update"),
        permission_ids.get("fishermen:delete"),
        # Trip management — full CRUD
        permission_ids.get("trips:create"),
        permission_ids.get("trips:read"),
        permission_ids.get("trips:update"),
        permission_ids.get("trips:delete"),
        # Catches — input/adjust crew catch
        permission_ids.get("catches:create"),
        permission_ids.get("catches:read"),
        permission_ids.get("catches:update"),
        permission_ids.get("catches:delete"),
        # Fish sales — review only (read + adjust, no create/delete)
        permission_ids.get("fish-sales:read"),
        permission_ids.get("fish-sales:update"),
        # Expenses — full (input additional expenses)
        permission_ids.get("expenses:create"),
        permission_ids.get("expenses:read"),
        permission_ids.get("expenses:update"),
        permission_ids.get("expenses:delete"),
        # Profit-sharing policies — full (configure Pakura/Tongko/custom)
        permission_ids.get("profit-sharing-policies:create"),
        permission_ids.get("profit-sharing-policies:read"),
        permission_ids.get("profit-sharing-policies:update"),
        permission_ids.get("profit-sharing-policies:delete"),
        # Profit shares — generate/finalize + view
        permission_ids.get("profit-shares:generate"),
        permission_ids.get("profit-shares:read"),
        # Cash advances — approve/decline crew requests
        permission_ids.get("cash-advances:create"),
        permission_ids.get("cash-advances:read"),
        permission_ids.get("cash-advances:update"),
        permission_ids.get("cash-advances:approve"),
        permission_ids.get("cash-advances:decline"),
        # Forecasts — view + create
        permission_ids.get("forecasts:read"),
        permission_ids.get("forecasts:create"),
        # AI / Training — analysis + history
        permission_ids.get("fish:analyze"),
        permission_ids.get("fish:analytics"),
        permission_ids.get("fish:history"),
        permission_ids.get("training-samples:read"),
        # Users — read (view company users for crew assignment)
        permission_ids.get("user:read"),
    ]
    await ensure_default_roles(
        {
            RoleNames.OWNER: [pid for pid in boat_owner_permissions if pid],
        }
    )


async def seed_fisherman_role_with_permissions() -> None:
    """Fishing Crew (Participant / Beneficiary) — per strict RBAC spec.

    CAN: view assigned trips, catches, earnings, deductions, request cash
    advance, view forecasts.

    CANNOT: create/edit sales/expenses/trips, assign catches, modify
    policies, alter earnings, view other crew earnings or broker finance.
    """
    permission_ids = await ensure_default_permissions()
    fisherman_permissions = [
        # View assigned trips and participation history
        permission_ids.get("trips:read"),
        # View attributed catches and summaries
        permission_ids.get("catches:read"),
        # View fish sales summaries
        permission_ids.get("fish-sales:read"),
        # View detailed earnings per trip (breakdown + deductions)
        permission_ids.get("profit-shares:read"),
        # Request cash advance + view status
        permission_ids.get("cash-advances:create"),
        permission_ids.get("cash-advances:read"),
        # Analyze trends (seasonality, production)
        permission_ids.get("forecasts:read"),
        # View own AI analysis history (no scan capability)
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
