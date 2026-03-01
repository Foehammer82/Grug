"""pgvector vector store backend.

Stores document chunk embeddings and conversation history summaries directly
in Postgres using the vector extension, replacing ChromaDB for deployments
that opt in to Postgres.

Cosine similarity is used for all queries (<=> operator).
"""

import logging
import uuid

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from grug.db.pg_models import ConversationHistoryEmbedding, DocumentChunkEmbedding
from grug.rag import embedder

logger = logging.getLogger(__name__)


class PGVectorStore:
    """VectorStore implementation backed by Postgres + pgvector."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    # ------------------------------------------------------------------
    # Document chunks
    # ------------------------------------------------------------------

    async def doc_upsert(
        self,
        guild_id: int,
        ids: list[str],
        texts: list[str],
        metadatas: list[dict],
    ) -> None:
        embeddings = embedder.embed(texts)
        async with self._session_factory() as session:
            for chunk_id, text_content, meta, embedding in zip(ids, texts, metadatas, embeddings):
                # Upsert: update if chunk_id already exists, otherwise insert.
                existing = await session.execute(
                    select(DocumentChunkEmbedding).where(
                        DocumentChunkEmbedding.chunk_id == chunk_id
                    )
                )
                row = existing.scalar_one_or_none()
                if row is None:
                    row = DocumentChunkEmbedding(
                        guild_id=guild_id,
                        chunk_id=chunk_id,
                        document_id=meta.get("document_id"),
                        filename=meta.get("filename", ""),
                        description=meta.get("description", ""),
                        chunk_index=meta.get("chunk_index", 0),
                        total_chunks=meta.get("total_chunks", 1),
                        content=text_content,
                        embedding=embedding,
                    )
                    session.add(row)
                else:
                    row.content = text_content
                    row.embedding = embedding
                    row.filename = meta.get("filename", row.filename)
                    row.description = meta.get("description", row.description)
            await session.commit()

    async def doc_query(
        self,
        guild_id: int,
        query: str,
        n_results: int,
        document_id: int | None = None,
    ) -> list[dict]:
        query_embedding = embedder.embed([query])[0]
        async with self._session_factory() as session:
            stmt = (
                select(DocumentChunkEmbedding)
                .where(DocumentChunkEmbedding.guild_id == guild_id)
                .order_by(DocumentChunkEmbedding.embedding.cosine_distance(query_embedding))
                .limit(n_results)
            )
            if document_id is not None:
                stmt = stmt.where(DocumentChunkEmbedding.document_id == document_id)
            result = await session.execute(stmt)
            rows = result.scalars().all()

        return [
            {
                "text": row.content,
                "filename": row.filename,
                "description": row.description,
                "chunk_index": row.chunk_index,
                # pgvector doesn't return raw distances here; use 0.0 as placeholder.
                "distance": 0.0,
            }
            for row in rows
        ]

    async def doc_get_ids(self, guild_id: int, document_id: int) -> list[str]:
        async with self._session_factory() as session:
            result = await session.execute(
                select(DocumentChunkEmbedding.chunk_id).where(
                    DocumentChunkEmbedding.guild_id == guild_id,
                    DocumentChunkEmbedding.document_id == document_id,
                )
            )
            return list(result.scalars().all())

    async def doc_delete(self, guild_id: int, ids: list[str]) -> None:
        if not ids:
            return
        async with self._session_factory() as session:
            await session.execute(
                delete(DocumentChunkEmbedding).where(
                    DocumentChunkEmbedding.chunk_id.in_(ids)
                )
            )
            await session.commit()

    async def guild_delete(self, guild_id: int) -> None:
        async with self._session_factory() as session:
            await session.execute(
                delete(DocumentChunkEmbedding).where(
                    DocumentChunkEmbedding.guild_id == guild_id
                )
            )
            await session.commit()

    # ------------------------------------------------------------------
    # History summaries
    # ------------------------------------------------------------------

    async def history_upsert(
        self,
        guild_id: int,
        id: str,
        summary: str,
        metadata: dict,
    ) -> None:
        embedding = embedder.embed([summary])[0]
        async with self._session_factory() as session:
            existing = await session.execute(
                select(ConversationHistoryEmbedding).where(
                    ConversationHistoryEmbedding.summary_id == id
                )
            )
            row = existing.scalar_one_or_none()
            if row is None:
                row = ConversationHistoryEmbedding(
                    guild_id=guild_id,
                    channel_id=metadata.get("channel_id"),
                    summary_id=id,
                    summary=summary,
                    message_count=metadata.get("message_count", 0),
                    start_time=str(metadata.get("start_time", "")),
                    end_time=str(metadata.get("end_time", "")),
                    embedding=embedding,
                )
                session.add(row)
            else:
                row.summary = summary
                row.embedding = embedding
                row.message_count = metadata.get("message_count", row.message_count)
                row.start_time = str(metadata.get("start_time", row.start_time))
                row.end_time = str(metadata.get("end_time", row.end_time))
            await session.commit()

    async def history_get(
        self,
        guild_id: int,
        channel_id: int,
    ) -> list[tuple[str, dict]]:
        async with self._session_factory() as session:
            result = await session.execute(
                select(ConversationHistoryEmbedding)
                .where(
                    ConversationHistoryEmbedding.guild_id == guild_id,
                    ConversationHistoryEmbedding.channel_id == channel_id,
                )
                .order_by(ConversationHistoryEmbedding.start_time.asc())
            )
            rows = result.scalars().all()

        return [
            (
                row.summary_id,
                {
                    "channel_id": row.channel_id,
                    "message_count": row.message_count,
                    "start_time": row.start_time,
                    "end_time": row.end_time,
                },
            )
            for row in rows
        ]

    async def history_delete(self, guild_id: int, ids: list[str]) -> None:
        if not ids:
            return
        async with self._session_factory() as session:
            await session.execute(
                delete(ConversationHistoryEmbedding).where(
                    ConversationHistoryEmbedding.summary_id.in_(ids)
                )
            )
            await session.commit()

    async def history_query(
        self,
        guild_id: int,
        channel_id: int,
        query: str,
        k: int,
    ) -> list[dict]:
        query_embedding = embedder.embed([query])[0]
        async with self._session_factory() as session:
            result = await session.execute(
                select(ConversationHistoryEmbedding)
                .where(
                    ConversationHistoryEmbedding.guild_id == guild_id,
                    ConversationHistoryEmbedding.channel_id == channel_id,
                )
                .order_by(
                    ConversationHistoryEmbedding.embedding.cosine_distance(query_embedding)
                )
                .limit(k)
            )
            rows = result.scalars().all()

        return [
            {
                "summary": row.summary,
                "start_time": row.start_time,
                "end_time": row.end_time,
                "message_count": row.message_count,
                "distance": 0.0,
            }
            for row in rows
        ]
