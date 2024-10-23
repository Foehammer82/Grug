from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable, Set

import discord
from discord import Poll
from elasticsearch import Elasticsearch
from loguru import logger
from openai.types import Image
from sqlalchemy import Date, func
from sqlmodel import cast, select

from grug.db import async_session
from grug.models import DalleImageRequest
from grug.models_crud import (
    get_distinct_users_who_last_brought_food,
    get_or_create_discord_server_group,
    get_or_create_next_game_session_event,
)
from grug.settings import settings

assistant_functions: Set[Callable[..., Any]] = set()


def register_function(function: Callable[..., Any]) -> Callable[..., Any]:
    """Register a function as an assistant function."""
    assistant_functions.add(function)
    return function


@register_function
async def generate_ai_image(prompt: str) -> dict[str, str | int] | None:
    """
    Generate an image using OpenAI's DALL-E model, and returns a URL to the generated image.

    Args:
        prompt (str): The prompt to generate the image from.

    Notes:
        - as of 6/9/2024, it costs $0.04 per dall-e-3 image, and $0.02 per dall-e-2 image
        - pricing reference: https://openai.com/api/pricing/
        - API reference: https://platform.openai.com/docs/guides/images/usage?context=python

    Returns:
        dict: A dictionary with the following keys:
            - image_url (str): The URL to the generated image.
            - model (str): The model used to generate the image.
            - size (str): The size of the generated image.
            - image_generations_left_today (Optional(int)): The number of image generations left today, based on the app's
              settings, and Grugs wallet.
        None: If the image generation limit has been exceeded or if the assistant is not available.
    """
    from grug.ai import assistant

    # Return None if the assistant is not available
    if not assistant:
        return None

    async with async_session() as session:

        # Get the image requests remaining for the day
        # noinspection PyTypeChecker,Pydantic
        picture_request_count_for_today = (
            await session.execute(
                select(func.count("*"))
                .select_from(DalleImageRequest)
                .where(cast(DalleImageRequest.request_time, Date) == date.today())
            )
        ).scalar()

        remaining_image_requests = settings.openai_image_daily_generation_limit - picture_request_count_for_today

        # Check if the user has exceeded the daily image generation limit
        if remaining_image_requests and remaining_image_requests <= 0:
            raise ValueError("You have exceeded the daily image generation limit.")
        logger.info(f"Remaining Dall-E image requests: {remaining_image_requests}")

        logger.info("### Generating AI Image ###")
        logger.info(f"Prompt: {prompt}")
        logger.info(f"Model: {settings.openai_image_default_model}")
        logger.info(f"Size: {settings.openai_image_default_size}")
        logger.info(f"Quality: {settings.openai_image_default_quality}")

        response = await assistant.async_client.images.generate(
            model=settings.openai_image_default_model,
            prompt=prompt,
            size=settings.openai_image_default_size,
            quality=settings.openai_image_default_quality,
            n=1,
        )
        response_image: Image = response.data[0]

        logger.info(f"revised prompt: {response_image.revised_prompt}")
        logger.info(f"Image URL: {response_image.url}")
        logger.info("### Completed Generating AI Image ###")

        # Save the image request to the database
        dalle_image_request = DalleImageRequest(
            prompt=prompt,
            model=settings.openai_image_default_model,
            size=settings.openai_image_default_size,
            quality=settings.openai_image_default_quality,
            revised_prompt=response_image.revised_prompt,
            image_url=response_image.url,
        )
        session.add(dalle_image_request)
        await session.commit()

    return {
        "image_url": response_image.url,
        "model": settings.openai_image_default_model,
        "size": settings.openai_image_default_size,
        "image_generations_left_today": remaining_image_requests,
    }


@register_function
async def get_food_schedule(message: discord.Message) -> dict[str, Any]:
    """
    Get information about who will bring and who has brought food for the group.

    Args:
        message (Message): The message that triggered the function.

    Returns:
        dict: A dictionary with the following keys
            - history (list): A list of tuples containing the name of the user, the date they brought food, and whether
              the date is in the past.
            - future (list): A list of tuples containing the name of the user, the date they are scheduled to bring food,
              and whether the date is in the future.
            - todays_date (datetime): The current date.
    """
    if not message.guild:
        return {
            "history": [],
            "future": [],
            "todays_date": datetime.now().astimezone(timezone.utc),
        }

    async with async_session() as db_session:
        group = await get_or_create_discord_server_group(message.guild, db_session)

        if not group or not group.id:
            raise ValueError("Group not found.")
        if not group.game_session_track_food:
            raise ValueError(f"Food tracking disabled for the group {group.name}.")

        food_log = [
            (user.friendly_name, session_date, session_date > datetime.now().astimezone(timezone.utc))
            for user, session_date in await get_distinct_users_who_last_brought_food(group.id, db_session)
        ]

        return {
            "history": [food for food in food_log if not food[2]],
            "future": [food for food in food_log if food[2]],
            "todays_date": datetime.now().astimezone(timezone.utc),
        }


