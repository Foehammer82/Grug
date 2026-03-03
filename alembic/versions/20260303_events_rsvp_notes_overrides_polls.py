"""Add event RSVP, notes, occurrence overrides, and availability polls tables.

Revision ID: 20260303_events_features
Revises: 20260302_is_super_admin
Create Date: 2026-03-03
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260303_events_features"
down_revision: Union[str, None] = "20260302_is_super_admin"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "event_rsvps",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "event_id",
            sa.Integer(),
            sa.ForeignKey("calendar_events.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("discord_user_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("event_id", "discord_user_id", name="uq_event_rsvp"),
    )

    op.create_table(
        "event_notes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "event_id",
            sa.Integer(),
            sa.ForeignKey("calendar_events.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "done",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("created_by", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_table(
        "event_occurrence_overrides",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "event_id",
            sa.Integer(),
            sa.ForeignKey("calendar_events.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("original_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("new_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("new_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "cancelled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "event_id", "original_start", name="uq_event_occurrence_override"
        ),
    )

    op.create_table(
        "availability_polls",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "guild_id",
            sa.BigInteger(),
            sa.ForeignKey("guild_configs.guild_id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "event_id",
            sa.Integer(),
            sa.ForeignKey("calendar_events.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column("title", sa.String(256), nullable=False),
        sa.Column("options", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("closes_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("winner_option_id", sa.Integer(), nullable=True),
        sa.Column("created_by", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_table(
        "poll_votes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "poll_id",
            sa.Integer(),
            sa.ForeignKey("availability_polls.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("discord_user_id", sa.BigInteger(), nullable=False),
        sa.Column("option_ids", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("poll_id", "discord_user_id", name="uq_poll_vote"),
    )


def downgrade() -> None:
    op.drop_table("poll_votes")
    op.drop_table("availability_polls")
    op.drop_table("event_occurrence_overrides")
    op.drop_table("event_notes")
    op.drop_table("event_rsvps")
