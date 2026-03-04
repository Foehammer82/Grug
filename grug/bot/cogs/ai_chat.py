"""AI chat cog — routes Discord messages to the Grug agent."""

import io
import logging
import re
from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import select

from grug.agent.core import AgentResponse, GrugAgent
from grug.bot.cogs.base import GrugCogBase
from grug.config.settings import get_settings
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
        auto_respond = channel_cfg.auto_respond if channel_cfg else False
        auto_respond_threshold = (
            channel_cfg.auto_respond_threshold if channel_cfg else 0.0
        )

        # Always log the message so Grug stays context-aware in the channel.
        await self._agent.save_passive_message(
            guild_id=message.guild.id,
            channel_id=message.channel.id,
            content=message.clean_content,
            author_id=message.author.id,
            author_name=message.author.display_name,
        )

        should_respond = mentioned
        if not should_respond and auto_respond:
            if auto_respond_threshold == 0.0:
                # Fast path: threshold 0.0 means always respond — skip LLM scoring.
                should_respond = True
            else:
                from grug.bot.auto_respond import score_auto_respond
                from grug.db.models import ConversationMessage
                from grug.db.session import get_session_factory

                # Fetch the last 5 messages in this channel as scored context.
                recent_context: list[str] = []
                try:
                    _factory = get_session_factory()
                    async with _factory() as _session:
                        _result = await _session.execute(
                            select(ConversationMessage)
                            .where(
                                ConversationMessage.channel_id == message.channel.id,
                                ConversationMessage.archived.is_(False),
                            )
                            .order_by(ConversationMessage.created_at.desc())
                            .limit(6)
                        )
                        _rows = list(reversed(_result.scalars().all()))
                        # Drop the last row — it's the message we just passively saved.
                        context_rows = _rows[:-1] if _rows else []
                        recent_context = [
                            f"{r.author_name or 'Grug'}: {r.content}"
                            for r in context_rows
                        ]
                except Exception:
                    logger.exception(
                        "Failed to fetch recent context for auto-respond scorer"
                    )

                score = await score_auto_respond(
                    message_content=message.clean_content,
                    recent_context=recent_context,
                    guild_id=message.guild.id,
                )
                should_respond = score >= auto_respond_threshold
                logger.info(
                    "Auto-respond | score=%.3f threshold=%.3f → %s | %r",
                    score,
                    auto_respond_threshold,
                    "RESPOND" if should_respond else "skip",
                    message.clean_content[:80],
                )

        if not should_respond:
            return

        content = message.clean_content
        if self.bot.user:
            content = content.replace(f"@{self.bot.user.display_name}", "").strip()
        if not content:
            content = "Hello!"

        # Resolve campaign_id for this channel (used for campaign-scoped RAG).
        campaign_id = await get_campaign_id_for_channel(message.channel.id)

        # Determine the effective context cutoff from the rolling lookback window.
        lookback = get_settings().agent_context_lookback_days
        context_cutoff = datetime.now(timezone.utc) - timedelta(days=lookback)

        try:
            async with message.channel.typing():
                agent_resp = await self._agent.respond(
                    guild_id=message.guild.id,
                    channel_id=message.channel.id,
                    user_id=message.author.id,
                    username=message.author.display_name,
                    message=content,
                    campaign_id=campaign_id,
                    context_cutoff=context_cutoff,
                )
            await _deliver_response(message, agent_resp)
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
            agent_resp = await self._agent.respond(
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

        for chunk in _split_message(agent_resp.text):
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
                    auto_respond=True,
                    auto_respond_threshold=0.5,
                )
                session.add(cfg)
                await session.commit()
                await interaction.response.send_message(
                    "Grug listen to everything in this channel now! 👂"
                )
            else:
                cfg.auto_respond = not cfg.auto_respond
                cfg.updated_at = datetime.now(timezone.utc)
                await session.commit()
                if cfg.auto_respond:
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


# Pattern used by agent tools to signal that a file should be DM'd.
# The sentinel is stripped from the public channel message.
_DM_FILE_RE = re.compile(r"\[DM_FILE:[^\]]+\]\s*")


async def _deliver_response(
    message: discord.Message, agent_resp: AgentResponse
) -> None:
    """Send the agent response to the channel and DM any pending files.

    If the agent included ``[DM_FILE:filename]`` sentinels in the text,
    those are stripped from the public message and the corresponding files
    are sent via DM.
    """
    # Strip DM_FILE sentinels from the public text.
    public_text = _DM_FILE_RE.sub("", agent_resp.text).strip()

    # Send the public reply in the channel.
    for chunk in _split_message(public_text):
        await message.channel.send(chunk)

    # DM any pending files to the requesting user.
    if agent_resp.dm_files:
        try:
            dm_channel = message.author.dm_channel or await message.author.create_dm()
            for filename, file_bytes in agent_resp.dm_files:
                df = discord.File(io.BytesIO(file_bytes), filename=filename)
                await dm_channel.send(
                    "Here's that character sheet you asked for, adventurer! 📜",
                    file=df,
                )
        except discord.Forbidden:
            await message.channel.send(
                "Grug tried to send you a DM but your DMs are closed! "
                "Enable DMs from server members and try again."
            )
        except Exception:
            logger.exception("Failed to DM files to user %s", message.author.id)
            await message.channel.send("Grug had trouble sending the file. Try again?")


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


async def _get_dm_context_cutoff(discord_user_id: int) -> datetime | None:
    """Return the DM context cutoff for a user, falling back to the configured rolling window."""
    from grug.db.models import UserProfile
    from grug.db.session import get_session_factory

    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(
            select(UserProfile).where(UserProfile.discord_user_id == discord_user_id)
        )
        profile = result.scalar_one_or_none()
        if profile is not None and profile.dm_context_cutoff is not None:
            return profile.dm_context_cutoff
    lookback = get_settings().agent_context_lookback_days
    return datetime.now(timezone.utc) - timedelta(days=lookback)


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
