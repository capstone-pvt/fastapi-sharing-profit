from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException

from app.deps import get_current_user, require_roles
from app.domain.fish_species.services import (
    build_create_species_payload,
    build_update_species_payload,
)
from app.infrastructure.fish_species.repository import (
    create_species as repo_create_species,
    delete_species as repo_delete_species,
    list_active_species as repo_list_active_species,
    list_species as repo_list_species,
    update_species as repo_update_species,
)


router = APIRouter(prefix="/fish/species", tags=["fish-species"])


@router.get("", dependencies=[Depends(require_roles("admin"))])
async def list_species():
    return await repo_list_species()


@router.get("/active", dependencies=[Depends(get_current_user)])
async def list_active_species():
    return await repo_list_active_species()


@router.post("", dependencies=[Depends(require_roles("admin"))])
async def create_species(payload: dict[str, Any] = Body(...)):
    species_payload = build_create_species_payload(payload)
    return await repo_create_species(species_payload)


@router.patch("/{species_id}", dependencies=[Depends(require_roles("admin"))])
async def update_species(species_id: str, payload: dict[str, Any] = Body(...)):
    species_payload = build_update_species_payload(payload)
    doc = await repo_update_species(species_id, species_payload)
    if not doc:
        raise HTTPException(status_code=404, detail="Species not found")
    return doc


@router.delete("/{species_id}", dependencies=[Depends(require_roles("admin"))])
async def delete_species(species_id: str):
    deleted = await repo_delete_species(species_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Species not found")
    return {"status": "deleted"}
