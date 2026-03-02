"""System / public info routes — no auth required."""

from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api.schemas import DefaultsOut
from grug.config.settings import get_settings

router = APIRouter(tags=["system"])

# Roadmap lives at the repo root, two levels above this file (api/routes/system.py).
_ROADMAP_PATH = Path(__file__).parent.parent.parent / "roadmap.md"


class RoadmapOut(BaseModel):
    content: str


@router.get("/api/defaults", response_model=DefaultsOut)
async def get_defaults() -> DefaultsOut:
    """Return server-wide defaults that the web UI can use as fallback values."""
    settings = get_settings()
    return DefaultsOut(default_timezone=settings.default_timezone)


@router.get("/api/roadmap", response_model=RoadmapOut)
async def get_roadmap() -> RoadmapOut:
    """Return the raw Markdown content of roadmap.md. Public — no auth required."""
    if not _ROADMAP_PATH.exists():
        raise HTTPException(status_code=404, detail="Roadmap not found")
    return RoadmapOut(content=_ROADMAP_PATH.read_text(encoding="utf-8"))
