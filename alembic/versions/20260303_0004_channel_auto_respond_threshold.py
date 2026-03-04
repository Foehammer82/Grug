"""Replace always_respond with auto_respond + auto_respond_threshold on channel_configs.

Revision ID: 20260303_0004_channel_auto_respond_threshold
Revises: 20260303_0003_llm_usage_daily_aggregates
Create Date: 2026-03-03

``always_respond`` (BOOLEAN) is renamed to ``auto_respond`` and a new
``auto_respond_threshold`` (FLOAT) column is added.

Upgrade logic preserves data:
- Rows where ``always_respond = TRUE``  → ``auto_respond = TRUE,  threshold = 0.0``
  (threshold 0.0 means "always respond when auto-respond is on", matching old behaviour)
- Rows where ``always_respond = FALSE`` → ``auto_respond = FALSE, threshold = 0.0``
"""

import sqlalchemy as sa
from alembic import op

revision = "20260303_0004_channel_auto_respond_threshold"
down_revision = "20260303_0003_llm_usage_daily_aggregates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add the new threshold column first (nullable so we can populate it).
    op.add_column(
        "channel_configs",
        sa.Column(
            "auto_respond_threshold",
            sa.Float(),
            nullable=True,
        ),
    )
    # Populate: set threshold to 0.0 for all rows.
    op.execute("UPDATE channel_configs SET auto_respond_threshold = 0.0")

    # Rename the boolean column.
    op.alter_column(
        "channel_configs",
        "always_respond",
        new_column_name="auto_respond",
        existing_type=sa.Boolean(),
        existing_nullable=False,
        existing_server_default="false",
    )

    # Tighten: make threshold non-nullable with a server default.
    op.alter_column(
        "channel_configs",
        "auto_respond_threshold",
        nullable=False,
        server_default="0.5",
    )


def downgrade() -> None:
    op.drop_column("channel_configs", "auto_respond_threshold")
    op.alter_column(
        "channel_configs",
        "auto_respond",
        new_column_name="always_respond",
        existing_type=sa.Boolean(),
        existing_nullable=False,
        existing_server_default="false",
    )
