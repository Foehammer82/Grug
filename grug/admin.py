from fastapi import FastAPI
from sqladmin import Admin, ModelView

from grug.auth import AdminAuth
from grug.db import async_engine
from grug.models import Event, Group, User
from grug.settings import settings


class UserAdmin(ModelView, model=User):
    """Admin interface for the User model."""

    column_list = [User.id, User.username]


class GroupAdmin(ModelView, model=Group):
    """Admin interface for the Group model."""

    column_list = [Group.id, Group.name]
    column_searchable_list = [Group.name]
    column_sortable_list = [Group.name]

    # Form Options
    form_excluded_columns = [Group.events]


class EventAdmin(ModelView, model=Event):
    # Metadata

    # List Page
    column_list = [Event.id, Event.name, Event.group]
    column_searchable_list = [Event.name, Event.group]
    column_sortable_list = [Event.name, Event.group]

    # Form Options
    form_excluded_columns = [Event.food, Event.attendance]


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
        title=f"{settings.bot_name} Admin",
    )

    admin.add_view(UserAdmin)
    admin.add_view(GroupAdmin)
    admin.add_view(EventAdmin)
