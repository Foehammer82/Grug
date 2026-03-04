"""Persistent Discord view with RSVP buttons for calendar events.

Uses :class:`discord.ui.DynamicItem` so the bot can handle button clicks on
messages it sent before a restart — no need to re-register per-event views on
startup.
"""

import logging
import re

import discord
from discord import Interaction
from sqlalchemy import select

from grug.db.models import CalendarEvent, EventRSVP
from grug.db.session import get_session_factory

logger = logging.getLogger(__name__)


# ── Embed builder ──────────────────────────────────────────────────────────


async def build_event_embed(
    event: CalendarEvent,
    *,
    reminder_label: str | None = None,
) -> discord.Embed:
    """Build a rich embed for a calendar event with RSVP summary.

    Parameters
    ----------
    event:
        The event to display (must have ``rsvps`` relationship loaded).
    reminder_label:
        Optional text like ``"starts in 1 hour"`` shown at the top.
    """
    colour = discord.Color.blue()
    title = f"📅 {event.title}"

    embed = discord.Embed(title=title, color=colour)

    if reminder_label:
        embed.description = f"**{reminder_label}**"

    # Time
    ts = int(event.start_time.timestamp())
    time_str = f"<t:{ts}:F> (<t:{ts}:R>)"
    if event.end_time:
        end_ts = int(event.end_time.timestamp())
        time_str += f" → <t:{end_ts}:t>"
    embed.add_field(name="When", value=time_str, inline=False)

    # Location
    if event.location:
        embed.add_field(name="Where", value=event.location, inline=True)

    # Description
    if event.description:
        embed.add_field(
            name="Details",
            value=event.description[:1024],
            inline=False,
        )

    # RSVP summary
    rsvps = event.rsvps or []
    attending = [r for r in rsvps if r.status == "attending"]
    maybe = [r for r in rsvps if r.status == "maybe"]
    declined = [r for r in rsvps if r.status == "declined"]

    parts: list[str] = []
    if attending:
        names = ", ".join(f"<@{r.discord_user_id}>" for r in attending)
        parts.append(f"✅ **Attending** ({len(attending)}): {names}")
    if maybe:
        names = ", ".join(f"<@{r.discord_user_id}>" for r in maybe)
        parts.append(f"🤔 **Maybe** ({len(maybe)}): {names}")
    if declined:
        names = ", ".join(f"<@{r.discord_user_id}>" for r in declined)
        parts.append(f"❌ **Declined** ({len(declined)}): {names}")

    if parts:
        embed.add_field(name="RSVPs", value="\n".join(parts), inline=False)
    else:
        embed.add_field(
            name="RSVPs",
            value="No responses yet — click a button below!",
            inline=False,
        )

    return embed


# ── RSVP button (DynamicItem) ──────────────────────────────────────────────

_RSVP_RE = re.compile(r"^rsvp:(?P<status>attending|maybe|declined):(?P<event_id>\d+)$")


class RSVPButton(
    discord.ui.DynamicItem[discord.ui.Button],
    template=r"rsvp:(?P<status>attending|maybe|declined):(?P<event_id>[0-9]+)",
):
    """A single RSVP button that encodes event_id and status in its custom_id.

    DynamicItem handles re-hydration on restart — each button click is routed
    here even if the view was sent before a reboot.
    """

    def __init__(self, event_id: int, status: str) -> None:
        self.event_id = event_id
        self.rsvp_status = status

        label_map = {
            "attending": "✅ Attending",
            "maybe": "🤔 Maybe",
            "declined": "❌ Decline",
        }
        style_map = {
            "attending": discord.ButtonStyle.success,
            "maybe": discord.ButtonStyle.secondary,
            "declined": discord.ButtonStyle.danger,
        }

        super().__init__(
            discord.ui.Button(
                label=label_map[status],
                style=style_map[status],
                custom_id=f"rsvp:{status}:{event_id}",
            )
        )

    @classmethod
    async def from_custom_id(
        cls,
        interaction: Interaction,  # noqa: ARG003
        item: discord.ui.Button,
        match: re.Match[str],
    ) -> "RSVPButton":
        event_id = int(match["event_id"])
        status = match["status"]
        inst = cls(event_id, status)
        inst.item = item  # type: ignore[attr-defined]
        return inst

    async def callback(self, interaction: Interaction) -> None:
        factory = get_session_factory()
        async with factory() as session:
            # Check event exists
            result = await session.execute(
                select(CalendarEvent).where(CalendarEvent.id == self.event_id)
            )
            event = result.scalar_one_or_none()
            if event is None:
                await interaction.response.send_message(
                    "This event no longer exists.", ephemeral=True
                )
                return

            # Upsert RSVP
            user_id = interaction.user.id
            result = await session.execute(
                select(EventRSVP).where(
                    EventRSVP.event_id == self.event_id,
                    EventRSVP.discord_user_id == user_id,
                )
            )
            rsvp = result.scalar_one_or_none()

            if rsvp is not None and rsvp.status == self.rsvp_status:
                # Toggle off — remove the RSVP
                await session.delete(rsvp)
                await session.commit()
                verb = "removed"
            elif rsvp is not None:
                rsvp.status = self.rsvp_status
                await session.commit()
                verb = self.rsvp_status
            else:
                rsvp = EventRSVP(
                    event_id=self.event_id,
                    discord_user_id=user_id,
                    status=self.rsvp_status,
                )
                session.add(rsvp)
                await session.commit()
                verb = self.rsvp_status

            # Reload event with rsvps for embed rebuild
            result = await session.execute(
                select(CalendarEvent).where(CalendarEvent.id == self.event_id)
            )
            event = result.scalar_one_or_none()
            if event:
                # Eagerly load rsvps
                await session.refresh(event, ["rsvps"])
                embed = await build_event_embed(event)
                await interaction.response.edit_message(embed=embed)
            else:
                await interaction.response.send_message(f"RSVP {verb}!", ephemeral=True)

        logger.info(
            "User %d RSVP'd %s to event %d",
            interaction.user.id,
            verb,  # type: ignore[possibly-undefined]
            self.event_id,
        )


# ── View factory ───────────────────────────────────────────────────────────


def create_rsvp_view(event_id: int) -> discord.ui.View:
    """Create a persistent view with Attending / Maybe / Decline buttons."""
    view = discord.ui.View(timeout=None)
    view.add_item(RSVPButton(event_id, "attending"))
    view.add_item(RSVPButton(event_id, "maybe"))
    view.add_item(RSVPButton(event_id, "declined"))
    return view
