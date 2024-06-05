import pytest

from grug.scheduler import scheduler


@pytest.mark.asyncio
async def test_scheduler_init():

    assert scheduler
