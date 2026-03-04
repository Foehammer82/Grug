"""Add allow_manual_dice_recording to campaigns.

Revision ID: 20260304_0009_campaign_allow_manual_dice
Revises: 20260304_0008_combat_depth
Create Date: 2026-03-04
"""

import sqlalchemy as sa
from alembic import op

revision: str = "20260304_0009_campaign_allow_manual_dice"
down_revision: str | None = "20260304_0008_combat_depth"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "campaigns",
        sa.Column(
            "allow_manual_dice_recording",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )


def downgrade() -> None:
    op.drop_column("campaigns", "allow_manual_dice_recording")
