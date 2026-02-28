"""AI chat cog — routes Discord messages to the Grug agent."""

import logging

import discord
from discord.ext import commands

from grug.agent.core import GrugAgent

logger = logging.getLogger(__name__)

# Channels where Grug replies to every message (not just mentions)
_ALWAYS_RESPOND_CHANNELS: set[int] = set()


class AIChatCog(commands.Cog, name="AI Chat"):
    """Handles AI-powered conversations with Grug."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._agent = GrugAgent()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        """Respond to messages that mention Grug or are in always-on channels."""
        if message.author.bot:
            return
        if message.guild is None:
            return

        mentioned = self.bot.user in message.mentions if self.bot.user else False
        always_on = message.channel.id in _ALWAYS_RESPOND_CHANNELS

        if not (mentioned or always_on):
            return

        # Strip the bot mention from the message content
        content = message.clean_content
        if self.bot.user:
            content = content.replace(f"@{self.bot.user.display_name}", "").strip()
        if not content:
            content = "Hello!"

        async with message.channel.typing():
            response = await self._agent.respond(
                guild_id=message.guild.id,
                channel_id=message.channel.id,
                user_id=message.author.id,
                username=message.author.display_name,
                message=content,
            )

        # Discord has a 2000-char limit; split if needed
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

        factory = get_session_factory()
        async with factory() as session:
            await session.execute(
                delete(ConversationMessage).where(
                    ConversationMessage.guild_id == ctx.guild.id,
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


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AIChatCog(bot))
