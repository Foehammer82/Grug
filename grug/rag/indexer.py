"""Document indexing for RAG — backend-agnostic via VectorStore."""

import logging
import re
import uuid
from pathlib import Path

import aiofiles

from grug.rag.vector_store import VectorStore, get_vector_store

logger = logging.getLogger(__name__)

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200


def _chunk_text(
    text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP
) -> list[str]:
    """Split text into overlapping chunks."""
    # Normalise whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)
    if not text:
        return []
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunks.append(text[start:end])
        if end == len(text):
            break
        start += chunk_size - overlap
    return chunks


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

        chunks = _chunk_text(text)
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
