"""RAG tools for the Grug agent."""

import logging
from typing import Any

from sqlalchemy import select

from grug.agent.tools.base import BaseTool
from grug.db.models import Document
from grug.db.session import get_session_factory
from grug.rag.retriever import DocumentRetriever

logger = logging.getLogger(__name__)


class SearchDocumentsTool(BaseTool):
    """Search indexed guild documents using semantic similarity."""

    def __init__(self, guild_id: int) -> None:
        self._guild_id = guild_id
        self._retriever = DocumentRetriever()

    @property
    def name(self) -> str:
        return "search_documents"

    @property
    def description(self) -> str:
        return (
            "Search the guild's indexed documents using a semantic similarity query. "
            "Use this when the user asks about rules, lore, or other content from uploaded documents."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query",
                },
                "k": {
                    "type": "integer",
                    "description": "Number of results to return (default 5)",
                    "default": 5,
                },
            },
            "required": ["query"],
        }

    async def run(self, query: str, k: int = 5, **_: Any) -> str:
        chunks = self._retriever.search(self._guild_id, query, k=k)
        if not chunks:
            return "No relevant documents found."
        parts = []
        for i, chunk in enumerate(chunks, 1):
            parts.append(
                f"[{i}] From **{chunk['filename']}** (chunk {chunk['chunk_index']}):\n{chunk['text']}"
            )
        return "\n\n---\n\n".join(parts)


class ListDocumentsTool(BaseTool):
    """List documents indexed for this guild."""

    def __init__(self, guild_id: int) -> None:
        self._guild_id = guild_id

    @property
    def name(self) -> str:
        return "list_documents"

    @property
    def description(self) -> str:
        return "List all documents that have been indexed for this server."

    @property
    def parameters(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}, "required": []}

    async def run(self, **_: Any) -> str:
        factory = get_session_factory()
        async with factory() as session:
            result = await session.execute(
                select(Document).where(Document.guild_id == self._guild_id)
            )
            docs = result.scalars().all()
        if not docs:
            return "No documents have been indexed for this server yet."
        lines = ["Indexed documents:"]
        for doc in docs:
            desc = f" — {doc.description}" if doc.description else ""
            lines.append(f"• **{doc.filename}** ({doc.chunk_count} chunks){desc}")
        return "\n".join(lines)
