"""Add pathbuilder_id column to characters for Pathbuilder 2e sync.

Revision ID: 20260303_0001_character_pathbuilder_id
Revises: 20260302_0002_document_content_hash
Create Date: 2026-03-03

Adds a nullable ``pathbuilder_id`` integer column to the ``characters``
table.  When set, the character's structured_data is synced from the
public Pathbuilder JSON endpoint instead of Claude extraction.
"""

import sqlalchemy as sa
from alembic import op

revision = "20260303_0001_character_pathbuilder_id"
down_revision = "20260302_0002_document_content_hash"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "characters",
        sa.Column("pathbuilder_id", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("characters", "pathbuilder_id")
