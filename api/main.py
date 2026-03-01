"""FastAPI application for the Grug web UI companion.

This module creates the ASGI app and includes route modules.  Domain logic,
models, and database sessions all live in the ``grug`` package — the API
layer is a thin HTTP skin on top.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import auth, documents, events, glossary, guilds
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

# Register route modules.
app.include_router(auth.router)
app.include_router(guilds.router)
app.include_router(events.router)
app.include_router(documents.router)
app.include_router(glossary.router)
