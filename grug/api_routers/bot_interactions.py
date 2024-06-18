from fastapi import APIRouter, Depends

from grug.auth import get_current_active_user

router = APIRouter(
    tags=["AI Interactions"],
    prefix="/api/v1/ai",
    dependencies=[Depends(get_current_active_user)],
)


@router.post("/message")
async def send_message_to_bot(text: str):
    # TODO: Implement this to be able to interact with Grug through API calls
    return {"message": "Message sent to bot."}
