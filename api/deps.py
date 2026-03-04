"""FastAPI dependencies shared across route modules."""

import logging
import time
from collections.abc import AsyncGenerator
from typing import Any, TypeVar

import httpx
from fastapi import Cookie, HTTPException, status
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import decode_jwt
from grug.config.settings import get_settings
from grug.db.session import get_session_factory

T = TypeVar("T")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Bounded in-memory cache for guild member role lookups.
# Key: (guild_id, user_id) -> (roles_list, timestamp)
# ---------------------------------------------------------------------------
_ROLE_CACHE_TTL = 300  # 5 minutes
_ROLE_CACHE_MAXSIZE = 2048


class _BoundedTTLCache:
    """Simple bounded TTL cache that evicts the oldest entry when full.

    Avoids unbounded memory growth for long-running processes with many
    unique (guild_id, user_id) pairs.
    """

    def __init__(self, maxsize: int, ttl: float) -> None:
        self._maxsize = maxsize
        self._ttl = ttl
        self._cache: dict[tuple[str, str], tuple[list[str], float]] = {}

    def get(self, key: tuple[str, str]) -> tuple[list[str], float] | None:
        return self._cache.get(key)

    def set(self, key: tuple[str, str], roles: list[str], timestamp: float) -> None:
        if len(self._cache) >= self._maxsize:
            # Evict the oldest entry by insertion order (dict preserves it in 3.7+).
            oldest = next(iter(self._cache))
            del self._cache[oldest]
        self._cache[key] = (roles, timestamp)

    def is_fresh(self, timestamp: float) -> bool:
        return time.time() - timestamp < self._ttl


_ROLE_CACHE = _BoundedTTLCache(maxsize=_ROLE_CACHE_MAXSIZE, ttl=_ROLE_CACHE_TTL)

# ---------------------------------------------------------------------------
# Bounded in-memory cache for guild owner lookups.
# Key: guild_id_str -> (owner_id_str, timestamp)
# ---------------------------------------------------------------------------
_GUILD_OWNER_CACHE: dict[str, tuple[str, float]] = {}

# ---------------------------------------------------------------------------
# Bounded in-memory cache for guild membership checks.
# Key: (guild_id, user_id) -> (is_member: bool, timestamp: float)
# ---------------------------------------------------------------------------
_MEMBER_CACHE: dict[tuple[str, str], tuple[bool, float]] = {}


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


async def assert_guild_member(guild_id: int | str, user: dict[str, Any]) -> None:
    """Raise 403 if the user is not a member of the given guild.

    Uses the Discord bot token to verify membership live, with a 5-minute
    in-process cache to avoid hammering the Discord API.  Super-admins bypass
    the check entirely.
    """
    if is_super_admin(user):
        return

    guild_id_str = str(guild_id)
    user_id = str(user.get("sub", user.get("id", "")))
    cache_key = (guild_id_str, user_id)
    now = time.time()

    cached = _MEMBER_CACHE.get(cache_key)
    if cached is not None and (now - cached[1]) < _ROLE_CACHE_TTL:
        if not cached[0]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not a member of this guild",
            )
        return

    try:
        bot_token = get_bot_token()
        async with httpx.AsyncClient(timeout=3.0) as http:
            resp = await http.get(
                f"https://discord.com/api/v10/guilds/{guild_id_str}/members/{user_id}",
                headers={"Authorization": f"Bot {bot_token}"},
            )
        is_member = resp.status_code == 200
    except HTTPException:
        return  # Bot token not configured — fail open
    except Exception:
        logger.warning(
            "Failed to check guild membership for user %s in guild %s",
            user_id,
            guild_id_str,
            exc_info=True,
        )
        return  # Fail open on transient errors

    # Evict oldest entry if cache is full
    if cache_key not in _MEMBER_CACHE and len(_MEMBER_CACHE) >= _ROLE_CACHE_MAXSIZE:
        oldest = next(iter(_MEMBER_CACHE))
        del _MEMBER_CACHE[oldest]
    _MEMBER_CACHE[cache_key] = (is_member, now)

    if not is_member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a member of this guild",
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


# --------------------------------------------------------------------------- #
# Permission helpers                                                           #
# --------------------------------------------------------------------------- #


def is_super_admin(user: dict[str, Any]) -> bool:
    """Check if the user is a Grug super-admin via environment variable."""
    settings = get_settings()
    return str(user.get("sub", user.get("id", ""))) in settings.grug_super_admin_ids


async def is_super_admin_full(user: dict[str, Any]) -> bool:
    """Check if the user is a super-admin by env var OR the DB ``is_super_admin`` flag."""
    if is_super_admin(user):
        return True
    from grug.db.models import GrugUser

    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(
            select(GrugUser).where(
                GrugUser.discord_user_id == int(user.get("sub", user.get("id", 0)))
            )
        )
        grug_user = result.scalar_one_or_none()
        return bool(grug_user and grug_user.is_super_admin)


async def assert_super_admin(user: dict[str, Any]) -> None:
    """Raise 403 if the user is not a super-admin (env var OR DB flag)."""
    if not await is_super_admin_full(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super-admin access required",
        )


