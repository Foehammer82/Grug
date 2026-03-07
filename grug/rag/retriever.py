"""Document retrieval for RAG — backend-agnostic via VectorStore."""

import logging

from sqlalchemy import select

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
        campaign_id: int | None = None,
        public_only: bool = False,
    ) -> list[dict]:
        """Return the top-k relevant chunks for *query*.

        When *campaign_id* is provided, filters results to documents associated
        with that campaign.  If no campaign-scoped documents are found, falls
        back to the full guild-wide search so a response is always possible.

        When *public_only* is ``True``, only documents with ``is_public=True``
        are searched (used for non-GM player queries).

        Returns a list of dicts with keys: text, filename, document_id,
        chunk_index, distance.
        """
        if campaign_id is not None:
            chunks = await self._search_campaign(
                guild_id, query, k=k, campaign_id=campaign_id, public_only=public_only
            )
            if chunks:
                return chunks
            # Fall back to guild-wide search.
            logger.debug(
                "No campaign-scoped chunks found for campaign %d; falling back to guild search",
                campaign_id,
            )

        return await self._store.doc_query(
            guild_id, query, n_results=k, document_id=document_id
        )

    async def _search_campaign(
        self,
        guild_id: int,
        query: str,
        k: int,
        campaign_id: int,
        public_only: bool = False,
    ) -> list[dict]:
        """Search only documents whose campaign_id matches.

        When *public_only* is ``True``, further restricts to documents with
        ``is_public=True`` so private GM documents are never leaked to players.
        """
        from grug.db.models import Document
        from grug.db.session import get_session_factory

        factory = get_session_factory()
        async with factory() as session:
            stmt = select(Document.id).where(
                Document.guild_id == guild_id,
                Document.campaign_id == campaign_id,
            )
            if public_only:
                stmt = stmt.where(Document.is_public.is_(True))
            result = await session.execute(stmt)
            doc_ids = [row[0] for row in result.all()]

        if not doc_ids:
            return []

        # Gather results across all campaign documents and pick the top-k.
        all_chunks: list[dict] = []
        for doc_id in doc_ids:
            chunks = await self._store.doc_query(
                guild_id, query, n_results=k, document_id=doc_id
            )
            all_chunks.extend(chunks)

        all_chunks.sort(key=lambda c: c.get("distance", 1.0))
        return all_chunks[:k]
