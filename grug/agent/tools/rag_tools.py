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


async def _is_gm_or_admin(ctx: RunContext[GrugDeps]) -> bool:
    """Return True if the requesting user is the campaign GM or a Grug admin."""
    from grug.agent.tools.campaign_tools import _is_admin
    from grug.db.models import Campaign
    from grug.db.session import get_session_factory

    if await _is_admin(ctx):
        return True

    if ctx.deps.campaign_id is None:
        return False

    factory = get_session_factory()
    async with factory() as session:
        campaign = (
            await session.execute(
                select(Campaign).where(Campaign.id == ctx.deps.campaign_id)
            )
        ).scalar_one_or_none()

    if campaign is None:
        return False

    return campaign.gm_discord_user_id is not None and str(
        campaign.gm_discord_user_id
    ) == str(ctx.deps.user_id)


def _doc_viewer_url(guild_id: int, campaign_id: int, document_id: int) -> str:
    """Build a web UI link to the document viewer page."""
    from grug.config.settings import get_settings

    base = get_settings().frontend_url.rstrip("/")
    return f"{base}/guilds/{guild_id}/campaigns/{campaign_id}/documents/{document_id}"


def register_rag_tools(agent: Agent[GrugDeps, str]) -> None:
    """Register document search and listing tools on *agent*."""

    @agent.tool
    async def search_documents(
        ctx: RunContext[GrugDeps], query: str, k: int = 5
    ) -> str:
        """Search indexed documents using semantic similarity.

        When in a campaign channel or DM with an active campaign, searches
        campaign-scoped documents first, then falls back to guild-wide results.
        GMs and admins search all documents (including private ones); regular
        players only see public documents.

        Always include a link to the source document so the user can view it
        in the web UI.
        """
        from grug.rag.retriever import DocumentRetriever

        gm_or_admin = await _is_gm_or_admin(ctx)
        retriever = DocumentRetriever()
        chunks = await retriever.search(
            ctx.deps.guild_id,
            query,
            k=k,
            campaign_id=ctx.deps.campaign_id,
            public_only=not gm_or_admin,
        )
        if not chunks:
            return "No relevant documents found."

        parts = []
        seen_doc_ids: set[int] = set()
        for i, c in enumerate(chunks, 1):
            doc_id: int | None = c.get("document_id")
            link_str = ""
            if doc_id is not None and ctx.deps.campaign_id is not None:
                link = _doc_viewer_url(ctx.deps.guild_id, ctx.deps.campaign_id, doc_id)
                if doc_id not in seen_doc_ids:
                    link_str = f"\n[📄 View document]({link})"
                    seen_doc_ids.add(doc_id)
            parts.append(
                f"[{i}] From **{c['filename']}** (chunk {c['chunk_index']}):\n{c['text']}{link_str}"
            )
        return "\n\n---\n\n".join(parts)

    @agent.tool
    async def list_documents(ctx: RunContext[GrugDeps]) -> str:
        """List documents indexed for the current campaign.

        When in a campaign channel, lists only documents belonging to that
        campaign.  GMs and admins see all documents (public and private); regular
        members only see public ones.  Falls back to a guild-wide list when no
        campaign is active.
        """
        from grug.db.models import Document
        from grug.db.session import get_session_factory

        gm_or_admin = await _is_gm_or_admin(ctx)

        factory = get_session_factory()
        async with factory() as session:
            if ctx.deps.campaign_id is not None:
                stmt = select(Document).where(
                    Document.guild_id == ctx.deps.guild_id,
                    Document.campaign_id == ctx.deps.campaign_id,
                )
                if not gm_or_admin:
                    stmt = stmt.where(Document.is_public.is_(True))
                result = await session.execute(stmt)
            else:
                result = await session.execute(
                    select(Document).where(Document.guild_id == ctx.deps.guild_id)
                )
            docs = result.scalars().all()

        if not docs:
            if ctx.deps.campaign_id is not None:
                if gm_or_admin:
                    return "No documents have been indexed for this campaign yet."
                return "No public documents have been shared for this campaign yet."
            return "No documents have been indexed for this server yet."

        lines = ["Indexed documents:"]
        for doc in docs:
            desc = f" — {doc.description}" if doc.description else ""
            if gm_or_admin:
                visibility = " 🔓" if doc.is_public else " 🔒"
            else:
                visibility = ""
            if ctx.deps.campaign_id is not None:
                link = _doc_viewer_url(ctx.deps.guild_id, ctx.deps.campaign_id, doc.id)
                link_str = f" ([view]({link}))"
            else:
                link_str = ""
            lines.append(
                f"• **{doc.filename}** ({doc.chunk_count} chunks){desc}{visibility}{link_str}"
            )
        return "\n".join(lines)
