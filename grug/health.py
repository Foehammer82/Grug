"""Health checks and status endpoints for the Grug application."""

from fastapi import FastAPI
from pydantic import BaseModel, computed_field

from grug.assistant_interfaces.discord_interface.bot import discord_bot
from grug.db import check_db_connection
from grug.scheduler import scheduler


class Health(BaseModel):

    @computed_field
    @property
    def scheduler(self) -> str:
        return scheduler.state.name

    @computed_field
    @property
    def discord(self) -> str:
        return discord_bot.status.name

    @computed_field
    @property
    def postgres(self) -> str:
        return "OK" if check_db_connection() else "DOWN"


def initialize_health_endpoints(app: FastAPI):
    @app.get("/health", tags=["System"])
    async def healthy() -> Health:
        """Health check route."""
        return Health()
