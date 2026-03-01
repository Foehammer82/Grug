"""FastAPI dependencies shared across route modules."""

from collections.abc import AsyncGenerator
from typing import Any

from fastapi import Cookie, HTTPException, status
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import decode_jwt
from grug.db.session import get_session_factory


async def get_current_user(
    session: str | None = Cookie(default=None),
) -> dict[str, Any]:
    """Extract and verify the current user from the session cookie."""
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )
    try:
        return decode_jwt(session)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session"
        )


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
