"""ChromaDB vector store backend.

Wraps the three existing ChromaDB usage patterns (document chunks, guild
deletion, history summaries) behind the VectorStore protocol so the rest of
the application never imports chromadb directly.

All ChromaDB calls are synchronous under the hood; they are dispatched to a
thread pool via asyncio.to_thread so the event loop is never blocked.
"""

import asyncio
import logging

import chromadb

from grug.rag import embedder

logger = logging.getLogger(__name__)

_HISTORY_SUFFIX = "_history"


def _collection_name(guild_id: int) -> str:
    return f"guild_{guild_id}"


def _history_collection_name(guild_id: int) -> str:
    return f"guild_{guild_id}{_HISTORY_SUFFIX}"


def _character_collection_name(character_id: int) -> str:
    return f"character_{character_id}"


class ChromaVectorStore:
    """VectorStore implementation backed by an embedded ChromaDB instance."""

    def __init__(self, persist_dir: str) -> None:
        self._persist_dir = persist_dir
        # Client is created lazily so tests can patch the directory.
        self._client: chromadb.PersistentClient | None = None

    def _get_client(self) -> chromadb.PersistentClient:
        if self._client is None:
            self._client = chromadb.PersistentClient(path=self._persist_dir)
        return self._client

    def _doc_collection(self, guild_id: int):
        return self._get_client().get_or_create_collection(
            name=_collection_name(guild_id)
        )

    def _history_collection(self, guild_id: int):
        return self._get_client().get_or_create_collection(
            name=_history_collection_name(guild_id)
        )

    def _character_collection(self, character_id: int):
        return self._get_client().get_or_create_collection(
            name=_character_collection_name(character_id)
        )

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
        def _sync():
            col = self._doc_collection(guild_id)
            # Provide explicit embeddings so the same model is used as pgvector.
            embeddings = embedder.embed(texts)
            col.upsert(
                ids=ids, documents=texts, metadatas=metadatas, embeddings=embeddings
            )

        await asyncio.to_thread(_sync)

    async def doc_query(
        self,
        guild_id: int,
        query: str,
        n_results: int,
        document_id: int | None = None,
    ) -> list[dict]:
        def _sync():
            col = self._doc_collection(guild_id)
            where = {"document_id": document_id} if document_id is not None else None
            query_embedding = embedder.embed([query])[0]
            try:
                results = col.query(
                    query_embeddings=[query_embedding],
                    n_results=n_results,
                    where=where,
                    include=["documents", "metadatas", "distances"],
                )
            except Exception as exc:
                logger.warning("ChromaDB doc query failed: %s", exc)
                return []
            chunks = []
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

        return await asyncio.to_thread(_sync)

    async def doc_get_ids(self, guild_id: int, document_id: int) -> list[str]:
        def _sync():
            col = self._doc_collection(guild_id)
            results = col.get(where={"document_id": document_id})
            return results["ids"]

        return await asyncio.to_thread(_sync)

    async def doc_delete(self, guild_id: int, ids: list[str]) -> None:
        if not ids:
            return

        def _sync():
            col = self._doc_collection(guild_id)
            col.delete(ids=ids)

        await asyncio.to_thread(_sync)

    async def guild_delete(self, guild_id: int) -> None:
        def _sync():
            name = _collection_name(guild_id)
            try:
                self._get_client().delete_collection(name)
            except Exception:
                pass

        await asyncio.to_thread(_sync)

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
        def _sync():
            col = self._history_collection(guild_id)
            embedding = embedder.embed([summary])[0]
            col.upsert(
                ids=[id],
                documents=[summary],
                metadatas=[metadata],
                embeddings=[embedding],
            )

        await asyncio.to_thread(_sync)

    async def history_get(
        self,
        guild_id: int,
        channel_id: int,
    ) -> list[tuple[str, dict]]:
        def _sync():
            col = self._history_collection(guild_id)
            results = col.get(where={"channel_id": channel_id}, include=["metadatas"])
            return list(zip(results["ids"], results["metadatas"]))

        return await asyncio.to_thread(_sync)

    async def history_delete(self, guild_id: int, ids: list[str]) -> None:
        if not ids:
            return

        def _sync():
            col = self._history_collection(guild_id)
            col.delete(ids=ids)

        await asyncio.to_thread(_sync)

    async def history_query(
        self,
        guild_id: int,
        channel_id: int,
        query: str,
        k: int,
    ) -> list[dict]:
        def _sync():
            col = self._history_collection(guild_id)
            query_embedding = embedder.embed([query])[0]
            try:
                results = col.query(
                    query_embeddings=[query_embedding],
                    n_results=k,
                    where={"channel_id": channel_id},
                    include=["documents", "metadatas", "distances"],
                )
            except Exception as exc:
                logger.warning("ChromaDB history query failed: %s", exc)
                return []
            summaries = []
            for doc, meta, dist in zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0],
            ):
                summaries.append(
                    {
                        "summary": doc,
                        "start_time": meta.get("start_time", ""),
                        "end_time": meta.get("end_time", ""),
                        "message_count": meta.get("message_count", 0),
                        "distance": dist,
                    }
                )
            return summaries

        return await asyncio.to_thread(_sync)

    # ------------------------------------------------------------------
    # Character sheets
    # ------------------------------------------------------------------

    async def character_upsert(
        self,
        character_id: int,
        ids: list[str],
        texts: list[str],
        metadatas: list[dict],
    ) -> None:
        def _sync():
            col = self._character_collection(character_id)
            embeddings = embedder.embed(texts)
            col.upsert(
                ids=ids, documents=texts, metadatas=metadatas, embeddings=embeddings
            )

        await asyncio.to_thread(_sync)

    async def character_query(
        self,
        character_id: int,
        query: str,
        n_results: int,
    ) -> list[dict]:
        def _sync():
            col = self._character_collection(character_id)
            query_embedding = embedder.embed([query])[0]
            try:
                results = col.query(
                    query_embeddings=[query_embedding],
                    n_results=n_results,
                    include=["documents", "metadatas", "distances"],
                )
            except Exception as exc:
                logger.warning("ChromaDB character query failed: %s", exc)
                return []
            chunks = []
            for doc, meta, dist in zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0],
            ):
                chunks.append(
                    {
                        "text": doc,
                        "chunk_index": meta.get("chunk_index", 0),
                        "distance": dist,
                    }
                )
            return chunks

        return await asyncio.to_thread(_sync)

    async def character_delete_all(self, character_id: int) -> None:
        def _sync():
            name = _character_collection_name(character_id)
            try:
                self._get_client().delete_collection(name)
            except Exception:
                pass

        await asyncio.to_thread(_sync)
