from datetime import date

from loguru import logger
from openai.types import Image
from sqlalchemy import Date, func
from sqlmodel import cast, select

from grug.db import async_session
from grug.models import DalleImageRequest
from grug.settings import settings


async def generate_ai_image(prompt: str) -> dict[str, str | int]:
    """
    Generate an image using OpenAI's DALL-E model, and returns a URL to the generated image.

    Args:
        prompt (str): The prompt to generate the image from.

    Notes:
        - as of 6/9/2024, it costs $0.04 per dall-e-3 image, and $0.02 per dall-e-2 image
        - pricing reference: https://openai.com/api/pricing/
        - API reference: https://platform.openai.com/docs/guides/images/usage?context=python

    Returns:
        str: The URL to the generated image.
        dict: A dictionary with the following keys:
            - image_url (str): The URL to the generated image.
            - model (str): The model used to generate the image.
            - size (str): The size of the generated image.
            - image_generations_left_today (Optional(int)): The number of image generations left today, based on the app's
              settings, and Grugs wallet.
    """
    from grug.openai_assistant import assistant

    async with async_session() as session:

        # Get the image requests remaining for the day
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
