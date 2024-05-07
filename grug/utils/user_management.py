from collections.abc import Iterable

import discord
from sqlmodel import select

from grug.db import async_session
from grug.models import Player


async def add_discord_members_to_db_as_players(discord_members: Iterable[discord.Member]):
    """
    Add Discord members to the database as Players if they do not already exist.

    Args:
        discord_members (Iterable[discord.Member]): An iterable of discord.Member objects.
    """

    players: list[Player] = []

    async with async_session() as session:
        for member in discord_members:
            if not member.bot:
                result = await session.execute(
                    select(Player)
                    .where(Player.discord_member_id == str(member.id))
                    .where(Player.discord_guild_id == str(member.guild.id))
                )
                player: Player | None = result.scalars().one_or_none()

                if player is None:
                    player = Player(
                        discord_member_id=str(member.id),
                        discord_guild_id=str(member.guild.id),
                        discord_username=member.name,
                    )

                    session.add(player)
                    await session.commit()
                    await session.refresh(player)

                players.append(player)

    return players
