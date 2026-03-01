"""Abstract vector store protocol and singleton factory.

Both ChromaDB and pgvector backends implement this protocol so the rest of
the codebase never imports either concrete implementation directly.

Usage
-----
    from grug.rag.vector_store import get_vector_store

    store = get_vector_store()
    await store.doc_upsert(guild_id, ids, texts, metadatas)
"""

import logging
from typing import Protocol, runtime_checkable

logger = logging.getLogger(__name__)


@runtime_checkable
class VectorStore(Protocol):
    """Protocol shared by ChromaVectorStore and PGVectorStore."""

    # ------------------------------------------------------------------
    # Document chunks (used by DocumentIndexer and DocumentRetriever)
    # ------------------------------------------------------------------

    async def doc_upsert(
        self,
        guild_id: int,
        ids: list[str],
        texts: list[str],
        metadatas: list[dict],
    ) -> None:
        """Insert or update document chunks for *guild_id*."""
        ...

    async def doc_query(
        self,
        guild_id: int,
        query: str,
        n_results: int,
        document_id: int | None = None,
    ) -> list[dict]:
        """Semantic search over document chunks.

        Returns a list of dicts with keys: text, filename, description,
        chunk_index, distance.
        """
        ...

    async def doc_get_ids(self, guild_id: int, document_id: int) -> list[str]:
        """Return all chunk IDs belonging to *document_id*."""
        ...

    async def doc_delete(self, guild_id: int, ids: list[str]) -> None:
        """Delete specific chunks by ID."""
        ...

    async def guild_delete(self, guild_id: int) -> None:
        """Delete all document chunks for an entire guild."""
        ...

    # ------------------------------------------------------------------
    # History summaries (used by ConversationArchiver)
    # ------------------------------------------------------------------

    async def history_upsert(
        self,
        guild_id: int,
        id: str,
        summary: str,
        metadata: dict,
    ) -> None:
        """Insert or update a history summary."""
        ...

    async def history_get(
        self,
        guild_id: int,
        channel_id: int,
    ) -> list[tuple[str, dict]]:
        """Return all (id, metadata) pairs for a channel — used for pruning."""
        ...

    async def history_delete(self, guild_id: int, ids: list[str]) -> None:
        """Delete specific history summaries by ID."""
        ...

    async def history_query(
        self,
        guild_id: int,
        channel_id: int,
        query: str,
        k: int,
    ) -> list[dict]:
        """Semantic search over history summaries.

        Returns a list of dicts with keys: summary, start_time, end_time,
        message_count, distance.
        """
        ...

    # ------------------------------------------------------------------
    # Character sheets (per-character collections)
    # ------------------------------------------------------------------

    async def character_upsert(
        self,
        character_id: int,
        ids: list[str],
        texts: list[str],
        metadatas: list[dict],
    ) -> None:
        """Insert or update character sheet chunks for *character_id*."""
        ...

    async def character_query(
        self,
        character_id: int,
        query: str,
        n_results: int,
    ) -> list[dict]:
        """Semantic search over a character's sheet chunks.

        Returns a list of dicts with keys: text, chunk_index, distance.
        """
        ...

    async def character_delete_all(self, character_id: int) -> None:
        """Delete all indexed chunks for a character (e.g. on re-upload)."""
        ...


# ---------------------------------------------------------------------------
# Singleton factory
# ---------------------------------------------------------------------------

_store: VectorStore | None = None


def get_vector_store() -> VectorStore:
    """Return the process-wide VectorStore instance (lazy, thread-safe-ish).

    Always uses the pgvector backend (Postgres required).
    """
    global _store
    if _store is None:
        from grug.db.session import get_session_factory
        from grug.rag.backends.pgvector_store import PGVectorStore

        logger.info("Vector backend: pgvector (Postgres)")
        _store = PGVectorStore(get_session_factory())
    return _store
