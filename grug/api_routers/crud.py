from fastapi import Depends
from fastcrud import crud_router

from grug.auth import get_current_active_user
from grug.db import async_session
from grug.models import Event

event_router = crud_router(
    session=async_session,
    model=Event,
    create_schema=Event,
    update_schema=Event,
    path="/events",
    tags=["Events"],
    read_deps=[Depends(get_current_active_user)],
    update_deps=[Depends(get_current_active_user)],
    create_deps=[Depends(get_current_active_user)],
    delete_deps=[Depends(get_current_active_user)],
    read_multi_deps=[Depends(get_current_active_user)],
    read_paginated_deps=[Depends(get_current_active_user)],
)
