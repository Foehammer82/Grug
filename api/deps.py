"""FastAPI dependencies shared across route modules."""

from collections.abc import AsyncGenerator
from typing import Any, TypeVar

from fastapi import Cookie, HTTPException, status
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import decode_jwt
from grug.db.session import get_session_factory

T = TypeVar("T")


async def get_current_user(
    session: str | None = Cookie(default=None),
) -> dict[str, Any]:
    """Extract and verify the current user from the session cookie.

    Normalises the decoded JWT so that ``user["id"]`` always equals
    ``user["sub"]`` (the Discord user ID).  This avoids inconsistencies
    across route handlers.
    """
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )
    try:
        payload = decode_jwt(session)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session"
        )
    # Ensure "id" is always present as an alias of "sub".
    if "id" not in payload:
        payload["id"] = payload["sub"]
    return payload


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async SQLAlchemy session from the shared session factory."""
    factory = get_session_factory()
    async with factory() as session:
        yield session


def assert_guild_member(guild_id: int | str, user: dict[str, Any]) -> None:
    """Raise 403 if the user is not a member of the given guild."""
    guild_ids = {g["id"] for g in user.get("guilds", [])}
    if str(guild_id) not in guild_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not a member of this guild"
        )


async def get_or_404(
    db: AsyncSession,
    model: type[T],
    *filters,
    detail: str = "Not found",
) -> T:
    """Fetch a single row or raise 404."""
    result = await db.execute(select(model).where(*filters))
    entity = result.scalar_one_or_none()
    if entity is None:
        raise HTTPException(status_code=404, detail=detail)
    return entity


def get_bot_token() -> str:
    """Return the Discord bot token, preferring the API-specific setting."""
    from grug.config.settings import get_settings

    settings = get_settings()
    token = settings.discord_bot_token or settings.discord_token
    if not token:
        raise HTTPException(status_code=503, detail="Bot token not configured")
    return token