@register_function
async def get_next_session_attendance(message: discord.Message) -> str:
    """
    Get information about who is scheduled to attend the next game session.

    Returns:
        Markdown-formatted string: A string containing the names of the users who RSVP'd to the next session.
    """
    if not message.guild:
        return "No upcoming game session found."

    async with async_session() as db_session:
        group = await get_or_create_discord_server_group(message.guild, db_session)

        if not group or not group.id:
            raise ValueError("Group not found.")
        if not group.game_session_track_food:
            raise ValueError(f"Food tracking disabled for the group {group.name}.")

        next_game_session_event = await get_or_create_next_game_session_event(group.id, db_session)

        if next_game_session_event:
            return next_game_session_event.user_attendance_summary_md
        else:
            return "No upcoming game session found."


@register_function
def search_archives_of_nethys(search_string: str) -> list[dict]:
    """
    Searches the Elasticsearch index for entries matching the given search string within the
    [AON](https://2e.aonprd.com/) (Archives of Nethys) dataset.

    Args:
        search_string (str): The string to search for within the AON dataset.

    Returns:
        list[dict]: A list of dictionaries, each representing a cleaned-up search result. Each dictionary contains
        the keys:
            - name (str): The name of the entry.
            - type (str): The type of the entry (e.g., Ancestry, Class).
            - summary (str, optional): A summary of the entry, if available.
            - sources (list): The sources from which the entry is derived.
            - url (str): The URL to the detailed entry on the AON website.

    Note:
        This function requires the Elasticsearch Python client and assumes access to an Elasticsearch instance with
        the AON dataset indexed under the index named "aon".
    """
    logger.info(f"Searching AoN for: {search_string}")

    es = Elasticsearch("https://elasticsearch.aonprd.com/")

    es_response = es.search(
        index="aon",
        query={
            "function_score": {
                "query": {
                    "bool": {
                        "should": [
                            {"match_phrase_prefix": {"name.sayt": {"query": search_string}}},
                            {"match_phrase_prefix": {"text.sayt": {"query": search_string, "boost": 0.1}}},
                            {"term": {"name": search_string}},
                            {
                                "bool": {
                                    "must": [
                                        {
                                            "multi_match": {
                                                "query": word,
                                                "type": "best_fields",
                                                "fields": [
                                                    "name",
                                                    "text^0.1",
                                                    "trait_raw",
                                                    "type",
                                                ],
                                                "fuzziness": "auto",
                                            }
                                        }
                                        for word in search_string.split(" ")
                                    ]
                                }
                            },
                        ],
                        "must_not": [{"term": {"exclude_from_search": True}}],
                        "minimum_should_match": 1,
                    }
                },
                "boost_mode": "multiply",
                "functions": [
                    {"filter": {"terms": {"type": ["Ancestry", "Class"]}}, "weight": 1.1},
                    {"filter": {"terms": {"type": ["Trait"]}}, "weight": 1.05},
                ],
            }
        },
        sort=["_score", "_doc"],
        aggs={
            "group1": {
                "composite": {
                    "sources": [{"field1": {"terms": {"field": "type", "missing_bucket": True}}}],
                    "size": 10000,
                }
            }
        },
        source={"excludes": ["text"]},
    )

    results_raw = [hit["_source"] for hit in es_response.body["hits"]["hits"]]

    results_clean = [
        {
            "name": hit["name"],
            "type": hit["type"],
            "summary": hit["summary"] if "summary" in hit else None,
            # "overview_markdown": hit["markdown"] if "markdown" in hit else None,
            # "rarity": hit["rarity"] if "rarity" in hit else None,
            "sources": hit["source_raw"],
            "url": f"https://2e.aonprd.com{hit['url']}",
        }
        for hit in results_raw
    ]

    logger.info(
        f'Found {len(results_clean)} results from AoN for "{search_string}": '
        f'{[result["name"] for result in results_clean]}'
    )

    return results_clean


@register_function
async def create_poll(
    message: discord.Message, poll_question: str, answers: str, duration_hours: int = 24, multiple: bool = False
) -> None:
    """
    Create a poll in the group's discord channel.

    Args:
        message (Message): The message that triggered the poll.
        poll_question (str): The question to ask in the poll.
        answers (str): A comma seperated list of answers to provide in the poll.
        duration_hours (int, optional): The duration of the poll in hours. Defaults to 24.
        multiple (bool, optional): Whether multiple answers can be selected in the poll. Defaults to False.
    """

    # Define the poll
    poll = Poll(
        question=poll_question,
        multiple=multiple,
        duration=timedelta(hours=duration_hours),
    )

    # Add the answers to the poll
    for answer in answers.split(","):
        poll.add_answer(text=answer.strip())

    # send a poll to the channel
    await message.channel.send(poll=poll)
