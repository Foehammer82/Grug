from fastapi import APIRouter, Depends

from grug.assistant_interfaces.discord_interface.bot import get_bot_invite_url
from grug.auth import get_current_active_user

router = APIRouter(
    tags=["Discord"],
    prefix="/api/v1/discord",
    dependencies=[Depends(get_current_active_user)],
)


@router.get("/invite_link")
async def get_invite_link():
    """Get the invite link for the Discord bot."""

    return {"invite_link": get_bot_invite_url()}
