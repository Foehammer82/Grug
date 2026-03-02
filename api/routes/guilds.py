"""Guild routes — list guilds, config CRUD, and channel proxy."""

from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import assert_guild_member, get_current_user, get_db
from api.schemas import (
    ChannelConfigOut,
    ChannelConfigUpdate,
    DiscordChannelOut,
    GuildConfigOut,
    GuildConfigUpdate,
    GuildOut,
)
from grug.config.settings import get_settings
from grug.db.models import ChannelConfig, GuildConfig

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
    return [
        GuildOut(id=g["id"], name=g["name"], icon=g.get("icon"))
        for g in user.get("guilds", [])
        if int(g["id"]) in shared
    ]


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
    result = await db.execute(
        select(GuildConfig).where(GuildConfig.guild_id == guild_id)
    )
    cfg = result.scalar_one_or_none()
    if cfg is None:
        raise HTTPException(status_code=404, detail="Guild config not found")

    # Auto-populate announce channel from Discord system channel on first load
    if cfg.announce_channel_id is None:
        settings = get_settings()
        bot_token = settings.discord_bot_token or settings.discord_token
        if bot_token:
            try:
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
            except Exception:
                pass  # Non-fatal; return config as-is

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
    result = await db.execute(
        select(GuildConfig).where(GuildConfig.guild_id == guild_id)
    )
    cfg = result.scalar_one_or_none()
    if cfg is None:
        raise HTTPException(status_code=404, detail="Guild config not found")
    if body.timezone is not None:
        cfg.timezone = body.timezone
    if "announce_channel_id" in body.model_fields_set:
        # Convert to int here — Python handles large snowflake IDs without precision loss
        val = body.announce_channel_id
        cfg.announce_channel_id = int(val) if val is not None else None
    if "context_cutoff" in body.model_fields_set:
        cfg.context_cutoff = body.context_cutoff
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
    settings = get_settings()
    bot_token = settings.discord_bot_token or settings.discord_token
    if not bot_token:
        raise HTTPException(status_code=503, detail="Bot token not configured")
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
        select(ChannelConfig).where(ChannelConfig.channel_id == channel_id)
    )
    cfg = result.scalar_one_or_none()
    if cfg is None:
        # Lazily create a default row.
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
    result = await db.execute(
        select(ChannelConfig).where(ChannelConfig.channel_id == channel_id)
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
