"""Document indexing for RAG using ChromaDB."""

import logging
import re
import uuid
from pathlib import Path

import aiofiles
import chromadb

from grug.config.settings import get_settings

logger = logging.getLogger(__name__)

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200


def _collection_name(guild_id: int) -> str:
    """Return a stable ChromaDB collection name for a guild."""
    return f"guild_{guild_id}"


def _chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
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
    """Indexes text documents into ChromaDB for a guild."""

    def __init__(self) -> None:
        settings = get_settings()
        self._client = chromadb.PersistentClient(path=settings.chroma_persist_dir)

    def _get_collection(self, guild_id: int):
        # Uses ChromaDB's built-in default embedding function (all-MiniLM-L6-v2 via ONNX)
        return self._client.get_or_create_collection(name=_collection_name(guild_id))

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

        collection = self._get_collection(guild_id)
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
        collection.upsert(ids=ids, documents=chunks, metadatas=metadatas)
        logger.info("Indexed %d chunks from %s for guild %d", len(chunks), file_path.name, guild_id)
        return len(chunks)

    def delete_document(self, guild_id: int, document_id: int) -> None:
        """Remove all chunks belonging to a document."""
        collection = self._get_collection(guild_id)
        results = collection.get(where={"document_id": document_id})
        if results["ids"]:
            collection.delete(ids=results["ids"])

    def delete_guild_collection(self, guild_id: int) -> None:
        """Remove the entire collection for a guild."""
        name = _collection_name(guild_id)
        try:
            self._client.delete_collection(name)
        except Exception:
            pass
