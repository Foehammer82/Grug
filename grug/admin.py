import inspect
import pickle

import wtforms
from fastapi import APIRouter, FastAPI
from sqladmin import Admin, ModelView, action
from starlette.requests import Request
from starlette.responses import RedirectResponse

from grug.assistant_interfaces.discord_interface.bot import get_bot_invite_url
from grug.auth import AdminAuth
from grug.db import async_engine, async_session
from grug.models import DalleImageRequest, DiscordServer, Event, EventOccurrence, Group, User
from grug.models_crud import get_or_create_next_event_occurrence
from grug.scheduler import scheduler
from grug.scheduler_models import ApSchedulerJob, ApSchedulerJobResult, ApschedulerSchedule, ApSchedulerTask
from grug.settings import settings
from grug.utils.attendance import send_attendance_reminder
from grug.utils.food import send_food_reminder

# TODO: use the grug favicon for the admin if possible.
# TODO: add a link to the API swagger docs in the admin interface


class UserAdmin(ModelView, model=User):
    """Admin interface for the User model."""

    name = "User"
    name_plural = "Users"
    icon = "fa-solid fa-user"
    category = "Users & Groups"

    # List Page Options
    column_list = [
        User.id,
        User.username,
        User.first_name,
        User.last_name,
        User.email,
        User.groups,
        User.disabled,
        User.is_admin,
        "is_owner",
    ]
    column_sortable_list = [User.username, User.first_name, User.last_name, User.email, User.disabled]
    column_searchable_list = [User.id, User.username, User.first_name, User.last_name, User.email]

    # Form Options
    form_excluded_columns = [
        "brought_food_for",
        "event_attendance",
        User.secrets,
        User.assistant_thread_id,
        User.auto_created,
    ]
    form_overrides = dict(
        email=wtforms.EmailField,
        phone=wtforms.TelField,
    )
    form_ajax_refs = {
        "groups": {
            "fields": ("id", "name"),
            "order_by": "name",
        },
    }

    # Detail Page Options
    column_details_list = [
        User.id,
        User.username,
        User.first_name,
        User.last_name,
        User.email,
        User.phone,
        User.discord_username,
        User.discord_member_id,
        User.disable_sms,
        User.disable_email,
        User.groups,
        User.disabled,
        User.is_admin,
        "is_owner",
    ]


class GroupAdmin(ModelView, model=Group):
    """Admin interface for the Group model."""

    name = "Group"
    name_plural = "Groups"
    icon = "fa-solid fa-users"
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


class EventAdmin(ModelView, model=Event):
    # TODO: since we have a tie into LLM's it would be super slick to allow the user to type in a prompt for the cron
    #       and have an LLM generate a cron expression.

    # Metadata
    name = "Event"
    name_plural = "Events"
    icon = "fa-solid fa-calendar"
    category = "Events"

    # List Page
    column_list = [Event.id, Event.name, Event.group]
    column_searchable_list = [Event.name, Event.group]
    column_sortable_list = [Event.name, Event.group]

    # Form Options
    form_excluded_columns = [Event.event_occurrences]
    form_overrides = dict(
        description=wtforms.TextAreaField,
    )
    # NOTE: There aren't THAT many groups, and I was finding it annoying to have to search for the group by name
    #       rather than select from a list.  If you (whoever is maintaining this) disagrees, feel free to uncomment
    #       this:
    # form_ajax_refs = {
    #     "group": {
    #         "fields": ("name",),
    #         "order_by": "name",
    #     }
    # }

    # Detail Page Options
    column_details_exclude_list = ["id", "group_id", "food", "attendance", "event_occurrences"]

    @action(
        name="send_food_reminder",
        label="Send Food Reminder",
        add_in_detail=True,
        add_in_list=True,
    )
    async def send_food_reminder(self, request: Request):
        pks = request.query_params.get("pks", "").split(",")
        if pks[0] != "":
            async with async_session() as session:
                for pk in pks:
                    next_event_occurrence = await get_or_create_next_event_occurrence(event_id=int(pk), session=session)
                    if next_event_occurrence.id is None:
                        raise ValueError(f"Event {pk} does not have a next event occurrence.")
                    await send_food_reminder(event_occurrence_id=next_event_occurrence.id, session=session)

        referer = request.headers.get("Referer")
        if referer:
            return RedirectResponse(referer)
        else:
            return RedirectResponse(request.url_for("admin:list", identity=self.identity))

    @action(
        name="send_attendance_reminder",
        label="Send Attendance Reminder",
        add_in_detail=True,
        add_in_list=True,
    )
    async def send_attendance_reminder(self, request: Request):
        pks = request.query_params.get("pks", "").split(",")
        if pks[0] != "":
            async with async_session() as session:
                for pk in pks:
                    next_event_occurrence = await get_or_create_next_event_occurrence(event_id=int(pk), session=session)
                    if next_event_occurrence.id is None:
                        raise ValueError(f"Event {pk} does not have a next event occurrence.")
                    await send_attendance_reminder(event_occurrence_id=next_event_occurrence.id, session=session)

        referer = request.headers.get("Referer")
        if referer:
            return RedirectResponse(referer)
        else:
            return RedirectResponse(request.url_for("admin:list", identity=self.identity))


