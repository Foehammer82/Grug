"""llm_usage_daily_aggregates

Revision ID: 20260303_0003_llm_usage_daily_aggregates
Revises: 20260303_0002_remove_guild_context_cutoff
Create Date: 2026-03-03

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260303_0003_llm_usage_daily_aggregates"
down_revision: str | None = "20260303_0002_remove_guild_context_cutoff"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "llm_usage_daily_aggregates",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("guild_id", sa.BigInteger(), nullable=True),
        sa.Column("user_id", sa.BigInteger(), nullable=True),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("call_type", sa.String(length=64), nullable=False),
        sa.Column("request_count", sa.Integer(), nullable=False),
        sa.Column("input_tokens", sa.BigInteger(), nullable=False),
        sa.Column("output_tokens", sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "date",
            "guild_id",
            "user_id",
            "model",
            "call_type",
            name="uq_llm_usage_daily",
        ),
    )
    op.create_index(
        op.f("ix_llm_usage_daily_aggregates_date"),
        "llm_usage_daily_aggregates",
        ["date"],
        unique=False,
    )
    op.create_index(
        op.f("ix_llm_usage_daily_aggregates_guild_id"),
        "llm_usage_daily_aggregates",
        ["guild_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_llm_usage_daily_aggregates_guild_id"),
        table_name="llm_usage_daily_aggregates",
    )
    op.drop_index(
        op.f("ix_llm_usage_daily_aggregates_date"),
        table_name="llm_usage_daily_aggregates",
    )
    op.drop_table("llm_usage_daily_aggregates")
