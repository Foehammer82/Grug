"""Archival of conversation history into the vector store for long-term RAG recall.

When the active message window overflows, old messages are summarised by Claude
into a compact narrative chunk and stored via the configured VectorStore backend
(ChromaDB or pgvector). This keeps Grug's memory from growing unbounded while
preserving the lore.
"""

import logging
import uuid
from datetime import datetime, timezone

from anthropic import AsyncAnthropic

from grug.config.settings import get_settings
from grug.rag.vector_store import VectorStore, get_vector_store

logger = logging.getLogger(__name__)

_SUMMARY_SYSTEM = (
    "You are a meticulous TTRPG session scribe. "
    "Summarise the provided conversation into a concise but information-dense paragraph. "
    "Capture: key decisions, NPC interactions, plot events, locations visited, "
    "items acquired, and any unresolved threads. "
    "Write in past tense, third person. Be specific — names, places, and outcomes matter. "
    "Omit small talk and bot command noise."
)


class ConversationArchiver:
    """Summarises and stores batches of old conversation messages in the vector store."""

    def __init__(self, store: VectorStore | None = None) -> None:
        settings = get_settings()
        self._store = store or get_vector_store()
        self._anthropic = AsyncAnthropic(api_key=settings.anthropic_api_key)
        self._model = settings.anthropic_model
        self._max_summaries = settings.agent_history_max_summaries

    async def _summarise(self, messages: list[dict]) -> str:
        """Ask Claude to summarise a batch of messages into a session narrative."""
        transcript_lines = []
        for m in messages:
            speaker = m.get("author_name") or m["role"].capitalize()
            transcript_lines.append(f"{speaker}: {m['content']}")
        transcript = "\n".join(transcript_lines)

        response = await self._anthropic.messages.create(
            model=self._model,
            max_tokens=512,
            system=_SUMMARY_SYSTEM,
            messages=[
                {
                    "role": "user",
                    "content": f"Conversation to summarise:\n\n{transcript}",
                }
            ],
        )
        return response.content[0].text.strip()

    async def _prune_oldest(self, guild_id: int, channel_id: int) -> None:
        """Remove the oldest summaries if we're over the per-channel cap."""
        pairs = await self._store.history_get(guild_id, channel_id)
        if len(pairs) <= self._max_summaries:
            return

        # history_get returns pairs sorted by start_time asc (oldest first).
        to_delete = [id_ for id_, _ in pairs[: len(pairs) - self._max_summaries]]
        await self._store.history_delete(guild_id, to_delete)
        logger.info(
            "Pruned %d old history summaries for guild %d channel %d",
            len(to_delete),
            guild_id,
            channel_id,
        )

    async def archive(
        self,
        guild_id: int,
        channel_id: int,
        messages: list[dict],
    ) -> str:
        """Summarise *messages* and store the result in the vector store. Returns the summary."""
        if not messages:
            return ""

        summary = await self._summarise(messages)
        start_time = messages[0].get(
            "created_at", datetime.now(timezone.utc).isoformat()
        )
        end_time = messages[-1].get(
            "created_at", datetime.now(timezone.utc).isoformat()
        )

        doc_id = str(uuid.uuid4())
        await self._store.history_upsert(
            guild_id=guild_id,
            id=doc_id,
            summary=summary,
            metadata={
                "guild_id": guild_id,
                "channel_id": channel_id,
                "message_count": len(messages),
                "start_time": str(start_time),
                "end_time": str(end_time),
            },
        )

        await self._prune_oldest(guild_id, channel_id)
        logger.info(
            "Archived %d messages into history summary for guild %d channel %d",
            len(messages),
            guild_id,
            channel_id,
        )
        return summary

    async def search(
        self, guild_id: int, channel_id: int, query: str, k: int = 3
    ) -> list[dict]:
        """Return the top-k relevant history summaries for *query*."""
        return await self._store.history_query(guild_id, channel_id, query, k)