class EventOccurrenceAdmin(ModelView, model=EventOccurrence):
    # Metadata
    name = "Event Occurrence"
    name_plural = "Event Occurrences"
    icon = "fa-solid fa-calendar-day"
    category = "Events"

    # List Page
    column_list = [
        EventOccurrence.id,
        EventOccurrence.event_date,
        EventOccurrence.event,
        EventOccurrence.user_assigned_food,
        EventOccurrence.users_attended,
    ]
    column_sortable_list = [EventOccurrence.event_date]
    column_searchable_list = [EventOccurrence.event_date, EventOccurrence.event]

    # Form Options
    form_columns = [
        "event_date",
        "event_time",
        "food_reminder",
        "user_assigned_food",
        "food_name",
        "food_description",
        "attendance_reminder",
        "users_attended",
    ]
    form_ajax_refs = {
        "user_assigned_food": {
            "fields": ("username",),
            "order_by": "username",
        },
        "users_attended": {
            "fields": ("username",),
            "order_by": "username",
        },
    }

    # Detail Page Options
    column_details_list = [
        "event",
        "event.timezone",
        "event_date",
        "event_time",
        "food_reminder",
        "user_assigned_food",
        "food_name",
        "food_description",
        "attendance_reminder",
        "users_attended",
    ]
    column_formatters_detail = {
        "food_reminder": lambda m, a: m.localized_food_reminder,
        "attendance_reminder": lambda m, a: m.localized_attendance_reminder,
    }

    @action(
        name="send_food_reminder",
        label="Send Food Reminder",
        add_in_detail=True,
        add_in_list=True,
    )
    async def send_food_reminder(self, request: Request):
        pks = request.query_params.get("pks", "").split(",")
        if pks[0] != "":
            async with async_session() as session:
                for pk in pks:
                    await send_food_reminder(event_occurrence_id=int(pk), session=session)

        referer = request.headers.get("Referer")
        if referer:
            return RedirectResponse(referer)
        else:
            return RedirectResponse(request.url_for("admin:list", identity=self.identity))

    @action(
        name="send_attendance_reminder",
        label="Send Attendance Reminder",
        add_in_detail=True,
        add_in_list=True,
    )
    async def send_attendance_reminder(self, request: Request):
        pks = request.query_params.get("pks", "").split(",")
        if pks[0] != "":
            async with async_session() as session:
                for pk in pks:
                    await send_attendance_reminder(event_occurrence_id=int(pk), session=session)

        referer = request.headers.get("Referer")
        if referer:
            return RedirectResponse(referer)
        else:
            return RedirectResponse(request.url_for("admin:list", identity=self.identity))


class DiscordServerAdmin(ModelView, model=DiscordServer):
    """Admin interface for the DiscordAccount model."""

    # TODO: evaluate how to handle on_delete (if a server is deleted, should the bot be removed from that server?)

    name = "Discord Server"
    name_plural = "Discord Servers"
    icon = "fa-brands fa-discord"
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


