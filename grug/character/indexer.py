"""Character sheet indexing for RAG retrieval."""

import logging
import uuid

from grug.rag.vector_store import VectorStore, get_vector_store
from grug.utils import chunk_text

logger = logging.getLogger(__name__)

# Character sheets use smaller chunks so keyword queries land on the
# right section (e.g. "what are my spells" vs "what is my AC").
_CHAR_CHUNK_SIZE = 800
_CHAR_CHUNK_OVERLAP = 100


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

        chunks = chunk_text(
            raw_text, chunk_size=_CHAR_CHUNK_SIZE, overlap=_CHAR_CHUNK_OVERLAP
        )
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
