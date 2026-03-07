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

        # Check guild owner + grug-admin role via Discord bot cache.
        guild_cfg = (
            await session.execute(
                select(GuildConfig).where(GuildConfig.guild_id == guild_id)
            )
        ).scalar_one_or_none()

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
                    # Guild owner always has admin rights.
                    if guild.owner_id == user_id:
                        return True
                    # Check grug-admin role if one is configured.
                    if guild_cfg is not None and guild_cfg.grug_admin_role_id:
                        member = guild.get_member(user_id)
                        if member is not None:
                            if any(
                                r.id == guild_cfg.grug_admin_role_id
                                for r in member.roles
                            ):
                                return True
        except Exception:
            logger.debug(
                "Could not check guild owner / grug-admin role for user %d in guild %d",
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

        Returns the campaign name, game system, active status, the Game Master
        (if assigned), a roster of characters (name, level, class, ancestry),
        and the next upcoming session event (if any).
        Use when a player asks about the campaign, the party, the GM, or who is playing.
        """
        from datetime import datetime, timezone

        from grug.db.models import CalendarEvent, Campaign, Character
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

            # Next upcoming session event for this campaign.
            now = datetime.now(timezone.utc)
            next_event = (
                await session.execute(
                    select(CalendarEvent)
                    .where(
                        CalendarEvent.campaign_id == campaign_id,
                        CalendarEvent.start_time >= now,
                    )
                    .order_by(CalendarEvent.start_time)
                    .limit(1)
                )
            ).scalar_one_or_none()

        lines = [
            f"Campaign: {campaign.name}",
            f"System: {campaign.system}",
            f"Status: {'active' if campaign.is_active else 'inactive'}",
            f"Schedule mode: {campaign.schedule_mode}",
        ]
        if campaign.gm_discord_user_id:
            lines.append(f"Game Master: <@{campaign.gm_discord_user_id}>")
        lines += [
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

        # Append next session info if available.
        if next_event:
            lines += [
                "",
                f"📅 Next session: **{next_event.title}** — "
                f"{next_event.start_time.strftime('%A, %B %d at %H:%M UTC')}",
            ]
            if next_event.location:
                lines.append(f"  Location: {next_event.location}")
        else:
            lines += ["", "No upcoming session scheduled."]

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

        # Check access: own character, guild admin, or campaign GM can see full details.
        is_owner = match.owner_discord_user_id == ctx.deps.user_id
        if not is_owner:
            admin = await _is_admin(ctx)
            # Also check if the requesting user is the GM for this campaign.
            if not admin:
                from grug.db.models import Campaign

                async with factory() as session:
                    campaign = (
                        await session.execute(
                            select(Campaign).where(Campaign.id == campaign_id)
                        )
                    ).scalar_one_or_none()
                    is_gm = (
                        campaign is not None
                        and campaign.gm_discord_user_id == ctx.deps.user_id
                    )
            else:
                is_gm = False
        else:
            admin = False
            is_gm = False

        sd = match.structured_data or {}
        if is_owner or admin or is_gm:
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
                f"(Full details are only available to the character's owner, GM, or an admin.)"
            )

    @agent.tool
    async def create_character_from_pathbuilder(
        ctx: RunContext[GrugDeps],
        pathbuilder_id: int,
    ) -> str:
        """Create a campaign character by importing from Pathbuilder 2e.

        When a user shares their Pathbuilder ID (the number from the Export JSON
        page URL), fetch their character and add it to the current campaign,
        owned by the requesting user.

        Use when someone says things like:
        - "my pathbuilder ID is 123456"
        - "create my character from pathbuilder 123456"
        - "import pathbuilder 123456"

        Only works when this channel has a linked campaign.  If the server-side
        fetch is blocked by Cloudflare, instruct the user to use the web UI
        instead (open their campaign, add character, enter the Pathbuilder ID).
        """
        from datetime import datetime, timezone

        from grug.character.pathbuilder import (
            PathbuilderError,
            fetch_pathbuilder_character,
        )
        from grug.character.indexer import CharacterIndexer
        from grug.db.models import Campaign, Character
        from grug.db.session import get_session_factory

        campaign_id = ctx.deps.campaign_id
        if campaign_id is None:
            return (
                "There's no campaign linked to this channel, so I can't add a character here. "
                "An admin needs to link a campaign first."
            )

        user_id = ctx.deps.user_id

        try:
            structured_data = await fetch_pathbuilder_character(pathbuilder_id)
        except PathbuilderError as exc:
            return (
                f"I couldn't fetch your character from Pathbuilder: {exc}\n\n"
                "Pathbuilder's site sometimes blocks automated requests. "
                "Try importing via the **web dashboard** instead: open your campaign, "
                "add a character, and enter your Pathbuilder ID in the Character Sheet section."
            )

        char_name = structured_data.get("name") or f"Pathbuilder #{pathbuilder_id}"

        db_factory = get_session_factory()
        async with db_factory() as session:
            campaign = (
                await session.execute(
                    select(Campaign).where(
                        Campaign.id == campaign_id,
                        Campaign.guild_id == ctx.deps.guild_id,
                    )
                )
            ).scalar_one_or_none()
            if campaign is None:
                return "Campaign not found."

            character = Character(
                owner_discord_user_id=user_id,
                campaign_id=campaign_id,
                name=char_name,
                system="pf2e",
                structured_data=structured_data,
                pathbuilder_id=pathbuilder_id,
                pathbuilder_synced_at=datetime.now(timezone.utc),
            )
            session.add(character)
            await session.commit()
            await session.refresh(character)
            character_id = character.id

        # Index for RAG search
        try:
            raw_text = structured_data.get("name", "")  # minimal index text
            indexer = CharacterIndexer()
            await indexer.index_character(character_id, raw_text)
        except Exception:
            logger.debug(
                "Failed to index character %d after Pathbuilder import", character_id
            )

        level = structured_data.get("level")
        class_name = structured_data.get("class_and_subclass")
        ancestry = structured_data.get("race_or_ancestry")
        details = [
            x
            for x in [
                f"Level {level}" if level else None,
                class_name,
                ancestry,
            ]
            if x
        ]
        summary = " · ".join(details) if details else ""

        return (
            f"Done! **{char_name}** has been added to the campaign."
            + (f"\n{summary}" if summary else "")
            + "\nYou can view and manage your character sheet in the web dashboard."
        )

    @agent.tool
    async def check_party_passives(
        ctx: RunContext[GrugDeps],
        skill: str = "perception",
        dc: int | None = None,
    ) -> str:
        """Check the party's passive skill scores — GM / admin only.

        Use when the GM wants to know whether any party member would passively
        notice something (a hidden trap, a lying NPC, a concealed door, etc.)
        without alerting the players by asking for rolls.

        Common queries that should trigger this tool:
        - "Can anyone in the party notice the hidden door?"
        - "What are the party's passive perceptions?"
        - "Check passive investigation against DC 15"
        - "Would anyone see through the disguise? DC 18 Insight"
        - "Passive stealth check for the party"

        Parameters
        ----------
        skill:
            The skill to check passively.  Defaults to ``"perception"``.
            Examples: perception, insight, investigation, stealth, arcana.
        dc:
            Optional Difficulty Class to check against.  When provided the
            result indicates which characters meet or exceed the DC.
        """
        from grug.character.passives import compute_passive_score
        from grug.db.models import Campaign, Character
        from grug.db.session import get_session_factory

        # GM / admin gate.
        campaign_id = ctx.deps.campaign_id
        if campaign_id is None:
            return (
                "No campaign is linked to this channel. "
                "An admin can create one with /campaign create."
            )

        admin = await _is_admin(ctx)
        factory = get_session_factory()

        # Also allow the campaign's designated GM.
        is_gm = False
        async with factory() as session:
            campaign = (
                await session.execute(
                    select(Campaign).where(Campaign.id == campaign_id)
                )
            ).scalar_one_or_none()
            if campaign is None:
                return "Campaign not found."
            if campaign.gm_discord_user_id == ctx.deps.user_id:
                is_gm = True

        if not admin and not is_gm:
            return (
                "Only the GM or an admin can check passive scores — "
                "wouldn't want to spoil the surprise for the players!"
            )

        # Fetch party characters.
        async with factory() as session:
            chars = (
                (
                    await session.execute(
                        select(Character).where(
                            Character.campaign_id == campaign_id
                        )
                    )
                )
                .scalars()
                .all()
            )

        if not chars:
            return "No characters in this campaign yet."

        skill_label = skill.strip().replace("_", " ").title()
        lines = [f"**Passive {skill_label} — Party Check**"]
        if dc is not None:
            lines[0] += f" (DC {dc})"
        lines.append("")

        any_score = False
        for c in chars:
            sd = c.structured_data or {}
            score = compute_passive_score(sd, skill)
            if score is None:
                lines.append(f"• **{c.name}**: — *(insufficient sheet data)*")
                continue
            any_score = True
            if dc is not None:
                result = "✅ pass" if score >= dc else "❌ fail"
                lines.append(f"• **{c.name}**: {score} {result}")
            else:
                lines.append(f"• **{c.name}**: {score}")

        if not any_score:
            lines.append(
                "\n⚠️ Could not compute passive scores — "
                "character sheets may need to be uploaded or synced."
            )

        return "\n".join(lines)
