"""Character sheet indexing for RAG retrieval."""

import logging
import uuid

from grug.rag.vector_store import VectorStore, get_vector_store

logger = logging.getLogger(__name__)

# Characters are chunked into smaller sections so keyword queries land on
# the right part of the sheet (e.g. "what are my spells" vs "what is my AC").
_CHUNK_SIZE = 800
_CHUNK_OVERLAP = 100


def _chunk_text(text: str) -> list[str]:
    if not text:
        return []
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + _CHUNK_SIZE, len(text))
        chunks.append(text[start:end])
        if end == len(text):
            break
        start += _CHUNK_SIZE - _CHUNK_OVERLAP
    return chunks


class CharacterIndexer:
    """Indexes character sheet text into a per-character vector store collection."""

    def __init__(self, store: VectorStore | None = None) -> None:
        self._store = store or get_vector_store()

    async def index_character(
        self,
        character_id: int,
        raw_text: str,
    ) -> int:
        """Index the character's raw sheet text; returns chunk count."""
        # Clear any previous index for this character (handles re-uploads).
        await self._store.character_delete_all(character_id)

        chunks = _chunk_text(raw_text)
        if not chunks:
            return 0

        ids = [str(uuid.uuid4()) for _ in chunks]
        metadatas = [
            {
                "character_id": character_id,
                "chunk_index": i,
                "total_chunks": len(chunks),
            }
            for i in range(len(chunks))
        ]
        await self._store.character_upsert(character_id, ids, chunks, metadatas)
        logger.info("Indexed %d chunks for character %d", len(chunks), character_id)
        return len(chunks)

    async def delete_character(self, character_id: int) -> None:
        """Remove all indexed chunks for a character."""
        await self._store.character_delete_all(character_id)
