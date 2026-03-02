"""Admin cog for Grug — configuration and status commands."""

import logging
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import select

from grug.config.settings import get_settings
from grug.db.models import CalendarEvent, ScheduledTask
from grug.db.session import get_session_factory
from grug.scheduler.manager import get_scheduler, remove_job
from grug.utils import ensure_guild

logger = logging.getLogger(__name__)


class AdminCog(commands.Cog, name="Admin"):
    """Administrative commands for configuring Grug."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild) -> None:
        """Create a GuildConfig row when Grug joins a new server."""
        try:
            await ensure_guild(guild.id)
            logger.info(
                "Created guild config for new guild %d (%s).", guild.id, guild.name
            )
        except Exception:
            logger.exception("Failed to create guild config for guild %d", guild.id)

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

    async def cog_app_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "You need the **Manage Server** permission to use that command.",
                ephemeral=True,
            )
        else:
            raise error


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AdminCog(bot))
