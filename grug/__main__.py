"""Main entry point for the grug package."""

from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from loguru import logger
from starlette.staticfiles import StaticFiles

from grug.admin import init_admin
from grug.api_routers import routers
from grug.assistant_interfaces.discord_interface import init_discord_bot
from grug.auth import init_auth
from grug.db import init_db
from grug.health import initialize_health_endpoints
from grug.log_config import init_logging
from grug.metrics import initialize_metrics
from grug.scheduler import init_scheduler
from grug.settings import settings

# TODO: create unit tests to make sure that the food and attendance tracking all works as expected!
# TODO: make unit tests for good code coverage
# TODO: evaluate adding this: https://github.com/aminalaee/fastapi-storages

if settings.sentry_dsn:
    import sentry_sdk

    # https://docs.sentry.io/platforms/python/#configure
    sentry_sdk.init(
        dsn=settings.sentry_dsn.get_secret_value(),
        # Set traces_sample_rate to 1.0 to capture 100%
        # of transactions for performance monitoring.
        traces_sample_rate=1.0,
        # Set profiles_sample_rate to 1.0 to profile 100%
        # of sampled transactions.
        # We recommend adjusting this value in production.
        profiles_sample_rate=1.0,
    )

logger.error("This is an error message")


@asynccontextmanager
async def lifespan(fast_api_app: FastAPI):
    """Lifespan event handler for the FastAPI app."""
    init_logging()
    await init_db()
    init_auth(fast_api_app)
    init_admin(fast_api_app)
    init_discord_bot()
    init_scheduler()
    yield


app = FastAPI(lifespan=lifespan, title=f"{settings.openai_assistant_name} API")
app.mount("/static", StaticFiles(directory=settings.root_dir / "grug" / "static"), name="static")

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
    uvicorn.run(app, port=settings.api_port, host=settings.api_host, log_level="info")
