from fastapi import APIRouter, Depends

from app.deps import require_roles
from app.routers.generic import build_crud_router
from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.users import router as users_router
from app.api.v1.endpoints.roles import router as roles_router
from app.api.v1.endpoints.permissions import router as permissions_router
from app.api.v1.endpoints.fish import router as fish_router
from app.api.v1.endpoints.fish_models import router as fish_models_router
from app.api.v1.endpoints.fish_species import router as fish_species_router
from app.api.v1.endpoints.fish_training_samples import (
    router as fish_training_router,
)


api_router = APIRouter(prefix="/api")

api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(roles_router)
api_router.include_router(permissions_router)
api_router.include_router(fish_router)
api_router.include_router(fish_models_router)
api_router.include_router(fish_species_router)
api_router.include_router(fish_training_router)

api_router.include_router(
    build_crud_router("vessels"),
    prefix="/vessels",
    tags=["vessels"],
    dependencies=[
        Depends(
            require_roles("admin", "system admin", "broker", "financer")
        )
    ],
)
api_router.include_router(
    build_crud_router("vessel_owners"),
    prefix="/vessel-owners",
    tags=["vessel-owners"],
    dependencies=[
        Depends(
            require_roles("admin", "system admin", "broker", "financer")
        )
    ],
)
api_router.include_router(
    build_crud_router("trips"),
    prefix="/trips",
    tags=["trips"],
    dependencies=[
        Depends(
            require_roles("admin", "system admin", "broker", "financer", "boat owner")
        )
    ],
)
api_router.include_router(
    build_crud_router("expenses"),
    prefix="/expenses",
    tags=["expenses"],
    dependencies=[
        Depends(
            require_roles("admin", "system admin", "broker", "financer", "boat owner")
        )
    ],
)
api_router.include_router(
    build_crud_router("fish_sales"),
    prefix="/fish-sales",
    tags=["fish-sales"],
    dependencies=[
        Depends(
            require_roles("admin", "system admin", "broker", "financer", "boat owner")
        )
    ],
)
api_router.include_router(
    build_crud_router("cash_advances"),
    prefix="/cash-advances",
    tags=["cash-advances"],
    dependencies=[
        Depends(
            require_roles(
                "admin",
                "system admin",
                "broker",
                "financer",
                "boat owner",
                "vessel owner",
                "fisherman",
            )
        )
    ],
)
api_router.include_router(
    build_crud_router("forecasts"),
    prefix="/forecasts",
    tags=["forecasts"],
    dependencies=[
        Depends(
            require_roles("admin", "system admin", "broker", "financer")
        )
    ],
)
