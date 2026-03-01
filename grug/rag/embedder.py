"""Shared text embedder for all RAG backends.

Uses ChromaDB's built-in ONNX model (all-MiniLM-L6-v2, 384 dimensions) so
both the Chroma and pgvector backends produce identical vectors for the same
input — embeddings stored by one remain valid if you migrate to the other.

The model is loaded once and cached; subsequent calls are fast.
"""

import logging
from functools import lru_cache

logger = logging.getLogger(__name__)

EMBEDDING_DIM = 384  # all-MiniLM-L6-v2 output dimension


@lru_cache(maxsize=1)
def _get_ef():
    """Return the cached ChromaDB default embedding function."""
    from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

    logger.info("Loading all-MiniLM-L6-v2 embedding model (one-time load)...")
    return DefaultEmbeddingFunction()


def embed(texts: list[str]) -> list[list[float]]:
    """Embed a list of texts. Returns a list of 384-dim float vectors."""
    if not texts:
        return []
    ef = _get_ef()
    result = ef(texts)
    # DefaultEmbeddingFunction returns numpy arrays or lists; normalise to list[list[float]].
    return [list(map(float, vec)) for vec in result]
