"""manager_agent_models

Creates the tables for the manager agent feature:
- user_feedback: user ratings on Grug's responses
- instruction_overrides: custom per-guild prompt overrides
- manager_reviews: batch review results from the manager agent

Revision ID: 20260307_0002_manager_agent_models
Revises: 20260307_0001_scheduled_task_timezone
Create Date: 2026-03-07
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260307_0002_manager_agent_models"
down_revision: Union[str, None] = "20260307_0001_scheduled_task_timezone"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -- manager_reviews (created first since instruction_overrides references it)
    op.create_table(
        "manager_reviews",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "guild_id",
            sa.BigInteger(),
            sa.ForeignKey("guild_configs.guild_id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "messages_reviewed",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "feedback_reviewed",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("observations", sa.JSON(), nullable=True),
        sa.Column("recommendations", sa.JSON(), nullable=True),
        sa.Column(
            "webhook_sent",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "started_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column(
            "completed_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # -- user_feedback
    op.create_table(
        "user_feedback",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("guild_id", sa.BigInteger(), nullable=False, index=True),
        sa.Column("channel_id", sa.BigInteger(), nullable=False, index=True),
        sa.Column(
            "message_id",
            sa.Integer(),
            sa.ForeignKey("conversation_messages.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "discord_user_id", sa.BigInteger(), nullable=False, index=True
        ),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "message_id",
            "discord_user_id",
            name="uq_user_feedback_msg_user",
        ),
    )

    # -- instruction_overrides
    op.create_table(
        "instruction_overrides",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "guild_id",
            sa.BigInteger(),
            sa.ForeignKey("guild_configs.guild_id"),
            nullable=False,
            index=True,
        ),
        sa.Column("channel_id", sa.BigInteger(), nullable=True, index=True),
        sa.Column(
            "scope",
            sa.String(length=16),
            nullable=False,
            server_default="guild",
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default="active",
        ),
        sa.Column(
            "source",
            sa.String(length=16),
            nullable=False,
            server_default="admin",
        ),
        sa.Column(
            "review_id",
            sa.Integer(),
            sa.ForeignKey("manager_reviews.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_by", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("instruction_overrides")
    op.drop_table("user_feedback")
    op.drop_table("manager_reviews")
