"""Add sort_order to rule_sources for priority ranking.

Revision ID: 20260302_0001_rule_source_sort_order
Revises: 20260303_0000_initial_schema
Create Date: 2026-03-02

Adds a ``sort_order`` integer column to ``rule_sources`` so guild admins can
rank their custom rule sources.  Built-in sources always run before custom
sources; this column controls ordering *within* the custom sources group.

Existing rows are assigned sort_orders 0, 10, 20, … per guild (ordered by
``created_at``) so they retain their original relative order.
"""

import sqlalchemy as sa
from alembic import op

revision = "20260302_0001_rule_source_sort_order"
down_revision = "20260303_0000_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Widen alembic_version.version_num — the default VARCHAR(32) is too short for this revision ID.
    op.execute("ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(64)")

    # Add column — nullable first so existing rows get NULL, then backfill, then enforce NOT NULL.
    op.add_column(
        "rule_sources",
        sa.Column("sort_order", sa.Integer(), nullable=True),
    )

    # Backfill: assign 0, 10, 20, … per guild ordered by created_at.
    op.execute(
        """
        UPDATE rule_sources
        SET sort_order = ranked.rn * 10
        FROM (
            SELECT id,
                   ROW_NUMBER() OVER (PARTITION BY guild_id ORDER BY created_at) - 1 AS rn
            FROM rule_sources
        ) AS ranked
        WHERE rule_sources.id = ranked.id
        """
    )

    # Set NOT NULL now that all rows have a value.
    op.alter_column("rule_sources", "sort_order", nullable=False)


def downgrade() -> None:
    op.drop_column("rule_sources", "sort_order")
