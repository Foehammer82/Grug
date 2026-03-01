"""Document indexing for RAG — backend-agnostic via VectorStore."""

import logging
import uuid
from pathlib import Path

import aiofiles

from grug.rag.vector_store import VectorStore, get_vector_store
from grug.utils import chunk_text

logger = logging.getLogger(__name__)


class DocumentIndexer:
    """Indexes text documents into the configured vector store for a guild."""

    def __init__(self, store: VectorStore | None = None) -> None:
        self._store = store or get_vector_store()

    async def index_file(
        self,
        guild_id: int,
        file_path: Path,
        document_id: int,
        description: str | None = None,
    ) -> int:
        """Index a text file and return the number of chunks stored."""
        async with aiofiles.open(file_path, encoding="utf-8", errors="replace") as f:
            text = await f.read()

        chunks = chunk_text(text)
        if not chunks:
            return 0

        ids = [str(uuid.uuid4()) for _ in chunks]
        metadatas = [
            {
                "document_id": document_id,
                "filename": file_path.name,
                "description": description or "",
                "chunk_index": i,
                "total_chunks": len(chunks),
            }
            for i, _ in enumerate(chunks)
        ]
        await self._store.doc_upsert(guild_id, ids, chunks, metadatas)
        logger.info(
            "Indexed %d chunks from %s for guild %d",
            len(chunks),
            file_path.name,
            guild_id,
        )
        return len(chunks)

    async def delete_document(self, guild_id: int, document_id: int) -> None:
        """Remove all chunks belonging to a document."""
        ids = await self._store.doc_get_ids(guild_id, document_id)
        if ids:
            await self._store.doc_delete(guild_id, ids)

    async def delete_guild_collection(self, guild_id: int) -> None:
        """Remove all document chunks for an entire guild."""
        await self._store.guild_delete(guild_id)
