"""Add content_hash to documents for duplicate-upload detection.

Revision ID: 20260302_0002_document_content_hash
Revises: 20260302_0001_rule_source_sort_order
Create Date: 2026-03-02

Adds a ``content_hash`` column (SHA-256 hex, 64 chars) to the ``documents``
table and a partial unique index on ``(guild_id, content_hash) WHERE
content_hash IS NOT NULL`` so the database enforces that no guild can have
two documents with identical byte content.  Existing rows receive NULL
(not backfilled) and are excluded from the uniqueness constraint.
"""

import sqlalchemy as sa
from alembic import op

revision = "20260302_0002_document_content_hash"
down_revision = "20260302_0001_rule_source_sort_order"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column("content_hash", sa.String(64), nullable=True),
    )

    # Regular index for fast hash lookups.
    op.create_index(
        "ix_documents_content_hash",
        "documents",
        ["content_hash"],
    )

    # Partial unique index — NULL hashes (legacy rows) are excluded so they
    # never trigger false duplicate violations.
    op.execute(
        """
        CREATE UNIQUE INDEX uq_documents_guild_content_hash
        ON documents (guild_id, content_hash)
        WHERE content_hash IS NOT NULL
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_documents_guild_content_hash")
    op.drop_index("ix_documents_content_hash", table_name="documents")
    op.drop_column("documents", "content_hash")
