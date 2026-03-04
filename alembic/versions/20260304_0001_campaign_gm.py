"""Add gm_discord_user_id to campaigns table.

Revision ID: 20260304_0001_campaign_gm
Revises: fb0301ba2bd8
Create Date: 2026-03-04

Assigns a Game Master (GM) to a campaign.  The GM gets full read access to
all character sheets in that campaign — equivalent to a guild admin but
scoped to a single campaign only.
"""

import sqlalchemy as sa
from alembic import op

revision: str = "20260304_0001_campaign_gm"
down_revision = "fb0301ba2bd8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "campaigns",
        sa.Column("gm_discord_user_id", sa.BigInteger(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("campaigns", "gm_discord_user_id")
