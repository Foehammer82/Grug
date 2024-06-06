from loguru import logger
from openai.types import Image

from grug.settings import settings


async def generate_ai_image(prompt: str) -> str:
    """
    Generate an image using OpenAI's DALL-E model, and returns a URL to the generated image.

    Args:
        prompt (str): The prompt to generate the image from.

    Returns:
        str: The URL to the generated image.
        dict: A dictionary with the following keys:
            - image_url (str): The URL to the generated image.
            - model (str): The model used to generate the image.
            - size (str): The size of the generated image.
            - image_generations_left_today (int): The number of image generations left today, based on the app's
              settings, and Grugs wallet.
    """
    from grug.openai_assistant import assistant

    # TODO: build in rate limiting (note that it costs $0.04 per dall-e-3 image, and $0.02 per dall-e-2 image)
    #       - pricing reference: https://openai.com/api/pricing/
    #       - API reference: https://platform.openai.com/docs/guides/images/usage?context=python

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

    return {
        "image_url": response_image.url,
        "model": settings.openai_image_default_model,
        "size": settings.openai_image_default_size,
        "image_generations_left_today": 25,  # TODO: Implement a way to track this
    }
