import asyncio

import discord
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from grug.models import DiscordAccount


async def wait_for_discord_to_start(timeout: int = 10) -> None:
    """Wait for the Discord bot to start."""
    from grug.assistant_interfaces.discord_interface.bot import discord_bot

    for _ in range(timeout):
        if discord_bot.is_ready():
            return
        await asyncio.sleep(1)
    raise TimeoutError(
        f"Timeout reached in {timeout} seconds. Discord bot did not achieve ready state in the allowed time."
    )


async def get_discord_account_given_interaction(
    interaction: discord.Interaction, session: AsyncSession
) -> DiscordAccount:
    """Get the DiscordAccount for the interaction."""
    discord_account: DiscordAccount = (
        (await session.execute(select(DiscordAccount).where(DiscordAccount.discord_member_id == interaction.user.id)))
        .scalars()
        .one_or_none()
    )

    if discord_account is None:
        raise ValueError("No discord_account found for this interaction.")

    return discord_account
