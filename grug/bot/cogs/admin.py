"""Admin cog for Grug — configuration and status commands."""

import logging
from datetime import datetime, timezone

import discord
from discord.ext import commands
from sqlalchemy import select

from grug.config.settings import get_settings
from grug.db.models import CalendarEvent, GuildConfig, Reminder, ScheduledTask
from grug.db.session import get_session_factory, init_db
from grug.scheduler.manager import get_scheduler, remove_job

logger = logging.getLogger(__name__)


async def _ensure_guild(guild_id: int) -> GuildConfig:
    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(
            select(GuildConfig).where(GuildConfig.guild_id == guild_id)
        )
        cfg = result.scalar_one_or_none()
        if cfg is None:
            cfg = GuildConfig(guild_id=guild_id)
            session.add(cfg)
            await session.commit()
            await session.refresh(cfg)
    return cfg


class AdminCog(commands.Cog, name="Admin"):
    """Administrative commands for configuring Grug."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.command(name="grug_status")
    async def status(self, ctx: commands.Context) -> None:
        """Show Grug's current status."""
        settings = get_settings()
        scheduler = get_scheduler()
        job_count = len(scheduler.get_jobs()) if scheduler.running else 0

        embed = discord.Embed(
            title="🪨 Grug Status",
            color=discord.Color.blurple(),
            timestamp=datetime.now(timezone.utc),
        )
        embed.add_field(name="Model", value=settings.openai_model, inline=True)
        embed.add_field(
            name="Scheduler",
            value="Running ✅" if scheduler.running else "Stopped ❌",
            inline=True,
        )
        embed.add_field(name="Scheduled Jobs", value=str(job_count), inline=True)
        await ctx.send(embed=embed)

    @commands.command(name="set_timezone")
    @commands.has_permissions(manage_guild=True)
    async def set_timezone(self, ctx: commands.Context, timezone: str) -> None:
        """Set the guild timezone (e.g. America/New_York).

        Usage: !set_timezone America/New_York
        """
        import zoneinfo
        try:
            zoneinfo.ZoneInfo(timezone)
        except Exception:
            await ctx.send(
                f"Grug not know timezone '{timezone}'. Try something like 'America/New_York'."
            )
            return

        factory = get_session_factory()
        async with factory() as session:
            result = await session.execute(
                select(GuildConfig).where(GuildConfig.guild_id == ctx.guild.id)
            )
            cfg = result.scalar_one_or_none()
            if cfg is None:
                cfg = GuildConfig(guild_id=ctx.guild.id, timezone=timezone)
                session.add(cfg)
            else:
                cfg.timezone = timezone
            await session.commit()
        await ctx.send(f"🕐 Timezone set to **{timezone}**!")

    @commands.command(name="list_tasks")
    async def list_tasks(self, ctx: commands.Context) -> None:
        """List all scheduled tasks for this guild."""
        factory = get_session_factory()
        async with factory() as session:
            result = await session.execute(
                select(ScheduledTask).where(
                    ScheduledTask.guild_id == ctx.guild.id,
                    ScheduledTask.enabled.is_(True),
                )
            )
            tasks = result.scalars().all()

        if not tasks:
            await ctx.send("No scheduled tasks set up yet.")
            return

        embed = discord.Embed(title="🔁 Scheduled Tasks", color=discord.Color.orange())
        for task in tasks:
            last = task.last_run.isoformat() if task.last_run else "never"
            embed.add_field(
                name=f"#{task.id} — {task.name}",
                value=f"Cron: `{task.cron_expression}`\nLast run: {last}",
                inline=False,
            )
        await ctx.send(embed=embed)

    @commands.command(name="cancel_task")
    @commands.has_permissions(manage_guild=True)
    async def cancel_task(self, ctx: commands.Context, task_id: int) -> None:
        """Cancel a scheduled task by ID.

        Usage: !cancel_task <task_id>
        """
        factory = get_session_factory()
        async with factory() as session:
            result = await session.execute(
                select(ScheduledTask).where(
                    ScheduledTask.id == task_id,
                    ScheduledTask.guild_id == ctx.guild.id,
                )
            )
            task = result.scalar_one_or_none()
            if task is None:
                await ctx.send(f"Grug not find task #{task_id}.")
                return
            task.enabled = False
            remove_job(f"task_{task_id}")
            await session.commit()
        await ctx.send(f"✅ Task #{task_id} cancelled.")

    @commands.command(name="upcoming")
    async def upcoming_events(self, ctx: commands.Context) -> None:
        """Show upcoming calendar events for this guild."""
        factory = get_session_factory()
        now = datetime.now(timezone.utc)
        async with factory() as session:
            result = await session.execute(
                select(CalendarEvent)
                .where(
                    CalendarEvent.guild_id == ctx.guild.id,
                    CalendarEvent.start_time >= now,
                )
                .order_by(CalendarEvent.start_time)
                .limit(10)
            )
            events = result.scalars().all()

        if not events:
            await ctx.send("No upcoming events! Ask Grug to schedule something. 📅")
            return

        embed = discord.Embed(title="📅 Upcoming Events", color=discord.Color.blue())
        for ev in events:
            val = ev.start_time.strftime("%Y-%m-%d %H:%M UTC")
            if ev.end_time:
                val += f" → {ev.end_time.strftime('%H:%M UTC')}"
            if ev.description:
                val += f"\n{ev.description}"
            embed.add_field(name=ev.title, value=val, inline=False)
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AdminCog(bot))
