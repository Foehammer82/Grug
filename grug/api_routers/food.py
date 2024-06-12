from fastapi import APIRouter, Depends
from sqlmodel import select

from grug.assistant_interfaces.discord_interface import send_discord_food_reminder
from grug.auth import get_current_active_user
from grug.db import async_session
from grug.models import Event, EventFood

router = APIRouter(
    tags=["Food"],
    prefix="/api/v1/food",
    dependencies=[Depends(get_current_active_user)],
)


@router.post("/reminder/{event_id}", response_model=EventFood)
async def send_food_reminder(event_id: int) -> EventFood:
    """Trigger a food reminder for the specified event."""

    async with async_session() as session:
        event = (await session.execute(select(Event).where(Event.id == event_id))).scalars().one_or_none()

        if event is None:
            raise ValueError(f"Event {event_id} not found.")

        return await send_discord_food_reminder(
            event=event,
            session=session,
        )
