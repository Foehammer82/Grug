"""Add campaign scheduling fields

Revision ID: 20260304_0005_campaign_scheduling
Revises: 20260304_0004_channel_enabled
Create Date: 2026-03-04 14:00:00.000000

Adds:
  - campaigns.schedule_mode  ('fixed' | 'poll', default 'fixed')
  - calendar_events.campaign_id  (nullable FK → campaigns.id, ON DELETE SET NULL)
  - scheduled_tasks.event_id  (nullable FK → calendar_events.id, ON DELETE CASCADE)
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260304_0005_campaign_scheduling"
down_revision: Union[str, None] = "20260304_0004_channel_enabled"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -- campaigns.schedule_mode ------------------------------------------------
    op.add_column(
        "campaigns",
        sa.Column(
            "schedule_mode",
            sa.String(16),
            server_default="fixed",
            nullable=False,
        ),
    )

    # -- calendar_events.campaign_id -------------------------------------------
    op.add_column(
        "calendar_events",
        sa.Column("campaign_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        "ix_calendar_events_campaign_id",
        "calendar_events",
        ["campaign_id"],
    )
    op.create_foreign_key(
        "fk_calendar_events_campaign_id",
        "calendar_events",
        "campaigns",
        ["campaign_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # -- scheduled_tasks.event_id ----------------------------------------------
    op.add_column(
        "scheduled_tasks",
        sa.Column("event_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        "ix_scheduled_tasks_event_id",
        "scheduled_tasks",
        ["event_id"],
    )
    op.create_foreign_key(
        "fk_scheduled_tasks_event_id",
        "scheduled_tasks",
        "calendar_events",
        ["event_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    # -- scheduled_tasks.event_id
    op.drop_constraint("fk_scheduled_tasks_event_id", "scheduled_tasks", type_="foreignkey")
    op.drop_index("ix_scheduled_tasks_event_id", table_name="scheduled_tasks")
    op.drop_column("scheduled_tasks", "event_id")

    # -- calendar_events.campaign_id
    op.drop_constraint("fk_calendar_events_campaign_id", "calendar_events", type_="foreignkey")
    op.drop_index("ix_calendar_events_campaign_id", table_name="calendar_events")
    op.drop_column("calendar_events", "campaign_id")

    # -- campaigns.schedule_mode
    op.drop_column("campaigns", "schedule_mode")
