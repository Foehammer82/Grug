"""Add grug_notes table for Grug's self-maintained notes.

Revision ID: 20260304_0000_grug_notes
Revises: 20260303_0008_character_owner_nullable_and_notes
Create Date: 2026-03-04

Two scopes: guild notes (guild_id set, user_id NULL) and personal notes
(user_id set, guild_id NULL).  Content is Markdown.
"""

import sqlalchemy as sa
from alembic import op

revision: str = "20260304_0000_grug_notes"
down_revision = "20260303_0008_character_owner_nullable_and_notes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "grug_notes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("guild_id", sa.BigInteger(), nullable=True),
        sa.Column("user_id", sa.BigInteger(), nullable=True),
        sa.Column("content", sa.Text(), nullable=False, server_default=""),
        sa.Column("updated_by", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_grug_notes_guild_id", "grug_notes", ["guild_id"])
    op.create_index("ix_grug_notes_user_id", "grug_notes", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_grug_notes_user_id", table_name="grug_notes")
    op.drop_index("ix_grug_notes_guild_id", table_name="grug_notes")
    op.drop_table("grug_notes")
