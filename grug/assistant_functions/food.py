from datetime import date

from grug.models import Group
from grug.utils.food import get_distinct_event_occurrence_food_history, send_food_reminder


async def send_food_reminder_assistant_tool(group: Group) -> str:
    """
    Send a food reminder for all scheduled group events.

    Args:
        group (Group): The group to send the food reminder for.

    Returns:
        str: The message indicating the food reminder was sent.
    """

    # If no group is provided, return a message indicating no group was found
    if not group:
        return "Group to send food reminder for not found."

    events_with_food = [event for event in group.events if event.track_food]

    if len(events_with_food) == 0:
        return "No events with food tracking found for the group."

    food_reminders_sent = []
    for event in events_with_food:
        if event.id:
            await send_food_reminder(event.id)
            food_reminders_sent.append(event.name)

    return f"Food reminders sent for events: {', '.join(food_reminders_sent)}"


async def get_food_history_assistant_tool(group: Group) -> dict[str, list[tuple[str, str]]]:
    """
    Get the history of who brought food to each event in the given group.

    Args:
        group (Group): The group to get the food history for.

    Returns:
        dict[str, str]: a dictionary where the keys are the event names and the values are a list of tuples whose
        with the first tuple value being the persons name and the second value being the event date they brought food
        on.
    """
    if not group:
        raise ValueError("Group not found.")

    events_with_food = [event for event in group.events if event.track_food]

    if len(events_with_food) == 0:
        raise ValueError("No events with food tracking found for the group.")

    food_history = {}
    for event in events_with_food:
        if event.id is None:
            raise ValueError("Event occurrence ID is required to get food history.")

        food_history[event.name] = [
            (
                event_food_history.user_assigned_food.friendly_name if event_food_history.user_assigned_food else None,
                event_food_history.event_occurrence.event_date,
            )
            for event_food_history in await get_distinct_event_occurrence_food_history(event.id)
            if event_food_history.event_occurrence.event_date <= date.today()
        ]

    return food_history
