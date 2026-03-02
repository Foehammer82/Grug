"""Shared service helpers for the API layer."""


async def parse_cron_from_text(text: str) -> str:
    """Use an LLM to convert plain-English schedule text to a 5-field UTC cron expression."""
    from pydantic import BaseModel as PydanticBase
    from pydantic_ai import Agent
    from pydantic_ai.models.anthropic import AnthropicModel
    from pydantic_ai.providers.anthropic import AnthropicProvider

    from grug.config.settings import get_settings

    class _CronResult(PydanticBase):
        cron_expression: str

    settings = get_settings()
    provider = AnthropicProvider(api_key=settings.anthropic_api_key)
    model = AnthropicModel(settings.anthropic_model, provider=provider)
    agent: Agent[None, _CronResult] = Agent(
        model,
        output_type=_CronResult,
        system_prompt=(
            "You convert plain-English schedule descriptions into a single 5-field UTC "
            "cron expression (minute, hour, day-of-month, month, day-of-week). "
            "Return ONLY the cron_expression field. Do not explain. Examples:\n"
            "  'every Monday at 9am UTC' -> '0 9 * * 1'\n"
            "  'every day at midnight' -> '0 0 * * *'\n"
            "  'every weekday at 5pm UTC' -> '0 17 * * 1-5'"
        ),
    )
    result = await agent.run(text)
    return result.output.cron_expression
