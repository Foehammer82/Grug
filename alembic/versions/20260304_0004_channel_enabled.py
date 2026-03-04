"""Add enabled column to channel_configs

Revision ID: 20260304_0004_channel_enabled
Revises: 20260304_0003_session_notes
Create Date: 2026-03-04 12:00:00.000000

Grandfathers in two sets of existing channels:
  1. Any row where auto_respond=TRUE (already invited for active use).
  2. The announce_channel_id for each guild (the default bot channel).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260304_0004_channel_enabled"
down_revision: Union[str, None] = "20260304_0003_session_notes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add the enabled column — default FALSE so unknown channels stay silent.
    op.add_column(
        "channel_configs",
        sa.Column(
            "enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )

    # Grandfather 1: channels that are already actively responding.
    op.execute(
        "UPDATE channel_configs SET enabled = TRUE WHERE auto_respond = TRUE"
    )

    # Grandfather 2: the guild's default announce channel (if one is set and a
    # ChannelConfig row already exists for it).
    op.execute(
        """
        UPDATE channel_configs
        SET enabled = TRUE
        WHERE channel_id IN (
            SELECT announce_channel_id
            FROM guild_configs
            WHERE announce_channel_id IS NOT NULL
        )
        """
    )

    # Grandfather 3: ensure every guild's announce_channel_id has an enabled row
    # even if no ChannelConfig row existed for it yet.
    op.execute(
        """
        INSERT INTO channel_configs (guild_id, channel_id, enabled, auto_respond, auto_respond_threshold, created_at, updated_at)
        SELECT
            gc.guild_id,
            gc.announce_channel_id,
            TRUE,
            FALSE,
            0.5,
            NOW(),
            NOW()
        FROM guild_configs gc
        WHERE gc.announce_channel_id IS NOT NULL
          AND NOT EXISTS (
              SELECT 1
              FROM channel_configs cc
              WHERE cc.channel_id = gc.announce_channel_id
          )
        """
    )


def downgrade() -> None:
    op.drop_column("channel_configs", "enabled")
