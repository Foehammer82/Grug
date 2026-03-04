"""Add session_notes table for per-campaign session log entries.

Revision ID: 20260304_0003_session_notes
Revises: 20260304_0002_gold_banking
Create Date: 2026-03-04

Creates the ``session_notes`` table which stores raw and LLM-synthesized
session notes scoped to a campaign.  Each note has a synthesis lifecycle
(pending → processing → done/failed) and a back-reference to the RAG
Document entry created when synthesis completes.
"""

import sqlalchemy as sa
from alembic import op

revision: str = "20260304_0003_session_notes"
down_revision = "20260304_0002_gold_banking"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "session_notes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("campaign_id", sa.Integer(), sa.ForeignKey("campaigns.id"), nullable=False),
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("session_date", sa.Date(), nullable=True),
        sa.Column("title", sa.String(256), nullable=True),
        sa.Column("raw_notes", sa.Text(), nullable=False),
        sa.Column("clean_notes", sa.Text(), nullable=True),
        sa.Column(
            "synthesis_status",
            sa.String(32),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("synthesis_error", sa.Text(), nullable=True),
        sa.Column("rag_document_id", sa.Integer(), nullable=True),
        sa.Column("submitted_by", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_session_notes_campaign_id", "session_notes", ["campaign_id"])
    op.create_index("ix_session_notes_guild_id", "session_notes", ["guild_id"])
    op.create_index("ix_session_notes_rag_document_id", "session_notes", ["rag_document_id"])


def downgrade() -> None:
    op.drop_index("ix_session_notes_rag_document_id", "session_notes")
    op.drop_index("ix_session_notes_guild_id", "session_notes")
    op.drop_index("ix_session_notes_campaign_id", "session_notes")
    op.drop_table("session_notes")
