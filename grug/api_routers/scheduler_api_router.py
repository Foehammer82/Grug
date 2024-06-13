from fastapi import APIRouter, Depends

from grug.auth import get_current_active_user
from grug.scheduler import ScheduleModel, scheduler

router = APIRouter(
    tags=["Scheduler"],
    prefix="/api/v1/scheduler",
    dependencies=[Depends(get_current_active_user)],
)


@router.get("/schedules")
async def get_schedules() -> list[ScheduleModel]:
    schedules = await ScheduleModel.get_all()

    return schedules


@router.get("/schedules/{schedule_id}")
async def get_schedule(schedule_id: str) -> ScheduleModel:
    schedule = await ScheduleModel.get(schedule_id)

    return schedule


@router.post("/schedules/{schedule_id}/pause")
async def pause_schedule(schedule_id: str):
    await scheduler.pause_schedule(schedule_id)

    return {"message": f"Paused schedule {schedule_id}"}


@router.post("/schedules/{schedule_id}/resume")
async def resume_schedule(schedule_id: str):
    await scheduler.unpause_schedule(schedule_id)

    return {"message": f"Resumed schedule {schedule_id}"}
