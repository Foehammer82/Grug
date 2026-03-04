"""Admin cog for Grug — configuration and status commands."""

import logging
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import select

from grug.bot.cogs.base import GrugCogBase
from grug.config.settings import get_settings
from grug.db.models import CalendarEvent, ChannelConfig, GuildConfig, ScheduledTask
from grug.db.session import get_session_factory
from grug.scheduler.manager import get_scheduler, remove_job
from grug.utils import ensure_guild

logger = logging.getLogger(__name__)

GRUG_ADMIN_ROLE_NAME = "grug-admin"


async def ensure_grug_admin_role(guild: discord.Guild) -> None:
    """Ensure a 'grug-admin' role exists in the guild and record its ID.

    If the role already exists, reuse it.  If it doesn't, create it.
    Either way, save the role ID to GuildConfig.grug_admin_role_id.
    """
    # Look for an existing role with the right name
    existing_role = discord.utils.get(guild.roles, name=GRUG_ADMIN_ROLE_NAME)

    if existing_role is None:
        try:
            existing_role = await guild.create_role(
                name=GRUG_ADMIN_ROLE_NAME,
                reason="Grug admin role — grants web UI admin access for this server.",
            )
            logger.info(
                "Created '%s' role (%d) in guild %d (%s).",
                GRUG_ADMIN_ROLE_NAME,
                existing_role.id,
                guild.id,
                guild.name,
            )
        except discord.Forbidden:
            logger.warning(
                "Missing MANAGE_ROLES permission in guild %d (%s); "
                "cannot create '%s' role.",
                guild.id,
                guild.name,
                GRUG_ADMIN_ROLE_NAME,
            )
            return
        except Exception:
            logger.exception(
                "Failed to create '%s' role in guild %d (%s).",
                GRUG_ADMIN_ROLE_NAME,
                guild.id,
                guild.name,
            )
            return

    # Persist the role ID to the database
    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(
            select(GuildConfig).where(GuildConfig.guild_id == guild.id)
        )
        cfg = result.scalar_one_or_none()
        if cfg is not None and cfg.grug_admin_role_id != existing_role.id:
            cfg.grug_admin_role_id = existing_role.id
            await session.commit()


async def _ensure_announce_channel_enabled(guild: discord.Guild) -> None:
    """Ensure the guild's announce (default) channel has an enabled ChannelConfig.

    If ``announce_channel_id`` is not yet set on the GuildConfig, falls back to
    the guild's Discord system channel.  The row is created with ``enabled=True``
    if it doesn't exist, or updated if it exists but is disabled.
    """
    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(
            select(GuildConfig).where(GuildConfig.guild_id == guild.id)
        )
        guild_cfg = result.scalar_one_or_none()
        if guild_cfg is None:
            return

        # Determine the channel to enable: stored announce_channel_id first,
        # then fall back to the Discord system channel.
        channel_id = guild_cfg.announce_channel_id
        if channel_id is None and guild.system_channel is not None:
            channel_id = guild.system_channel.id
            guild_cfg.announce_channel_id = channel_id
            guild_cfg.updated_at = datetime.now(timezone.utc)

        if channel_id is None:
            return  # No default channel to enable

        ch_result = await session.execute(
            select(ChannelConfig).where(ChannelConfig.channel_id == channel_id)
        )
        ch_cfg = ch_result.scalar_one_or_none()
        if ch_cfg is None:
            ch_cfg = ChannelConfig(
                guild_id=guild.id,
                channel_id=channel_id,
                enabled=True,
            )
            session.add(ch_cfg)
            logger.info(
                "Auto-enabled announce channel %d for guild %d (%s).",
                channel_id,
                guild.id,
                guild.name,
            )
        elif not ch_cfg.enabled:
            ch_cfg.enabled = True
            ch_cfg.updated_at = datetime.now(timezone.utc)
            logger.info(
                "Re-enabled announce channel %d for guild %d (%s).",
                channel_id,
                guild.id,
                guild.name,
            )

        await session.commit()


