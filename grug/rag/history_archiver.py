"""Archival of conversation history into ChromaDB for long-term RAG recall.

When the active message window overflows, old messages are summarised by Claude
into a compact narrative chunk and stored in a per-guild history collection.
This keeps Grug's memory from growing unbounded while preserving the lore.
"""

import logging
import uuid
from datetime import datetime, timezone

import chromadb
from anthropic import AsyncAnthropic

from grug.config.settings import get_settings

logger = logging.getLogger(__name__)

_HISTORY_COLLECTION_SUFFIX = "_history"

_SUMMARY_SYSTEM = (
    "You are a meticulous TTRPG session scribe. "
    "Summarise the provided conversation into a concise but information-dense paragraph. "
    "Capture: key decisions, NPC interactions, plot events, locations visited, "
    "items acquired, and any unresolved threads. "
    "Write in past tense, third person. Be specific — names, places, and outcomes matter. "
    "Omit small talk and bot command noise."
)


def _history_collection_name(guild_id: int) -> str:
    return f"guild_{guild_id}{_HISTORY_COLLECTION_SUFFIX}"


class ConversationArchiver:
    """Summarises and stores batches of old conversation messages into ChromaDB."""

    def __init__(self) -> None:
        settings = get_settings()
        self._client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
        self._anthropic = AsyncAnthropic(api_key=settings.anthropic_api_key)
        self._model = settings.anthropic_model
        self._max_summaries = settings.agent_history_max_summaries

    def _get_collection(self, guild_id: int):
        return self._client.get_or_create_collection(name=_history_collection_name(guild_id))

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
            messages=[{"role": "user", "content": f"Conversation to summarise:\n\n{transcript}"}],
        )
        return response.content[0].text.strip()

    def _prune_oldest(self, guild_id: int, channel_id: int) -> None:
        """Remove the oldest summaries if we're over the per-channel cap."""
        collection = self._get_collection(guild_id)
        results = collection.get(
            where={"channel_id": channel_id},
            include=["metadatas"],
        )
        ids = results["ids"]
        if len(ids) <= self._max_summaries:
            return

        # Sort by start_time ascending and delete the oldest excess entries.
        paired = sorted(
            zip(ids, results["metadatas"]),
            key=lambda x: x[1].get("start_time", ""),
        )
        to_delete = [id_ for id_, _ in paired[: len(ids) - self._max_summaries]]
        collection.delete(ids=to_delete)
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
        """Summarise *messages* and store the result in ChromaDB. Returns the summary text."""
        if not messages:
            return ""

        summary = await self._summarise(messages)
        start_time = messages[0].get("created_at", datetime.now(timezone.utc).isoformat())
        end_time = messages[-1].get("created_at", datetime.now(timezone.utc).isoformat())

        collection = self._get_collection(guild_id)
        doc_id = str(uuid.uuid4())
        collection.upsert(
            ids=[doc_id],
            documents=[summary],
            metadatas=[
                {
                    "guild_id": guild_id,
                    "channel_id": channel_id,
                    "message_count": len(messages),
                    "start_time": str(start_time),
                    "end_time": str(end_time),
                }
            ],
        )

        self._prune_oldest(guild_id, channel_id)
        logger.info(
            "Archived %d messages into history summary for guild %d channel %d",
            len(messages),
            guild_id,
            channel_id,
        )
        return summary

    def search(self, guild_id: int, channel_id: int, query: str, k: int = 3) -> list[dict]:
        """Return the top-k relevant history summaries for *query*."""
        collection = self._get_collection(guild_id)
        try:
            results = collection.query(
                query_texts=[query],
                n_results=k,
                where={"channel_id": channel_id},
                include=["documents", "metadatas", "distances"],
            )
        except Exception as exc:
            logger.warning("History ChromaDB query failed: %s", exc)
            return []

        summaries = []
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            summaries.append(
                {
                    "summary": doc,
                    "start_time": meta.get("start_time", ""),
                    "end_time": meta.get("end_time", ""),
                    "message_count": meta.get("message_count", 0),
                    "distance": dist,
                }
            )
        return summaries