async def has_can_invite(user: dict[str, Any]) -> bool:
    """Check if the user has the can_invite privilege."""
    if await is_super_admin_full(user):
        return True
    from grug.db.models import GrugUser

    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(
            select(GrugUser).where(
                GrugUser.discord_user_id == int(user.get("sub", user.get("id", 0)))
            )
        )
        grug_user = result.scalar_one_or_none()
        return grug_user.can_invite if grug_user else False


async def assert_can_invite(user: dict[str, Any]) -> None:
    """Raise 403 if the user cannot invite Grug to servers."""
    if not await has_can_invite(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invite privilege required",
        )


async def _has_grug_admin_role(guild_id: int | str, user_id: str) -> bool:
    """Check if a Discord user has the grug-admin role in a guild.

    Uses the bot token to query the Discord API for the member's roles,
    then cross-references with the stored grug_admin_role_id.  Results
    are cached for 5 minutes to avoid rate-limiting.
    """
    guild_id_str = str(guild_id)
    cache_key = (guild_id_str, user_id)
    now = time.time()

    # Check cache first
    cached_entry = _ROLE_CACHE.get(cache_key)
    if cached_entry and _ROLE_CACHE.is_fresh(cached_entry[1]):
        cached_roles, _ = cached_entry
        return await _check_role_match(guild_id_str, cached_roles)

    # Fetch from Discord
    try:
        bot_token = get_bot_token()
        async with httpx.AsyncClient() as http:
            resp = await http.get(
                f"https://discord.com/api/v10/guilds/{guild_id_str}/members/{user_id}",
                headers={"Authorization": f"Bot {bot_token}"},
            )
        if resp.status_code == 200:
            member_roles = resp.json().get("roles", [])
            _ROLE_CACHE.set(cache_key, member_roles, now)
            return await _check_role_match(guild_id_str, member_roles)
    except HTTPException:
        pass  # Bot token not configured
    except Exception:
        logger.warning(
            "Failed to check grug-admin role for user %s in guild %s",
            user_id,
            guild_id_str,
            exc_info=True,
        )

    return False


async def _check_role_match(guild_id_str: str, member_roles: list[str]) -> bool:
    """Check if any of the member's roles matches the grug_admin_role_id."""
    from grug.db.models import GuildConfig

    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(
            select(GuildConfig.grug_admin_role_id).where(
                GuildConfig.guild_id == int(guild_id_str)
            )
        )
        role_id = result.scalar_one_or_none()
        if role_id is None:
            return False
        return str(role_id) in member_roles


async def _is_guild_owner(guild_id: int | str, user_id: str) -> bool:
    """Return True if *user_id* is the owner of *guild_id*.

    Fetches the guild from the Discord API and caches the ``owner_id`` for
    5 minutes to avoid repeated lookups.
    """
    guild_id_str = str(guild_id)
    now = time.time()

    cached = _GUILD_OWNER_CACHE.get(guild_id_str)
    if cached is not None and (now - cached[1]) < _ROLE_CACHE_TTL:
        return cached[0] == user_id

    try:
        bot_token = get_bot_token()
        async with httpx.AsyncClient(timeout=3.0) as http:
            resp = await http.get(
                f"https://discord.com/api/v10/guilds/{guild_id_str}",
                headers={"Authorization": f"Bot {bot_token}"},
            )
        if resp.status_code == 200:
            owner_id = str(resp.json().get("owner_id", ""))
            if len(_GUILD_OWNER_CACHE) >= _ROLE_CACHE_MAXSIZE:
                del _GUILD_OWNER_CACHE[next(iter(_GUILD_OWNER_CACHE))]
            _GUILD_OWNER_CACHE[guild_id_str] = (owner_id, now)
            return owner_id == user_id
    except HTTPException:
        pass  # Bot token not configured
    except Exception:
        logger.warning(
            "Failed to check guild owner for guild %s",
            guild_id_str,
            exc_info=True,
        )

    return False


async def is_guild_admin(guild_id: int | str, user: dict[str, Any]) -> bool:
    """Check if the user has admin access to a guild.

    Admin access is granted if any of the following are true:
    1. The user is a Grug super-admin (env var or DB flag).
    2. The user is the Discord guild owner.
    3. The user has the ``grug-admin`` role in the Discord guild (live check).

    Note: Discord ADMINISTRATOR permission bits are no longer read from the JWT
    to avoid stale-permission escalation.  Discord server admins who are not
    the guild owner or a Grug super-admin must be assigned the ``grug-admin``
    role via guild config.
    """
    if await is_super_admin_full(user):
        return True
    user_id = str(user.get("sub", user.get("id", "")))
    if await _is_guild_owner(guild_id, user_id):
        return True
    return await _has_grug_admin_role(guild_id, user_id)


async def assert_guild_admin(guild_id: int | str, user: dict[str, Any]) -> None:
    """Raise 403 if the user does not have admin access to this guild."""
    if not await is_guild_admin(guild_id, user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Guild admin access required",
        )
