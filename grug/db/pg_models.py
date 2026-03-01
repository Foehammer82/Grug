"""Postgres-specific ORM models for vector embeddings.

These tables only exist in Postgres deployments (pgvector backend).
They are intentionally kept in a separate module from grug/db/models.py
so the SQLite path never imports them and create_all stays clean.

Alembic migrations create these tables when DATABASE_URL is a Postgres URL.
"""

from pgvector.sqlalchemy import Vector
from sqlalchemy import BigInteger, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from grug.db.models import Base
from grug.rag.embedder import EMBEDDING_DIM


class DocumentChunkEmbedding(Base):
    """One chunk of an indexed document, stored with its embedding vector."""

    __tablename__ = "document_chunk_embeddings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    document_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    chunk_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True)  # UUID
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    total_chunks: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM), nullable=False)


class ConversationHistoryEmbedding(Base):
    """A summarised conversation history chunk, stored with its embedding vector."""

    __tablename__ = "conversation_history_embeddings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    channel_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    summary_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True)  # UUID
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    message_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    start_time: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    end_time: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM), nullable=False)
