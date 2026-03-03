"""Add llm_usage_records table for sub-daily (hourly) usage reporting.

Revision ID: 20260303_0005_llm_usage_records
Revises: 20260303_0004_channel_auto_respond_threshold
Create Date: 2026-03-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260303_0005_llm_usage_records"
down_revision: str | None = "20260303_0004_channel_auto_respond_threshold"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "llm_usage_records",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column("guild_id", sa.BigInteger(), nullable=True),
        sa.Column("user_id", sa.BigInteger(), nullable=True),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("call_type", sa.String(length=64), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_llm_usage_records_created_at"),
        "llm_usage_records",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_llm_usage_records_created_at"),
        table_name="llm_usage_records",
    )
    op.drop_table("llm_usage_records")
