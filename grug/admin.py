from fastapi import FastAPI
from sqladmin import Admin, ModelView
from sqladmin.models import ModelViewMeta

from grug.assistant_interfaces.discord_interface.bot import get_bot_invite_url
from grug.auth import AdminAuth
from grug.db import async_engine
from grug.models import (
    DiscordAccount,
    DiscordServer,
    Event,
    EventAttendance,
    EventFood,
    Group,
    User,
)
from grug.settings import settings

# TODO: use the grug favicon for the admin if possible.


class UserAdmin(ModelView, model=User):
    """Admin interface for the User model."""

    name = "User"
    name_plural = "Users"
    category = "Users & Groups"

    column_list = [User.id, User.username]

    # Form Options
    form_excluded_columns = [
        User.brought_food_for,
        User.event_attendance,
        User.secrets,
        User.assistant_thread_id,
        User.auto_created,
    ]
    form_ajax_refs = {
        "groups": {
            "fields": ("id", "name"),
            "order_by": "name",
        },
        "discord_accounts": {
            "fields": ("discord_member_id", "discord_member_name"),
            "order_by": "discord_member_name",
        },
    }


class GroupAdmin(ModelView, model=Group):
    """Admin interface for the Group model."""

    name = "Group"
    name_plural = "Groups"
    category = "Users & Groups"

    column_list = [Group.id, Group.name]
    column_searchable_list = [Group.name]
    column_sortable_list = [Group.name]

    # Form Options
    form_excluded_columns = [Group.events]
    form_ajax_refs = {
        "users": {
            "fields": ("username",),
            "order_by": "username",
        },
        "discord_servers": {
            "fields": ("discord_guild_id", "discord_guild_name"),
            "order_by": "discord_guild_id",
        },
    }


class DiscordAccountAdmin(ModelView, model=DiscordAccount):
    """Admin interface for the DiscordAccount model."""

    name = "Discord Account"
    name_plural = "Discord Accounts"
    category = "Discord"

    # Column Options
    column_list = [
        DiscordAccount.id,
        DiscordAccount.discord_member_name,
        "user.username",
        "user.friendly_name",
        DiscordAccount.discord_member_id,
    ]
    column_searchable_list = [
        "user.username",
        DiscordAccount.discord_member_id,
    ]

    # Form Options
    # form_excluded_columns = [Group.events]
    form_ajax_refs = {
        "user": {
            "fields": ("username",),
            "order_by": "username",
        }
    }


class DiscordServerAdmin(ModelView, model=DiscordServer):
    """Admin interface for the DiscordAccount model."""

    name = "Discord Server"
    name_plural = "Discord Servers"
    category = "Discord"

    # Column Options
    column_list = [
        DiscordServer.id,
        DiscordServer.discord_guild_name,
        "group.name",
        DiscordServer.discord_guild_id,
    ]
    column_searchable_list = [
        "group.name",
        DiscordServer.discord_guild_id,
    ]

    # Form Options
    form_excluded_columns = [DiscordServer.discord_text_channels]
    form_ajax_refs = {
        "group": {
            "fields": ("name",),
            "order_by": "name",
        }
    }


class EventAdmin(ModelView, model=Event):
    # Metadata
    name = "Event"
    name_plural = "Events"
    category = "Events"

    # List Page
    column_list = [Event.id, Event.name, Event.group]
    column_searchable_list = [Event.name, Event.group]
    column_sortable_list = [Event.name, Event.group]

    # Form Options
    form_excluded_columns = [Event.food, Event.attendance]


class EventFoodAdmin(ModelView, model=EventFood):
    # Metadata
    name = "Event Food History"
    name_plural = "Event Food History"
    category = "Events"

    # List Page
    column_list = [EventFood.id, EventFood.event_date]
    column_sortable_list = [EventFood.event_date]


class EventAttendanceAdmin(ModelView, model=EventAttendance):
    # Metadata
    name = "Event Attendance History"
    name_plural = "Event Attendance History"
    category = "Events"

    # List Page
    column_list = [EventAttendance.id, EventAttendance.event_date]
    column_sortable_list = [EventAttendance.event_date]


def init_admin(app: FastAPI):
    """
    Initialize the admin interface.

    Args:
        app: The FastAPI app.

    Returns: None

    """

    admin = Admin(
        app,
        engine=async_engine,
        authentication_backend=AdminAuth(secret_key=settings.security_key.get_secret_value()),
        title=f"{settings.openai_assistant_name} Admin",
        templates_dir=settings.root_dir / "grug" / "templates",
    )

    admin.templates.env.globals["get_discord_bot_invite_url"] = get_bot_invite_url

    # Add all model views to the admin interface
    for model_view in list(globals().values()):
        if isinstance(model_view, ModelViewMeta) and model_view.name != "":
            admin.add_view(model_view)
