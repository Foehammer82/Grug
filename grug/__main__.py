"""Main entry point for the grug package."""

import asyncio
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from loguru import logger

from grug.admin import init_admin
from grug.api_routers import routers
from grug.assistant_interfaces.discord_interface import start_discord_bot
from grug.auth import init_auth
from grug.db import init_db
from grug.health import initialize_health_endpoints
from grug.log_config import init_logging
from grug.metrics import initialize_metrics
from grug.scheduler import start_scheduler
from grug.settings import settings


# noinspection PyUnusedLocal,PyAsyncCall
@asynccontextmanager
async def lifespan(fast_api_app: FastAPI):
    """Lifespan event handler for the FastAPI app."""
    init_logging()
    init_db()
    init_auth(fast_api_app)
    init_admin(fast_api_app)
    asyncio.create_task(start_discord_bot())
    asyncio.create_task(start_scheduler())
    yield


app = FastAPI(lifespan=lifespan)

# Include all API routers
for router in routers:
    app.include_router(router)

# Initialize metrics if enabled
if settings.enable_metrics:
    initialize_metrics(app)

# Initialize health endpoints if enabled
if settings.enable_health_endpoint:
    initialize_health_endpoints(app)


if __name__ == "__main__":
    logger.info({"app_settings": settings.dict()})

    uvicorn.run(app, port=settings.api_port, host=settings.api_host)
