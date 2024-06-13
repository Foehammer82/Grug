import inspect

from fastapi import FastAPI
from sqladmin import Admin, ModelView, action
from starlette.requests import Request
from starlette.responses import RedirectResponse

from grug.assistant_interfaces.discord_interface.bot import get_bot_invite_url
from grug.auth import AdminAuth
from grug.db import async_engine
from grug.models import DiscordAccount, DiscordServer, Event, EventAttendance, EventFood, Group, User
from grug.settings import settings
from grug.utils.attendance import send_attendance_reminder
from grug.utils.food import send_food_reminder

# TODO: use the grug favicon for the admin if possible.


class UserAdmin(ModelView, model=User):
    """Admin interface for the User model."""

    name = "User"
    name_plural = "Users"
    category = "Users & Groups"

    column_list = [User.id, User.username]

    # Form Options
    form_excluded_columns = [
        "brought_food_for",
        "event_attendance",
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

    # Detail Page Options
    column_details_exclude_list = [
        "id",
        "secrets",
        "assistant_thread_id",
        "auto_created",
        "event_attendance",
        "brought_food_for",
    ]


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

    # Detail Page Options
    column_details_exclude_list = ["id", "auto_created", "events"]


class DiscordAccountAdmin(ModelView, model=DiscordAccount):
    """Admin interface for the DiscordAccount model."""

    # TODO: create an event listener that triggers before a change to the discord_member_id field that checks
    #       checks if that user id exists in discord and grabbing the username if it does.  in short, when editing the
    #       discord account, only the discord id should be edited, the rest should be pulled.

    name = "Discord Account"
    name_plural = "Discord Accounts"
    category = "Discord"
    can_create = False
    can_delete = False

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
    form_excluded_columns = ["discord_member_name"]
    form_ajax_refs = {
        "user": {
            "fields": ("username",),
            "order_by": "username",
        }
    }

    # Detail Page Options
    column_details_exclude_list = ["id", "user_id"]


class DiscordServerAdmin(ModelView, model=DiscordServer):
    """Admin interface for the DiscordAccount model."""

    # TODO: evaluate how to handle on_delete (if a server is deleted, should the bot be removed from that server?)

    name = "Discord Server"
    name_plural = "Discord Servers"
    category = "Discord"
    can_create = False

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
    form_excluded_columns = [DiscordServer.discord_text_channels, DiscordServer.discord_guild_name]
    form_ajax_refs = {
        "group": {
            "fields": ("name",),
            "order_by": "name",
        }
    }

    # Detail Page Options
    column_details_exclude_list = ["id", "discord_text_channels", "group_id"]

    # noinspection PyUnusedLocal
    @action(
        name="invite_to_discord_server",
        label="Invite to Server",
        add_in_detail=False,
        add_in_list=True,
    )
    async def invite_to_discord_server(self, request: Request):
        return RedirectResponse(get_bot_invite_url())


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
    form_ajax_refs = {
        "group": {
            "fields": ("name",),
            "order_by": "name",
        }
    }

    # Detail Page Options
    column_details_exclude_list = ["id", "group_id", "food", "attendance"]


class EventFoodAdmin(ModelView, model=EventFood):
    # Metadata
    name = "Event Food History"
    name_plural = "Event Food History"
    category = "Events"

    # List Page
    column_list = [EventFood.id, EventFood.event_date, "user_assigned_food.friendly_name", "food_name"]
    column_sortable_list = [EventFood.event_date]
    can_create = False
    can_delete = False

    # Form Options
    form_excluded_columns = ["discord_messages"]
    form_ajax_refs = {
        "event": {
            "fields": ("name",),
            "order_by": "name",
        },
        "user_assigned_food": {
            "fields": ("username",),
            "order_by": "username",
        },
    }

    # Detail Page Options
    column_details_exclude_list = ["id", "user_assigned_food_id", "event_id", "discord_messages"]

    @action(
        name="send_food_reminder",
        label="Send Reminder",
        add_in_detail=True,
        add_in_list=True,
    )
    async def send_food_reminder(self, request: Request):
        pks = request.query_params.get("pks", "").split(",")
        if pks[0] != "":
            for pk in pks:
                model: EventFood = await self.get_object_for_details(pk)
                await send_food_reminder(event_id=model.event_id)

        referer = request.headers.get("Referer")
        if referer:
            return RedirectResponse(referer)
        else:
            return RedirectResponse(request.url_for("admin:list", identity=self.identity))


class EventAttendanceAdmin(ModelView, model=EventAttendance):
    # Metadata
    name = "Event Attendance History"
    name_plural = "Event Attendance History"
    category = "Events"

    # List Page
    column_list = [EventAttendance.id, EventAttendance.event_date]
    column_sortable_list = [EventAttendance.event_date]
    can_create = False
    can_delete = False

    # Form Options
    form_excluded_columns = ["discord_messages"]
    form_ajax_refs = {
        "event": {
            "fields": ("name",),
            "order_by": "name",
        },
        "users_attended": {
            "fields": ("username",),
            "order_by": "username",
        },
    }

    # Detail Page Options
    column_details_exclude_list = ["id", "user_assigned_food_id", "event_id", "discord_messages"]

    @action(
        name="send_attendance_reminder",
        label="Send Reminder",
        add_in_detail=True,
        add_in_list=True,
    )
    async def send_attendance_reminder(self, request: Request):
        pks = request.query_params.get("pks", "").split(",")
        if pks[0] != "":
            for pk in pks:
                model: EventAttendance = await self.get_object_for_details(pk)
                await send_attendance_reminder(event_id=model.event_id)

        referer = request.headers.get("Referer")
        if referer:
            return RedirectResponse(referer)
        else:
            return RedirectResponse(request.url_for("admin:list", identity=self.identity))


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
        if inspect.isclass(model_view) and issubclass(model_view, ModelView) and model_view.name != "":
            admin.add_view(model_view)
