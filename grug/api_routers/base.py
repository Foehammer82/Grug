from typing import Annotated

from fastapi import APIRouter, Depends
from loguru import logger

from grug.auth import get_current_active_user
from grug.models import User

router = APIRouter()


@router.get("/")
def index() -> str:
    """Index route."""
    logger.info("loguru info log")
    logger.info({"test": 1})

    return "Hello, world!"


@router.get("/health")
def healthy() -> str:
    """Health check route."""
    return "Healthy"


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
