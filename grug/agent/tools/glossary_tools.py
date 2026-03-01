"""Glossary agent tools — look up and curate server-specific TTRPG definitions."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from pydantic_ai import RunContext
from sqlalchemy import or_, select

if TYPE_CHECKING:
    from pydantic_ai import Agent

    from grug.agent.core import GrugDeps

logger = logging.getLogger(__name__)

# Sentinel: agent-authored rows use 0 as the created_by / changed_by value.
_AGENT_USER_ID = 0


def register_glossary_tools(agent: "Agent[GrugDeps, str]") -> None:
    """Register all glossary tools on the provided pydantic-ai Agent."""

    @agent.tool
    async def lookup_glossary_term(ctx: RunContext, term: str) -> str:
        """Look up a term in this guild's glossary.

        Returns the best matching definition, preferring a channel-level definition
        over a guild-level one when both exist. Use whenever a term may have a
        server-specific or campaign-specific meaning that overrides your training.
        """
        from grug.db.models import GlossaryTerm
        from grug.db.session import get_session_factory

        factory = get_session_factory()
        search = f"%{term.lower()}%"
        async with factory() as session:
            result = await session.execute(
                select(GlossaryTerm)
                .where(
                    GlossaryTerm.guild_id == ctx.deps.guild_id,
                    or_(
                        GlossaryTerm.channel_id == ctx.deps.channel_id,
                        GlossaryTerm.channel_id.is_(None),
                    ),
                    GlossaryTerm.term.ilike(search),
                )
                .order_by(
                    # Channel-scoped rows first (higher precedence).
                    GlossaryTerm.channel_id.is_(None).asc(),
                    GlossaryTerm.term.asc(),
                )
            )
            matches = result.scalars().all()

        if not matches:
            return f"No glossary definition found for '{term}'."

        lines = [f"📖 Glossary results for '{term}':"]
        seen_terms: set[str] = set()
        for m in matches:
            key = m.term.lower()
            scope = f"#channel {m.channel_id}" if m.channel_id else "server-wide"
            if key not in seen_terms:
                lines.append(f"• **{m.term}** ({scope}): {m.definition}")
                seen_terms.add(key)
        return "\n".join(lines)

    @agent.tool
    async def upsert_glossary_term(
        ctx: RunContext,
        term: str,
        definition: str,
    ) -> str:
        """Add or update a guild-wide glossary term.

        Call this when:
        - A player defines or redefines a campaign-specific word.
        - You are corrected on what a term means in this server's context.
        - You observe a consistent pattern in how this group uses a particular word.

        IMPORTANT: You must NEVER overwrite a term that was created or edited by a human
        (ai_generated=False). If the term exists but is human-owned, return an
        acknowledgement without writing to the database.
        """
        from grug.db.models import GlossaryTerm, GlossaryTermHistory
        from grug.db.session import get_session_factory

        factory = get_session_factory()
        async with factory() as session:
            result = await session.execute(
                select(GlossaryTerm).where(
                    GlossaryTerm.guild_id == ctx.deps.guild_id,
                    GlossaryTerm.channel_id.is_(None),  # agent writes are always guild-wide
                    GlossaryTerm.term.ilike(term),
                )
            )
            existing = result.scalar_one_or_none()

            if existing is not None:
                if not existing.ai_generated:
                    # Human-owned — never overwrite.
                    return (
                        f"Grug note: '{existing.term}' is defined by the humans here as: "
                        f"{existing.definition}. Grug respect that and not change."
                    )
                # AI-owned — snapshot history then update.
                session.add(
                    GlossaryTermHistory(
                        term_id=existing.id,
                        guild_id=existing.guild_id,
                        old_term=existing.term,
                        old_definition=existing.definition,
                        old_ai_generated=existing.ai_generated,
                        changed_by=_AGENT_USER_ID,
                    )
                )
                existing.term = term
                existing.definition = definition
                existing.updated_at = datetime.now(timezone.utc)
                await session.commit()
                return f"📖 Grug update glossary: **{term}** — {definition}"
            else:
                # New term — ensure guild config exists first.
                from grug.agent.core import _ensure_guild

                await _ensure_guild(ctx.deps.guild_id)
                new_term = GlossaryTerm(
                    guild_id=ctx.deps.guild_id,
                    channel_id=None,  # guild-wide
                    term=term,
                    definition=definition,
                    ai_generated=True,
                    originally_ai_generated=True,
                    created_by=_AGENT_USER_ID,
                    updated_at=datetime.now(timezone.utc),
                )
                session.add(new_term)
                await session.commit()
                return f"📖 Grug add to glossary: **{term}** — {definition}"
