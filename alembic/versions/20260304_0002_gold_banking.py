"""Add gold banking: Campaign banking flags + party_gold, Character.gold, gold_transactions table.

Revision ID: 20260304_0002_gold_banking
Revises: 20260304_0001_campaign_gm
Create Date: 2026-03-04

Adds opt-in gold banking to campaigns:
- banking_enabled (master switch)
- player_banking_enabled (let players manage their own wallet + party pool)
- banking_ledger_enabled (record every transaction)
- party_gold (shared pool balance)

Adds gold wallet to characters:
- gold (personal balance)

Creates gold_transactions table for ledger mode.
"""

import sqlalchemy as sa
from alembic import op

revision: str = "20260304_0002_gold_banking"
down_revision = "20260304_0001_campaign_gm"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Campaign banking columns ──────────────────────────────────────────
    op.add_column(
        "campaigns",
        sa.Column(
            "banking_enabled",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )
    op.add_column(
        "campaigns",
        sa.Column(
            "player_banking_enabled",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )
    op.add_column(
        "campaigns",
        sa.Column(
            "banking_ledger_enabled",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )
    op.add_column(
        "campaigns",
        sa.Column(
            "party_gold",
            sa.Numeric(precision=12, scale=4),
            nullable=False,
            server_default="0",
        ),
    )

    # ── Character gold wallet ─────────────────────────────────────────────
    op.add_column(
        "characters",
        sa.Column(
            "gold",
            sa.Numeric(precision=12, scale=4),
            nullable=False,
            server_default="0",
        ),
    )

    # ── Gold transactions ledger table ────────────────────────────────────
    op.create_table(
        "gold_transactions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("campaign_id", sa.Integer(), nullable=False),
        sa.Column("character_id", sa.Integer(), nullable=True),
        sa.Column("actor_discord_user_id", sa.BigInteger(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["character_id"], ["characters.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_gold_transactions_campaign_id"),
        "gold_transactions",
        ["campaign_id"],
    )
    op.create_index(
        op.f("ix_gold_transactions_character_id"),
        "gold_transactions",
        ["character_id"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_gold_transactions_character_id"), table_name="gold_transactions"
    )
    op.drop_index(
        op.f("ix_gold_transactions_campaign_id"), table_name="gold_transactions"
    )
    op.drop_table("gold_transactions")
    op.drop_column("characters", "gold")
    op.drop_column("campaigns", "party_gold")
    op.drop_column("campaigns", "banking_ledger_enabled")
    op.drop_column("campaigns", "player_banking_enabled")
    op.drop_column("campaigns", "banking_enabled")
