"""RAG (document search) tools for the Grug agent.

Registers ``search_documents`` and ``list_documents`` on the pydantic-ai Agent
following the same ``register_*_tools(agent)`` pattern used by glossary_tools.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from pydantic_ai import RunContext
from sqlalchemy import select

from grug.agent.core import GrugDeps

if TYPE_CHECKING:
    from pydantic_ai import Agent

logger = logging.getLogger(__name__)


def register_rag_tools(agent: Agent[GrugDeps, str]) -> None:
    """Register document search and listing tools on *agent*."""

    @agent.tool
    async def search_documents(
        ctx: RunContext[GrugDeps], query: str, k: int = 5
    ) -> str:
        """Search indexed documents using semantic similarity.

        When in a campaign channel or DM with an active campaign, searches
        campaign-scoped documents first, then falls back to guild-wide results.
        Use when the user asks about rules, lore, or content from uploaded documents.
        """
        from grug.rag.retriever import DocumentRetriever

        retriever = DocumentRetriever()
        chunks = await retriever.search(
            ctx.deps.guild_id, query, k=k, campaign_id=ctx.deps.campaign_id
        )
        if not chunks:
            return "No relevant documents found."
        parts = [
            f"[{i}] From **{c['filename']}** (chunk {c['chunk_index']}):\n{c['text']}"
            for i, c in enumerate(chunks, 1)
        ]
        return "\n\n---\n\n".join(parts)

    @agent.tool
    async def list_documents(ctx: RunContext[GrugDeps]) -> str:
        """List documents indexed for the current campaign.

        When in a campaign channel, lists only documents belonging to that
        campaign.  Falls back to a guild-wide list when no campaign is active.
        """
        from grug.db.models import Document
        from grug.db.session import get_session_factory

        factory = get_session_factory()
        async with factory() as session:
            if ctx.deps.campaign_id is not None:
                result = await session.execute(
                    select(Document).where(
                        Document.guild_id == ctx.deps.guild_id,
                        Document.campaign_id == ctx.deps.campaign_id,
                    )
                )
            else:
                result = await session.execute(
                    select(Document).where(Document.guild_id == ctx.deps.guild_id)
                )
            docs = result.scalars().all()
        if not docs:
            if ctx.deps.campaign_id is not None:
                return "No documents have been indexed for this campaign yet."
            return "No documents have been indexed for this server yet."
        lines = ["Indexed documents:"]
        for doc in docs:
            desc = f" — {doc.description}" if doc.description else ""
            lines.append(f"• **{doc.filename}** ({doc.chunk_count} chunks){desc}")
        return "\n".join(lines)
