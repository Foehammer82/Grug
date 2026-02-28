"""FastAPI dependencies."""

from typing import Any

from fastapi import Cookie, HTTPException, status
from jose import JWTError

from .auth import decode_jwt


async def get_current_user(session: str | None = Cookie(default=None)) -> dict[str, Any]:
    if not session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        return decode_jwt(session)
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session")
