"""AI chat cog — routes Discord messages to the Grug agent."""

import logging
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import select

from grug.agent.core import GrugAgent
from grug.bot.cogs.base import GrugCogBase
from grug.utils import get_campaign_id_for_channel

logger = logging.getLogger(__name__)

# Sentinel guild_id for DM sessions (no real guild)
_DM_GUILD_ID = 0


class AIChatCog(GrugCogBase, name="AI Chat"):
    """Handles AI-powered conversations with Grug."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._agent = GrugAgent()
        self._history_flushed = False

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        """Flush conversation history on startup when FLUSH_CHAT_HISTORY=true."""
        if self._history_flushed:
            return
        self._history_flushed = True

        from grug.config.settings import get_settings

        if not get_settings().flush_chat_history:
            return

        try:
            from grug.db.models import ConversationMessage
            from grug.db.session import get_session_factory
            from sqlalchemy import update

            factory = get_session_factory()
            async with factory() as session:
                result = await session.execute(
                    update(ConversationMessage)
                    .where(ConversationMessage.archived.is_(False))
                    .values(archived=True)
                )
                await session.commit()
                count = result.rowcount  # type: ignore[union-attr]
                if count:
                    logger.info(
                        "FLUSH_CHAT_HISTORY enabled — archived %d messages", count
                    )
        except Exception:
            logger.exception("Failed to flush conversation history on startup")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        """Log every message for context awareness; respond when @mentioned or always-on."""
        if message.author.bot:
            return

        # ---------------------------------------------------------------- DMs
        if message.guild is None:
            await self._handle_dm(message)
            return

        # -------------------------------------------------------- Guild messages
        mentioned = self.bot.user in message.mentions if self.bot.user else False
        channel_cfg = await _get_channel_config(message.channel.id)
        always_on = channel_cfg.always_respond if channel_cfg else False

        # Always log the message so Grug stays context-aware in the channel.
        await self._agent.save_passive_message(
            guild_id=message.guild.id,
            channel_id=message.channel.id,
            content=message.clean_content,
            author_id=message.author.id,
            author_name=message.author.display_name,
        )

        if not (mentioned or always_on):
            return

        content = message.clean_content
        if self.bot.user:
            content = content.replace(f"@{self.bot.user.display_name}", "").strip()
        if not content:
            content = "Hello!"

        # Resolve campaign_id for this channel (used for campaign-scoped RAG).
        campaign_id = await get_campaign_id_for_channel(message.channel.id)

        # Determine the effective context cutoff: channel override > guild default.
        context_cutoff = await _get_effective_context_cutoff(
            guild_id=message.guild.id,
            channel_id=message.channel.id,
        )

        try:
            async with message.channel.typing():
                response = await self._agent.respond(
                    guild_id=message.guild.id,
                    channel_id=message.channel.id,
                    user_id=message.author.id,
                    username=message.author.display_name,
                    message=content,
                    campaign_id=campaign_id,
                    context_cutoff=context_cutoff,
                )
            for chunk in _split_message(response):
                await message.channel.send(chunk)
        except Exception:
            logger.exception(
                "Unhandled error in on_message for guild %s channel %s",
                message.guild.id,
                message.channel.id,
            )
            await message.channel.send(
                "Grug brain hurt... something go very wrong. Try again?"
            )

    async def _handle_dm(self, message: discord.Message) -> None:
        """Process a direct message from a user."""
        content = message.clean_content.strip() or "Hello!"
        user_id = message.author.id

        # Resolve the user's active character and its campaign.
        active_character_id, campaign_id = await _get_user_character_context(user_id)

        # Load the user's DM context cutoff (if configured).
        dm_context_cutoff = await _get_dm_context_cutoff(user_id)

        async with message.channel.typing():
            response = await self._agent.respond(
                guild_id=_DM_GUILD_ID,
                channel_id=message.channel.id,  # DM channel ID is stable per user
                user_id=user_id,
                username=message.author.display_name,
                message=content,
                campaign_id=campaign_id,
                active_character_id=active_character_id,
                is_dm_session=True,
                context_cutoff=dm_context_cutoff,
            )

        for chunk in _split_message(response):
            await message.channel.send(chunk)

    @app_commands.command(
        name="chat_here",
        description="Toggle Grug responding to every message in this channel.",
    )
    @app_commands.checks.has_permissions(manage_channels=True)
    async def toggle_always_on(self, interaction: discord.Interaction) -> None:
        cid = interaction.channel_id
        gid = interaction.guild_id
        if cid is None or gid is None:
            return

        from grug.db.models import ChannelConfig
        from grug.db.session import get_session_factory
        from grug.utils import ensure_guild

        await ensure_guild(gid)
        factory = get_session_factory()
        async with factory() as session:
            result = await session.execute(
                select(ChannelConfig).where(ChannelConfig.channel_id == cid)
            )
            cfg = result.scalar_one_or_none()
            if cfg is None:
                cfg = ChannelConfig(
                    guild_id=gid,
                    channel_id=cid,
                    always_respond=True,
                )
                session.add(cfg)
                await session.commit()
                await interaction.response.send_message(
                    "Grug listen to everything in this channel now! 👂"
                )
            else:
                cfg.always_respond = not cfg.always_respond
                cfg.updated_at = datetime.now(timezone.utc)
                await session.commit()
                if cfg.always_respond:
                    await interaction.response.send_message(
                        "Grug listen to everything in this channel now! 👂"
                    )
                else:
                    await interaction.response.send_message(
                        "Grug go quiet now. Only respond when mentioned."
                    )

    @app_commands.command(
        name="clear_history",
        description="Clear Grug's conversation history for this channel.",
    )
    @app_commands.checks.has_permissions(manage_messages=True)
    async def clear_history(self, interaction: discord.Interaction) -> None:
        from grug.db.session import get_session_factory
        from grug.db.models import ConversationMessage
        from sqlalchemy import delete

        guild_id = interaction.guild_id if interaction.guild_id else _DM_GUILD_ID
        factory = get_session_factory()
        async with factory() as session:
            await session.execute(
                delete(ConversationMessage).where(
                    ConversationMessage.guild_id == guild_id,
                    ConversationMessage.channel_id == interaction.channel_id,
                )
            )
            await session.commit()
        await interaction.response.send_message(
            "Grug forget everything said here. Fresh start! 🧹"
        )


def _split_message(text: str, limit: int = 2000) -> list[str]:
    """Split a long message into ≤2000-char chunks, respecting line breaks."""
    if len(text) <= limit:
        return [text]
    chunks: list[str] = []
    while text:
        if len(text) <= limit:
            chunks.append(text)
            break
        split_at = text.rfind("\n", 0, limit)
        if split_at == -1:
            split_at = limit
        chunks.append(text[:split_at])
        text = text[split_at:].lstrip("\n")
    return chunks


async def _get_channel_config(channel_id: int):
    """Return the ChannelConfig row for a channel, or None if none exists."""
    from grug.db.models import ChannelConfig
    from grug.db.session import get_session_factory

    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(
            select(ChannelConfig).where(ChannelConfig.channel_id == channel_id)
        )
        return result.scalar_one_or_none()


async def _get_effective_context_cutoff(
    guild_id: int, channel_id: int
) -> datetime | None:
    """Return the context cutoff for a channel, falling back to the guild setting.

    Precedence: channel-level ``context_cutoff`` > guild-level ``context_cutoff``.
    Returns ``None`` if neither is set (no cutoff applied).
    """
    from grug.db.models import ChannelConfig, GuildConfig
    from grug.db.session import get_session_factory

    factory = get_session_factory()
    async with factory() as session:
        ch_result = await session.execute(
            select(ChannelConfig).where(ChannelConfig.channel_id == channel_id)
        )
        ch_cfg = ch_result.scalar_one_or_none()
        if ch_cfg is not None and ch_cfg.context_cutoff is not None:
            return ch_cfg.context_cutoff

        g_result = await session.execute(
            select(GuildConfig).where(GuildConfig.guild_id == guild_id)
        )
        g_cfg = g_result.scalar_one_or_none()
        if g_cfg is not None:
            return g_cfg.context_cutoff
    return None


async def _get_dm_context_cutoff(discord_user_id: int) -> datetime | None:
    """Return the DM context cutoff for a user, or None if not configured."""
    from grug.db.models import UserProfile
    from grug.db.session import get_session_factory

    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(
            select(UserProfile).where(UserProfile.discord_user_id == discord_user_id)
        )
        profile = result.scalar_one_or_none()
        if profile is not None:
            return profile.dm_context_cutoff
    return None


async def _get_user_character_context(
    discord_user_id: int,
) -> tuple[int | None, int | None]:
    """Return (active_character_id, campaign_id) for a user's DM session."""
    from grug.db.models import Character, UserProfile
    from grug.db.session import get_session_factory

    factory = get_session_factory()
    async with factory() as session:
        profile_result = await session.execute(
            select(UserProfile).where(UserProfile.discord_user_id == discord_user_id)
        )
        profile = profile_result.scalar_one_or_none()
        if profile is None or profile.active_character_id is None:
            return None, None

        char_result = await session.execute(
            select(Character).where(Character.id == profile.active_character_id)
        )
        character = char_result.scalar_one_or_none()
        if character is None:
            return None, None

        return character.id, character.campaign_id


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AIChatCog(bot))
