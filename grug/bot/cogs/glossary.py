"""Glossary cog — Discord slash commands for managing server/channel glossary terms."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import select

from grug.db.models import GlossaryTerm, GlossaryTermHistory
from grug.db.session import get_session_factory

logger = logging.getLogger(__name__)

_TERMS_PER_PAGE = 10


class GlossaryCog(commands.Cog, name="Glossary"):
    """Slash commands for managing the guild's TTRPG glossary."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    glossary_group = app_commands.Group(
        name="glossary",
        description="Manage server/channel-specific term definitions",
    )

    # ---------------------------------------------------------------------- lookup

    @glossary_group.command(name="lookup", description="Look up a term in the glossary")
    @app_commands.describe(term="The term to search for")
    async def lookup(self, interaction: discord.Interaction, term: str) -> None:
        factory = get_session_factory()
        async with factory() as session:
            result = await session.execute(
                select(GlossaryTerm)
                .where(
                    GlossaryTerm.guild_id == interaction.guild_id,
                    GlossaryTerm.term.ilike(f"%{term}%"),
                    GlossaryTerm.channel_id.in_(
                        [interaction.channel_id, None]  # type: ignore[list-item]
                    ),
                )
                .order_by(
                    # Channel-scoped rows first (higher precedence).
                    GlossaryTerm.channel_id.is_(None).asc(),
                    GlossaryTerm.term.asc(),
                )
            )
            matches = result.scalars().all()

        if not matches:
            await interaction.response.send_message(
                f"Grug not find '{term}' in glossary.", ephemeral=True
            )
            return

        embed = discord.Embed(
            title=f"📖 Glossary: '{term}'", color=discord.Color.blurple()
        )
        seen: set[str] = set()
        for m in matches:
            key = m.term.lower()
            if key not in seen:
                scope = "channel override" if m.channel_id else "server-wide"
                if m.ai_generated:
                    source = "🤖 AI"
                elif m.originally_ai_generated:
                    source = "🤖→👤 AI-origin (edited)"
                else:
                    source = "👤 Human"
                embed.add_field(
                    name=f"{m.term} ({scope})",
                    value=f"{m.definition}\n*Source: {source}*",
                    inline=False,
                )
                seen.add(key)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ---------------------------------------------------------------------- add

    @glossary_group.command(name="add", description="Add a new glossary term")
    @app_commands.describe(
        term="The term to define",
        definition="The definition",
        channel="Optional: scope this definition to a specific channel",
    )
    async def add(
        self,
        interaction: discord.Interaction,
        term: str,
        definition: str,
        channel: discord.TextChannel | None = None,
    ) -> None:
        channel_id = channel.id if channel else None
        guild_id = interaction.guild_id

        factory = get_session_factory()
        async with factory() as session:
            # Check for duplicate.
            result = await session.execute(
                select(GlossaryTerm).where(
                    GlossaryTerm.guild_id == guild_id,
                    GlossaryTerm.channel_id == channel_id,
                    GlossaryTerm.term.ilike(term),
                )
            )
            if result.scalar_one_or_none() is not None:
                await interaction.response.send_message(
                    f"A definition for **{term}** already exists in that scope. "
                    f"Use `/glossary edit` to change it.",
                    ephemeral=True,
                )
                return

            from grug.db.models import GuildConfig

            cfg_result = await session.execute(
                select(GuildConfig).where(GuildConfig.guild_id == guild_id)
            )
            if cfg_result.scalar_one_or_none() is None:
                session.add(GuildConfig(guild_id=guild_id))

            entry = GlossaryTerm(
                guild_id=guild_id,
                channel_id=channel_id,
                term=term,
                definition=definition,
                ai_generated=False,
                originally_ai_generated=False,
                created_by=interaction.user.id,
                updated_at=datetime.now(timezone.utc),
            )
            session.add(entry)
            await session.commit()

        scope = f" in {channel.mention}" if channel else " (server-wide)"
        await interaction.response.send_message(
            f"📖 Added **{term}**{scope} to the glossary!", ephemeral=True
        )

    # ---------------------------------------------------------------------- edit

    @glossary_group.command(name="edit", description="Edit an existing glossary term")
    @app_commands.describe(
        term="The exact term to edit",
        definition="The new definition",
    )
    async def edit(
        self,
        interaction: discord.Interaction,
        term: str,
        definition: str,
    ) -> None:
        guild_id = interaction.guild_id
        factory = get_session_factory()
        async with factory() as session:
            result = await session.execute(
                select(GlossaryTerm).where(
                    GlossaryTerm.guild_id == guild_id,
                    GlossaryTerm.term.ilike(term),
                )
            )
            entry = result.scalar_one_or_none()
            if entry is None:
                await interaction.response.send_message(
                    f"No glossary entry found for **{term}**.", ephemeral=True
                )
                return

            # Snapshot history before mutating.
            history = GlossaryTermHistory(
                term_id=entry.id,
                guild_id=entry.guild_id,
                old_term=entry.term,
                old_definition=entry.definition,
                old_ai_generated=entry.ai_generated,
                changed_by=interaction.user.id,
            )
            session.add(history)
            entry.definition = definition
            entry.ai_generated = False  # human edit clears AI ownership
            entry.updated_at = datetime.now(timezone.utc)
            await session.commit()

        await interaction.response.send_message(
            f"📖 Updated **{term}** in the glossary.", ephemeral=True
        )

    # ---------------------------------------------------------------------- remove

    @glossary_group.command(name="remove", description="Remove a glossary term")
    @app_commands.describe(term="The exact term to remove")
    async def remove(
        self,
        interaction: discord.Interaction,
        term: str,
    ) -> None:
        guild_id = interaction.guild_id
        factory = get_session_factory()
        async with factory() as session:
            result = await session.execute(
                select(GlossaryTerm).where(
                    GlossaryTerm.guild_id == guild_id,
                    GlossaryTerm.term.ilike(term),
                )
            )
            entry = result.scalar_one_or_none()
            if entry is None:
                await interaction.response.send_message(
                    f"No glossary entry found for **{term}**.", ephemeral=True
                )
                return

            was_ai = entry.ai_generated
            await session.delete(entry)
            await session.commit()

        note = (
            " *(that one was AI-generated — Grug can recreate it if needed)*"
            if was_ai
            else ""
        )
        await interaction.response.send_message(
            f"🗑️ Removed **{term}** from the glossary.{note}", ephemeral=True
        )

    # ---------------------------------------------------------------------- list

    @glossary_group.command(
        name="list", description="List glossary terms for this server"
    )
    @app_commands.describe(
        channel="Optional: list only terms for a specific channel",
        page="Page number (default: 1)",
    )
    async def list_terms(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel | None = None,
        page: int = 1,
    ) -> None:
        guild_id = interaction.guild_id
        channel_id = channel.id if channel else None
        factory = get_session_factory()

        async with factory() as session:
            stmt = select(GlossaryTerm).where(GlossaryTerm.guild_id == guild_id)
            if channel_id is not None:
                stmt = stmt.where(GlossaryTerm.channel_id == channel_id)
            stmt = stmt.order_by(
                GlossaryTerm.channel_id.is_(None).asc(),
                GlossaryTerm.term.asc(),
            )
            result = await session.execute(stmt)
            all_terms = result.scalars().all()

        if not all_terms:
            scope = f" for {channel.mention}" if channel else ""
            await interaction.response.send_message(
                f"No glossary terms found{scope}.", ephemeral=True
            )
            return

        offset = (page - 1) * _TERMS_PER_PAGE
        page_terms = all_terms[offset : offset + _TERMS_PER_PAGE]
        total_pages = (len(all_terms) + _TERMS_PER_PAGE - 1) // _TERMS_PER_PAGE

        embed = discord.Embed(
            title=f"📖 Glossary (page {page}/{total_pages})",
            color=discord.Color.blurple(),
        )
        for t in page_terms:
            scope = "📌 channel" if t.channel_id else "🌐 server"
            if t.ai_generated:
                source = "🤖"
            elif t.originally_ai_generated:
                source = "🤖→👤"
            else:
                source = "👤"
            short_def = (
                t.definition[:80] + "…" if len(t.definition) > 80 else t.definition
            )
            embed.add_field(
                name=f"{source} {t.term} ({scope})",
                value=short_def,
                inline=False,
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    cog = GlossaryCog(bot)
    await bot.add_cog(cog)
    # Note: add_cog() automatically registers app_commands.Group attributes
    # defined on the Cog class.  Calling bot.tree.add_command() here as well
    # would double-register the group and raise CommandAlreadyRegistered.