class AdminCog(GrugCogBase, name="Admin"):
    """Administrative commands for configuring Grug."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._ready_synced = False

    async def cog_load(self) -> None:
        """Register persistent RSVP buttons so they survive restarts."""
        from grug.bot.views.event_rsvp import RSVPButton

        self.bot.add_dynamic_items(RSVPButton)

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        """On (re)connect, ensure the announce channel is enabled for every guild."""
        if self._ready_synced:
            return
        self._ready_synced = True
        for guild in self.bot.guilds:
            try:
                await _ensure_announce_channel_enabled(guild)
            except Exception:
                logger.exception(
                    "Failed to sync announce channel for guild %d (%s)",
                    guild.id,
                    guild.name,
                )

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild) -> None:
        """Create a GuildConfig row and grug-admin role when Grug joins a new server."""
        try:
            await ensure_guild(guild.id)
            logger.info(
                "Created guild config for new guild %d (%s).", guild.id, guild.name
            )
        except Exception:
            logger.exception("Failed to create guild config for guild %d", guild.id)

        # Ensure the guild's default (system) channel is enabled for Grug.
        try:
            await _ensure_announce_channel_enabled(guild)
        except Exception:
            logger.exception(
                "Failed to enable announce channel for guild %d (%s)",
                guild.id,
                guild.name,
            )

        # Create the grug-admin role (non-fatal if it fails)
        await ensure_grug_admin_role(guild)

    @app_commands.command(name="grug_status", description="Show Grug's current status.")
    async def status(self, interaction: discord.Interaction) -> None:
        settings = get_settings()
        scheduler = get_scheduler()
        job_count = len(scheduler.get_jobs()) if scheduler.running else 0

        embed = discord.Embed(
            title="🪨 Grug Status",
            color=discord.Color.blurple(),
            timestamp=datetime.now(timezone.utc),
        )
        embed.add_field(name="Model", value=settings.anthropic_model, inline=True)
        embed.add_field(
            name="Big Brain Model",
            value=settings.anthropic_big_brain_model,
            inline=True,
        )
        embed.add_field(
            name="Scheduler",
            value="Running ✅" if scheduler.running else "Stopped ❌",
            inline=True,
        )
        embed.add_field(name="Scheduled Jobs", value=str(job_count), inline=True)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name="list_tasks", description="List all scheduled tasks for this guild."
    )
    async def list_tasks(self, interaction: discord.Interaction) -> None:
        if interaction.guild_id is None:
            await interaction.response.send_message(
                "This command only works in a server.", ephemeral=True
            )
            return

        factory = get_session_factory()
        async with factory() as session:
            result = await session.execute(
                select(ScheduledTask).where(
                    ScheduledTask.guild_id == interaction.guild_id,
                    ScheduledTask.enabled.is_(True),
                )
            )
            tasks = result.scalars().all()

        if not tasks:
            await interaction.response.send_message("No scheduled tasks set up yet.")
            return

        embed = discord.Embed(title="�️ Scheduled Tasks", color=discord.Color.orange())
        for task in tasks:
            label = task.name or task.prompt[:60]
            if task.type == "once":
                trigger = f"Once — {task.fire_at.isoformat() if task.fire_at else '?'}"
                last = "pending"
            else:
                trigger = f"Cron: `{task.cron_expression}`"
                last = task.last_run.isoformat() if task.last_run else "never"
            embed.add_field(
                name=f"#{task.id} — {label}",
                value=f"Type: {task.type} | {trigger}\nLast run: {last}",
                inline=False,
            )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name="cancel_task", description="Cancel a scheduled task by ID."
    )
    @app_commands.describe(task_id="The task ID (from /list_tasks).")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def cancel_task(self, interaction: discord.Interaction, task_id: int) -> None:
        if interaction.guild_id is None:
            await interaction.response.send_message(
                "This command only works in a server.", ephemeral=True
            )
            return

        factory = get_session_factory()
        async with factory() as session:
            result = await session.execute(
                select(ScheduledTask).where(
                    ScheduledTask.id == task_id,
                    ScheduledTask.guild_id == interaction.guild_id,
                )
            )
            task = result.scalar_one_or_none()
            if task is None:
                await interaction.response.send_message(
                    f"Grug not find task #{task_id}."
                )
                return
            task.enabled = False
            remove_job(f"task_{task_id}")
            await session.commit()
        await interaction.response.send_message(f"✅ Task #{task_id} cancelled.")

    @app_commands.command(
        name="upcoming", description="Show upcoming calendar events for this guild."
    )
    async def upcoming_events(self, interaction: discord.Interaction) -> None:
        if interaction.guild_id is None:
            await interaction.response.send_message(
                "This command only works in a server.", ephemeral=True
            )
            return

        factory = get_session_factory()
        now = datetime.now(timezone.utc)
        async with factory() as session:
            result = await session.execute(
                select(CalendarEvent)
                .where(
                    CalendarEvent.guild_id == interaction.guild_id,
                    CalendarEvent.start_time >= now,
                )
                .order_by(CalendarEvent.start_time)
                .limit(10)
            )
            events = result.scalars().all()

        if not events:
            await interaction.response.send_message(
                "No upcoming events! Ask Grug to schedule something. 📅"
            )
            return

        embed = discord.Embed(title="📅 Upcoming Events", color=discord.Color.blue())
        for ev in events:
            val = ev.start_time.strftime("%Y-%m-%d %H:%M UTC")
            if ev.end_time:
                val += f" → {ev.end_time.strftime('%H:%M UTC')}"
            if ev.description:
                val += f"\n{ev.description}"
            embed.add_field(name=ev.title, value=val, inline=False)
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AdminCog(bot))
