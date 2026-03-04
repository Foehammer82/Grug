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
    _usage = result.usage()
    from grug.llm_usage import CallType, record_llm_usage

    await record_llm_usage(
        model=settings.anthropic_model,
        call_type=CallType.CRON_PARSE,
        input_tokens=_usage.request_tokens or 0,
        output_tokens=_usage.response_tokens or 0,
    )
    return result.output.cron_expression


async def parse_rrule_from_text(text: str) -> str:
    """Use an LLM to convert plain-English recurrence text to an iCal RRULE string."""
    from pydantic import BaseModel as PydanticBase
    from pydantic_ai import Agent
    from pydantic_ai.models.anthropic import AnthropicModel
    from pydantic_ai.providers.anthropic import AnthropicProvider

    from grug.config.settings import get_settings

    class _RruleResult(PydanticBase):
        rrule: str

    settings = get_settings()
    provider = AnthropicProvider(api_key=settings.anthropic_api_key)
    model = AnthropicModel(settings.anthropic_model, provider=provider)
    agent: Agent[None, _RruleResult] = Agent(
        model,
        output_type=_RruleResult,
        system_prompt=(
            "You convert plain-English recurrence descriptions into a single iCal "
            "RRULE string (without the 'RRULE:' prefix). Return ONLY the rrule "
            "field. Do not explain. Examples:\n"
            "  'every Thursday' -> 'FREQ=WEEKLY;BYDAY=TH'\n"
            "  'every other week on Saturday' -> 'FREQ=WEEKLY;INTERVAL=2;BYDAY=SA'\n"
            "  'first Monday of every month' -> 'FREQ=MONTHLY;BYDAY=1MO'\n"
            "  'every 2 weeks on Tuesday and Thursday' -> 'FREQ=WEEKLY;INTERVAL=2;BYDAY=TU,TH'\n"
            "  'every day' -> 'FREQ=DAILY'\n"
            "  'every 3 months on the 15th' -> 'FREQ=MONTHLY;INTERVAL=3;BYMONTHDAY=15'"
        ),
    )
    result = await agent.run(text)
    _usage = result.usage()
    from grug.llm_usage import CallType, record_llm_usage

    await record_llm_usage(
        model=settings.anthropic_model,
        call_type=CallType.RRULE_PARSE,
        input_tokens=_usage.request_tokens or 0,
        output_tokens=_usage.response_tokens or 0,
    )
    return result.output.rrule