class DalleImageRequestAdmin(ModelView, model=DalleImageRequest):
    name = "DALL-E Image Request"
    name_plural = "DALL-E Image Requests"
    icon = "fa-solid fa-image"
    category = "OpenAI"

    can_create = False
    can_edit = False
    can_delete = False
    can_export = False

    # List Page
    column_list = ["id", "request_time", "model", "size"]
    column_sortable_list = ["request_time", "model", "size"]
    column_searchable_list = ["model", "size"]

    # Detail Page Options
    column_formatters_detail = {
        "image_url": lambda m, a: f'<img src="{m.image_url}" style="max-width: 100%; max-height: 100%;">',
    }


class SchedulerScheduleAdmin(ModelView, model=ApschedulerSchedule):
    name = "Schedule"
    name_plural = "Schedules"
    icon = "fa-solid fa-clock"
    category = "Job Scheduler"

    can_create = False
    can_edit = False
    can_delete = False
    can_export = False

    # List Page
    column_list = ["id", "next_fire_time"]

    # Detail Page Options
    column_formatters_detail = {
        "trigger": lambda m, a: str(pickle.loads(m.trigger)),
        "args": lambda m, a: str(pickle.loads(m.args)),
        "kwargs": lambda m, a: str(pickle.loads(m.kwargs)),
    }

    @action(
        name="pause_schedule",
        label="Pause",
        add_in_detail=True,
        add_in_list=True,
    )
    async def pause_schedule(self, request: Request):
        pks = request.query_params.get("pks", "").split(",")
        if pks[0] != "":
            for pk in pks:
                model: ApschedulerSchedule = await self.get_object_for_details(pk)

                # noinspection PyUnresolvedReferences
                await scheduler.pause_schedule(model.id)

        referer = request.headers.get("Referer")
        if referer:
            return RedirectResponse(referer)
        else:
            return RedirectResponse(request.url_for("admin:list", identity=self.identity))

    @action(
        name="unpause_schedule",
        label="Unpause",
        add_in_detail=True,
        add_in_list=True,
    )
    async def unpause_schedule(self, request: Request):
        pks = request.query_params.get("pks", "").split(",")
        if pks[0] != "":
            for pk in pks:
                model: ApschedulerSchedule = await self.get_object_for_details(pk)

                # noinspection PyUnresolvedReferences
                await scheduler.unpause_schedule(model.id)

        referer = request.headers.get("Referer")
        if referer:
            return RedirectResponse(referer)
        else:
            return RedirectResponse(request.url_for("admin:list", identity=self.identity))


class SchedulerTaskAdmin(ModelView, model=ApSchedulerTask):
    name = "Task"
    name_plural = "Tasks"
    icon = "fa-solid fa-list-check"
    category = "Job Scheduler"

    can_create = False
    can_edit = False
    can_delete = False
    can_export = False

    # List Page
    column_list = ["id", "func"]


class SchedulerJobAdmin(ModelView, model=ApSchedulerJob):
    name = "Job"
    name_plural = "Jobs"
    icon = "fa-solid fa-hammer"
    category = "Job Scheduler"

    can_create = False
    can_edit = False
    can_delete = False
    can_export = False


class SchedulerJobResultAdmin(ModelView, model=ApSchedulerJobResult):
    name = "Job Results"
    name_plural = "Job Results"
    icon = "fa-solid fa-clipboard-check"
    category = "Job Scheduler"

    can_create = False
    can_edit = False
    can_delete = False
    can_export = False


auth_router = APIRouter(
    tags=["Oauth"],
    prefix="/auth",
)


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
        base_url="/",
    )

    admin.templates.env.globals["get_discord_bot_invite_url"] = get_bot_invite_url
    admin.templates.env.globals["oauth_discord_enabled"] = settings.discord.enable_oauth if settings.discord else False

    # Add all model views to the admin interface
    for model_view in list(globals().values()):
        if inspect.isclass(model_view) and issubclass(model_view, ModelView) and model_view.name != "":
            admin.add_view(model_view)
