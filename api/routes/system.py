"""System / public info routes — no auth required."""

from fastapi import APIRouter

from api.schemas import DefaultsOut
from grug.config.settings import get_settings

router = APIRouter(tags=["system"])


@router.get("/api/defaults", response_model=DefaultsOut)
async def get_defaults() -> DefaultsOut:
    """Return server-wide defaults that the web UI can use as fallback values."""
    settings = get_settings()
    return DefaultsOut(default_timezone=settings.default_timezone)
