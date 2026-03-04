"""Campaign and party tools for the Grug agent.

Registers tools that let Grug look up campaign info, party roster,
and individual character sheets — respecting ownership and admin
permissions so players only see their own detailed data while GMs
and admins can access everything.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from pydantic_ai import RunContext
from sqlalchemy import select

from grug.agent.core import GrugDeps

if TYPE_CHECKING:
    from pydantic_ai import Agent

logger = logging.getLogger(__name__)


async def _is_admin(ctx: RunContext[GrugDeps]) -> bool:
    """Check whether the requesting user is a Grug admin.

    Checks:
    1. ``GRUG_SUPER_ADMIN_IDS`` env var.
    2. ``UserProfile.is_super_admin`` flag in the DB.
    3. Whether the user has the guild's ``grug-admin`` role (looked up via
       the Discord bot's cached member data).
    """
    from grug.config.settings import get_settings
    from grug.db.models import GrugUser, GuildConfig
    from grug.db.session import get_session_factory

    user_id = ctx.deps.user_id
    guild_id = ctx.deps.guild_id

    settings = get_settings()
    if str(user_id) in settings.grug_super_admin_ids:
        return True

    factory = get_session_factory()
    async with factory() as session:
        # Check DB super-admin flag.
        grug_user = (
            await session.execute(
                select(GrugUser).where(GrugUser.discord_user_id == user_id)
            )
        ).scalar_one_or_none()
        if grug_user is not None and grug_user.is_super_admin:
            return True

        # Check grug-admin role via Discord bot cache.
        guild_cfg = (
            await session.execute(
                select(GuildConfig).where(GuildConfig.guild_id == guild_id)
            )
        ).scalar_one_or_none()
        if guild_cfg is not None and guild_cfg.grug_admin_role_id:
            try:
                import discord

                bot: discord.Client | None = None
                try:
                    from grug.bot.client import get_bot

                    bot = get_bot()
                except Exception:
                    pass
                if bot is not None:
                    guild = bot.get_guild(guild_id)
                    if guild is not None:
                        member = guild.get_member(user_id)
                        if member is not None:
                            if any(
                                r.id == guild_cfg.grug_admin_role_id
                                for r in member.roles
                            ):
                                return True
            except Exception:
                logger.debug(
                    "Could not check grug-admin role for user %d in guild %d",
                    user_id,
                    guild_id,
                    exc_info=True,
                )
    return False


def register_campaign_tools(agent: Agent[GrugDeps, str]) -> None:
    """Register all campaign / party tools on *agent*."""

    @agent.tool
    async def get_campaign_info(ctx: RunContext[GrugDeps]) -> str:
        """Get information about this channel's campaign.

        Returns the campaign name, game system, active status, and a roster
        of characters (name, level, class, ancestry).  Use when a player
        asks about the campaign, the party, or who is playing.
        """
        from grug.db.models import Campaign, Character
        from grug.db.session import get_session_factory

        campaign_id = ctx.deps.campaign_id
        if campaign_id is None:
            return (
                "No campaign is linked to this channel. "
                "An admin can create one with /campaign create."
            )

        factory = get_session_factory()
        async with factory() as session:
            campaign = (
                await session.execute(
                    select(Campaign).where(Campaign.id == campaign_id)
                )
            ).scalar_one_or_none()
            if campaign is None:
                return "Campaign not found."

            chars = (
                (
                    await session.execute(
                        select(Character).where(Character.campaign_id == campaign_id)
                    )
                )
                .scalars()
                .all()
            )

        lines = [
            f"Campaign: {campaign.name}",
            f"System: {campaign.system}",
            f"Status: {'active' if campaign.is_active else 'inactive'}",
            "",
            "Party roster:",
        ]
        if not chars:
            lines.append("  (no characters yet)")
        for c in chars:
            sd = c.structured_data or {}
            level = sd.get("level", "?")
            ancestry = sd.get("ancestry") or sd.get("race") or ""
            cls = sd.get("class") or sd.get("classes") or ""
            if isinstance(cls, list):
                cls = "/".join(str(x) for x in cls)
            detail = f"Lvl {level}"
            if cls:
                detail += f" {cls}"
            if ancestry:
                detail += f" {ancestry}"
            owner = ""
            if c.owner_discord_user_id:
                owner = f" (player <@{c.owner_discord_user_id}>)"
            lines.append(f"  - {c.name}: {detail}{owner}")

        return "\n".join(lines)

    @agent.tool
    async def get_party_character(
        ctx: RunContext[GrugDeps], character_name: str
    ) -> str:
        """Look up a specific character in this channel's campaign by name.

        Returns the full character sheet if the requesting user owns the
        character or is a guild admin.  For characters owned by other
        players, returns only public info (name, class, level, ancestry).

        Parameters
        ----------
        character_name:
            The name (or partial name) of the character to look up.
        """
        from grug.db.models import Character
        from grug.db.session import get_session_factory

        campaign_id = ctx.deps.campaign_id
        if campaign_id is None:
            return (
                "No campaign is linked to this channel. "
                "An admin can create one with /campaign create."
            )

        factory = get_session_factory()
        async with factory() as session:
            chars = (
                (
                    await session.execute(
                        select(Character).where(Character.campaign_id == campaign_id)
                    )
                )
                .scalars()
                .all()
            )

        if not chars:
            return "No characters in this campaign."

        # Fuzzy name match: exact first, then case-insensitive contains.
        search = character_name.strip().lower()
        match = None
        for c in chars:
            if c.name.lower() == search:
                match = c
                break
        if match is None:
            for c in chars:
                if search in c.name.lower():
                    match = c
                    break
        if match is None:
            names = ", ".join(c.name for c in chars)
            return f"No character matching '{character_name}' found. Available: {names}"

        # Check access: own character or admin can see full details.
        is_owner = match.owner_discord_user_id == ctx.deps.user_id
        admin = await _is_admin(ctx) if not is_owner else False

        sd = match.structured_data or {}
        if is_owner or admin:
            # Full details
            lines = [
                f"Character: {match.name}",
                f"System: {match.system}",
                f"Structured data: {json.dumps(sd, indent=2)}",
            ]
            if match.notes:
                lines += ["", f"Notes: {match.notes}"]
            if match.raw_sheet_text:
                lines += ["", "Raw sheet text:", match.raw_sheet_text[:3000]]
            return "\n".join(lines)
        else:
            # Public summary only
            level = sd.get("level", "?")
            ancestry = sd.get("ancestry") or sd.get("race") or ""
            cls = sd.get("class") or sd.get("classes") or ""
            if isinstance(cls, list):
                cls = "/".join(str(x) for x in cls)
            hp = sd.get("hp", {})
            hp_str = ""
            if isinstance(hp, dict):
                hp_max = hp.get("max", "?")
                hp_str = f", HP max: {hp_max}"
            ac = sd.get("ac") or sd.get("armor_class")
            ac_str = f", AC: {ac}" if ac else ""
            return (
                f"Character: {match.name} — Lvl {level} {cls} {ancestry}"
                f"{hp_str}{ac_str}\n"
                f"(Full details are only available to the character's owner.)"
            )
