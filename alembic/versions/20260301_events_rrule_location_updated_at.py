"""add_rrule_location_updated_at_to_calendar_events

Add rrule, location, and updated_at columns to the calendar_events table
to support recurring events and richer event metadata.

Revision ID: 20260301_events_rrule
Revises: a85972762040
Create Date: 2026-03-01
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260301_events_rrule"
down_revision: Union[str, None] = "a85972762040"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "calendar_events",
        sa.Column("rrule", sa.String(512), nullable=True),
    )
    op.add_column(
        "calendar_events",
        sa.Column("location", sa.String(256), nullable=True),
    )
    op.add_column(
        "calendar_events",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("calendar_events", "updated_at")
    op.drop_column("calendar_events", "location")
    op.drop_column("calendar_events", "rrule")
