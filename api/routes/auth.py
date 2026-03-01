"""Auth routes — Discord OAuth2 login/callback/logout and /auth/me."""

from typing import Any

from fastapi import APIRouter, Depends, Response
from fastapi.responses import RedirectResponse

from api.auth import (
    build_discord_oauth_url,
    create_jwt,
    exchange_code,
    fetch_discord_guilds,
    fetch_discord_user,
)
from api.deps import get_current_user
from api.schemas import UserOut
from grug.config.settings import get_settings

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/discord/login")
async def discord_login() -> RedirectResponse:
    """Redirect the user to Discord's OAuth2 authorization page."""
    return RedirectResponse(build_discord_oauth_url())


@router.get("/discord/callback")
async def discord_callback(code: str, response: Response) -> RedirectResponse:
    """Handle Discord's OAuth2 callback — exchange the code and set a session cookie."""
    token_data = await exchange_code(code)
    access_token = token_data["access_token"]
    user = await fetch_discord_user(access_token)
    guilds = await fetch_discord_guilds(access_token)

    payload: dict[str, Any] = {
        "sub": user["id"],
        "username": user["username"],
        "discriminator": user.get("discriminator", "0"),
        "avatar": user.get("avatar"),
        "guilds": [
            {"id": g["id"], "name": g["name"], "icon": g.get("icon")} for g in guilds
        ],
    }
    jwt_token = create_jwt(payload)
    response = RedirectResponse(
        url=f"{get_settings().frontend_url}/dashboard", status_code=302
    )
    response.set_cookie(
        key="session",
        value=jwt_token,
        httponly=True,
        samesite="lax",
        max_age=86400,
    )
    return response


@router.get("/me", response_model=UserOut)
async def get_me(user: dict[str, Any] = Depends(get_current_user)) -> UserOut:
    """Return the currently authenticated user's profile."""
    return UserOut(
        id=user["sub"],
        username=user["username"],
        discriminator=user["discriminator"],
        avatar=user.get("avatar"),
    )


@router.post("/logout")
async def logout(
    response: Response,
    _user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, str]:
    """Clear the session cookie."""
    response.delete_cookie("session")
    return {"status": "ok"}
