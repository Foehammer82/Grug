"""Session notes tools for the Grug agent.

Registers a tool that lets Grug search past session notes for the campaign
linked to the current Discord channel.  Uses the existing RAG DocumentRetriever
scoped by campaign_id so only notes from the relevant campaign are returned.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from pydantic_ai import RunContext

from grug.agent.core import GrugDeps

if TYPE_CHECKING:
    from pydantic_ai import Agent

logger = logging.getLogger(__name__)


def register_session_notes_tools(agent: Agent[GrugDeps, str]) -> None:
    """Register session notes tools onto *agent*."""

    @agent.tool
    async def search_session_notes(ctx: RunContext[GrugDeps], query: str) -> str:
        """Search past session notes for the campaign linked to this channel.

        Use this tool when a player or GM asks about events, NPCs, loot,
        decisions, or anything else that may have been recorded in past
        session notes.

        Args:
            query: A natural language question or search phrase about the
                   campaign's session history, e.g. "What happened with the
                   merchant guild?" or "What loot did we get last session?"
        """
        campaign_id = ctx.deps.campaign_id
        guild_id = ctx.deps.guild_id

        if campaign_id is None:
            return (
                "There is no campaign linked to this channel. "
                "Session notes can only be searched for channels with an active campaign."
            )

        from grug.db.models import SessionNote
        from grug.db.session import get_session_factory
        from grug.rag.retriever import DocumentRetriever
        from sqlalchemy import select

        # Quick check — are there any synthesized notes for this campaign?
        factory = get_session_factory()
        async with factory() as session:
            result = await session.execute(
                select(SessionNote.id).where(
                    SessionNote.campaign_id == campaign_id,
                    SessionNote.synthesis_status == "done",
                )
            )
            note_ids = [row[0] for row in result.all()]

        if not note_ids:
            return (
                "No synthesized session notes found for this campaign yet. "
                "Notes may still be processing, or none have been submitted."
            )

        # Use DocumentRetriever — it already handles campaign-scoped doc search.
        retriever = DocumentRetriever()
        chunks = await retriever.search(
            guild_id=guild_id,
            query=query,
            k=5,
            campaign_id=campaign_id,
        )

        if not chunks:
            return "No relevant session notes found for that query."

        lines: list[str] = [f"**Session notes matching**: *{query}*\n"]
        for i, chunk in enumerate(chunks, start=1):
            filename = chunk.get("filename", "unknown")
            text = chunk.get("text", "").strip()
            # Strip the internal filename prefix so we show a friendly label.
            note_label = (
                filename.replace("session_note_", "Note ").split("_")[0]
                if "session_note_" in filename
                else filename
            )
            lines.append(f"**[{i}] {note_label}**\n{text}\n")

        return "\n".join(lines)
