"""Main entry point for the grug package."""

from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from starlette.middleware import Middleware
from starlette.middleware.sessions import SessionMiddleware
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

if settings.sentry_dsn:
    import sentry_sdk

    sentry_sdk.init(
        dsn=settings.sentry_dsn.get_secret_value(),
        traces_sample_rate=settings.sentry_traces_sample_rate,
        profiles_sample_rate=settings.sentry_profiles_sample_rate,
    )


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


app = FastAPI(
    lifespan=lifespan,
    title=f"{settings.openai_assistant_name} API",
    docs_url="/api",
    redoc_url=None,
    middleware=[Middleware(SessionMiddleware, secret_key=settings.security_key.get_secret_value())],
)
app.mount(
    "/static",
    StaticFiles(directory=settings.root_dir / "grug" / "static"),
    name="static",
)

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
    uvicorn.run(
        app,
        port=settings.api_port,
        host=settings.api_host,
        log_level="info",
    )
