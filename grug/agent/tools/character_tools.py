"""Character sheet tools for the Grug agent.

Registers ``get_character_sheet``, ``update_character_field``, and
``search_character_knowledge`` on the pydantic-ai Agent.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from pydantic_ai import RunContext
from sqlalchemy import select

from grug.agent.core import GrugDeps

if TYPE_CHECKING:
    from pydantic_ai import Agent

logger = logging.getLogger(__name__)


def register_character_tools(agent: Agent[GrugDeps, str]) -> None:
    """Register all character-sheet tools on *agent*."""

    @agent.tool
    async def get_character_sheet(ctx: RunContext[GrugDeps]) -> str:
        """Retrieve the current user's active character sheet.

        Use when asked about the user's character, stats, abilities,
        inventory, HP, or any other character-specific information.
        Returns an error string if no active character is set.
        """
        from grug.db.models import Character, UserProfile
        from grug.db.session import get_session_factory

        char_id = ctx.deps.active_character_id
        if char_id is None:
            factory = get_session_factory()
            async with factory() as session:
                profile = (
                    await session.execute(
                        select(UserProfile).where(
                            UserProfile.discord_user_id == ctx.deps.user_id
                        )
                    )
                ).scalar_one_or_none()
                if profile is None or profile.active_character_id is None:
                    return "No active character found. Ask the player to upload a sheet with !character upload."
                char_id = profile.active_character_id

        factory = get_session_factory()
        async with factory() as session:
            character = (
                await session.execute(select(Character).where(Character.id == char_id))
            ).scalar_one_or_none()

        if character is None:
            return "Character not found."

        sd = character.structured_data or {}
        lines = [
            f"Character: {character.name}",
            f"System: {character.system}",
            f"Structured data: {json.dumps(sd, indent=2)}",
        ]
        if character.raw_sheet_text:
            lines += ["", "Raw sheet text:", character.raw_sheet_text[:3000]]
        return "\n".join(lines)

    @agent.tool
    async def update_character_field(
        ctx: RunContext[GrugDeps], field: str, value: str
    ) -> str:
        """Update a specific field in the current user's active character sheet.

        Use when the player's character changes during a session: HP loss/gain,
        levelling up, acquiring/spending items, learning spells, etc.

        Parameters
        ----------
        field:
            Dot-notation path to the field, e.g. 'hp.current', 'level', 'notes'.
        value:
            New value as a string. Numbers and JSON structures are coerced automatically.
        """
        from grug.character.indexer import CharacterIndexer
        from grug.db.models import Character, UserProfile
        from grug.db.session import get_session_factory

        char_id = ctx.deps.active_character_id
        if char_id is None:
            factory = get_session_factory()
            async with factory() as session:
                profile = (
                    await session.execute(
                        select(UserProfile).where(
                            UserProfile.discord_user_id == ctx.deps.user_id
                        )
                    )
                ).scalar_one_or_none()
                if profile is None or profile.active_character_id is None:
                    return "No active character to update."
                char_id = profile.active_character_id

        factory = get_session_factory()
        async with factory() as session:
            character = (
                await session.execute(select(Character).where(Character.id == char_id))
            ).scalar_one_or_none()
            if character is None:
                return "Character not found."

            sd = dict(character.structured_data or {})
            coerced: object = value
            try:
                coerced = json.loads(value)
            except (json.JSONDecodeError, TypeError):
                pass

            # Navigate dot-notation path and set the leaf key.
            keys = field.split(".")
            target = sd
            for key in keys[:-1]:
                if not isinstance(target, dict):
                    target = {}
                target = target.setdefault(key, {})
            if isinstance(target, dict):
                target[keys[-1]] = coerced

            character.structured_data = sd
            await session.commit()
            await session.refresh(character)
            raw_text = character.raw_sheet_text or ""
            character_id = character.id

        # Re-index so semantic search reflects the change.
        if raw_text:
            indexer = CharacterIndexer()
            await indexer.index_character(character_id, raw_text)

        return f"\u2705 Updated {field} = {coerced} for character ID {character_id}."

    @agent.tool
    async def search_character_knowledge(
        ctx: RunContext[GrugDeps], query: str, k: int = 4
    ) -> str:
        """Search the current user's character sheet for specific information.

        Use when asked about the character's specific abilities, spells,
        equipment, or traits. Searches the indexed sheet chunks semantically.
        """
        from grug.db.models import UserProfile
        from grug.db.session import get_session_factory
        from grug.rag.vector_store import get_vector_store

        char_id = ctx.deps.active_character_id
        if char_id is None:
            factory = get_session_factory()
            async with factory() as session:
                profile = (
                    await session.execute(
                        select(UserProfile).where(
                            UserProfile.discord_user_id == ctx.deps.user_id
                        )
                    )
                ).scalar_one_or_none()
                if profile is None or profile.active_character_id is None:
                    return "No active character to search."
                char_id = profile.active_character_id

        store = get_vector_store()
        chunks = await store.character_query(char_id, query, n_results=k)
        if not chunks:
            return "Nothing relevant found in the character sheet."
        parts = [
            f"[{i}] (chunk {c['chunk_index']}):\n{c['text']}"
            for i, c in enumerate(chunks, 1)
        ]
        return "\n\n---\n\n".join(parts)
