"""add_channel_context_awareness

Add ChannelConfig table plus context_cutoff and is_passive columns to support
passive message logging and per-channel / per-guild context cutoff settings.

Revision ID: 20260301_channel_ctx
Revises: 20260301_events_rrule
Create Date: 2026-03-01
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260301_channel_ctx"
down_revision: Union[str, None] = "20260301_events_rrule"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- guild_configs: global context cutoff ---
    op.add_column(
        "guild_configs",
        sa.Column("context_cutoff", sa.DateTime(timezone=True), nullable=True),
    )

    # --- channel_configs: per-channel overrides (always_respond + cutoff) ---
    op.create_table(
        "channel_configs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("channel_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "always_respond",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
        sa.Column("context_cutoff", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["guild_id"],
            ["guild_configs.guild_id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_channel_configs_guild_id"), "channel_configs", ["guild_id"]
    )
    op.create_index(
        op.f("ix_channel_configs_channel_id"),
        "channel_configs",
        ["channel_id"],
        unique=True,
    )

    # --- user_profiles: per-user DM context cutoff ---
    op.add_column(
        "user_profiles",
        sa.Column("dm_context_cutoff", sa.DateTime(timezone=True), nullable=True),
    )

    # --- conversation_messages: passive message flag ---
    op.add_column(
        "conversation_messages",
        sa.Column(
            "is_passive",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )


def downgrade() -> None:
    op.drop_column("conversation_messages", "is_passive")
    op.drop_column("user_profiles", "dm_context_cutoff")
    op.drop_index(op.f("ix_channel_configs_channel_id"), table_name="channel_configs")
    op.drop_index(op.f("ix_channel_configs_guild_id"), table_name="channel_configs")
    op.drop_table("channel_configs")
    op.drop_column("guild_configs", "context_cutoff")
