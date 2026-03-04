"""Make owner_discord_user_id nullable, add owner_display_name and notes.

Revision ID: 20260303_0008_character_owner_nullable_and_notes
Revises: 20260303_0007_character_pathbuilder_synced_at
Create Date: 2026-03-03

Allows characters to exist without a Discord owner (for NPCs or non-Discord
players).  Adds ``owner_display_name`` (free-form fallback shown when no
Discord owner is set) and ``notes`` (private text visible only to the
character owner and guild admins).
"""

import sqlalchemy as sa
from alembic import op

revision: str = "20260303_0008_character_owner_nullable_and_notes"
down_revision = "20260303_0007_character_pathbuilder_synced_at"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Allow null owner — for NPCs and non-Discord players.
    op.alter_column(
        "characters",
        "owner_discord_user_id",
        existing_type=sa.BigInteger(),
        nullable=True,
    )
    op.add_column(
        "characters",
        sa.Column("owner_display_name", sa.String(256), nullable=True),
    )
    op.add_column(
        "characters",
        sa.Column("notes", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("characters", "notes")
    op.drop_column("characters", "owner_display_name")
    # Restore NOT NULL — set any null owner rows to 0 first.
    op.execute(
        "UPDATE characters SET owner_discord_user_id = 0 WHERE owner_discord_user_id IS NULL"
    )
    op.alter_column(
        "characters",
        "owner_discord_user_id",
        existing_type=sa.BigInteger(),
        nullable=False,
    )
