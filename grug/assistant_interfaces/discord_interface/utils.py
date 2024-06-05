import asyncio

from grug.assistant_interfaces.discord_interface.bot import discord_bot


async def wait_for_discord_to_start(timeout: int = 10) -> None:
    """Wait for the Discord bot to start."""
    for _ in range(timeout):
        if discord_bot.is_ready():
            return
        await asyncio.sleep(1)
    raise TimeoutError(
        f"Timeout reached in {timeout} seconds. Discord bot did not achieve ready state in the allowed time."
    )
