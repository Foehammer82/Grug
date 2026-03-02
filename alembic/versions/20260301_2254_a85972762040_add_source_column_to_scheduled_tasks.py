"""add_source_column_to_scheduled_tasks

Revision ID: a85972762040
Revises: merge_reminders_001
Create Date: 2026-03-01 22:54:43.633072
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a85972762040"
down_revision: Union[str, None] = "merge_reminders_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "scheduled_tasks",
        sa.Column(
            "source", sa.String(length=16), server_default="discord", nullable=False
        ),
    )


def downgrade() -> None:
    op.drop_column("scheduled_tasks", "source")
