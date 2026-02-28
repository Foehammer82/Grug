"""Document retrieval for RAG using ChromaDB."""

import logging

import chromadb

from grug.config.settings import get_settings

logger = logging.getLogger(__name__)


class DocumentRetriever:
    """Retrieves relevant document chunks from ChromaDB."""

    def __init__(self) -> None:
        settings = get_settings()
        self._client = chromadb.PersistentClient(path=settings.chroma_persist_dir)

    def _get_collection(self, guild_id: int):
        # Uses ChromaDB's built-in default embedding function (all-MiniLM-L6-v2 via ONNX)
        return self._client.get_or_create_collection(name=f"guild_{guild_id}")

    def search(
        self,
        guild_id: int,
        query: str,
        k: int = 5,
        document_id: int | None = None,
    ) -> list[dict]:
        """Return the top-k relevant chunks for *query*.

        Returns a list of dicts with keys: text, filename, chunk_index, distance.
        """
        collection = self._get_collection(guild_id)
        where = {"document_id": document_id} if document_id is not None else None
        try:
            results = collection.query(
                query_texts=[query],
                n_results=k,
                where=where,
                include=["documents", "metadatas", "distances"],
            )
        except Exception as exc:
            logger.warning("ChromaDB query failed: %s", exc)
            return []

        chunks: list[dict] = []
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            chunks.append(
                {
                    "text": doc,
                    "filename": meta.get("filename", "unknown"),
                    "description": meta.get("description", ""),
                    "chunk_index": meta.get("chunk_index", 0),
                    "distance": dist,
                }
            )
        return chunks
