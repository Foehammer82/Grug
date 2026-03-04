"""Add is_hidden column to combatants

Revision ID: 20260304_0010_combatant_hidden
Revises: 20260304_0009_campaign_allow_manual_dice
Create Date: 2026-03-04
"""

import sqlalchemy as sa
from alembic import op

revision: str = "20260304_0010_combatant_hidden"
down_revision: str | None = "20260304_0009_campaign_allow_manual_dice"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # -- Combatant: is_hidden -------------------------------------------------
    # Hidden combatants are only visible to the GM; players never see them.
    op.add_column(
        "combatants",
        sa.Column(
            "is_hidden",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )


def downgrade() -> None:
    op.drop_column("combatants", "is_hidden")
