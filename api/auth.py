"""Discord OAuth helpers and JWT creation/verification."""

from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from jose import jwt

from .config import settings

DISCORD_API = "https://discord.com/api/v10"
ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = 24


def build_discord_oauth_url(state: str = "") -> str:
    params = (
        f"client_id={settings.discord_client_id}"
        f"&redirect_uri={settings.discord_redirect_uri}"
        "&response_type=code"
        "&scope=identify+guilds" + (f"&state={state}" if state else "")
    )
    return f"https://discord.com/api/oauth2/authorize?{params}"


async def exchange_code(code: str) -> dict[str, Any]:
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
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{DISCORD_API}/users/@me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        resp.raise_for_status()
        return resp.json()


async def fetch_discord_guilds(access_token: str) -> list[dict[str, Any]]:
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{DISCORD_API}/users/@me/guilds",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        resp.raise_for_status()
        return resp.json()


def create_jwt(payload: dict[str, Any]) -> str:
    data = payload.copy()
    data["exp"] = datetime.now(timezone.utc) + timedelta(hours=TOKEN_EXPIRE_HOURS)
    return jwt.encode(data, settings.web_secret_key, algorithm=ALGORITHM)


def decode_jwt(token: str) -> dict[str, Any]:
    return jwt.decode(token, settings.web_secret_key, algorithms=[ALGORITHM])
