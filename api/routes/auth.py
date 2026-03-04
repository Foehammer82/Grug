"""Auth routes — Discord OAuth2 login/callback/logout and /auth/me."""

from typing import Any

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from fastapi.responses import RedirectResponse

from api.auth import (
    build_discord_oauth_url,
    create_jwt,
    exchange_code,
    fetch_discord_user,
    generate_state,
    revoke_token,
)
from api.deps import get_current_user, has_can_invite, is_super_admin_full
from api.schemas import UserOut
from grug.config.settings import get_settings

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/discord/login")
async def discord_login(response: Response) -> RedirectResponse:
    """Redirect the user to Discord's OAuth2 authorization page.

    Generates a random ``state`` token, stores it in a short-lived httponly
    cookie, and includes it in the authorization URL.  The callback validates
    the round-trip to prevent login-CSRF attacks.
    """
    state = generate_state()
    redirect = RedirectResponse(build_discord_oauth_url(state))
    # Short-lived, httponly, samesite=lax — valid for 10 minutes.
    redirect.set_cookie(
        key="oauth_state",
        value=state,
        httponly=True,
        samesite="lax",
        secure=True,
        max_age=600,
    )
    return redirect


@router.get("/discord/callback")
async def discord_callback(
    code: str,
    state: str,
    response: Response,
    oauth_state: str | None = Cookie(default=None),
) -> RedirectResponse:
    """Handle Discord's OAuth2 callback — exchange the code and set a session cookie.

    Validates the ``state`` parameter against the signed cookie set during
    :func:`discord_login` to prevent login-CSRF.
    """
    if not oauth_state or state != oauth_state:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OAuth state — possible CSRF attempt",
        )

    token_data = await exchange_code(code)
    access_token = token_data["access_token"]
    user = await fetch_discord_user(access_token)

    payload: dict[str, Any] = {
        "sub": user["id"],
        "username": user["username"],
        "discriminator": user.get("discriminator", "0"),
        "avatar": user.get("avatar"),
    }
    jwt_token = create_jwt(payload)
    redirect = RedirectResponse(
        url=f"{get_settings().frontend_url}/dashboard", status_code=302
    )
    # Clear the one-time state cookie.
    redirect.delete_cookie("oauth_state")
    redirect.set_cookie(
        key="session",
        value=jwt_token,
        httponly=True,
        samesite="lax",
        secure=True,
        max_age=86400,
    )
    return redirect


@router.get("/me", response_model=UserOut)
async def get_me(user: dict[str, Any] = Depends(get_current_user)) -> UserOut:
    """Return the currently authenticated user's profile."""
    impersonator = user.get("impersonator")
    return UserOut(
        id=user["sub"],
        username=user["username"],
        discriminator=user["discriminator"],
        avatar=user.get("avatar"),
        is_super_admin=await is_super_admin_full(user),
        can_invite=await has_can_invite(user),
        impersonating=impersonator is not None,
        impersonator_id=impersonator.get("sub") if impersonator else None,
        impersonator_username=impersonator.get("username") if impersonator else None,
    )


@router.post("/logout")
async def logout(
    response: Response,
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, str]:
    """Invalidate the session cookie and revoke the JWT."""
    jti = user.get("jti")
    if jti:
        revoke_token(jti)
    response.delete_cookie("session")
    return {"status": "ok"}
