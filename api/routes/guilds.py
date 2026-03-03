"""Guild routes — list guilds, config CRUD, and channel proxy."""

import logging
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import (
    assert_guild_admin,
    assert_guild_member,
    get_bot_token,
    get_current_user,
    get_db,
    get_or_404,
    is_guild_admin,
)
from api.schemas import (
    ChannelConfigOut,
    ChannelConfigUpdate,
    DiscordChannelOut,
    GuildConfigOut,
    GuildConfigUpdate,
    GuildOut,
)
from grug.db.models import ChannelConfig, GuildConfig

logger = logging.getLogger(__name__)

router = APIRouter(tags=["guilds"])


@router.get("/api/guilds", response_model=list[GuildOut])
async def list_guilds(
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[GuildOut]:
    """Return guilds where the user AND the bot are both members."""
    user_guild_ids = {int(g["id"]) for g in user.get("guilds", [])}
    result = await db.execute(select(GuildConfig))
    configs = result.scalars().all()
    bot_guild_ids = {c.guild_id for c in configs}
    shared = user_guild_ids & bot_guild_ids

    guilds: list[GuildOut] = []
    for g in user.get("guilds", []):
        if int(g["id"]) in shared:
            admin = await is_guild_admin(g["id"], user)
            guilds.append(
                GuildOut(id=g["id"], name=g["name"], icon=g.get("icon"), is_admin=admin)
            )
    return guilds


@router.get("/api/guilds/{guild_id}/config", response_model=GuildConfigOut)
async def get_guild_config(
    guild_id: int,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GuildConfig:
    """Get the configuration for a specific guild.

    If announce_channel_id is not set, attempts to auto-populate it from the
    guild's system messages channel as configured in Discord.
    """
    assert_guild_member(guild_id, user)
    cfg = await get_or_404(
        db,
        GuildConfig,
        GuildConfig.guild_id == guild_id,
        detail="Guild config not found",
    )

    # Auto-populate announce channel from Discord system channel on first load
    if cfg.announce_channel_id is None:
        try:
            bot_token = get_bot_token()
            async with httpx.AsyncClient() as http:
                resp = await http.get(
                    f"https://discord.com/api/v10/guilds/{guild_id}",
                    headers={"Authorization": f"Bot {bot_token}"},
                )
            if resp.status_code == 200:
                system_channel_id = resp.json().get("system_channel_id")
                if system_channel_id:
                    cfg.announce_channel_id = int(system_channel_id)
                    cfg.updated_at = datetime.now(timezone.utc)
                    await db.commit()
                    await db.refresh(cfg)
        except HTTPException:
            pass  # Bot token not configured — non-fatal
        except Exception:
            logger.warning(
                "Failed to auto-populate announce_channel_id for guild %d",
                guild_id,
                exc_info=True,
            )

    return cfg


@router.patch("/api/guilds/{guild_id}/config", response_model=GuildConfigOut)
async def update_guild_config(
    guild_id: int,
    body: GuildConfigUpdate,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GuildConfig:
    """Update guild configuration fields."""
    assert_guild_member(guild_id, user)
    await assert_guild_admin(guild_id, user)
    cfg = await get_or_404(
        db,
        GuildConfig,
        GuildConfig.guild_id == guild_id,
        detail="Guild config not found",
    )

    for field in body.model_fields_set:
        value = getattr(body, field)
        if field == "announce_channel_id" and value is not None:
            value = int(value)
        setattr(cfg, field, value)

    cfg.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(cfg)
    return cfg


@router.get("/api/guilds/{guild_id}/channels", response_model=list[DiscordChannelOut])
async def list_guild_channels(
    guild_id: int,
    user: dict[str, Any] = Depends(get_current_user),
) -> list[DiscordChannelOut]:
    """Proxy Discord's channel list so the web UI can display channel names."""
    assert_guild_member(guild_id, user)
    bot_token = get_bot_token()
    async with httpx.AsyncClient() as http:
        resp = await http.get(
            f"https://discord.com/api/v10/guilds/{guild_id}/channels",
            headers={"Authorization": f"Bot {bot_token}"},
        )
    if resp.status_code != 200:
        raise HTTPException(
            status_code=502, detail="Failed to fetch channels from Discord"
        )
    channels = resp.json()
    return [
        DiscordChannelOut(id=str(c["id"]), name=c["name"], type=c["type"])
        for c in channels
        if c.get("type") in (0, 5)
    ]


@router.get(
    "/api/guilds/{guild_id}/channels/{channel_id}/config",
    response_model=ChannelConfigOut,
)
async def get_channel_config(
    guild_id: int,
    channel_id: int,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChannelConfig:
    """Return the per-channel config, creating a default row if none exists."""
    assert_guild_member(guild_id, user)
    result = await db.execute(
        select(ChannelConfig).where(
            ChannelConfig.channel_id == channel_id,
            ChannelConfig.guild_id == guild_id,
        )
    )
    cfg = result.scalar_one_or_none()
    if cfg is None:
        from grug.utils import ensure_guild

        await ensure_guild(guild_id)
        cfg = ChannelConfig(guild_id=guild_id, channel_id=channel_id)
        db.add(cfg)
        await db.commit()
        await db.refresh(cfg)
    return cfg


@router.patch(
    "/api/guilds/{guild_id}/channels/{channel_id}/config",
    response_model=ChannelConfigOut,
)
async def update_channel_config(
    guild_id: int,
    channel_id: int,
    body: ChannelConfigUpdate,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChannelConfig:
    """Update per-channel config fields (always_respond, context_cutoff)."""
    assert_guild_member(guild_id, user)
    await assert_guild_admin(guild_id, user)
    result = await db.execute(
        select(ChannelConfig).where(
            ChannelConfig.channel_id == channel_id,
            ChannelConfig.guild_id == guild_id,
        )
    )
    cfg = result.scalar_one_or_none()
    if cfg is None:
        from grug.utils import ensure_guild

        await ensure_guild(guild_id)
        cfg = ChannelConfig(guild_id=guild_id, channel_id=channel_id)
        db.add(cfg)
    if "always_respond" in body.model_fields_set and body.always_respond is not None:
        cfg.always_respond = body.always_respond
    if "context_cutoff" in body.model_fields_set:
        cfg.context_cutoff = body.context_cutoff
    cfg.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(cfg)
    return cfg


# --------------------------------------------------------------------------- #
# Calendar feed token                                                          #
# --------------------------------------------------------------------------- #


@router.get("/api/guilds/{guild_id}/calendar-token")
async def get_calendar_token(
    guild_id: int,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return the guild's calendar feed token, generating one if missing.

    Any guild member can call this endpoint to get the token (so they can
    subscribe to the feed).  The token acts like a shareable-but-secret URL
    segment — anyone with the URL can read the calendar, so the regenerate
    endpoint is admin-only.
    """
    import secrets

    assert_guild_member(guild_id, user)
    cfg = await get_or_404(
        db,
        GuildConfig,
        GuildConfig.guild_id == guild_id,
        detail="Guild config not found",
    )
    if not cfg.calendar_token:
        cfg.calendar_token = secrets.token_urlsafe(32)
        cfg.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(cfg)
    return {"token": cfg.calendar_token}


@router.post("/api/guilds/{guild_id}/calendar-token/regenerate")
async def regenerate_calendar_token(
    guild_id: int,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Regenerate the guild's calendar feed token (invalidates existing subscriptions).

    All subscribers must update their feed URL with the new token.  Admin-only.
    """
    import secrets

    assert_guild_member(guild_id, user)
    await assert_guild_admin(guild_id, user)
    cfg = await get_or_404(
        db,
        GuildConfig,
        GuildConfig.guild_id == guild_id,
        detail="Guild config not found",
    )
    cfg.calendar_token = secrets.token_urlsafe(32)
    cfg.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(cfg)
    return {"token": cfg.calendar_token}
