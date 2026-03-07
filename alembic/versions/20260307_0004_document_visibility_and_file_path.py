"""Add is_public and file_path columns to documents table.

Revision ID: 20260307_0004_document_visibility_and_file_path
Revises: 20260307_0003_guild_allow_llm_model_override
Create Date: 2026-03-07
"""

from alembic import op
import sqlalchemy as sa

revision: str = "20260307_0004_document_visibility_and_file_path"
down_revision: str | None = "20260307_0003_guild_allow_llm_model_override"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column(
            "is_public",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )
    op.add_column(
        "documents",
        sa.Column("file_path", sa.String(1024), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("documents", "file_path")
    op.drop_column("documents", "is_public")
