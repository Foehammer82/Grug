"""AI chat cog — routes Discord messages to the Grug agent."""

import logging

import discord
from discord.ext import commands
from sqlalchemy import select

from grug.agent.core import GrugAgent
from grug.utils import get_campaign_id_for_channel

logger = logging.getLogger(__name__)

# Channels where Grug replies to every message (not just mentions)
_ALWAYS_RESPOND_CHANNELS: set[int] = set()

# Sentinel guild_id for DM sessions (no real guild)
_DM_GUILD_ID = 0


class AIChatCog(commands.Cog, name="AI Chat"):
    """Handles AI-powered conversations with Grug."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._agent = GrugAgent()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        """Respond to messages that mention Grug, are in always-on channels, or are DMs."""
        if message.author.bot:
            return

        # ---------------------------------------------------------------- DMs
        if message.guild is None:
            await self._handle_dm(message)
            return

        # -------------------------------------------------------- Guild messages
        mentioned = self.bot.user in message.mentions if self.bot.user else False
        always_on = message.channel.id in _ALWAYS_RESPOND_CHANNELS

        if not (mentioned or always_on):
            return

        content = message.clean_content
        if self.bot.user:
            content = content.replace(f"@{self.bot.user.display_name}", "").strip()
        if not content:
            content = "Hello!"

        # Resolve campaign_id for this channel (used for campaign-scoped RAG).
        campaign_id = await get_campaign_id_for_channel(message.channel.id)

        async with message.channel.typing():
            response = await self._agent.respond(
                guild_id=message.guild.id,
                channel_id=message.channel.id,
                user_id=message.author.id,
                username=message.author.display_name,
                message=content,
                campaign_id=campaign_id,
            )

        for chunk in _split_message(response):
            await message.channel.send(chunk)

    async def _handle_dm(self, message: discord.Message) -> None:
        """Process a direct message from a user."""
        content = message.clean_content.strip() or "Hello!"
        user_id = message.author.id

        # Resolve the user's active character and its campaign.
        active_character_id, campaign_id = await _get_user_character_context(user_id)

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
            )

        for chunk in _split_message(response):
            await message.channel.send(chunk)

    @commands.command(name="chat_here", aliases=["always_on"])
    @commands.has_permissions(manage_channels=True)
    async def toggle_always_on(self, ctx: commands.Context) -> None:
        """Toggle Grug responding to every message in this channel (manage channels required)."""
        cid = ctx.channel.id
        if cid in _ALWAYS_RESPOND_CHANNELS:
            _ALWAYS_RESPOND_CHANNELS.discard(cid)
            await ctx.send("Grug go quiet now. Only respond when mentioned.")
        else:
            _ALWAYS_RESPOND_CHANNELS.add(cid)
            await ctx.send("Grug listen to everything in this channel now! 👂")

    @commands.command(name="clear_history")
    @commands.has_permissions(manage_messages=True)
    async def clear_history(self, ctx: commands.Context) -> None:
        """Clear Grug's conversation history for this channel."""
        from grug.db.session import get_session_factory
        from grug.db.models import ConversationMessage
        from sqlalchemy import delete

        guild_id = ctx.guild.id if ctx.guild else _DM_GUILD_ID
        factory = get_session_factory()
        async with factory() as session:
            await session.execute(
                delete(ConversationMessage).where(
                    ConversationMessage.guild_id == guild_id,
                    ConversationMessage.channel_id == ctx.channel.id,
                )
            )
            await session.commit()
        await ctx.send("Grug forget everything said here. Fresh start! 🧹")


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
