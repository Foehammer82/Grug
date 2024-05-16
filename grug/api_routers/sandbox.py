from typing import Annotated

from fastapi import APIRouter, Depends
from loguru import logger

from grug.assistant_functions.food import send_discord_food_reminder
from grug.auth import get_current_active_user
from grug.models import User

router = APIRouter(tags=["Sandbox API"], prefix="/api/v1")


@router.get("/")
def index() -> str:
    """Index route."""
    logger.info("loguru info log")
    logger.info({"test": 1})

    return "Hello, world!"


@router.get("/secure", dependencies=[Depends(get_current_active_user)])
def secure_endpoint() -> str:
    """Secure endpoint."""
    return "I am secure!"


@router.get("/users/me/", response_model=User)
async def read_users_me(
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """Return the current user."""
    return current_user


@router.get("/send-food-reminder")
async def send_food_reminder():
    await send_discord_food_reminder()
