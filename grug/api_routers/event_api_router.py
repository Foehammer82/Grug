from fastapi import APIRouter, Depends

from grug.auth import get_current_active_user
from grug.db import async_session
from grug.models import EventAttendance, EventFood
from grug.utils.attendance import send_attendance_reminder
from grug.utils.food import send_food_reminder

router = APIRouter(
    tags=["Event"],
    prefix="/api/v1/event",
    dependencies=[Depends(get_current_active_user)],
)


@router.post("/food/reminder/{event_id}", response_model=EventFood)
async def send_food_reminder_endpoint(event_id: int) -> EventFood:
    """Trigger a food reminder for the specified event."""
    # TODO: enable the api to force select which interfaces to send reminders to

    async with async_session() as session:
        return await send_food_reminder(
            event_id=event_id,
            session=session,
        )


@router.post("/attendance/reminder/{event_id}", response_model=EventAttendance)
async def send_attendance_reminder_endpoint(event_id: int) -> EventAttendance:
    """Trigger an attendance reminder for the specified event."""
    # TODO: enable the api to force select which interfaces to send reminders to

    async with async_session() as session:
        return await send_attendance_reminder(
            event_id=event_id,
            session=session,
        )
