"""Discord bot interface for the Grug assistant server."""

__all__ = [
    "init_discord_bot",
    "send_discord_food_reminder",
    "send_discord_attendance_reminder",
    "wait_for_discord_to_start",
]

from grug.assistant_interfaces.discord_interface.attendance import send_discord_attendance_reminder
from grug.assistant_interfaces.discord_interface.bot import init_discord_bot
from grug.assistant_interfaces.discord_interface.food import send_discord_food_reminder
from grug.assistant_interfaces.discord_interface.utils import wait_for_discord_to_start
