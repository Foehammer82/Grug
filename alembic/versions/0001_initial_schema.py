"""Initial schema — all tables for a fresh Postgres deployment.

Revision ID: 0001
Revises: —
Create Date: 2026-02-28

Creates the complete application schema including:
- pgvector extension
- All standard relational tables (matching grug/db/models.py)
- Vector embedding tables (document_chunk_embeddings, conversation_history_embeddings)
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

from grug.rag.embedder import EMBEDDING_DIM

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable pgvector — safe to run repeatedly.
    op.execute(sa.text("CREATE EXTENSION IF NOT EXISTS vector"))

    # ------------------------------------------------------------------
    # Standard relational tables
    # ------------------------------------------------------------------
    op.create_table(
        "guild_configs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("prefix", sa.String(10), nullable=False, server_default="!"),
        sa.Column("timezone", sa.String(64), nullable=False, server_default="UTC"),
        sa.Column("announce_channel_id", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("guild_id"),
    )
    op.create_index("ix_guild_configs_guild_id", "guild_configs", ["guild_id"])

    op.create_table(
        "documents",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("filename", sa.String(512), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("chroma_collection", sa.String(256), nullable=False),
        sa.Column("chunk_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("uploaded_by", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_documents_guild_id", "documents", ["guild_id"])

    op.create_table(
        "calendar_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("title", sa.String(256), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("channel_id", sa.BigInteger(), nullable=True),
        sa.Column("created_by", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["guild_id"], ["guild_configs.guild_id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_calendar_events_guild_id", "calendar_events", ["guild_id"])

    op.create_table(
        "reminders",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("channel_id", sa.BigInteger(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("remind_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sent", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["guild_id"], ["guild_configs.guild_id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_reminders_guild_id", "reminders", ["guild_id"])
    op.create_index("ix_reminders_user_id", "reminders", ["user_id"])

    op.create_table(
        "scheduled_tasks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("channel_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("cron_expression", sa.String(128), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_run", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["guild_id"], ["guild_configs.guild_id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scheduled_tasks_guild_id", "scheduled_tasks", ["guild_id"])

    op.create_table(
        "conversation_messages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("channel_id", sa.BigInteger(), nullable=False),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("author_id", sa.BigInteger(), nullable=True),
        sa.Column("author_name", sa.String(256), nullable=True),
        sa.Column("archived", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_conversation_messages_guild_id", "conversation_messages", ["guild_id"]
    )
    op.create_index(
        "ix_conversation_messages_channel_id", "conversation_messages", ["channel_id"]
    )

    # ------------------------------------------------------------------
    # Vector embedding tables (pgvector-only)
    # ------------------------------------------------------------------
    op.create_table(
        "document_chunk_embeddings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("chunk_id", sa.String(36), nullable=False),
        sa.Column("filename", sa.String(512), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("total_chunks", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("chunk_id"),
    )
    op.create_index(
        "ix_doc_chunk_embeddings_guild_id", "document_chunk_embeddings", ["guild_id"]
    )
    op.create_index(
        "ix_doc_chunk_embeddings_document_id",
        "document_chunk_embeddings",
        ["document_id"],
    )
    # IVFFlat cosine index — speeds up nearest-neighbour search.
    op.execute(
        sa.text(
            "CREATE INDEX ix_doc_chunk_embeddings_vector "
            "ON document_chunk_embeddings "
            "USING ivfflat (embedding vector_cosine_ops) "
            "WITH (lists = 100)"
        )
    )

    op.create_table(
        "conversation_history_embeddings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("channel_id", sa.BigInteger(), nullable=False),
        sa.Column("summary_id", sa.String(36), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("message_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("start_time", sa.String(64), nullable=False, server_default=""),
        sa.Column("end_time", sa.String(64), nullable=False, server_default=""),
        sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("summary_id"),
    )
    op.create_index(
        "ix_conv_history_embeddings_guild_id",
        "conversation_history_embeddings",
        ["guild_id"],
    )
    op.create_index(
        "ix_conv_history_embeddings_channel_id",
        "conversation_history_embeddings",
        ["channel_id"],
    )
    op.execute(
        sa.text(
            "CREATE INDEX ix_conv_history_embeddings_vector "
            "ON conversation_history_embeddings "
            "USING ivfflat (embedding vector_cosine_ops) "
            "WITH (lists = 100)"
        )
    )


def downgrade() -> None:
    op.drop_table("conversation_history_embeddings")
    op.drop_table("document_chunk_embeddings")
    op.drop_table("conversation_messages")
    op.drop_table("scheduled_tasks")
    op.drop_table("reminders")
    op.drop_table("calendar_events")
    op.drop_table("documents")
    op.drop_table("guild_configs")
    op.execute(sa.text("DROP EXTENSION IF EXISTS vector"))
