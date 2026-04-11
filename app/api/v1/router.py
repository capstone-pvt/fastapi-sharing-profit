from fastapi import APIRouter, Depends

from app.api.v1.auth.routes import router as auth_router
from app.api.v1.fish.routes import router as fish_router
from app.api.v1.fish_models.routes import router as fish_models_router
from app.api.v1.fish_species.routes import router as fish_species_router
from app.api.v1.fish_training_samples.routes import (
    router as fish_training_router,
)
from app.api.v1.profile.routes import router as profile_router
from app.api.v1.companies.routes import router as companies_router
from app.api.v1.cash_advances.routes import router as cash_advances_router
from app.api.v1.permissions.routes import router as permissions_router
from app.api.v1.roles.routes import router as roles_router
from app.api.v1.shared.crud import build_crud_router
from app.api.v1.users.routes import router as users_router
from app.api.v1.audit.routes import router as audit_router
from app.api.v1.weather.routes import router as weather_router
from app.api.v1.licenses.routes import router as licenses_router
from app.api.v1.forecast.routes import router as forecast_router
from app.api.v1.trips.routes import router as trips_router
from app.api.v1.notifications.routes import router as notifications_router
from app.api.v1.profit_shares.routes import router as profit_shares_custom_router
from app.deps import require_roles


api_router = APIRouter(prefix="/api")

api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(roles_router)
api_router.include_router(permissions_router)
api_router.include_router(fish_router)
api_router.include_router(fish_models_router)
api_router.include_router(fish_species_router)
api_router.include_router(fish_training_router)
api_router.include_router(profile_router)
api_router.include_router(companies_router)
api_router.include_router(cash_advances_router)
api_router.include_router(audit_router)
api_router.include_router(weather_router)
api_router.include_router(licenses_router)
api_router.include_router(forecast_router)

api_router.include_router(
    build_crud_router(
        "boats",
        permissions={
            "create": "boats:create",
            "read": "boats:read",
            "update": "boats:update",
            "delete": "boats:delete",
        },
    ),
    prefix="/boats",
    tags=["boats"],
)
api_router.include_router(
    build_crud_router(
        "vessels",
        permissions={
            "create": "vessels:create",
            "read": "vessels:read",
            "update": "vessels:update",
            "delete": "vessels:delete",
        },
    ),
    prefix="/vessels",
    tags=["vessels"],
)
api_router.include_router(
    build_crud_router(
        "vessel_owners",
        permissions={
            "create": "vessel-owners:create",
            "read": "vessel-owners:read",
            "update": "vessel-owners:update",
            "delete": "vessel-owners:delete",
        },
    ),
    prefix="/vessel-owners",
    tags=["vessel-owners"],
)
api_router.include_router(trips_router)
api_router.include_router(
    build_crud_router(
        "expenses",
        permissions={
            "create": "expenses:create",
            "read": "expenses:read",
            "update": "expenses:update",
            "delete": "expenses:delete",
        },
    ),
    prefix="/expenses",
    tags=["expenses"],
)
api_router.include_router(
    build_crud_router(
        "fish_sales",
        permissions={
            "create": "fish-sales:create",
            "read": "fish-sales:read",
            "update": "fish-sales:update",
            "delete": "fish-sales:delete",
        },
    ),
    prefix="/fish-sales",
    tags=["fish-sales"],
)
api_router.include_router(
    build_crud_router(
        "cash_advances",
        permissions={
            "create": "cash-advances:create",
            "read": "cash-advances:read",
            "update": "cash-advances:update",
            "delete": "cash-advances:delete",
        },
    ),
    prefix="/cash-advances",
    tags=["cash-advances"],
)
api_router.include_router(
    build_crud_router(
        "forecasts",
        permissions={
            "read": "forecasts:read",
            "create": "forecasts:create",
            "update": "forecasts:update",
            "delete": "forecasts:delete",
        },
        allowed_actions={"create", "read", "update", "delete"},
    ),
    prefix="/forecasts",
    tags=["forecasts"],
)

api_router.include_router(
    build_crud_router(
        "catches",
        permissions={
            "create": "catches:create",
            "read": "catches:read",
            "update": "catches:update",
            "delete": "catches:delete",
        },
    ),
    prefix="/catches",
    tags=["catches"],
)

api_router.include_router(
    build_crud_router(
        "crew",
        permissions={
            "create": "fishermen:create",
            "read": "fishermen:read",
            "update": "fishermen:update",
            "delete": "fishermen:delete",
        },
    ),
    prefix="/crew",
    tags=["crew"],
)

api_router.include_router(notifications_router)

# Custom profit-shares routes (/compute, /generate, /status) — must be
# included BEFORE the generic CRUD so the custom paths take priority.
api_router.include_router(profit_shares_custom_router)

api_router.include_router(
    build_crud_router(
        "profit_shares",
        permissions={
            "create": "profit-shares:generate",
            "read": "profit-shares:read",
        },
        allowed_actions={"create", "read"},
    ),
    prefix="/profit-shares",
    tags=["profit-shares"],
)

api_router.include_router(
    build_crud_router(
        "profit_sharing_policies",
        permissions={
            "create": "profit-sharing-policies:create",
            "read": "profit-sharing-policies:read",
            "update": "profit-sharing-policies:update",
            "delete": "profit-sharing-policies:delete",
        },
    ),
    prefix="/profit-sharing-policies",
    tags=["profit-sharing-policies"],
)
