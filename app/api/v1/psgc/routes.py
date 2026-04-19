from fastapi import APIRouter, Path

from app.data.ph_zip_codes import get_zip_code

router = APIRouter(prefix="/psgc", tags=["psgc"])


@router.get("/zipcode/{city_code}")
async def lookup_zip_code(
    city_code: str = Path(
        ...,
        min_length=9,
        max_length=9,
        pattern=r"^\d{9}$",
        description="9-digit PSGC city/municipality code, e.g. 072217000",
    ),
):
    """Return the Philippine zip code for a PSGC city/municipality code.

    This is a **public** endpoint (no authentication required).
    """
    zip_code = get_zip_code(city_code)
    return {"zipCode": zip_code}
