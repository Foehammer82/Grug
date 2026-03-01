"""Document retrieval for RAG — backend-agnostic via VectorStore."""

import logging

from grug.rag.vector_store import VectorStore, get_vector_store

logger = logging.getLogger(__name__)


class DocumentRetriever:
    """Retrieves relevant document chunks from the configured vector store."""

    def __init__(self, store: VectorStore | None = None) -> None:
        self._store = store or get_vector_store()

    async def search(
        self,
        guild_id: int,
        query: str,
        k: int = 5,
        document_id: int | None = None,
    ) -> list[dict]:
        """Return the top-k relevant chunks for *query*.

        Returns a list of dicts with keys: text, filename, chunk_index, distance.
        """
        return await self._store.doc_query(
            guild_id, query, n_results=k, document_id=document_id
        )
