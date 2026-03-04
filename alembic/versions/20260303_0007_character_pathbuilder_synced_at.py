"""Add pathbuilder_synced_at column to characters for sync cooldown tracking.

Revision ID: 20260303_0007_character_pathbuilder_synced_at
Revises: 20260303_0006_campaign_soft_delete
Create Date: 2026-03-03

Adds a nullable ``pathbuilder_synced_at`` timestamptz column to the
``characters`` table.  Populated after each successful Pathbuilder sync;
used to enforce a 5-minute global cooldown before re-fetching the same
character from the Pathbuilder API.
"""

import sqlalchemy as sa
from alembic import op

revision = "20260303_0007_character_pathbuilder_synced_at"
down_revision = "20260303_0006_campaign_soft_delete"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "characters",
        sa.Column("pathbuilder_synced_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("characters", "pathbuilder_synced_at")
