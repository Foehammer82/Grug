"""FastAPI application for the Grug web UI companion.

This module creates the ASGI app and includes route modules.  Domain logic,
models, and database sessions all live in the ``grug`` package — the API
layer is a thin HTTP skin on top.
"""

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.deps import get_current_user
from api.routes import (
    admin,
    auth,
    campaigns,
    documents,
    events,
    glossary,
    guilds,
    personal,
    system,
)
from grug.config.settings import get_settings

settings = get_settings()

app = FastAPI(title="Grug API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.web_cors_origins.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Public auth routes (login redirect & OAuth callback must be unauthenticated).
app.include_router(auth.router)
# Public system routes (server defaults etc. — no auth required).
app.include_router(system.router)

# All remaining routes require an authenticated session at the router level.
# Individual endpoints that also declare Depends(get_current_user) to access
# the user object are fine — FastAPI deduplicates the dependency call.
_auth_required = [Depends(get_current_user)]
app.include_router(guilds.router, dependencies=_auth_required)
app.include_router(events.router, dependencies=_auth_required)
app.include_router(personal.router, dependencies=_auth_required)
app.include_router(documents.router, dependencies=_auth_required)
app.include_router(glossary.router, dependencies=_auth_required)
app.include_router(campaigns.router, dependencies=_auth_required)
app.include_router(admin.router, dependencies=_auth_required)
