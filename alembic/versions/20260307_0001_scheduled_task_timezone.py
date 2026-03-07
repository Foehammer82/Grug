"""scheduled_task_timezone

Adds a ``timezone`` column to ``scheduled_tasks`` so that cron-based recurring
tasks are evaluated in the guild's local timezone rather than always UTC.

Revision ID: 20260307_0001_scheduled_task_timezone
Revises: 20260304_0010_combatant_hidden
Create Date: 2026-03-07
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260307_0001_scheduled_task_timezone"
down_revision: Union[str, None] = "20260304_0010_combatant_hidden"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "scheduled_tasks",
        sa.Column(
            "timezone",
            sa.String(length=64),
            nullable=False,
            server_default="UTC",
        ),
    )


def downgrade() -> None:
    op.drop_column("scheduled_tasks", "timezone")
