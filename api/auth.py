"""Discord OAuth helpers and JWT creation/verification."""

import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from jose import jwt

from grug.config.settings import get_settings

DISCORD_API = "https://discord.com/api/v10"
ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = 24

# In-memory revocation set.  Entries are JWT IDs (jti) that have been
# explicitly invalidated (e.g. on logout).  This is process-scoped — a
# server restart clears it, but token TTL is only 24 h so the exposure
# window is bounded.  Replace with a Redis/DB set for multi-process deploys.
_REVOKED_TOKENS: set[str] = set()


def generate_state() -> str:
    """Generate a cryptographically random OAuth state token."""
    return secrets.token_urlsafe(32)


def revoke_token(jti: str) -> None:
    """Add a JWT ID to the revocation set."""
    _REVOKED_TOKENS.add(jti)


def build_discord_oauth_url(state: str) -> str:
    """Build the Discord OAuth2 authorization URL.

    ``state`` is required — callers must generate one with :func:`generate_state`
    and store it in a short-lived signed cookie to prevent login-CSRF.
    """
    settings = get_settings()
    params = (
        f"client_id={settings.discord_client_id}"
        f"&redirect_uri={settings.discord_redirect_uri}"
        "&response_type=code"
        f"&scope=identify+guilds"
        f"&state={state}"
    )
    return f"https://discord.com/api/oauth2/authorize?{params}"


async def exchange_code(code: str) -> dict[str, Any]:
    """Exchange an OAuth2 authorization code for an access token."""
    settings = get_settings()
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{DISCORD_API}/oauth2/token",
            data={
                "client_id": settings.discord_client_id,
                "client_secret": settings.discord_client_secret,
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": settings.discord_redirect_uri,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        resp.raise_for_status()
        return resp.json()


async def fetch_discord_user(access_token: str) -> dict[str, Any]:
    """Fetch the authenticated Discord user's profile."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{DISCORD_API}/users/@me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        resp.raise_for_status()
        return resp.json()


async def fetch_discord_guilds(access_token: str) -> list[dict[str, Any]]:
    """Fetch the guilds the authenticated user belongs to."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{DISCORD_API}/users/@me/guilds",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        resp.raise_for_status()
        return resp.json()


def create_jwt(payload: dict[str, Any]) -> str:
    """Create a signed JWT with a 24-hour expiry and a unique jti claim."""
    settings = get_settings()
    data = payload.copy()
    data["exp"] = datetime.now(timezone.utc) + timedelta(hours=TOKEN_EXPIRE_HOURS)
    data["jti"] = str(uuid.uuid4())
    return jwt.encode(data, settings.web_secret_key, algorithm=ALGORITHM)


def decode_jwt(token: str) -> dict[str, Any]:
    """Decode and verify a JWT, rejecting explicitly revoked tokens."""
    settings = get_settings()
    payload = jwt.decode(token, settings.web_secret_key, algorithms=[ALGORITHM])
    jti = payload.get("jti")
    if jti and jti in _REVOKED_TOKENS:
        from jose import JWTError

        raise JWTError("Token has been revoked")
    return payload
