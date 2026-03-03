"""Remove context_cutoff columns from guild_configs and channel_configs.

Revision ID: 20260303_0002_remove_guild_context_cutoff
Revises: 20260303_0001_character_pathbuilder_id
Create Date: 2026-03-03

The per-guild and per-channel context cutoff overrides have been replaced by a
single rolling lookback window configured via the ``AGENT_CONTEXT_LOOKBACK_DAYS``
environment variable (default 30 days).  The per-user DM cutoff
(``user_profiles.dm_context_cutoff``) is unchanged.
"""

import sqlalchemy as sa
from alembic import op

revision = "20260303_0002_remove_guild_context_cutoff"
down_revision = "20260303_0001_character_pathbuilder_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("guild_configs", "context_cutoff")
    op.drop_column("channel_configs", "context_cutoff")


def downgrade() -> None:
    op.add_column(
        "guild_configs",
        sa.Column(
            "context_cutoff",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "channel_configs",
        sa.Column(
            "context_cutoff",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
